"""Glyph-per-node SVG shape library (DESIGN_SYSTEM.md S4, MOTION_SPEC.md).

One function per ``NodeType`` returning a deterministic SVG fragment for the node's
bounding box. Rules:

- ``currentColor`` stroke everywhere (theme-aware via CSS ``color``).
- ``--shield`` fill only when the node is ``highlight``ed (a KEY node).
- Deterministic: all floats rounded to 2 dp, no ``random``/timestamp-derived ids —
  every id is derived from the node's own ``id`` string so two builds of the same
  spec are byte-identical.
- Compute/engine/mind/detector nodes (``alive=True``) get an ambient-pulse inner
  element (MOTION_SPEC S4) — CSS animation only, gated behind
  ``prefers-reduced-motion: no-preference`` by the caller's stylesheet.

Stdlib only; mypy --strict clean.
"""

from __future__ import annotations

from tools.docgen.models import Node, NodeType

_STROKE_WIDTH = 1.5


def _r(value: float) -> float:
    """Round to the diagram's fixed 2dp precision (determinism/hash-gate)."""
    return round(value, 2)


def _fmt(value: float) -> str:
    """Format a coordinate deterministically (no trailing float noise)."""
    r = _r(value)
    if r == int(r):
        return str(int(r))
    return f"{r:g}"


def _safe_id(node_id: str) -> str:
    """Derive a deterministic, SVG-id-safe token from a node id (no random ids)."""
    out = []
    for ch in node_id:
        out.append(ch if (ch.isalnum() or ch in "-_") else "-")
    return "".join(out) or "n"


def _fill(node: Node) -> str:
    return "var(--shield)" if node.highlight else "none"


# Default colour family by node type, so a diagram with several kinds of box is not one ink. A node's own `tone`
# wins; "none" restores the single-ink look. The families map to the Atlas brand colours in `visual._defs_css`.
_DEFAULT_TONE: dict[NodeType, str] = {
    NodeType.SOURCE: "blue",
    NodeType.PROCESS: "steel",
    NodeType.DECISION: "gold",
    NodeType.GATE: "green",
    NodeType.DATASTORE: "bronze",
    NodeType.OUTPUT: "blue",
    NodeType.FALLBACK: "steel",
    NodeType.ATTACKER: "red",
    NodeType.STATE: "blue",
}


# The closed vocabulary of a node's ``tone``. It is printed into an SVG ``class`` attribute, so free text would let a
# crafted spec close the attribute and add its own (``x" onclick="..."``): the colour families, ``none`` and ``""``
# are the only values that ever reach the markup (OG-273).
TONES: tuple[str, ...] = ("blue", "gold", "green", "red", "bronze", "steel")


def validate_tone(tone: str) -> str:
    """``tone`` as a spec writes it — ``""`` (by node type), ``"none"`` or one of :data:`TONES` — or ``ValueError``."""
    if tone in ("", "none") or tone in TONES:
        return tone
    raise ValueError(f"unknown tone {tone!r}: use one of {', '.join(TONES)}, or 'none' for the single-ink look")


def resolve_tone(node: Node) -> str:
    """The colour family of ``node``: its own ``tone``, else the default for its type, else ``""`` (single ink)."""
    tone = validate_tone(node.tone)
    if tone == "none":
        return ""
    return tone or _DEFAULT_TONE.get(node.type, "")


def _class_list(node: Node, extra: str = "") -> str:
    classes = [f"glyph glyph-{node.type.value}"]
    tone = resolve_tone(node)
    if tone:
        classes.append(f"tone-{tone}")
    if node.highlight:
        classes.append("glyph-hi")
    if node.alive:
        classes.append("glyph-alive")
    if extra:
        classes.append(extra)
    return " ".join(classes)


def glyph_source(node: Node) -> str:
    """Rounded stadium — an entry point / source of data."""
    x, y, w, h = _fmt(node.x), _fmt(node.y), _fmt(node.w), _fmt(node.h)
    rx = _fmt(node.h / 2)
    return (
        f'<rect class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
        f'fill="{_fill(node)}" stroke="currentColor" stroke-width="{_STROKE_WIDTH}"/>'
    )


def glyph_process(node: Node) -> str:
    """Plain rectangle — a processing step."""
    x, y, w, h = _fmt(node.x), _fmt(node.y), _fmt(node.w), _fmt(node.h)
    rx = _fmt(6.0)
    return (
        f'<rect class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
        f'fill="{_fill(node)}" stroke="currentColor" stroke-width="{_STROKE_WIDTH}"/>'
    )


def glyph_decision(node: Node) -> str:
    """Diamond — a yes/no branch point."""
    cx, cy = _r(node.cx), _r(node.cy)
    hw, hh = _r(node.w / 2), _r(node.h / 2)
    pts = " ".join(
        f"{_fmt(px)},{_fmt(py)}"
        for px, py in (
            (cx, cy - hh),
            (cx + hw, cy),
            (cx, cy + hh),
            (cx - hw, cy),
        )
    )
    return (
        f'<polygon class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'points="{pts}" fill="{_fill(node)}" stroke="currentColor" '
        f'stroke-width="{_STROKE_WIDTH}" stroke-linejoin="round"/>'
    )


def glyph_gate(node: Node) -> str:
    """Hexagon — a validation/security gate."""
    x, y, w, h = node.x, node.y, node.w, node.h
    inset = _r(w * 0.18)
    pts = " ".join(
        f"{_fmt(px)},{_fmt(py)}"
        for px, py in (
            (x + inset, y),
            (x + w - inset, y),
            (x + w, y + h / 2),
            (x + w - inset, y + h),
            (x + inset, y + h),
            (x, y + h / 2),
        )
    )
    return (
        f'<polygon class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'points="{pts}" fill="{_fill(node)}" stroke="currentColor" '
        f'stroke-width="{_STROKE_WIDTH}" stroke-linejoin="round"/>'
    )


def glyph_datastore(node: Node) -> str:
    """Cylinder — a data store / database."""
    x, y, w, h = node.x, node.y, node.w, node.h
    ry = _r(min(h * 0.16, 14.0))
    body_h = _r(h - ry)
    path_d = (
        f"M {_fmt(x)} {_fmt(y + ry)} "
        f"a {_fmt(w / 2)} {_fmt(ry)} 0 0 0 {_fmt(w)} 0 "
        f"v {_fmt(body_h - ry)} "
        f"a {_fmt(w / 2)} {_fmt(ry)} 0 0 1 {_fmt(-w)} 0 "
        f"z"
    )
    top_ellipse = (
        f'<ellipse cx="{_fmt(node.cx)}" cy="{_fmt(y + ry)}" rx="{_fmt(w / 2)}" '
        f'ry="{_fmt(ry)}" fill="none" stroke="currentColor" stroke-width="{_STROKE_WIDTH}"/>'
    )
    return (
        f'<g class="{_class_list(node)}" data-node="{_safe_id(node.id)}">'
        f'<path d="{path_d}" fill="{_fill(node)}" stroke="currentColor" '
        f'stroke-width="{_STROKE_WIDTH}"/>{top_ellipse}</g>'
    )


def glyph_output(node: Node) -> str:
    """Parallelogram — an output / export / report artifact."""
    x, y, w, h = node.x, node.y, node.w, node.h
    skew = _r(min(w * 0.18, 20.0))
    pts = " ".join(
        f"{_fmt(px)},{_fmt(py)}"
        for px, py in (
            (x + skew, y),
            (x + w, y),
            (x + w - skew, y + h),
            (x, y + h),
        )
    )
    return (
        f'<polygon class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'points="{pts}" fill="{_fill(node)}" stroke="currentColor" '
        f'stroke-width="{_STROKE_WIDTH}" stroke-linejoin="round"/>'
    )


def glyph_fallback(node: Node) -> str:
    """Dashed rounded rect — a fallback/escalation path."""
    x, y, w, h = _fmt(node.x), _fmt(node.y), _fmt(node.w), _fmt(node.h)
    rx = _fmt(6.0)
    return (
        f'<rect class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
        f'fill="{_fill(node)}" stroke="currentColor" stroke-width="{_STROKE_WIDTH}" '
        f'stroke-dasharray="6 4"/>'
    )


def glyph_attacker(node: Node) -> str:
    """Ember-tinted rect — an adversarial/attacker-controlled node."""
    x, y, w, h = _fmt(node.x), _fmt(node.y), _fmt(node.w), _fmt(node.h)
    rx = _fmt(6.0)
    fill = "var(--shield)" if node.highlight else "var(--ember-tint, rgba(192,40,42,0.12))"
    return (
        f'<rect class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
        f'fill="{fill}" stroke="var(--ember, currentColor)" stroke-width="{_STROKE_WIDTH}"/>'
    )


def glyph_junction(node: Node) -> str:
    """Small filled circle — a fork/merge junction point."""
    cx, cy = _fmt(node.cx), _fmt(node.cy)
    r = _fmt(min(node.w, node.h) / 4)
    return (
        f'<circle class="{_class_list(node)}" data-node="{_safe_id(node.id)}" '
        f'cx="{cx}" cy="{cy}" r="{r}" fill="currentColor" stroke="none"/>'
    )


_GLYPH_FUNCS = {
    NodeType.SOURCE: glyph_source,
    NodeType.PROCESS: glyph_process,
    NodeType.DECISION: glyph_decision,
    NodeType.GATE: glyph_gate,
    NodeType.DATASTORE: glyph_datastore,
    NodeType.OUTPUT: glyph_output,
    NodeType.FALLBACK: glyph_fallback,
    NodeType.ATTACKER: glyph_attacker,
    NodeType.JUNCTION: glyph_junction,
    NodeType.STATE: glyph_source,  # state diagrams reuse the rounded-stadium shape
}


def render_glyph(node: Node) -> str:
    """Dispatch to the glyph function matching ``node.type``. Deterministic output."""
    fn = _GLYPH_FUNCS[node.type]
    return fn(node)


def ambient_pulse_defs(node_id: str) -> str:
    """Inner ambient-pulse element for an ``alive`` compute/engine node (MOTION_SPEC S4).

    A slow (2.5s), low-amplitude opacity breathing on an inner ring, wrapped by the
    caller in ``@media (prefers-reduced-motion: no-preference)``. Deterministic:
    the animation is pure CSS keyframes referencing a class, no per-build randomness.
    """
    safe = _safe_id(node_id)
    return (
        f'<circle class="glyph-pulse" data-node="{safe}" '
        f'r="3" fill="var(--shield-hi, currentColor)" opacity="0.35"/>'
    )
