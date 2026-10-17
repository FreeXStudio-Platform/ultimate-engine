"""The document index and the reference cards' contract (OG-283): a number in a document says what it is.

Measured on the 2026-10-10 report: every back-link read ``↑ 8`` because the title ``8. Modules`` was cut at its first
``". "``, and a reader could not tell what section 8 was, let alone which documents it drew on. The index is the page's own
answer, and these tests pin it from three sides: the pure functions, the built document (no reference may dangle), and the
real browser (``tools/tests/browser/figure_runtime_check.mjs``, run by ``test_figure_runtime_browser``).
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.docgen import components, doc_index, generator
from tools.tests import test_figure_system as fixtures

_REPO = Path(__file__).resolve().parents[2]


class OrdinalsAreKeptWhole(unittest.TestCase):
    def test_an_ordinal_is_split_from_its_title(self) -> None:
        for title, want in (
            ("8. Modules", ("8", "Modules")),
            ("15. The system, from far to near", ("15", "The system, from far to near")),
            ("2.1) Sub-part", ("2.1", "Sub-part")),
            ("8 · Modules", ("8", "Modules")),
            ("Modules", ("", "Modules")),
            ("10 findings remain", ("", "10 findings remain")),  # a sentence, not an ordinal
            ("2026-10-10 notes", ("", "2026-10-10 notes")),  # a date
        ):
            self.assertEqual(doc_index.split_ordinal(title), want, title)

    def test_a_back_link_names_its_section_instead_of_just_its_number(self) -> None:
        self.assertEqual(components._short("8. Modules"), "8 · Modules")
        self.assertEqual(components._short("16. What I could not verify"), "16 · What I could not verify")
        # a sentence-shaped title is still cut at the sentence, after the ordinal is protected
        self.assertEqual(components._short("3. Open items. And more"), "3 · Open items")
        self.assertEqual(components._short("Overview. More"), "Overview")
        long = components._short("9. " + "very long title " * 10, 30)
        self.assertLessEqual(len(long), 30)
        self.assertTrue(long.startswith("9 · "))

    def test_the_heading_number_becomes_a_reference_and_the_heading_text_is_unchanged(self) -> None:
        html = components.section("8. Modules", "<p>body</p>", section_id="sec-modules")
        self.assertIn('<span class="sec-n" data-ref="sec-modules" tabindex="0">8</span>. Modules', html)
        plain = components.section("Modules", "<p>body</p>", section_id="sec-modules")
        self.assertNotIn("sec-n", plain)
        self.assertNotIn("sec-n", components.section("8. Modules", "<p>body</p>"), "no id, nothing to point at")


class TheIndexReadsTheSectionsItIndexes(unittest.TestCase):
    def test_lede_is_the_first_sentence_of_the_first_paragraph(self) -> None:
        md = "\n## 8. Modules\n\nThe system has fourteen modules, each owning one job. The second sentence is dropped.\n\nAnother paragraph."
        self.assertEqual(doc_index.lede(md), "The system has fourteen modules, each owning one job.")

    def test_lede_skips_tables_code_lists_and_headings(self) -> None:
        md = "# T\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```\ncode here\n```\n\n- a list item\n\nThe real opening sentence of this section is here.\n"
        self.assertEqual(doc_index.lede(md), "The real opening sentence of this section is here.")

    def test_lede_strips_markdown_and_figure_markers_and_caps_its_length(self) -> None:
        md = "See [[fig:flow]] for the **bold** `code` [link](https://x.example) that explains it all in one go."
        self.assertEqual(doc_index.lede(md), "See the figure for the bold code link that explains it all in one go.")
        self.assertLessEqual(len(doc_index.lede("word " * 200)), 240)
        self.assertEqual(doc_index.lede(""), "")

    def test_a_stub_first_sentence_does_not_stand_alone(self) -> None:
        self.assertEqual(doc_index.lede("Overview. Everything about the thing is described in this paragraph."), "Overview. Everything about the thing is described in this paragraph.")

    def test_documents_are_the_paths_a_section_names_in_code_spans(self) -> None:
        md = "Read `docs/current-state/MODULE_MAP.json` and `src/a/b.py:120-140`, not `plain`; again `docs/current-state/MODULE_MAP.json`."
        self.assertEqual(doc_index.documents_in(md), ["docs/current-state/MODULE_MAP.json", "src/a/b.py"])

    def test_the_index_joins_a_sections_text_to_its_figures_sources(self) -> None:
        figs = [{"dom_id": "fig-a", "number": 1, "kind": "treemap", "caption": "Source size. Details follow", "section": "sec-m",
                 "reader_question": "How big?", "data_sources": [{"kind": "metric", "ref": "docs/x/MAP.json", "url": ""},
                                                                  {"kind": "cited", "ref": "R-9", "url": "https://r.example/9"}]}]
        secs = [{"id": "sec-m", "title": "8. Modules", "figures": ["fig-a"], "markdown": "The modules are described in `docs/y/ARCH.md` here.\n"}]
        index = doc_index.build(secs, figs)
        assert index is not None
        self.assertEqual(index["figures"]["fig-a"]["title"], "Source size.")
        self.assertEqual(index["figures"]["fig-a"]["n"], 1)
        self.assertEqual(index["sections"]["sec-m"]["n"], "8")
        self.assertEqual(index["sections"]["sec-m"]["title"], "Modules")
        refs = [(d["ref"], d["kind"]) for d in index["sections"]["sec-m"]["docs"]]
        self.assertEqual(refs, [("docs/x/MAP.json", "metric"), ("R-9", "cited"), ("docs/y/ARCH.md", "mentioned")])
        self.assertEqual(index["sections"]["sec-m"]["docs"][1]["url"], "https://r.example/9")

    def test_a_document_with_no_figures_has_no_index(self) -> None:
        self.assertIsNone(doc_index.build([{"id": "sec-a", "title": "A", "figures": [], "markdown": "x"}], []))

    def test_the_json_cannot_end_its_script_block_early(self) -> None:
        index: dict[str, Any] = {"v": 1, "sections": {}, "figures": {"f": {"title": "</script><img src=x onerror=alert(1)> &  "}}}
        body = doc_index.to_script_json(index)
        self.assertNotIn("<", body)
        self.assertNotIn(">", body)
        self.assertNotIn(" ", body)
        self.assertEqual(json.loads(body)["figures"]["f"]["title"], index["figures"]["f"]["title"], "it still round-trips")


class ABuiltDocumentNeverPointsAtNothing(unittest.TestCase):
    out: Path
    html: str

    @classmethod
    def setUpClass(cls) -> None:
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        cls.out = Path(tempfile.mkdtemp(dir=scratch))
        md = cls.out / "doc.md"
        md.write_text(fixtures._DOC.replace("## First section", "## 1. First section").replace("## Second section", "## 2. Second section"), encoding="utf-8")
        (cls.out / "doc_spec.json").write_text(json.dumps(fixtures._spec_json()), encoding="utf-8")
        result = generator.build(md, formats=("html",), out_dir=cls.out)
        assert result.ok, [f.message for f in result.gate.findings]
        cls.html = result.outputs["html"].read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.out, ignore_errors=True)

    def _index(self) -> dict[str, Any]:
        match = re.search(r'<script type="application/json" id="ve-doc-index">(.*?)</script>', self.html, re.DOTALL)
        assert match, "the page ships no index"
        data: dict[str, Any] = json.loads(match.group(1))
        return data

    def test_the_page_ships_one_index_before_the_runtime(self) -> None:
        self.assertEqual(self.html.count('id="ve-doc-index"'), 1)
        self.assertLess(self.html.index('id="ve-doc-index"'), self.html.index("window.__veFigures"), "the runtime reads it at boot")
        self.assertEqual(self._index()["v"], 1)

    def test_every_reference_in_the_page_resolves_to_an_index_entry(self) -> None:
        index = self._index()
        refs = set(re.findall(r'data-ref="([^"]+)"', self.html))
        self.assertGreaterEqual(len(refs), 4, refs)
        for ref in refs:
            self.assertTrue(ref in index["figures"] or ref in index["sections"], f"{ref} points at nothing")

    def test_every_figure_and_section_is_indexed_under_its_dom_id(self) -> None:
        index = self._index()
        self.assertEqual(sorted(index["figures"]), ["fig-flow", "fig-seq"])
        self.assertEqual(sorted(index["sections"]), ["sec-1-first-section", "sec-2-second-section"])
        self.assertEqual(index["sections"]["sec-1-first-section"]["n"], "1")
        self.assertEqual(index["sections"]["sec-1-first-section"]["figures"], ["fig-flow"])
        self.assertEqual(index["figures"]["fig-flow"]["section"], "sec-1-first-section")
        self.assertTrue(index["figures"]["fig-flow"]["question"])

    def test_the_back_links_name_their_sections(self) -> None:
        self.assertIn("↑ 1 · First section", self.html)
        self.assertIn("↑ 2 · Second section", self.html)
        self.assertNotRegex(self.html, r'class="fig-up"[^>]*>↑ \d+</a>')

    def test_a_document_without_figures_is_unchanged(self) -> None:
        scratch = _REPO / ".docgen"
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            md = out / "doc.md"
            md.write_text(fixtures._DOC.split("## First section")[0] + "## 1. Plain\n\nJust prose here.\n", encoding="utf-8")
            result = generator.build(md, formats=("html",), out_dir=out)
            assert result.ok, [f.message for f in result.gate.findings]
            html = result.outputs["html"].read_text(encoding="utf-8")
            self.assertNotIn("ve-doc-index", html)
            self.assertNotIn("window.__veFigures", html)
            self.assertIn('<span class="sec-n"', html, "the heading number is still a reference marker")
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
