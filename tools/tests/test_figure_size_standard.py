"""The figure SIZE STANDARD (FS-1 … FS-5, docs/design/FIGURE_SYSTEM.md §12) and the diagram look that rides with it.

Measured on the 2026-10-10 report (OG-277): a native diagram is a bare ``viewBox`` with no size of its own, so the page
stretched it to the width of the column — 960x740 became 1150x886 (x1.2), taller than a laptop screen, while the build
before it had drawn the same picture at x0.61 (text 7px). Nobody had decided a size; the column had. The standard decides:

* FS-1 never larger than the picture's own design size times a stated enlargement ceiling (1 for an engine chart, 1.3 for
  a diagram that was drawn on an abstract canvas);
* FS-2 a landscape figure fits one screen: its height never exceeds ``min(82vh, 700px)``;
* FS-3 ... but never shrinks below 80% of its design size, so a 12px label stays above 9px (the page scrolls instead);
* FS-4 a tall figure (height >= 90% of width) is read by scrolling and is exempt from FS-2;
* FS-5 no figure is wider than 1150px, whatever the monitor.

These tests pin the arithmetic the document hands to the stylesheet and the stylesheet's own text; the real-browser
check (``test_figure_size_browser``) pins what Chromium actually draws at four viewports. Every case turns red when its fix
is reverted.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.docgen import (
    components,
    echarts_bridge,
    figure_support,
    generator,
    tokens,
    visual,
)
from tools.docgen.models import Edge, Node, NodeType, VisualSpec
from tools.tests import test_figure_system as fixtures

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "tools" / "tests" / "browser" / "figure_size_check.mjs"
_GOLDEN = _REPO / "tools" / "visual-engine" / "renders" / "golden"
_SKIP_EXIT = 3


def _svg(width: float, height: float, *, natural: bool = False) -> str:
    size = f' width="{width:g}" height="{height:g}"' if natural else ""
    return f'<svg viewBox="0 0 {width:g} {height:g}"{size} xmlns="http://www.w3.org/2000/svg"></svg>'


def _wrap_attrs(html: str) -> str:
    """The opening tag of the first ``.svgwrap`` in ``html``."""
    match = re.search(r'<div class="svgwrap[^"]*"[^>]*>', html)
    assert match, html
    return match.group(0)


class TheDocumentReadsEachPicturesDesignSize(unittest.TestCase):
    def test_a_bare_viewbox_is_a_diagram_with_no_size_of_its_own(self) -> None:
        geo = figure_support.figure_geometry(_svg(960, 740))
        assert geo is not None
        self.assertEqual((geo.width, geo.height, geo.natural), (960.0, 740.0, False))

    def test_a_declared_pixel_size_makes_a_picture_natural_size(self) -> None:
        geo = figure_support.figure_geometry(_svg(620, 380, natural=True))
        assert geo is not None
        self.assertEqual((geo.width, geo.height, geo.natural), (620.0, 380.0, True))

    def test_a_picture_without_a_viewbox_is_left_alone_not_guessed(self) -> None:
        self.assertIsNone(figure_support.figure_geometry('<svg width="10" height="10"></svg>'))
        self.assertIsNone(figure_support.figure_geometry("<p>not a picture</p>"))
        self.assertIsNone(figure_support.figure_geometry('<svg viewBox="0 0 0 0"></svg>'))

    def test_only_the_root_element_is_read(self) -> None:
        # a nested <svg> (an icon inside a Mermaid node) must not be taken for the picture
        svg = '<svg viewBox="0 0 800 400"><g><svg viewBox="0 0 24 24" width="24" height="24"></svg></g></svg>'
        geo = figure_support.figure_geometry(svg)
        assert geo is not None
        self.assertEqual((geo.width, geo.height, geo.natural), (800.0, 400.0, False))


class TheFigureBlockHandsTheStandardTheNumbers(unittest.TestCase):
    def _figure(self, svg: str, kind: str) -> str:
        return components.figure(svg, "A caption", fig_id="fig-x", number=1, kind=kind)

    def test_a_native_diagram_may_be_enlarged_up_to_the_ceiling_and_is_landscape(self) -> None:
        wrap = _wrap_attrs(self._figure(_svg(960, 740), "flowchart"))
        self.assertIn("svgwrap--sized", wrap)
        self.assertIn("--fw:960", wrap)
        self.assertIn("--fh:740", wrap)
        self.assertIn(f"--up:{figure_support.FIG_UP_SCALED:g}", wrap)
        self.assertNotIn("svgwrap--tall", wrap)

    def test_a_tall_diagram_is_never_enlarged_because_it_is_already_as_tall_as_it_should_be(self) -> None:
        wrap = _wrap_attrs(self._figure(_svg(700, 900), "flowchart"))
        self.assertIn("svgwrap--tall", wrap)
        self.assertIn("--up:1", wrap)
        self.assertNotIn(f"--up:{figure_support.FIG_UP_SCALED:g}", wrap)

    def test_an_engine_chart_is_never_enlarged(self) -> None:
        wrap = _wrap_attrs(self._figure(_svg(620, 380, natural=True), "echarts"))
        self.assertIn("--up:1", wrap)
        self.assertNotIn(f"--up:{figure_support.FIG_UP_SCALED:g}", wrap)

    def test_a_tall_figure_is_exempt_from_the_screen_fit(self) -> None:
        for w, h in ((620, 640), (673, 1307), (900, 810)):
            self.assertIn("svgwrap--tall", _wrap_attrs(self._figure(_svg(w, h, natural=True), "mermaid")), (w, h))
        for w, h in ((960, 740), (620, 380), (900, 809)):
            self.assertNotIn("svgwrap--tall", _wrap_attrs(self._figure(_svg(w, h, natural=True), "mermaid")), (w, h))

    def test_a_picture_the_document_cannot_measure_is_not_given_invented_numbers(self) -> None:
        html = self._figure('<svg width="10" height="10"></svg>', "mermaid")
        self.assertNotIn("--fw", html)
        self.assertNotIn("svgwrap--sized", html)

    def test_the_same_numbers_ride_on_a_figure_that_has_no_id(self) -> None:
        html = components.figure(_svg(960, 740), "caption")
        self.assertIn("svgwrap--sized", _wrap_attrs(html))
        self.assertIn("--fw:960", _wrap_attrs(html))


class TheBlueprintGridBelongsToNodeAndEdgeDiagramsOnly(unittest.TestCase):
    def test_flow_and_state_diagrams_sit_on_the_grid(self) -> None:
        for kind in sorted(figure_support.GRID_KINDS):
            wrap = _wrap_attrs(components.figure(_svg(960, 740), "c", fig_id="fig-x", number=1, kind=kind))
            self.assertIn("svgwrap--grid", wrap, kind)

    def test_charts_sequences_and_foreign_engines_do_not(self) -> None:
        for kind in ("echarts", "sequence", "mermaid", "sankey", "heatmap", "radar", ""):
            wrap = _wrap_attrs(components.figure(_svg(900, 540), "c", fig_id="fig-x", number=1, kind=kind))
            self.assertNotIn("svgwrap--grid", wrap, kind)

    def test_the_grid_is_a_faint_wash_of_the_page_ink_not_a_loud_rule(self) -> None:
        css = tokens.build_css()
        block = re.search(r"\.svgwrap--grid\s*\{[^}]*\}", css)
        assert block, "no .svgwrap--grid rule"
        self.assertIn("--grid-line", block.group(0))
        self.assertNotIn("var(--faint)", block.group(0))  # --faint is a hairline BORDER colour: far too loud for a ground
        root = re.search(r"--grid-line:\s*([^;]+);", css)
        assert root, "--grid-line is never defined"
        share = re.search(r"var\(--fg\)\s+(\d+(?:\.\d+)?)%", root.group(1))
        assert share, root.group(1)
        self.assertLessEqual(float(share.group(1)), 8.0)


class TheStylesheetCarriesTheStandardVerbatim(unittest.TestCase):
    def setUp(self) -> None:
        self.css = tokens.build_css()

    def test_the_budget_is_declared_once_in_the_root(self) -> None:
        self.assertRegex(self.css, rf"--fig-max-w:\s*{figure_support.FIG_MAX_W_PX}px")
        self.assertRegex(self.css, rf"--fig-fit-h:\s*min\({figure_support.FIG_FIT_VH}vh,\s*{figure_support.FIG_FIT_H_PX}px\)")
        self.assertRegex(self.css, rf"--fig-min-scale:\s*{figure_support.FIG_MIN_SCALE:g}")

    def test_the_width_is_the_smallest_of_column_ceiling_enlargement_and_screen_fit(self) -> None:
        rule = re.search(r"\.svgwrap--sized svg\s*\{([^}]*)\}", self.css)
        assert rule, "no .svgwrap--sized svg rule"
        body = re.sub(r"\s+", "", rule.group(1))
        self.assertIn("width:min(100%,var(--fig-max-w)", body)  # FS-5 and the column
        self.assertIn("calc(var(--fw)*var(--up,1)*1px)", body)  # FS-1
        self.assertIn("calc(var(--fig-fit-h)*var(--fw)/var(--fh))", body)  # FS-2
        self.assertIn("calc(var(--fw)*var(--fig-min-scale)*1px)", body)  # FS-3

    def test_a_tall_figure_skips_only_the_screen_fit(self) -> None:
        rule = re.search(r"\.svgwrap--sized\.svgwrap--tall svg\s*\{([^}]*)\}", self.css)
        assert rule, "no .svgwrap--tall rule"
        body = re.sub(r"\s+", "", rule.group(1))
        self.assertNotIn("--fig-fit-h", body)
        self.assertIn("var(--fig-max-w)", body)


class ANativeDiagramReadsAsADiagramOnADarkPage(unittest.TestCase):
    def _spec(self) -> VisualSpec:
        nodes = [
            Node(id="a", type=NodeType.PROCESS, label="First", x=60.0, y=120.0, w=120.0, h=56.0),
            Node(id="b", type=NodeType.PROCESS, label="Second", x=360.0, y=120.0, w=120.0, h=56.0),
            Node(id="c", type=NodeType.PROCESS, label="Third", x=660.0, y=120.0, w=120.0, h=56.0),
        ]
        edges = [
            Edge(src="a", dst="b", label="one", main=True, note="a to b"),
            Edge(src="b", dst="c", label="two", main=True, note="b to c"),
        ]
        return VisualSpec(id="t", title="A title", caption="cap", nodes=nodes, edges=edges, width=840.0, height=320.0)

    def test_the_title_carries_a_fill_so_it_is_not_black_on_a_dark_page(self) -> None:
        svg = visual.render(self._spec())
        title = re.search(r'<text[^>]*class="figure-title"[^>]*>', svg)
        assert title, "no title element"
        self.assertIn('fill="currentColor"', title.group(0))

    def test_every_native_title_rule_in_the_stylesheet_paints_with_the_page_ink(self) -> None:
        css = visual._defs_css(None)
        group = re.search(r"([^{}]*\.figure-title[^{}]*)\{([^}]*)\}", css)
        assert group, "the title is not styled at all"
        self.assertIn("fill:currentColor", group.group(2))

    def test_an_edge_label_is_cut_out_of_the_line_it_sits_beside(self) -> None:
        css = visual._defs_css(None)
        rule = re.search(r"\.edge-label,\.edge-condition\{([^}]*)\}", css)
        assert rule, "edge labels are not styled as a pair with their conditions"
        for need in ("paint-order:stroke", "stroke:var(--paper,transparent)", "stroke-width:5px"):
            self.assertIn(need, rule.group(1))

    def test_a_step_number_is_big_enough_to_read_and_to_hit(self) -> None:
        self.assertGreaterEqual(visual._EDGE_BADGE_R, 17.0)  # 34px across at design size: above the 24px target minimum at x0.8
        svg = visual.render(self._spec())
        radii = {float(r) for r in re.findall(r'<circle[^>]*\br="([\d.]+)"[^>]*class="edge-badge"', svg)}
        self.assertEqual(radii, {visual._EDGE_BADGE_R})
        size = re.search(r"\.edge-badge-label\{[^}]*font-size:(\d+(?:\.\d+)?)px", svg)
        assert size, "the badge digit has no size"
        self.assertGreaterEqual(float(size.group(1)), 16.0)

    def test_the_step_digit_stays_centred_in_its_circle(self) -> None:
        svg = visual.render(self._spec())
        circle = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="[\d.]+" class="edge-badge"/>', svg)
        label = re.search(r'<text x="([\d.]+)" y="([\d.]+)" text-anchor="middle" class="edge-badge-label">', svg)
        assert circle and label
        self.assertEqual(circle.group(1), label.group(1))
        # baseline sits about a third of the font size below the centre, so the digit is optically centred
        self.assertAlmostEqual(float(label.group(2)) - float(circle.group(2)), 0.35 * 17.0, delta=1.2)


def _diagram(fig_id: str, kind: str, width: float, height: float) -> dict[str, Any]:
    """A four-box diagram drawn on a ``width`` x ``height`` canvas (a loop around the canvas, so it fills it)."""
    xs = [width * 0.12, width * 0.60, width * 0.60, width * 0.12]
    ys = [height * 0.16, height * 0.16, height * 0.62, height * 0.62]
    nodes = [
        {"id": f"n{i}", "type": "state" if kind == "state" else "process", "label": f"Stage {i + 1}", "x": round(x), "y": round(y), "w": 150, "h": 64}
        for i, (x, y) in enumerate(zip(xs, ys, strict=True))
    ]
    edges = [
        {"src": f"n{i}", "dst": f"n{i + 1}", "label": f"step {i + 1}", "main": True, "note": f"what happens at step {i + 1}"}
        for i in range(3)
    ]
    return {"id": fig_id, "kind": kind, "title": f"A {kind}", "caption": f"A {kind} on a {width:g}x{height:g} canvas",
            "width": width, "height": height, "nodes": nodes, "edges": edges}


class FigureSizeInARealBrowser(unittest.TestCase):
    """What Chromium actually draws, at five viewports, against the standard re-derived from its constants."""

    def test_the_standard_is_what_chromium_draws(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not on PATH")
        ok, why = echarts_bridge.engine_available()
        if not ok:
            self.skipTest(f"chart engine unavailable: {why}")
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            job = json.loads((_GOLDEN / "SIM-17-svg.job.json").read_text(encoding="utf-8"))
            job["classification"] = "public"
            sources = [{"kind": "metric", "ref": "browser fixture", "retrieved": "2026-10-10"}]
            specs: list[dict[str, Any]] = [
                _diagram("flow", "flowchart", 960, 740),  # the report's headline case: was x1.2, 886px high
                _diagram("states", "state", 960, 740),
                _diagram("tallflow", "flowchart", 700, 900),  # tall: exempt from the screen fit
                {"id": "chart", "kind": "echarts", "caption": "A chart", "job": job, "data_sources": sources},
            ]
            seq = fixtures._spec_json()[1]
            seq.update({"id": "seq", "width": 900, "height": 540})
            specs.append(seq)
            doc = fixtures._DOC.split("## First section")[0] + "## Figures\n\n" + "\n\n".join(
                f"<!-- figure:{f['id']} -->" for f in specs
            ) + "\n"
            md = out / "doc.md"
            md.write_text(doc, encoding="utf-8")
            (out / "doc_spec.json").write_text(json.dumps(specs), encoding="utf-8")
            result = generator.build(md, formats=("html",), out_dir=out)
            self.assertTrue(result.ok, [f.message for f in result.gate.findings])
            std = {
                "maxW": figure_support.FIG_MAX_W_PX, "fitVh": figure_support.FIG_FIT_VH, "fitH": figure_support.FIG_FIT_H_PX,
                "minScale": figure_support.FIG_MIN_SCALE, "tall": figure_support.FIG_TALL_RATIO,
            }
            proc = subprocess.run(
                [node, str(_SCRIPT), str(result.outputs["html"]), json.dumps(std)],
                capture_output=True, text=True, timeout=240, check=False,
            )
            if proc.returncode == _SKIP_EXIT:
                self.skipTest(proc.stdout.strip() or "no browser available")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertGreaterEqual(proc.stdout.count("PASS"), 60, proc.stdout)
            self.assertNotIn("FAIL", proc.stdout)
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
