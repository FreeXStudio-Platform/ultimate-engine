"""`build_index.py` L14 tier fail-closed exclusion — retained counter-example. Closes the
finding registered as `GAP-build_index-L14-tier-exclusion-untested`.

**Why this file exists.** `build_index.py` never executes anywhere in a full traced
`docgen build` run, and nothing asserted its documented behaviour: "Fail-closed on tier: any
sidecar whose `header.classification` is not exactly `public` is skipped entirely"
(`scan_public_doc_jsons` docstring). Pass 8's worst CRITICAL finding was a `classification:
secret` document escaping a *different* L14 gate on a leading blank line — the same law, on an
adjacent surface, so a defect class that has already happened once here gets its counter-example
on this surface too rather than being assumed safe by analogy.

The probe: plant a `public` sidecar and a byte-identical `secret` twin carrying a distinctive
canary title, run the real ``build_index`` end-to-end (the actual artifact the gate certifies —
not just the scan function in isolation), and assert the canary never appears anywhere in the
rendered index: not as a title, not as a doc id, not indexed at all.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.docgen.build_index import build_index, scan_public_doc_jsons

_CANARY_TITLE = "TOPSECRET-CANARY-TITLE"


def _write_sidecar(build_dir: Path, name: str, *, classification: str, doc_id: str, title: str) -> None:
    (build_dir / f"{name}.json").write_text(
        json.dumps({"header": {"classification": classification, "id": doc_id, "title": title}}),
        encoding="utf-8",
    )
    # A matching .html must exist or scan_public_doc_jsons drops the entry regardless of tier.
    (build_dir / f"{name}.html").write_text(f"<html><body>{title}</body></html>", encoding="utf-8")


class TierExclusionHoldsAtTheIndex(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.build_dir = Path(self._tmp.name) / "build"
        self.build_dir.mkdir(parents=True)
        _write_sidecar(
            self.build_dir,
            "public-doc",
            classification="public",
            doc_id="PUB-1",
            title="Public Document",
        )
        _write_sidecar(
            self.build_dir,
            "secret-twin",
            classification="secret",
            doc_id="SEC-1",
            title=_CANARY_TITLE,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_scan_indexes_only_the_public_document(self) -> None:
        docs = scan_public_doc_jsons(self.build_dir)
        self.assertEqual([d.id for d in docs], ["PUB-1"])
        self.assertNotIn(_CANARY_TITLE, [d.title for d in docs])

    def test_rendered_index_never_names_the_secret_twin(self) -> None:
        out_path = build_index(self.build_dir, manifest_rows=[], out_path=self.build_dir / "index.html")
        html = out_path.read_text(encoding="utf-8")
        self.assertNotIn(_CANARY_TITLE, html)
        self.assertNotIn("SEC-1", html)
        self.assertIn("Public Document", html)
        self.assertIn("PUB-1", html)


if __name__ == "__main__":
    unittest.main()
