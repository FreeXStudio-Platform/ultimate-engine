"""Git pre-commit / pre-push scanner: block a classified doc staged outside ``docs/confidential/``.

The doc-system moat (RULEBOOK L14, CLASSIFICATION.md) says only ``classification: public`` documents
may be committed to a public/tracked location; ``confidential`` and ``secret`` docs live ONLY under
``docs/confidential/``. This hook is the last-line, index-level enforcement of that: it reads the
**staged bytes** of every added/modified file (``git diff --cached``), parses the doc-system YAML
header with the same ``classification.parse_header`` the engine uses, and BLOCKS the commit/push if a
non-public header is staged at any path outside ``docs/confidential/``.

Design (matches the engine's fail-closed posture):

* **Staged bytes, not working tree** — we scan exactly what is in the index (``git show :<path>``), so
  a clean working-tree copy can never mask a classified blob that was actually staged.
* **Fail-closed on ambiguity** — a file that git reports as staged but whose staged blob cannot be
  read is reported as a BLOCKING finding, never silently skipped. An un-decodable (binary) staged blob
  is simply not a Markdown doc and is skipped (it has no doc-header to leak), which is safe: the header
  parser only ever matches text front-matter.
* **Header is authority** — classification comes from the parsed header (the engine's single source of
  truth), NOT from the filename. A public-looking filename with a ``secret`` header is still blocked.
* **Deterministic + side-effect-free** — reads only; sorts findings by path; no writes, no network.

Public API:

* ``iter_staged_files(repo_root) -> list[str] | None`` — repo-relative paths of added/modified staged
  files, or ``None`` if git could not be asked (fail-closed; ``scan_staged`` turns that into a
  BLOCKING finding).
* ``read_staged_bytes(repo_root, rel_path) -> bytes | None`` — the staged blob, or ``None`` if unreadable.
* ``is_inside_confidential_dir(rel_path, repo_root) -> bool`` — path-containment test (blocks ``../``
  escape) **against the repository being scanned**, which is why ``repo_root`` is required.
* ``scan_staged(repo_root, *, files=None) -> list[Finding]`` — the core, git-free-testable check.
* ``main(argv=None) -> int`` — CLI entry (exit 0 = clean, 1 = blocked, 2 = usage/IO error).
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path, PurePosixPath

from tools.docgen import engine_config
from tools.docgen.classification import (
    _FRONT_MATTER_RE,
    UNPARSEABLE_LEADING_BLOCK,
    parse_header,
    unparseable_leading_block,
)
from tools.docgen.hooks.materialise import (
    _CANDIDATE_WIDE,
    looks_utf16_or_32,
    normalise_for_scanning,
)
from tools.docgen.models import Finding, Severity, Tier

# The one sanctioned home for non-public (confidential/secret) documents (CLASSIFICATION.md).
# Resolved via engine_config's docSystem.confidentialDir — see ../../../CONFIGURATION.md.
VAULT_DIR = engine_config.confidential_dir_relative()

# WHICH staged files are inspected for a classification header — a DENYLIST, and the direction is
# the whole fix (`OG-213`, the Phase-7 moat red-team's BREACH #1).
#
# It used to be an ALLOWLIST of nine document suffixes, and `_looks_like_doc` SKIPPED anything else.
# So a `classification: secret` document saved as `notes.mkd` — a standard, GitHub-rendered Markdown
# alias — or with NO extension at all, was never read, and reached the remote through BOTH placement
# gates with an affirmative "clean" line. That directly contradicted this module's own stated
# principle, three lines up: *"Header is authority ... NOT from the filename."* An earlier note here
# even reasoned that the list must stay in sync with `stamps.py`'s suffix set — treating the wrong
# instrument as the thing to keep true.
#
# **An allowlist fails UNSAFE**: an unrecognised extension means "not checked", and the failure is a
# leaked classified document. **A denylist fails SAFE**: an unrecognised extension means "read the
# content and let the header decide", and the worst failure is a false refusal of a data file —
# which `OG-41` already accepted as the safe direction. So placement is now decided by CONTENT for
# every file EXCEPT the structured-data formats a prose document is never written in. `OG-41`
# deliberately excluded exactly these (a `.yaml`/`.json`/`.csv` legitimately opens with `---` and
# `key: value` and is not a document); keeping them out preserves that decision while closing the
# hole for everything the allowlist could not enumerate — including the next Markdown alias nobody
# thought of, and the no-extension file.
#
# A binary blob still decodes to `None` in `_decode_for_scanning` (cheap NUL probe) and is skipped —
# so "read every file" does not mean "scan every JPEG for YAML", it means one `cat-file` plus an 8 KB
# probe, the same blobs the secret scan already reads. Only a genuine doc-system header (checked by
# `_has_doc_header`) outside the vault blocks, at ANY extension, or none.
_NON_DOC_SUFFIXES = frozenset({
    ".yaml", ".yml", ".json", ".csv", ".tsv", ".toml", ".ini", ".cfg", ".lock",
})

# The document extensions this gate is CERTAIN carry prose — documentation of the common case only
# (.md/.markdown/.mdx/.txt/.rst/.adoc/.org/.html/.htm), and for the `stamps.py` symmetry note; the
# placement filter no longer gates on this list — content does, via `_NON_DOC_SUFFIXES` above, which
# IS live. `_FRONT_MATTER_RE` matches only a leading `---`-fenced block, so an ordinary file of any
# of these types with no such block is unaffected: this decides WHAT is inspected, not what is a
# header. No executable constant is kept here: a list nothing reads goes stale
# exactly like a comment, but a comment does not also draw an "unused global" finding forever.

_GATE = "staged-content-scanner"


_LOG = logging.getLogger(__name__)


def _repo_root_default() -> Path:
    """The repository being committed — the CWD's git root, falling back to this file's location.

    This is a git hook helper, and the hook has already ``cd``-ed to the repository whose index is
    being written. Deriving the root from THIS FILE's location instead meant the scanner inspected
    the index of whatever checkout the *module* lives in, which is the same thing only when the
    engine is vendored inside the repository under test.

    It matters in the one place it is hardest to notice: `tools.health`'s behavioural probe runs the
    installed hook in a throwaway repository with `PYTHONPATH` pointing at the engine. Under the old
    rule the placement gate scanned the ENGINE's index — always clean — so the probe reported the
    hook as gating while that dimension was never exercised at all. A guard that cannot fail in the
    harness that certifies it is worse than an absent one.

    ``--repo-root`` still overrides, and the fallback keeps the previous behaviour for a caller with
    no git context.
    """
    try:
        proc = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            capture_output=True, text=True, timeout=10, check=False,
            encoding="utf-8", errors="surrogateescape",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        # No git on PATH, no git context, or a decode failure — all documented above as "a caller
        # with no git context", which this fallback exists to serve. Logged at debug so the normal
        # no-git case stays quiet while the fallback is still traceable if ever suspected.
        _LOG.debug("_repo_root_default: git rev-parse failed, falling back to module path: %s", exc)
    return Path(__file__).resolve().parents[3]


def iter_staged_files(repo_root: Path) -> list[str] | None:
    """Return repo-relative POSIX paths of files added or modified in the git index.

    Uses ``git diff --cached --name-only --diff-filter=ACMRT`` so deletions (D) are ignored — a deleted
    file cannot leak content. ``scan_staged`` accepts an explicit ``files`` list so the core logic is
    git-free-testable.

    ⚠ **THIS RETURNED AN EMPTY LIST ON A GIT ERROR, AND EVERY CALLER READS EMPTY AS "CLEAN".** The
    docstring asserted the opposite of what the code did — *"callers that need to distinguish 'no
    staged files' from 'git error' should use ``main`` (which surfaces the error)"* — and ``main``
    surfaced nothing: it called ``scan_staged``, got no findings, and returned 0. Measured through the
    documented CLI with a ``git`` that fails only ``diff --cached --name-only``: the same index that
    exits **1 (BLOCKED)** under real git exited **0 with zero output**.

    That is `OG-118` with the halves swapped. `scan_manifest` was made fail-closed on every
    unreadable-object path in this same module; the sibling enumerator stayed permissive, so the
    module had one stated contract and two behaviours again.

    Now: ``None`` means "git could not be asked", which ``scan_staged`` turns into a BLOCKING finding.
    An empty list still means, and only means, "git answered: nothing staged". The ``timeout`` and the
    widened ``except`` are part of the same property — ``TimeoutExpired`` is a ``SubprocessError`` and
    was not caught here at all, so a hung ``git`` produced a traceback rather than a diagnosis.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z"],
            cwd=str(repo_root),
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    # ``-z`` gives NUL-separated paths (safe for any filename); decode as UTF-8, drop empties.
    raw = proc.stdout.decode("utf-8", errors="replace")
    return sorted(p for p in raw.split("\x00") if p)


def read_staged_bytes(repo_root: Path, rel_path: str) -> bytes | None:
    """Read the STAGED blob of ``rel_path`` from the index (``git show :<path>``).

    Returns the staged bytes, or ``None`` if the blob cannot be read (git error / path not in index).
    Reading the index — not the working tree — is the whole point: it is the bytes that would actually
    be committed. ``None`` is treated fail-closed by ``scan_staged`` (reported as a blocking finding).
    """
    try:
        proc = subprocess.run(
            ["git", "show", f":{rel_path}"],
            cwd=str(repo_root),
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout


def _is_staged_gitlink(repo_root: Path, rel_path: str) -> bool:
    """True iff ``rel_path`` is staged as a submodule gitlink (index mode ``160000``).

    A gitlink's staged "content" is a commit sha that lives in ANOTHER repository, so
    ``git show :<path>`` fails here with ``fatal: bad object`` and ``read_staged_bytes`` returns
    ``None`` — indistinguishable from a genuinely unreadable blob by the ``None`` alone, but benign:
    a gitlink is a pointer, not a document, and cannot carry a classification header. Telling the two
    apart is what lets the fail-closed block in ``scan_staged`` stay strict for real blobs while a
    legitimate submodule COMMIT is allowed through. This is the commit-time twin of
    ``scan_manifest``'s non-blob skip at push time (`OG-226`): neither treats a non-file object as
    file content. A gitlink cannot BE a secret document — it is a 20-byte object reference — so
    skipping it can never let a classified file slip past the gate.

    A git failure returns ``False`` **on purpose**: if we cannot confirm the entry is a gitlink, the
    caller must fall through to the fail-closed block, because a real unreadable blob must never be
    assumed benign just because git happened to error.

    **Why a false positive here cannot cause an evasion.** ``rel_path`` reaches git as a PATHSPEC, so
    a file literally named ``*`` or ``:x`` could in principle match an unrelated staged entry and make
    this return ``True`` for the wrong reason. It is inert regardless, because ``scan_staged`` consults
    this verdict ONLY after ``read_staged_bytes`` already returned ``None`` for that path — and a path
    that carries a readable classified blob never reads as ``None`` (``git show :<path>`` is an exact
    stage-0 index lookup, not a pathspec), so it is decoded and BLOCKED before this is called. The
    verdict only ever decides skip-vs-block for an already-unreadable entry; it never decides whether
    readable content is scanned (`OG-234`, confirmed by the adversarial verifier's worst-case labs).
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--stage", "-z", "--", rel_path],
            cwd=str(repo_root),
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    # `git ls-files --stage` prints "<mode> <sha> <stage>\t<path>"; a gitlink's mode is 160000.
    return proc.stdout.decode("utf-8", errors="replace").startswith("160000 ")


@lru_cache(maxsize=8)
def _vault_is_gitignored(vault: str, repo_root: str) -> bool:
    """True when the configured vault is actually IGNORED BY GIT (`OG-167`).

    **The anchor has to be something an environment variable cannot move.** `OG-102` refused a
    vault that contains the rule layer, and both halves of that invariant are read from the same
    operator-controlled config — so setting BOTH at once satisfies it and disables the gate:

        ENGINE_CONFIDENTIAL_DIR=docs                      -> refused (OG-102), commit blocked
        ENGINE_CONFIDENTIAL_DIR=docs ENGINE_DOC_SYSTEM_DIR=rules -> ACCEPTED, secret doc committed

    Measured exactly that way. An invariant relating two things the attacker controls is not an
    invariant; it is a puzzle with a solution.

    Git's ignore rules are the anchor. A vault is a place whose contents are NEVER committed —
    `docs/confidential/` is gitignored by design and `STRUCT-07` asserts it. `docs` is not ignored,
    and neither is `rules`. So a "vault" git would happily commit is not one, and nothing is
    treated as inside it.

    Fails CLOSED: if git cannot answer, the vault is not honoured, so a document must be genuinely
    public to pass. That is the safe direction — the cost is a false refusal, not a leak.
    """
    try:
        proc = subprocess.run(
            ("git", "-C", repo_root, "check-ignore", "-q", f"{vault.rstrip('/')}/"),
            capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    return proc.returncode == 0


def is_inside_confidential_dir(rel_path: str, repo_root: Path | str) -> bool:
    """True iff ``rel_path`` is contained within ``docs/confidential/`` (containment, not prefix match).

    Uses ``PurePosixPath`` containment so a sibling like ``docs/confidential-notes/x.md`` is correctly
    treated as OUTSIDE, and normalizes ``.``/``..`` segments so ``docs/confidential/../secret.md`` (which
    resolves outside) is NOT accepted. Backslashes are normalized to ``/`` so a Windows-style staged path
    is handled identically (git always reports forward slashes, but this keeps the helper robust).

    ⚠ **``repo_root`` IS REQUIRED BECAUSE THIS FUNCTION USED TO INVENT ONE.** The `OG-167` vault
    anchor below was evaluated against ``_repo_root_default()`` — *the current working directory's*
    git root — while ``scan_manifest``/``scan_staged`` read every blob from the ``repo_root`` they
    were handed. Identical manifest, identical target repository, identical blob; only the CWD
    differed:

        cd $HOST && … --repo-root $HOST --manifest m   -> exit 1, BLOCKED   (vault not gitignored)
        cd $OTHER && … --repo-root $HOST --manifest m  -> exit 0, silent

    $HOST genuinely commits its "vault" and the scan cleared it. Worse than a CWD trick: when the CWD
    is not a git repository at all, ``_repo_root_default`` falls back to *the engine's own checkout*,
    whose ``docs/confidential/`` **is** gitignored — so a vendored engine invoked from any non-git
    directory against a host project inherited the wrong answer by default. Measured that way too.

    ``_repo_root_default`` was itself rewritten for exactly this class ("the scanner inspected the
    index of whatever checkout the *module* lives in"); the fix landed on blob reading and not on the
    vault anchor. So the parameter is required rather than defaulted: a caller cannot forget an
    argument the signature will not let it omit, and `classify_file` took the same self-containment
    lesson one door over.
    """
    normalized = rel_path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    # Reject any path that tries to climb out with ``..``; such a path is never legitimately "inside".
    if ".." in candidate.parts:
        return False
    confidential = PurePosixPath(VAULT_DIR)
    if not (candidate == confidential or confidential in candidate.parents):
        return False
    # **The vault must be gitignored** (`OG-167`). See `_vault_is_gitignored`: an operator can move
    # both halves of `OG-102`'s invariant at once, so containment alone is not enough — the vault
    # itself has to be a place git will not commit.
    if not _vault_is_gitignored(VAULT_DIR, str(repo_root)):
        _LOG.error(
            "confidentialDir=%r is NOT git-ignored, so it is not a vault — anything placed there "
            "would be committed. Nothing is treated as inside it. REFUSED. (OG-167)",
            VAULT_DIR,
        )
        return False
    return True


def _might_carry_classification(rel_path: str) -> bool:
    """True unless this path is a known structured-data format that is never a prose document.

    A DENYLIST, deliberately (`OG-213`): an unknown or absent extension is READ, and its CONTENT
    decides, because the alternative — an allowlist of document suffixes — skipped `.mkd` and
    no-extension classified documents and let them reach the remote. The header, not the filename, is
    authority; this function only spares the gate from decoding a `.yaml`/`.json` data file that
    `OG-41` already ruled out of scope.

    An EMPTY path is never a document: the `pre-push` manifest lists path-LESS objects (the commit
    and tree objects themselves) as `<sha>\\t` with no name, and turning the denylist into a
    "read anything without a known data suffix" rule made those objects READ — `git cat-file blob`
    on a commit sha exits 128 and raised a BLOCKING finding on every push (an adversarial verifier
    caught it the same round the denylist landed). A name is required before a suffix can be judged.
    """
    if not rel_path.strip():
        return False
    return PurePosixPath(rel_path.replace("\\", "/")).suffix.lower() not in _NON_DOC_SUFFIXES


def classify_file(rel_path: str, text: str, repo_root: Path | str) -> Finding | None:
    """The placement decision for ONE file's text. Shared by the index scan and the tree scan.

    Extracted 2026-08-20 so `pre-push` can apply the identical rule to the commits being published.
    The commit-time gate runs only for `git commit`; `git merge`, `git cherry-pick` and `git rebase`
    all create commits without it, and nothing re-checked placement at push time — so a classified
    document could reach the remote with every gate green and no bypass flag used.

    **Self-contained on purpose (2026-08-21).** This function used to emit a finding saying a
    document was *"placed outside docs/confidential/"* without ever checking whether it was — the
    containment test lived only in the two callers, as a pre-filter. Any third caller that forgot it
    would produce a message that is simply false about the path it names. The first retained
    counter-example written for this module caught it. The callers still pre-filter (it saves
    reading blobs that cannot matter); this is now a correctness property of the function rather
    than a convention its callers must remember.
    """
    if is_inside_confidential_dir(rel_path, repo_root):
        return None
    # A second, FOREIGN header syntax exists in this tree: documents inherited from the project this
    # engine was extracted from declare `<!-- classification: X -->`, whose vocabulary (INTERNAL /
    # GITHUB / COMMERCIAL) this engine does not implement. The placement gate could not see that
    # syntax at all, so an author following the engine's own (stale) AUTHORING_PROMPT instructions
    # could write `<!-- classification: secret -->` and commit it anywhere, believing they were
    # protected. Handled fail-closed: only the literal value `public` passes.
    legacy = _LEGACY_CLASSIFICATION_RE.search(text)
    if legacy is not None and _FRONT_MATTER_RE.search(text) is None:
        value = legacy.group(1)
        if value.strip().lower() == Tier.PUBLIC.value:
            return None
        return Finding(
            gate=_GATE,
            message=(
                f"'{rel_path}' declares classification='{value}' in the legacy "
                f"`<!-- classification: … -->` form. This engine's tiers are "
                f"{', '.join(t.value for t in Tier)}; anything else is refused rather than "
                f"guessed (RULEBOOK L14). Use YAML front-matter, or write `public`."
            ),
            severity=Severity.CRIT,
            blocking=True,
            evidence=rel_path,
        )
    header = parse_header(text)
    if header.classification is Tier.PUBLIC:
        return None
    # Only treat it as a real classified doc if a header was actually present: a header-less README
    # parses to the SECRET sentinel (correct fail-closed default for the RENDER gate) but is
    # legitimate outside the vault.
    if not _has_doc_header(text):
        # "I cannot parse this" is NOT "there is nothing here to protect".
        # Four rounds of widening the comment grammar each left a shape the next round found
        # fail-open here, because this branch reads an unparseable leading block and a genuinely
        # header-less README as the same answer. If the block STARTS with a comment and a
        # classification header sits behind a `-->` where base 1.0.12's token could have reached it,
        # refuse and name the line — the author reformats one line, and every shape nobody has
        # generated yet is a refusal instead of a silent pass.
        #
        # `_has_doc_header` is handed IN rather than re-implemented inside `tools.lib`.
        # It is this module's own authoritative answer to "does this declare a classification?",
        # and it is the same predicate the fail-open branch two lines above turns on — so the
        # verdict and the branch it guards cannot disagree about what a header is.
        offending = unparseable_leading_block(text, declares_classification=_has_doc_header)
        if offending is not None:
            return Finding(
                gate=_GATE,
                message=(
                    f"'{rel_path}': {UNPARSEABLE_LEADING_BLOCK}. Offending line: {offending!r}"
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=rel_path,
            )
        return None
    return Finding(
        gate=_GATE,
        message=(
            f"'{rel_path}' has classification='{header.classification.value}' but is placed "
            f"outside '{VAULT_DIR}/'. Non-public docs may only live in the confidential "
            f"vault (RULEBOOK L14 / CLASSIFICATION.md)."
        ),
        severity=Severity.CRIT,
        blocking=True,
        evidence=rel_path,
    )


# How far into a blob to look for the NUL that marks genuinely binary content, and how much
# replacement-character noise a real document may carry. Both are deliberately generous: the
# failure this guards is a classified document being DISCARDED, not a JPEG being scanned.
_BINARY_NUL_WINDOW = 8192
_MAX_REPLACEMENT_RATIO = 0.30


def _decode_for_scanning(data: bytes) -> str | None:
    """Decode a blob for the L14 placement scan, transcoding UTF-16/32 first. ``None`` if binary.

    ⚠ **Both scan paths in this module used to do a bare ``data.decode("utf-8")`` inside a ``try``
    whose ``except UnicodeDecodeError`` body was ``continue``** — so a `classification: secret`
    document written as UTF-16 (Notepad "Unicode", PowerShell redirection) decoded to nothing, was
    skipped, and **committed and pushed clean**. Proven end-to-end through the real installed hook:
    the UTF-8 copy was refused, the byte-identical UTF-16 copy printed *"classification placement
    clean."* and exited 0.

    The root fix already existed. `materialise.normalise_for_scanning` was written for exactly this
    class and wired into the *secret* path in the same hook, reading the same blobs — and
    `OPEN_GATES.md` `OG-56` recorded the class as "closed at the ROOT". It was closed for one of the
    two consumers. `docs/process/RULES.md`:62 names UTF-16 as its own exemplar of a fix that MOVED a
    hole rather than closing it; this was that sibling, still standing (`OG-84`).
    """
    normalised, transcoded_from = normalise_for_scanning(data)

    # ⚠ **"NOT STRICT UTF-8" IS NOT "BINARY", AND EQUATING THEM WAS A HOLE THIS WIDE:**
    # a `classification: secret` document that is 99.5% ASCII with ONE Windows-1252 byte — 0x92,
    # the curly apostrophe you get pasting from Word — decoded to nothing, was treated as binary,
    # and **committed and pushed clean** through both placement gates. Measured by Pass 7 through
    # the real installed hook.
    #
    # The previous fix narrowed the hole from "UTF-16 is unreadable" to "anything that is not clean
    # UTF-8 or clean UTF-16 is unreadable" — still wide enough to walk a classified document
    # through, which is `LESSONS.md` L-26 exactly.
    #
    # So: decode leniently, and decide binary-ness from a REAL binary signal rather than from one
    # undecodable byte. `normalise_for_scanning` already applies the same leniency on its
    # transcoding branch, so the two paths now agree about what "readable" means.
    if transcoded_from is None and b"\x00" in normalised[:_BINARY_NUL_WINDOW]:
        # A NUL in the head is the actual signature of binary content — **but only when no wide
        # reading was found.** That qualifier is load-bearing and its absence was a live hole for
        # one commit: `normalise_for_scanning` became ADDITIVE (it appends readable views to the
        # original bytes instead of replacing them, so a misclassified encoding can no longer
        # destroy the payload), which means the raw NUL-bearing prefix is still there by design.
        # Testing the head unconditionally therefore rejected every wide-encoded document as
        # "binary" — the exact `OG-84` failure, re-entering through the fix for `OG-101`.
        #
        # When `transcoded_from` is set, a readable view exists further down the buffer and the
        # replacement-ratio test below is what decides whether it is really text.
        return None
    # ⚠ **A WIDE-ENCODED BLOB IS DECODED CLEANLY HERE, not read out of the additive buffer** (`OG-213`).
    # `normalise_for_scanning` returns the ORIGINAL wide bytes FIRST and appends a UTF-8 view, which
    # is right for the SECRET scan (it greps the union and does not care about position). But this
    # decoder feeds the PLACEMENT gate, whose front-matter regex is `\A`-anchored: on the additive
    # buffer the header sits AFTER the mojibake prefix, at position ≠ 0, so a UTF-16 `classification:
    # secret` document read as a header-less README and passed — `OG-84` re-entering through the one
    # consumer `OG-56`'s "closed at the ROOT" never covered. Decoding the raw bytes with the detected
    # wide codec puts a real header back at position 0; a non-wide blob keeps the (identical, for
    # UTF-8) additive decode.
    wide = looks_utf16_or_32(data)
    if wide is not None:
        text = data.decode(wide, errors="replace")
    else:
        text = normalised.decode("utf-8", errors="replace")
    # A CJK-heavy wide document lowers NUL density below the detector's UTF-16 threshold, or fails its
    # UTF-32 quad test and is read AS UTF-16 with the wrong stride — either way the chosen decode can
    # leave a real front-matter header off position 0, where the `\A`-anchored placement gate misses
    # it (`OG-227`, the `OG-101`/`OG-84` CJK-padding class re-entering the placement path once
    # content-classification became the sole gate). When the blob carries NULs but no header
    # surfaced, try every candidate wide codec and prefer a CLEAN decode that puts a header at pos 0.
    if b"\x00" in data[:_BINARY_NUL_WINDOW] and not _has_doc_header(text):
        for codec in _CANDIDATE_WIDE:
            try:
                candidate = data.decode(codec, errors="replace")
            except (UnicodeDecodeError, LookupError):
                continue
            if _has_doc_header(candidate):
                text = candidate
                break
    if not text:
        return None
    # A high replacement ratio means it really was not text. One stray byte in a document is far
    # below this; a JPEG is far above it. **But a classified document whose HEADER is ASCII at
    # position 0 and whose BODY is an undecodable NARROW legacy encoding \u2014 Shift-JIS, EUC-JP, GB18030,
    # a Japanese/Chinese editor's default \u2014 decodes to >30% U+FFFD as UTF-8 and was DISCARDED here,
    # walking its header past the placement gate** (`OG-232`, the `OG-227` CJK class one encoding
    # family over: narrow, not wide, so `looks_utf16_or_32` never fires and the candidate-codec retry
    # above does not apply). The placement gate reads only the header, and a genuinely binary blob has
    # no front-matter header at pos 0, so a blob whose header survives there is kept regardless of how
    # undecodable its body is.
    if text.count("\ufffd") / len(text) > _MAX_REPLACEMENT_RATIO and not _has_doc_header(text):
        return None
    return text


def _unreadable(rel: str, sha: str, why: str) -> Finding:
    """A blocking finding for a staged object the gate could not read.

    Fail-closed, matching `scan_staged`. An object git reports as staged but will not hand over is
    not "probably fine" — it is the one case where the gate has no idea what is being published.
    """
    return Finding(
        gate=_GATE,
        message=(
            f"Staged blob {sha[:12]} for '{rel}' could not be read; refusing to pass it "
            f"(fail-closed — an unreadable staged doc must not be assumed public; {why})."
        ),
        severity=Severity.CRIT,
        blocking=True,
        evidence=rel,
    )


def scan_manifest(repo_root: Path, manifest: Path) -> list[Finding]:
    """Apply the placement rule to (blob-sha, path) pairs, reading each blob with ``git cat-file``.

    **Blob-true by construction, and that is the whole point.** The previous version walked a
    directory that ``pre-push`` had materialised with ``git archive``. An independent adversarial
    pass proved that indirection is exploitable in at least four ways, none of which needs a bypass
    flag: ``git archive`` honours ``export-ignore`` from a tracked *or untracked* ``.gitattributes``
    (so a path simply vanishes from the scan while the real blob reaches the remote); it applies
    smudge filters and ``working-tree-encoding`` (so the bytes scanned are provably not the bytes
    recorded); two paths differing only in case collide on a case-insensitive filesystem such as
    macOS APFS (one blob silently overwrites the other); and a symlink is not a regular file, so a
    directory walk skips it entirely.

    Reading the object with ``git cat-file blob`` bypasses every one of those, because it is the
    object, not a rendering of it.

    Manifest format: one record per line, ``<blob-sha><TAB><path>``. Paths are reported as given, so
    the caller controls what a finding is named after.
    """
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    # ⚠ **ONE NON-UTF-8 BYTE USED TO DISABLE THIS ENTIRE GATE** (`OG-152`).
    #
    # This read was `manifest.read_text(encoding="utf-8")` inside `except (OSError, ValueError):
    # return findings`. `UnicodeDecodeError` IS a `ValueError`, so a single undecodable byte
    # anywhere in the manifest — a filename with an invalid byte is enough, and git tracks such
    # paths quite happily — returned an EMPTY findings list, which every caller reads as "clean".
    # Measured through the real entry point: a `classification: secret` document listed in the same
    # manifest exited **1 (refused)** on its own, and **0 (accepted)** once one bad byte was added.
    # `tools/hooks/pre-push` builds this manifest, so that is the push-time L14 gate failing OPEN.
    #
    # Two changes. A path is bytes, not text, so it is decoded with `surrogateescape`, which never
    # raises and round-trips an undecodable byte — the scan proceeds and the odd path is simply
    # carried through as given. And a genuine read failure (`OSError`) is now a BLOCKING finding
    # rather than a silent empty pass, matching this module's stated contract and `scan_staged`.
    try:
        raw = manifest.read_bytes()
    except OSError as exc:
        findings.append(
            Finding(
                gate=_GATE,
                message=(
                    f"the published-object manifest at '{manifest}' could not be read; refusing to "
                    f"pass the push (fail-closed — an unreadable manifest is not an empty one; {exc})."
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=str(manifest),
            )
        )
        return findings
    lines = raw.decode("utf-8", errors="surrogateescape").splitlines()
    for line in lines:
        if "\t" not in line:
            continue
        sha, rel = line.split("\t", 1)
        if (sha, rel) in seen:
            continue
        seen.add((sha, rel))
        if not _might_carry_classification(rel) or is_inside_confidential_dir(rel, repo_root):
            continue
        # ⚠ **THE MANIFEST LISTS TREE AND COMMIT OBJECTS, NOT ONLY BLOBS** (`OG-226`). `pre-push`
        # builds it from `git rev-list --objects`, which emits a TREE for every directory (with the
        # directory's PATH — `docs`, `tools/blueprint`) and the commit itself (empty path). A tree or
        # commit is not a document, and `git cat-file blob` on one exits 128. `OG-213`'s empty-path
        # fix skipped only the commit and the root tree; every SUBTREE still reached the blob read —
        # a verifier measured **11 false blocking findings and exit 1** on the real push manifest, so
        # this gate refused every push. Read the object TYPE first and skip a non-blob. A missing sha
        # (the type probe fails) falls through to the blob read, which fails and is fail-closed.
        try:
            type_proc = subprocess.run(
                ("git", "-C", str(repo_root), "cat-file", "-t", sha),
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            type_proc = None
        if type_proc is not None and type_proc.returncode == 0 and type_proc.stdout.strip() != "blob":
            continue  # a tree or commit object, not a document
        # ⚠ **THESE THREE EXITS USED TO `continue`, AND THIS FUNCTION IS THE PUSH-TIME GATE**
        # (`OG-118`). The module docstring states fail-closed as a property of the module — *"a
        # file that git reports as staged but whose staged blob cannot be read is reported as a
        # BLOCKING finding, never silently skipped"* — and `scan_staged` implements it. This
        # function did the opposite on every unreadable-object path, including
        # `subprocess.SubprocessError`, which covers the `TimeoutExpired` its own `timeout=60`
        # can raise. Measured: a manifest naming a nonexistent blob sha exited **0, CLEAN**, while
        # the same condition through `scan_staged` produced a blocking CRIT. One module, two
        # contracts, and the push-time half was the permissive one.
        try:
            proc = subprocess.run(
                ("git", "-C", str(repo_root), "cat-file", "blob", sha),
                capture_output=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            findings.append(_unreadable(rel, sha, f"{type(exc).__name__}: {exc}"))
            continue
        if proc.returncode != 0:
            findings.append(
                _unreadable(rel, sha, f"git cat-file exited {proc.returncode}")
            )
            continue
        text = _decode_for_scanning(proc.stdout)
        if text is None:
            # No readable text in ANY candidate encoding — see `normalise_for_scanning`, which
            # tries every wide decoding before this returns None. That is a real binary object,
            # which carries no doc-system header to leak, and is the one benign case here.
            continue
        found = classify_file(rel, text, repo_root)
        if found is not None:
            findings.append(found)
    return sorted(findings, key=lambda f: (f.evidence, f.message))


def scan_staged(
    repo_root: Path,
    *,
    files: list[str] | None = None,
) -> list[Finding]:
    """Core check: return a BLOCKING ``Finding`` for every classified doc staged outside the vault.

    For each staged Markdown file (``files`` explicit list, or discovered via ``iter_staged_files``):
      1. skip files already inside ``docs/confidential/`` (that is where they belong);
      2. read the STAGED bytes; if unreadable -> a blocking finding (fail-closed);
      3. parse the doc-system header; if ``classification`` is CONFIDENTIAL or SECRET -> a blocking
         finding naming the path and tier.

    A file with a ``public`` header, or with no doc-system header at all (e.g. an ordinary README), is
    clean — only an actual non-public classification outside the vault blocks. Findings are returned
    sorted by evidence path for deterministic output.
    """
    findings: list[Finding] = []
    if files is not None:
        staged = files
    else:
        enumerated = iter_staged_files(repo_root)
        if enumerated is None:
            # Fail-closed, matching `scan_manifest`'s unreadable-object paths and this module's
            # stated posture. "git would not tell us what is staged" is the one case where the gate
            # has no idea what is being committed, and it is not "nothing is staged".
            return [
                Finding(
                    gate=_GATE,
                    message=(
                        f"the staged file list for '{repo_root}' could not be read from git; "
                        f"refusing to pass the commit (fail-closed — a git failure is not an empty "
                        f"index)."
                    ),
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=str(repo_root),
                )
            ]
        staged = enumerated

    for rel_path in staged:
        if not _might_carry_classification(rel_path):
            continue
        if is_inside_confidential_dir(rel_path, repo_root):
            continue

        blob = read_staged_bytes(repo_root, rel_path)
        if blob is None:
            if _is_staged_gitlink(repo_root, rel_path):
                # A submodule pointer, not a document: its "staged bytes" are a commit sha in
                # another repository, so it reads as ``None`` for a benign reason. Skipping it lets a
                # legitimate submodule COMMIT through, while the fail-closed block below stays strict
                # for a real blob that genuinely will not read. `OG-234`; retained counter-example:
                # the submodule case in `tools/tests/hook_attacks.sh` and `test_staged_scanner.py`.
                continue
            findings.append(
                Finding(
                    gate=_GATE,
                    message=(
                        f"Staged file '{rel_path}' could not be read from the index; refusing to pass "
                        f"it (fail-closed — an unreadable staged doc must not be assumed public)."
                    ),
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=rel_path,
                )
            )
            continue

        text = _decode_for_scanning(blob)
        if text is None:
            # Genuinely binary => not a doc-system Markdown header; nothing to leak here.
            continue

        found = classify_file(rel_path, text, repo_root)
        if found is not None:
            findings.append(found)

    return sorted(findings, key=lambda f: (f.evidence, f.message))


# The legacy/foreign single-line form. Anchored to the head of the file so a mention of the syntax
# in prose (this engine documents it, in order to reject it) cannot be mistaken for a declaration.
_LEGACY_CLASSIFICATION_RE = re.compile(
    r"\A\s*(?:<!--[^>]*-->\s*)*?<!--\s*classification:\s*([^>|-]+?)\s*-->", re.IGNORECASE)


def _has_doc_header(text: str) -> bool:
    """True iff ``text`` begins with a doc-system YAML front-matter block that declares ``classification``.

    Guards against treating an ordinary (header-less) Markdown file as SECRET: ``parse_header`` returns
    the SECRET sentinel for header-less input (correct fail-closed default for the render gate), but the
    placement guard must only fire on files that genuinely carry a non-public classification header.
    """
    # Use ``.search`` (not ``.match``) to mirror ``parse_header`` exactly: whatever front-matter the
    # engine's parser would honor as the header is the same block this guard treats as authoritative.
    header_match = _FRONT_MATTER_RE.search(text)
    if header_match is None:
        return False
    return "classification" in header_match.group(1)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: scan the git index and block on any classified doc outside the vault.

    Exit codes: 0 = clean, 1 = one or more blocking findings, 2 = usage/IO error (e.g. not a git repo).
    Intended to be invoked from a ``pre-commit``/``pre-push`` shell hook.
    """
    parser = argparse.ArgumentParser(
        prog="staged-content-scanner",
        description=(
            "Block a confidential/secret doc-system document staged outside docs/confidential/."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help=(
            "Repository root to scan. Default: the CWD's git root, falling back to this file's "
            "location — see `_repo_root_default`. Whatever this resolves to is the repository "
            "whose blobs are read AND whose ignore rules decide the vault anchor; the two used to "
            "be able to disagree."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Scan (blob-sha<TAB>path) records read from FILE, fetching each blob with `git cat-file`. "
            "Used by pre-push over the objects being published, so placement is enforced on what is "
            "PUBLISHED — `git merge`, `git cherry-pick` and `git rebase` all create commits without "
            "pre-commit — and read blob-true, which a directory walk cannot be."
        ),
    )
    args = parser.parse_args(argv)

    if args.manifest:
        manifest = Path(args.manifest)
        if not manifest.is_file():
            sys.stderr.write(f"staged-content-scanner: --manifest '{manifest}' is not a file\n")
            return 2
        root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_default()
        tree_findings = scan_manifest(root, manifest)
        for finding in tree_findings:
            sys.stderr.write(f"[{finding.gate}] {finding.severity.value}: {finding.message}\n")
        if tree_findings:
            sys.stderr.write(
                f"staged-content-scanner: BLOCKED — {len(tree_findings)} classified doc(s) outside "
                f"'{VAULT_DIR}/' in the content being published.\n"
            )
            return 1
        return 0

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_default()

    if not (repo_root / ".git").exists():
        sys.stderr.write(
            f"staged-content-scanner: '{repo_root}' is not a git repository (no .git). \n"
        )
        return 2

    findings = scan_staged(repo_root)
    for finding in findings:
        sys.stderr.write(f"[{finding.gate}] {finding.severity.value}: {finding.message}\n")

    if findings:
        sys.stderr.write(
            f"staged-content-scanner: BLOCKED — {len(findings)} blocking finding(s) over the staged "
            f"index. A classified doc must live in '{VAULT_DIR}/' or declare "
            f"classification: public; a finding naming an unreadable index or blob means the gate "
            f"could not SEE what is staged, which is refused rather than assumed clean.\n"
        )
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
