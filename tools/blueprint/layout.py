"""Auto-layout for the system graph — the Python half of the ELK bridge (`BUILD_PLAN.md` D5).

WHAT THIS CLOSES
================
docgen's oldest documented gap: every node diagram needed hand-supplied ``x``/``y``, and the
hand-layout iterations were the largest authoring cost measured in the gallery build. ELK supplies
the coordinates; docgen's existing ``system_map`` / ``dependency_graph`` renderers consume them
unchanged. **No new renderer, no new dependency** — ``elkjs`` is already in the tree under the
mermaid engine.

THE ABSENCE CONTRACT, WHICH IS THE PART THAT USUALLY GOES WRONG
===============================================================
``node`` or ``elkjs`` missing is an **environment fact, not a finding about the artifact**
(`LESSONS.md` L-25). It is reported as a SKIP naming its cause, never as a failure — a gate that
fails closed on the innocent teaches people to bypass it, and on this project that took the whole
moat down once already. It is equally never a silent pass: :func:`compute` returns a
:class:`LayoutOutcome` whose ``skipped`` flag its caller must handle, so "we could not check" can
never be mistaken for "we checked and it was fine".

**The asymmetry, stated because it is surprising.** An ABSENT ``node`` is a SKIP at exit 0; a
``node`` that is PRESENT BUT BROKEN — a stub, non-JSON output, a non-zero exit — is a FAILURE at
exit 1. That is deliberate: absence is an environment fact about the machine, while a bridge that
answers wrongly is a fact about the artifact. So exit 1 covers bridge failure and placement
findings as well as staleness; it is not drift alone.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BRIDGE = Path(__file__).resolve().parent / "elk_layout.mjs"
_ELK = (
    Path(__file__).resolve().parents[1]
    / "mermaid-engine" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js"
)


@dataclass(frozen=True)
class LayoutOutcome:
    """Either coordinates, or the named reason there are none."""

    ok: bool
    skipped: bool
    reason: str
    layout: dict[str, Any] | None = None


def available() -> tuple[bool, str]:
    """``(usable, reason)`` — checked before running, so the reason is specific rather than 'failed'."""
    from tools.docgen import engine_config

    node_bin = engine_config.tool_path("node")
    if not node_bin:
        return False, "node not found (checked ENGINE_NODE_BIN, engine.config.json, PATH)"
    if not _ELK.is_file():
        return False, f"elkjs not installed at {_ELK} (run `npm install` in tools/mermaid-engine)"
    if not _BRIDGE.is_file():
        return False, f"layout bridge missing at {_BRIDGE}"
    return True, ""


def graph_input(model: dict[str, Any]) -> dict[str, Any]:
    """The package-level graph, as ELK input — **sorted**, because the output is committed.

    Package level for the same reason the mermaid render is: 97 modules and 203 edges lay out as a
    hairball that costs tokens and teaches nothing. Sorting is not cosmetic — an unsorted input
    would let dictionary ordering leak into the coordinates and make a re-derivation differ from
    the committed copy for no real reason.
    """
    packages: dict[str, int] = {}
    for node in model["graph"]["nodes"]:
        packages[node["package"]] = packages.get(node["package"], 0) + 1

    edges: set[tuple[str, str]] = set()
    for edge in model["graph"]["edges"]:
        src, _, dst = edge.partition(" -> ")
        a, b = src.rsplit(".", 1)[0], dst.rsplit(".", 1)[0]
        if a != b and a in packages and b in packages:
            edges.add((a, b))

    return {
        "nodes": [
            # Width tracks the label so ELK reserves room for the text docgen will draw, rather
            # than laying out boxes that the renderer then overflows.
            {"id": name, "width": max(140, 9 * len(name) + 40), "height": 48}
            for name in sorted(packages)
        ],
        "edges": [{"source": a, "target": b} for a, b in sorted(edges)],
    }


def compute(model: dict[str, Any]) -> LayoutOutcome:
    """Run ELK over the package graph. Never raises; every failure is a named outcome."""
    usable, reason = available()
    if not usable:
        return LayoutOutcome(ok=False, skipped=True, reason=reason)

    from tools.docgen import engine_config

    payload = json.dumps(graph_input(model), sort_keys=True)
    try:
        proc = subprocess.run(
            [engine_config.tool_path("node") or "node", str(_BRIDGE)],
            input=payload, capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return LayoutOutcome(ok=False, skipped=True, reason=f"node failed to run: {exc}")

    try:
        result = json.loads(proc.stdout or "{}")
    except ValueError:
        return LayoutOutcome(
            ok=False, skipped=False,
            reason=f"bridge produced no JSON (exit {proc.returncode}): {(proc.stderr or '')[:300]}",
        )
    if not result.get("ok"):
        return LayoutOutcome(
            ok=False, skipped=False, reason=str(result.get("error", "unknown bridge failure"))
        )
    # VALIDATE WHAT CAME BACK. `compute` promises every failure is a NAMED outcome, and that promise
    # leaked: a bridge answering `{"ok": true}` with missing or malformed `nodes` produced an
    # uncaught KeyError one layer up instead. The .mjs validates its own output; trusting that from
    # here means trusting whatever `ENGINE_NODE_BIN` points at.
    placed = result.get("nodes")
    if not isinstance(placed, list) or not placed:
        return LayoutOutcome(
            ok=False, skipped=False,
            reason="bridge reported ok with no usable `nodes` array — refusing an empty layout",
        )
    for node in placed:
        if not isinstance(node, dict) or not all(
            isinstance(node.get(k), (int, float)) for k in ("x", "y", "width", "height")
        ):
            return LayoutOutcome(
                ok=False, skipped=False,
                reason=f"bridge returned a malformed node record: {node!r}",
            )
    # Carry the input edges into the result: the bridge places nodes, and a dependency graph
    # without its edges is a scatter plot of package names.
    result["edges"] = graph_input(model)["edges"]
    return LayoutOutcome(ok=True, skipped=False, reason="", layout=result)


def collision_report(layout: dict[str, Any]) -> dict[str, Any]:
    """Run docgen's OWN collision checker over the laid-out spec and split the verdict in two.

    **The split is the honest part, and it is not a convenience.** Two different things can be
    wrong with a figure, and exactly one of them is the layout engine's responsibility:

    ``node_placement``
        Overlapping boxes, and gaps under docgen's 1.5x-larger-short-side rule. This is what ELK
        controls and what D5 promised to stop doing by hand. It must be **zero**; ``blueprint
        layout`` fails if it is not.

    ``edge_routing``
        Edges passing through a node that is not their endpoint. This is **not** a placement
        defect: docgen draws every edge as a straight line between two centres and its ``Edge``
        carries no waypoints, so a graph with skip-level edges at this density cannot be drawn
        cleanly at ANY placement — measured across ``layered``, ``force``, ``mrtree`` and
        ``stress``, and at container level as well as package level, the count never reached zero.

    Reporting one number for both would have let a real placement regression hide inside a known
    renderer limitation. Reporting only the total would have made this command fail forever for a
    reason ELK cannot fix.
    """
    from tools.docgen.visual import check_collisions

    spec = _spec(layout)
    findings = check_collisions(spec)
    routing = [f for f in findings if "passes through" in f.message]
    placement = [f for f in findings if "passes through" not in f.message]
    return {
        "node_placement": [f.message for f in placement],
        "edge_routing": len(routing),
        "clean": not findings,
    }


def _spec(layout: dict[str, Any]) -> Any:
    """The laid-out graph as a docgen ``VisualSpec``.

    Coordinates pass through untouched: ELK and ``Node`` both use a **top-left** origin with
    explicit ``w``/``h``, so translating between them would invent a discrepancy — the first
    version of this code added ``width // 2`` to reach a centre origin ``Node`` does not use.
    """
    from tools.docgen.models import Edge, Node, NodeType, VisualSpec

    # Room for the title docgen draws at y=20 and the caption near the bottom; without it the top
    # row of boxes collides with the title and the whole render is refused.
    margin_top, margin_bottom, margin_x = 72.0, 56.0, 40.0
    nodes = [
        Node(
            id=n["id"], type=NodeType.PROCESS, label=n["id"],
            x=float(n["x"]) + margin_x, y=float(n["y"]) + margin_top,
            w=float(n["width"]), h=float(n["height"]),
        )
        for n in layout["nodes"]
    ]
    edges = [Edge(src=e["source"], dst=e["target"]) for e in layout.get("edges", [])]
    return VisualSpec(
        id="blueprint-package-graph",
        title="Package dependency graph — ELK auto-layout",
        caption=(
            f"{len(nodes)} package(s), {len(edges)} edge(s). Coordinates computed by ELK "
            f"({layout.get('algorithm', 'layered')}), rendered by docgen's own dependency-graph "
            f"renderer and held to its own collision gate."
        ),
        nodes=nodes, edges=edges,
        width=float(layout.get("width", 0)) + 2 * margin_x,
        height=float(layout.get("height", 0)) + margin_top + margin_bottom,
    )


def render_svg(layout: dict[str, Any]) -> str:
    """The laid-out graph as SVG, through docgen's OWN renderer — never a second drawing routine.

    D5's claim was never "draw a graph"; it was "supply the coordinates the existing renderers have
    always needed". A renderer here would be a second visual language for one system.

    Raises ``CollisionError`` when the spec does not pass docgen's gate. Callers must not write a
    diagram that raised: Phase 4 fixed exactly that shape — ``docgen build`` reported BLOCKED and
    wrote the artifact anyway.
    """
    from tools.docgen import diagram_graphs

    return diagram_graphs.render_dependency_graph(_spec(layout))
