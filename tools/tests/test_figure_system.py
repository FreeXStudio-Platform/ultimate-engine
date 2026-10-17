"""The figure system's contract: unique ids, scoped hover CSS, numbered circles that explain themselves, and a
document in which text and pictures point at each other (OG-250 … OG-261).

Every case is a defect measured on a report that inlined 28 charts and 19 diagrams into one page or a
guarantee the AI-readable twin of a document depends on. Each test is written so that reverting its fix turns it red.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from tools.docgen import components, figure_support, generator, sequence_diagram, visual
from tools.docgen.generator import BuildBlockedError
from tools.docgen.models import (
    Actor,
    Edge,
    Message,
    Node,
    NodeType,
    SequenceSpec,
    VisualSpec,
)

_REPO = Path(__file__).resolve().parents[2]
_ID = re.compile(r'(?<![\w-])id="([^"]+)"')


def _top_level(selector: str) -> list[str]:
    """Split a selector list on the commas that are not inside ``(...)`` or ``[...]``."""
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in selector:
        depth += ch in "([" 
        depth -= ch in ")]"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _flow(fig_id: str = "flow", *, n_main: int = 3) -> VisualSpec:
    """A left-to-right chain with ``n_main`` numbered steps and enough room for every badge."""
    nodes = [
        Node(id=f"n{i}", type=NodeType.PROCESS, label=f"Step {i}", x=40.0 + i * 300.0, y=120.0, w=120.0, h=56.0)
        for i in range(n_main + 1)
    ]
    edges = [
        Edge(src=f"n{i}", dst=f"n{i + 1}", label=f"hand-off {i + 1}", main=True, note=f"what happens at step {i + 1}")
        for i in range(n_main)
    ]
    return VisualSpec(
        id=fig_id, title="A chain", caption="A chain of steps", nodes=nodes, edges=edges,
        width=80.0 + (n_main + 1) * 300.0, height=320.0, motion=True,
    )


def _seq(fig_id: str = "seq", *, title: str = "A call") -> SequenceSpec:
    return SequenceSpec(
        id=fig_id, title=title, caption="A call", width=700.0, height=360.0,
        actors=[Actor(id="a", label="client"), Actor(id="b", label="server"), Actor(id="c", label="queue")],
        messages=[
            Message(src="a", dst="b", label="request", order=1),
            Message(src="b", dst="a", label="response", order=2, style="dashed"),
            Message(src="b", dst="c", label="enqueue", order=3, kind="async"),
        ],
    )


class FigureSupportPlumbing(unittest.TestCase):
    def test_dom_ids_and_scopes(self) -> None:
        self.assertEqual(figure_support.fig_dom_id("Paid audit"), "fig-paid-audit")
        self.assertEqual(figure_support.fig_dom_id("fig-already"), "fig-already", "no double prefix")
        self.assertEqual(figure_support.slug("  ***  "), "x", "never empty")

    def test_section_ids_are_unique_in_document_order(self) -> None:
        taken: set[str] = set()
        ids = [figure_support.section_dom_id(t, taken) for t in ("Intro", "Intro", "Intro", "Other")]
        self.assertEqual(ids, ["sec-intro", "sec-intro-2", "sec-intro-3", "sec-other"])

    def test_hand_written_figure_prefixes_are_dropped(self) -> None:
        for raw, want in (("Fig. 5 — The call order", "The call order"), ("Figure 3: Something", "Something"),
                          ("No prefix", "No prefix")):
            self.assertEqual(figure_support.strip_fig_prefix(raw), want)

    def test_scoping_ids_stops_one_figure_borrowing_anothers_gradient(self) -> None:
        a = '<svg><defs><linearGradient id="g0"/><clipPath id="c0"/></defs><rect fill="url(#g0)" clip-path="url(#c0)"/></svg>'
        b = '<svg><defs><linearGradient id="g0"/></defs><rect fill="url(#g0)"/></svg>'
        sa, sb = figure_support.scope_svg_ids(a, "fig-a"), figure_support.scope_svg_ids(b, "fig-b")
        declared = _ID.findall(sa) + _ID.findall(sb)
        self.assertEqual(len(declared), len(set(declared)), "ids are document-unique after scoping")
        self.assertIn('fill="url(#fig-a-g0)"', sa)
        self.assertIn('fill="url(#fig-b-g0)"', sb)

    def test_scoping_never_rewrites_data_id_because_the_adjacency_lists_name_those_ids(self) -> None:
        """A `\\bid=` pattern matches inside `data-id=`; scoping the mark's id but not the `data-nb` list that names it
        broke every hover highlight in a built document while all unit tests stayed green."""
        svg = '<svg><g id="n0" data-id="n0" data-nb="n1"/><g id="n1" data-id="n1" data-nb="n0"/></svg>'
        scoped = figure_support.scope_svg_ids(svg, "fig-z")
        self.assertIn('id="fig-z-n0" data-id="n0" data-nb="n1"', scoped)
        self.assertEqual(_ID.findall(scoped), ["fig-z-n0", "fig-z-n1"])

    def test_scoping_handles_href_and_style_selectors_and_is_idempotent(self) -> None:
        svg = '<svg><style>#arrow{fill:red}</style><marker id="arrow"/><use href="#arrow"/></svg>'
        once = figure_support.scope_svg_ids(svg, "fig-x")
        self.assertIn('href="#fig-x-arrow"', once)
        self.assertIn("#fig-x-arrow{fill:red}", once)
        self.assertEqual(figure_support.scope_svg_ids(once, "fig-x"), once)

    def test_native_css_is_scoped_and_never_recolours_on_hover(self) -> None:
        nodes = [("a", ["b"], ["e0"]), ("b", ["a"], ["e0"])]
        edges = [("e0", ["a", "b"])]
        css = figure_support.native_figure_css("fig-x", nodes, edges)
        scope = 'svg[data-fig="fig-x"]'
        for rule in re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/|@media[^{]*\{", "", css, flags=re.DOTALL)):
            for sel in _top_level(rule[0]):
                self.assertTrue(sel.startswith(scope), f"unscoped selector {sel!r}")
            if ":hover" in rule[0]:
                self.assertNotRegex(rule[1], r"(^|;)\s*(fill|background|color)\s*:", rule[0])
                self.assertNotIn("pointer-events:none", rule[1])
        self.assertIn(":has(", css, "a small diagram keeps the no-script adjacency fallback")
        self.assertIn(":not(.edge-hit)", css, "a lit edge must not shrink its own pointer target")

    def test_a_large_diagram_drops_the_css_only_fallback_and_keeps_the_runtime_rules(self) -> None:
        nodes: list[tuple[str, list[str], list[str]]] = [(f"n{i}", [], []) for i in range(200)]
        css = figure_support.native_figure_css("fig-big", nodes, [])
        self.assertNotIn(":has(", css)
        self.assertIn("[data-ve-js][data-ve-on]", css)


class ReadableInkIsOneRuleInTwoLanguages(unittest.TestCase):
    """`contrast.mjs::inkFor` (engine charts) and `figure_support.ink_for` (native charts) must agree on every fill."""

    def test_every_literal_fill_clears_wcag_aa(self) -> None:
        for r in range(0, 256, 51):
            for g in range(0, 256, 51):
                for b in range(0, 256, 51):
                    fill = f"rgb({r},{g},{b})"
                    ink = figure_support.ink_for(fill)
                    assert ink is not None
                    ratio = figure_support.contrast_ratio(
                        figure_support.parse_color(fill),  # type: ignore[arg-type]
                        figure_support.parse_color(ink),  # type: ignore[arg-type]
                    )
                    self.assertGreaterEqual(ratio, 4.5, f"{fill} -> {ink} is {ratio:.2f}:1")

    def test_non_literal_fills_are_not_guessed(self) -> None:
        self.assertIsNone(figure_support.ink_for("var(--fg)"))
        self.assertIsNone(figure_support.ink_for("url(#g)"))

    def test_the_native_heatmap_prints_each_value_in_the_ink_its_cell_needs(self) -> None:
        from tools.docgen import charts
        from tools.docgen.models import HeatmapSpec

        spec = HeatmapSpec(
            id="hm", title="t", caption="c", width=520.0, height=300.0,
            row_labels=["a", "b"], col_labels=["x", "y"], matrix=[[0.0, 5.0], [9.0, 11.0]],
            min_value=0.0, max_value=11.0,
        )
        svg = charts.render_heatmap(spec)
        inks = re.findall(r'class="chart-value"[^>]*fill="([^"]+)"', svg)
        self.assertGreaterEqual(len(set(inks)), 2, "light and dark cells must not share one ink")
        self.assertNotIn("white", inks, "the literal keyword is the old single-ink behaviour")

    def test_a_radar_legend_entry_that_names_a_series_is_painted_with_that_series_colour(self) -> None:
        from tools.docgen import charts
        from tools.docgen.models import LegendEntry, RadarSeries, RadarSpec

        spec = RadarSpec(
            id="rd", title="t", caption="c", axes=["a", "b", "c"], max_value=10.0,
            series=[RadarSeries(label="files", values=[3.0, 6.0, 9.0])],
            legend=[LegendEntry(kind="swatch", key="files", label="Files per directory")],
        )
        svg = charts.render_radar(spec)
        swatch = re.search(r'<rect[^>]*rx="3"[^>]*fill="([^"]+)"', svg)
        self.assertIsNotNone(swatch)
        assert swatch is not None
        self.assertNotEqual(swatch.group(1), "files", "a series key is not a colour")
        self.assertIsNotNone(figure_support.parse_color(swatch.group(1)) or swatch.group(1).startswith("var("))

    def test_python_and_javascript_agree(self) -> None:
        node = shutil.which("node")
        mjs = _REPO / "tools" / "visual-engine" / "adapters" / "echarts" / "contrast.mjs"
        if node is None or not mjs.is_file():
            self.skipTest("node (or the chart adapter) is not available in this environment")
        samples = ["#000000", "#ffffff", "#4A7FC1", "#C8972A", "#EDB84A", "rgb(178,163,117)", "rgb(15,32,64)",
                   "rgb(153,102,153)", "#3DA875", "#C0282A", "#606878", "rgb(237,184,74)"]
        script = (
            f"import {{ inkFor }} from {json.dumps(mjs.as_uri())};"
            f"console.log(JSON.stringify({json.dumps(samples)}.map((s) => inkFor(s))));"
        )
        proc = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
        js = json.loads(proc.stdout)
        py = [figure_support.ink_for(c) for c in samples]
        self.assertEqual([i.upper() if i else i for i in py], [i.upper() if i else i for i in js])


class NativeDiagramsExplainTheirNumbers(unittest.TestCase):
    def test_the_key_has_one_line_per_numbered_circle_and_each_circle_links_to_it(self) -> None:
        spec = _flow(n_main=3)
        key = visual.reading_key(spec)
        svg = visual.render(spec)
        self.assertEqual([k["n"] for k in key], [1, 2, 3])
        badges = re.findall(r'<a class="fig-badge" href="#([^"]+)"', svg)
        self.assertEqual(badges, [k["anchor"] for k in key], "the picture and the key share one numbering")
        self.assertIn("what happens at step 2", key[1]["detail"])
        self.assertEqual(key[0]["title"], "Step 0 → Step 1")

    def test_badges_keep_the_engines_gap_from_everything_including_each_other(self) -> None:
        self.assertEqual([f.message for f in visual.check_collisions(_flow(n_main=3))], [])

    def test_a_diagram_without_a_main_path_has_no_key_and_a_map_style_guide(self) -> None:
        spec = _flow(n_main=2)
        plain = VisualSpec(**{**spec.__dict__, "edges": [Edge(src=e.src, dst=e.dst) for e in spec.edges]})
        self.assertEqual(visual.reading_key(plain), [])
        self.assertIn("components", visual.how_to_read(plain))
        self.assertIn("moving dot", visual.how_to_read(spec))

    def test_edge_roles_and_dot_phases_default_by_position(self) -> None:
        spec = _flow(n_main=3)
        self.assertEqual({visual.edge_role(e) for e in spec.edges}, {"flow"})
        self.assertEqual(list(visual._phases(spec).values()), ["raw", "processed", "verified"])
        err = Edge(src="n0", dst="n1", main=True, role="error")
        self.assertEqual(visual.edge_role(err), "error")
        self.assertEqual(visual.edge_role(Edge(src="a", dst="b", style="dashed")), "async")

    def test_rendering_is_deterministic(self) -> None:
        self.assertEqual(visual.render(_flow()), visual.render(_flow()))
        self.assertEqual(sequence_diagram.render(_seq()), sequence_diagram.render(_seq()))

    def test_the_rendered_svg_carries_the_attribute_contract_and_a_title_per_mark(self) -> None:
        svg = visual.render(_flow(n_main=2))
        self.assertRegex(svg, r'<svg [^>]*data-fig="fig-flow"')
        nodes = re.findall(r'<g[^>]*data-k="node"[^>]*>', svg)
        self.assertEqual(len(nodes), 3)
        for tag in nodes:
            self.assertRegex(tag, r'data-id="[^"]+"')
            self.assertRegex(tag, r'data-nb="[^"]*"')
        self.assertGreaterEqual(svg.count("<title>"), 3)

    def test_sequence_messages_are_numbered_and_coloured_by_kind(self) -> None:
        spec = _seq()
        self.assertEqual([k["n"] for k in sequence_diagram.reading_key(spec)], [1, 2, 3])
        by_order = sorted(spec.messages, key=lambda m: m.order)
        self.assertEqual(sequence_diagram.message_kind(by_order[0], 1.0, 2.0), "call")
        self.assertEqual(sequence_diagram.message_kind(by_order[1], 2.0, 1.0), "async", "dashed = async")
        self.assertEqual(sequence_diagram.message_kind(by_order[2], 2.0, 3.0), "async", "explicit kind wins")
        self.assertEqual(sequence_diagram.message_kind(Message(src="a", dst="b", label="", order=9), 3.0, 1.0), "return")
        svg = sequence_diagram.render(spec)
        for kind in ("call", "async"):
            self.assertIn(f"msg-{kind}", svg)

    def test_a_title_clears_the_first_row_of_participants_without_invalidating_old_specs(self) -> None:
        """The title reserve grows a titled spec by at most 24px; it never refuses a spec that was valid before it.

        Found by a HOST's own suite, not by this one: a titled, one-message spec at height 200 was valid at the old 180
        minimum and was refused at the new 204. The first version of this test asserted the opposite (that 23px of slack
        was refused) and so pinned the regression instead of catching it.
        """
        rows = 8
        old_minimum = 56.0 + 36.0 + rows * 48.0 + 40.0  # the requirement before the reserve existed

        def make(height: float, title: str = "Titled") -> SequenceSpec:
            return SequenceSpec(
                id="old", title=title, caption="", width=900.0, height=height,
                actors=[Actor(id="a", label="a"), Actor(id="b", label="b")],
                messages=[Message(src="a", dst="b", label=str(i), order=i) for i in range(1, rows + 1)],
            )

        # sized exactly to the OLD minimum: valid, and drawn 24px taller so the title clears the participants
        at_old = make(old_minimum)
        self.assertEqual(sequence_diagram.check_collisions(at_old), [])
        self.assertRegex(sequence_diagram.render(at_old), rf'viewBox="0 0 900 {int(old_minimum) + 24}"')
        # 23px of slack over the old minimum is the same case, not a refusal
        self.assertEqual(sequence_diagram.check_collisions(make(old_minimum + 23.0)), [])
        # a spec that is already tall enough is drawn exactly as authored
        self.assertRegex(sequence_diagram.render(make(old_minimum + 80.0)), rf'viewBox="0 0 900 {int(old_minimum) + 80}"')
        # an untitled spec has no reserve, so no growth
        self.assertRegex(sequence_diagram.render(make(old_minimum, title="")), rf'viewBox="0 0 900 {int(old_minimum)}"')
        # one pixel under the OLD minimum is still refused, with or without a title
        for title in ("Titled", ""):
            self.assertTrue(
                any("below" in f.message for f in sequence_diagram.check_collisions(make(old_minimum - 1.0, title))),
                f"a spec short of the old minimum must still be refused (title={title!r})",
            )


    def test_a_highlighted_node_labels_in_the_light_ink_and_clears_wcag_aa(self) -> None:
        """A highlighted node is filled with the navy shield; its label used to inherit the page ink and vanish (OG-270)."""
        base = _flow()
        nodes = [replace(n, highlight=(i == 1)) for i, n in enumerate(base.nodes)]
        svg = visual.render(replace(base, nodes=nodes))
        classes = {label: cls for cls, label in re.findall(r'<text[^>]*class="(node-label[^"]*)"[^>]*>(Step \d)</text>', svg)}
        self.assertEqual(classes["Step 1"], "node-label node-label-hl")
        self.assertEqual(classes["Step 0"], "node-label", "an ordinary node keeps the page ink")
        rule = re.search(r"\.node-label-hl\{fill:var\(--on-shield,(#[0-9A-Fa-f]{6})\);\}", svg)
        self.assertIsNotNone(rule, "the light ink is declared")
        assert rule is not None
        shield = json.loads((_REPO / "tools" / "docgen" / "assets" / "tokens.json").read_text(encoding="utf-8"))["brand"]["shield"]
        ink, fill = figure_support.parse_color(rule.group(1)), figure_support.parse_color(shield)
        assert ink is not None and fill is not None
        ratio = figure_support.contrast_ratio(ink, fill)
        self.assertGreaterEqual(ratio, 4.5, f"label ink {rule.group(1)} on the shield {shield} is {ratio:.2f}:1")

    def test_a_message_label_that_crosses_a_lifeline_cuts_it_instead_of_being_struck_through(self) -> None:
        """The dashed lifeline ran through the letters of a label centred on it (OG-271)."""
        def spans(spec: SequenceSpec) -> dict[str, list[tuple[float, float]]]:
            svg = sequence_diagram.render(spec)
            out: dict[str, list[tuple[float, float]]] = {}
            for x, y0, y1 in re.findall(r'<line class="lifeline" x1="([\d.]+)" y1="([\d.]+)" x2="[\d.]+" y2="([\d.]+)"', svg):
                out.setdefault(x, []).append((float(y0), float(y1)))
            return out

        actors = [Actor(id="a", label="a"), Actor(id="b", label="b"), Actor(id="c", label="c")]
        crossing = SequenceSpec(
            id="cross", title="", caption="", width=900.0, height=300.0, actors=actors,
            messages=[Message(src="a", dst="c", label="a label centred on the middle participant", order=1)],
        )
        by_x = spans(crossing)
        self.assertEqual([len(v) for _x, v in sorted(by_x.items(), key=lambda kv: float(kv[0]))], [1, 2, 1])
        upper, lower = by_x["450"]
        self.assertGreater(lower[0] - upper[1], 8.0, "the gap is wider than a hairline: it clears the glyphs")
        # a label that crosses nothing leaves every lifeline whole
        clear = SequenceSpec(
            id="clear", title="", caption="", width=900.0, height=300.0, actors=actors,
            messages=[Message(src="a", dst="b", label="ok", order=1)],
        )
        self.assertEqual([len(v) for v in spans(clear).values()], [1, 1, 1])

    def test_a_figure_whose_marks_have_no_numbers_has_no_empty_value_column(self) -> None:
        """A tree's marks carry paths, not values: the table had a 'Value' column with nothing under it (OG-272)."""
        def table(marks: list[tuple[str, str, str]]) -> str:
            return components.figure("<svg></svg>", "cap", fig_id="fig-x", number=1, kind="tree", marks=marks)

        none = table([("Plan", "", "6 children"), ("W1", "", "path: Plan")])
        self.assertNotIn(">Value<", none)
        self.assertEqual(none.count("<td>"), 2, "one cell per row: what it tells you")
        some = table([("a", "12", "x"), ("b", "", "y")])
        self.assertIn(">Value<", some)
        self.assertEqual(some.count("<td>"), 4)


_DOC = """---
id: WF-901
classification: public
title: Figure system fixture
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-10-10
---

# Figure system fixture

## First section

The pipeline is shown in [[fig:flow]], and the exchange in [[fig:seq]].

<!-- figure:flow -->

## Second section

<!-- figure:seq -->

Back to [[fig:flow]] once more.
"""


def _spec_json(flow_id: str = "flow", seq_id: str = "seq") -> list[dict[str, Any]]:
    flow = _flow(flow_id)
    seq = _seq(seq_id)
    return [
        {
            "id": flow.id, "kind": "flowchart", "title": flow.title, "caption": "Fig. 9 - The pipeline",
            "width": flow.width, "height": flow.height, "motion": True,
            "reader_question": "What happens, in order?", "insight": "Four stages.",
            "legend": [{"kind": "node", "key": "process", "label": "A pipeline step"}],
            "nodes": [{"id": n.id, "type": "process", "label": n.label, "x": n.x, "y": n.y, "w": n.w, "h": n.h}
                      for n in flow.nodes],
            "edges": [{"src": e.src, "dst": e.dst, "label": e.label, "main": True, "note": e.note} for e in flow.edges],
        },
        {
            "id": seq.id, "kind": "sequence", "title": seq.title, "caption": "The exchange",
            "width": seq.width, "height": seq.height,
            "actors": [{"id": a.id, "label": a.label} for a in seq.actors],
            "messages": [{"src": m.src, "dst": m.dst, "label": m.label, "order": m.order, "style": m.style,
                          "kind": m.kind, "note": "why"} for m in seq.messages],
        },
    ]


class TextAndPicturesPointAtEachOther(unittest.TestCase):
    """One document with two sections and two figures, built for real (html + blueprint)."""

    html: str
    blueprint: dict[str, Any]
    out: Path

    @classmethod
    def setUpClass(cls) -> None:
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        cls.out = Path(tempfile.mkdtemp(dir=scratch))
        md = cls.out / "doc.md"
        md.write_text(_DOC, encoding="utf-8")
        (cls.out / "doc_spec.json").write_text(json.dumps(_spec_json()), encoding="utf-8")
        result = generator.build(md, formats=("html", "blueprint"), out_dir=cls.out)
        assert result.ok, [f.message for f in result.gate.findings]
        cls.html = result.outputs["html"].read_text(encoding="utf-8")
        cls.blueprint = json.loads(result.outputs["blueprint"].read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_figures_are_numbered_in_placement_order_with_their_own_anchors(self) -> None:
        self.assertIn('<figure class="doc-figure" id="fig-flow"', self.html)
        self.assertIn('<figure class="doc-figure" id="fig-seq"', self.html)
        self.assertRegex(self.html, r'<a class="fig-num" href="#fig-flow" data-ref="fig-flow">Fig\. 1</a>')
        self.assertRegex(self.html, r'<a class="fig-num" href="#fig-seq" data-ref="fig-seq">Fig\. 2</a>')
        self.assertNotIn("Fig. 9", self.html, "a hand-written number in a caption is replaced by the document's own")

    def test_sections_are_link_targets_and_list_the_figures_they_hold(self) -> None:
        self.assertIn('<section class="doc-section" id="sec-first-section">', self.html)
        self.assertIn('<section class="doc-section" id="sec-second-section">', self.html)
        self.assertRegex(self.html, r'class="fig-chip" href="#fig-flow"')
        self.assertRegex(self.html, r'class="fig-chip" href="#fig-seq"')

    def test_each_figure_links_back_to_its_section(self) -> None:
        self.assertRegex(self.html, r'class="fig-up" href="#sec-first-section"')
        self.assertRegex(self.html, r'class="fig-up" href="#sec-second-section"')

    def test_prose_references_become_links_and_the_markers_are_gone(self) -> None:
        self.assertEqual(self.html.count('<a class="fig-ref" href="#fig-flow" data-ref="fig-flow">Fig. 1</a>'), 2)
        self.assertEqual(self.html.count('<a class="fig-ref" href="#fig-seq" data-ref="fig-seq">Fig. 2</a>'), 1)
        self.assertNotIn("[[fig:", self.html)

    def test_every_numbered_circle_points_at_a_line_of_the_key_that_exists(self) -> None:
        declared = set(_ID.findall(self.html))
        for target in re.findall(r'<a class="fig-badge" href="#([^"]+)"', self.html):
            self.assertIn(target, declared, f"badge links to a missing key line {target}")
        self.assertIn('<summary>What the numbers mean</summary>', self.html)
        self.assertIn("what happens at step 1", self.html)

    def test_a_legend_the_figure_draws_itself_is_not_printed_a_second_time_under_the_caption(self) -> None:
        self.assertIn('<g class="legend"', self.html)
        self.assertIn("A pipeline step", self.html)
        self.assertNotIn('<span class="figure-legend-item">', self.html, "a second, unstyled copy read as a stray line (OG-272)")

    def test_no_id_is_declared_twice_in_the_whole_document(self) -> None:
        dupes = [i for i, n in Counter(_ID.findall(self.html)).items() if n > 1]
        self.assertEqual(dupes, [])

    def test_the_runtime_is_injected_once_and_only_because_figures_exist(self) -> None:
        self.assertEqual(self.html.count("window.__veFigures"), 2, "guard check + assignment, one copy")
        self.assertNotRegex(self.html, r"<script[^>]*\bsrc=", "inline, never loaded from anywhere")

    def test_the_blueprint_is_the_machine_twin_of_the_same_render(self) -> None:
        bp = self.blueprint
        self.assertEqual(bp["schema"], "ultimate-engine/blueprint/1")
        self.assertEqual(bp["document"]["id"], "WF-901")
        self.assertEqual([f["number"] for f in bp["figures"]], [1, 2])
        self.assertEqual([s["id"] for s in bp["sections"]], ["sec-first-section", "sec-second-section"])
        self.assertEqual(bp["counts"], {"sections": 2, "figures": 2, "references": 3, "links": len(bp["links"])})
        flow = bp["figures"][0]
        self.assertEqual(len(flow["key"]), 3)
        self.assertEqual(flow["reader_question"], "What happens, in order?")
        self.assertIn("The pipeline", flow["caption"].replace("Fig. 9 - ", "The pipeline") or "")
        kinds = {(link["kind"], link["from"], link["to"]) for link in bp["links"]}
        self.assertIn(("contains", "sec-first-section", "fig-flow"), kinds)
        self.assertIn(("described-by", "fig-flow", "sec-first-section"), kinds)
        self.assertIn(("references", "sec-second-section", "fig-flow"), kinds)
        self.assertIn("[[fig:flow]]", bp["sections"][0]["markdown"], "sections carry their Markdown source")


class TheDocumentRefusesWhatItCannotLink(unittest.TestCase):
    def _build(self, body: str, spec: list[dict[str, Any]] | None = None) -> None:
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            md = out / "doc.md"
            md.write_text(_DOC.split("# Figure system fixture")[0] + "# t\n\n" + body, encoding="utf-8")
            (out / "doc_spec.json").write_text(json.dumps(spec if spec is not None else _spec_json()), encoding="utf-8")
            generator.build(md, formats=("html",), out_dir=out)
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_a_reference_to_a_figure_the_document_does_not_place_is_refused(self) -> None:
        with self.assertRaises(BuildBlockedError) as caught:
            self._build("See [[fig:ghost]].\n\n<!-- figure:flow -->\n\n<!-- figure:seq -->\n")
        self.assertIn("ghost", str(caught.exception))

    def test_a_figure_placed_twice_is_refused_because_it_would_print_one_id_twice(self) -> None:
        with self.assertRaises(BuildBlockedError) as caught:
            self._build("<!-- figure:flow -->\n\n<!-- figure:flow -->\n\n<!-- figure:seq -->\n")
        self.assertIn("placed twice", str(caught.exception))

    def test_figures_whose_ids_normalize_to_one_dom_id_are_refused(self) -> None:
        """OG-276: ``A_B`` and ``A-B`` are both legal ids and both become ``fig-a-b`` — one anchor, one SVG scope, two figures."""
        base = _spec_json()
        flow_a = dict(base[0], id="A_B")
        flow_b = dict(base[0], id="A-B")
        with self.assertRaises(BuildBlockedError) as caught:
            self._build("<!-- figure:A_B -->\n\n<!-- figure:A-B -->\n", [flow_a, flow_b])
        message = str(caught.exception)
        self.assertIn("fig-a-b", message)
        self.assertIn("A_B", message)
        self.assertIn("A-B", message)

    def test_a_figure_already_named_with_the_fig_prefix_collides_with_its_unprefixed_twin(self) -> None:
        base = _spec_json()
        with self.assertRaises(BuildBlockedError):
            self._build("<!-- figure:flow -->\n\n<!-- figure:fig-flow -->\n", [dict(base[0], id="flow"), dict(base[0], id="fig-flow")])

    def test_a_document_without_figures_ships_no_runtime_and_keeps_its_text(self) -> None:
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            md = out / "doc.md"
            md.write_text(_DOC.split("# Figure system fixture")[0] + "# t\n\n## Only text\n\nLiteral [[fig:x]] stays.\n",
                          encoding="utf-8")
            result = generator.build(md, formats=("html",), out_dir=out)
            html = result.outputs["html"].read_text(encoding="utf-8") if "html" in result.outputs else ""
            # An unbound reference table (no figures placed) must refuse rather than print a dead marker.
            self.assertFalse(result.ok and "[[fig:x]]" in html and "fig-ref" in html)
        except BuildBlockedError as exc:
            self.assertIn("x", str(exc))
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_inline_rendering_outside_a_document_leaves_the_marker_alone(self) -> None:
        self.assertEqual(generator._render_inline("see [[fig:flow]]"), "see [[fig:flow]]")


class ASpecTokenCannotBreakOutOfAnAttribute(unittest.TestCase):
    """OG-273: a node's ``tone`` is printed into an SVG ``class`` attribute, so it is a closed vocabulary, not free text."""

    _HOSTILE = 'x" onclick="alert(1)'

    def _node(self, tone: str) -> Any:
        from tools.docgen.models import Node, NodeType

        return Node(id="n", type=NodeType.PROCESS, label="n", x=0.0, y=0.0, tone=tone)

    def test_every_documented_family_and_the_two_sentinels_still_render(self) -> None:
        from tools.docgen.assets import glyphs

        for tone in ("blue", "gold", "green", "red", "bronze", "steel"):
            self.assertIn(f"tone-{tone}", glyphs.glyph_process(self._node(tone)))
        self.assertNotIn("tone-", glyphs.glyph_process(self._node("none")))
        self.assertIn("glyph-process", glyphs.glyph_process(self._node("")))

    def test_the_sink_refuses_a_tone_outside_the_documented_families(self) -> None:
        from tools.docgen.assets import glyphs

        for hostile in (self._HOSTILE, "blue onclick", "BLUE", "tone-blue", "<script>", "a b"):
            with self.assertRaises(ValueError, msg=hostile):
                glyphs.glyph_process(self._node(hostile))

    def test_a_spec_that_carries_such_a_tone_is_refused_at_ingest_with_the_node_named(self) -> None:
        base = _spec_json()
        flow = dict(base[0])
        flow["nodes"] = [dict(n) for n in base[0]["nodes"]]
        flow["nodes"][0]["tone"] = self._HOSTILE
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            md = out / "doc.md"
            md.write_text(_DOC.split("# Figure system fixture")[0] + "# t\n\n## S\n\n<!-- figure:flow -->\n", encoding="utf-8")
            (out / "doc_spec.json").write_text(json.dumps([flow]), encoding="utf-8")
            with self.assertRaises(BuildBlockedError) as caught:
                generator.build(md, formats=("html",), out_dir=out)
            self.assertIn("tone", str(caught.exception))
            self.assertIn(base[0]["nodes"][0]["id"], str(caught.exception))
        finally:
            shutil.rmtree(out, ignore_errors=True)


class ANativeHeatmapsInkSurvivesTheStylesheet(unittest.TestCase):
    """OG-275: a ``fill`` attribute is a presentation attribute and loses to ANY author rule, so the per-cell ink has to ride
    in the element's own ``style`` — the stylesheet's ``.chart-value{fill:currentColor}`` used to paint every value one colour."""

    def test_every_cell_value_carries_its_ink_where_the_stylesheet_cannot_override_it(self) -> None:
        from tools.docgen import charts
        from tools.docgen.models import HeatmapSpec

        spec = HeatmapSpec(
            id="hm", title="t", caption="c", width=520.0, height=300.0,
            row_labels=["a", "b"], col_labels=["x", "y"], matrix=[[0.0, 5.0], [9.0, 11.0]],
            min_value=0.0, max_value=11.0,
        )
        svg = charts.render_heatmap(spec)
        cells = re.findall(r'<text class="chart-value"[^>]*>', svg)
        value_cells = [c for c in cells if 'fill="' in c]
        self.assertEqual(len(value_cells), 4)
        for tag in value_cells:
            attr = re.search(r'fill="([^"]+)"', tag)
            styled = re.search(r'style="[^"]*fill:\s*([^;"]+)', tag)
            self.assertIsNotNone(styled, f"the ink is only a presentation attribute: {tag}")
            assert attr is not None and styled is not None
            self.assertEqual(styled.group(1).strip(), attr.group(1))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
