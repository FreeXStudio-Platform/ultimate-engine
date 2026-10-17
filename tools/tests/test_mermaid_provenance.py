"""A Mermaid figure that writes a number into its own text can declare where the number came from (OG-296).

The census report's XY chart carries a month-by-month count. ``MermaidFigureSpec`` had no ``data_sources`` field, so the L16 provenance gate could
refuse the figure and nothing the author wrote could satisfy it.
"""

from __future__ import annotations

import unittest

from tools.docgen import generator

_XY = 'xychart-beta\n    title "Documents added per month"\n    x-axis [2026-01, 2026-02]\n    y-axis "Documents" 0 --> 1290\n    bar [840, 1290]'


class AMermaidFigureCanDeclareItsSources(unittest.TestCase):
    def test_a_sourced_figure_passes_the_provenance_gate(self) -> None:
        spec = generator._mermaid_spec_from_dict(
            {"id": "m", "kind": "mermaid", "code": _XY, "caption": "c", "insight": "1,290 documents were added over the history.", "data_sources": [{"kind": "metric", "ref": "git history", "retrieved": "2026-10-10"}]}
        )
        self.assertEqual(len(spec.data_sources), 1)
        self.assertEqual(generator.check_figure_provenance({"m": ("mermaid", spec)}), [])

    def test_an_unsourced_figure_that_writes_numbers_is_still_flagged(self) -> None:
        spec = generator._mermaid_spec_from_dict({"id": "m", "kind": "mermaid", "code": _XY, "caption": "c", "insight": "1,290 documents were added over the history."})
        findings = generator.check_figure_provenance({"m": ("mermaid", spec)})
        self.assertEqual([f.gate for f in findings], ["figure_provenance"])


if __name__ == "__main__":
    unittest.main()
