"""The ELK bridge must hand docgen a layout whose same-row nodes clear its gap rule, whatever the graph.

Measured 2026-10-10: after the engine gained a module, `blueprint layout` failed with
``Node gap 32.00px between 'tools.corpus_check.guards' and 'tools.project_index' below required 72.00px``. ELK spaces
two neighbours by ``elk.spacing.nodeNode`` (100) — but two nodes with a routed edge BETWEEN them are separated by that
edge's dummy node and ELK then uses the edge-to-node distance (10 px default), so 32 px came out. Raising an option would
not close the class (the next arrangement finds the next dummy); `elk_layout.mjs` now legalises each row deterministically.

``elk_gap_fixture.json`` is the exact graph that produced the 32 px gap: red before the legalisation, green after.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from itertools import pairwise
from pathlib import Path
from typing import Any

from tools.blueprint import layout

_BRIDGE = Path(layout.__file__).resolve().parent / "elk_layout.mjs"
_FIXTURE = Path(__file__).resolve().parent / "elk_gap_fixture.json"
_DOCGEN_MIN_GAP_PX = 72  # 1.5 x the larger short side of 48 px boxes (visual.check_collisions rule c)
_MIN_GAP_PX = 100


def _place(payload: dict[str, Any]) -> dict[str, Any]:
    usable, why = layout.available()
    if not usable:
        raise unittest.SkipTest(f"ELK bridge unavailable: {why}")
    from tools.docgen import engine_config

    node = engine_config.tool_path("node")
    assert node is not None
    proc = subprocess.run(
        [node, str(_BRIDGE)], input=json.dumps(payload), capture_output=True, text=True, check=True, timeout=120
    )
    out: dict[str, Any] = json.loads(proc.stdout)
    return out


class SameRowNodesClearTheGapRule(unittest.TestCase):
    def _worst_row_gap(self, placed: list[dict[str, int]]) -> int:
        rows: dict[int, list[dict[str, int]]] = {}
        for p in placed:
            rows.setdefault(p["y"], []).append(p)
        worst = 10**9
        for row in rows.values():
            row.sort(key=lambda p: p["x"])
            for left, right in pairwise(row):
                worst = min(worst, right["x"] - (left["x"] + left["width"]))
        return worst

    def test_the_graph_that_produced_a_32px_gap_now_clears_the_rule(self) -> None:
        payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        result = _place(payload)
        self.assertTrue(result["ok"])
        nodes = result["nodes"]
        self.assertEqual(len(nodes), len(payload["nodes"]))
        worst = self._worst_row_gap(nodes)
        self.assertGreaterEqual(worst, _DOCGEN_MIN_GAP_PX, f"a same-row gap of {worst}px is below docgen's rule")
        self.assertGreaterEqual(worst, _MIN_GAP_PX)

    def test_the_reported_width_covers_every_node(self) -> None:
        result = _place(json.loads(_FIXTURE.read_text(encoding="utf-8")))
        right_edge = max(p["x"] + p["width"] for p in result["nodes"])
        self.assertGreaterEqual(result["width"], right_edge, "legalising shifted nodes past the canvas the layout reports")

    def test_a_layout_is_deterministic(self) -> None:
        payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(_place(payload), _place(payload))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
