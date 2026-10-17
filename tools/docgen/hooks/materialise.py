"""Materialise git blob objects for scanning — one process, encoding-normalised, gitlink-aware.

**Why this module exists.** Both git hooks used to write each published blob with its own
``git cat-file blob`` fork, then hand the raw bytes to a ``grep``-based scanner. Three defects came
out of that shape, and an adversarial verifier proved all three:

* **O(n) forks.** 1000 tiny files totalling 10,890 bytes took **331 seconds** to commit — of which
  9.9 s was compute. The rest was process creation. That is not slowness, it is *denial of the
  gate*: at ~16 minutes for 3000 files, people bypass it, and a gate people bypass is worth less
  than one that runs.
* **Encodings the scanner cannot read.** A blob that natively *is* UTF-16 — what Notepad
  "Unicode", PowerShell redirection and any Windows-authored config produce — defeats
  ``grep -E 'AKIA[0-9A-Z]{16}'`` entirely, because the pattern cannot match across interleaved NUL
  bytes. The scan reported clean over a live-shaped credential. Fixing ``working-tree-encoding``
  earlier had only moved this hole, not closed it.
* **Gitlinks.** A submodule pointer's "blob sha" is a *commit* sha, so ``cat-file blob`` failed and
  the whole commit was refused with no path named and no diagnosis — leaving
  ``ENGINE_SKIP_PRECOMMIT=1`` as the only way forward. **The moat teaching its own bypass** is a
  worse outcome than the gap it was guarding.

One place, so the two hooks cannot drift apart, and so the counter-examples in
``tools/tests/test_materialise.py`` cover both.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# A blob is treated as UTF-16/32 when it carries a byte-order mark, or when NUL bytes are dense
# enough that no UTF-8 text could look like this. 0.10 is deliberately conservative: real UTF-16
# ASCII-ish text is ~50% NUL, while a genuinely binary blob (an image, a font) is excluded by the
# BOM test and would not have matched the scanner's text patterns anyway.
_NUL_DENSITY_THRESHOLD = 0.10

# Bytes inspected when classifying. One constant, so the detector and the union-of-views gate
# below can never disagree about how much of a blob they looked at.
_SAMPLE_BYTES = 8192
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


@dataclass
class MaterialiseResult:
    """What was written, what was skipped, and why — so a caller never has to guess."""

    written: int = 0
    transcoded: list[str] = field(default_factory=list)
    skipped_gitlinks: list[str] = field(default_factory=list)
    # Unnamed commit objects from `rev-list --objects`. Counted, not named: they have
    # no path to print, and printing empty parentheses is what `OG-130` was.
    skipped_commits: int = 0
    failed: list[str] = field(default_factory=list)


def looks_utf16_or_32(data: bytes) -> str | None:
    """Return the encoding name if ``data`` is UTF-16/32 text, else ``None``.

    Checked by BOM first, then by NUL density, because plenty of Windows tooling emits UTF-16
    without a BOM.
    """
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            return encoding
    sample = data[:_SAMPLE_BYTES]
    if not sample:
        return None
    nul_density = sample.count(0) / len(sample)
    if nul_density < _NUL_DENSITY_THRESHOLD:
        return None

    # ⚠ **UTF-32 IS TESTED FIRST, AND THE ORDER IS THE WHOLE FIX.**
    #
    # This branch used to end `return "utf-16-be" if even_nuls > odd_nuls else "utf-16-le"` — so a
    # function named `looks_utf16_or_32`, whose docstring says UTF-16/32 and whose register row
    # (`OG-56`) claims detection "by BOM **or** NUL density", could **never return a UTF-32 answer
    # without a BOM**. A BOM-less UTF-32 blob is ~75% NUL, sails past the density threshold, and was
    # then transcoded AS UTF-16 into interleaved-NUL text that matches no pattern at all.
    #
    # Four Pass-7 agents drove it to a real commit through the installed hook: a
    # `classification: secret` document AND an AWS-key-shaped credential both landed clean — and the
    # hook printed *"1 blob(s) transcoded for scanning (… (utf-16-le))"*, so an operator auditing the
    # output saw the encoding defence apparently working on the exact blob it had just failed to
    # read. **A false affirmative is worse than a silent miss.**
    #
    # UTF-32 text is ~3 NULs in every 4 bytes with the non-NUL byte at a fixed offset in each group;
    # UTF-16 is ~1 in 2. Testing the wider stride first is what makes the narrower one unreachable
    # for input it was never right about.
    groups = len(sample) // 4
    if groups >= 2:
        quads = [sample[i * 4 : i * 4 + 4] for i in range(groups)]
        le32 = sum(1 for q in quads if q[1] == 0 and q[2] == 0 and q[3] == 0)
        be32 = sum(1 for q in quads if q[0] == 0 and q[1] == 0 and q[2] == 0)
        if le32 >= groups * 0.7:
            return "utf-32-le"
        if be32 >= groups * 0.7:
            return "utf-32-be"

    # Distinguish LE from BE by which side of the pairs the NULs fall on.
    even_nuls = sum(1 for i in range(0, len(sample) - 1, 2) if sample[i] == 0)
    odd_nuls = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
    return "utf-16-be" if even_nuls > odd_nuls else "utf-16-le"


# Every wide encoding worth trying when detection declines to commit to one. Order is irrelevant:
# all of them are appended, and the scanner greps the union.
_CANDIDATE_WIDE = ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be")

# Minimum run of printable ASCII kept from a decoded view. `strings` defaults to 4; this uses 8
# because 4 admits far too much noise from compressed data — every tracked `.woff2` grew ~150% at
# 4 and ~6% at 8. Nothing is lost: the shortest credential class this scanner recognises is an
# `AKIA`/`ASIA` id at 20 characters, and a run is broken only by a NON-ASCII byte, so a secret
# surrounded by wide-encoded padding always survives as one run of its own full length.
_MIN_RUN = 8

# Hard cap on the extracted text appended per blob. A bound is required, not optional: without one
# a large wide-encoded file would multiply by the number of candidate encodings. 1 MiB is orders of
# magnitude above any real config or document, and truncation is reported rather than silent.
_MAX_EXTRACT = 1024 * 1024

_ASCII_RUN_RE = re.compile(rb"[\x20-\x7e]{%d,}" % _MIN_RUN)


def _ascii_runs(data: bytes, encoding: str) -> bytes:
    """Printable-ASCII runs from ``data`` read as ``encoding`` — a `strings` pass, one decoding deep.

    **Runs, not the whole decoded view, and the difference is measured.** Appending full decodings
    quadrupled every tracked `.woff2` (22 KB to 88 KB each): compressed bytes read as UTF-16 land
    on valid BMP codepoints, so they are neither replacement characters nor control codes and no
    cleanliness test rejects them. Two earlier discriminators — printable-byte share, then decode
    damage — both failed on real assets in exactly that way.

    Extracting ASCII runs sidesteps the classification question entirely. A scanner hunting
    an AWS key id, an `sk-ant-` token or a credential embedded in a connection string needs
    ASCII and nothing else, so this keeps
    precisely what it can use and discards what it cannot. A font contributes a few hundred bytes
    of noise; a CJK-padded UTF-16 document contributes the credential hidden in it.
    """
    try:
        text = data.decode(encoding, errors="replace")
    except (UnicodeDecodeError, LookupError):  # pragma: no cover - defensive
        return b""
    # **UTF-8, not ASCII-with-replace.** `encode("ascii", errors="replace")` maps every non-ASCII
    # character to `?` — a printable ASCII byte — so a font decoded as UTF-16 became one enormous
    # run of `????…` and every tracked `.woff2` grew 150%. UTF-8 encodes non-ASCII with the high
    # bit set, which the run pattern excludes, so a non-ASCII character correctly BREAKS a run.
    raw = text.encode("utf-8", errors="replace")
    return b"\n".join(_ASCII_RUN_RE.findall(raw))


def normalise_for_scanning(data: bytes) -> tuple[bytes, str | None]:
    """Return bytes a text scanner can actually read, plus the encoding transcoded from (if any).

    A scanner that greps for ``AKIA…`` finds nothing in UTF-16 no matter how correct its patterns
    are. Handing it unreadable bytes and recording a pass is the wrong-artifact defect one level
    below the one the blob rewrite fixed.

    **Two strategies, because classification alone is not safe.** When a BOM or a dense field of
    NULs identifies the encoding, the blob is transcoded — that answer is certain. When it does
    not, the blob is not therefore UTF-8: Pass 7 built a UTF-16-LE document padded with CJK, whose
    two-byte non-NUL codepoints drop NUL density to **0.0004** — far under the 0.10 threshold —
    while an ASCII AWS key inside it still sat interleaved with NULs and matched no pattern
    (`OG-101`). Detection had a blind spot precisely where the payload was hiding.

    So a NUL-bearing blob that detection declines to classify is not guessed at. Every candidate
    wide decoding is **appended** to the raw bytes, and the scanner greps the union: a secret
    visible in ANY plausible reading is found, without this function having to be right about
    which reading was intended. Blobs with no NUL at all — the overwhelming majority — are
    returned untouched, so the common path costs nothing.
    """
    # **The classified transcode is ADDITIVE, never a replacement, and that is a correctness fix.**
    # It used to return the transcoded bytes alone. A CJK-padded UTF-32-LE blob is ~50% NUL, which
    # `looks_utf16_or_32` reads as UTF-16-LE — a wrong answer that then REPLACED the blob with a
    # mojibake view, and the AWS key planted in it disappeared from the scan entirely. Classifying
    # can be wrong; discarding the original on the strength of that guess is what made it fatal.
    base = data
    encoding = looks_utf16_or_32(data)
    if encoding is not None:
        try:
            base = data + b"\n" + data.decode(encoding, errors="replace").encode("utf-8")
        except (UnicodeDecodeError, LookupError):  # pragma: no cover - defensive
            encoding = None

    if b"\x00" not in data:
        return base, encoding

    extracted: list[bytes] = []
    kept: list[str] = []
    budget = _MAX_EXTRACT
    for candidate in _CANDIDATE_WIDE:
        runs = _ascii_runs(data, candidate)
        if not runs:
            continue
        if len(runs) > budget:
            runs = runs[:budget]
        budget -= len(runs)
        extracted.append(runs)
        kept.append(candidate)
        if budget <= 0:
            break
    if not extracted:
        return base, encoding
    label = "ascii-runs:" + ",".join(kept)
    return base + b"\n" + b"\n".join(extracted), (f"{encoding}+{label}" if encoding else label)


def materialise(records: list[tuple[str, str]], dest: Path, repo_root: Path) -> MaterialiseResult:
    """Write every blob in ``records`` (``(sha, path)``) into ``dest``, named by its SHA.

    Named by SHA, never by path — that is load-bearing three times over: it defeats the portfolio
    scanner's basename self-exclusion (any file called ``secret-scan.sh`` was silently dropped), it
    makes case collision on a case-insensitive filesystem impossible, and it keeps a path with a
    newline or a quote in it from becoming a shell problem.
    """
    result = MaterialiseResult()
    wanted: dict[str, str] = {}
    for sha, path in records:
        if sha and sha not in wanted:
            wanted[sha] = path
    if not wanted:
        return result
    dest.mkdir(parents=True, exist_ok=True)

    # ONE process for every object. `--batch` streams `<sha> <type> <size>\n<payload>\n` per request.
    proc = subprocess.Popen(
        ("git", "-C", str(repo_root), "cat-file", "--batch"),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        proc.stdin.write(("\n".join(wanted) + "\n").encode("ascii"))
        proc.stdin.flush()
        proc.stdin.close()
        for _ in range(len(wanted)):
            header = proc.stdout.readline()
            if not header:
                break
            parts = header.decode("utf-8", errors="replace").split()
            if len(parts) < 2:
                continue
            sha = parts[0]
            if parts[1] == "missing" or len(parts) < 3:
                result.failed.append(f"{sha} ({wanted.get(sha, '?')})")
                continue
            kind, size = parts[1], int(parts[2])
            payload = proc.stdout.read(size)
            proc.stdout.read(1)  # the trailing newline git appends
            if kind == "commit":
                # A commit object. **Two very different things arrive here, and calling both
                # "submodule pointer" was wrong on every ordinary repository** (`OG-130`):
                #
                # * a GITLINK — a submodule pointer, which has a PATH, because it is a tree entry;
                # * an ordinary COMMIT reached by `git rev-list --objects`, which emits it with no
                #   name at all. `pre-push` feeds those in with an empty path on purpose, so the
                #   secret scan can reach a blob git never named on that line.
                #
                # Measured on a lab repository with **no submodules at all**:
                #   `note: 6 submodule pointer(s) skipped (, , ) — a gitlink carries no bytes`
                # — six phantom submodules and three empty names, on every push. A gate that
                # reports things that do not exist is a gate people stop reading.
                path = wanted.get(sha, "")
                if path:
                    result.skipped_gitlinks.append(path)
                else:
                    result.skipped_commits += 1
                continue
            if kind != "blob":
                continue
            normalised, transcoded_from = normalise_for_scanning(payload)
            if transcoded_from:
                result.transcoded.append(f"{wanted.get(sha, sha)} ({transcoded_from})")
            (dest / sha).write_bytes(normalised)
            result.written += 1
    finally:
        proc.stdout.close()
        proc.wait(timeout=60)
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI for the hooks: read ``<sha>\\t<path>`` lines on stdin, write blobs into ``argv[1]``.

    Prints a one-line summary on stderr and exits non-zero only when an object could not be read —
    "I could not materialise what is being published" is never a pass.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        # `P8-109`: this line named the two positional args but never said the tool also reads
        # stdin — the ONLY way it receives what to materialise. A caller who gets rc=2 here and
        # reads only this line has no way to discover that a `<sha>\t<path>` manifest belongs on
        # stdin; the docstring above says so, but `--help`-style output is what a caller actually
        # sees at the command line, not the module docstring.
        sys.stderr.write(
            "usage: <sha>\\t<path> lines on stdin | materialise.py <dest-dir> <repo-root>\n"
        )
        return 2
    dest, repo_root = Path(args[0]), Path(args[1])
    records: list[tuple[str, str]] = []
    for line in sys.stdin.read().splitlines():
        if "\t" in line:
            sha, path = line.split("\t", 1)
            records.append((sha.strip(), path))
    result = materialise(records, dest, repo_root)
    if result.transcoded:
        sys.stderr.write(
            f"   note: {len(result.transcoded)} blob(s) transcoded for scanning "
            f"({', '.join(result.transcoded[:3])}) — a UTF-16 blob is invisible to a text scanner\n"
        )
    if result.skipped_commits:
        sys.stderr.write(
            f"   note: {result.skipped_commits} commit object(s) carry no scannable bytes\n"
        )
    if result.skipped_gitlinks:
        sys.stderr.write(
            f"   note: {len(result.skipped_gitlinks)} submodule pointer(s) skipped "
            f"({', '.join(result.skipped_gitlinks[:3])}) — a gitlink carries no bytes to scan\n"
        )
    if result.failed:
        sys.stderr.write(f"⛔ could not read {len(result.failed)} object(s): {', '.join(result.failed[:5])}\n")
        return 1
    sys.stdout.write(f"{result.written}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
