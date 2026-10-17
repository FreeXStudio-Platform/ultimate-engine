"""Where did we stop — per node and per document, from evidence.

WHAT THIS ANSWERS THAT THE DEPTH LADDER DOES NOT
================================================
Phase 5 derived a six-rung ladder and reported each node's rung. That is a *measurement*. This is
the *report*: it collapses the ladder into the three states `BUILD_PLAN.md` row 6 asks for —
**sketched**, **documented**, **verified** — and it adds the half the ladder never covered, the
document's own lifecycle.

**The ladder is not re-derived here.** It is read from the model that owns it. A second derivation
of one fact is the defect this engine exists to catch, and `stopped_because` already names the exact
rung each node failed; this module's job is to say what that means and what it costs.

THE THREE STATES, AND WHY `verified` IS NOT SIMPLY RUNG 5
=========================================================
======================= ========================================================================
state                   what it means, and the evidence — **exactly what is measured**
======================= ========================================================================
``sketched``            rungs 0-1. The node is named, and perhaps says what it is for, but what is
                        inside it is not established.
``documented``          rungs 2-3, OR rung 4 or deeper whose owning document has not certified it —
                        its contents are **enumerable**; ``why`` names which rung it stopped at, or
                        the certification it lacks. ``documented`` and ``verified`` PARTITION the
                        rung-4-and-deeper nodes: a fully-pinned node whose owning document is not
                        verified is ``documented``, not a lesser ``verified``.
``verified``            **rung 4 or deeper** — enumerable AND read by a gate AND pinned by a retained
                        counter-example — plus an owning document that is governed, claims a
                        verified state, and carries a body-certifying stamp that still covers it.
======================= ========================================================================

**The exact wording lives in ``STATE_DEFINITIONS`` (below), which the renderer emits; this table is
a gloss on it, never a second source.** A Phase-7 verifier found this table saying ``rungs 2-4``
while the constant said ``rungs 2-3`` and the code classified 33 rung-4 nodes as ``documented`` —
three statements of one fact, all three wrong in a different way (`OG-217`, the `L-39` shape one
layer up from where it was first paid for). Change the constant; this prose follows it.

**These definitions were rewritten after three verifiers refuted the first ones.** The published
table said ``documented`` meant "contents, edges, gatekeepers and probes established" and
``verified`` meant "all of that, and…", while the code asked only for rung 2. Measured: **73 of 103
documented nodes failed the published definition**, and in a lab a module that no gate reads and no
counter-example names reported ``verified``. Two fixes, in opposite directions, because the two
halves were wrong in different ways:

* ``documented`` now says what rung 2 actually establishes — *enumerable* — instead of claiming the
  two rungs above it. The claim shrank to the evidence.
* ``verified`` now REQUIRES rung 4 or deeper, so it is genuinely "everything the ladder can
  establish, plus the document". The evidence grew to the claim.

**The rung numbers here are FLOORS, not points — because rung 5 is now populated.** Once a node's
owning document claims ``verified``, ``depth.py`` reads it at the ladder's top rung (``detail``, 5),
so a ``verified`` node can measure rung 5, not only rung 4. A definition that named ``rung 4`` as a
terminal value excluded the node's real rung — the `OG-217` `L-39` shape recurring one rung up, found
by a Phase-7 verifier attacking the fix for the rung-4 version of it. Both definitions say "or
deeper", and the pin below asserts the depth against the FLOOR constant so a future rung cannot
re-open the gap.

**The word "edges" is gone from both.** ``depth.py`` states plainly that edges are known for every
node and therefore discriminate nothing, so no rung tests them — a state that claimed them was
claiming a measurement that does not exist.

The ladder's top rung reads a header's CLAIM — Phase 5 corrected its own docstring for saying
otherwise, and that correction is what makes the split here necessary. ``verified`` is not the
claim: the stamp is found, **filtered to the kinds that certify a body**, its commit resolved, and
the body at that commit compared with the body now. A claim with no stamp behind it reports
``documented`` and says why.

**When the evidence cannot be gathered, the state falls — it never rises.** No git, no stamp, an
unreadable document: each lands as ``documented`` with the cause named, because "we could not check"
must never render as "we checked and it was fine" (`LESSONS.md` L-25 applied to a report rather than
a gate).

THE DOCUMENT LIFECYCLE — SIX STEPS, EACH READ FROM ITS OWNER
============================================================
`BUILD_PLAN.md` row 6 mandates *tag / wire / date / version / changelog / stamp*. Each is derived
from the artifact that owns it, and **none of them is enforced here**: `classification` already
gates the tag, `manifest_drift` the wire, `identity` and `stamps` the version and the stamp. This
reports which steps a document has completed. Two enforcers of one rule is the defect; a report
beside an enforcer is not.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tools.blueprint.model import tracked_paths

SKETCHED, DOCUMENTED, VERIFIED = "sketched", "documented", "verified"

# THE ONE DEFINITION OF EACH STATE. Data, not prose, and not two copies.
#
# It was two copies: this module's docstring and a hardcoded table in `render.py`. The definitions
# were corrected here and in the docstring and NOT in the renderer, so `COMPLETENESS.md` went on
# publishing "contents, edges, gatekeepers and probes" — the exact wording three verifiers refuted —
# while the module announced two sections above that the wording was gone. The fix landed in the one
# place no reader of the report ever looks, and the code change made the published table MORE wrong:
# `verified` now requires rung 4, so `documented` is no longer a subset of it, yet the table still
# said "all of that, and…". A retained probe now compares the rendered table with this constant.
STATE_DEFINITIONS: dict[str, str] = {
    SKETCHED: (
        "rungs 0-1 — the node is named, and may say what it is for, but what is inside it is not "
        "established"
    ),
    DOCUMENTED: (
        "rungs 2-3, or rung 4 or deeper whose owning document has not certified it as verified — its "
        "contents are **enumerable**; it may or may not also be read by a gate or pinned by a probe, "
        "and `why` names the rung it stopped at (or the certification it still lacks), which is the "
        "actionable half"
    ),
    VERIFIED: (
        "**rung 4 or deeper** — enumerable AND read by a gate AND pinned by a retained counter-example "
        "— plus an owning document that is governed, claims a verified state, and carries a "
        "body-certifying stamp that still covers it"
    ),
}
NODE_STATES: tuple[str, ...] = (SKETCHED, DOCUMENTED, VERIFIED)

LIFECYCLE_STEPS: tuple[str, ...] = ("tag", "wire", "date", "version", "changelog", "stamp")

# Rungs 0-1 are `sketched`; 2 and above are at least `documented`.
_DOCUMENTED_FROM_RUNG = 2
# `verified` demands the TOP of documented — rung 4, `pinned`, which by the ladder's contiguity also
# means enumerable and gated. Without this the state was reachable by a rung-2 node that no gate read
# and no counter-example named, purely because its owning document happened to be stamped.
_VERIFIED_FROM_RUNG = 4


def _stamp_covers_body(root: Path, rel: str) -> tuple[bool, str]:
    """Is there a stamp on this document whose commit still matches its body?

    Uses the engine's own stamp machinery — `identity.find_stamps` and `identity.body_matches` —
    rather than a second reading of the same format. Returns ``(ok, why)``; ``why`` is always
    populated on a negative so the report can say what was missing instead of just showing a cross.
    """
    from tools.docgen import identity

    path = root / rel
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"unreadable ({type(exc).__name__})"

    # ONLY the kinds that certify a body. `guards/identity.py` and `guards/stamps.py` both filter on
    # `certifies_body`; this did not, so a `session-state` stamp — which `identity.
    # DRIFT_SENSITIVE_KINDS` excludes precisely because drifting from its own stamp is its designed
    # behaviour — lifted nodes to `verified` while `corpus_check` reported CRITICAL on the same tree.
    # Two readers of one fact, disagreeing: the Rule 1 defect this module's docstring cites.
    stamps = [s for s in identity.find_stamps(text) if s.certifies_body]
    if not stamps:
        return False, "no body-certifying stamp in the document"

    # The question is "does ANY body-certifying stamp still cover the body", so an unresolvable or
    # path-absent stamp is SKIPPED, not treated as the verdict. Returning on the first was a false
    # negative the moment a document carried more than one: a re-stamp appended over a stale
    # `@ 0000000` placeholder left the stale one FIRST, and the lifecycle probe caught the real
    # covering stamp being reported as drift because the loop bailed before reaching it.
    reasons: list[str] = []
    for stamp in stamps:
        commit = getattr(stamp, "sha", "") or ""
        if not commit:
            reasons.append("a body-certifying stamp carries no commit sha")
            continue
        try:
            blob = subprocess.run(
                ["git", "-C", str(root), "show", f"{commit}:./{rel}"],
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            # An environment fact, not a fact about the document: if git is unavailable it is
            # unavailable for every stamp, so this aborts rather than mislabels. The state falls.
            return False, f"git unavailable, so the stamp could not be checked ({exc})"
        if blob.returncode != 0:
            # Split the two ways this fails, which the previous message conflated (a verifier read
            # "does not contain this path" for a commit that does not exist). `verified` here is
            # machine-local by design — the stamped commit only has to be in the LOCAL object store,
            # not reachable from a ref — so a clone lacking the object reports `documented` where the
            # author reports `verified`. That bound is pre-existing (the first-stamp code had it) and
            # is STATED in `OPEN_GATES.md` (`OG-231`) rather than closed, because requiring
            # reachability here would diverge this reader from the corpus `stamps` guard.
            exists = subprocess.run(
                ["git", "-C", str(root), "cat-file", "-e", f"{commit}^{{commit}}"],
                capture_output=True, timeout=60, check=False,
            ).returncode == 0
            reasons.append(
                f"stamped commit {commit[:8]} does not contain this path" if exists
                else f"stamped commit {commit[:8]} is not in this repository"
            )
            continue
        if identity.body_matches(blob.stdout, text):
            return True, f"stamp at {commit[:8]} still covers the body"
        reasons.append(f"the body has drifted from the stamp at {commit[:8]}")
    return False, "; ".join(reasons) or "the body has drifted from every stamped commit"


def node_states(root: Path, model: dict[str, Any]) -> dict[str, dict[str, str]]:
    """``{module id -> {"state": ..., "why": ...}}`` for every node in the model."""
    depths = model.get("depth", {}).get("modules", {})
    owner = model.get("ownership", {}).get("owner", {})
    container_doc = {c["id"]: c["document"] for c in model.get("containers", [])}
    governed = {
        d["path"]: d for d in model.get("documents", [])
        if d.get("tier") and not str(d.get("tier", "")).startswith("(")
    }

    # Adjudicate each owning document ONCE. Several containers share `ARCHITECTURE.md`, and a git
    # call per node would run it 105 times for 9 distinct answers.
    verdict: dict[str, tuple[bool, str]] = {}
    for doc in sorted(set(container_doc.values())):
        if not doc:
            continue
        record = governed.get(doc)
        if record is None:
            verdict[doc] = (False, "the owning document carries no doc-system header")
        elif record.get("verified_state") != "verified":
            verdict[doc] = (
                False,
                f"the owning document declares verified_state: {record.get('verified_state') or 'unset'}",
            )
        else:
            verdict[doc] = _stamp_covers_body(root, doc)

    levels = model.get("depth", {}).get("levels", [])

    def _rung(depth: int) -> str:
        return levels[depth] if 0 <= depth < len(levels) else str(depth)

    out: dict[str, dict[str, str]] = {}
    for module_id, rec in depths.items():
        depth = int(rec.get("depth", 0))
        missing = rec.get("stopped_because") or ""
        # NODE-SPECIFIC, always. Every non-sketched node used to carry one of two identical strings
        # — 103 of 107 shared a sentence about the owning DOCUMENT and said nothing about the node.
        # For a report whose stated job is "where did we stop", the reason has to name where THIS
        # node stopped. The rung reached and the evidence it lacks lead; the document follows.
        reached = f"reached rung {depth} (`{_rung(depth)}`)"
        lacks = f"; lacks `{missing}`" if missing else ""

        if depth < _DOCUMENTED_FROM_RUNG:
            out[module_id] = {"state": SKETCHED, "why": f"{reached}{lacks}"}
            continue

        doc = container_doc.get(owner.get(module_id, ""), "")
        ok, doc_why = verdict.get(doc, (False, "no owning document"))
        if depth < _VERIFIED_FROM_RUNG:
            # Short of rung 4, the node cannot be `verified` however well-stamped its document is —
            # and saying so is more useful than naming the document, which the reader cannot act on.
            out[module_id] = {
                "state": DOCUMENTED,
                "why": f"{reached}{lacks} — below rung {_VERIFIED_FROM_RUNG} "
                       f"(`{_rung(_VERIFIED_FROM_RUNG)}`), which `verified` requires",
            }
            continue
        out[module_id] = {
            "state": VERIFIED if ok else DOCUMENTED,
            "why": f"{reached}; {doc_why}" if ok else f"{reached}; not verified: {doc_why}",
        }
    return out


# The fields `AUTHORING_CONTRACT.md` step 1 names. Checked against the raw header rather than the
# parsed one, because the parsed one defaults.
_TAG_FIELDS = frozenset({"id", "classification", "surface", "owner", "status"})


def _under(root: Path, configured: Path) -> Path:
    """A configured path, re-rooted at the tree actually being measured.

    `engine_config` resolves against `host_root()`, which is right for a normal run and wrong for a
    caller that passed an explicit root — a verifier's throwaway lab, or the health check that
    measures `ctx.root`. Reading the real repository's manifest while reporting on a lab is a
    silent, confident mismatch; `spec_path` already had to solve exactly this.
    """
    try:
        rel = configured.resolve().relative_to(engine_root().resolve())
    except (OSError, ValueError):
        return configured
    local = root / rel
    return local if local.exists() else configured


def engine_root() -> Path:
    from tools.docgen import engine_config

    return engine_config.host_root()


def _is_iso_date(value: str) -> bool:
    """A real `YYYY-MM-DD`, not merely a non-empty string.

    `date` accepted `banana` and `n/a` because it tested presence. A field that can hold anything
    measures nothing, and the step's whole purpose is that staleness be visible rather than inferred.
    """
    from datetime import date as _date

    try:
        _date.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def _front_matter_keys(text: str) -> set[str]:
    """Keys declared WITH A NON-EMPTY VALUE in the document's FIRST front-matter block.

    First block only, and that matters: `skills/document-engine/SKILL.md` carries its own YAML
    header and then shows a doc-system header as an EXAMPLE inside a fenced code block. A scan of
    the opening kilobyte read the example as the document's own — a false positive that a probe
    written to be "independent" reproduced exactly, because naive is not the same as independent.
    """
    if not text.startswith("---"):
        return set()
    _, _, rest = text.partition("---")
    block, sep, _ = rest.partition("\n---")
    if not sep:
        return set()
    keys: set[str] = set()
    for line in block.splitlines():
        key, colon, value = line.partition(":")
        if colon and key.strip() and not key.startswith((" ", "\t", "#")) and value.strip():
            keys.add(key.strip())
    return keys


def document_lifecycle(root: Path, model: dict[str, Any]) -> list[dict[str, Any]]:
    """Per governed document, which of the six lifecycle steps is complete.

    **Every step below was rewritten after a verifier proved three of them did not read the artifact
    they name.** The findings, kept because each is a distinct way for a derived-looking check to be
    a constant:

    ``version`` was **structurally unreachable**. It resolved the archive directory with
    ``archive_id(rel)`` — no header — which yields a *path slug*, while the only writer,
    ``archive cut``, passes the header and writes the *header id*. A verifier cut a real snapshot,
    confirmed it on disk, and watched the step report ``False``. Since every governed document has a
    header id by construction, the step could never be true for any subject it examines.

    ``wire`` was a byte scan of the manifest FILE rather than the manifest's RULE. Manifest rows are
    keyed by **type prefix** (``WF``, ``ADR``, …) and ``check_manifest_drift`` says so; the step
    tested `full_id in text`. Three false negatives, one true caused by a prose sentence in the
    manifest's intro — and appending a comment saying a document *"was deleted and must never be
    built"* flipped that document to wired, so the report asserted the opposite of the text it read.

    ``date`` never read the header at all: the model did not extract ``last_reviewed``, so the check
    fell through to a substring scan of the whole file. It reported complete for a document whose
    field had been deleted but whose body discussed it, for one whose field was present and
    **empty**, and for one that merely had a ``produced_by`` — a generator's name is not a review
    date.

    ``tag`` was half tautology (``bool(tier)`` inside a loop that already skips untiered documents)
    and never checked the ``surface`` its own comment claimed. ``stamp`` accepted any stamp kind,
    disagreeing with :func:`_stamp_covers_body` in this same module.
    """
    from tools.docgen import (
        archive,
        classification,
        doc_manifest,
        engine_config,
        identity,
    )

    # The CONFIGURED manifest path, not a hardcoded one. With `ENGINE_DOC_SYSTEM_DIR` set — a
    # documented override — the hardcoded path read nothing, the `except` turned that into "nothing
    # is wired", and every document silently lost its `wire` step while `manifest_drift` reported
    # them all wired. Silent disagreement with the gate, caused by not asking the gate's own
    # resolver where the file is.
    try:
        manifest_rows = doc_manifest.read_manifest(_under(root, engine_config.doc_manifest_path()))
    except Exception:  # noqa: BLE001 — an unreadable manifest means "nothing is wired", not a crash
        manifest_rows = []
    registered_prefixes = {row.id for row in manifest_rows}
    try:
        changelog_text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        changelog_text = ""

    out: list[dict[str, Any]] = []
    for record in model.get("documents", []):
        tier = str(record.get("tier", ""))
        if not tier or tier.startswith("("):
            continue  # ungoverned: the lifecycle is a contract governed documents opt into
        rel = record["path"]
        if identity.is_archived_path(rel):
            # A superseded SNAPSHOT is not a live document. Without this, cutting a version injected
            # the archived copy into the lifecycle set and reported one id twice.
            continue
        doc_id = str(record.get("id", ""))
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError:
            text = ""

        # The archive is keyed the way `archive cut` keys it — by header id when there is one — and
        # a generation counts only when a SNAPSHOT is actually there and TRACKED. An empty `v1/`
        # directory reported a version with nothing in it, and an uncommitted cut reported one that
        # a fresh clone would not have: every other fact in this map resolves against `git ls-files`
        # on the stated grounds that an untracked file is present for its author and absent for
        # everybody else.
        archive_key = doc_id if (doc_id and identity.is_safe_id(doc_id)) else identity.archive_id(rel)
        archived: list[int] = []
        try:
            for version in archive.versions_on_disk(root, archive_key):
                snapshot = archive.snapshot_in(root, archive_key, version)
                if snapshot is None:
                    continue
                snap_rel = snapshot.resolve().relative_to(root.resolve()).as_posix()
                if tracked_paths(root, snap_rel):
                    archived.append(version)
        except Exception:  # noqa: BLE001 — an unreadable archive is "not versioned", not a crash
            archived = []

        # The ENGINE's prefix rule, imported. Re-implementing it as `split("-", 1)[0]` disagreed
        # with `check_manifest_drift` in both directions: `WF-201-draft` has no extractable prefix
        # and is a blocking finding for the gate while `wire` called it complete, and a `SOC-S-101`
        # id resolved to `SOC` instead of `SOC-S` and was called unwired while the gate wired it.
        prefix = classification._extract_prefix(doc_id) if doc_id else None
        last_reviewed = str(record.get("last_reviewed", "") or "").strip()
        stamp_ok, _stamp_why = _stamp_covers_body(root, rel)
        # The RAW front-matter block, because several parsed fields carry defaults and therefore
        # cannot go false: blanking `surface:` still yields a parsed surface, so a check on the
        # parsed value asserts nothing. `tag` means "the header is complete as written".
        declared = _front_matter_keys(text)

        steps = {
            # TAG — the header declares, WITH A VALUE, every field the contract names. Gated by
            # `header`, which is what refuses a document whose header cannot be parsed at all.
            "tag": _TAG_FIELDS <= declared,
            # WIRE — the manifest registers this document's TYPE PREFIX, extracted by the engine's
            # own rule. Not a substring of the file, and not a second implementation of the rule.
            "wire": bool(prefix) and prefix in registered_prefixes,
            # DATE — a real ISO date in the header's own field. Presence alone accepted
            # `last_reviewed: banana` and `last_reviewed: n/a`.
            "date": _is_iso_date(last_reviewed),
            # VERSION — a generation exists on disk under the id the writer uses.
            "version": bool(archived),
            # CHANGELOG — the change record names this document by path or by id.
            "changelog": bool(changelog_text) and (rel in changelog_text or (
                bool(doc_id) and doc_id in changelog_text
            )),
            # STAMP — a body-certifying stamp that STILL COVERS THE BODY, adjudicated by the same
            # function the node states use. Presence-only meant this module returned two verdicts
            # for one document: `stamp: true` beside "stamped commit deadbeef does not contain this
            # path". Aligning the kind filter was not enough; the validity check had to be the same.
            "stamp": stamp_ok,
        }
        out.append({
            "path": rel,
            "id": doc_id,
            "steps": steps,
            "complete": sum(1 for v in steps.values() if v),
            "of": len(LIFECYCLE_STEPS),
            "missing": sorted(k for k, v in steps.items() if not v),
            "version_declared": str(record.get("version", "") or ""),
            "versions_on_disk": archived,
        })
    return sorted(out, key=lambda r: r["path"])


# `git show <rev>:<path>` resolves a bare <path> against the repository TOP-LEVEL, while
# `git log -- <path>` and `git ls-tree <rev> -- <path>` resolve it against the invocation
# directory. The two agree only when the scanned root IS the top-level. A `./` prefix makes
# `show` resolve from the working directory too, so a host scanned from a subdirectory of its
# repository (a vendored or nested payload) reads the same blob `ls-tree` just proved exists.
# Found 2026-09-07 on a host whose payload sits one level below its `.git`; before this, that
# layout reported "historical spec blob … is unreadable" and the ratchet memory was UNAVAILABLE.
def _historical_floors(root: Path) -> tuple[dict[str, int] | None, str]:
    """The **highest floor each container has ever been committed with**, and any missing memory.

    **Memory has to be something the commit under scrutiny cannot rewrite.** The first attempt read
    `HEAD`, and a verifier defeated it by adding one commit: make the loosening edits, commit them,
    rebuild — `HEAD` is now the attacker's own commit, the ratchet reports level, every probe passes,
    and the git-moat container sits at `sketch` in a tree that pushes clean. `HEAD` guards the
    working tree only.

    The maximum over the file's whole history cannot be lowered by appending to that history. Undoing
    it requires rewriting published history, which is separately forbidden and separately visible.

    Cheap in practice: one `git log` over a single path plus one `git show` per commit that touched
    it — this spec has a handful.

    Unavailable git, or a spec with no history yet, is reported as a cause and never as a pass. The
    caller degrades and SAYS so: an earlier version claimed `ratchet memory: git HEAD` while the
    memory it reported was a commit of the very tree under test, and confidently wrong is worse than
    a named unknown.
    """
    import subprocess

    from tools.blueprint import spec as spec_mod

    try:
        rel = spec_mod.spec_path(root).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        # Not inside the repository — the basename lookup this replaced would have silently
        # searched for the wrong path rather than saying it could not look.
        return None, "the system spec is not inside the repository, so it has no history here"
    # A clone can be TRUNCATED without any history rewrite, in more than one shape, and each lets the
    # maximum floor over what is locally readable sit BELOW the true high-water mark — a loosening
    # passing unseen. The ratchet's memory must be a history the change under test cannot shorten OR
    # truncate (`L-40`), so a truncated tree is UNAVAILABLE, not partial. Three shapes, because a
    # verifier drove the first fix (shallow only) through the other two (`OG-218`):
    #   * SHALLOW  (`git clone --depth N`): `git log` returns a PREFIX of the commits;
    #   * PARTIAL/BLOBLESS (`git clone --filter=blob:none`): `git log` lists EVERY commit and the tree
    #     is not "shallow", but the historical spec blobs were never fetched, so `git show <sha>:spec`
    #     fails on them — silently skipped, the max was taken over only the commits whose blobs
    #     happened to be present;
    #   * GRAFTED (`git replace --graft`): a synthetic root hides ancestors, so `git log` returns a
    #     tiny prefix with every blob present — no read fails, and the memory is confidently the
    #     grafted prefix's max.
    # Off the local-hook path (a working clone is full) but reachable under CI, where
    # `actions/checkout` defaults to `fetch-depth: 1` and offers `filter: blob:none`.
    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=30, check=False,
        )

    try:
        if _git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
            return None, "shallow clone — history is truncated, so the highest-ever floor cannot be known"
        # A promisor remote or a partial-clone filter means blobs may be absent from the object store.
        partial = _git("config", "--get-regexp", r"^remote\..*\.(promisor|partialclonefilter)$")
        if partial.returncode == 0 and partial.stdout.strip():
            return None, ("partial/blobless clone — historical spec blobs may be absent, so the "
                          "highest-ever floor cannot be known")
        # `git replace --graft` rewrites the visible ancestry without touching stored history. git
        # honours replace refs under `refs/replace/` OR under a base named by `GIT_REPLACE_REF_BASE`
        # — the SAME env-var relocation the `info/grafts` / `GIT_GRAFT_FILE` pair below already
        # defends. Checking only the literal `refs/replace` left a symmetric hole: a graft relocated
        # via `GIT_REPLACE_REF_BASE` is ACTIVE for `git log` yet invisible to a literal `refs/replace`
        # scan, so `_historical_floors` returned a confident LOWERED max — the false green this guard
        # exists to stop. Found by the 1.0.0 audit re-attack; the fix is the mirror of the graft-file
        # override handling, so both graft mechanisms are defended against env-var relocation.
        replace_bases = {"refs/replace"}
        env_base = os.environ.get("GIT_REPLACE_REF_BASE")
        if env_base:
            replace_bases.add(env_base.rstrip("/") or "refs/replace")
        for base in sorted(replace_bases):
            if _git("for-each-ref", "--format=%(refname)", base).stdout.strip():
                return None, ("grafted history (refs/replace) — the visible ancestry is synthetic, so "
                              "the highest-ever floor cannot be trusted")
        # The OLDER graft mechanism — `$GIT_DIR/info/grafts` (and the `GIT_GRAFT_FILE` override) — is
        # still honoured by git (a deprecation hint, not an error) and is invisible to the
        # `refs/replace` check above: a verifier grafted a committed loosening's parent away through
        # this file with all three checks silent (`OG-228`, the same truncation tier, a second
        # spelling). A non-empty grafts file makes the ancestry synthetic just as `refs/replace` does.
        graft_hint = _git("rev-parse", "--git-path", "info/grafts").stdout.strip()
        graft_file = os.environ.get("GIT_GRAFT_FILE") or (str(root / graft_hint) if graft_hint else "")
        try:
            grafted = bool(graft_file and Path(graft_file).is_file()
                           and Path(graft_file).read_text(encoding="utf-8", errors="replace").strip())
        except OSError:
            grafted = False
        if grafted:
            return None, ("grafted history (info/grafts) — the visible ancestry is synthetic, so the "
                          "highest-ever floor cannot be trusted")
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git unavailable ({type(exc).__name__})"
    try:
        # `--full-history` because default `git log -- <path>` applies HISTORY SIMPLIFICATION and
        # prunes a side branch whose merge is TREESAME to one parent — so an ordinary `git merge
        # -s ours` of a committed floor RAISE removes it from the walk with no rewrite, and the
        # ratchet's memory silently forgets it (`OG-229`). It carries NO `--diff-filter`: a merge's
        # default diff is empty, so `--diff-filter=ACMR` dropped MERGE commits, and a floor committed
        # uniquely in an evil merge's tree was forgotten — a regression a verifier measured (floor
        # 9-in-a-merge lowered to 8, unseen), `OG-233`. Deletion-vs-missing-object is instead
        # disambiguated per commit by `git ls-tree` below. `log.follow`/`log.showSignature` are forced
        # off: `--follow` would walk across a rename into commits where `rel` does not exist (false
        # "unreadable" on a FULL clone), and a signature would interleave non-sha tokens (`OG-230`).
        log = subprocess.run(
            ["git", "-C", str(root),
             "-c", "log.follow=false", "-c", "log.showSignature=false",
             "log", "--format=%H", "--no-show-signature",
             "--full-history", "--", rel],
            capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git unavailable ({type(exc).__name__})"
    if log.returncode != 0:
        return None, f"git log failed for {rel}"
    # Validate each token is a full 40-hex sha before it is handed to `git show` — defence in depth
    # against any config (a stray `log.showSignature`, a decoration) leaking a non-sha token that
    # would then fail `git show` and misread as a truncated object store (`OG-230`).
    commits = [tok for tok in log.stdout.split()
               if len(tok) == 40 and all(c in "0123456789abcdef" for c in tok)]
    if not commits:
        return None, f"{rel} has no commit history yet"

    highest: dict[str, int] = {}
    for commit in commits:
        # Is `rel` in THIS commit's tree? `git ls-tree` reads the TREE object (present even in a
        # blobless partial clone) and lists `rel` with its blob sha — so it distinguishes the two
        # ways `git show` below can fail WITHOUT the `--diff-filter=ACMR` that dropped merges
        # (`OG-233`): an EMPTY listing means `rel` is absent at this commit (a deletion, or a commit
        # before it was added) and is correctly skipped, not a truncation; a NON-empty listing whose
        # `git show` then fails is a MISSING OBJECT (a truncated store), fail-closed.
        try:
            tree = subprocess.run(
                ["git", "-C", str(root), "ls-tree", commit, "--", rel],
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"git unavailable reading tree {commit[:12]} ({type(exc).__name__})"
        if tree.returncode != 0 or not tree.stdout.strip():
            continue  # `rel` is absent at this commit (deletion or pre-add) — not a truncation
        try:
            blob = subprocess.run(
                ["git", "-C", str(root), "show", f"{commit}:./{rel}"],
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"git unavailable reading {commit[:12]}:{rel} ({type(exc).__name__})"
        if blob.returncode != 0:
            # `ls-tree` proved `rel` is in this commit's tree, so an unreadable blob is a truncated
            # object store — UNAVAILABLE, never a silent skip that lowers the max.
            return None, (f"historical spec blob {commit[:12]}:{rel} is unreadable — the object store "
                          "is incomplete (partial clone or missing objects), so the highest-ever "
                          "floor cannot be known")
        try:
            doc = json.loads(blob.stdout)
        except ValueError:
            continue
        for row in doc.get("containers", []):
            value = row.get("depthFloor")
            # `isinstance(True, int)` is True in Python, so a JSON `true` was accepted as a floor of
            # 1 — and four containers really do have floor 1, so the coercion was live.
            if isinstance(value, int) and not isinstance(value, bool):
                cid = str(row.get("id", ""))
                highest[cid] = max(highest.get(cid, 0), int(value))
    return highest, ""


def floor_findings(model: dict[str, Any], historical: dict[str, int] | None = None) -> list[str]:
    """Every way the ratchet can be violated. Four directions, not two.

    * a container measuring **below** its floor is a regression;
    * a floor written **beneath its own measurement** is slack — a regression scheduled in advance;
    * a floor written **below the highest it has ever carried** is a loosening, and this is the one
      that made the first two versions a suggestion: a regression *cures* the slack check, and a
      single extra commit *cured* the `HEAD` check;
    * a container that has a remembered floor and **no longer exists** is a rename or a deletion
      carrying its commitment away with it — a verifier lowered a floor simply by renaming the
      container, because memory was keyed on an id nothing required to persist.
    """
    findings: list[str] = []
    live = {c["id"] for c in model.get("containers", [])}
    for container in model.get("containers", []):
        cid = container["id"]
        floor = container.get("depth_floor")
        if floor is None:
            findings.append(
                f"{cid}: declares no `depth_floor` — every container must commit to one, or the "
                f"ladder is a dashboard rather than a gate"
            )
            continue
        floor = int(floor)
        depth = int(container.get("depth", 0))
        was = (historical or {}).get(cid)
        if was is not None and floor < was:
            findings.append(
                f"{cid}: `depthFloor` is {floor} but this container has previously been committed "
                f"at {was}. A ratchet may only be RAISED — if it genuinely cannot hold {was}, say so "
                f"in the register and let a reviewer see the argument, not just the number."
            )
        if depth < floor:
            findings.append(
                f"{cid}: measures depth {depth} ({container.get('level')}), below its declared "
                f"floor of {floor}. Shallowest: "
                f"{', '.join(container.get('shallowest', [])[:3]) or 'unknown'}"
            )
        elif depth > floor:
            findings.append(
                f"{cid}: measures depth {depth} but declares a floor of {floor} — the ratchet has "
                f"slack. Raise the floor to {depth} to keep what has been earned."
            )
    for cid, was in sorted((historical or {}).items()):
        if cid and cid not in live:
            findings.append(
                f"{cid}: was committed with a floor of {was} and no longer exists. A container "
                f"cannot shed its commitment by being renamed — either restore the id, or record "
                f"the removal in `docs/process/OPEN_GATES.md` so a reviewer sees the argument."
            )
    return findings


def build(root: Path, model: dict[str, Any]) -> dict[str, Any]:
    """The whole report: node states, the lifecycle table, and the ratchet's verdict."""
    nodes = node_states(root, model)
    summary: dict[str, int] = {state: 0 for state in NODE_STATES}
    for record in nodes.values():
        summary[record["state"]] = summary.get(record["state"], 0) + 1
    documents = document_lifecycle(root, model)
    historical, memory_gap = _historical_floors(root)
    return {
        "states": list(NODE_STATES),
        "nodes": nodes,
        "summary": summary,
        "documents": documents,
        "lifecycle_steps": list(LIFECYCLE_STEPS),
        "floor_findings": floor_findings(model, historical),
        # Named, never silent: without it the ratchet degrades to the memoryless equality lock a
        # verifier defeated in one line, and the report would look identical.
        "ratchet_memory": (
            f"git history of the spec ({len(historical)} container(s) remembered)"
            if historical is not None else f"UNAVAILABLE — {memory_gap}"
        ),
    }
