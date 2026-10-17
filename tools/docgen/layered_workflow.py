"""2.5D layered-workflow renderer (VISUAL_LIBRARY.md §2 — "how work moves across LAYERS,
up/down + left/right"). Draws each layer as a horizontally-sheared "shelf" plane stacked
on a vertical (depth) axis, with connectors moving both within a plane (horizontal) and
between planes (vertical) — the operator's explicit "3D, data going up and down" ask,
built as a bounded 2.5D shear (not a true 3D engine).

A single ``render()`` call emits BOTH variants in one self-contained SVG: the isometric
shear view (default) and a flat, un-skewed fallback of the *same* graph, switched purely
by ``@media (prefers-reduced-motion: reduce), print`` — VISUAL_LIBRARY §2's explicit
requirement ("Provide a flat 2D fallback for reduced-motion / print / small screens").

Reuses the flowchart family's generic geometry/text/escape helpers so collision math and
formatting stay identical across every figure type in the engine.

Stdlib only; mypy --strict clean; deterministic (2dp-rounded floats, stable ordering).
"""

from __future__ import annotations

from collections.abc import Callable

from tools.docgen.models import Finding, LayeredSpec, Severity
from tools.docgen.visual import (
    _CHAR_ADVANCE_FACTOR,
    BBox,
    _escape,
    _fmt,
    _gap,
    _intersects,
    _r,
    _wrap_text,
)

_MAX_LAYERS = 4  # VISUAL_LIBRARY §2: "keep it legible: max ~3-4 stacked planes"
_LAYER_HEIGHT = 96.0
_COL_WIDTH = 140.0
_SHEAR_PER_LAYER = 28.0  # horizontal shift per layer, gives the receding-shelf look
_NODE_W = 110.0
_NODE_H = 44.0
_TOP_MARGIN = 56.0
_LEFT_MARGIN = 96.0
_LABEL_FONT_PX = 12.0
_NODE_PAD_PX = 8.0
_NODE_MAX_LINES = 3
_NODE_LINE_H = 12.5
_SOFT_BREAKS = "/-_."

PosFn = Callable[[int, float], tuple[float, float]]


class LayeredCollisionError(RuntimeError):
    """Raised by ``render`` when ``check_collisions`` finds a blocking overlap."""


def _node_pos_isometric(node_layer: int, node_col: float) -> tuple[float, float]:
    x = _r(_LEFT_MARGIN + node_col * _COL_WIDTH + node_layer * _SHEAR_PER_LAYER)
    y = _r(_TOP_MARGIN + node_layer * _LAYER_HEIGHT)
    return (x, y)


def _node_pos_flat(node_layer: int, node_col: float) -> tuple[float, float]:
    x = _r(_LEFT_MARGIN + node_col * _COL_WIDTH)
    y = _r(_TOP_MARGIN + node_layer * _LAYER_HEIGHT)
    return (x, y)


def check_collisions(spec: LayeredSpec) -> list[Finding]:
    """Blocking findings: too many layers, unknown node refs, and node overlap in
    EITHER variant (isometric shear can create overlaps the flat layout wouldn't, and
    vice versa — both must be clean since both ship in the same document).
    """
    findings: list[Finding] = []
    n_layers = len(spec.layer_labels)
    if n_layers == 0:
        findings.append(
            Finding(
                gate="layered.rule",
                message="layered workflow has no layers",
                severity=Severity.CRIT,
            )
        )
        return findings
    if n_layers > _MAX_LAYERS:
        findings.append(
            Finding(
                gate="layered.rule",
                message=f"{n_layers} layers exceeds the {_MAX_LAYERS}-layer legibility cap",
                severity=Severity.CRIT,
            )
        )

    node_ids = {n.id for n in spec.nodes}
    for n in spec.nodes:
        if not (0 <= n.layer < n_layers):
            findings.append(
                Finding(
                    gate="layered.rule",
                    message=f"node '{n.id}' layer={n.layer} out of range [0,{n_layers})",
                    severity=Severity.CRIT,
                )
            )
    for c in spec.connectors:
        if c.src not in node_ids:
            findings.append(
                Finding(
                    gate="layered.rule",
                    message=f"connector references unknown src '{c.src}'",
                    severity=Severity.CRIT,
                )
            )
        if c.dst not in node_ids:
            findings.append(
                Finding(
                    gate="layered.rule",
                    message=f"connector references unknown dst '{c.dst}'",
                    severity=Severity.CRIT,
                )
            )
    if findings:
        return findings

    for pos_fn, variant in ((_node_pos_isometric, "isometric"), (_node_pos_flat, "flat")):
        boxes: list[BBox] = []
        for n in spec.nodes:
            x, y = pos_fn(n.layer, n.col)
            boxes.append((x, y, x + _NODE_W, y + _NODE_H))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if _intersects(boxes[i], boxes[j]):
                    findings.append(
                        Finding(
                            gate="layered.collision",
                            message=f"[{variant}] nodes '{spec.nodes[i].id}' and '{spec.nodes[j].id}' overlap",
                            severity=Severity.CRIT,
                        )
                    )
                elif _gap(boxes[i], boxes[j]) < 22.0:
                    findings.append(
                        Finding(
                            gate="layered.collision",
                            message=f"[{variant}] gap between '{spec.nodes[i].id}' and '{spec.nodes[j].id}' below the 22px minimum",
                            severity=Severity.CRIT,
                        )
                    )

    return findings


def _node_lines(label: str) -> tuple[list[str], float]:
    """A node label as ``(lines, font px)`` that fits the 110 px box: wrapped at spaces, then after ``/ - _ .`` inside a word too long
    for a line, then (only if still too long) cut with an ellipsis — the full text stays in the node's ``<title>``.

    A label that fits on one line is returned unchanged, so a figure whose labels already fit is drawn exactly as before. A label
    that did not fit used to run through the box and into its neighbour with no error.
    """
    avail = _NODE_W - 2 * _NODE_PAD_PX
    if len(label) * _LABEL_FONT_PX * _CHAR_ADVANCE_FACTOR <= avail:
        return [label], _LABEL_FONT_PX
    font = _LABEL_FONT_PX if len(label) <= 30 else 10.5
    per_line = max(4, int(avail / (font * _CHAR_ADVANCE_FACTOR)))
    lines: list[str] = []
    for line in _wrap_text(label, font, avail) or [label]:
        while len(line) > per_line:
            cut = max((line.rfind(ch, 0, per_line) for ch in _SOFT_BREAKS), default=-1)
            cut = cut + 1 if cut >= per_line // 3 else per_line
            lines.append(line[:cut])
            line = line[cut:]
        lines.append(line)
    if len(lines) > _NODE_MAX_LINES:
        lines = lines[:_NODE_MAX_LINES]
        lines[-1] = lines[-1][: max(1, per_line - 1)].rstrip() + "\u2026"
    return lines, font


def _defs_css() -> str:
    return (
        "<style><![CDATA["
        ".layer-plane{fill:var(--paper-2,#141420);opacity:0.35;stroke:currentColor;stroke-width:0.75;}"
        # A plane's name is drawn after the connectors and knocked out of them (a stroke in the paper colour, painted first), so a
        # line that crosses the heading never strikes through it.
        ".layer-label{font-family:var(--f-mono,monospace);fill:currentColor;fill-opacity:0.7;stroke:var(--paper,#0b0b10);"
        "stroke-width:5;stroke-linejoin:round;paint-order:stroke;}"
        ".lnode{fill:var(--paper,#0b0b10);stroke:currentColor;stroke-width:1.5;}"
        ".lnode-label{font-family:var(--f-body,Inter,system-ui,sans-serif);fill:currentColor;}"
        ".lconn{stroke:currentColor;stroke-width:1.5;fill:none;opacity:0.8;}"
        ".figure-caption{font-family:var(--f-body,Inter,system-ui,sans-serif);fill:currentColor;}"
        ".layered-iso{display:block;}"
        ".layered-flat{display:none;}"
        "@media (prefers-reduced-motion: reduce), print{"
        ".layered-iso{display:none;}"
        ".layered-flat{display:block;}"
        "}"
        "]]></style>"
    )


def _render_variant(spec: LayeredSpec, pos_fn: PosFn, css_class: str) -> str:
    parts: list[str] = [f'<g class="{css_class}">']
    headings: list[str] = []

    for layer_idx, layer_label in enumerate(spec.layer_labels):
        x0, y0 = pos_fn(layer_idx, -0.3)
        # The plane spans its OWN columns. It used the total node count of the whole figure, so a figure with eleven nodes drew every
        # plane eleven columns wide, far past the canvas.
        last_col = max((n.col for n in spec.nodes if n.layer == layer_idx), default=0.0)
        x1, _y1 = pos_fn(layer_idx, last_col + 0.3)
        plane_w = _r(x1 - x0 + _NODE_W)
        parts.append(
            f'<rect class="layer-plane" x="{_fmt(x0)}" y="{_fmt(y0 - 8.0)}" '
            f'width="{_fmt(plane_w)}" height="{_fmt(_NODE_H + 16.0)}" rx="8"/>'
        )
        headings.append(
            f'<text class="layer-label" x="{_fmt(x0)}" y="{_fmt(y0 - 14.0)}" '
            f'font-size="10">{_escape(layer_label.upper())}</text>'
        )

    nodes_by_id = {n.id: n for n in spec.nodes}
    for conn in spec.connectors:
        src, dst = nodes_by_id[conn.src], nodes_by_id[conn.dst]
        sx, sy = pos_fn(src.layer, src.col)
        dx, dy = pos_fn(dst.layer, dst.col)
        x0c, y0c = _r(sx + _NODE_W / 2), _r(sy + _NODE_H / 2)
        x1c, y1c = _r(dx + _NODE_W / 2), _r(dy + _NODE_H / 2)
        parts.append(
            f'<line class="lconn" x1="{_fmt(x0c)}" y1="{_fmt(y0c)}" x2="{_fmt(x1c)}" y2="{_fmt(y1c)}"/>'
        )
        if conn.label:
            mx, my = _r((x0c + x1c) / 2), _r((y0c + y1c) / 2 - 6.0)
            parts.append(
                f'<text class="lnode-label" x="{_fmt(mx)}" y="{_fmt(my)}" '
                f'text-anchor="middle" font-size="10">{_escape(conn.label)}</text>'
            )

    parts.extend(headings)

    for n in spec.nodes:
        x, y = pos_fn(n.layer, n.col)
        lines, font = _node_lines(n.label)
        first = y + _NODE_H / 2 + 4.0 - (len(lines) - 1) * _NODE_LINE_H / 2
        if len(lines) == 1:
            text = (
                f'<text class="lnode-label" x="{_fmt(x + _NODE_W / 2)}" y="{_fmt(first)}" '
                f'text-anchor="middle" font-size="{font:g}">{_escape(lines[0])}</text>'
            )
        else:
            spans = "".join(
                f'<tspan x="{_fmt(x + _NODE_W / 2)}" dy="{_fmt(0.0 if m == 0 else _NODE_LINE_H)}">{_escape(line)}</tspan>' for m, line in enumerate(lines)
            )
            text = (
                f'<text class="lnode-label" x="{_fmt(x + _NODE_W / 2)}" y="{_fmt(first)}" text-anchor="middle" '
                f'font-size="{font:g}"><title>{_escape(n.label)}</title>{spans}</text>'
            )
        parts.append(
            f'<rect class="lnode" x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(_NODE_W)}" height="{_fmt(_NODE_H)}" rx="6"/>{text}'
        )

    parts.append("</g>")
    return "".join(parts)


def render(spec: LayeredSpec, *, theme: str | None = None) -> str:
    """Render ``spec`` to a self-contained ``<svg>`` carrying BOTH the isometric-shear
    view and its flat fallback (CSS-switched). Raises ``LayeredCollisionError`` on any
    blocking finding in either variant. Deterministic across calls.
    """
    collisions = check_collisions(spec)
    if collisions:
        messages = "; ".join(f.message for f in collisions)
        raise LayeredCollisionError(
            f"{spec.id}: {len(collisions)} blocking collision(s): {messages}"
        )

    body = _defs_css()
    body += _render_variant(spec, _node_pos_isometric, "layered-iso")
    body += _render_variant(spec, _node_pos_flat, "layered-flat")

    if spec.title:
        body += (
            f'<text x="{_fmt(spec.width / 2)}" y="20" class="figure-title" '
            f'font-size="18" text-anchor="middle" font-weight="700" fill="currentColor">{_escape(spec.title)}</text>'
        )
    if spec.caption:
        body += (
            f'<text x="{_fmt(spec.width / 2)}" y="{_fmt(spec.height - 10.0)}" class="figure-caption" '
            f'font-size="12" text-anchor="middle">{_escape(spec.caption)}</text>'
        )

    # Stamp data-theme ONLY when a caller explicitly pins a theme (the standalone-SVG CLI
    # path). Embedded in a docgen document the page owns the theme: tokens.py declares the
    # palette on `[data-theme="dark"]` / `[data-theme="light"]`, so a data-theme attribute on
    # the <svg> re-declares that whole palette ON THE FIGURE — a descendant of the <html> the
    # toggle writes to — and the figure keeps its pinned colours while the rest of the page
    # switches. Measured: with a hardcoded "dark" default, 7 of 21 figures in a real document
    # stayed dark in light mode. None = inherit from the page, which is what an embedded
    # figure should always do.
    theme_attr = f'data-theme="{theme}" ' if theme else ""
    return (
        f'<svg viewBox="0 0 {_fmt(spec.width)} {_fmt(spec.height)}" '
        f'xmlns="http://www.w3.org/2000/svg" class="fig-figure fig-layered" {theme_attr}'
        f'role="img" aria-label="{_escape(spec.title or spec.id)}">{body}</svg>'
    )
