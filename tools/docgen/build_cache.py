"""Content-hash-keyed incremental build cache for the doc-system engine (ENGINE_PLAN §4b).

The generator is deterministic: identical inputs (source markdown + sibling figure spec +
requested formats + ``local_preview`` flag + engine source) always produce byte-identical
outputs (``generator.build`` embeds no wall-clock timestamps in hashed content). That property
is exactly what makes a content-hash cache SAFE: if the cache key for a document is unchanged
AND every output it produced last time still exists on disk, rebuilding would reproduce the
same bytes, so the build can be skipped.

Design (all fail-open — a cache miss, a corrupt entry, an unreadable file, or ANY error
degrades to a full ``generator.build``; the cache is only ever an optimization, never a
gate and never a source of truth):

* **Key** = sha256 over, in a fixed order: the source ``.md`` bytes, the sibling
  ``<stem>_spec.json`` bytes (or a sentinel when absent), the sorted requested ``formats``,
  the ``local_preview`` flag, and an **engine-source fingerprint** (the sha256 of every
  ``tools/docgen/*.py`` file). Folding the engine fingerprint in means any change to the
  renderer/generator/gate invalidates every entry — a doc whose output would differ after an
  engine edit is never wrongly skipped.
* **Store** = one JSON file (default ``<build_dir>/.docgen_cache.json``), mapping the
  canonical source path (repo-relative) to ``{key, outputs: [rel_path, ...]}``. The outputs
  are recorded so a skip can verify every promised artifact is still present before trusting
  the entry (a deleted output forces a rebuild).

Nothing here embeds a timestamp, so the cache file itself is deterministic given the same
corpus + engine — two clean rebuilds write the same cache bytes.

This module NEVER relaxes the leak-gate: a skip only happens for a doc that already built
cleanly (its outputs are on disk, which only occurs when its gate passed). A blocked build
writes no output, so it is never cached as skippable and always re-runs the gate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from tools.docgen import generator
from tools.docgen.models import BuildResult, Finding, GateResult, Severity

_LOG = logging.getLogger("tools.docgen.build_cache")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCGEN_DIR = Path(__file__).resolve().parent
_DEFAULT_CACHE_NAME = ".docgen_cache.json"
_NO_SIBLING = b"\x00<no-sibling-spec>\x00"

# Cache-format version: bump if the key composition below changes so stale on-disk caches
# (written by an older layout) are treated as a miss rather than mis-trusted.
# v2 (2026-08-20): the key composition changed after an independent verification pass proved four
# classes of WRONG cache hit under v1 — assets/glyphs.py, assets/tokens.json and the embedded fonts
# were invisible to a non-recursive *.py glob, out_dir was absent entirely, and the whole
# doc-governance rule layer was outside the key while a skip synthesised a PASSING GateResult.
# Bumping the format makes every v1 cache a miss rather than something trusted.
# v3 (2026-08-20): the key now also covers the OUT-OF-TREE renderers (tools/mermaid-engine,
# tools/visual-engine/adapters + both package-lock.json). Under v2 an edit to either changed a
# built document's bytes but not the key, so --cached served a stale artifact under a success
# message — proven by mutating render.mjs and watching the marker survive a "1 reused" rebuild.
_CACHE_FORMAT = "docgen-build-cache/v3"


@dataclass(frozen=True)
class CacheEntry:
    """A single cached build record: the content key, the outputs, and their digests."""

    key: str
    outputs: dict[str, str]  # format -> repo-relative POSIX path of the written artifact
    # format -> sha256 of the bytes this build actually wrote. Absent in entries written before
    # 2026-08-21; `_entry_is_fresh` treats a missing digest as unverifiable and rebuilds, so an old
    # cache degrades to a miss rather than to a false hit.
    digests: dict[str, str] = field(default_factory=dict)


def _engine_fingerprint() -> str:
    """sha256 over **every file** under ``tools/docgen/`` (recursive, sorted), so any engine edit
    busts the cache.

    This used to glob ``*.py`` non-recursively, and an independent verification pass proved three
    separate classes of WRONG cache hit as a direct result — each one silently serving a stale
    artifact under a success message:

    * ``assets/glyphs.py`` is imported by ``visual.py`` and renders into the SVG, but lives one
      directory down, so the glob never saw it;
    * ``assets/tokens.json`` is the design-token source the entire visual layer is generated from,
      and is not a ``.py`` file at all;
    * the eight ``assets/fonts/*.woff2`` blobs are embedded base64 in every built document.

    So the defect was never the individual files — it was the glob. Hashing every file underneath
    is the conservative choice: it can only cause extra rebuilds, never a wrong skip, and "extra
    rebuild" is the failure mode a cache is *allowed* to have.

    Deterministic: entries are hashed in sorted order of their path **relative to** ``_DOCGEN_DIR``
    (bare ``p.name`` would collide across subdirectories now that the walk is recursive).
    ``__pycache__`` is excluded — it is derived from the ``.py`` files already hashed, and its
    mtime-keyed contents would make the fingerprint non-deterministic.
    """
    hasher = hashlib.sha256()
    for path in sorted(_DOCGEN_DIR.rglob("*"), key=lambda p: p.relative_to(_DOCGEN_DIR).as_posix()):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        hasher.update(path.relative_to(_DOCGEN_DIR).as_posix().encode("utf-8"))
        hasher.update(b"\x00")
        try:
            hasher.update(path.read_bytes())
        except OSError:  # pragma: no cover - a file vanishing mid-scan; fail toward a miss
            hasher.update(b"\x00<unreadable>\x00")
        hasher.update(b"\x00")
    return hasher.hexdigest()


# The two renderer bridges live OUTSIDE tools/docgen, so `_engine_fingerprint` cannot see them:
# mermaid figures render through tools/mermaid-engine/render.mjs and ECharts figures through
# tools/visual-engine/adapters/**. Editing either changed a built document's bytes but not the
# cache key, so `build --cached` reported "reused from cache" and left a STALE artifact on disk
# that the current engine would never produce — the docstring's "never a wrong skip" was false.
#
# Only inputs are hashed. `evidence/` and `renders/` are the engines' OWN OUTPUT and churn on every
# run (a benchmark's render_ms alone rewrites seven files), so including them would bust the cache
# constantly while proving nothing about the renderer. package-lock.json IS included: the rendered
# SVG depends on the pinned library versions, not just on our source.
_RENDERER_INPUTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tools/mermaid-engine", ("render.mjs", "package.json", "package-lock.json")),
    ("tools/visual-engine", ("package.json", "package-lock.json")),
)
_RENDERER_TREES: tuple[str, ...] = (
    "tools/visual-engine/adapters",
    "tools/visual-engine/themes",
    "tools/visual-engine/schemas",
    # Added 2026-08-21: `presets/` is a first-class TRACKED renderer input — render.mjs reads it
    # through resolvePreset()/listPresets() — and editing a preset changes the rendered bytes.
    "tools/visual-engine/presets",
)


def _renderer_fingerprint() -> str:
    """sha256 over the out-of-tree renderer sources the built document actually depends on."""
    hasher = hashlib.sha256()
    for rel, names in _RENDERER_INPUTS:
        for name in names:
            path = _REPO_ROOT / rel / name
            hasher.update(f"{rel}/{name}".encode())
            hasher.update(b"\x00")
            try:
                hasher.update(path.read_bytes() if path.is_file() else b"<absent>")
            except OSError:  # pragma: no cover - fail toward a miss, never toward a stale hit
                hasher.update(b"<unreadable>")
            hasher.update(b"\x00")
    for rel in _RENDERER_TREES:
        root = _REPO_ROOT / rel
        if not root.is_dir():
            hasher.update(f"{rel}\x00<absent>\x00".encode())
            continue
        for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
            if not path.is_file() or "node_modules" in path.parts:
                continue
            hasher.update(f"{rel}/{path.relative_to(root).as_posix()}".encode())
            hasher.update(b"\x00")
            try:
                hasher.update(path.read_bytes())
            except OSError:  # pragma: no cover
                hasher.update(b"<unreadable>")
            hasher.update(b"\x00")
    return hasher.hexdigest()


def _rule_layer_fingerprint() -> str:
    """sha256 over the doc-governance data the BUILD GATES read.

    Why this is not optional. A cache hit does not re-run the gates — :func:`_skipped_result`
    synthesizes a passing ``GateResult`` outright. Under v1 the key covered the document and the
    engine but **nothing the gates consult**, so editing ``DOC_MANIFEST.md`` or ``TAXONOMY.md`` to
    make a document *illegal* left it building green from cache, with the stale artifact still on
    disk and the CLI reporting success. That is a blocking gate bypassed by an optimisation, which
    is not a performance trade-off — it is silent corruption of a governed artifact.

    Hashed by resolved path (honouring the ``engine_config`` overrides), so pointing the engine at
    a different rule layer is itself a key change. Unreadable or absent files hash to a sentinel
    rather than being skipped: "the rules could not be read" must not collide with "the rules say
    what they said last time".
    """
    from tools.docgen import engine_config

    doc_system = engine_config.doc_system_dir()
    # DERIVED from VERSION.json's own `rulebook_files`, never a hand-maintained literal. The list
    # used to be seven paths written out here while `rulebook_files` held nine — so the two moat
    # hooks were hash-LOCKED as rules and simultaneously absent from the cache key, and adding any
    # future locked file would silently fail to invalidate the cache. The answer and the question
    # must not live in two places (LESSONS.md L-13); `docs/process/RULES.md` Rule 2 is the same
    # principle for prose.
    inputs: list[Path] = [engine_config.version_json_path()]
    try:
        declared = json.loads(engine_config.version_json_path().read_text(encoding="utf-8"))
        listed = declared.get("rulebook_files")
        if isinstance(listed, list):
            inputs += [_REPO_ROOT / str(rel) for rel in listed]
    except (OSError, ValueError, AttributeError):
        # Unreadable VERSION.json: fall back to the floor below and let the hash gate itself report
        # the real problem. Failing toward MORE hashed inputs can only cause extra rebuilds.
        pass
    # A floor, so a shrunken or unreadable `rulebook_files` cannot quietly narrow the key.
    inputs += [
        engine_config.doc_manifest_path(),
        doc_system / "TAXONOMY.md",
        doc_system / "RULEBOOK.md",
        doc_system / "CONTRADICTION.md",
        doc_system / "update_impact_map.json",
        # The config ACTUALLY IN FORCE, not the literal file — every other entry in this
        # list resolves through `engine_config`, and a run under `ENGINE_CONFIG_PATH`
        # would otherwise fingerprint a file it is ignoring (`F8`).
        engine_config.config_path(),
    ]
    seen: set[str] = set()
    deduped: list[Path] = []
    for candidate in inputs:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    inputs = deduped
    hasher = hashlib.sha256()
    for path in inputs:
        hasher.update(str(path).encode("utf-8"))
        hasher.update(b"\x00")
        try:
            hasher.update(path.read_bytes())
        except OSError:
            hasher.update(b"\x00<absent-or-unreadable>\x00")
        hasher.update(b"\x00")
    return hasher.hexdigest()


def _sibling_spec_bytes(md_path: Path) -> bytes:
    """Return the ``<stem>_spec.json`` sidecar bytes, or a stable sentinel when absent/unreadable."""
    sidecar = md_path.with_name(f"{md_path.stem}_spec.json")
    try:
        return sidecar.read_bytes()
    except OSError:
        return _NO_SIBLING


def compute_key(
    md_path: Path,
    *,
    formats: tuple[str, ...],
    local_preview: bool,
    engine_fingerprint: str,
    rule_layer_fingerprint: str,
    out_dir: Path | None,
) -> str:
    """Content key for one document build.

    Composes, in a fixed order: the source bytes, the sibling spec bytes, the sorted formats, the
    ``local_preview`` flag, the **output directory**, the engine fingerprint (which covers
    ``tools/docgen`` **and** the out-of-tree renderer bridges) and the **rule-layer fingerprint**. Fixed field order + sorted formats keep it deterministic. Raises ``OSError``
    only if the source markdown itself cannot be read (the caller treats that as a miss and lets
    ``generator.build`` surface the real error).

    ``out_dir`` is in the key because a cache entry records *where* it wrote its outputs, and
    :func:`_entry_is_fresh` only checks that those recorded paths still exist. Without it, building
    the same source into a different ``-o`` with a shared cache reported a successful skip and
    wrote **nothing at all** to the requested directory.
    """
    hasher = hashlib.sha256()
    hasher.update(_CACHE_FORMAT.encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(md_path.read_bytes())
    hasher.update(b"\x00")
    hasher.update(_sibling_spec_bytes(md_path))
    hasher.update(b"\x00")
    hasher.update(",".join(sorted(formats)).encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(b"lp=1" if local_preview else b"lp=0")
    hasher.update(b"\x00")
    hasher.update(b"<beside-source>" if out_dir is None else repo_rel(out_dir).encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(engine_fingerprint.encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(rule_layer_fingerprint.encode("utf-8"))
    return hasher.hexdigest()


def load_cache(cache_path: Path) -> dict[str, CacheEntry]:
    """Read the on-disk cache. Fail-open: any error (missing, corrupt, wrong format) → empty.

    ``ValueError`` — not ``json.JSONDecodeError`` — because a cache file containing non-UTF-8 bytes
    raises ``UnicodeDecodeError``, which is a ``ValueError`` and is NOT an ``OSError``. Under the
    narrower handler it escaped this module entirely and crashed the build, contradicting the
    docstring's promise that ANY error degrades to a full rebuild. This repository has paid for the
    identical mistake once before, in ``classification.load_taxonomy_prefixes``.
    """
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict) or raw.get("format") != _CACHE_FORMAT:
        return {}
    entries_obj = raw.get("entries")
    if not isinstance(entries_obj, dict):
        return {}
    out: dict[str, CacheEntry] = {}
    for src, record in entries_obj.items():
        if not isinstance(record, dict):
            continue
        key = record.get("key")
        outputs = record.get("outputs")
        if not isinstance(key, str) or not isinstance(outputs, dict):
            continue
        # Coerce/validate the outputs mapping (format -> str path); skip malformed entries.
        clean_outputs = {
            str(fmt): str(rel) for fmt, rel in outputs.items() if isinstance(rel, str)
        }
        raw_digests = record.get("digests")
        clean_digests = (
            {str(fmt): str(d) for fmt, d in raw_digests.items() if isinstance(d, str)}
            if isinstance(raw_digests, dict) else {}
        )
        out[str(src)] = CacheEntry(key=key, outputs=clean_outputs, digests=clean_digests)
    return out


def save_cache(cache_path: Path, cache: dict[str, CacheEntry]) -> None:
    """Write the cache deterministically (sorted keys, no timestamp). Fail-open: log + return on error.

    **Merges before writing, and replaces atomically.** Two ``build --cached`` runs sharing one
    cache file used to silently discard each other's work: each loaded the file at entry and wrote
    its own dict at exit, so the second writer erased every entry the first had earned — a textbook
    lost update, invisible in both directions because both runs printed a successful summary. It is
    not an exotic case: with no ``-o``, ``--cached`` puts every document in ONE repo-wide file, so
    any two concurrent builds in the same checkout collide.

    Merge is last-writer-wins **per source path**, never per file, so a concurrent run's unrelated
    entries survive. ``os.replace`` makes the swap atomic, so a reader never observes a half-written
    cache. Neither is a lock: two writers can still interleave between the re-read and the replace,
    and the worst outcome of that race is a lost entry — a future rebuild, never a wrong skip.
    """
    merged: dict[str, CacheEntry] = dict(load_cache(cache_path))
    merged.update(cache)
    payload = {
        "format": _CACHE_FORMAT,
        "entries": {
            src: {"key": entry.key, "outputs": entry.outputs, "digests": entry.digests}
            for src, entry in sorted(merged.items())
        },
    }
    tmp_path = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(tmp_path, cache_path)
    except OSError as exc:  # pragma: no cover - disk/permission failure; cache is best-effort
        _LOG.warning("build_cache: could not write cache %s: %s", cache_path, exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            # Best-effort cleanup of the temp file the failed `os.replace` above left behind.
            # `missing_ok=True` already absorbs "it's gone"; anything else reaching here is the
            # SAME disk/permission failure just logged above, so a stray temp file is the known,
            # harmless cost — worth a debug line, never worth escalating past the warning already
            # issued for the real failure (N22).
            _LOG.debug("build_cache: could not remove stale temp file %s: %s", tmp_path, cleanup_exc)


def repo_rel(path: Path) -> str:
    """POSIX repo-relative path for stable cache keys/values; falls back to the absolute path.

    Public because callers need it to line ``CorpusResult.results`` (keyed by this) back up with
    the paths they passed in — reaching into a private helper for that is how a consumer ends up
    carrying a ``noqa: SLF001`` forever.
    """
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _entry_is_fresh(entry: CacheEntry, key: str) -> bool:
    """Trusted iff the key matches AND every recorded output still exists **with the bytes it had**.

    Existence was not enough. The entry recorded WHERE a build wrote, never WHAT it wrote, so any
    out-of-band change to a built artifact — an edit, a truncation, a half-finished copy, another
    tool writing to the same path — survived a cached run reported as success, with the 7-gate
    export sanitizer never re-run over the bytes that are actually on disk.

    A missing digest (an entry written before digests existed) is treated as UNVERIFIABLE and
    rebuilds. Fail toward a miss: an extra rebuild is the failure mode a cache is allowed to have.
    """
    if entry.key != key:
        return False
    if not entry.outputs:
        return False
    for fmt, rel in entry.outputs.items():
        candidate = (_REPO_ROOT / rel).resolve()
        if not candidate.is_file():
            return False
        recorded = entry.digests.get(fmt)
        if not recorded:
            return False
        try:
            if hashlib.sha256(candidate.read_bytes()).hexdigest() != recorded:
                return False
        except OSError:
            return False
    return True


def _skipped_result(doc_id: str, entry: CacheEntry) -> BuildResult:
    """Synthesize a passing ``BuildResult`` for a cache-hit skip (no gate re-run needed)."""
    outputs = {fmt: (_REPO_ROOT / rel) for fmt, rel in entry.outputs.items()}
    gate = GateResult(
        gate="build-cache",
        findings=[
            Finding(
                gate="build-cache",
                message=f"unchanged — reused cached build ({doc_id})",
                severity=Severity.INFO,
                blocking=False,
            )
        ],
    )
    return BuildResult(doc_id=doc_id, gate=gate, outputs=outputs)


def build_cached(
    md_path: Path,
    *,
    formats: tuple[str, ...] = ("html",),
    out_dir: Path | None = None,
    local_preview: bool = False,
    cache: dict[str, CacheEntry],
    engine_fingerprint: str,
    rule_layer_fingerprint: str | None = None,
) -> tuple[BuildResult, bool]:
    """Build ``md_path`` through the cache. Returns ``(result, was_skipped)``.

    Fail-open at every step: if the key cannot be computed, if the entry is stale, or if the
    entry is missing, fall straight through to ``generator.build``. A cache hit is trusted ONLY
    when the content key matches AND every output it recorded is still on disk — otherwise the
    document is rebuilt and the cache is refreshed. A blocked build (``result.ok`` False) is
    NOT cached as skippable (it produced no trustworthy outputs), so the gate always re-runs on
    a still-broken document.

    The passed ``cache`` dict is mutated in place with the fresh entry on a real build; the
    caller persists it once at the end via :func:`save_cache`.
    """
    src_key = repo_rel(md_path)
    if rule_layer_fingerprint is None:
        rule_layer_fingerprint = _rule_layer_fingerprint()
    try:
        key = compute_key(
            md_path,
            formats=formats,
            local_preview=local_preview,
            engine_fingerprint=engine_fingerprint,
            rule_layer_fingerprint=rule_layer_fingerprint,
            out_dir=out_dir,
        )
    except OSError:
        # Source unreadable — let generator.build raise the real, honest error.
        result = generator.build(
            md_path, formats=formats, out_dir=out_dir, local_preview=local_preview
        )
        return result, False

    existing = cache.get(src_key)
    if existing is not None and _entry_is_fresh(existing, key):
        # Recover the doc_id cheaply from the parsed header without a full build.
        try:
            from tools.docgen.classification import parse_header

            doc_id = parse_header(md_path.read_text(encoding="utf-8")).id
        except (OSError, ValueError, KeyError):
            doc_id = existing.outputs and next(iter(existing.outputs.values())) or src_key
        return _skipped_result(str(doc_id), existing), True

    # Miss (or stale) → full build, then refresh the entry only if it produced outputs.
    result = generator.build(
        md_path, formats=formats, out_dir=out_dir, local_preview=local_preview
    )
    if result.ok and result.outputs:
        def _digest(path: Path) -> str:
            try:
                return hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:  # pragma: no cover - the file was just written
                return ""
        cache[src_key] = CacheEntry(
            key=key,
            outputs={fmt: repo_rel(path) for fmt, path in sorted(result.outputs.items())},
            digests={fmt: _digest(path) for fmt, path in sorted(result.outputs.items())},
        )
    else:
        # Do not cache a blocked/empty build as skippable; drop any stale entry for it.
        cache.pop(src_key, None)
    return result, False


def default_cache_path(build_dir: Path) -> Path:
    """The conventional cache file location for a corpus built into ``build_dir``."""
    return build_dir / _DEFAULT_CACHE_NAME


@dataclass
class CorpusResult:
    """Aggregate outcome of a corpus build: per-doc results plus which were skipped/blocked."""

    results: dict[str, BuildResult]  # source rel-path -> BuildResult
    skipped: list[str]  # source rel-paths reused from cache
    blocked: list[str]  # source rel-paths whose build was blocked

    @property
    def ok(self) -> bool:
        return not self.blocked


def build_corpus(
    md_paths: list[Path],
    *,
    formats: tuple[str, ...] = ("html",),
    out_dir: Path | None = None,
    local_preview: bool = False,
    cache_path: Path,
) -> CorpusResult:
    """Build many documents through one shared cache, skipping unchanged ones.

    Loads the cache once, builds each path via :func:`build_cached`, then persists the cache
    once at the end. Fail-open throughout: a corrupt cache simply means nothing is skipped this
    run. The engine fingerprint is computed a single time for the whole corpus so every doc is
    keyed against the same engine snapshot.
    """
    cache = load_cache(cache_path)
    # Both halves of "the code that produces the bytes": tools/docgen itself, and the two renderer
    # bridges that live outside it. Combined into one digest so the key composition is unchanged.
    fingerprint = hashlib.sha256(
        (_engine_fingerprint() + "|" + _renderer_fingerprint()).encode("utf-8")
    ).hexdigest()
    rule_fingerprint = _rule_layer_fingerprint()
    results: dict[str, BuildResult] = {}
    skipped: list[str] = []
    blocked: list[str] = []

    try:
        for md_path in md_paths:
            rel = repo_rel(md_path)
            # Per-document isolation. A renderer that raises used to abort the whole corpus AND
            # skip the save below, discarding every entry the earlier documents had just earned —
            # so one bad document made the next run rebuild everything. A raising document is a
            # BLOCKED document, recorded as a blocking finding and moved past; it is never cached
            # as skippable, so its gate re-runs every time until it is fixed.
            try:
                result, was_skipped = build_cached(
                    md_path,
                    formats=formats,
                    out_dir=out_dir,
                    local_preview=local_preview,
                    cache=cache,
                    engine_fingerprint=fingerprint,
                    rule_layer_fingerprint=rule_fingerprint,
                )
            except Exception as exc:  # noqa: BLE001 - a raising build is a blocked build, never a skip
                _LOG.warning("build_cache: %s raised %s", rel, type(exc).__name__)
                cache.pop(rel, None)
                result, was_skipped = (
                    BuildResult(
                        doc_id=rel,
                        gate=GateResult(
                            gate="build-cache",
                            findings=[
                                Finding(
                                    gate="build-cache",
                                    message=f"build raised {type(exc).__name__}: {exc}",
                                    severity=Severity.CRIT,
                                    blocking=True,
                                )
                            ],
                        ),
                        outputs={},
                    ),
                    False,
                )
            results[rel] = result
            if was_skipped:
                skipped.append(rel)
            if not result.ok:
                blocked.append(rel)
    finally:
        # In a `finally` so an interrupt or an escaping error still persists what was earned.
        save_cache(cache_path, cache)
    return CorpusResult(results=results, skipped=skipped, blocked=blocked)
