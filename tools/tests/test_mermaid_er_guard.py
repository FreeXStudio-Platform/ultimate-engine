"""An ER diagram that lost relationships must fail the build (OG-292).

The Mermaid renderer drops a relationship line it cannot place, silently: six declared, three drawn, and an entity whose only
relationship was dropped is gone from the picture. ``check_er_relationships`` compares what the source declares with what the SVG draws.
"""

from __future__ import annotations

import unittest

from tools.docgen import mermaid_bridge as mb

_ER = """erDiagram
    DOCUMENT ||--o{ LINK : contains
    DOCUMENT }o--o{ DOCUMENT : cites
    DOCUMENT }o--|| AREA : "lives in"
    DOCUMENT ||--o| STAMP : "may carry"
    DOCUMENT {
        int total "10"
    }
"""


def _svg(n: int) -> str:
    return "<svg>" + '<g class="er-relationship"/>' * n + "</svg>"


class AnErDiagramMustDrawEveryRelationshipItDeclares(unittest.TestCase):
    def test_a_diagram_that_dropped_relationships_is_refused_with_the_way_out(self) -> None:
        with self.assertRaises(mb.MermaidRenderError) as ctx:
            mb.check_er_relationships("fig", _ER, _svg(2))
        msg = str(ctx.exception)
        self.assertIn("declares 4", msg)
        self.assertIn("drew 2", msg)
        self.assertIn("}o", msg)

    def test_a_diagram_that_drew_them_all_passes(self) -> None:
        mb.check_er_relationships("fig", _ER, _svg(4))

    def test_other_diagram_types_are_not_inspected(self) -> None:
        mb.check_er_relationships("fig", "graph LR\n  A --> B", "<svg/>")

    def test_attribute_blocks_are_not_counted_as_relationships(self) -> None:
        mb.check_er_relationships("fig", "erDiagram\n    A {\n        int x \"1\"\n    }\n", "<svg/>")

    @unittest.skipUnless(mb.engine_available()[0], "the Mermaid engine is not installed here")
    def test_the_real_renderer_trips_the_guard_on_the_documented_defect(self) -> None:
        with self.assertRaises(mb.MermaidRenderError):
            mb.render(mb.MermaidFigureSpec(id="er", caption="c", code=_ER))

    @unittest.skipUnless(mb.engine_available()[0], "the Mermaid engine is not installed here")
    def test_the_real_renderer_draws_the_supported_forms(self) -> None:
        code = "erDiagram\n    A ||--o{ B : has\n    B ||--o{ A : owns\n    A ||--o| C : may\n"
        self.assertIn("er-relationship", mb.render(mb.MermaidFigureSpec(id="er", caption="c", code=code)))


if __name__ == "__main__":
    unittest.main()
