"""The module explorer in a real browser (tools/tests/browser/explorer_check.mjs).

The zoom, the labels that follow the camera, the arrows on hover, the panel, the reader, the keyboard, reduced motion, the
phone layout, print and the no-script outline are not knowable from bytes. This builds one document with one explorer and
drives it with real pointer and keyboard events in headless Chromium.

It SKIPS — with the cause, never a silent pass — when node, Playwright or a Chromium build is absent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.docgen import generator
from tools.tests import test_figure_system as fixtures

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "tools" / "tests" / "browser" / "explorer_check.mjs"
_SKIP_EXIT = 3


def browser_spec() -> dict[str, Any]:
    """system > api (routes (handlers, schemas), deps), db (models), bank: three levels, a cross-branch edge, a document."""
    return {
        "id": "map", "kind": "explorer", "title": "The system, from far to near", "caption": "How big each part is",
        "reader_question": "What are the parts of the system and what does each one call?",
        "insight": "Most of the code sits in one part.",
        "data_sources": [{"kind": "metric", "ref": "browser fixture", "retrieved": "2026-10-10"}],
        "unit": "lines of code",
        "statuses": [
            {"key": "CLEAN", "label": "clean", "tone": "green", "detail": "no leaks"},
            {"key": "LEAKY", "label": "leaky", "tone": "gold"},
            {"key": "ENTANGLED", "label": "entangled", "tone": "red"},
            {"key": "NOT_BUILT", "label": "not built", "tone": "steel"},
            {"key": "OUT", "label": "outside the repo", "tone": "blue"},
        ],
        "kinds": [{"key": "leak", "label": "not declared", "tone": "red"}, {"key": "declared", "label": "declared", "tone": "blue"}],
        "root": {
            "id": "system", "name": "The system", "kicker": "System", "summary": "Three modules.",
            "children": [
                {"id": "api", "name": "Ingress & API", "kicker": "Module", "status": "LEAKY", "summary": "The public door.",
                 "facts": [["Files", "128"]], "lists": [{"title": "Invariants", "items": ["Enters only through a port."]}],
                 "docs": ["d-api"], "refs": [{"label": "Section 8", "href": "#sec-1"}],
                 "children": [
                     {"id": "api.routes", "name": "routes", "status": "ENTANGLED", "children": [
                         {"id": "api.routes.handlers", "name": "handlers", "value": 6000},
                         {"id": "api.routes.schemas", "name": "schemas", "value": 3000}]},
                     {"id": "api.deps", "name": "deps", "value": 3000}]},
                {"id": "db", "name": "Persistence", "kicker": "Module", "status": "CLEAN",
                 "children": [{"id": "db.models", "name": "models", "value": 4000}]},
                {"id": "bank", "name": "Contract bank", "kicker": "Module", "status": "NOT_BUILT", "value": 1500},
                {"id": "tiny", "name": "Telemetryinstrumentation", "kicker": "Module", "status": "CLEAN", "value": 600},
            ],
        },
        "edges": [
            {"src": "api", "dst": "db", "weight": 12, "kind": "declared"},
            {"src": "db", "dst": "api", "weight": 2, "kind": "leak"},
            {"src": "api.routes", "dst": "api.deps", "weight": 5},
        ],
        "documents": [{"id": "d-api", "title": "Ingress & API — dossier", "sources": ["docs/design/MODULAR_ARCHITECTURE.md"],
                       "blocks": [{"t": "h", "text": "What it is"}, {"t": "p", "text": "The public door."},
                                  {"t": "ul", "items": ["a", "b"]}, {"t": "kv", "rows": [["Files", "128"]]},
                                  {"t": "table", "head": ["Package", "Lines"], "rows": [["routes", "9,000"]]}]}],
    }


class ExplorerInARealBrowser(unittest.TestCase):
    def test_explorer_behaves_in_chromium(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not on PATH")
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            body = fixtures._DOC.split("## First section")[0] + "## 1. The map\n\nExplore [[fig:map]] below.\n\n<!-- figure:map -->\n"
            md = out / "doc.md"
            md.write_text(body, encoding="utf-8")
            (out / "doc_spec.json").write_text(json.dumps([browser_spec()]), encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
