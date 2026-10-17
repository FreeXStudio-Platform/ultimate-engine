"""Markdown -> HTML/JSON(/PDF) generator (RULEBOOK L7/L13/L14; ENGINE_PLAN.md §1/§4b).

``build()`` is the integration seam: it canonicalizes the input path (L12 isolation), parses
the document header, renders the Markdown body to a self-contained HTML document (inline CSS
from ``tokens.build_css()``, inline mark, embedded rendered SVG figures), appends the
verified-stamp, stamps the output with a ``generated-by`` + content-sha256 comment (L7), and
— critically — re-runs the leak-gate on the FINAL RENDERED bytes of every output channel
before writing anything to disk. A public document that fails the gate is never written.

This module composes ``classification.py``, ``export_sanitizer.py``, and ``visual.py`` (all
already built by sibling Wave-1 modules) plus this builder's own ``tokens.py``/``components.py``.
PDF rendering is attempted via ``weasyprint`` if importable; otherwise the build degrades
gracefully and records ``pdf: skipped(weasyprint absent)`` rather than silently faking it.

Stdlib + PyYAML (already a project dependency via ``classification.py``) only for the core
path; ``weasyprint`` is optional. mypy --strict clean.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from html import escape, unescape
from pathlib import Path
from typing import Any

from tools.docgen import (
    adjudication,
    charts,
    components,
    diagram_graphs,
    doc_index,
    doc_manifest,
    echarts_bridge,
    engine_config,
    explorer,
    export_sanitizer,
    geo_map,
    i18n,
    isometric3d,
    layered_workflow,
    mermaid_bridge,
    sankey,
    sequence_diagram,
    tokens,
    views,
    visual,
)
from tools.docgen.classification import parse_header, validate_header
from tools.docgen.echarts_bridge import EChartsFigureSpec
from tools.docgen.explorer import ExplorerSpec
from tools.docgen.figure_support import (
    KeyItem,
    explorer_runtime_js,
    fig_dom_id,
    runtime_js,
    section_dom_id,
    strip_fig_prefix,
)
from tools.docgen.geo_map import ChoroplethSpec, GeoMapSpec
from tools.docgen.isometric3d import IsometricSpec
from tools.docgen.mermaid_bridge import MermaidFigureSpec
from tools.docgen.models import (
    BarSpec,
    BuildResult,
    DocHeader,
    Finding,
    GateResult,
    HeatmapSpec,
    LayeredSpec,
    PieSpec,
    RadarSpec,
    SequenceSpec,
    Severity,
    Tier,
    TimelineSpec,
    VisualSpec,
)
from tools.docgen.sankey import SankeySpec
from tools.lib import md_table

# The union of every figure-spec type the generator can dispatch. Node/edge-graph kinds
# (flowchart/state/system_map/dependency_graph) share ``VisualSpec``; the others each own a
# distinct spec shape and render via ``isinstance`` narrowing (mypy --strict clean).
# ``echarts`` delegates data charts to the visual-engine (ENGINE_ROUTING_POLICY.json) —
# one engine per family, no second chart implementation here.
_FigureSpec = (
    VisualSpec
    | SequenceSpec
    | SankeySpec
    | GeoMapSpec
    | ChoroplethSpec
    | IsometricSpec
    | EChartsFigureSpec
    | MermaidFigureSpec
    | BarSpec
    | RadarSpec
    | PieSpec
    | TimelineSpec
    | HeatmapSpec
    | LayeredSpec
    | ExplorerSpec
)

# Host-project root + doc-governance paths, resolved via engine_config (env var > engine.config.json
# > auto-detected git root > this engine's own directory as a last-resort default) rather than a
# fixed Path(__file__).resolve().parents[2] — see ../../CONFIGURATION.md. _REPO_ROOT is kept as a
# module-level name (read at import time, matching the original pattern) since callers below treat
# it as a constant within one process; re-import or restart to pick up a changed host project.
_REPO_ROOT = engine_config.host_root()
_DOC_MANIFEST_PATH = engine_config.doc_manifest_path()
_FIGURE_DIRECTIVE_RE = re.compile(r"<!--\s*figure:([A-Za-z0-9_-]+)\s*-->")


class BuildBlockedError(RuntimeError):
    """Raised when a build is blocked by the leak-gate (public doc must never be written)."""


def _canonicalize_inside_repo(path: Path, *, root: Path = _REPO_ROOT) -> Path:
    """Resolve ``path`` to an absolute, symlink-free path and assert it stays inside ``root``.

    Fail-closed (RULEBOOK L12 isolation): a path that escapes the repo root (via ``..`` or a
    symlink) raises rather than silently being read/written.
    """
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BuildBlockedError(
            f"path {path} resolves outside the repo root ({root}): {resolved}"
        ) from exc
    return resolved


def _read_markdown(md_path: Path) -> str:
    return md_path.read_text(encoding="utf-8")


def _strip_front_matter(md: str) -> str:
    """Remove the YAML front-matter block (already parsed into a DocHeader) from the body."""
    match = re.match(r"^\s*---\s*\n.*?\n---\s*\n?", md, re.DOTALL)
    if match is None:
        return md
    return md[match.end() :]


# The kinds that SHARE ``VisualSpec`` — one parser, four renderers. Kept as its own map because
# that is exactly what distinguishes them from the typed kinds below; ``_FIGURE_KINDS`` (bottom of
# this module) is built FROM it, so this is a source, not a second copy.
_FIGURE_RENDERERS: dict[str, Callable[[VisualSpec], str]] = {
    "flowchart": visual.render,
    "state": diagram_graphs.render_state_diagram,
    "system_map": diagram_graphs.render_system_map,
    "dependency_graph": diagram_graphs.render_dependency_graph,
}


@dataclass(frozen=True)
class _Rendered:
    """A rendered figure plus everything that explains it (the document prints it; the blueprint carries it)."""

    svg: str
    how_to_read: str = ""
    key: tuple[KeyItem, ...] = ()
    record: Mapping[str, Any] = field(default_factory=dict)
    # (mark, value, what it tells you) rows for the "what each mark shows" table; empty when the chart has too many.
    marks: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class _FigureKind:
    """One figure ``kind``: how to parse its sidecar entry, and how to render the result.

    `P8-090`: parsing and rendering used to be two independent hand-maintained dispatch chains —
    a ``kind == "..."`` chain in ``_load_sibling_figure`` and an ``isinstance(spec, ...Spec)``
    chain in ``_render_markdown_body`` — with no test asserting they stayed in bijection and a
    ``visual.render`` fallback that turned any disagreement into a silently-wrong FLOWCHART.
    Adding a kind is now ONE edit: a row in ``_FIGURE_KINDS``.
    """

    load: Callable[[dict[str, Any]], _FigureSpec]
    render: Callable[[Any], str]
    # **Does this kind put NUMBERS in front of a reader?** (`OG-63`.) Declared per kind rather
    # than inferred, because no property of the spec class answers it: ``VisualSpec`` carries a
    # ``data_sources`` field and is shared by flowchart/state/system_map/dependency_graph, none of
    # which renders a quantity — so "the dataclass has the field" would demand a source for every
    # flowchart in the corpus. The question is about what the figure SHOWS, and the only honest
    # place to answer it is where the kind is declared, which keeps `P8-090`'s one-edit property:
    # adding a kind still means adding one row, and that row now has to state this.
    carries_data: bool = False
    # **Optional richer renderer.** ``render`` stays the one thing every kind has (and what the dispatch tests
    # pin); ``present`` is for kinds whose renderer yields more than a picture — the numbered key of a
    # diagram, the per-mark record of an engine chart — and for kinds that need the building document's
    # classification. Taking it from the kind's own row (not an ``isinstance`` ladder) keeps `P8-090`'s
    # one-edit property: a kind is still ONE row.
    present: Callable[[Any, Tier], _Rendered] | None = None
    # The plain-language reading guide printed under every figure of this kind, for kinds whose ``present`` hook does
    # not compute a more specific one. A figure with numbers or marks and no explanation of them is a puzzle, not a view.
    guide: str = ""


# --- inline Markdown -------------------------------------------------------------------------
#
# Order matters and is the whole correctness argument here. Code spans are lifted out FIRST, into
# placeholders, so that a `**` or `_` inside `` `code` `` is never treated as emphasis. Only then is
# the text HTML-escaped, and only then are emphasis and links applied to the already-escaped text.
# Doing it the other way round (markdown first, escape second) would escape the tags we just
# generated; escaping last would let a document inject markup. The placeholder is a private-use
# codepoint that cannot appear in a UTF-8 source document by accident.
_CODE_SLOT = "\ue000"

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.DOTALL)
_ITALIC_RE = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])")
_UNDERSCORE_ITALIC_RE = re.compile(r"(?<![\w_])_(?=\S)([^_]+?)(?<=\S)_(?![\w_])")


# `[[fig:ID]]` in prose becomes a link to that figure ("Fig. 3"). The table is bound only while a document body
# renders, so a direct caller of ``_render_inline`` (a finance report, a test) sees the text unchanged.
_FIG_REF_RE = re.compile(r"\[\[fig:([A-Za-z0-9_-]+)\]\]")


@dataclass
class _RefTable:
    """The figures a document body can point at, and which of them its prose actually points at."""

    ids: dict[str, tuple[str, int]]
    section: str = ""
    used: list[tuple[str, str]] = field(default_factory=list)  # (section dom id, figure id), in text order


_FIG_REFS: contextvars.ContextVar[_RefTable | None] = contextvars.ContextVar("docgen_fig_refs", default=None)


def _fig_ref(match: re.Match[str]) -> str:
    table = _FIG_REFS.get()
    if table is None:
        return match.group(0)
    fid = match.group(1)
    hit = table.ids.get(fid)
    if hit is None:
        known = ", ".join(sorted(table.ids)[:8]) or "(none)"
        raise BuildBlockedError(
            f"the text points at [[fig:{fid}]] but this document places no figure with that id "
            f"(placed: {known}). A dangling figure reference is refused, not rendered as plain text."
        )
    dom, number = hit
    table.used.append((table.section, fid))
    return f'<a class="fig-ref" href="#{dom}" data-ref="{dom}">Fig. {number}</a>'


def _safe_href(url: str) -> str:
    """Allow only hrefs that cannot execute. Anything else renders as plain text, not a link.

    `javascript:`, `data:` and `vbscript:` are the executable schemes; a document is untrusted
    input to this renderer, so the link gate is an allow-list, never a block-list.
    """
    candidate = url.strip()
    lowered = candidate.lower().replace("\t", "").replace("\n", "")
    if lowered.startswith(("http://", "https://", "mailto:", "#", "/", "./", "../")):
        return candidate
    if ":" not in lowered.split("/")[0]:
        return candidate
    return ""


def _render_inline(text: str) -> str:
    """Render inline Markdown (code, bold, italic, links) to HTML, escaping everything else."""
    spans: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return f"{_CODE_SLOT}{len(spans) - 1}{_CODE_SLOT}"

    # Double-backtick first so ``a `b` c`` keeps its inner backticks.
    text = re.sub(r"``(.+?)``", _stash, text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", _stash, text)

    out = escape(text)

    def _link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        href = _safe_href(unescape(url))
        if not href:
            return label
        return f'<a class="t-link" href="{escape(href)}">{label}</a>'

    out = _LINK_RE.sub(_link, out)
    out = _BOLD_RE.sub(r"<strong>\1</strong>", out)
    out = _ITALIC_RE.sub(r"<em>\1</em>", out)
    out = _UNDERSCORE_ITALIC_RE.sub(r"<em>\1</em>", out)

    out = _FIG_REF_RE.sub(_fig_ref, out)

    def _restore(match: re.Match[str]) -> str:
        return f"<code class=\"t-code\">{escape(spans[int(match.group(1))])}</code>"

    return re.sub(f"{_CODE_SLOT}(\\d+){_CODE_SLOT}", _restore, out)


@dataclass
class _OutlineSection:
    """One ``##`` section of a document body: its heading, the figures placed in it, and its Markdown source."""

    title: str
    figure_ids: list[str] = field(default_factory=list)
    md: list[str] = field(default_factory=list)


@dataclass
class _DocStructure:
    """What a render learned about the document, collected for the blueprint JSON (machines read this, not HTML)."""

    sections: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    refs: list[dict[str, Any]] = field(default_factory=list)


def _scan_outline(md_body: str, known: set[str]) -> tuple[list[_OutlineSection], dict[str, int]]:
    """Walk a body the way ``_render_markdown_body`` does and return its sections and its figure numbers.

    Figures are numbered ``Fig. 1..N`` in the order they are PLACED, and the numbers have to be known before
    the first one renders — a section's chip row, a figure's caption and a ``[[fig:ID]]`` in an earlier
    paragraph all print them. Fenced code is skipped exactly as the renderer skips it, so a directive quoted
    inside a code block is not a placement. A figure placed twice is refused: it would print one DOM id twice.
    """
    sections = [_OutlineSection("overview")]
    numbers: dict[str, int] = {}
    dom_ids: dict[str, str] = {}
    fence: str | None = None
    for raw in md_body.splitlines():
        stripped = raw.strip()
        if fence is not None:
            sections[-1].md.append(raw)
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            sections[-1].md.append(raw)
            continue
        if raw.startswith("# "):
            continue
        if raw.startswith("## "):
            sections.append(_OutlineSection(raw[3:].strip()))
            continue
        sections[-1].md.append(raw)
        placed = _FIGURE_DIRECTIVE_RE.match(stripped)
        if placed and placed.group(1) in known:
            fid = placed.group(1)
            if fid in numbers:
                raise BuildBlockedError(
                    f"figure '{fid}' is placed twice in one document; each figure is one numbered, "
                    "linkable object — place it once and point at it with [[fig:" + fid + "]]"
                )
            dom = fig_dom_id(fid)
            if dom in dom_ids:
                raise BuildBlockedError(
                    f"figures '{dom_ids[dom]}' and '{fid}' both become the DOM id '{dom}' (ids are lower-cased and "
                    "every run of other characters becomes '-'); two figures cannot share one anchor and one SVG scope — "
                    "rename one of them"
                )
            dom_ids[dom] = fid
            numbers[fid] = len(numbers) + 1
            sections[-1].figure_ids.append(fid)
    return sections, numbers


def _render_markdown_body(
    md_body: str,
    *,
    figures: dict[str, tuple[str, _FigureSpec]],
    doc_tier: Tier = Tier.PUBLIC,
    structure: _DocStructure | None = None,
) -> str:
    """Render a constrained Markdown subset (headings, paragraphs, tables, figure directives) to HTML.

    This is intentionally a small, dependency-free renderer (no third-party ``markdown`` package
    is installed in this project's venv) covering exactly what ``sample.md``-style documents need:
    ``#``/``##`` headings become sectioned blocks via ``components.section``, blank-line-separated
    paragraphs, GitHub-style pipe tables via ``components.data_table``, and a
    ``<!-- figure:ID -->`` directive that renders the matching spec via the renderer named by its
    ``kind`` (``_FIGURE_RENDERERS`` — flowchart/state/system_map/dependency_graph all share
    ``VisualSpec``'s node/edge shape, just render as a different convention; ``sequence``,
    ``sankey``, ``geo_map`` and ``isometric3d`` each own a distinct spec shape and render via
    ``isinstance`` narrowing so mypy narrows the type) wrapped in ``components.figure``.
    Data-series charts use ``kind: "echarts"`` — a visual-engine job packet in the sidecar,
    rendered via ``echarts_bridge`` (the canonical chart engine; wired 2026-08-10, closing
    this docstring's old "NOT yet wired" note). docgen's native chart renderers in
    ``charts.py`` remain available to direct callers (e.g. ``tools/finance_report``) but the
    generator routes document data charts through the engine. Unrecognized
    constructs pass through as escaped paragraph text (fail-closed toward safety: never emit raw
    unescaped user Markdown as HTML).

    Every figure is a numbered, anchored object (``Fig. N`` / ``fig-<slug>``), every section a link target
    (``sec-<slug>``), and the two point at each other: a section prints a chip per figure it holds, a figure
    links back to its section, and ``[[fig:ID]]`` in prose becomes a link to the figure. ``doc_tier`` is the
    building document's classification (an engine chart may not outrank it); ``structure``, when given, is
    filled with the sections, figures and references for the blueprint JSON.
    """
    lines = md_body.splitlines()
    blocks: list[str] = []
    current_section: list[str] = []
    current_eyebrow = "overview"
    i = 0
    outline, numbers = _scan_outline(md_body, set(figures))
    taken_ids: set[str] = set()
    section_ids = [section_dom_id(sec.title, taken_ids) for sec in outline]
    section_index = 0
    table = _RefTable({fid: (fig_dom_id(fid), n) for fid, n in numbers.items()}, section=section_ids[0])

    def _flush_section() -> None:
        if current_section:
            blocks.append(
                components.section(
                    current_eyebrow,
                    "\n".join(current_section),
                    eyebrow_renderer=_render_inline,
                    section_id=section_ids[section_index],
                    figures=[
                        (fig_dom_id(fid), numbers[fid], figures[fid][1].caption)
                        for fid in outline[section_index].figure_ids
                    ],
                )
            )
            current_section.clear()

    ref_token = _FIG_REFS.set(table)
    try:
        while i < len(lines):
            line = lines[i]

            if line.startswith("# "):
                # Document title is handled by the masthead; skip the H1 line itself.
                i += 1
                continue

            if line.startswith("## "):
                _flush_section()
                current_eyebrow = line[3:].strip()
                section_index += 1
                table.section = section_ids[section_index]
                i += 1
                continue

            fig_match = _FIGURE_DIRECTIVE_RE.match(line.strip())
            if fig_match:
                fig_id = fig_match.group(1)
                entry = figures.get(fig_id)
                if entry is not None:
                    _kind, spec = entry
                    # The document numbers its own figures now. A caption that still says "Fig. 9 - ..." would print
                    # a second, contradicting number inside the picture (native renderers draw the caption in the SVG).
                    caption = getattr(spec, "caption", None) if is_dataclass(spec) else None
                    if isinstance(caption, str) and caption:
                        plain_caption = strip_fig_prefix(caption)
                        if plain_caption != caption:
                            spec = replace(spec, caption=plain_caption)
                    # ONE dispatch table, shared with ``_load_sibling_figure`` (`P8-090`). This used to
                    # be a second, hand-maintained ``isinstance`` chain running parallel to the parse
                    # chain's ``kind ==`` chain, with nothing asserting the two stayed in bijection —
                    # and its final ``else`` fell back to ``visual.render``, so a kind present in one
                    # chain and absent from the other rendered as a FLOWCHART rather than failing.
                    # Now both chains read ``_FIGURE_KINDS``, so they cannot disagree.
                    handler = _FIGURE_KINDS.get(_kind)
                    if handler is None:
                        raise BuildBlockedError(
                            f"figure '{fig_id}' carries kind={_kind!r}, which this engine cannot "
                            f"render. Known kinds: {', '.join(sorted(_FIGURE_KINDS))}. Refusing to "
                            "guess a renderer."
                        )
                    shown = (
                        handler.present(spec, doc_tier)
                        if handler.present is not None
                        else _Rendered(svg=handler.render(spec))
                    )
                    # Not every spec type carries a ``legend`` field (SankeySpec/GeoMapSpec do
                    # not); guard with getattr so the legend row is simply empty for those.
                    legend_html = "".join(
                        f'<span class="figure-legend-item">{escape(entry_.label)}</span>'
                        for entry_ in getattr(spec, "legend", [])
                    )
                    if '<g class="legend"' in shown.svg:
                        # The figure draws its own key; a second, unstyled copy under the caption read as a stray line.
                        legend_html = ""
                    # EChartsFigureSpec carries its interpretive fields inside the nested chart-engine
                    # job packet (that engine's own mandatory `reader_question` + advisory
                    # `text_summary`, Gate G7) rather than as direct attributes like every other spec
                    # here — surface them the same way so a chart-engine figure is just as
                    # interpretable in the rendered document as a native docgen figure.
                    if isinstance(spec, EChartsFigureSpec):
                        reader_question = str(spec.job.get("reader_question", ""))
                        insight = str(spec.job.get("text_summary", ""))
                    else:
                        reader_question = getattr(spec, "reader_question", "")
                        insight = getattr(spec, "insight", "")
                    current_section.append(
                        components.figure(
                            shown.svg, spec.caption, legend_html,
                            reader_question=reader_question, insight=insight,
                            fig_id=fig_dom_id(fig_id), number=numbers[fig_id], kind=_kind,
                            section_id=section_ids[section_index], section_title=current_eyebrow,
                            how_to_read=shown.how_to_read or handler.guide, key=list(shown.key),
                            marks=list(shown.marks),
                        )
                    )
                    if structure is not None:
                        structure.figures.append(
                            {
                                "id": fig_id,
                                "dom_id": fig_dom_id(fig_id),
                                "number": numbers[fig_id],
                                "kind": _kind,
                                "caption": spec.caption,
                                "section": section_ids[section_index],
                                "section_title": current_eyebrow,
                                "reader_question": reader_question,
                                "insight": insight,
                                "how_to_read": shown.how_to_read or handler.guide,
                                "key": [dict(item) for item in shown.key],
                                "data_sources": [asdict(src) for src in getattr(spec, "data_sources", [])],
                                "record": dict(shown.record),
                            }
                        )
                i += 1
                continue

            if (
                line.strip().startswith("|")
                and i + 1 < len(lines)
                and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1].strip())
            ):
                table_lines = [line]
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    table_lines.append(lines[j])
                    j += 1
                headers, rows = _parse_pipe_table(table_lines)
                current_section.append(
                    components.data_table(headers, rows, cell_renderer=_render_inline)
                )
                i = j
                continue

            stripped = line.strip()

            # Fenced code. Everything inside is literal: no inline rendering, no figure directives.
            if stripped.startswith(("```", "~~~")):
                fence = stripped[:3]
                lang = stripped[3:].strip()
                body: list[str] = []
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith(fence):
                    body.append(lines[j])
                    j += 1
                # An unterminated fence consumes to end-of-document rather than spilling raw
                # backticks into the prose, which is what the old renderer did.
                lang_attr = f' data-lang="{escape(lang)}"' if lang else ""
                current_section.append(
                    f'<pre class="t-pre"{lang_attr}><code>{escape(chr(10).join(body))}</code></pre>'
                )
                i = j + 1
                continue

            # Thematic break. Guarded against a `---` that is really a setext underline or a stray
            # front-matter delimiter by requiring the line to be nothing but rule characters.
            if len(stripped) >= 3 and set(stripped) in ({"-"}, {"*"}, {"_"}):
                current_section.append('<hr class="t-rule" />')
                i += 1
                continue

            # h3-h6. h1 is the masthead and h2 opens a section, both handled above.
            heading = re.match(r"^(#{3,6})\s+(.*)$", stripped)
            if heading:
                level = len(heading.group(1))
                tag = f"h{level}"
                cls = "t-h3" if level == 3 else "t-h4"
                current_section.append(
                    f'<{tag} class="{cls}">{_render_inline(heading.group(2).strip())}</{tag}>'
                )
                i += 1
                continue

            # Blockquote: consume the whole run of `>` lines as one quote.
            if stripped.startswith(">"):
                quoted: list[str] = []
                j = i
                while j < len(lines) and lines[j].strip().startswith(">"):
                    quoted.append(re.sub(r"^\s*>\s?", "", lines[j]))
                    j += 1
                inner = " ".join(q.strip() for q in quoted if q.strip())
                current_section.append(
                    f'<blockquote class="t-quote"><p class="t-body">{_render_inline(inner)}</p></blockquote>'
                )
                i = j
                continue

            # Lists. A run of sibling items becomes one <ul>/<ol>; a hard-wrapped continuation line
            # (indented, not itself a marker) folds into the item above it rather than starting a new
            # one, which is how the same paragraph rule applies inside a list.
            list_item = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
            if list_item:
                ordered = not list_item.group(2) in ("-", "*", "+")
                items: list[str] = []
                j = i
                while j < len(lines):
                    candidate = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", lines[j])
                    if candidate:
                        if (not candidate.group(2) in ("-", "*", "+")) != ordered:
                            break
                        items.append(candidate.group(3).strip())
                        j += 1
                        continue
                    if lines[j].strip() and lines[j][:1].isspace() and items:
                        items[-1] = f"{items[-1]} {lines[j].strip()}"
                        j += 1
                        continue
                    break
                tag = "ol" if ordered else "ul"
                rendered = "".join(f"<li>{_render_inline(item)}</li>" for item in items)
                current_section.append(f'<{tag} class="t-list">{rendered}</{tag}>')
                i = j
                continue

            # Paragraph. Consecutive non-blank lines are ONE paragraph joined with a space — Markdown's
            # actual rule. Emitting one <p> per source line (what this renderer used to do) turns every
            # hard-wrapped document into a stack of one-line paragraphs and breaks reflow mid-sentence.
            if stripped:
                para: list[str] = []
                j = i
                while j < len(lines):
                    nxt = lines[j]
                    nxt_s = nxt.strip()
                    if not nxt_s:
                        break
                    # A line that opens any other block ends the paragraph.
                    if (
                        nxt_s.startswith(("#", ">", "```", "~~~", "<!-- figure:"))
                        or (nxt_s.startswith("|") and j + 1 < len(lines)
                            and re.match(r"^\|[\s:|-]+\|\s*$", lines[j + 1].strip()))
                        or re.match(r"^(\s*)([-*+]|\d+[.)])\s+", nxt)
                        or (len(nxt_s) >= 3 and set(nxt_s) in ({"-"}, {"*"}, {"_"}))
                    ):
                        break
                    para.append(nxt_s)
                    j += 1
                current_section.append(f'<p class="t-body">{_render_inline(" ".join(para))}</p>')
                i = j
                continue
            i += 1

        _flush_section()
    finally:
        _FIG_REFS.reset(ref_token)
    if structure is not None:
        for sec_id, sec in zip(section_ids, outline, strict=True):
            body_md = "\n".join(sec.md).strip()
            if body_md or sec.figure_ids:
                structure.sections.append(
                    {
                        "id": sec_id,
                        "title": sec.title,
                        "figures": [fig_dom_id(fid) for fid in sec.figure_ids],
                        "markdown": body_md,
                    }
                )
        structure.refs.extend(
            {"from_section": sec_id, "figure": fig_dom_id(fid), "number": numbers[fid]}
            for sec_id, fid in table.used
        )
    return "\n".join(blocks)


def _parse_pipe_table(table_lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Split an already-isolated table block into ``(headers, rows)``.

    **Delegates the cell dialect to the one reader** (`OG-36`). This used to protect escaped pipes
    with a ``\x00`` sentinel — correct about ``\\|``, and still wrong about edge cells, because
    ``str.strip("|")`` eats an unbounded run of pipes and so deleted an intentionally empty first
    or last column. `tools/lib/md_table.py` removes exactly one pipe from each end.

    The row slice stays ``[2:]`` rather than moving to ``md_table.parse_block``: this caller has
    already established that line 1 is the delimiter row when it isolated the block, and a reader
    that re-derives that would silently accept a two-line "table" the caller never meant to pass.
    """
    headers = md_table.split_row(table_lines[0])
    rows = [md_table.split_row(line) for line in table_lines[2:] if line.strip()]
    return headers, rows


def _content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# The L7 generated-file marker. **A constant because a second reader exists.**
# `rendered-output` identifies a docgen-built artifact by this text, and carried its own
# hand-copied literal — two spellings of one fact, with nothing coupling them (`OG-114`). Measured:
# rewriting the stamp here left that guard unable to recognise any built document, and its answer
# degraded to a SKIP that a default health run treats as green, so a planted defect in both
# tracked artifacts produced no finding at all.
GENERATED_MARKER = "generated-by docgen"


def _stamp_generated(html_doc: str) -> str:
    """Append the L7 generated-file guard comment with the content hash of everything BEFORE it."""
    digest = _content_sha256(html_doc.encode("utf-8"))
    return f"{html_doc}\n<!-- {GENERATED_MARKER} · content-sha256:{digest} -->\n"


_LOCALE_FIELD_RE = re.compile(r"^\s*locale\s*:\s*(?P<val>[^\r\n#]+)", re.MULTILINE)


def _extract_locale(md: str) -> str | None:
    """Read an OPTIONAL ``locale:`` front-matter field (i18n scaffold hook, ENGINE_PLAN §4b).

    Returns the raw declared locale string, or ``None`` when the document declares none.
    ``DocHeader`` is a frozen contract shared across the engine, so the scaffold reads this
    optional field directly from the raw markdown rather than widening that dataclass — a
    document without a ``locale:`` field is unaffected (``<html lang>`` stays ``en``, so
    existing builds remain byte-identical).
    """
    match = _LOCALE_FIELD_RE.search(md)
    if match is None:
        return None
    return match.group("val").strip().strip("'\"") or None


def _render_html(
    header: DocHeader, body_html: str, *, lang: str = i18n.DEFAULT_LOCALE, index: dict[str, Any] | None = None
) -> str:
    """Assemble the full self-contained HTML document: inline CSS + masthead + body + stamp.

    ``lang`` is the resolved ``<html lang="…">`` value (see ``i18n.resolve_lang``); it defaults
    to English so callers that do not opt into the i18n scaffold get identical output.
    """
    css = tokens.build_css()
    masthead_html = components.masthead(header)
    verified = components.verified_stamp(header.id)
    title = escape(header.title)
    lang_attr = escape(lang, quote=True)
    # One copy of the figure runtime per document, and only when a figure is present: tooltips, click-to-pin,
    # keyboard focus and adjacency highlighting read the attributes the figures already carry. Nothing is loaded,
    # evaluated or sent anywhere; a document without figures stays byte-identical.
    runtime = f"<script>\n{runtime_js()}\n</script>\n" if 'data-fig="' in body_html else ""
    # The explorer's own runtime (zoom, labels, panel, reader), inlined only when a document holds an explorer.
    if "data-ve-explorer" in body_html:
        runtime += f"<script>\n{explorer_runtime_js()}\n</script>\n"
    # The document index (doc_index.py): what each number in the page IS. Data, never code: the runtime parses it and writes
    # card text with textContent. Present only when there is something to point at.
    index_block = (
        f'<script type="application/json" id="ve-doc-index">{doc_index.to_script_json(index)}</script>\n'
        if index and 'data-ref="' in body_html
        else ""
    )
    doc = f"""\
<!doctype html>
<html lang="{lang_attr}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
</style>
</head>
<!-- No data-theme here on purpose. tokens.py declares the palette on `:root, [data-theme="dark"]`,
     so :root already yields the dark theme with no attribute and no JS — while components.py's
     toggle sets data-theme on <html>. A hardcoded `data-theme="dark"` on <body> re-declared the
     dark variables on a DESCENDANT of the element the toggle writes to, so body's own values won
     the cascade for the whole document and the light theme was unreachable: the toggle flipped
     the attribute, persisted it, relabelled itself, and changed nothing visible. -->
<body>
<div class="doc-root">
{masthead_html}
<main>
{body_html}
</main>
{verified}
</div>
{index_block}{runtime}</body>
</html>
"""
    return _stamp_generated(doc)


def _findings_to_json(gate: GateResult) -> dict[str, object]:
    return {
        "gate": gate.gate,
        "ok": gate.ok,
        "findings": [
            {
                "gate": f.gate,
                "message": f.message,
                "severity": f.severity.value,
                "blocking": f.blocking,
                "evidence": f.evidence,
            }
            for f in gate.findings
        ],
    }


def _render_json(header: DocHeader, gate: GateResult) -> str:
    payload = {
        "header": {
            "id": header.id,
            "classification": header.classification.value,
            "title": header.title,
            "audience": header.audience,
            "owner": header.owner,
            "status": header.status,
            "export_allowed": header.export_allowed,
            "surface": header.surface.value,
            "last_reviewed": header.last_reviewed,
            "variants": header.variants,
        },
        "gate": _findings_to_json(gate),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


BLUEPRINT_SCHEMA = "ultimate-engine/blueprint/1"


def _render_blueprint(header: DocHeader, structure: _DocStructure) -> str:
    """The machine-readable twin of the rendered document (``<stem>.blueprint.json``, AI-only).

    The HTML is for people: it carries pictures, tooltips and layout. This file is for a model: the same
    document as data — every section with its Markdown source, every figure numbered and explained (what it
    answers, how to read it, what each numbered circle means, and for an engine chart every mark with its value and
    neighbours), and the links that join text to pictures. It is generated from the SAME render pass as the HTML,
    so the two cannot describe different documents, and it passes the same leak-gate before it is written.
    """
    links: list[dict[str, str]] = []
    for sec in structure.sections:
        for dom in sec["figures"]:
            links.append({"from": sec["id"], "to": dom, "kind": "contains"})
            links.append({"from": dom, "to": sec["id"], "kind": "described-by"})
    for ref in structure.refs:
        links.append({"from": ref["from_section"], "to": ref["figure"], "kind": "references"})
    payload = {
        "schema": BLUEPRINT_SCHEMA,
        "purpose": (
            "Machine-readable twin of the rendered document. Sections carry their Markdown source; figures carry "
            "the question they answer, how to read them, what every numbered circle means and (engine charts) "
            "every mark with its value and connections; links join text to pictures. Read this instead of the HTML."
        ),
        "document": {
            "id": header.id,
            "title": header.title,
            "classification": header.classification.value,
            "audience": header.audience,
            "owner": header.owner,
            "status": header.status,
            "surface": header.surface.value,
            "last_reviewed": header.last_reviewed,
        },
        "sections": structure.sections,
        "figures": structure.figures,
        "references": structure.refs,
        "links": links,
        "counts": {
            "sections": len(structure.sections),
            "figures": len(structure.figures),
            "references": len(structure.refs),
            "links": len(links),
        },
    }
    return json.dumps(payload, indent=2)


def _try_render_pdf(html_doc: str) -> bytes | None:
    """Attempt PDF rendering via weasyprint. Returns None (never raises) if unavailable."""
    try:
        import weasyprint  # type: ignore[import-untyped,import-not-found,unused-ignore]  # no stubs/py.typed upstream; absent in some envs
    except ImportError:
        return None
    pdf_bytes: bytes = weasyprint.HTML(string=html_doc).write_pdf()
    return pdf_bytes


_CONFIDENTIAL_ROOT = engine_config.confidential_dir()


def build(
    md_path: Path,
    *,
    formats: tuple[str, ...] = ("html",),
    out_dir: Path | None = None,
    local_preview: bool = False,
) -> BuildResult:
    """Build ``md_path`` into the requested ``formats`` (subset of ``html``/``json``/``pdf``).

    Pipeline (RULEBOOK L7/L13/L14):
    1. Canonicalize ``md_path``; assert it resolves inside the repo (L12).
    2. Parse + validate the document header.
    3. Render the Markdown body to a self-contained HTML document.
    4. Re-run ``export_sanitizer.run_gates`` on the FINAL RENDERED bytes of each requested
       output channel (not just the source Markdown) — a public document that fails the
       gate is never written to disk (``BuildResult.ok`` is False and no ``outputs`` entry
       is produced for the blocked format).
    5. Write the passing outputs; PDF degrades to a recorded skip if weasyprint is absent.

    ``local_preview=True`` (RULEBOOK L3/DETECTOR_DOC_SPEC §4) lets a CONFIDENTIAL/SECRET
    document render for internal/NDA'd-partner review WITHOUT being export-eligible — Gate 1
    is relaxed (see ``export_sanitizer.gate_tier``) but every other gate (secret-value, PII,
    manifest-drift, variant-overlap) still runs and still blocks. This function additionally
    enforces the ONE safety backstop the gate itself cannot: a non-public document may only
    be written under the git-ignored ``docs/confidential/`` tree — fail-closed
    (``BuildBlockedError``) if ``local_preview`` is requested for a non-public document whose
    resolved output directory falls outside it, so a preview build can never leak a
    confidential/secret render into a public/committed path by accident. ``local_preview``
    has no effect on a ``classification: public`` document (Gate 1 already passes it).

    Deterministic: no wall-clock timestamps are embedded in the hashed HTML content (the
    content-sha256 stamp covers only the document body preceding it).
    """
    resolved_md = _canonicalize_inside_repo(md_path)
    md_text = _read_markdown(resolved_md)
    header = parse_header(md_text)
    # ``source=`` is what turns on the present-but-wrong-typed field checks (`P8-094`); the build
    # gate has the raw Markdown in hand, so there is no reason for it to validate blind.
    header_findings = validate_header(header, source=md_text)

    manifest_rows = doc_manifest.read_manifest(_DOC_MANIFEST_PATH)

    figures = _load_sibling_figure(resolved_md)
    body_md = _strip_front_matter(md_text)
    # Always collected: the page's reference cards (doc_index) read it as well as the blueprint JSON does.
    structure = _DocStructure()
    body_html = _render_markdown_body(
        body_md, figures=figures, doc_tier=header.classification, structure=structure
    )
    lang = i18n.resolve_lang(_extract_locale(md_text))
    html_doc = _render_html(
        header, body_html, lang=lang, index=doc_index.build(structure.sections, structure.figures)
    )

    out_directory = out_dir if out_dir is not None else resolved_md.parent
    out_directory = _canonicalize_inside_repo(out_directory)

    if local_preview and header.classification is not Tier.PUBLIC:
        try:
            out_directory.relative_to(_CONFIDENTIAL_ROOT)
        except ValueError as exc:
            raise BuildBlockedError(
                f"local_preview requested for a '{header.classification.value}' document "
                f"but out_dir {out_directory} is not under {_CONFIDENTIAL_ROOT} — refusing "
                "to risk a non-public render outside the git-ignored confidential tree"
            ) from exc

    outputs: dict[str, Path] = {}
    # Figure provenance joins the header findings BEFORE any format is written, so a document with
    # an unsourced number produces no output at all rather than one output per format (`OG-63`).
    pre_format_gate = GateResult(
        gate="build",
        findings=[*header_findings, *check_figure_provenance(figures)],
    )
    final_gate = GateResult(gate="build", findings=list(pre_format_gate.findings))

    # ⛔ **A blocked build must not leave an artifact behind.**
    #
    # Every write below used to be guarded by its own format's `run_gates` result alone, and
    # `run_gates` does not run `validate_header` or the figure checks — those are computed here,
    # merged into `final_gate`, and reported. So `docgen build` printed `BLOCKED`, exited
    # non-zero, and **wrote the HTML anyway**. Measured 2026-08-24 on a document with a blocking
    # `identity` finding: `docgen build: BLOCKED` on stderr, `probe_hdr.html` on disk.
    #
    # That is worse than either honest outcome. A reader who sees the file assumes it passed, and
    # `OG-63` would have inherited exactly the defect it exists to close: RULEBOOK L16 says an
    # unsourced number means *the figure does not render*, not that it renders with a complaint.
    #
    # Fixed at the root rather than for the new gate: this guards the header findings that were
    # already being ignored, and every future pre-format finding, not just provenance
    # (`docs/process/RULES.md` Rule 1).
    may_write = pre_format_gate.ok

    for fmt in formats:
        if fmt == "html":
            gate = export_sanitizer.run_gates(
                html_doc, header, manifest_rows=manifest_rows, local_preview=local_preview
            )
            final_gate = final_gate.merge(gate)
            if gate.ok and may_write:
                out_path = out_directory / f"{resolved_md.stem}.html"
                out_path.write_text(html_doc, encoding="utf-8")
                outputs["html"] = out_path
        elif fmt == "json":
            json_doc = _render_json(header, final_gate)
            gate = export_sanitizer.run_gates(
                json_doc, header, manifest_rows=manifest_rows, local_preview=local_preview
            )
            final_gate = final_gate.merge(gate)
            if gate.ok and may_write:
                out_path = out_directory / f"{resolved_md.stem}.json"
                out_path.write_text(json_doc, encoding="utf-8")
                outputs["json"] = out_path
        elif fmt == "blueprint" and structure is not None:
            blueprint_doc = _render_blueprint(header, structure)
            gate = export_sanitizer.run_gates(
                blueprint_doc, header, manifest_rows=manifest_rows, local_preview=local_preview
            )
            final_gate = final_gate.merge(gate)
            if gate.ok and may_write:
                out_path = out_directory / f"{resolved_md.stem}.blueprint.json"
                out_path.write_text(blueprint_doc, encoding="utf-8")
                outputs["blueprint"] = out_path
        elif fmt == "pdf":
            gate = export_sanitizer.run_gates(
                html_doc, header, manifest_rows=manifest_rows, local_preview=local_preview
            )
            final_gate = final_gate.merge(gate)
            if gate.ok and may_write:
                pdf_bytes = _try_render_pdf(html_doc)
                if pdf_bytes is None:
                    # BLOCKING, and deliberately so. `pdf` reaches here only because a caller asked
                    # for it by name — the default is `("html",)`. Recording "skipped" as INFO meant
                    # `--formats pdf` printed an easily-missed line, exited 0, and produced no file:
                    # the engine reported success for an artifact it had not made. Note the
                    # contrast one branch below, where an unknown format is already HIGH+blocking —
                    # so asking for `pdff` failed loudly while asking for `pdf` failed silently.
                    final_gate.findings.append(
                        Finding(
                            gate="pdf",
                            message=(
                                "pdf requested but weasyprint is not installed, so no PDF was "
                                "written. Install it (`python3 -m pip install weasyprint`) or drop "
                                "`pdf` from --formats; the engine will not report success for a "
                                "file it did not produce."
                            ),
                            severity=Severity.HIGH,
                            blocking=True,
                        )
                    )
                else:
                    out_path = out_directory / f"{resolved_md.stem}.pdf"
                    out_path.write_bytes(pdf_bytes)
                    outputs["pdf"] = out_path
        else:
            final_gate.findings.append(
                Finding(
                    gate="build",
                    message=f"unknown format requested: {fmt!r}",
                    severity=Severity.HIGH,
                    blocking=True,
                )
            )

    # Audience views: purely additive. A document with zero body audience markers
    # takes zero extra work here -- `build_and_gate_views` returns an empty, clean result
    # immediately (see `views.has_audience_markers`), so this cannot change behaviour for
    # any document that predates audience views. A document that DOES declare markers gets one
    # generated `<stem>.<audience>.md` sibling per audience, each independently gated by
    # the full `export_sanitizer` pipeline (gate 9 armed against its own excluded blocks --
    # see `views.py`'s module docstring "Gate-9 wiring") and written only if that gate is
    # clean and `may_write` -- the same `if gate.ok and may_write` discipline the html/json/
    # pdf loop above already applies. Folded into `final_gate` so `BuildResult.ok` reflects
    # a blocked view the same way it already reflects a blocked html/json/pdf output.
    views_result = views.build_and_gate_views(
        source_stem=resolved_md.stem,
        md_text=md_text,
        header=header,
        out_directory=out_directory,
        manifest_rows=manifest_rows,
        local_preview=local_preview,
        may_write=may_write,
    )
    final_gate = final_gate.merge(views_result.gate)
    outputs.update(views_result.outputs)

    # L11 active consultation (ENGINE_PLAN §4b deferred item, now implemented in
    # ``adjudication.py``): for any blocking gate finding, attach the CONTRADICTION.md
    # tie-breaker that already governs its conflict class as an advisory INFO note. Purely
    # additive and fail-open — every appended finding is non-blocking, so ``BuildResult.ok``
    # is unchanged, and a missing/unreadable matrix leaves the findings untouched.
    final_gate.findings = adjudication.annotate_with_contradictions(final_gate.findings)

    return BuildResult(doc_id=header.id, gate=final_gate, outputs=outputs)


def _load_sibling_figure(md_path: Path) -> dict[str, tuple[str, _FigureSpec]]:
    """Load the ``<stem>_spec.json`` figure spec(s) adjacent to ``md_path``, if present.

    Returns an empty mapping (never raises) when no sidecar spec file exists — a document
    with no ``<!-- figure:ID --> `` directives needs none. The sidecar is either a single
    figure object (the original, still-supported shape — every document authored before
    this could hold at most one figure) or a JSON array of figure objects, for documents
    that embed more than one (e.g. a workflow doc combining a flowchart, a sequence, and a
    state diagram). Each object's ``kind`` field selects its loader/renderer; it defaults to
    ``"flowchart"`` so a spec authored before the multi-convention renderers existed renders
    exactly as before. ``"sequence"`` is the one kind whose JSON shape differs (``actors``/
    ``messages``, not ``nodes``/``edges``) since it doesn't share ``VisualSpec``'s geometry,
    so it gets its own loader.
    """
    spec_path = md_path.parent / f"{md_path.stem}_spec.json"
    if not spec_path.is_file():
        # A document with no `<!-- figure:ID -->` directives legitimately has no sidecar. A document
        # that REFERENCES figures and has lost its sidecar is a different thing entirely, and used
        # to be silent: `cli build` exited 0 with one `wrote html:` line, empty stderr and no
        # finding of any severity, having dropped every figure the document declared. On the
        # flagship gallery that is 21 figures gone from a build reported as successful.
        try:
            body = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {}
        referenced = _FIGURE_DIRECTIVE_RE.findall(body)
        if referenced:
            raise BuildBlockedError(
                f"{md_path.name} references {len(referenced)} figure(s) "
                f"({', '.join(sorted(set(referenced))[:5])}) but its sidecar "
                f"{spec_path.name} is missing. Refusing to build a document with its figures "
                "silently removed."
            )
        return {}
    raw = json.loads(spec_path.read_text(encoding="utf-8"))
    entries = raw if isinstance(raw, list) else [raw]
    figures: dict[str, tuple[str, _FigureSpec]] = {}
    for data in entries:
        kind = data.get("kind", "flowchart")
        handler = _FIGURE_KINDS.get(kind)
        if handler is None:
            # An unrecognised kind used to fall through to _visual_spec_from_dict here and to
            # `_FIGURE_RENDERERS.get(_kind, visual.render)` at render time, so a figure whose kind
            # the engine does not know — a typo, or a new kind whose author missed one of the edit
            # sites — built EXIT 0 and rendered silently as a FLOWCHART, with the author's correct
            # caption and legend and no finding, no warning and no gate. A wrong diagram that looks
            # right is worse than a failed build.
            raise BuildBlockedError(
                f"figure '{data.get('id', '<no id>')}' declares kind='{kind}', which this engine "
                f"does not render. Known kinds: {', '.join(sorted(_FIGURE_KINDS))}. "
                "Refusing to guess."
            )
        spec: _FigureSpec = handler.load(data)
        # A sidecar carrying the SAME id twice used to keep whichever entry came last and drop the
        # other without a word — the document rendered one figure where two were authored, exit 0
        # (`P8-085`, the duplicate edge of the orphan check below).
        if spec.id in figures:
            raise BuildBlockedError(
                f"{spec_path.name} declares figure id {spec.id!r} more than once; the later entry "
                "would silently replace the earlier one. Refusing to build a document with a "
                "figure silently dropped."
            )
        figures[spec.id] = (kind, spec)
    # The sidecar EXISTS but does not carry every id the document references. The missing-sidecar
    # case above has been guarded for a while; this one — a single typo'd or renamed id — was not,
    # and it is the more common of the two. The directive matched nothing, the branch that renders
    # a figure was skipped, and the figure vanished from the output with exit 0, `wrote html`,
    # `check` PASSED and `--strict` silent. A figure disappearing from a document that reports
    # success is precisely the silent-wrong-output class this engine exists to refuse.
    try:
        body = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return figures
    referenced_ids: set[str] = set(_FIGURE_DIRECTIVE_RE.findall(body))
    missing = sorted(referenced_ids - set(figures))
    if missing:
        known = ", ".join(sorted(figures)[:8]) or "(none)"
        raise BuildBlockedError(
            f"{md_path.name} references figure id(s) not present in {spec_path.name}: "
            f"{', '.join(missing)}. Known ids: {known}. Refusing to build a document with its "
            "figures silently removed."
        )
    # ...and the OTHER direction (`P8-085`). ``missing`` above was computed one-way, so the
    # sidecar side of the same typo — the author renames `<!-- figure:FIG-3 -->` to `FIG-03` in the
    # Markdown and forgets the sidecar, or deletes the directive and leaves the entry — was
    # ACCEPTED in silence: the orphan was parsed, rendered by nothing, and the build reported
    # success while the sidecar and the document disagreed about what the document contains. An id
    # in exactly one of the two files is the same authoring mistake whichever file it is in, so it
    # gets the same answer. Measured on the live corpus before shipping: 3 sidecars
    # (examples/capability-gallery, tools/docgen/sample, tools/docgen/sample-multi-figure),
    # 25 entries, ZERO orphans — this narrows nothing that is currently authored.
    orphans = sorted(set(figures) - referenced_ids)
    if orphans:
        raise BuildBlockedError(
            f"{spec_path.name} declares figure id(s) that {md_path.name} never references: "
            f"{', '.join(orphans)}. Nothing renders them, so the sidecar and the document "
            "disagree about what the document contains. Reference them or delete them."
        )
    return figures


def _sequence_spec_from_dict(data: dict[str, Any]) -> SequenceSpec:
    """Build a ``SequenceSpec`` (with nested ``Actor``/``Message``) from parsed JSON."""
    from tools.docgen.models import Actor, DataSource, LegendEntry, Message

    actors = [Actor(id=a["id"], label=a["label"]) for a in data["actors"]]
    messages = [
        Message(
            src=m["src"],
            dst=m["dst"],
            label=m.get("label", ""),
            order=int(m["order"]),
            style=m.get("style", "solid"),
            kind=str(m.get("kind", "")),
            note=str(m.get("note", "")),
        )
        for m in data["messages"]
    ]
    legend = [
        LegendEntry(kind=item["kind"], key=item["key"], label=item["label"])
        for item in data.get("legend", [])
    ]
    data_sources = [
        DataSource(
            kind=src["kind"],
            ref=src["ref"],
            retrieved=src.get("retrieved", ""),
            url=src.get("url", ""),
        )
        for src in data.get("data_sources", [])
    ]
    return SequenceSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        actors=actors,
        messages=messages,
        width=float(data.get("width", 720.0)),
        height=float(data.get("height", 420.0)),
        legend=legend,
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=data_sources,
    )


def _mermaid_spec_from_dict(data: dict[str, Any]) -> MermaidFigureSpec:
    """Build a ``MermaidFigureSpec`` from a sidecar ``*_spec.json`` object (``kind: "mermaid"``).

    ``code`` is raw Mermaid text — one of the 6 types tools/mermaid-engine actually supports
    (mermaid_bridge.render fails closed with a clear message on anything else).
    """
    code = data.get("code")
    if not isinstance(code, str) or not code.strip():
        raise mermaid_bridge.MermaidRenderError(
            f'figure "{data.get("id", "?")}": kind "mermaid" requires a non-empty "code" string '
            "(raw Mermaid diagram text)"
        )
    return MermaidFigureSpec(
        id=str(data.get("id", "mermaid-figure")),
        caption=str(data.get("caption", "")),
        code=code,
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        # Explicit dict.get default (not just the dataclass field default) — passing bg=None
        # here would override MermaidFigureSpec's own default with a real None.
        bg=data.get("bg", "var(--mermaid-bg)"),
        fg=data.get("fg", "var(--mermaid-fg)"),
        data_sources=_data_sources_from_dict(data),
    )


def _sankey_spec_from_dict(data: dict[str, Any]) -> SankeySpec:
    """Build a ``SankeySpec`` (nested ``SankeyNode``/``SankeyFlow``) from parsed JSON.

    A Sankey has no ``legend`` field (its bands ARE its legend); its distinct shape is
    ``nodes`` with a ``col`` index + ``flows`` with a positive ``value``. ``data_sources``
    are threaded through for the L16 source-attribution footer.
    """
    from tools.docgen.models import DataSource
    from tools.docgen.sankey import SankeyFlow, SankeyNode

    nodes = [SankeyNode(id=n["id"], label=n["label"], col=int(n["col"])) for n in data["nodes"]]
    flows = [
        SankeyFlow(
            src=f["src"],
            dst=f["dst"],
            value=float(f["value"]),
            label=f.get("label", ""),
            emphasis=bool(f.get("emphasis", False)),
        )
        for f in data["flows"]
    ]
    data_sources = [
        DataSource(
            kind=src["kind"],
            ref=src["ref"],
            retrieved=src.get("retrieved", ""),
            url=src.get("url", ""),
        )
        for src in data.get("data_sources", [])
    ]
    return SankeySpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        nodes=nodes,
        flows=flows,
        unit=data.get("unit", ""),
        width=float(data.get("width", 720.0)),
        height=float(data.get("height", 420.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=data_sources,
    )


def _geo_map_spec_from_dict(data: dict[str, Any]) -> GeoMapSpec:
    """Build a ``GeoMapSpec`` (nested ``GeoPoint``/``GeoLink``) from parsed JSON.

    Distinct shape: ``points`` (``lon``/``lat`` degrees, optional sourced ``value``) +
    ``links`` (``src``/``dst``). No ``legend`` field. ``value`` stays ``None`` unless
    present so the L16 unsourced-value gate in the renderer keeps its meaning.
    """
    from tools.docgen.geo_map import GeoLink, GeoPoint
    from tools.docgen.models import DataSource

    points = [
        GeoPoint(
            id=p["id"],
            label=p["label"],
            lon=float(p["lon"]),
            lat=float(p["lat"]),
            hot=bool(p.get("hot", False)),
            value=None if p.get("value") is None else float(p["value"]),
            note=p.get("note", ""),
        )
        for p in data["points"]
    ]
    links = [
        GeoLink(
            src=link_["src"],
            dst=link_["dst"],
            label=link_.get("label", ""),
            style=link_.get("style", "solid"),
        )
        for link_ in data.get("links", [])
    ]
    data_sources = [
        DataSource(
            kind=src["kind"],
            ref=src["ref"],
            retrieved=src.get("retrieved", ""),
            url=src.get("url", ""),
        )
        for src in data.get("data_sources", [])
    ]
    return GeoMapSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        points=points,
        links=links,
        width=float(data.get("width", 900.0)),
        height=float(data.get("height", 500.0)),
        show_base=bool(data.get("show_base", True)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=data_sources,
    )


def _choropleth_spec_from_dict(data: dict[str, Any]) -> ChoroplethSpec:
    """Build a ``ChoroplethSpec`` from parsed JSON (``kind: "choropleth"``).

    ``values`` keys must match a country name in the bundled dataset exactly — call
    ``tools.docgen.geo_map.list_choropleth_country_names()`` to check spelling. Country names
    are the dataset's short/common form (e.g. ``"USA"``, not ``"United States of America"``).
    """
    from tools.docgen.models import DataSource

    values = {str(k): float(v) for k, v in data["values"].items()}
    data_sources = [
        DataSource(
            kind=src["kind"],
            ref=src["ref"],
            retrieved=src.get("retrieved", ""),
            url=src.get("url", ""),
        )
        for src in data.get("data_sources", [])
    ]
    return ChoroplethSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        values=values,
        unit=data.get("unit", ""),
        width=float(data.get("width", 900.0)),
        height=float(data.get("height", 500.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=data_sources,
    )


def _isometric_spec_from_dict(data: dict[str, Any]) -> IsometricSpec:
    """Build an ``IsometricSpec`` (nested ``IsoBox``/``IsoConnector``) from parsed JSON.

    Distinct shape: ``boxes`` (world-placed cuboids) + ``connectors`` + ``layer_labels``,
    not ``nodes``/``edges``. It DOES carry a ``legend`` (like ``VisualSpec``/``SequenceSpec``).
    """
    from tools.docgen.isometric3d import IsoBox, IsoConnector
    from tools.docgen.models import DataSource, LegendEntry

    boxes = [
        IsoBox(
            id=b["id"],
            label=b["label"],
            x=float(b["x"]),
            y=float(b["y"]),
            z=float(b["z"]),
            w=float(b.get("w", 96.0)),
            d=float(b.get("d", 96.0)),
            h=float(b.get("h", 44.0)),
            note=b.get("note", ""),
            highlight=bool(b.get("highlight", False)),
        )
        for b in data["boxes"]
    ]
    connectors = [
        IsoConnector(
            src=c["src"],
            dst=c["dst"],
            label=c.get("label", ""),
            style=c.get("style", "solid"),
        )
        for c in data.get("connectors", [])
    ]
    legend = [
        LegendEntry(kind=item["kind"], key=item["key"], label=item["label"])
        for item in data.get("legend", [])
    ]
    data_sources = [
        DataSource(
            kind=src["kind"],
            ref=src["ref"],
            retrieved=src.get("retrieved", ""),
            url=src.get("url", ""),
        )
        for src in data.get("data_sources", [])
    ]
    return IsometricSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        boxes=boxes,
        connectors=connectors,
        layer_labels=data.get("layer_labels", []),
        legend=legend,
        motion=bool(data.get("motion", True)),
        width=float(data.get("width", 720.0)),
        height=float(data.get("height", 480.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=data_sources,
    )


def _visual_spec_from_dict(data: dict[str, Any]) -> VisualSpec:
    """Build a ``VisualSpec`` (with nested ``Node``/``Edge``/``LegendEntry``) from parsed JSON."""
    from tools.docgen.assets.glyphs import validate_tone
    from tools.docgen.models import DataSource, Edge, LegendEntry, Node, NodeType

    def _tone_of(n: dict[str, Any]) -> str:
        # A tone is printed into an SVG class attribute: refuse anything outside the documented families up front,
        # naming the node, rather than at render time (OG-273).
        try:
            return validate_tone(str(n.get("tone", "")))
        except ValueError as exc:
            raise BuildBlockedError(f"node '{n['id']}': {exc}") from exc

    nodes = [
        Node(
            id=n["id"],
            type=NodeType(n["type"]),
            label=n["label"],
            x=float(n["x"]),
            y=float(n["y"]),
            w=float(n.get("w", 120.0)),
            h=float(n.get("h", 56.0)),
            note=n.get("note", ""),
            highlight=bool(n.get("highlight", False)),
            alive=bool(n.get("alive", False)),
            tone=_tone_of(n),
        )
        for n in data["nodes"]
    ]
    edges = [
        Edge(
            src=e["src"],
            dst=e["dst"],
            label=e.get("label", ""),
            style=e.get("style", "solid"),
            condition=e.get("condition", ""),
            main=bool(e.get("main", False)),
            role=str(e.get("role", "")),
            phase=str(e.get("phase", "")),
            note=str(e.get("note", "")),
        )
        for e in data["edges"]
    ]
    legend = [
        LegendEntry(kind=item["kind"], key=item["key"], label=item["label"])
        for item in data.get("legend", [])
    ]
    data_sources = [
        DataSource(
            kind=src["kind"],
            ref=src["ref"],
            retrieved=src.get("retrieved", ""),
            url=src.get("url", ""),
        )
        for src in data.get("data_sources", [])
    ]
    return VisualSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        nodes=nodes,
        edges=edges,
        legend=legend,
        motion=bool(data.get("motion", True)),
        width=float(data.get("width", 720.0)),
        height=float(data.get("height", 420.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=data_sources,
    )


def _data_sources_from_dict(data: dict[str, Any]) -> list[Any]:
    """Shared ``data_sources`` list parser — every chart spec below sources its numbers the
    same way (L16), so this replaces 6 near-identical inline comprehensions with one."""
    from tools.docgen.models import DataSource

    return [
        DataSource(
            kind=src["kind"],
            ref=src["ref"],
            retrieved=src.get("retrieved", ""),
            url=src.get("url", ""),
        )
        for src in data.get("data_sources", [])
    ]


def _bar_spec_from_dict(data: dict[str, Any]) -> BarSpec:
    """Build a ``BarSpec`` from parsed JSON (``kind: "bar"``) — zero-baseline bar chart."""
    from tools.docgen.models import BarItem

    items = [BarItem(label=i["label"], value=float(i["value"]), note=i.get("note", "")) for i in data["items"]]
    return BarSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        items=items,
        unit=data.get("unit", ""),
        log_scale=bool(data.get("log_scale", False)),
        width=float(data.get("width", 720.0)),
        height=float(data.get("height", 420.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=_data_sources_from_dict(data),
    )


def _radar_spec_from_dict(data: dict[str, Any]) -> RadarSpec:
    """Build a ``RadarSpec`` from parsed JSON (``kind: "radar"``) — needs >=3 axes (checked at render)."""
    from tools.docgen.models import LegendEntry, RadarSeries

    series = [RadarSeries(label=s["label"], values=[float(v) for v in s["values"]]) for s in data["series"]]
    legend = [
        LegendEntry(kind=item["kind"], key=item["key"], label=item["label"]) for item in data.get("legend", [])
    ]
    return RadarSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        axes=list(data["axes"]),
        series=series,
        max_value=float(data["max_value"]),
        width=float(data.get("width", 480.0)),
        height=float(data.get("height", 480.0)),
        legend=legend,
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=_data_sources_from_dict(data),
    )


def _pie_spec_from_dict(data: dict[str, Any]) -> PieSpec:
    """Build a ``PieSpec`` from parsed JSON (``kind: "pie"``) — <=6 slices (checked at render)."""
    from tools.docgen.models import LegendEntry, PieSlice

    slices = [PieSlice(label=s["label"], value=float(s["value"])) for s in data["slices"]]
    legend = [
        LegendEntry(kind=item["kind"], key=item["key"], label=item["label"]) for item in data.get("legend", [])
    ]
    return PieSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        slices=slices,
        donut=bool(data.get("donut", True)),
        width=float(data.get("width", 480.0)),
        height=float(data.get("height", 480.0)),
        legend=legend,
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=_data_sources_from_dict(data),
    )


def _timeline_spec_from_dict(data: dict[str, Any]) -> TimelineSpec:
    """Build a ``TimelineSpec`` from parsed JSON (``kind: "timeline"``) — point events, not Gantt."""
    from tools.docgen.models import TimelineEvent

    events = [
        TimelineEvent(label=e["label"], date_label=e["date_label"], t=float(e["t"]), note=e.get("note", ""))
        for e in data["events"]
    ]
    return TimelineSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        events=events,
        width=float(data.get("width", 900.0)),
        height=float(data.get("height", 260.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=_data_sources_from_dict(data),
    )


def _heatmap_spec_from_dict(data: dict[str, Any]) -> HeatmapSpec:
    """Build a ``HeatmapSpec`` from parsed JSON (``kind: "heatmap"``) — carries a mandatory
    color-scale legend at render time regardless of what's passed here (docgen law)."""
    return HeatmapSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        row_labels=list(data["row_labels"]),
        col_labels=list(data["col_labels"]),
        matrix=[[float(v) for v in row] for row in data["matrix"]],
        min_value=float(data["min_value"]),
        max_value=float(data["max_value"]),
        width=float(data.get("width", 720.0)),
        height=float(data.get("height", 420.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=_data_sources_from_dict(data),
    )


def _layered_spec_from_dict(data: dict[str, Any]) -> LayeredSpec:
    """Build a ``LayeredSpec`` from parsed JSON (``kind: "layered_workflow"``) — 2.5D
    layer+column placement, distinct from ``VisualSpec``'s free x/y."""
    from tools.docgen.models import LayerConnector, LayerNode

    nodes = [
        LayerNode(id=n["id"], label=n["label"], layer=int(n["layer"]), col=int(n["col"]))
        for n in data["nodes"]
    ]
    connectors = [
        LayerConnector(src=c["src"], dst=c["dst"], label=c.get("label", "")) for c in data.get("connectors", [])
    ]
    return LayeredSpec(
        id=data["id"],
        title=data["title"],
        caption=data["caption"],
        layer_labels=list(data["layer_labels"]),
        nodes=nodes,
        connectors=connectors,
        width=float(data.get("width", 720.0)),
        height=float(data.get("height", 480.0)),
        reader_question=data.get("reader_question", ""),
        insight=data.get("insight", ""),
        data_sources=_data_sources_from_dict(data),
    )


# --------------------------------------------------------------------------------------
# THE figure dispatch table (`P8-090`). Defined last because every loader above must exist
# first; both consumers (``_load_sibling_figure``, ``_render_markdown_body``) read it at call
# time. A kind present here is parseable AND renderable by construction — the two cannot drift.
# --------------------------------------------------------------------------------------
_MARK_ROWS_MAX = 30


def _mark_rows(record: Mapping[str, Any]) -> tuple[tuple[str, str, str], ...]:
    """Rows for the table that names every mark of an engine chart — empty above ``_MARK_ROWS_MAX``.

    A chart with thirty dots needs a legend you can read; one with a thousand needs the blueprint JSON, so past the
    limit the table is left out rather than printed as a wall. Connections ("edge") and whole-series shapes carry no
    value of their own, and the mark they join already says so.
    """
    rows: list[tuple[str, str, str]] = []
    for mark in record.get("marks") or []:
        if mark.get("kind") in ("edge", "series"):
            continue
        label = str(mark.get("label") or "")
        value = mark.get("value")
        shown = ", ".join(str(v) for v in value) if isinstance(value, list) else ("" if value is None else str(value))
        detail = str(mark.get("description") or "")
        if label and detail.startswith(f"{label}; "):
            detail = detail[len(label) + 2 :]
        rows.append((label, shown, detail))
    return tuple(rows) if 0 < len(rows) <= _MARK_ROWS_MAX else ()


# Reading guides for kinds whose renderer does not compute one. Every figure that puts a number, a colour or a numbered
# circle in front of a reader says what it means (the document layer prints this under the figure).
_GUIDE_MERMAID = (
    "Boxes are steps or components and arrows show direction: read from an arrow's tail to its head. A label on an "
    "arrow says what flows or what condition applies."
)
_GUIDE_SANKEY = (
    "Bands are flows between nodes and a band's width is the quantity, so a wider band moved more. Read left to right."
)
_GUIDE_MAP = (
    "Each marker or shaded region is a place; its size or colour carries the quantity named in the legend, and darker "
    "or larger means more."
)
_GUIDE_ISOMETRIC = (
    "A block diagram drawn in isometric view: each block is a component, its label names it, and its position shows "
    "how the parts stack or connect."
)
_GUIDE_BAR = "Each bar is one category and its length is the value printed on or beside it; compare bars by length."
_GUIDE_RADAR = (
    "Each corner of the polygon is one measure and farther from the centre is higher; a larger shape scores higher "
    "overall."
)
_GUIDE_PIE = "Each slice is one part of the whole; its angle is its share, and the label gives the value."
_GUIDE_TIMELINE = "Events are placed on a time axis, earliest on the left; each marker's label names the event."
_GUIDE_HEATMAP = "Each cell is one row-and-column pair; colour is the value, read against the scale beside the grid."
_GUIDE_LAYERED = (
    "Rows are layers and boxes are the stages inside them; connectors show hand-offs, drawn from the stage that "
    "produces to the stage that consumes."
)


def _present_diagram(renderer: Callable[[VisualSpec], str]) -> Callable[[Any, Tier], _Rendered]:
    """Present a node/edge diagram: its picture, the reading guide that fits it, and the key to its numbered circles."""

    def present(spec: Any, _tier: Tier) -> _Rendered:
        return _Rendered(renderer(spec), visual.how_to_read(spec), tuple(visual.reading_key(spec)))

    return present


def _present_sequence(spec: Any, _tier: Tier) -> _Rendered:
    return _Rendered(
        sequence_diagram.render(spec),
        sequence_diagram.HOW_TO_READ_SEQUENCE,
        tuple(sequence_diagram.reading_key(spec)),
    )


def _explorer_spec_from_dict(data: dict[str, Any]) -> ExplorerSpec:
    """Build the explorer spec, turning the explorer's own refusals into a blocked build that names the figure."""
    try:
        return explorer.spec_from_dict(data)
    except explorer.ExplorerError as exc:
        raise BuildBlockedError(f"figure '{data.get('id', '<no id>')}' (kind explorer) is refused: {exc}") from exc


def _present_explorer(spec: Any, _tier: Tier) -> _Rendered:
    """Present an explorer: its block of HTML, the guide, the machine twin of the whole hierarchy and the table of its parts."""
    return _Rendered(explorer.render(spec), explorer.how_to_read(spec), (), explorer.record(spec), explorer.marks(spec))


def _present_echarts(spec: Any, tier: Tier) -> _Rendered:
    """Present an engine chart. The engine's own per-figure record (every mark, its value and connections, how to read
    it) rides along so the blueprint JSON can hand it to a machine; ``tier`` is the building document's classification."""
    svg, record = echarts_bridge.render_with_figure(spec, doc_tier=tier)
    return _Rendered(svg, str(record.get("how_to_read") or ""), (), record, _mark_rows(record))


_FIGURE_KINDS: dict[str, _FigureKind] = {
    **{
        kind: _FigureKind(_visual_spec_from_dict, renderer, present=_present_diagram(renderer))
        for kind, renderer in _FIGURE_RENDERERS.items()
    },
    # Structural kinds: they show relationships, not quantities. A flowchart's boxes are named,
    # not measured, so demanding a data source for one would be provenance theatre.
    "sequence": _FigureKind(_sequence_spec_from_dict, sequence_diagram.render, present=_present_sequence),
    "mermaid": _FigureKind(_mermaid_spec_from_dict, mermaid_bridge.render, guide=_GUIDE_MERMAID),
    # Data-carrying kinds: every one of these renders at least one number a reader may quote.
    "echarts": _FigureKind(
        echarts_bridge.spec_from_dict, echarts_bridge.render, carries_data=True, present=_present_echarts
    ),
    "sankey": _FigureKind(
        _sankey_spec_from_dict, sankey.render_sankey, carries_data=True, guide=_GUIDE_SANKEY
    ),
    "geo_map": _FigureKind(
        _geo_map_spec_from_dict, geo_map.render_geo_map, carries_data=True, guide=_GUIDE_MAP
    ),
    "choropleth": _FigureKind(
        _choropleth_spec_from_dict, geo_map.render_choropleth, carries_data=True, guide=_GUIDE_MAP
    ),
    "isometric3d": _FigureKind(
        _isometric_spec_from_dict, isometric3d.render, carries_data=True, guide=_GUIDE_ISOMETRIC
    ),
    "bar": _FigureKind(_bar_spec_from_dict, charts.render_bar, carries_data=True, guide=_GUIDE_BAR),
    "radar": _FigureKind(
        _radar_spec_from_dict, charts.render_radar, carries_data=True, guide=_GUIDE_RADAR
    ),
    "pie": _FigureKind(_pie_spec_from_dict, charts.render_pie, carries_data=True, guide=_GUIDE_PIE),
    "timeline": _FigureKind(
        _timeline_spec_from_dict, charts.render_timeline, carries_data=True, guide=_GUIDE_TIMELINE
    ),
    "heatmap": _FigureKind(
        _heatmap_spec_from_dict, charts.render_heatmap, carries_data=True, guide=_GUIDE_HEATMAP
    ),
    "layered_workflow": _FigureKind(
        _layered_spec_from_dict, layered_workflow.render, carries_data=True, guide=_GUIDE_LAYERED
    ),
    # A zoomable, clickable map of a hierarchy (modules, packages, submodules) with a panel and a reader; it carries sizes.
    "explorer": _FigureKind(
        _explorer_spec_from_dict, explorer.render, carries_data=True, present=_present_explorer
    ),
}


def data_carrying_kinds() -> frozenset[str]:
    """Figure kinds that put a number in front of a reader — DERIVED from the dispatch table.

    Exposed so a probe can take its subject set from the engine's own declaration rather than
    from a list copied into a test (`LESSONS.md` L-37). A hand-copied list stops covering a kind
    the moment one is added, and says nothing when it does.
    """
    return frozenset(kind for kind, spec in _FIGURE_KINDS.items() if spec.carries_data)


# A QUANTITY a reader would take as a measurement, as opposed to an IDENTIFIER that merely
# contains digits (`OG-194`).
#
# **Rewritten 2026-08-24 after an adversarial verifier refuted the first version end to end.**
# That version was three alternatives — `[$£€¥]\s?\d`, a digit before `%`, and comma-grouped
# digits — and the refutation did not need cleverness. Re-punctuating the very repro that had
# closed the finding got through: `Revenue: 4.2M USD ARR, 87 pct margin` built clean and rendered
# verbatim. So did `₹500 crore`, because the currency class was four hardcoded symbols. So did
# `1.500,00 €`, because the symbol trailed the amount and the grouping used periods.
#
# **And it produced false positives that mattered more than the misses.** `Covered by Patent
# 10,123,456` BLOCKED a build. That is legitimate citation-shaped content, the gate could not tell
# it from a measurement, and an author who hits that once looks for a way around the gate rather
# than through it — which is the failure `OG-194`'s own reasoning warned about.
#
# **The posture changed because of that, and the widening follows from the posture.** For a
# structural figure this is now an ADVISORY finding, not a blocking one — the same contract Gate 4
# (`detector_internal`) carries and for the same stated reason: a semantic net over free prose is
# paraphrase-fragile and must never be the sole moat. `cli.py`'s `--strict` promotes advisories to
# failures, so a project that wants it blocking has that switch. Once a false positive costs a
# line of output instead of a build, the detector can afford to be generous — which is the only
# way it can be broad enough to be worth reading.
#
# **What is still NOT detected, stated so nobody re-derives it:** a bare number that is genuinely a
# measurement (`Revenue 4200000`), a unit-suffixed figure (`250ms`, `4.2GB`), scientific notation,
# and numeric series inside a `mermaid` figure's raw diagram source — an `xychart-beta` block
# carries real axis values that none of these patterns see. Separating a measurement from an
# identifier in free text is not a thing a regular expression can do, and the blocking half of L16
# deliberately does not depend on this heuristic.
_CURRENCY = "$£€¥₹₩₽₺₦₪₫₴₸฿₡₱₲₵₭₮"
_ISO_CCY = (
    "USD|EUR|GBP|JPY|INR|CNY|RMB|CHF|CAD|AUD|NZD|SEK|NOK|DKK|PLN|ZAR|BRL|MXN|"
    "KRW|SGD|HKD|TRY|RUB|AED|SAR|ILS|THB"
)
_QUANTITY_RE = re.compile(
    # currency symbol before OR after the amount, with optional scale suffix: $4.2 / 900 € / £ 1,2
    rf"[{_CURRENCY}]\s?\d"
    rf"|\d(?:[.,]\d+)?\s?[kKmMbB]?[nN]?\s?[{_CURRENCY}]"
    # an ISO currency code on either side of an amount: 4.2M USD / USD 4.2M
    rf"|\d(?:[.,]\d+)?\s?[kKmMbB]?[nN]?\s?(?:{_ISO_CCY})\b"
    rf"|\b(?:{_ISO_CCY})\s?\d"
    # a percentage, in symbol, full-width or word form
    r"|\d(?:[.,]\d+)?\s?[%％]"
    r"|\d(?:[.,]\d+)?\s?(?:percent|per\s?cent|pct)\b"
    # thousands-grouped with commas: 4,200,000
    r"|\b\d{1,3}(?:,\d{3})+\b",
    re.IGNORECASE,
)

# **Masked out BEFORE the scan, because each reads as a quantity and is not one.**
#
# `%2F` in a URL is percent-ENCODING, not a percentage — `/items/42%2Fchild` matched the percent
# alternative purely because a digit preceded a `%`. Masking is used rather than a negative
# lookahead so the two concerns stay separately readable.
_NOT_A_QUANTITY_RE = re.compile(r"%[0-9A-Fa-f]{2}")

# A comma-grouped number introduced by one of these is an IDENTIFIER, not a measurement. Patent
# numbers are the real-world case that blocked a build: the USPTO writes them `10,123,456`.
_IDENTIFIER_LEAD_RE = re.compile(
    r"(?:patent|ticket|invoice|order|serial|case|claim|ref|reference|no|nr|num|number|ext|id|"
    r"issue|docket|isbn|#)\s*[.:#\-]?\s*$",
    re.IGNORECASE,
)


def quantities_in(text: str) -> list[str]:
    """Every substring of ``text`` a reader would take as a measurement, deduplicated and sorted.

    Public because the probes read it directly: asserting on the detector is far more precise than
    asserting on a build's exit code, and a probe that can only see the build cannot show WHICH
    boundary moved.
    """
    masked = _NOT_A_QUANTITY_RE.sub(lambda m: "\x00" * len(m.group(0)), text)
    found: set[str] = set()
    for match in _QUANTITY_RE.finditer(masked):
        lead = masked[max(0, match.start() - 24) : match.start()]
        if _IDENTIFIER_LEAD_RE.search(lead):
            continue
        found.add(text[match.start() : match.end()].strip())
    return sorted(found)


# Field names whose string values are machinery, not prose a reader sees: identifiers, style
# tokens and colour references. `note` and `condition` are deliberately NOT here — both render as
# visible text, and a note reading "throughput 4,000/s" is exactly the case this exists for.
_NON_PROSE_FIELDS = frozenset({"id", "kind", "key", "style", "bg", "fg", "type", "src", "dst"})


def _resolvable(sources: list[object]) -> bool:
    """True when at least one declared source points somewhere.

    One definition, both call sites. RULEBOOK L16 says *resolvable*; a `DataSource` whose `ref`
    and `url` are both blank names nothing, and a figure carrying one reads as attributed to every
    later check while being sourced to nothing at all.
    """
    return any(
        str(getattr(src, "ref", "")).strip() or str(getattr(src, "url", "")).strip()
        for src in sources
    )


def _prose_of(value: object, *, field_name: str = "") -> list[str]:
    """Every reader-visible string inside a figure spec, recursively.

    Walks dataclasses, lists and tuples rather than naming each spec's label fields, because a
    per-kind extractor is a list that stops covering a kind the moment one is added — and the six
    structural kinds do not share a shape (`VisualSpec` has nodes and edges, `SequenceSpec` has
    actors and messages, `MermaidFigureSpec` has one blob of diagram source).
    """
    if field_name in _NON_PROSE_FIELDS:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [s for item in value for s in _prose_of(item)]
    if is_dataclass(value) and not isinstance(value, type):
        return [
            s
            for f in fields(value)
            for s in _prose_of(getattr(value, f.name, None), field_name=f.name)
        ]
    return []


def check_figure_provenance(
    figures: Mapping[str, tuple[str, _FigureSpec]],
) -> list[Finding]:
    """RULEBOOK L16 at the render gate, for **every** data-carrying kind (`OG-63`).

    L16 says a number with no resolvable ``DataSource`` fails the render, and its own status block
    named the two gates that enforced it: ``geomap.source`` and ``choropleth.source``. Two kinds
    out of eleven. Every other numeric spec declared ``data_sources`` with an empty default and
    nothing ever read it, so a bar chart, a pie, a heatmap or an ECharts figure carrying real
    numbers and no provenance rendered clean — the law was enforced on the two kinds someone had
    got to, and was a convention everywhere else.

    That is `docs/process/RULES.md` Rule 1's exact shape: one root, several consumers, two
    guarded. This closes it at the root — the dispatch table already knows which kinds carry
    data, so the check is over that set rather than over a list someone remembered to extend.

    Blocking and CRITICAL, deliberately. An unsourced number that survives review becomes a fact
    by repetition, which is `CONTRADICTION.md` row 8's own reasoning; an advisory here would leave
    the convention exactly as unenforced as it was.
    """
    findings: list[Finding] = []
    for fig_id, (kind, spec) in sorted(figures.items()):
        handler = _FIGURE_KINDS.get(kind)
        if handler is None:
            continue
        declared = list(getattr(spec, "data_sources", ()) or ())
        if not handler.carries_data:
            # **A structural kind still answers to L16 for numbers it writes into its text**
            # (`OG-194`). These kinds are exempt from *declaring a data series*, because their
            # boxes are named rather than measured and demanding `data_sources` from every
            # flowchart is provenance theatre. They are not exempt from the law: L16 says a
            # number with no resolvable DataSource fails the render, and it does not care whether
            # the number arrived as a datum or as a label.
            quantities = sorted({q for text in _prose_of(spec) for q in quantities_in(text)})
            if not quantities or _resolvable(declared):
                continue
            shown = ", ".join(repr(q) for q in quantities[:3])
            findings.append(
                Finding(
                    gate="figure_provenance",
                    message=(
                        f"figure '{fig_id}' (kind={kind}) writes {len(quantities)} quantity/ies "
                        f"into its own text and declares no data_sources. RULEBOOK L16 applies to "
                        f"a number wherever it renders, not only to a declared data series. "
                        f"Source it, or move the number into prose the document already sources. "
                        f"ADVISORY: this is a heuristic over free text and is not the moat — run "
                        f"with --strict to make it blocking."
                    ),
                    severity=Severity.MED,
                    # ⚠ **Advisory, and the reason is the same one Gate 4 states for itself.**
                    #
                    # The first version blocked, and an adversarial verifier showed both halves of
                    # why that was wrong. It missed `4.2M USD` and `87 pct` — the very repro that
                    # closed the finding, merely re-punctuated — so the block was not the
                    # protection it looked like. And it REFUSED a build on `Covered by Patent
                    # 10,123,456`, which is a citation, not a measurement. A gate that blocks
                    # legitimate work on a heuristic teaches authors to route around it, and this
                    # finding's own reasoning is what warned about that.
                    #
                    # `detector_internal` is the established posture for exactly this shape — a
                    # semantic net over prose, paraphrase-fragile, advisory unless `--strict`,
                    # explicitly "not the sole moat". `cli.py` fails the build on any advisory
                    # under `--strict`, so a project that wants this blocking has the switch.
                    #
                    # **The blocking half of L16 does not depend on this heuristic**: a figure kind
                    # that declares a data series must still name a resolvable source, and that is
                    # a structural check with no guessing in it.
                    blocking=False,
                    evidence=f"quantities found: {shown}",
                )
            )
            continue
        # **RULEBOOK L16 says RESOLVABLE, and that word is the gate's real boundary.**
        #
        # The first version of this check asked only whether the list was non-empty, and its own
        # new edge went straight through: `data_sources: [{"kind": "metric", "ref": ""}]` — a
        # source naming nothing — satisfied it completely. That is a worse state than no source at
        # all, because the figure now *looks* attributed to every reader and to every later check.
        # A source has to point somewhere: a `ref` or a `url`. (`RULES.md` Rule 1's corollary:
        # after narrowing anything, ask what the widest input is that still gets through.)
        if _resolvable(declared):
            continue
        empty_but_present = bool(declared)
        findings.append(
            Finding(
                gate="figure_provenance",
                message=(
                    f"figure '{fig_id}' (kind={kind}) renders numbers but declares "
                    + (
                        f"{len(declared)} data_source(s) that name nothing — every one has an "
                        "empty ref and an empty url"
                        if empty_but_present
                        else "no data_sources"
                    )
                    + ". RULEBOOK L16: a number with no resolvable DataSource fails the render. "
                    "Add a data_sources entry naming where the numbers came from, or use a "
                    "structural figure kind if there is nothing to source."
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=(
                    f"kind={kind} carries data; "
                    + (
                        f"{len(declared)} declared source(s), 0 resolvable"
                        if empty_but_present
                        else "data_sources is empty"
                    )
                ),
            )
        )
    return findings
