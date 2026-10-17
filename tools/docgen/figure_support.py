"""Shared figure plumbing: unique ids, anchors, reading keys, scoped hover CSS, and the figure runtime.

Every figure in a document is an inline ``<svg>``. Inlining ten or fifty of them into ONE page makes four things
global that were written as if they were local, and each one was a measured defect (OG-250 … OG-261):

* **ids.** ``<clipPath id="zr-c0">`` and ``url(#zr-g0)`` exist in every chart; Mermaid's ``arrowhead`` marker and
  its node ids (``API``, ``BT``) exist in every diagram. ``url(#x)`` resolves to the FIRST element with that id in the
  document, so a sankey borrowed a heat-map's gradient. ``scope_svg_ids`` prefixes every id a figure declares, and
  every reference to it, with the figure's own scope.
* **CSS.** A ``<style>`` inside an inline SVG applies to the whole page. Hover rules are therefore generated per
  figure and every selector starts with ``svg[data-fig="<scope>"]`` (``native_figure_css``).
* **anchors.** A figure, each numbered badge in it, and each section of the text get a stable ``id`` so the prose,
  the picture and the reading key can link to one another (``fig_dom_id`` / ``section_dom_id``).
* **meaning.** A numbered circle that does not say what number 3 IS is decoration. ``reading_key`` produces the
  list the document prints under the figure and the blueprint JSON carries for machines.

Stdlib only; ``mypy --strict`` clean; deterministic (no clock, no randomness).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, NamedTuple, TypedDict

_ASSETS: Final[Path] = Path(__file__).resolve().parent / "assets"
# `(?<![\w-])`, not `\b`: a word boundary also sits between `-` and `i` in `data-id="..."`, and rewriting THAT attribute
# scopes the mark's own id while leaving the `data-nb` / `data-eg` / `data-en` lists that name it untouched, which silently
# breaks every adjacency highlight (found by hovering a node in a built document, not by any unit test).
_ID_DECL_RE: Final = re.compile(r'(?<![\w-])id="([^"]+)"')
_STYLE_BLOCK_RE: Final = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.DOTALL)
_FIG_PREFIX_RE: Final = re.compile(r"^\s*(?:Fig(?:ure)?\.?)\s*(?:\d+\s*)?[-–—:.]?\s*", re.IGNORECASE)


class KeyItem(TypedDict):
    """One line of a figure's reading key."""

    n: int
    title: str
    detail: str
    anchor: str


def slug(text: str) -> str:
    """Lower-case ``text`` to ``[a-z0-9-]``; never empty."""
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return out or "x"


def fig_dom_id(fig_id: str) -> str:
    """The DOM id (and SVG scope) of a figure: ``fig-<slug>``. Figures already named ``fig-...`` are not re-prefixed."""
    s = slug(fig_id)
    return s if s.startswith("fig-") else f"fig-{s}"


def section_dom_id(title: str, taken: set[str]) -> str:
    """A unique ``sec-<slug>`` for a section heading (a numeric suffix breaks ties, in document order)."""
    base = f"sec-{slug(title)[:48].rstrip('-')}"
    candidate = base
    n = 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    taken.add(candidate)
    return candidate


def strip_fig_prefix(caption: str) -> str:
    """Drop a hand-written ``Fig. -`` / ``Figure 3:`` lead-in: the document numbers its own figures now."""
    return _FIG_PREFIX_RE.sub("", caption, count=1).strip() or caption.strip()


def scope_svg_ids(svg: str, scope: str) -> str:
    """Prefix every id declared in ``svg``, and every reference to one, with ``scope-``.

    References handled: ``url(#id)`` (paint servers, clip paths, markers), ``href="#id"`` / ``xlink:href="#id"``
    (``<use>``, ``<mpath>``) and ``#id`` selectors inside the SVG's own ``<style>`` blocks (Mermaid). Ids that already
    start with ``scope`` are left alone, so the function is idempotent and an engine that scoped its own ids is not
    double-prefixed.
    """
    ids = sorted({i for i in _ID_DECL_RE.findall(svg) if not i.startswith(scope)}, key=len, reverse=True)
    if not ids:
        return svg
    alt = "|".join(re.escape(i) for i in ids)

    out = re.sub(rf'((?<![\w-])id=")({alt})(")', lambda m: f'{m.group(1)}{scope}-{m.group(2)}{m.group(3)}', svg)
    out = re.sub(rf"(url\(#)({alt})(\))", lambda m: f"{m.group(1)}{scope}-{m.group(2)}{m.group(3)}", out)
    out = re.sub(rf'(href=")#({alt})(")', lambda m: f'{m.group(1)}#{scope}-{m.group(2)}{m.group(3)}', out)

    def _style(m: re.Match[str]) -> str:
        body = re.sub(rf"#({alt})(?![\w-])", lambda x: f"#{scope}-{x.group(1)}", m.group(2))
        return f"{m.group(1)}{body}{m.group(3)}"

    return _STYLE_BLOCK_RE.sub(_style, out)


# ---- the figure SIZE STANDARD (FS-1 … FS-5; docs/design/FIGURE_SYSTEM.md §12) --------------------------------------------
# A native diagram is a bare ``viewBox`` with no size of its own, so the page used to stretch it to the width of the
# column: 960x740 drawn at x1.2 (1150x886), taller than a laptop screen, where the build before had drawn it at x0.61
# (7px text). Nobody had decided a size. These numbers decide it, once, for every figure; the stylesheet (``tokens.py``)
# and the real-browser check read the same constants.
FIG_MAX_W_PX: Final = 1150  # FS-5  no figure is wider than this, whatever the monitor
FIG_FIT_VH: Final = 82  # FS-2  a landscape figure is at most this share of the viewport height ...
FIG_FIT_H_PX: Final = 700  # ... and at most this many pixels, whichever is smaller, so figure and caption fit one screen
FIG_MIN_SCALE: Final = 0.8  # FS-3  never below this share of the design size (a 12px label stays above 9px): scroll instead
FIG_UP_SCALED: Final = 1.3  # FS-1  a diagram drawn on an abstract canvas may be enlarged this much; an engine chart never
FIG_TALL_RATIO: Final = 0.9  # FS-4  height >= this share of width = a tall figure, read by scrolling: exempt from FS-2
# Node-and-edge diagrams sit on the faint blueprint grid (the line-art figures the grid was designed for). Charts, sequence
# diagrams and foreign engines do not: the grid showed through every plot area, and a sequence diagram has no free layout.
GRID_KINDS: Final = frozenset({"flowchart", "state", "system_map", "dependency_graph"})
# Kinds that are a block of HTML with its own layout (the explorer), not a picture with a design size: no sizing, no grid.
BLOCK_KINDS: Final = frozenset({"explorer"})

# Attribute values are matched as quoted strings so a ">" inside one (``aria-label="a > b"``) cannot end the tag early.
_ROOT_SVG_RE: Final = re.compile(r"""<svg\b((?:[^>"']|"[^"]*"|'[^']*')*)>""", re.IGNORECASE)
_VIEWBOX_RE: Final = re.compile(r'\bviewBox\s*=\s*"\s*[-\d.eE]+[ ,]+[-\d.eE]+[ ,]+([\d.eE]+)[ ,]+([\d.eE]+)\s*"')
_WIDTH_PX_RE: Final = re.compile(r'\swidth\s*=\s*"\s*[\d.]+\s*(?:px)?\s*"')
_HEIGHT_PX_RE: Final = re.compile(r'\sheight\s*=\s*"\s*[\d.]+\s*(?:px)?\s*"')


class FigureGeometry(NamedTuple):
    """What the document needs to size a picture: its design size, and whether the picture already declares a pixel size."""

    width: float
    height: float
    natural: bool


def figure_geometry(svg: str) -> FigureGeometry | None:
    """Read the ROOT ``<svg>``'s design size, or ``None`` when it cannot be measured (the document then guesses nothing).

    ``natural`` is true when the root declares a pixel ``width`` and ``height`` of its own (an engine chart, a Mermaid
    diagram): such a picture is already drawn at the size its author chose and is never enlarged. A bare ``viewBox``
    (every native diagram) has no size of its own, which is exactly the case the standard exists for.
    """
    root = _ROOT_SVG_RE.search(svg)
    if root is None:
        return None
    attrs = root.group(1)
    box = _VIEWBOX_RE.search(attrs)
    if box is None:
        return None
    width, height = float(box.group(1)), float(box.group(2))
    if width <= 0 or height <= 0:
        return None
    declared = bool(_WIDTH_PX_RE.search(attrs) and _HEIGHT_PX_RE.search(attrs))
    return FigureGeometry(width, height, declared)


_DARK_INK: Final = "#0B0E14"
_LIGHT_INK: Final = "#FFFFFF"
_PURE_BLACK: Final = "#000000"
_AA: Final = 4.5
_RGB_RE: Final = re.compile(r"^rgba?\(\s*(\d+(?:\.\d+)?)[ ,]+(\d+(?:\.\d+)?)[ ,]+(\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_color(color: str) -> tuple[float, float, float] | None:
    """``#rgb``, ``#rrggbb[aa]`` or ``rgb[a](r, g, b)`` -> ``(r, g, b)``; anything else (``var(--x)``, a gradient) -> ``None``."""
    c = color.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", c):
        return tuple(float(int(h + h, 16)) for h in c[1:])  # type: ignore[return-value]
    if re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", c):
        return float(int(c[1:3], 16)), float(int(c[3:5], 16)), float(int(c[5:7], 16))
    m = _RGB_RE.match(c)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    return None


def _luminance(rgb: tuple[float, float, float]) -> float:
    def f(v: float) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2])


def contrast_ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = (la, lb) if la >= lb else (lb, la)
    return (hi + 0.05) / (lo + 0.05)


def ink_for(fill: str) -> str | None:
    """The label ink for text drawn ON ``fill``: brand near-black or white, whichever reads better; pure black or white
    for the mid-tone band where neither reaches WCAG AA. ``None`` when ``fill`` is not a literal colour.

    This is the Python twin of ``tools/visual-engine/adapters/echarts/contrast.mjs::inkFor`` — one rule, two languages,
    kept identical by a parity test (``tools/tests/test_figure_system.py``).
    """
    rgb = parse_color(fill)
    if rgb is None:
        return None
    dark = contrast_ratio(rgb, parse_color(_DARK_INK))  # type: ignore[arg-type]
    light = contrast_ratio(rgb, parse_color(_LIGHT_INK))  # type: ignore[arg-type]
    best_ink, best = (_DARK_INK, dark) if dark >= light else (_LIGHT_INK, light)
    if best >= _AA:
        return best_ink
    black = contrast_ratio(rgb, parse_color(_PURE_BLACK))  # type: ignore[arg-type]
    return _PURE_BLACK if black >= light else _LIGHT_INK


def explorer_runtime_js() -> str:
    """The module explorer's runtime (zoom, labels, panel, reader). Inlined only into a document that holds an explorer."""
    return (_ASSETS / "explorer_runtime.js").read_text(encoding="utf-8")


def runtime_js() -> str:
    """The figure runtime (tooltips, pinning, keyboard, nearest-mark assist, adjacency). One copy per document."""
    return (_ASSETS / "figure_runtime.js").read_text(encoding="utf-8")


def native_figure_css(
    fid: str,
    nodes: list[tuple[str, list[str], list[str]]],
    edges: list[tuple[str, list[str]]],
) -> str:
    """Scoped hover/focus CSS for a native docgen diagram (flowchart, state, system map, dependency graph).

    ``nodes`` are ``(id, neighbour-node-ids, incident-edge-ids)``; ``edges`` are ``(id, [end-node-ids])``. The rules
    are the Python twin of ``tools/visual-engine/adapters/echarts/figure-layer.mjs``'s ``figureCss`` (same attribute
    contract: ``data-k`` / ``data-id`` / ``data-nb`` / ``data-eg`` / ``data-en``), and the two are exercised by the
    same browser test. Law: a hover state may change brightness, outline, thickness and opacity — never hue, never
    the fill of an open path, never the pointer target.
    """
    s = f'svg[data-fig="{fid}"]'
    nojs = f"{s}:not([data-ve-js])"
    r: list[str] = [
        f"/* ve-fig v1 - scoped to {fid} */",
        f"{s} text,{s} tspan{{pointer-events:none}}",
        f'{s} [data-k="node"],{s} [data-k="edge"],{s} a.fig-badge{{cursor:pointer}}',
        # Glyph interiors are `fill:none`, which the browser does not hit-test; make the whole shape a target.
        f'{s} [data-k="node"] *{{pointer-events:all}}',
        f'{s} [data-k="node"],{s} [data-k="edge"]{{transition:opacity .14s ease,filter .14s ease}}',
        f"@media (prefers-reduced-motion:reduce){{{s} [data-k]{{transition:none}}}}",
        (
            f'{s} [data-k="node"]:hover>:not(title),{s} [data-k="node"]:focus-visible>:not(title)'
            "{stroke-width:2.8px;vector-effect:non-scaling-stroke;filter:brightness(1.18)}"
        ),
        f"{s} a.fig-badge:hover circle,{s} a.fig-badge:focus-visible circle{{stroke-width:2.6px;vector-effect:non-scaling-stroke}}",
    ]

    def dim(selector: str, o: float) -> str:
        return f"{selector}{{opacity:{o}}}"

    def lit_sel(ids: list[str]) -> str:
        return ":is(" + ",".join(f'[data-id="{i}"]' for i in ids) + ")"

    def rule(hover: str, lit: list[str], lit_edges: list[str]) -> None:
        r.append(dim(f'{hover} [data-k="node"]:not({lit_sel(lit)})', 0.3))
        r.append(dim(f'{hover} [data-k="edge"]:not({lit_sel(lit)})', 0.1))
        if lit_edges:
            r.append(
                f'{hover} {lit_sel(lit_edges)}[data-k="edge"]:not(.edge-hit)'
                "{opacity:1;stroke-width:3.2px;vector-effect:non-scaling-stroke}"
            )

    if len(nodes) + len(edges) <= 160:
        for nid, nb, eg in nodes:
            rule(f'{nojs}:has([data-k="node"][data-id="{nid}"]:hover)', [nid, *nb, *eg], eg)
        for eid, ends in edges:
            rule(f'{nojs}:has([data-k="edge"][data-id="{eid}"]:hover)', [eid, *ends], [eid])
    # Runtime-driven focus: same look, any size of diagram.
    r.append(f"{s}[data-ve-js][data-ve-on] [data-k]:not(.ve-on){{opacity:.2}}")
    # `:not(.edge-hit)`: the wide transparent twin of an edge is its pointer target; narrowing it on hover would drop the
    # pointer off the very line that just lit up.
    r.append(
        f'{s}[data-ve-js] [data-k="edge"].ve-on:not(.edge-hit){{opacity:1;stroke-width:3.2px;vector-effect:non-scaling-stroke}}'
    )
    r.append(f'{s} .ve-pin>:not(title){{stroke-width:3.2px;vector-effect:non-scaling-stroke}}')
    return "\n".join(r)
