"""HTML partials for the doc-system (DESIGN_SYSTEM.md §4-6, RULEBOOK L21).

Every function returns a plain ``str`` of HTML. All interpolated text is escaped via
``html.escape`` — callers may pass pre-built (already-escaped/safe) HTML fragments as
``body``/``svg`` parameters where documented. Stdlib only; mypy --strict clean.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from html import escape
from pathlib import Path
from typing import Final

from tools.docgen import engine_config
from tools.docgen.doc_index import split_ordinal
from tools.docgen.figure_support import (
    BLOCK_KINDS,
    FIG_TALL_RATIO,
    FIG_UP_SCALED,
    GRID_KINDS,
    KeyItem,
    figure_geometry,
    scope_svg_ids,
    strip_fig_prefix,
)
from tools.docgen.models import DocHeader, Tier

_ASSETS_DIR: Final[Path] = Path(__file__).resolve().parent / "assets"

_TIER_BADGE_CLASS: Final[dict[Tier, str]] = {
    Tier.PUBLIC: "badge-public",
    Tier.CONFIDENTIAL: "badge-confidential",
    Tier.SECRET: "badge-secret",
}

_TIER_LABEL: Final[dict[Tier, str]] = {
    Tier.PUBLIC: "PUBLIC",
    Tier.CONFIDENTIAL: "CONFIDENTIAL",
    Tier.SECRET: "SECRET",
}

_TIER_GLYPH: Final[dict[Tier, str]] = {
    # Shield glyph for PUBLIC, gold diamond for CONFIDENTIAL, ember hazard-stripe swatch for SECRET.
    Tier.PUBLIC: '<span aria-hidden="true">&#128737;</span>',
    Tier.CONFIDENTIAL: '<span aria-hidden="true">&#9670;</span>',
    Tier.SECRET: '<span aria-hidden="true">&#9888;</span>',
}


def classification_badge(tier: Tier) -> str:
    """Render the classification badge: PUBLIC=shield, CONFIDENTIAL=gold, SECRET=ember-striped."""
    css_class = _TIER_BADGE_CLASS[tier]
    label = _TIER_LABEL[tier]
    glyph = _TIER_GLYPH[tier]
    return f'<span class="badge {css_class}">{glyph}<span>{escape(label)}</span></span>'


def logo_svg() -> str:
    """Inline the project mark, resolved through ``engine_config.mark_path()``.

    Read at CALL time, not import time: the path comes from config/env, and a module-level
    ``Final`` constant froze it before any host override could apply.
    """
    svg = engine_config.mark_path().read_text(encoding="utf-8").strip()
    # Tag with a class hook for sizing via CSS (masthead vs. verified-stamp contexts differ).
    return svg.replace("<svg ", '<svg class="mark-svg" ', 1)


def theme_toggle() -> str:
    """A small inline-JS theme toggle: persists to localStorage, honors prefers-color-scheme.

    Self-contained (no external script). Safe to inline multiple times per page (uses
    ``closest`` lookups and idempotent listeners scoped to the clicked button).
    """
    return """\
<button type="button" class="theme-toggle" data-docgen-theme-toggle aria-label="Toggle light/dark theme">
  <span data-docgen-theme-label>theme</span>
</button>
<script>
(function () {
  var KEY = "docgen-theme";
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll("[data-docgen-theme-label]").forEach(function (el) {
      el.textContent = theme;
    });
  }
  function initial() {
    try {
      var saved = window.localStorage.getItem(KEY);
      if (saved === "dark" || saved === "light") return saved;
    } catch (e) { /* localStorage unavailable — fall through */ }
    var prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
    return prefersLight ? "light" : "dark";
  }
  var current = initial();
  apply(current);
  document.querySelectorAll("[data-docgen-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      current = current === "dark" ? "light" : "dark";
      apply(current);
      try { window.localStorage.setItem(KEY, current); } catch (e) { /* ignore */ }
    });
  });
})();
</script>"""


def masthead(header: DocHeader) -> str:
    """Render the document masthead: logo + title + mono meta line + classification badge + theme toggle."""
    title = escape(header.title)
    meta_bits = [
        escape(header.id),
        escape(header.owner),
        escape(header.status),
        escape(header.last_reviewed),
    ]
    meta_line = " &middot; ".join(meta_bits)
    badge = classification_badge(header.classification)
    logo = logo_svg()
    toggle = theme_toggle()
    return f"""\
<header class="masthead">
  <div class="masthead-brand">
    <div class="masthead-logo" aria-hidden="true">{logo}</div>
    <div class="masthead-titles">
      <h1 class="t-h2">{title}</h1>
      <div class="t-mono-label masthead-meta">{meta_line}</div>
    </div>
  </div>
  <div class="masthead-meta">
    {badge}
    {toggle}
  </div>
</header>"""


def section(
    eyebrow: str,
    body: str,
    *,
    eyebrow_renderer: Callable[[str], str] | None = None,
    section_id: str = "",
    figures: list[tuple[str, int, str]] | None = None,
) -> str:
    """Render a numbered section frame: mono eyebrow (real id) + hairline + body.

    ``eyebrow_renderer`` is the same opt-in used by :func:`data_table`: a heading authored in
    Markdown may legitimately contain a code span, and escaping it left literal backticks in the
    rendered heading. Defaults to plain escaping for callers whose eyebrow is a literal id.

    ``section_id`` makes the heading a link target (``#sec-...``); ``figures`` is the list of
    ``(figure dom id, figure number, caption)`` the section contains, rendered as a chip row under the
    heading so the text points at its pictures — the other half of the link the figure's own
    "back to section" anchor makes.
    """
    render_eyebrow = eyebrow_renderer or escape
    id_attr = f' id="{escape(section_id, quote=True)}"' if section_id else ""
    number, heading = split_ordinal(eyebrow)
    if number and section_id:
        # The number in front of a heading is a reference like any other: hover it and the card says what the section is.
        eyebrow_html = (
            f'<span class="sec-n" data-ref="{escape(section_id, quote=True)}" tabindex="0">{escape(number)}</span>. '
            f"{render_eyebrow(heading)}"
        )
    else:
        eyebrow_html = render_eyebrow(eyebrow)
    chips = ""
    if figures:
        items = "".join(
            f'<a class="fig-chip" href="#{escape(dom, quote=True)}" data-ref="{escape(dom, quote=True)}">'
            f'<span class="fig-chip-n">Fig. {num}</span> {escape(_short(cap))}</a>'
            for dom, num, cap in figures
        )
        chips = f'\n  <nav class="sec-figs" aria-label="Figures in this section">{items}</nav>'
    return f"""\
<section class="doc-section"{id_attr}>
  <h2 class="t-eyebrow">{eyebrow_html}</h2>{chips}
  <div class="t-body">{body}</div>
</section>"""


def _plain(text: str) -> str:
    """Navigation and key text is plain: a code span or emphasis marker in an authored heading or label is dropped
    rather than printed as a literal backtick (which is exactly what the rendered-output guard exists to catch)."""
    return text.replace("`", "").replace("**", "")


def _short(text: str, limit: int = 58) -> str:
    """A caption (or a section title) shortened for a chip or a back-link: first clause, at most ``limit`` characters.

    A leading ordinal is kept whole and set off with a middle dot. Cutting at the first ``". "`` used to read the dot in
    ``"8. Modules"`` as the end of a sentence, so every back-link in the report said ``\u2191 8`` and nothing else: a number
    that named a section nobody could identify (OG-283).
    """
    t = strip_fig_prefix(_plain(text))
    number, rest = split_ordinal(t)
    for sep in (". ", "; "):
        if sep in rest:
            rest = rest.split(sep, 1)[0]
    t = f"{number} \u00b7 {rest}" if number else rest
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "\u2026"


def data_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    cell_renderer: Callable[[str], str] | None = None,
) -> str:
    """Render a data table: dark header row, tabular-nums, wrapped in an overflow-x container.

    ``headers`` and each row cell are HTML-escaped by default (plain text only, no embedded
    markup). A caller whose cells are Markdown — the document generator — passes ``cell_renderer``
    to get inline rendering (code spans, emphasis, links) instead. It stays opt-in because the
    other callers (finance_report and friends) pass literal strings, where a stray ``*`` must
    remain a ``*`` and not silently become emphasis. The renderer is responsible for its own
    escaping; that is why the default is ``escape`` itself.
    """
    render = cell_renderer or escape
    head_cells = "".join(f"<th>{render(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{render(str(c))}</td>" for c in row)
        body_rows.append(f"<tr>{cells}</tr>")
    body_html = "".join(body_rows)
    return f"""\
<div class="doc-table-wrap">
  <table class="doc-table">
    <thead><tr>{head_cells}</tr></thead>
    <tbody>{body_html}</tbody>
  </table>
</div>"""


def svgwrap_open(svg: str, kind: str = "") -> str:
    """The opening tag of a figure's framed canvas, carrying the picture's DESIGN SIZE for the size standard.

    The stylesheet decides how large the picture is shown (FS-1 … FS-5, ``figure_support``); it can only do that if the
    document tells it how large the picture was drawn. ``--fw`` / ``--fh`` are the root ``viewBox``; ``--up`` is the most the
    picture may be enlarged (1 for an engine chart that declares its own pixel size and for any tall figure,
    ``FIG_UP_SCALED`` for a landscape diagram drawn on an abstract canvas). A picture that cannot be measured gets no numbers and keeps the plain "fit the column" rule.
    Node-and-edge diagrams also sit on the faint blueprint grid (``GRID_KINDS``).
    """
    classes = ["svgwrap"]
    style = ""
    if kind in BLOCK_KINDS:
        return '<div class="svgwrap svgwrap--block">'
    geo = figure_geometry(svg)
    if geo is not None:
        classes.append("svgwrap--sized")
        tall = geo.height >= FIG_TALL_RATIO * geo.width - 1e-9
        if tall:
            classes.append("svgwrap--tall")
        # Enlargement exists so a wide, short diagram can use the screen; a tall one is already as tall as it should be.
        up = 1 if geo.natural or tall else FIG_UP_SCALED
        style = f' style="--fw:{geo.width:g};--fh:{geo.height:g};--up:{up:g}"'
    if kind in GRID_KINDS:
        classes.append("svgwrap--grid")
    return f'<div class="{" ".join(classes)}"{style}>'


def figure(
    svg: str,
    caption: str,
    legend_html: str = "",
    *,
    reader_question: str = "",
    insight: str = "",
    fig_id: str = "",
    number: int | None = None,
    kind: str = "",
    section_id: str = "",
    section_title: str = "",
    how_to_read: str = "",
    key: list[KeyItem] | None = None,
    marks: list[tuple[str, str, str]] | None = None,
) -> str:
    """Render a figure block: a numbered, anchored canvas + caption + reading guide.

    ``svg`` is trusted pre-rendered SVG markup (from ``visual.render`` or an engine); ``caption``,
    ``reader_question``, ``insight`` and every key line are escaped. ``legend_html`` is trusted pre-built
    HTML and passed through unescaped by design — callers are responsible for escaping any dynamic text.

    A figure is a VIEW of the same system/calculation the surrounding document already
    describes in prose and numbers — not decoration (see ``../../INTERPRETATION.md``).
    ``reader_question`` states what this specific figure answers; ``insight`` states the
    plain-language conclusion the picture makes obvious that raw numbers/text alone don't.

    When ``fig_id`` is given the figure joins the document's link graph:

    * its ``id`` is ``fig_id`` (``fig-<slug>``) and every id INSIDE the SVG is prefixed with it
      (:func:`tools.docgen.figure_support.scope_svg_ids`), so figures cannot borrow each other's gradients,
      clip paths or markers;
    * the caption leads with ``Fig. <number>`` and links back to the section that describes it;
    * ``how_to_read`` and ``key`` (the numbered explanation of every badge in the picture, each ``<li>``
      carrying the anchor the badge links to) print under the figure in an open ``<details>``.
    """
    legend_block = f'<div class="figure-legend">{legend_html}</div>' if legend_html else ""
    insight_parts = []
    if reader_question:
        insight_parts.append(f'<div class="figure-reader-question">{escape(reader_question)}</div>')
    if insight:
        insight_parts.append(f'<div class="figure-insight">{escape(insight)}</div>')
    insight_block = f'<div class="figure-insight-block">{"".join(insight_parts)}</div>' if insight_parts else ""
    # Emit the optional rows ONLY when they carry something. Interpolating an empty
    # ``legend_block`` into an indented template leaves a line holding two spaces and nothing else,
    # which is a whitespace error to `git diff --check` — so every figure without a legend put a
    # defect into a GENERATED file that no author could fix at the source. Measured: 15 such lines
    # in the tracked `examples/capability-gallery.html` (`OG-245`). Joining the populated blocks is
    # the repair rather than stripping the output afterwards, because a cleanup pass over generated
    # HTML is a second thing to keep correct.
    if not fig_id:
        optional_rows = "".join(f"  {block}\n" for block in (legend_block, insight_block) if block)
        return f"""\
<figure class="doc-figure">
  {svgwrap_open(svg, kind)}{svg}</div>
  <figcaption class="figcap">{escape(caption)}</figcaption>
{optional_rows}</figure>"""

    dom = escape(fig_id, quote=True)
    svg = scope_svg_ids(svg, fig_id)
    num_html = f'<a class="fig-num" href="#{dom}" data-ref="{dom}">Fig. {number}</a> ' if number is not None else ""
    up_html = (
        f' <a class="fig-up" href="#{escape(section_id, quote=True)}" data-ref="{escape(section_id, quote=True)}">'
        f"\u2191 {escape(_short(section_title, 44))}</a>"
        if section_id and section_title
        else ""
    )
    guide_rows: list[str] = []
    if how_to_read:
        guide_rows.append(f'<p class="fig-howto">{escape(_plain(how_to_read))}</p>')
    if key:
        lis = "".join(
            f'<li id="{escape(item["anchor"], quote=True)}"><span class="fig-key-n">{item["n"]}</span>'
            f'<span class="fig-key-t">{escape(_plain(item["title"]))}</span>'
            + (f'<span class="fig-key-d">{escape(_plain(item["detail"]))}</span>' if item["detail"] else "")
            + "</li>"
            for item in key
        )
        guide_rows.append(f'<ol class="fig-key">{lis}</ol>')
    if marks:
        # A figure whose marks carry no number (a tree, a flow) had a column headed "Value" and nothing under it.
        has_value = any(_plain(value).strip() for _label, value, _detail in marks)
        body_rows = "".join(
            f"<tr><th scope=\"row\">{escape(_plain(label))}</th>"
            + (f"<td>{escape(_plain(value))}</td>" if has_value else "")
            + f"<td>{escape(_plain(detail))}</td></tr>"
            for label, value, detail in marks
        )
        value_head = '<th scope="col">Value</th>' if has_value else ""
        guide_rows.append(
            f'<table class="fig-marks"><thead><tr><th scope="col">Mark</th>{value_head}'
            f'<th scope="col">What it tells you</th></tr></thead><tbody>{body_rows}</tbody></table>'
        )
    guide = ""
    if guide_rows:
        summary = "What the numbers mean" if key else ("What each mark shows" if marks else "How to read this figure")
        guide = (
            f'  <details class="fig-guide"{" open" if key or marks else ""}>'
            f"<summary>{summary}</summary>{''.join(guide_rows)}</details>\n"
        )
    kind_attr = f' data-fig-kind-name="{escape(kind, quote=True)}"' if kind else ""
    optional_rows = "".join(f"  {block}\n" for block in (legend_block, insight_block) if block)
    return f"""\
<figure class="doc-figure" id="{dom}"{kind_attr} aria-labelledby="{dom}-cap">
  {svgwrap_open(svg, kind)}{svg}</div>
  <figcaption class="figcap" id="{dom}-cap">{num_html}<span class="fig-title">{escape(strip_fig_prefix(caption) if number is not None else caption)}</span>{up_html}</figcaption>
{optional_rows}{guide}</figure>"""


_CALLOUT_CLASS: Final[dict[str, str]] = {
    "info": "callout-info",
    "warn": "callout-warn",
    "crit": "callout-crit",
}


def callout(kind: str, body: str) -> str:
    """Render a callout block with an accent/severity left rule.

    ``kind`` is one of ``info``/``warn``/``crit`` (unknown kinds fall back to the neutral
    accent rule rather than raising, since callouts are presentational, not gating).
    """
    css_class = _CALLOUT_CLASS.get(kind, "")
    return f'<div class="callout {css_class}">{body}</div>'


def verified_stamp(audit_ref: str) -> str:
    """Render the 'Verified by ' trust footer stamp (DESIGN_SYSTEM §6).

    Static by default (reduced-motion compliant — no animation is emitted here; a future
    motion layer may progressively enhance this markup, but the base render must be legible
    and complete without any script/animation running).
    """
    logo = logo_svg()
    ref = escape(audit_ref)
    # "Verified by <project>" — the slot was always in this markup; before branding.projectName
    # there was no way to fill it, so every document rendered a dangling "Verified by ".
    publisher = escape(engine_config.project_name())
    by_label = f"Verified by {publisher}" if publisher else "Verified by "
    return f"""\
<div class="verified-stamp">
  <div class="verified-stamp-mark" aria-hidden="true">{logo}</div>
  <div class="verified-stamp-text">
    <span class="t-mono-label">{by_label}</span>
    <span class="t-body-sm">{ref}</span>
  </div>
</div>"""


# ---- WCAG AA contrast helpers -------------------------------------------------------------


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    """Parse a ``#rrggbb`` or ``#rgb`` hex color into 0-255 float channels. Raises on bad input."""
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise ValueError(f"not a hex color: {color!r}")
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return float(r), float(g), float(b)


def _srgb_channel_to_linear(c: float) -> float:
    cs = c / 255.0
    if cs <= 0.04045:
        return cs / 12.92
    return math.pow((cs + 0.055) / 1.055, 2.4)


def _relative_luminance(color: str) -> float:
    r, g, b = _hex_to_rgb(color)
    rl = _srgb_channel_to_linear(r)
    gl = _srgb_channel_to_linear(g)
    bl = _srgb_channel_to_linear(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def contrast_ratio(fg: str, bg: str) -> float:
    """Return the WCAG contrast ratio between two ``#rrggbb`` hex colors (1.0 .. 21.0)."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_aa_ok(fg: str, bg: str, large: bool = False) -> bool:
    """True if ``fg`` on ``bg`` meets WCAG AA: >=4.5:1 normal text, >=3:1 large text (>=18pt/14pt-bold)."""
    ratio = contrast_ratio(fg, bg)
    threshold = 3.0 if large else 4.5
    return ratio >= threshold
