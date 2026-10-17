"""Labels must fit the picture they are in (OG-292).

The census report was the first document to draw a radar with long axis names and a layered diagram with eleven nodes. The radar cut
its names off at the canvas edge, the layered diagram drew every plane eleven columns wide (past the canvas) and ran a long node label
through its box into the next one — all with no error. These tests build the real figures and read the geometry back.
"""

from __future__ import annotations

import hashlib
import re
import unittest

from tools.docgen import charts, layered_workflow, models

_LONG_AXES = [
    "Markdown documents with a title (1,287 of 1,290)",
    "Relative links that resolve (3,386 of 3,415)",
    "Live documents updated recently (331 of 771)",
    "Source-of-truth stamps that still hold (0 of 53)",
    "Authoritative documents other live documents cite (171 of 200)",
    "Code packages named by a live document (31 of 31)",
]


def _radar(axes: list[str], width: float = 560.0, height: float = 560.0) -> models.RadarSpec:
    return models.RadarSpec(
        id="r", title="t", caption="c", width=width, height=height, max_value=100, axes=axes,
        series=[models.RadarSeries(label="s", values=[50.0] * len(axes))], legend=[],
    )


class RadarAxisNamesStayOnTheCanvas(unittest.TestCase):
    def test_long_names_are_wrapped_and_every_line_is_inside_the_canvas(self) -> None:
        spec = _radar(_LONG_AXES)
        radius, placed = charts._radar_placements(spec)
        self.assertLess(radius, min(spec.width, spec.height) / 2 - 64.0, "the ring should have shrunk to make room")
        for (lines, _x, _y, _anchor, box), name in zip(placed, spec.axes, strict=True):
            self.assertGreaterEqual(box[0], 6.0, name)
            self.assertLessEqual(box[2], spec.width - 6.0, name)
            self.assertGreater(len(lines), 1, f"{name!r} should be wrapped")
        svg = charts.render_radar(spec)
        for name in spec.axes:
            self.assertIn(name.split(" ")[0], svg)

    def test_a_radar_whose_names_already_fit_is_drawn_exactly_as_it_always_was(self) -> None:
        svg = charts.render_radar(_radar(["a", "b", "c", "d", "e"]))
        # Hash of the output before the fix (the axis names were centred, one line, 22 px past the ring): unchanged.
        self.assertEqual(hashlib.sha256(svg.encode()).hexdigest()[:12], "dbc379efaabd")

    def test_a_name_that_cannot_fit_even_wrapped_is_refused_not_clipped(self) -> None:
        spec = _radar(["x" * 400, "b", "c"], width=240.0, height=240.0)
        with self.assertRaises(charts.ChartRuleError):
            charts.render_radar(spec)


def _layered(n_nodes: int, label: str = "area") -> models.LayeredSpec:
    nodes = [models.LayerNode(id=f"n{i}", label=f"{label} {i}", layer=i % 3, col=i // 3) for i in range(n_nodes)]
    return models.LayeredSpec(
        id="l", title="t", caption="c", layer_labels=["a", "b", "c"], nodes=nodes, connectors=[models.LayerConnector(src="n0", dst="n1")],
        width=900.0, height=480.0,
    )


class LayeredDiagramsFitTheirCanvas(unittest.TestCase):
    def test_a_plane_spans_its_own_columns_not_the_whole_figure_s_node_count(self) -> None:
        svg = layered_workflow.render(_layered(11))
        widths = [float(w) for w in re.findall(r'class="layer-plane"[^>]*width="([0-9.]+)"', svg)]
        self.assertTrue(widths)
        for w in widths:
            self.assertLess(w, 900.0, "a plane wider than the canvas runs off its edge")

    def test_a_long_node_label_is_wrapped_inside_its_box_and_keeps_its_full_text_in_a_title(self) -> None:
        lines, font = layered_workflow._node_lines("skills/doc-lifecycle · 1")
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(len(line) * font * 0.62, layered_workflow._NODE_W, line)
        svg = layered_workflow.render(_layered(3, label="skills/doc-lifecycle-and-more"))
        self.assertIn("<title>skills/doc-lifecycle-and-more 0</title>", svg)

    def test_a_label_that_fits_is_one_unchanged_line(self) -> None:
        self.assertEqual(layered_workflow._node_lines("dir / file"), (["dir / file"], 12.0))

    def test_nodes_are_filled_so_a_connector_never_runs_through_a_label(self) -> None:
        self.assertIn(".lnode{fill:var(--paper", layered_workflow._defs_css())

    def test_a_plane_s_name_is_drawn_after_the_connectors_and_knocked_out_of_them(self) -> None:
        svg = layered_workflow.render(_layered(6))
        self.assertGreater(len(re.findall(r'class="lconn"', svg)), 0)
        for body in svg.split('<g class="layered-')[1:]:
            last_connector = body.rfind('class="lconn"')
            first_heading = body.find('class="layer-label"')
            self.assertGreater(first_heading, last_connector, "a heading drawn before a connector is struck through by it")
            self.assertLess(first_heading, body.find('class="lnode"'), "the nodes stay on top of everything")
        css = layered_workflow._defs_css()
        self.assertIn("paint-order:stroke", css.split(".layer-label{", 1)[1].split("}", 1)[0])


if __name__ == "__main__":
    unittest.main()
