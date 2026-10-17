"""The figure runtime in a real browser (OG-250 … OG-261).

Hover colour, flicker, adjacency, tooltips, pinning and keyboard focus cannot be known from bytes. This test builds one
document that mixes native diagrams with engine charts and drives it with real pointer and keyboard events in headless
Chromium (``tools/tests/browser/figure_runtime_check.mjs``).

It SKIPS — with the cause, never a silent pass — when node, the chart engine's dependencies, Playwright or a Chromium
build are absent. The three defects it exists for all passed every byte-level test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.docgen import echarts_bridge, generator
from tools.tests import test_figure_system as fixtures

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "tools" / "tests" / "browser" / "figure_runtime_check.mjs"
_GOLDEN = _REPO / "tools" / "visual-engine" / "renders" / "golden"
_SKIP_EXIT = 3


def _chart(fig_id: str, golden: str, caption: str) -> dict[str, Any]:
    job = json.loads((_GOLDEN / f"{golden}.job.json").read_text(encoding="utf-8"))
    job["classification"] = "public"
    return {
        "id": fig_id, "kind": "echarts", "caption": caption, "job": job,
        "data_sources": [{"kind": "metric", "ref": "engine golden fixture", "retrieved": "2026-10-10"}],
    }


class FigureRuntimeInARealBrowser(unittest.TestCase):
    def test_runtime_behaves_in_chromium(self) -> None:
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
            spec = fixtures._spec_json() + [
                _chart("graph", "SIM-04-workflow-pipeline", "Pipeline graph"),
                _chart("bars", "SIM-17-svg", "Horizontal bars"),
                _chart("lines", "SIM-08-queue-latency", "Queue latency"),
                {
                    "id": "heat", "kind": "heatmap", "title": "A native heatmap", "caption": "Light and dark cells",
                    "row_labels": ["a", "b"], "col_labels": ["x", "y"], "matrix": [[0, 5], [9, 11]],
                    "min_value": 0, "max_value": 11,
                    "data_sources": [{"kind": "metric", "ref": "browser fixture", "retrieved": "2026-10-10"}],
                },
            ]
            body = (
                fixtures._DOC.rstrip()
                + "\n\n## 3. Charts\n\nSee [[fig:graph]] and [[fig:bars]].\n\n"
                "<!-- figure:graph -->\n\n<!-- figure:bars -->\n\n<!-- figure:lines -->\n\n<!-- figure:heat -->\n"
            )
            md = out / "doc.md"
            md.write_text(body, encoding="utf-8")
            (out / "doc_spec.json").write_text(json.dumps(spec), encoding="utf-8")
            result = generator.build(md, formats=("html",), out_dir=out)
            self.assertTrue(result.ok, [f.message for f in result.gate.findings])
            proc = subprocess.run(
                [node, str(_SCRIPT), str(result.outputs["html"])], capture_output=True, text=True, timeout=240, check=False
            )
            if proc.returncode == _SKIP_EXIT:
                self.skipTest(proc.stdout.strip() or "no browser available")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertGreaterEqual(proc.stdout.count("PASS"), 40, proc.stdout)
            self.assertNotIn("FAIL", proc.stdout)
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
