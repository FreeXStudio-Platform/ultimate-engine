"""``python -m tools.docgen.cli`` — argparse entry point for the doc-system engine.

Subcommands: ``build`` (one or many Markdown documents -> HTML/JSON/PDF via ``generator.build``,
or via the content-hash incremental cache under ``--cached``/``--cache``), ``render``
(a standalone ``VisualSpec`` JSON file -> SVG via ``visual.render``), ``manifest`` (print
``DOC_MANIFEST.md`` rows), and ``check`` (best-effort structural check: header validity +
manifest drift + gate re-run — the full hash-gate lives in ``validate_doc_system.py`` once
built; ``check`` here degrades honestly if that module is absent rather than pretending).

Exit codes: 0 = success, 1 = gate/validation failure, 2 = usage/IO error. ``--strict`` turns
advisory findings into hard failures (RULEBOOK L13/CLASSIFICATION.md gate spec).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from tools.docgen import (
    archive,
    build_cache,
    doc_manifest,
    engine_config,
    export_sanitizer,
    generator,
    identity,
    tokens,
    visual,
)
from tools.docgen.classification import parse_header, validate_header
from tools.docgen.generator import (
    _visual_spec_from_dict,
)
from tools.docgen.models import BuildResult, Finding, GateResult, Severity

# Resolved via engine_config (env var > engine.config.json > auto-detected git root > this
# engine's own directory) — see ../../CONFIGURATION.md. Previously each hardcoded independently
# off a fixed Path(__file__).resolve().parents[2]; now every doc-governance path in this CLI
# comes from the one shared loader, so there is a single place to override all of them.
_REPO_ROOT = engine_config.host_root()
_DOC_SYSTEM_DIR = engine_config.doc_system_dir()
_DOC_MANIFEST_PATH = engine_config.doc_manifest_path()
_VERSION_JSON_PATH = engine_config.version_json_path()
_TAXONOMY_PATH = _DOC_SYSTEM_DIR / "TAXONOMY.md"
_AUTHORED_DOCS_ROOT = engine_config.authored_docs_root()
_CONTENT_INDEX_PATH = engine_config.content_index_path()
# Where `--cached` puts the cache when no -o was given. Gitignored: it is derived state, and
# committing it would make a stale checkout skip builds it never actually ran.
_DEFAULT_CACHE_DIR = _REPO_ROOT / ".docgen"


def _emit_build_result(result: BuildResult, *, skipped: bool) -> None:
    """Print a single build's findings + written artifacts (shared by one-shot and watch)."""
    for finding in result.gate.findings:
        stream = sys.stderr if finding.blocking else sys.stdout
        stream.write(f"[{finding.gate}] {finding.severity.value}: {finding.message}\n")
    if skipped:
        sys.stdout.write(f"skipped (unchanged): {result.doc_id}\n")
        return
    for fmt, out_path in result.outputs.items():
        sys.stdout.write(f"wrote {fmt}: {out_path}\n")


def _resolve_cache_path(args: argparse.Namespace) -> Path | None:
    """The cache file this build should use, or ``None`` to rebuild everything.

    One resolver for every entry point (one-shot and ``--watch``) so ``--cache`` and ``--cached``
    can never disagree about where the cache lives: an explicit ``--cache PATH`` always wins;
    ``--cached`` picks the conventional file beside the output directory, or under ``.docgen/``
    when no ``-o`` was given.

    ``--strict`` deliberately returns ``None``. A cache hit skips the gate re-run, so its only
    finding is the INFO "reused cached build" — which under ``--strict`` (advisories are failures)
    would either fail every cached build or, worse, let a document that *was* advisory-dirty pass
    because it was skipped. Strict wants a fresh verdict; a cache exists to avoid producing one.
    """
    # STRICT FIRST — unconditionally, before the explicit-path branch. This guard used to sit
    # BELOW `if args.cache`, so `--strict --cache PATH` kept its cache: the run then failed on the
    # skip's own INFO finding and blamed the document, while the document's real advisory findings
    # were never recomputed. Both horns of the dilemma this guard exists to prevent, on the one
    # flag it did not cover.
    if getattr(args, "strict", False):
        return None
    if args.cache:
        return Path(args.cache)
    if not getattr(args, "cached", False):
        return None
    base = Path(args.out_dir) if args.out_dir else _DEFAULT_CACHE_DIR
    return build_cache.default_cache_path(base)


def _build_paths(
    md_paths: list[Path],
    *,
    formats: tuple[str, ...],
    out_dir: Path | None,
    local_preview: bool,
    cache_path: Path | None,
) -> list[tuple[BuildResult, bool]]:
    """Build one or many documents, optionally through the incremental cache.

    Returns one ``(result, was_skipped)`` per input, **in input order**. When ``cache_path`` is
    set the whole list goes through ``build_cache.build_corpus`` — one cache load, one engine
    fingerprint, one save for the corpus — so an N-document build does not re-hash the engine N
    times. Fail-open throughout: a corrupt or absent cache just means nothing is skipped this run.
    """
    if cache_path is None:
        # Per-document isolation, matching build_corpus exactly. OG-24 gave the CACHED path this
        # and stopped there, so the same corpus, same command, differing only by a performance
        # flag, produced two entirely different failure surfaces: a clean `[build-cache] crit:`
        # finding plus a BLOCKED summary with --cached, versus an uncaught traceback and an
        # abandoned corpus without it. An optimisation must not have a STRONGER contract than the
        # path it optimises (LESSONS.md L-16, read in the other direction).
        out: list[tuple[BuildResult, bool]] = []
        for md_path in md_paths:
            try:
                out.append((
                    generator.build(
                        md_path, formats=formats, out_dir=out_dir, local_preview=local_preview
                    ),
                    False,
                ))
            except Exception as exc:  # noqa: BLE001 - a raising build is a blocked build
                out.append((
                    BuildResult(
                        doc_id=build_cache.repo_rel(md_path),
                        gate=GateResult(
                            gate="build",
                            findings=[
                                Finding(
                                    gate="build",
                                    message=f"build raised {type(exc).__name__}: {exc}",
                                    severity=Severity.CRIT,
                                    blocking=True,
                                )
                            ],
                        ),
                        outputs={},
                    ),
                    False,
                ))
        return out

    corpus = build_cache.build_corpus(
        md_paths,
        formats=formats,
        out_dir=out_dir,
        local_preview=local_preview,
        cache_path=cache_path,
    )
    skipped = set(corpus.skipped)
    return [
        (corpus.results[build_cache.repo_rel(md_path)], build_cache.repo_rel(md_path) in skipped)
        for md_path in md_paths
    ]


def _emit_corpus_summary(
    pairs: list[tuple[BuildResult, bool]], *, elapsed_s: float, cache_path: Path | None
) -> None:
    """Print the one measured line: wall-clock, and how much of the corpus the cache skipped.

    This exists so a cache hit is evidence the tool *produces*, not a claim the operator makes
    with a stopwatch — BUILD_PLAN §3 Phase 2's exit condition is a **measured** hit.
    """
    reused = sum(1 for _, was_skipped in pairs if was_skipped)
    where = f" [cache: {cache_path}]" if cache_path is not None else ""
    sys.stdout.write(
        f"built {len(pairs)} doc(s) in {elapsed_s:.3f}s — "
        f"{reused} reused from cache, {len(pairs) - reused} rebuilt{where}\n"
    )


def _rulebook_gate_blocks() -> list[str]:
    """Blocking messages from the L9 rulebook hash-gate, or an empty list when it holds.

    Fail-closed: if the gate module cannot be imported at all, that is reported as a block rather
    than treated as "nothing to check".
    """
    try:
        from tools.docgen import validate_doc_system
    except ImportError as exc:
        return [f"validate_doc_system is unimportable ({exc}) — the hash-gate could not run"]
    result = validate_doc_system.check(rules_dir=_DOC_SYSTEM_DIR, version_json_path=_VERSION_JSON_PATH)
    return [f.message for f in result.findings if f.blocking]


def _cmd_build(args: argparse.Namespace) -> int:
    md_paths = [Path(raw) for raw in args.input]
    # Check every input up front. Without this a bad path surfaces as a raw FileNotFoundError
    # traceback from deep inside generator.build, and in a corpus it does worse: the run aborts
    # mid-list, so `save_cache` never runs and the entries the earlier documents just earned are
    # thrown away. A usage error is exit 2, not a stack trace.
    missing = [str(p) for p in md_paths if not p.is_file()]
    if missing:
        for path in missing:
            sys.stderr.write(f"docgen build: input not found: {path}\n")
        return 2
    formats = tuple(args.formats.split(",")) if args.formats else ("html",)
    out_dir = Path(args.out_dir) if args.out_dir else None
    # Create -o if it does not exist. generator.build writes straight into it, so a fresh output
    # directory used to surface as a FileNotFoundError traceback from pathlib — and `--cached`
    # makes that path far more common, since the conventional cache lives beside the outputs.
    if out_dir is not None:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            sys.stderr.write(f"docgen build: cannot create output directory {out_dir}: {exc}\n")
            return 2
    cache_path = _resolve_cache_path(args)
    if (args.cached or args.cache) and args.strict:
        sys.stdout.write(
            "docgen build: --strict overrides --cached/--cache (a skipped build cannot re-assert "
            "an advisory verdict); rebuilding everything.\n"
        )

    # RULEBOOK L9 — refuse to produce artifacts under a tampered rulebook. `check` gated the
    # rulebook while `build` did not, so a locked-rule edit was caught only if someone happened to
    # run `check` first; `build` wrote output regardless. A gate that guards one entry point and not
    # the one people actually use is not a gate.
    if args.allow_rulebook_drift:
        # **A BYPASS THAT LEAVES NO TRACE IS NOT A BYPASS, IT IS A HOLE** (`OG-170`).
        # This flag skipped the L9 hash gate silently: a build over a tampered locked rule file
        # produced ordinary output, exit 0, and nothing in the artifact, the log or the terminal
        # recorded that the rules had been unverified. The flag's own help already says "never for
        # a source-of-truth artifact", which only works if someone can tell afterwards that it was
        # used. It is announced now, on stderr, naming what was skipped.
        drift = _rulebook_gate_blocks()
        sys.stderr.write(
            "⚠ docgen: --allow-rulebook-drift is set — the RULEBOOK L9 hash gate was NOT run.\n"
        )
        for msg in drift:
            sys.stderr.write(f"⚠   unverified: {msg}\n")
        if not drift:
            sys.stderr.write("⚠   (the rulebook happens to be clean, but it was not checked)\n")
    if not args.allow_rulebook_drift:
        blocks = _rulebook_gate_blocks()
        if blocks:
            for msg in blocks:
                sys.stderr.write(f"[hash_gate] crit: {msg}\n")
            sys.stderr.write(
                "docgen build: REFUSED — the locked rulebook has undeclared drift (RULEBOOK L9). "
                "Re-baseline it, or pass --allow-rulebook-drift to build anyway (never for a "
                "source-of-truth artifact).\n"
            )
            return 1

    if args.watch:
        return _run_watch(
            md_paths,
            formats=formats,
            out_dir=out_dir,
            local_preview=args.local_preview,
            cache_path=cache_path,
            interval=args.watch_interval,
        )

    started = time.perf_counter()
    try:
        pairs = _build_paths(
            md_paths,
            formats=formats,
            out_dir=out_dir,
            local_preview=args.local_preview,
            cache_path=cache_path,
        )
    except generator.BuildBlockedError as exc:
        sys.stderr.write(f"docgen build: blocked: {exc}\n")
        return 2
    elapsed_s = time.perf_counter() - started

    for result, skipped in pairs:
        _emit_build_result(result, skipped=skipped)
    if cache_path is not None or len(pairs) > 1:
        _emit_corpus_summary(pairs, elapsed_s=elapsed_s, cache_path=cache_path)

    blocked = [result for result, _ in pairs if not result.ok]
    if blocked:
        sys.stderr.write(
            f"docgen build: BLOCKED ({len(blocked)} of {len(pairs)} doc(s): "
            f"{', '.join(r.doc_id for r in blocked)}) — see findings above\n"
        )
        return 1

    if args.strict and any(not f.blocking for result, _ in pairs for f in result.gate.findings):
        sys.stderr.write("docgen build: --strict set and advisory findings exist\n")
        return 1

    return 0


def _run_watch(
    md_paths: list[Path],
    *,
    formats: tuple[str, ...],
    out_dir: Path | None,
    local_preview: bool,
    cache_path: Path | None,
    interval: float,
) -> int:
    """Poll-based ``--watch`` rebuild loop: rebuild on each tick, skipping unchanged docs via cache.

    The cache makes an unchanged tick nearly free (a hash + an existence check, no render). This
    is a simple stdlib polling loop (no OS-specific fs-event dependency) so it degrades honestly
    everywhere. Runs until interrupted (Ctrl-C); returns 0 on clean exit. A blocked build in one
    tick is reported but does not stop the loop — the author fixes the doc and the next tick picks
    it up. When no cache is requested, ``--watch`` still works (every tick is a full rebuild).
    """
    # cache_path is AUTHORITATIVE — resolved once, by _resolve_cache_path, in _cmd_build. This
    # used to re-derive a default cache whenever cache_path was None and -o was set, which meant
    # `--watch --strict` silently rebuilt the cache the strict guard had just refused: every tick
    # after the first skipped the gate entirely. A second resolver is a second answer.
    effective_cache = cache_path
    watched = ", ".join(str(p) for p in md_paths)
    sys.stdout.write(
        f"docgen build --watch: watching {watched} (every {interval:g}s; Ctrl-C to stop)\n"
    )
    sys.stdout.flush()
    try:
        while True:
            try:
                # Re-check the locked rule set EVERY tick. The gate ran once, before the loop, so
                # tampering with a locked rule mid-watch was never re-detected and the watch kept
                # building against rules the gate would now refuse. A long-lived process that
                # checks a security invariant only at startup does not have that invariant.
                try:
                    from tools.docgen import validate_doc_system as _vds

                    _gate = _vds.check(rules_dir=engine_config.doc_system_dir())
                    if _gate.blocked:
                        for _f in _gate.findings:
                            if _f.blocking:
                                sys.stderr.write(f"[hash_gate] crit: {_f.message}\n")
                        sys.stderr.write(
                            "docgen watch: REFUSED — the locked rulebook drifted while watching.\n"
                        )
                        return 1
                except ImportError as _exc:  # pragma: no cover - engine always ships this
                    sys.stderr.write(f"[hash_gate] crit: validate_doc_system unimportable: {_exc}\n")
                    return 1
                pairs = _build_paths(
                    md_paths,
                    formats=formats,
                    out_dir=out_dir,
                    local_preview=local_preview,
                    cache_path=effective_cache,
                )
                for result, skipped in pairs:
                    _emit_build_result(result, skipped=skipped)
                    if not result.ok:
                        sys.stderr.write(
                            f"docgen build --watch: BLOCKED (doc_id={result.doc_id})\n"
                        )
            except generator.BuildBlockedError as exc:
                sys.stderr.write(f"docgen build --watch: blocked: {exc}\n")
            sys.stdout.flush()
            sys.stderr.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        sys.stdout.write("\ndocgen build --watch: stopped\n")
        return 0


def _cmd_render(args: argparse.Namespace) -> int:
    # Containment, matching `build`. `render` and `index` used to write ANYWHERE at exit 0 while
    # `build` fail-closed on the identical shape — the same command family disagreeing about
    # whether the repository boundary is real. An entry point that writes into the repo by design
    # must be the strictest about where "the repo" ends (OG-60).
    # ⚠ **ONLY WHEN THERE IS AN OUTPUT PATH** (`OG-141`). `-o` defaults to `None`, and its help text
    # documents that default as "stdout" — but this containment check ran `Path(args.out)`
    # unconditionally, one line before the branch that handles stdout correctly. So the documented
    # DEFAULT mode of a shipped subcommand crashed with a raw `TypeError` on every invocation:
    #
    #     $ python3 -m tools.docgen.cli render tools/docgen/sample_spec.json
    #     TypeError: argument should be a str or an os.PathLike object ... not 'NoneType'
    #
    # Containment asks "may I write here?", and stdout writes nowhere on disk, so the question does
    # not arise. `OG-86` fixed this same subcommand for reading `args.output` when the dest was
    # `out`; the surface was still never executed without `-o`, which is why `OG-134`'s lane found
    # it. A flag's default is part of the surface.
    if args.out:
        try:
            generator._canonicalize_inside_repo(
                Path(args.out).parent if Path(args.out).suffix else Path(args.out)
            )
        except generator.BuildBlockedError as exc:
            sys.stderr.write(f"⛔ docgen: {exc}\n")
            return 2
    spec_path = Path(args.spec)
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
        spec = _visual_spec_from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        sys.stderr.write(f"docgen render: failed to load spec {spec_path}: {exc}\n")
        return 2

    try:
        svg = visual.render(spec, theme=args.theme)
    except visual.CollisionError as exc:
        sys.stderr.write(f"docgen render: collision detected, refusing to emit SVG: {exc}\n")
        return 1

    # Secret/PII export gate (`P8-076`). `render` used to write/print an SVG built from an
    # arbitrary VisualSpec JSON with NO scan at all — reproduced live: a value shaped like a
    # database connection string with embedded credentials (the `dsn_with_credentials` gate
    # pattern: a URI scheme, then a colon-separated user/password pair, then an `@`-prefixed host)
    # planted in a node label came out verbatim in the written SVG at exit 0. Full
    # `export_sanitizer.run_gates()` is the wrong tool here — it requires a
    # `DocHeader` for gates (tier classification, manifest drift, variant non-overlap) that
    # presuppose a governed Markdown document and do not apply to a standalone chart spec. This
    # runs only the two gates that take plain text and answer exactly the question this finding
    # raised: is a secret or a PII/internal-path/hostname value about to be exported. Applied
    # before EITHER output route (file or stdout) — a leak printed to a terminal is exported just
    # as much as one written to disk.
    leak_check = export_sanitizer.gate_secret_value(svg).merge(
        export_sanitizer.gate_pii_path_internal(svg)
    )
    if leak_check.blocked:
        for finding in leak_check.findings:
            if finding.blocking:
                sys.stderr.write(f"[{finding.gate}] {finding.severity.value}: {finding.message}\n")
        sys.stderr.write(
            "docgen render: refusing to emit SVG — export leak gate blocked (see above)\n"
        )
        return 1

    if args.out:
        Path(args.out).write_text(svg, encoding="utf-8")
        sys.stdout.write(f"wrote {args.out}\n")
    else:
        sys.stdout.write(svg)
        sys.stdout.write("\n")
    return 0


def _cmd_manifest(_args: argparse.Namespace) -> int:
    rows = doc_manifest.read_manifest(_DOC_MANIFEST_PATH)
    if not rows:
        sys.stderr.write(f"docgen manifest: no rows found in {_DOC_MANIFEST_PATH}\n")
        return 1
    for row in rows:
        variants = "/".join(t.value for t in row.variants)
        sys.stdout.write(
            f"{row.id}\t{row.title}\t{row.type}\t{variants}\t{row.surface.value}\t{row.status}\n"
        )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    """Best-effort structural check: header validity + manifest drift.

    Honest degradation: the full VERSION.json rule-hash-gate is owned by
    ``validate_doc_system.py`` (a separate module in this plan, not yet present at the time
    this CLI was authored). If that module exists, delegate to it; otherwise, run the
    checks this module CAN perform and say plainly that the hash-gate was skipped.
    """
    md_path = Path(args.input)
    text = md_path.read_text(encoding="utf-8")
    header = parse_header(text)
    findings = validate_header(header)

    from tools.docgen.classification import (
        check_manifest_drift,
        check_taxonomy_prefix,
        load_taxonomy_prefixes,
    )

    # RULEBOOK L2/L5 — the id-prefix must be a known TAXONOMY.md doc type. Fail-closed: an absent
    # or unparseable taxonomy yields an empty prefix set, which blocks rather than waves through.
    findings.extend(check_taxonomy_prefix(header, load_taxonomy_prefixes(_TAXONOMY_PATH)))

    manifest_rows = doc_manifest.read_manifest(_DOC_MANIFEST_PATH)
    if manifest_rows:
        findings.extend(check_manifest_drift(header, manifest_rows))

    for finding in findings:
        stream = sys.stderr if finding.blocking else sys.stdout
        stream.write(f"[{finding.gate}] {finding.severity.value}: {finding.message}\n")

    try:
        from tools.docgen import validate_doc_system

        # Reuse this module's own already-resolved paths (single source: engine_config) instead
        # of re-deriving them inline — the two used to be independently hardcoded copies of the
        # same literal, a duplication risk that could silently drift (see CONFIGURATION.md).
        hash_result = validate_doc_system.check(
            rules_dir=_DOC_SYSTEM_DIR,
            version_json_path=_VERSION_JSON_PATH,
        )
        # Actively consult the L10/L11 matrices, exactly as the standalone gate CLI does, so the
        # two entry points cannot disagree about what governance said. Additive and fail-open:
        # every appended finding is non-blocking, so this never changes the exit code.
        hash_result = validate_doc_system.consult_governance(hash_result)
        for finding in hash_result.findings:
            stream = sys.stderr if finding.blocking else sys.stdout
            stream.write(f"[{finding.gate}] {finding.severity.value}: {finding.message}\n")
        if not hash_result.ok:
            return 1
    except ImportError as exc:
        # FAIL CLOSED. This used to print a note and fall through to a 0 exit, so a check with the
        # hash-gate silently absent was indistinguishable from a check that passed one. A gate that
        # cannot run has not passed — an unavailable gate is a governance defect, not a free pass.
        sys.stderr.write(
            f"[hash_gate] crit: validate_doc_system is unimportable ({exc}) — the rulebook "
            "hash-gate could not run. Failing closed: this is NOT a gate pass.\n"
        )
        return 1

    if any(f.blocking for f in findings):
        return 1
    # Say so explicitly. A silent success is indistinguishable from a check that ran nothing —
    # the exact ambiguity this engine's gates exist to remove.
    sys.stdout.write(
        f"docgen check: PASSED — header + taxonomy-prefix + manifest-drift + rulebook hash-gate "
        f"({md_path.name})\n"
    )
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    # Containment, matching `build`. `render` and `index` used to write ANYWHERE at exit 0 while
    # `build` fail-closed on the identical shape — the same command family disagreeing about
    # whether the repository boundary is real. An entry point that writes into the repo by design
    # must be the strictest about where "the repo" ends (OG-60).
    try:
        generator._canonicalize_inside_repo(Path(args.out).parent if Path(args.out).suffix else Path(args.out))
    except generator.BuildBlockedError as exc:
        sys.stderr.write(f"⛔ docgen: {exc}\n")
        return 2
    from tools.docgen import build_index

    manifest_rows = doc_manifest.read_manifest(_DOC_MANIFEST_PATH)
    if not manifest_rows:
        sys.stderr.write(f"docgen index: no DOC_MANIFEST.md rows found at {_DOC_MANIFEST_PATH}\n")
        return 1

    written = build_index.build_index(Path(args.build_dir), manifest_rows, Path(args.out))
    docs = build_index.scan_public_doc_jsons(Path(args.build_dir))
    sys.stdout.write(f"wrote index: {written} ({len(docs)} public document(s) indexed)\n")
    return 0


def _archive_target(raw: str) -> tuple[Path, str]:
    """Resolve a user-supplied path to (host root, repo-relative POSIX path).

    Refuses anything outside the host root before it is joined onto the archive, for the same
    reason ``index`` and ``build`` refuse it: an entry point that writes into the repository by
    design must be the strictest about where the repository ends (`OG-60`).
    """
    root = engine_config.host_root().resolve()
    candidate = Path(raw).resolve()
    try:
        rel = candidate.relative_to(root)
    except ValueError as exc:
        raise generator.BuildBlockedError(
            f"{raw} resolves outside the host project root ({root}); refusing to archive it"
        ) from exc
    return root, rel.as_posix()


def _cmd_archive_cut(args: argparse.Namespace) -> int:
    """Cut the next version of a document into the archive."""
    try:
        root, rel = _archive_target(args.input)
    except generator.BuildBlockedError as exc:
        sys.stderr.write(f"⛔ docgen: {exc}\n")
        return 2

    source = (root / rel).read_text(encoding="utf-8", errors="replace") if (root / rel).is_file() else ""
    header = parse_header(source) if source else None
    doc_id = identity.archive_id(rel, header)

    try:
        entry = archive.cut(root, rel, header=header, cut_on=args.date)
    except archive.ArchiveError as exc:
        sys.stderr.write(f"⛔ docgen archive: {exc}\n")
        return 2

    superseded = [v for v in archive.versions_on_disk(root, doc_id) if v < entry.version]
    note = (
        f"; v{', v'.join(str(v) for v in superseded)} now superseded" if superseded else ""
    )
    sys.stdout.write(
        f"cut {doc_id} v{entry.version} from {rel} "
        f"(sha256 {entry.sha256[:12]}…, commit {entry.commit}){note}\n"
    )
    return 0


def _cmd_archive_list(args: argparse.Namespace) -> int:
    """Report every archived document: its versions, which are superseded, and whether it is frozen.

    ``frozen`` is measured against the snapshot's bytes on every run, never read from a field.
    """
    root = engine_config.host_root().resolve()
    wanted = args.doc_id
    ids = [i for i in archive.archived_ids(root) if wanted is None or i == wanted]
    if not ids:
        sys.stdout.write(
            f"no archived documents under {engine_config.archive_dir_relative()}/"
            + (f" matching {wanted!r}" if wanted else "")
            + "\n"
        )
        return 0 if wanted is None else 1

    defects = 0
    for doc_id in ids:
        entries = archive.read_history(root, doc_id)
        versions = archive.versions_on_disk(root, doc_id)
        latest = versions[-1] if versions else 0
        source_rel = archive.live_path(root, doc_id)
        state = archive.freeze_state(root, source_rel, doc_id) if source_rel else None
        marks = " ".join(
            f"v{v}{'' if v == latest else ' (superseded)'}" for v in versions
        ) or "no versions on disk"
        verdict = (
            ("frozen" if state.frozen else f"NOT frozen — {state.reason}")
            if state is not None
            else "live document not found"
        )
        sys.stdout.write(f"{doc_id}: {marks} · {verdict}\n")
        if source_rel:
            sys.stdout.write(f"    live: {source_rel}\n")
        for entry in entries:
            sys.stdout.write(
                f"    v{entry.version}  {entry.cut_on}  {entry.commit}  "
                f"{entry.sha256[:12]}…  {entry.cut_by}\n"
            )
        for defect in archive.audit_id(root, doc_id):
            defects += 1
            sys.stdout.write(f"    ⛔ {defect.message}  {defect.evidence}\n")
    return 1 if defects else 0


def _cmd_content_index(args: argparse.Namespace) -> int:
    """Emit the machine-readable CONTENT_INDEX.json over the authored PUBLIC docs.

    Source of truth = the authored ``.md`` sources' headers, cross-referenced against
    DOC_MANIFEST.md. Leak-safe (RULEBOOK L14): only ``classification: public`` docs are listed;
    non-public authored docs are counted in aggregate but never named.
    """
    from tools.docgen import build_index

    manifest_rows = doc_manifest.read_manifest(_DOC_MANIFEST_PATH)
    if not manifest_rows:
        sys.stderr.write(
            f"docgen content-index: no DOC_MANIFEST.md rows found at {_DOC_MANIFEST_PATH}\n"
        )
        return 1

    docs_root = Path(args.docs_root) if args.docs_root else _AUTHORED_DOCS_ROOT
    out_path = Path(args.out) if args.out else _CONTENT_INDEX_PATH

    # Containment, matching `build`/`render`/`index` (`P8-074`). This subcommand writes an
    # arbitrary `--out` path exactly like `index` does, but never carried the same guard — measured
    # live: `content-index --docs-root docs -o /tmp/...` wrote outside the repo at exit 0, while
    # `index` refused the identical shape with exit 2. One write-capable command family disagreeing
    # about whether the repository boundary is real is the exact defect `OG-60` closed for
    # `render`/`index`; it was never extended to this sibling subcommand.
    try:
        generator._canonicalize_inside_repo(out_path.parent if out_path.suffix else out_path)
    except generator.BuildBlockedError as exc:
        sys.stderr.write(f"⛔ docgen: {exc}\n")
        return 2

    if not docs_root.is_dir():
        sys.stderr.write(f"docgen content-index: docs root not found: {docs_root}\n")
        return 2

    written = build_index.write_content_index(
        docs_root,
        manifest_rows,
        out_path,
        repo_root=_REPO_ROOT,
        manifest_path=_DOC_MANIFEST_PATH,
    )
    entries, non_public = build_index.scan_authored_docs(
        docs_root, manifest_rows, repo_root=_REPO_ROOT
    )
    sys.stdout.write(
        f"wrote content-index: {written} "
        f"({len(entries)} public doc(s) listed, {non_public} non-public excluded)\n"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docgen", description=" doc-system engine CLI")
    parser.add_argument("--strict", action="store_true", help="treat advisory findings as failures")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="build a Markdown document into HTML/JSON/PDF")
    p_build.add_argument(
        "input",
        nargs="+",
        help=(
            "path(s) to the source .md file(s). Several paths build as one corpus through a "
            "single shared cache (one cache load, one engine fingerprint, one save)."
        ),
    )
    p_build.add_argument("-o", "--out-dir", dest="out_dir", default=None, help="output directory")
    p_build.add_argument(
        "--formats", default="html", help="comma-separated formats: html,json,blueprint,pdf (default: html); blueprint = the AI-only <stem>.blueprint.json twin of the document"
    )
    p_build.add_argument(
        "--local-preview",
        dest="local_preview",
        action="store_true",
        help=(
            "allow a CONFIDENTIAL/SECRET document to render for local review (Gate 1 "
            "relaxed to advisory); out-dir must resolve under docs/confidential/ or the "
            "build is blocked. Never affects a public document. Never makes a doc export-eligible."
        ),
    )
    p_build.add_argument(
        "--cache",
        default=None,
        help=(
            "path to an incremental build-cache JSON. When set, an unchanged document (same "
            "source, sibling spec, formats, flag, and engine) whose outputs still exist is "
            "skipped. Fail-open: a corrupt/absent cache just does a full build."
        ),
    )
    p_build.add_argument(
        "--cached",
        action="store_true",
        help=(
            "build through the conventional incremental cache: <out-dir>/.docgen_cache.json, or "
            ".docgen/.docgen_cache.json when no -o is given. An unchanged document whose outputs "
            "still exist is skipped. Use --cache PATH to name the file explicitly. Ignored under "
            "--strict, which always re-runs the gate."
        ),
    )
    p_build.add_argument(
        "--watch",
        action="store_true",
        help=(
            "rebuild on a fixed interval until interrupted (poll-based, stdlib-only). Combine "
            "with --cached or --cache so unchanged ticks are near-free."
        ),
    )
    p_build.add_argument(
        "--watch-interval",
        dest="watch_interval",
        type=float,
        default=1.0,
        help="seconds between --watch rebuild ticks (default: 1.0)",
    )
    p_build.add_argument(
        "--allow-rulebook-drift",
        action="store_true",
        help="Build even when the RULEBOOK L9 hash-gate is blocking. Never use for a "
        "source-of-truth artifact — it disables the locked-rule guard for this run.",
    )
    p_build.set_defaults(func=_cmd_build)

    p_render = sub.add_parser("render", help="render a VisualSpec JSON file to SVG")
    p_render.add_argument("spec", help="path to a VisualSpec .json file")
    p_render.add_argument("-o", "--out", default=None, help="output .svg path (default: stdout)")
    p_render.add_argument("--theme", default="dark", choices=("dark", "light"))
    p_render.set_defaults(func=_cmd_render)

    p_manifest = sub.add_parser("manifest", help="print DOC_MANIFEST.md rows")
    p_manifest.set_defaults(func=_cmd_manifest)

    p_check = sub.add_parser("check", help="run the doc-system gate against a document")
    p_check.add_argument("input", help="path to the source .md file")
    p_check.set_defaults(func=_cmd_check)

    p_index = sub.add_parser(
        "index", help="scan built docgen JSON sidecars and emit a browsable PUBLIC docs index"
    )
    p_index.add_argument(
        "build_dir", help="directory to scan (recursively) for docgen JSON sidecars"
    )
    p_index.add_argument("-o", "--out", required=True, help="path to write the index HTML")
    p_index.set_defaults(func=_cmd_index)

    p_archive = sub.add_parser(
        "archive",
        help=(
            "document version archive: cut a new version, or report what is archived, "
            "superseded and frozen"
        ),
    )
    archive_sub = p_archive.add_subparsers(dest="archive_command", required=True)

    p_cut = archive_sub.add_parser(
        "cut",
        help=(
            "snapshot a document as its next version under <archiveDir>/<id>/vN/, record the cut "
            "in HISTORY.md, and bump version/revision in its front matter when it has any"
        ),
    )
    p_cut.add_argument("input", help="path to the live .md document")
    p_cut.add_argument(
        "--date",
        required=True,
        help=(
            "the cut date, YYYY-MM-DD. Required rather than read from the clock so a cut is "
            "reproducible: a probe supplies a fixed date and gets a deterministic record."
        ),
    )
    p_cut.set_defaults(func=_cmd_archive_cut)

    p_list = archive_sub.add_parser(
        "list",
        help="report archived documents: versions, which are superseded, and whether each is frozen",
    )
    p_list.add_argument(
        "doc_id", nargs="?", default=None, help="limit the report to one archive id"
    )
    p_list.set_defaults(func=_cmd_archive_list)

    p_ci = sub.add_parser(
        "content-index",
        help=(
            "emit a machine-readable CONTENT_INDEX.json over the authored PUBLIC docs "
            "(for a graphify pass / the app docs page — no Markdown re-parsing)"
        ),
    )
    p_ci.add_argument(
        "--docs-root",
        dest="docs_root",
        default=None,
        help=(
            "root to scan (recursively) for authored .md sources "
            f"(default: {_AUTHORED_DOCS_ROOT})"
        ),
    )
    p_ci.add_argument(
        "-o",
        "--out",
        default=None,
        help=f"path to write CONTENT_INDEX.json (default: {_CONTENT_INDEX_PATH})",
    )
    p_ci.set_defaults(func=_cmd_content_index)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except tokens.TokensUnavailable as exc:
        # Fail-closed is correct — a document rendered without its design tokens is not the
        # document. A raw traceback naming a JSON column is not: every entry point imports this
        # module, so one corrupt file killed `docgen manifest` and everything else with a stack
        # trace instead of a diagnosis.
        sys.stderr.write(f"⛔ docgen: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
