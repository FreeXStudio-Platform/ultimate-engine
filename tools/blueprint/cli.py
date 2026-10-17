"""`python3 -m tools.blueprint build|check|verify|layout|index|query|search`.

``build``   derive the model and write ``blueprint/``
``check``   fail if the committed map is not what a fresh build produces
``verify``  ``check`` PLUS every disagreement between the authored spec and the tree
``layout``  ELK auto-layout for the package graph (`BUILD_PLAN.md` D5)
``completeness`` where did we stop, per node and per document — and the depth ratchet (row 6)
``index``   build the gitignored SQLite + FTS5 index (D1)
``query``   run one of the canonical joins against that index
``search``  full-text search across the corpus

WHY ``check`` AND ``verify`` BOTH EXIST
=======================================
``check`` answers one question — *is the committed map stale?* — and it is what the retained
counter-examples call. (**Not the push hook directly**: nothing under `tools/hooks/` mentions
`blueprint` at all. The hook reaches it transitively, by running `tools.health`, whose SUITE-05
runs the suite that calls it. The first version of this sentence claimed a direct caller that does
not exist.) ``verify`` is the phase's named command and is a strict
superset: it asks that question **and** whether the authored spec still describes the tree.

They are not merged, and the reason is a contract rather than taste: ``check`` must keep meaning
exactly what its existing callers already depend on it meaning. Widening a command in place is how
a caller silently starts asserting something it never agreed to — the same shape as `L-16`, where a
skip-if-unchanged optimisation inherited the contract of everything it skipped without saying so.
``verify`` calls ``check``'s own comparison rather than reimplementing it, so the two can never
disagree about staleness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.blueprint.model import build_model
from tools.blueprint.render import blueprint_files

OUT_DIR = "blueprint"


def _root() -> Path:
    """The HOST project being mapped — never this engine's own install directory.

    `Path(__file__).parents[2]` is the ENGINE's root, which is the wrong question: this engine is
    vendored INTO other projects, and a map of the engine handed to an agent working on the project
    that consumes it is useless — silently so, because it still looks like a plausible map.
    `engine_config.host_root()` is the one answer to "which project am I governing", already
    honoured by the CLI, the generator, the doc-system validator and the health run.
    """
    from tools.docgen import engine_config
    return engine_config.host_root()


def _out_dir(root: Path) -> Path:
    from tools.docgen import engine_config

    configured = engine_config.blueprint_dir()
    local = root / OUT_DIR
    return local if configured != local and local.parent.is_dir() else configured


def _staleness(root: Path, files: dict[str, str]) -> list[str]:
    """The ONE comparison of committed vs. fresh. ``check`` and ``verify`` both call it."""
    out = _out_dir(root)
    drift: list[str] = []
    for name, contents in files.items():
        path = out / name
        if not path.is_file():
            drift.append(f"{name}: MISSING")
        elif path.read_text(encoding="utf-8") != contents:
            drift.append(f"{name}: stale (does not match a fresh build)")
    return drift


def _cmd_build(root: Path, files: dict[str, str]) -> int:
    out = _out_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    for name, contents in files.items():
        (out / name).write_text(contents, encoding="utf-8")
    print(f"blueprint: wrote {', '.join(sorted(files))} → {out}")
    return 0


def _cmd_check(root: Path, files: dict[str, str]) -> int:
    drift = _staleness(root, files)
    if drift:
        print("blueprint: STALE — " + "; ".join(drift), file=sys.stderr)
        print("  run `python3 -m tools.blueprint build` and commit the result", file=sys.stderr)
        return 1
    print(f"blueprint: current ({len(files)} file(s) match a fresh build)")
    return 0


def _cmd_verify(root: Path, model: dict[str, Any], files: dict[str, str]) -> int:
    """Every way the map can be wrong, in one command, with the count it checked."""
    from tools.blueprint import spec as spec_mod

    problems: list[str] = []
    try:
        spec = spec_mod.load_spec(root)
    except spec_mod.SpecError as exc:
        print(f"blueprint verify: FAILED\n  {exc}", file=sys.stderr)
        return 1

    module_ids = [n["id"] for n in model["graph"]["nodes"]]
    assignment = spec_mod.assign(spec, module_ids)
    for drift in spec_mod.spec_drift(root, spec, assignment):
        problems.append(drift.render())

    problems.extend(f"{'stale-map':<22} {d}" for d in _staleness(root, files))

    checked = (
        f"{len(spec.containers)} container(s), {len(module_ids)} module(s), "
        f"{len(model['documents'])} document(s), {len(files)} derived file(s)"
    )
    if problems:
        print(f"blueprint verify: FAILED — {len(problems)} problem(s) over {checked}\n", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(f"blueprint verify: clean — {checked}")
    return 0


def _cmd_layout(root: Path, model: dict[str, Any], *, check_only: bool) -> int:
    """ELK auto-layout. The coordinates are the deliverable; the SVG is written only when clean.

    Three outcomes, and keeping them distinct is the whole design:

    * **SKIP** — ``node`` or ``elkjs`` absent. An environment fact is not a finding about the
      artifact (`LESSONS.md` L-25): exit 0, say SKIP out loud, never let it read as a pass.
    * **FAIL** — the bridge failed, or docgen's collision gate found a **node-placement** problem.
      That is what ELK controls and what D5 promised, so it blocks.
    * **PASS with the renderer's limit named** — placement is clean but docgen's straight-line edges
      cross nodes. The coordinates are written; the SVG is not, because writing a diagram the gate
      refused is precisely the defect Phase 4 fixed (``docgen build`` reported BLOCKED and wrote the
      artifact anyway).
    """
    from tools.blueprint import layout as layout_mod

    outcome = layout_mod.compute(model)
    if outcome.skipped:
        print(f"blueprint layout: SKIP: {outcome.reason}")
        return 0
    if not outcome.ok or outcome.layout is None:
        print(f"blueprint layout: FAILED — {outcome.reason}", file=sys.stderr)
        return 1

    report = layout_mod.collision_report(outcome.layout)
    placed = len(outcome.layout["nodes"])
    if report["node_placement"]:
        print(
            f"blueprint layout: FAILED — ELK placed {placed} node(s) but docgen refuses "
            f"{len(report['node_placement'])} of them on placement grounds:",
            file=sys.stderr,
        )
        for message in report["node_placement"][:10]:
            print(f"  {message}", file=sys.stderr)
        return 1

    artifacts: dict[str, str] = {
        "system.layout.json": json.dumps(
            {**outcome.layout, "docgen_collisions": {
                "node_placement": 0, "edge_routing": report["edge_routing"]}},
            indent=2, sort_keys=True,
        ) + "\n"
    }
    if report["clean"]:
        artifacts["system.layout.svg"] = layout_mod.render_svg(outcome.layout)

    out = _out_dir(root)
    if check_only:
        drift = [
            f"{name}: {'MISSING' if not (out / name).is_file() else 'stale'}"
            for name, body in artifacts.items()
            if not (out / name).is_file() or (out / name).read_text(encoding="utf-8") != body
        ]
        # An artifact this run would NOT write must not be sitting there from a run that would
        # have. The SVG only enters `artifacts` when the layout is clean, so while it is unclean the
        # comparison above never looked at `system.layout.svg` at all — a verifier planted garbage
        # under that name and `--check` reported "current", exit 0, garbage untouched. No live drift
        # today because none is committed; the risk is a previously-clean layout going dirty and
        # orphaning an SVG that no gate would ever flag again.
        drift += [
            f"{name}: ORPHANED (this layout would not produce it — delete it)"
            for name in ("system.layout.svg",)
            if name not in artifacts and (out / name).is_file()
        ]
        if drift:
            print("blueprint layout: STALE — " + "; ".join(drift), file=sys.stderr)
            print("  run `python3 -m tools.blueprint layout` and commit the result", file=sys.stderr)
            return 1
        print(f"blueprint layout: current ({placed} node(s) placed by ELK, 0 placement finding(s))")
        return 0

    out.mkdir(parents=True, exist_ok=True)
    for name, body in artifacts.items():
        (out / name).write_text(body, encoding="utf-8")
    print(
        f"blueprint layout: wrote {', '.join(sorted(artifacts))} → {out} "
        f"({placed} node(s), {outcome.layout['width']}×{outcome.layout['height']}, "
        f"0 placement finding(s))"
    )
    if not report["clean"]:
        print(
            f"  no SVG written: {report['edge_routing']} edge(s) would cross a non-endpoint node. "
            f"That is docgen's renderer, not the layout — it draws every edge as a straight line "
            f"between two centres and `Edge` carries no waypoints, so a graph this dense cannot be "
            f"drawn cleanly at any placement. The coordinates above are valid and committed; "
            f"`blueprint/system.mmd` is the rendered graph (mermaid routes its own edges)."
        )
    return 0


def _cmd_completeness(root: Path, model: dict[str, Any], *, check_only: bool) -> int:
    """*Where did we stop* — and, with ``--check``, the ratchet that stops it slipping back.

    The report and the gate are one command on purpose. A completeness report nobody is obliged to
    act on is a dashboard, and `BUILD_PLAN.md` row 6 asks for the ladder ENFORCED — so the same
    derivation that prints the three states also decides an exit code.
    """
    report = model.get("completeness", {})
    summary = report.get("summary", {})
    total = sum(summary.values())
    findings = list(report.get("floor_findings", []))

    # A REPORT OVER NOTHING IS NOT A CLEAN REPORT. With no `system.spec.json` at all this printed
    # "0 node(s) ... ratchet level across 0 container(s)" and exited 0 — the same confident-empty
    # shape as the 0-node dependency graph this whole layer was built to replace, and `build_model`
    # had recorded the cause the whole time without anyone reading it.
    spec_error = model.get("system", {}).get("spec_error", "")
    if spec_error:
        findings.append(f"the system spec could not be read, so nothing below is a measurement: {spec_error}")
    if not total:
        findings.append("the model contains no nodes — an empty report is not a clean report")
    memory = str(report.get("ratchet_memory", ""))
    if memory.startswith("UNAVAILABLE"):
        # A SKIP, said out loud. The ratchet still checks what it can; it just cannot see history.
        print(f"completeness: ratchet memory {memory} — loosening cannot be detected this run")

    print(
        f"completeness: {total} node(s) — "
        + " · ".join(f"{state} {summary.get(state, 0)}" for state in report.get("states", []))
    )
    documents = report.get("documents", [])
    if documents:
        done = sum(d["complete"] for d in documents)
        of = sum(d["of"] for d in documents)
        print(
            f"  document lifecycle: {done}/{of} step(s) complete across "
            f"{len(documents)} governed document(s)"
        )
    if not check_only:
        for doc in documents:
            if doc["missing"]:
                print(f"    {doc['path']}: missing {', '.join(doc['missing'])}")
        for node, rec in sorted(report.get("nodes", {}).items()):
            if rec["state"] == "sketched":
                print(f"    {node}: {rec['why']}")

    if findings:
        print(f"completeness: FAILED — {len(findings)} ratchet finding(s)", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print(f"  ratchet level across {len(model.get('containers', []))} container(s)")
    return 0


def _cmd_index(root: Path, model: dict[str, Any]) -> int:
    from tools.blueprint import index_db

    try:
        counts = index_db.build(root, model)
    except index_db.EmptyIndexError as exc:
        print(f"blueprint index: REFUSED — {exc}", file=sys.stderr)
        return 1
    path = index_db.index_path(root)
    print(f"blueprint index: wrote {path} (FTS5 available)")
    print("  " + " · ".join(f"{table} {n}" for table, n in sorted(counts.items())))
    print("  derived, gitignored, rebuildable — never authoritative (BUILD_PLAN.md D1)")
    return 0


def _cmd_query(root: Path, question: str) -> int:
    from tools.blueprint import index_db

    if not question:
        print("Canonical questions:")
        for name, (why, _) in sorted(index_db.QUERIES.items()):
            print(f"  {name!r}\n      {why}")
        return 0
    try:
        sql, rows, cols = index_db.query(root, question)
    except KeyError:
        print(f"blueprint query: unknown question {question!r}", file=sys.stderr)
        print("  run `python3 -m tools.blueprint query` with no argument to list them", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"blueprint query: no index at {exc} — run `python3 -m tools.blueprint index`", file=sys.stderr)
        return 1
    print(f"{question}  ({len(rows)} row(s))")
    print(f"  SQL: {sql}")
    if rows:
        print("  " + " | ".join(cols))
        for row in rows:
            print("  " + " | ".join(str(c) for c in row))
    return 0


def _cmd_search(root: Path, text: str) -> int:
    from tools.blueprint import index_db

    try:
        hits = index_db.search(root, text)
    except FileNotFoundError as exc:
        print(f"blueprint search: no index at {exc} — run `python3 -m tools.blueprint index`", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — FTS5 syntax errors are the user's, reported as theirs
        print(f"blueprint search: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"{len(hits)} document(s) match {text!r}")
    for path, snippet in hits:
        print(f"  {path}\n      {snippet}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.blueprint", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="derive the model and write blueprint/")
    sub.add_parser("check", help="fail if the committed blueprint is not what a fresh build produces")
    sub.add_parser("verify", help="check PLUS every disagreement between the system spec and the tree")
    p_layout = sub.add_parser("layout", help="ELK auto-layout for the package graph (D5)")
    p_layout.add_argument(
        "--check", action="store_true",
        help="fail if the committed layout is stale; SKIP if node/elkjs are absent",
    )
    p_comp = sub.add_parser(
        "completeness", help="where did we stop — per node and per document, and the depth ratchet"
    )
    p_comp.add_argument(
        "--check", action="store_true",
        help="report only the summary and the ratchet verdict, not the per-node detail",
    )
    sub.add_parser("index", help="build the gitignored SQLite + FTS5 derived index (D1)")
    p_query = sub.add_parser("query", help="run a canonical join against the derived index")
    p_query.add_argument("question", nargs="?", default="", help="the question (omit to list them)")
    p_search = sub.add_parser("search", help="full-text search across the corpus")
    p_search.add_argument("text", help="FTS5 match expression")
    args = parser.parse_args(argv)

    root = _root()
    # `query`/`search` read the index and must not pay to rebuild the whole model first.
    if args.cmd == "query":
        return _cmd_query(root, args.question)
    if args.cmd == "search":
        return _cmd_search(root, args.text)

    model = build_model(root)
    files = blueprint_files(model)
    if args.cmd == "build":
        return _cmd_build(root, files)
    if args.cmd == "check":
        return _cmd_check(root, files)
    if args.cmd == "verify":
        return _cmd_verify(root, model, files)
    if args.cmd == "layout":
        return _cmd_layout(root, model, check_only=args.check)
    if args.cmd == "completeness":
        return _cmd_completeness(root, model, check_only=args.check)
    if args.cmd == "index":
        return _cmd_index(root, model)
    parser.error(f"unknown command {args.cmd}")
    return 2
