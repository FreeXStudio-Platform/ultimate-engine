"""The document archive — snapshots, history, and the freeze check that makes them mean something.

`BUILD_PLAN.md` row 4: *"``docs/current/`` (last verified) vs ``docs/archive/<id>/vN/``"*. The live
tree **is** ``current`` — every document stays exactly where it lives, and nothing is moved into a
parallel directory. Introducing a literal ``docs/current/`` would relocate every governed document,
break every path every other document cites, and buy nothing the archive does not already give: a
document's *current* bytes are the ones in the working tree, and its *superseded* bytes are the
ones under ``docs/archive/<id>/vN/``. One tree moves, one tree does not.

**What a cut does.** ``cut()`` copies the document's exact bytes to
``<archive>/<id>/v<N>/<basename>``, appends a row to ``<archive>/<id>/HISTORY.md`` recording the
things that are NOT derivable later — the date, the commit, who cut it, and the sha256 of the
snapshot — and, when the document is governed, writes ``version``/``revision`` back into its front
matter so it is self-describing.

**What makes the archive trustworthy is the hash, not the fact that a file is present.** A snapshot
whose bytes no longer match the hash its history recorded is a corrupted record, and the audit says
so. Without that, an archive is a directory of files anyone could have edited, certifying nothing.

**Supersession is derived, never stored.** A version is superseded exactly when a higher version
exists. `docs/process/RULES.md` Rule 2: if code can derive it, the document must not state it — a
``superseded: true`` field would be a hand-maintained second answer that goes stale on the next cut,
and correcting it would restore it to true only until the cut after that.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tools.docgen import engine_config
from tools.docgen.identity import archive_id, is_safe_id
from tools.lib.front_matter import LEADING_COMMENT_LINES

HISTORY_NAME = "HISTORY.md"

_VERSION_DIR_RE = re.compile(r"^v([1-9][0-9]*)$")
# The writer wraps `commit` and `sha256` in backticks so they render as code; the reader must
# therefore accept them. It did not, and the round-trip failed silently in exactly the way the
# audit exists to catch: every cut wrote a row, every read returned none, and `archive list`
# reported "v1 exists on disk but HISTORY.md records no row for it" on a freshly written archive.
# **Write and read are one grammar** — the backticks are optional here rather than stripped
# afterwards, so a hand-written row without them still parses.
_ROW_RE = re.compile(
    r"^\|\s*v([1-9][0-9]*)\s*\|\s*([^|]*?)\s*\|\s*`?([^|`]*?)`?\s*\|"
    r"\s*`?([0-9a-f]{64})`?\s*\|\s*([^|]*?)\s*\|\s*$"
)


class ArchiveError(RuntimeError):
    """A cut could not be made. Never raised for a *reading* operation — reads degrade to empty."""


@dataclass(frozen=True)
class Entry:
    """One recorded cut: the facts about the moment of cutting that nothing can re-derive later."""

    version: int
    cut_on: str
    commit: str
    sha256: str
    cut_by: str

    def row(self) -> str:
        return (
            f"| v{self.version} | {self.cut_on} | `{self.commit}` | `{self.sha256}` "
            f"| {self.cut_by} |"
        )


def archive_root(root: Path) -> Path:
    """The archive directory under an EXPLICIT root.

    Every path function in this module takes the root as an argument rather than calling
    ``engine_config.host_root()`` for itself. That auto-detection walks up from the *current
    working directory*, which is right for a CLI invocation and wrong for every other caller: the
    ``identity`` corpus guard must read the archive of the tree it is checking, and a verification
    lab is a different tree at the same cwd. The first version of this module resolved the root
    internally, so a guard running against a lab would have audited the real repository's archive
    and reported it as the lab's — a false result that looks entirely plausible.
    """
    return root / engine_config.archive_dir_relative()


def doc_dir(root: Path, doc_id: str) -> Path:
    if not is_safe_id(doc_id):
        raise ArchiveError(f"unsafe archive id {doc_id!r} — refusing to join it onto a path")
    return archive_root(root) / doc_id


def version_dir(root: Path, doc_id: str, version: int) -> Path:
    if version < 1:
        raise ArchiveError(f"version must be >= 1, got {version}")
    return doc_dir(root, doc_id) / f"v{version}"


def history_path(root: Path, doc_id: str) -> Path:
    return doc_dir(root, doc_id) / HISTORY_NAME


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def versions_on_disk(root: Path, doc_id: str) -> list[int]:
    """Version numbers that have a directory, ascending. Missing archive reads as empty, never raises."""
    try:
        base = doc_dir(root, doc_id)
    except ArchiveError:
        return []
    if not base.is_dir():
        return []
    found: list[int] = []
    for child in base.iterdir():
        match = _VERSION_DIR_RE.match(child.name)
        if match is not None and child.is_dir():
            found.append(int(match.group(1)))
    return sorted(found)


def snapshot_in(root: Path, doc_id: str, version: int) -> Path | None:
    """The single snapshot file inside a version directory, or None when it is absent/ambiguous.

    A version directory holds exactly one file. Returning ``None`` for two is deliberate: guessing
    which of them is the document is how an archive starts certifying the wrong bytes, and the
    audit reports the ambiguity instead.
    """
    try:
        vdir = version_dir(root, doc_id, version)
    except ArchiveError:
        return None
    if not vdir.is_dir():
        return None
    files = sorted(p for p in vdir.iterdir() if p.is_file())
    return files[0] if len(files) == 1 else None


def read_history(root: Path, doc_id: str) -> list[Entry]:
    """Parse ``HISTORY.md`` into entries, ascending by version. Unreadable/absent reads as empty."""
    path = history_path(root, doc_id) if is_safe_id(doc_id) else None
    if path is None or not path.is_file():
        return []
    entries: list[Entry] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _ROW_RE.match(line)
        if match is None:
            continue
        entries.append(
            Entry(
                version=int(match.group(1)),
                cut_on=match.group(2).strip(),
                commit=match.group(3).strip().strip("`"),
                sha256=match.group(4),
                cut_by=match.group(5).strip(),
            )
        )
    return sorted(entries, key=lambda e: e.version)


def latest_version(root: Path, doc_id: str) -> int:
    """The highest version that exists on disk, or 0 when the document has never been cut."""
    versions = versions_on_disk(root, doc_id)
    return versions[-1] if versions else 0


def write_history(root: Path, doc_id: str, source_rel: str, entries: list[Entry]) -> Path:
    """(Re)write ``HISTORY.md`` from entries. Machine-written; the header says so."""
    path = history_path(root, doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(entry.row() for entry in sorted(entries, key=lambda e: e.version))
    path.write_text(
        f"<!-- title: ARCHIVE HISTORY {doc_id} -->\n"
        "<!-- GENERATED by `python3 -m tools.docgen.cli archive cut` — do not hand-edit. -->\n"
        f"# Archive history — `{doc_id}`\n\n"
        f"{_LIVE_PREFIX}{source_rel}`\n\n"
        "Each row records what cannot be re-derived from the directory listing: when the cut was "
        "made, the commit it was cut at, who cut it, and the sha256 of the snapshot. The version "
        "list itself is **not** a fact this table owns — the directories are — and the audit "
        "compares the two every run.\n\n"
        "A version is **superseded** exactly when a higher one exists below it. That is derived, "
        "never written down here.\n\n"
        "| version | cut on | commit | sha256 | cut by |\n"
        "|---|---|---|---|---|\n"
        f"{rows}\n",
        encoding="utf-8",
    )
    return path


_LIVE_PREFIX = "Live document: `"


def live_path(root: Path, doc_id: str) -> str:
    """The live document a ``HISTORY.md`` names, or ``""`` when it names none.

    The archive records the live path at cut time rather than re-deriving it, because a header-id
    archive (``WF-201``) carries no path information at all — only the history knows which document
    it belongs to. Both the CLI report and the ``identity`` guard need this answer, so it is
    written once here: two implementations of "which document is this archive for" is the shape
    `docs/process/RULES.md` Rule 1 names, and the first version of this phase had exactly that.
    """
    path = history_path(root, doc_id) if is_safe_id(doc_id) else None
    if path is None or not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(_LIVE_PREFIX) and line.endswith("`"):
            return line[len(_LIVE_PREFIX) : -1]
    return ""


def _git(root: Path, *argv: str) -> str | None:
    try:
        proc = subprocess.run(
            ("git", "-C", str(root), *argv),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def engine_version() -> str:
    """This engine's own version, for cut attribution. ``unknown`` when it cannot be read."""
    candidate = Path(__file__).resolve().parents[2] / "PROJECT_VERSION"
    try:
        return candidate.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


@dataclass(frozen=True)
class FreezeState:
    """Whether a document's live bytes still equal its newest snapshot."""

    doc_id: str
    version: int
    frozen: bool
    reason: str

    @property
    def versioned(self) -> bool:
        return self.version > 0


def freeze_state(root: Path, source_rel: str, doc_id: str) -> FreezeState:
    """Compare the live document against its newest archived snapshot.

    ``frozen`` is a MEASUREMENT — the bytes were compared — not a reading of any field a document
    wrote about itself. That is the whole point of the archive: the header may claim
    ``revision: 0``, and this is what decides whether the claim is true.
    """
    version = latest_version(root, doc_id)
    if version == 0:
        return FreezeState(doc_id, 0, False, "never cut")
    snapshot = snapshot_in(root, doc_id, version)
    if snapshot is None:
        return FreezeState(doc_id, version, False, f"v{version} holds no single snapshot file")
    try:
        live = (root / source_rel).read_bytes()
    except OSError:
        return FreezeState(doc_id, version, False, f"live document unreadable at {source_rel}")
    if live == snapshot.read_bytes():
        return FreezeState(doc_id, version, True, f"live bytes equal the v{version} snapshot")
    return FreezeState(doc_id, version, False, f"live bytes differ from the v{version} snapshot")


def cut(root: Path, source_rel: str, *, header: object = None, cut_on: str) -> Entry:
    """Cut the next version of a document: snapshot its bytes, record the cut, bump its header.

    ``cut_on`` is passed in rather than read from the clock so the operation is reproducible and
    testable — a probe supplies a fixed date and gets a deterministic result.
    """
    live_path = root / source_rel
    if not live_path.is_file():
        raise ArchiveError(f"no document at {source_rel}")

    doc_id = archive_id(source_rel, header)  # type: ignore[arg-type]
    if not is_safe_id(doc_id):
        raise ArchiveError(f"cannot derive a safe archive id for {source_rel}")

    # **A cut that changes nothing is not a version** (`OG-197`). Measured the moment it
    # happened: a rule-layer edit touched `RULEBOOK.md` only, and cutting `CONTRADICTION.md`
    # afterwards produced a v5 byte-identical to v4 — same sha256 in the history, two directories,
    # one document state. Nothing downstream could tell which was the real generation, and the
    # supersession derivation would report v4 superseded by a copy of itself. Refusing costs one
    # comparison; the alternative is an archive whose version numbers stop meaning anything.
    current = latest_version(root, doc_id)
    if current:
        state = freeze_state(root, source_rel, doc_id)
        if state.frozen:
            raise ArchiveError(
                f"{doc_id} is already frozen at v{current}: the live bytes are identical to that "
                "snapshot, so there is no new version to cut. Edit the document first, or leave "
                "the archive alone."
            )

    next_version = current + 1
    entries = read_history(root, doc_id)
    if any(entry.version == next_version for entry in entries):
        raise ArchiveError(
            f"history already records v{next_version} for {doc_id} but no directory exists for it; "
            "the archive is inconsistent — run the audit before cutting again"
        )

    # The header is written back BEFORE the snapshot is taken, so the archived bytes are the bytes
    # the live document has after the cut. Taking the snapshot first would archive a version that
    # never existed in the tree, and `revision: 0` would be false the instant it was written.
    _write_header_version(live_path, next_version)

    payload = live_path.read_bytes()
    target_dir = version_dir(root, doc_id, next_version)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / live_path.name
    target.write_bytes(payload)

    entry = Entry(
        version=next_version,
        cut_on=cut_on,
        commit=(_git(root, "rev-parse", "--short", "HEAD") or "unknown"),
        sha256=sha256_bytes(payload),
        cut_by=f"docgen {engine_version()}",
    )
    write_history(root, doc_id, source_rel, [*entries, entry])
    return entry


_FM_FENCE_RE = re.compile(
    rf"\A(﻿?{LEADING_COMMENT_LINES}[ \t]*---[ \t]*\r?\n)(.*?\r?\n)(---[ \t]*\r?\n)",
    re.DOTALL,
)


def _write_header_version(path: Path, version: int) -> bool:
    """Set ``version: N`` / ``revision: 0`` in a document's front matter. False when it has none.

    An ungoverned document — this repository's hash-locked rule files are the worked example — is
    left untouched on purpose, and its identity is carried by the archive alone. Editing it would
    change bytes that a hash gate is holding, to record something the archive already records.

    Only the two derived fields are written. ``produced_by`` and ``verified_state`` are the
    author's to state: one is attribution and the other is a claim, and a tool that filled either
    in automatically would be manufacturing the evidence it is supposed to check.
    """
    text = path.read_text(encoding="utf-8")
    match = _FM_FENCE_RE.match(text)
    if match is None:
        return False
    opening, body, closing = match.group(1), match.group(2), match.group(3)
    body = _set_scalar(body, "version", str(version))
    body = _set_scalar(body, "revision", "0")
    path.write_text(opening + body + closing + text[match.end() :], encoding="utf-8")
    return True


def _set_scalar(front_matter: str, key: str, value: str) -> str:
    """Replace ``key: …`` in a front-matter block, or append it when absent.

    Line-based on purpose: a YAML round-trip would reformat and reorder the whole block, so a
    one-field cut would land as a whole-file diff and the review that matters would be buried.
    """
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*:.*$", re.MULTILINE)
    if pattern.search(front_matter):
        return pattern.sub(rf"\g<1>{key}: {value}", front_matter, count=1)
    suffix = "" if front_matter.endswith("\n") else "\n"
    return f"{front_matter}{suffix}{key}: {value}\n"


def archived_ids(root: Path) -> list[str]:
    """Every id that has an archive directory, sorted. Missing archive root reads as empty."""
    base = archive_root(root)
    if not base.is_dir():
        return []
    return sorted(child.name for child in base.iterdir() if child.is_dir())


@dataclass(frozen=True)
class Defect:
    """One thing wrong with an archived document's record."""

    doc_id: str
    message: str
    evidence: str = ""


def audit_id(root: Path, doc_id: str) -> list[Defect]:
    """Everything wrong with one document's archive: the record against the bytes on disk.

    Four ways an archive can lie, each checked, because an archive nobody audits certifies only
    that somebody once copied a file:

    * a **version directory with no history row** — a snapshot whose cut nothing recorded;
    * a **history row with no version directory** — a cut whose snapshot is gone;
    * a **version directory that does not hold exactly one file** — nothing can say which bytes
      the version *is*;
    * a **snapshot whose sha256 no longer matches the row** — the record and the bytes disagree,
      which is the only one of the four that a casual reader could never notice.
    """
    defects: list[Defect] = []
    on_disk = set(versions_on_disk(root, doc_id))
    entries = read_history(root, doc_id)
    recorded = {entry.version for entry in entries}

    for version in sorted(on_disk - recorded):
        defects.append(
            Defect(
                doc_id,
                f"v{version} exists on disk but {HISTORY_NAME} records no row for it",
                evidence=f"recorded: {sorted(recorded) or 'none'}",
            )
        )
    for version in sorted(recorded - on_disk):
        defects.append(
            Defect(
                doc_id,
                f"{HISTORY_NAME} records v{version} but no directory exists for it",
                evidence=f"on disk: {sorted(on_disk) or 'none'}",
            )
        )

    for entry in entries:
        if entry.version not in on_disk:
            continue
        snapshot = snapshot_in(root, doc_id, entry.version)
        if snapshot is None:
            defects.append(
                Defect(
                    doc_id,
                    f"v{entry.version} does not hold exactly one snapshot file",
                    evidence=str(version_dir(root, doc_id, entry.version)),
                )
            )
            continue
        actual = sha256_bytes(snapshot.read_bytes())
        if actual != entry.sha256:
            defects.append(
                Defect(
                    doc_id,
                    f"v{entry.version} snapshot bytes no longer match the sha256 its history "
                    "recorded — the archive has been edited after the cut",
                    evidence=f"recorded {entry.sha256[:12]}…, measured {actual[:12]}…",
                )
            )
    return defects
