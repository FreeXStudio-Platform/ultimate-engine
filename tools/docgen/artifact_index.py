"""A project's own map of everything this engine has built for it.

Solves a specific problem: an agent (or a person) doing sustained work on a large project —
dozens of generated documents, charts, graphs, diagrams — loses track of what already exists,
where it lives, and whether it's finished. This module is a tiny, stdlib-only, JSON-backed
registry: register an artifact once when you create or finish it, then query "what do I have"
instead of re-deriving it from memory or re-scanning the filesystem by hand.

This is NOT a build system and NOT a database — it's a flat JSON file
(PROJECT_INDEX.json, at the host project's root by default) that you read and write
explicitly. Nothing in this engine writes to it automatically; an agent using docgen/
chart-engine/graph-engine/mermaid-engine to produce something is expected to call
``register_artifact`` right after, the same way it would note the fact in any other memory.

Stdlib only (json/pathlib/dataclasses) apart from two deliberate engine imports: ``engine_config``
(where the index file and the confidential vault live) and the doc-system classification authority
used by ``register_artifact``'s fail-closed gate. That gate is not optional decoration —
``PROJECT_INDEX.json`` is a TRACKED file, so an entry naming a confidential document publishes its
path, title and summary past both commit-time hooks. See ``RegistrationRefused``.

**Home moved here 2026-09-24.** This used to live at ``tools/project_index/index.py`` and
``tools.docgen.views`` imported it from there. That made audience views (``views.py``)
unconditionally inert in any host project that vendors ``tools/docgen`` without also vendoring
``tools/project_index`` and happens to own an unrelated package of the same name — one downstream host is
exactly that host: it vendors ``tools/docgen`` but keeps its own ``tools/project_index`` (a
docs-index/supersession gate — see that host's engine-profile file ▸
``not_vendored``), so ``from tools.project_index import index`` there imports a module with no
``index`` submodule at all and ``views.ViewRegistrationUnavailable`` fired on every build. Moving
the implementation into ``tools/docgen`` — a package every consuming host already vendors whole —
means this registry now travels WITH ``views.py`` instead of depending on a sibling package a host
may deliberately not have. ``tools/project_index/index.py`` is now a thin re-export shim over this
module, kept only so the engine's own ``tools.project_index.cli``/``dashboard`` and this
standalone repo's existing entry points (``python3 -m tools.project_index.cli ...``) keep working
unchanged — see that file's docstring for why patching a private name through the shim does not
patch this module's own behaviour, and always target ``tools.docgen.artifact_index`` directly for
that.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from tools.docgen import engine_config
from tools.docgen.hooks.staged_content_scanner import (
    _decode_for_scanning,
    classify_file,
)


def _index_path() -> Path:
    """Where the index file lives — see engine_config.project_index_path()
    (env var > engine.config.json's projectIndex.path > host project root)."""
    return engine_config.project_index_path()


@dataclass
class Artifact:
    """One registered thing this engine built: a document, a chart, a graph, a diagram."""

    id: str
    path: str
    type: str  # "document" | "chart" | "graph" | "diagram" | "map" | "mermaid" | "other"
    title: str
    section: str = ""  # a free-text grouping, e.g. "Architecture", "Q3 Report"
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    status: str = "draft"  # "draft" | "review" | "final" — free text, not enforced
    created: str = ""  # caller-supplied timestamp/date string (this module never calls
    #                    datetime.now() itself — determinism/testability, matching the rest
    #                    of this engine's "no wall-clock in generated output" discipline)
    updated: str = ""
    engine: str = ""  # which engine produced it, e.g. "document-engine", "chart-engine"


class IndexUnreadable(RuntimeError):
    """``PROJECT_INDEX.json`` exists but could not be parsed.

    Raised rather than swallowed because the quiet path was data loss: ``_load`` used to turn any
    unparseable index into ``{"artifacts": []}``, and the very next ``_save`` wrote that empty list
    back over the file — every registered artifact destroyed, exit code 0, nothing printed. Absent
    and unparseable are different questions and only one of them has a safe default.
    """


def _load(*, for_write: bool = False) -> dict[str, Any]:
    p = _index_path()
    if not p.is_file():
        return {"artifacts": []}          # genuinely absent — an empty index is the right answer
    try:
        loaded: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        return loaded
    except (OSError, ValueError) as exc:
        # ValueError covers UnicodeDecodeError as well as JSONDecodeError; the narrower tuple used
        # to crash on a non-UTF-8 index while silently wiping a UTF-8 one (LESSONS.md L-17).
        if for_write:
            raise IndexUnreadable(
                f"{p} exists but could not be read as JSON ({exc}). Refusing to overwrite it — "
                "move or repair the file, then retry."
            ) from exc
        return {"artifacts": []}


def _save(data: dict[str, Any]) -> None:
    p = _index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


class RegistrationRefused(ValueError):
    """``register_artifact`` refused to name a non-public document in the index.

    ``PROJECT_INDEX.json`` is TRACKED (``git ls-files PROJECT_INDEX.json`` lists it), so every
    field written here — ``path``, ``title``, ``summary``, ``tags`` — enters committed, public
    history. That makes this module an *index*, and RULEBOOK L14 says an index is itself a PUBLIC
    artifact that must carry zero non-public content, not even a title.

    Until this class existed there was no classification gate here at all
    (``grep -rn 'classification|Tier|confidential' -E tools/project_index/`` returned nothing),
    while the sibling that answers the identical question — ``tools/docgen/build_index.py`` —
    is fail-closed at two separate sites. One root, two consumers, one guarded: the ``OG-84``
    shape. Measured end-to-end through the real installed hooks before this gate existed::

        $ python3 -m tools.project_index.cli register --id leak-1 \
            --path docs/confidential/SECRET-NOTES.md --type document \
            --title "Acquisition target shortlist Q4" \
            --summary "Board-only shortlist: Acme, Zenith, Northwind" --status final
        registered: leak-1 (document) -> docs/confidential/SECRET-NOTES.md
        $ git add PROJECT_INDEX.json
        $ python3 -m tools.docgen.hooks.staged_content_scanner ; echo $?
        0
        $ ~/.claude/scripts/secret-scan.sh <staged blob> ; echo $?
        ✓ secret-scan: 1 file(s), 33 lines actually read — no definite secret pattern.
        0

    Neither commit-time gate can see it: the placement gate judges the *document's* own blob (which
    is gitignored and never staged), and the leak is a paraphrase in a ``.json``, which carries no
    secret pattern and whose suffix the push-time placement gate skips outright.
    """


# How much of a named file to read when looking for a doc-system header. Both header syntaxes are
# anchored at the very start of the file (``classification._FRONT_MATTER_RE`` and the scanner's
# ``_LEGACY_CLASSIFICATION_RE`` both begin ``\A``), so the head is the whole question — and a cap
# keeps `register` from pulling a 500 MB PDF into memory to learn it has no YAML in it.
_HEADER_READ_LIMIT = 262_144


def _path_parts(raw: str) -> tuple[str, ...]:
    """``raw`` as posix path segments with ``.`` dropped and ``..`` resolved TEXTUALLY.

    Resolving ``..`` here rather than rejecting it is the difference between a containment test and
    a spelling test. ``staged_content_scanner.is_inside_confidential_dir`` refuses any path
    containing ``..`` outright, which is correct for *that* gate (a staged path that climbs out is
    never legitimately inside the vault) — but reused verbatim here it inverts: this gate refuses
    what is inside the vault, so "contains ``..`` → not inside" hands the caller an escape,
    ``docs/../docs/confidential/x.md``, that normalises straight back in.
    """
    parts: list[str] = []
    for part in PurePosixPath(raw.replace("\\", "/").strip()).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts and parts[-1] not in ("..", "/"):
                parts.pop()
            else:
                parts.append(part)
            continue
        parts.append(part)
    return tuple(parts)


def _starts_with(candidate: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    """Case-INSENSITIVE segment-prefix containment (``==`` counts: the vault dir is not indexable).

    Case-insensitive because this engine's own reference platform (macOS/APFS) is, so
    ``DOCS/Confidential/x.md`` opens exactly the same bytes as ``docs/confidential/x.md`` — and
    ``Path.resolve()`` does not canonicalise case there, so the filesystem route below cannot catch
    it either. On a case-sensitive host the cost of this is refusing to index a hypothetical
    directory that differs from the vault only in case, which is not a real artifact location.
    """
    if len(candidate) < len(prefix) or not prefix:
        return False
    return [p.casefold() for p in candidate[: len(prefix)]] == [p.casefold() for p in prefix]


def _is_vault_path(raw: str) -> bool:
    """True if ``raw`` names anything inside the configured confidential vault.

    Two independent routes, because either alone is walkable:

    * **textual** — ``..``-normalised, case-folded segment containment against
      ``engine_config.confidential_dir_relative()`` (the same host-root-relative value the
      placement gate uses, with all of its ``OG-92``/``OG-102``/``OG-128`` refusals already
      applied). Catches the vault path that does not exist on disk *yet* — an artifact may be
      registered before it is built, and ``verify()`` exists precisely to report that gap, so a
      not-yet-created vault document must still be refused.
    * **filesystem** — ``resolve()``d absolute containment. Catches an absolute ``--path``, and a
      symlink whose name says ``docs/public/`` while its target is in the vault.

    Deliberately NOT routed through ``staged_content_scanner.is_inside_confidential_dir``: that
    helper additionally returns False when the vault is not git-ignored (``OG-167``), which fails
    CLOSED for a gate that refuses documents *outside* the vault and would fail OPEN here, where
    "not inside the vault" is the permissive answer. Same question, opposite polarity — a
    non-git-ignored vault makes registering its contents worse, not safer.
    """
    vault_rel = engine_config.confidential_dir_relative()
    vault_parts = _path_parts(vault_rel)
    root = _artifact_root()
    cleaned = raw.replace("\\", "/").strip()
    candidate = Path(cleaned)
    # A registered path is relative to the INDEX's directory, while the vault is relative
    # to the HOST root. When the index is relocated below the host root the two frames differ, so
    # the textual route must compare the candidate re-expressed host-relative: without that,
    # `../../confidential/x` from `docs/design/doc-system/` never matched `docs/confidential`
    # (found in a code review of the copy, P1). The index-relative spelling is still checked
    # too, which is the only frame when the index sits at the host root.
    if _starts_with(_path_parts(cleaned), vault_parts):
        return True
    if not candidate.is_absolute():
        index_dir = os.path.relpath(root, engine_config.host_root())
        if _starts_with(_path_parts(f"{index_dir}/{cleaned}"), vault_parts):
            return True
    absolute = candidate if candidate.is_absolute() else root / candidate
    try:
        resolved = absolute.resolve()
        # The configured vault is host-root-relative. Refuse anything inside it as resolved from
        # EITHER anchor: the host root (the correct frame once the index is relocated) and the
        # index's directory (the frame every pre-relocation host, and caller, has used). Refusing
        # more is the fail-closed direction for a gate whose permissive answer leaks.
        vault_anchors = (
            engine_config.confidential_dir().resolve(),
            (root / vault_rel).resolve(),
        )
    except (OSError, RuntimeError):
        # A path this process cannot even resolve (symlink loop, permission wall) is not one to
        # take on trust — fail closed, matching the rest of the engine.
        return True
    return any(_starts_with(resolved.parts, anchor.parts) for anchor in vault_anchors)


def _refusal_reason(artifact: Artifact) -> str | None:
    """Why this artifact may not enter the tracked index, or ``None`` if it may.

    Classification is decided by the same authority the commit-time gate uses —
    ``staged_content_scanner.classify_file``, which is ``classification.parse_header`` plus the
    legacy ``<!-- classification: … -->`` syntax, both fail-closed — rather than by a second,
    private notion of "classified" that could drift from it.
    """
    raw = artifact.path.strip()
    if not raw:
        return None  # a path-less entry names nothing; verify() already reports it as missing
    if _is_vault_path(raw):
        return (
            f"'{artifact.path}' resolves inside the confidential vault "
            f"'{engine_config.confidential_dir_relative()}/'."
        )

    root = _artifact_root()
    candidate = Path(raw.replace("\\", "/"))
    target = candidate if candidate.is_absolute() else root / candidate
    try:
        if not target.is_file():
            # Not built yet is a legitimate state for this hand-maintained registry (``verify``
            # reports it as ``missing``), and the vault test above already covers the case where
            # the *location* is the disclosure. Nothing readable, nothing to classify.
            return None
        with target.open("rb") as fh:
            data = fh.read(_HEADER_READ_LIMIT)
    except OSError as exc:
        return (
            f"'{artifact.path}' exists but could not be read ({exc}), so its classification "
            f"could not be established — refusing rather than assuming it is public."
        )
    # ⚠ **KNOWN RESIDUAL, and it belongs to the shared authority, not to this gate.**
    # ``_decode_for_scanning`` returns ``normalise_for_scanning``'s ADDITIVE buffer (raw bytes +
    # appended readable views), while both header patterns are ``\A``-anchored — so a
    # ``classification: secret`` document written as UTF-16 and placed OUTSIDE the vault reads as
    # header-less to ``classify_file`` and is accepted here. Measured at HEAD and in the working
    # tree (2026-08-23): ``classify_file('…/wide.md', _decode_for_scanning(<utf-16 secret>), root)``
    # -> ``None``, and the real installed pre-commit gate exits **0** on the same staged blob. That
    # is the placement gate's own blind spot; the same document inside the vault is still refused
    # here by ``_is_vault_path`` (containment, encoding-independent), and a fix at the root closes
    # this call site with it — which is exactly why the decision is delegated rather than copied.
    text = _decode_for_scanning(data)
    if text is None:
        return None  # genuinely binary (.png/.pdf) — carries no doc-system header to leak
    parts = _path_parts(raw)
    # ``_artifact_root()`` is the correct ``repo_root`` for the vault anchor: it is the directory the
    # index file itself lives in, which is the frame every registered ``path`` is already read
    # against (see ``_artifact_root``). Passing it explicitly rather than letting the scanner infer
    # one is the `OG-167` lesson — the CWD is not the host project.
    finding = classify_file(str(PurePosixPath(*parts)) if parts else raw, text, root)
    if finding is None:
        return None
    return f"'{artifact.path}' is not a public document — {finding.message}"


def _refuse_if_not_public(artifact: Artifact) -> None:
    """Fail-closed classification gate for the tracked index. See ``RegistrationRefused``."""
    reason = _refusal_reason(artifact)
    if reason is None:
        return
    raise RegistrationRefused(
        f"{reason} {_index_path().name} is a TRACKED, public artifact, so registering this would "
        f"commit the document's path, title and summary to public history (RULEBOOK L14 / "
        f"CLASSIFICATION.md). Refusing — nothing was written."
    )


def register_artifact(artifact: Artifact) -> None:
    """Add a new artifact, or update it in place if ``artifact.id`` already exists."""
    _refuse_if_not_public(artifact)
    data = _load(for_write=True)
    artifacts = data.setdefault("artifacts", [])
    for i, existing in enumerate(artifacts):
        if existing.get("id") == artifact.id:
            artifacts[i] = asdict(artifact)
            _save(data)
            return
    artifacts.append(asdict(artifact))
    _save(data)


def remove_artifact(artifact_id: str) -> bool:
    """Remove an artifact by id. Returns True if something was actually removed."""
    data = _load(for_write=True)
    artifacts = data.get("artifacts", [])
    before = len(artifacts)
    data["artifacts"] = [a for a in artifacts if a.get("id") != artifact_id]
    _save(data)
    return len(data["artifacts"]) < before


def list_artifacts(
    *, section: str | None = None, type: str | None = None, tag: str | None = None
) -> list[dict[str, Any]]:
    """All artifacts, optionally filtered by exact section/type match or tag membership."""
    artifacts: list[dict[str, Any]] = _load().get("artifacts", [])
    if section is not None:
        artifacts = [a for a in artifacts if a.get("section") == section]
    if type is not None:
        artifacts = [a for a in artifacts if a.get("type") == type]
    if tag is not None:
        artifacts = [a for a in artifacts if tag in (a.get("tags") or [])]
    return artifacts


def search_artifacts(query: str) -> list[dict[str, Any]]:
    """Case-insensitive substring match across title/summary/tags/section/path."""
    q = query.lower()
    results = []
    for a in _load().get("artifacts", []):
        haystack = " ".join(
            [
                a.get("title", ""),
                a.get("summary", ""),
                a.get("section", ""),
                a.get("path", ""),
                " ".join(a.get("tags") or []),
            ]
        ).lower()
        if q in haystack:
            results.append(a)
    return results


def sections() -> list[str]:
    """Every distinct, non-empty section name currently in use, sorted."""
    return sorted({a.get("section", "") for a in _load().get("artifacts", []) if a.get("section")})


def stats() -> dict[str, Any]:
    """A quick summary: counts by type, by section, by status — the 'what have I built' view."""
    artifacts = _load().get("artifacts", [])
    by_type: dict[str, int] = {}
    by_section: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for a in artifacts:
        by_type[a.get("type", "other")] = by_type.get(a.get("type", "other"), 0) + 1
        sec = a.get("section") or "(none)"
        by_section[sec] = by_section.get(sec, 0) + 1
        status = a.get("status", "draft")
        by_status[status] = by_status.get(status, 0) + 1
    return {"total": len(artifacts), "by_type": by_type, "by_section": by_section, "by_status": by_status}


def _artifact_root() -> Path:
    """Directory that a registered ``path`` is interpreted relative to.

    The index file's own directory — which under the default configuration IS the host project
    root, so ``examples/foo.html`` resolves the way a person would read it. Keeping the two
    together means moving the index moves its frame of reference with it, rather than silently
    re-pointing every relative path at a root the file no longer sits in.
    """
    return _index_path().parent


def verify(*, scan: str | None = None) -> dict[str, Any]:
    """Check the index against the filesystem. Returns findings; never modifies anything.

    The index is hand-maintained and nothing else in this engine writes to it, so it can
    disagree with reality in two directions and, until this function existed, could report
    neither — ``list``/``stats``/``dashboard`` present a registered artifact identically
    whether or not its file is still there. On a project with dozens of artifacts that is
    precisely how the map stops being trustworthy: not by being wrong loudly, but by being
    confidently stale.

    - ``missing``: registered artifacts whose ``path`` no longer resolves to a file. Either the
      artifact moved (update the entry) or it was deleted (``remove`` it).
    - ``unregistered``: only when ``scan`` is given — files under that directory that no
      artifact claims. Advisory, not an error: plenty of files legitimately are not artifacts.
      Restricted to the output extensions this engine actually produces.
    - ``duplicate_paths``: two or more ids pointing at the same file, which usually means the
      same artifact was registered twice under different ids.
    """
    root = _artifact_root()
    # `verify` exists specifically so the registry can be FALSIFIED rather than merely trusted, and
    # it was the one caller that must not use the read path's safe default: an unreadable index
    # degraded to zero artifacts and it reported success over an empty set. Listing may degrade;
    # verifying may not.
    artifacts = _load(for_write=True).get("artifacts", [])
    if not isinstance(artifacts, list):
        raise IndexUnreadable(
            f"{_index_path()} parsed, but 'artifacts' is {type(artifacts).__name__}, not a list. "
            "Refusing to report a verification result over a payload of the wrong shape."
        )

    missing = []
    by_path: dict[str, list[str]] = {}
    for a in artifacts:
        rel = a.get("path", "")
        if not rel:
            missing.append({"id": a.get("id", "?"), "path": "", "reason": "no path recorded"})
            continue
        by_path.setdefault(rel, []).append(a.get("id", "?"))
        if not (root / rel).is_file():
            missing.append({"id": a.get("id", "?"), "path": rel, "reason": "file not found"})

    duplicate_paths = [
        {"path": p, "ids": sorted(ids)} for p, ids in sorted(by_path.items()) if len(ids) > 1
    ]

    unregistered: list[str] = []
    if scan:
        known = {a.get("path", "") for a in artifacts}
        scan_dir = root / scan if not Path(scan).is_absolute() else Path(scan)
        if scan_dir.is_dir():
            for f in sorted(scan_dir.rglob("*")):
                if not f.is_file() or f.suffix.lower() not in _OUTPUT_SUFFIXES:
                    continue
                try:
                    rel = str(f.relative_to(root))
                except ValueError:
                    rel = str(f)
                if rel not in known:
                    unregistered.append(rel)

    return {
        "index_path": str(_index_path()),
        "artifact_root": str(root),
        "total": len(artifacts),
        "missing": missing,
        "duplicate_paths": duplicate_paths,
        "unregistered": unregistered,
        "ok": not missing and not duplicate_paths,
    }


# Output formats this engine actually emits — the `--scan` direction only reports these, so a
# scan of a source tree does not drown the real signal in .py/.md/.json noise.
_OUTPUT_SUFFIXES = {".html", ".svg", ".png", ".pdf"}


__all__ = [
    "Artifact",
    "RegistrationRefused",
    "list_artifacts",
    "register_artifact",
    "remove_artifact",
    "search_artifacts",
    "sections",
    "stats",
    "verify",
]
