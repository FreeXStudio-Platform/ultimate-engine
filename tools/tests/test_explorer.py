"""The module explorer's contract (OG-285): a zoomable map whose every number is true and whose every string is inert.

Pure-function layer (spec, layout, connections, markup); the document layer and the real browser are exercised by the other
two classes at the bottom and by ``tools/tests/browser/explorer_check.mjs`` (run by ``test_explorer_browser``).
"""

from __future__ import annotations

import json
import random
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

from tools.docgen import explorer, generator
from tools.docgen.assets.glyphs import TONES
from tools.docgen.explorer import ExplorerError
from tools.docgen.models import Tier
from tools.tests import test_figure_system as fixtures

_REPO = Path(__file__).resolve().parents[2]


def _spec_dict(**over: Any) -> dict[str, Any]:
    """A small, valid explorer spec: a system, three modules, packages inside two of them, edges, a status legend, a document."""
    base: dict[str, Any] = {
        "id": "explorer", "kind": "explorer", "title": "The system, from far to near", "caption": "How big each part is",
        "reader_question": "What are the parts of the system and what does each one call?",
        "insight": "Most of the code sits in one part.",
        "data_sources": [{"kind": "metric", "ref": "docs/current-state/MODULE_MAP.json", "retrieved": "2026-10-10"}],
        "unit": "lines of code",
        "statuses": [
            {"key": "CLEAN", "label": "clean", "tone": "green", "detail": "no leaks"},
            {"key": "LEAKY", "label": "leaky", "tone": "gold"},
            {"key": "NOT_BUILT", "label": "not built", "tone": "steel"},
        ],
        "kinds": [{"key": "leak", "label": "not declared", "tone": "red"}, {"key": "declared", "label": "declared", "tone": "blue"}],
        "root": {
            "id": "system", "name": "The system", "kicker": "System", "summary": "Three modules.",
            "children": [
                {"id": "api", "name": "Ingress & API", "kicker": "Module", "status": "LEAKY", "summary": "The public door.",
                 "facts": [["Files", "128"]], "lists": [{"title": "Invariants", "items": ["Enters only through a port."]}],
                 "docs": ["d-api"], "refs": [{"label": "Section 8", "href": "#sec-modules"}],
                 "children": [{"id": "api.routes", "name": "routes", "value": 9000}, {"id": "api.deps", "name": "deps", "value": 3000}]},
                {"id": "db", "name": "Persistence", "kicker": "Module", "status": "CLEAN",
                 "children": [{"id": "db.models", "name": "models", "value": 4000}]},
                {"id": "bank", "name": "Contract bank", "kicker": "Module", "status": "NOT_BUILT"},
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
    base.update(over)
    return base


def _spec(**over: Any) -> explorer.ExplorerSpec:
    return explorer.spec_from_dict(_spec_dict(**over))


def _with(path: list[Any], value: Any) -> dict[str, Any]:
    """``_spec_dict`` with one nested field replaced; ``path`` is keys and list indexes."""
    data = _spec_dict()
    cur: Any = data
    for step in path[:-1]:
        cur = cur[step]
    cur[path[-1]] = value
    return data


class TheSpecRefusesWhatItCannotDraw(unittest.TestCase):
    def test_a_valid_spec_parses_with_every_field(self) -> None:
        spec = _spec()
        self.assertEqual([c.id for c in spec.root.children], ["api", "db", "bank"])
        self.assertEqual(spec.root.children[0].facts, (("Files", "128"),))
        self.assertEqual(spec.root.children[0].docs, ("d-api",))
        self.assertEqual(spec.edges[0].kind, "declared")
        self.assertEqual(spec.documents[0].blocks[1].text, "The public door.")

    def test_each_refusal_names_what_is_wrong(self) -> None:
        cases = {
            "duplicate id": (_with(["root", "children", 1, "id"], "api"), "unique"),
            "status not declared": (_with(["root", "children", 0, "status"], "MISSING"), "not declared"),
            "edge to nowhere": (_with(["edges", 0, "dst"], "ghost"), "not a node"),
            "self edge": (_with(["edges", 0, "dst"], "api"), "itself"),
            "edge kind not declared": (_with(["edges", 0, "kind"], "mystery"), "not declared"),
            "same edge twice": (_with(["edges", 1], {"src": "api", "dst": "db", "weight": 1}), "twice"),
            "document missing": (_with(["root", "children", 0, "docs"], ["nope"]), "not in `documents`"),
            "negative size": (_with(["root", "children", 0, "children", 0, "value"], -1), "finite number"),
            "infinite size": (_with(["root", "children", 0, "children", 0, "value"], float("inf")), "finite number"),
            "id with a space": (_with(["root", "children", 0, "id"], "a b"), "not an id"),
            "empty explorer": (_with(["root", "children"], []), "no children"),
            "block of an unknown type": (_with(["documents", 0, "blocks", 0, "t"], "script"), "is not one of"),
        }
        for label, (data, needle) in cases.items():
            with self.assertRaises(ExplorerError, msg=label) as ctx:
                explorer.spec_from_dict(data)
            self.assertIn(needle, str(ctx.exception), label)

    def test_a_status_tone_is_a_closed_vocabulary(self) -> None:
        # the tone becomes a CSS class, so free text would close the attribute and add its own (the OG-273 class)
        data = _spec_dict()
        data["statuses"][0]["tone"] = 'x" onclick="alert(1)'
        with self.assertRaises(ExplorerError):
            explorer.spec_from_dict(data)

    def test_a_link_in_a_part_points_inside_the_page(self) -> None:
        for bad in ("javascript:alert(1)", "https://example.com", "//evil", "#a b", ""):
            with self.assertRaises(ExplorerError, msg=bad):
                explorer.spec_from_dict(_with(["root", "children", 0, "refs", 0, "href"], bad))

    def test_the_size_of_what_it_will_hold_is_bounded(self) -> None:
        deep: dict[str, Any] = {"id": "leaf", "name": "leaf", "value": 1}
        for i in range(explorer.MAX_DEPTH + 1):
            deep = {"id": f"n{i}", "name": f"n{i}", "children": [deep]}
        with self.assertRaises(ExplorerError):
            explorer.spec_from_dict(_with(["root", "children"], [deep]))
        wide = [{"id": f"w{i}", "name": f"w{i}", "value": 1} for i in range(explorer.MAX_CHILDREN + 1)]
        with self.assertRaises(ExplorerError):
            explorer.spec_from_dict(_with(["root", "children"], wide))
        many = [{"id": f"m{i}", "name": f"m{i}", "children": [{"id": f"m{i}x{j}", "name": "x", "value": 1} for j in range(20)]} for i in range(40)]
        with self.assertRaises(ExplorerError):
            explorer.spec_from_dict(_with(["root", "children"], many))


class TheLayoutIsTrueAndTilesWithoutOverlap(unittest.TestCase):
    def test_squarify_gives_each_value_its_share_of_the_area(self) -> None:
        values = [60.0, 30.0, 6.0, 3.0, 1.0]
        tiles = explorer.squarify(values, 0, 0, 100, 60)
        total_area = 100 * 60
        for v, (_x, _y, w, h) in zip(values, tiles, strict=True):
            self.assertAlmostEqual(w * h / total_area, v / sum(values), delta=0.003)
        self.assertAlmostEqual(sum(w * h for _x, _y, w, h in tiles), total_area, delta=1.0)

    def test_squarify_tiles_do_not_overlap_and_stay_inside(self) -> None:
        rng = random.Random(7)
        for _ in range(60):
            n = rng.randint(1, 30)
            values = sorted((rng.random() * 100 + 0.5 for _ in range(n)), reverse=True)
            tiles = explorer.squarify(values, 5, 5, 990, 610)
            for x, y, w, h in tiles:
                self.assertGreaterEqual(x, 5 - 0.01)
                self.assertGreaterEqual(y, 5 - 0.01)
                self.assertLessEqual(x + w, 995 + 0.01)
                self.assertLessEqual(y + h, 615 + 0.01)
            for i, a in enumerate(tiles):
                for b in tiles[i + 1 :]:
                    overlap_w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
                    overlap_h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                    self.assertFalse(overlap_w > 0.02 and overlap_h > 0.02, (a, b))

    def test_squarify_is_deterministic_and_keeps_tiles_near_square(self) -> None:
        values = [50.0, 20.0, 12.0, 8.0, 5.0, 3.0, 2.0]
        self.assertEqual(explorer.squarify(values, 0, 0, 1000, 620), explorer.squarify(values, 0, 0, 1000, 620))
        worst = max(max(w / h, h / w) for _x, _y, w, h in explorer.squarify(values, 0, 0, 1000, 620))
        self.assertLess(worst, 4.5)

    def test_the_root_fills_the_stage_and_every_child_sits_inside_its_parent(self) -> None:
        spec = _spec()
        rects = explorer.layout(spec)
        self.assertEqual(rects["system"], (0.0, 0.0, explorer.WORLD_W, explorer.WORLD_H))
        for node, _depth, parent in explorer.walk(spec.root):
            if not parent:
                continue
            px, py, pw, ph = rects[parent]
            x, y, w, h = rects[node.id]
            self.assertGreaterEqual(x, px - 0.01, node.id)
            self.assertGreaterEqual(y, py - 0.01, node.id)
            self.assertLessEqual(x + w, px + pw + 0.01, node.id)
            self.assertLessEqual(y + h, py + ph + 0.01, node.id)

    def test_a_tile_s_area_is_its_size_so_a_bigger_part_is_a_bigger_rectangle(self) -> None:
        spec = _spec()
        rects = explorer.layout(spec)
        routes, deps = rects["api.routes"], rects["api.deps"]
        # 9000 vs 3000 lines inside the same parent: three times the area (the stage proportions are shared)
        self.assertAlmostEqual((routes[2] * routes[3]) / (deps[2] * deps[3]), 3.0, delta=0.25)
        self.assertEqual(explorer.raw_value(spec.root.children[0]), 12000.0, "a parent is the sum of its children")

    def test_a_part_with_no_size_is_still_drawn_and_still_clickable(self) -> None:
        spec = _spec()
        bank = explorer.layout(spec)["bank"]  # NOT_BUILT: no children, no value
        stage_area = explorer.WORLD_W * explorer.WORLD_H
        share = bank[2] * bank[3] / stage_area
        self.assertGreater(share, explorer.FLOOR_SHARE * 0.5)
        self.assertGreater(bank[2], 20)
        self.assertGreater(bank[3], 20)

    def test_a_system_of_parts_that_all_have_no_size_is_laid_out_evenly(self) -> None:
        data = _spec_dict()
        data["root"]["children"] = [{"id": f"p{i}", "name": f"p{i}"} for i in range(4)]
        data["edges"] = []
        data["documents"] = []
        for c in data["root"]["children"]:
            c.pop("docs", None)
        rects = explorer.layout(explorer.spec_from_dict(data))
        areas = [rects[f"p{i}"][2] * rects[f"p{i}"][3] for i in range(4)]
        self.assertLess(max(areas) / min(areas), 1.2)

    def test_layout_is_deterministic(self) -> None:
        self.assertEqual(explorer.layout(_spec()), explorer.layout(_spec()))


class ConnectionsAreExact(unittest.TestCase):
    def test_calls_and_called_by_are_the_same_edges_read_from_each_end(self) -> None:
        conn = explorer.connections(_spec())
        self.assertEqual(conn.out["api"], [("db", 12.0, "declared")])
        self.assertEqual(conn.into["db"], [("api", 12.0, "declared")])
        self.assertEqual(conn.out["db"], [("api", 2.0, "leak")])
        self.assertEqual(conn.into["api"], [("db", 2.0, "leak")])

    def test_siblings_are_edges_whose_ends_share_a_parent(self) -> None:
        conn = explorer.connections(_spec())
        self.assertEqual(sorted(conn.sib["system"]), [("api", "db", 12.0, "declared"), ("db", "api", 2.0, "leak")])
        self.assertEqual(conn.sib["api"], [("api.routes", "api.deps", 5.0, "")])
        self.assertNotIn("db", conn.sib)

    def test_an_edge_between_levels_is_exact_not_rolled_up(self) -> None:
        data = _spec_dict()
        data["edges"] = [{"src": "api.routes", "dst": "db", "weight": 3}]
        conn = explorer.connections(explorer.spec_from_dict(data))
        self.assertEqual(conn.out["api.routes"], [("db", 3.0, "")])
        self.assertNotIn("api", conn.out, "the module does not inherit its package's edge")
        self.assertEqual(conn.sib, {}, "the ends have different parents, so no stage arrow")

    def test_connections_are_listed_most_important_kind_first_then_heaviest(self) -> None:
        data = _spec_dict()
        data["edges"] = [
            {"src": "api", "dst": "db", "weight": 1, "kind": "declared"},
            {"src": "api", "dst": "bank", "weight": 99, "kind": "declared"},
            {"src": "api.routes", "dst": "api.deps", "weight": 1},
        ]
        conn = explorer.connections(explorer.spec_from_dict(data))
        self.assertEqual([o for o, _w, _k in conn.out["api"]], ["bank", "db"], "heavier first within a kind")
        data["edges"] = [{"src": "api", "dst": "db", "weight": 50, "kind": "declared"}, {"src": "api", "dst": "bank", "weight": 1, "kind": "leak"}]
        conn = explorer.connections(explorer.spec_from_dict(data))
        self.assertEqual([k for _o, _w, k in conn.out["api"]], ["leak", "declared"], "kinds are listed in the order the spec declares them")


class TheMarkupIsInert(unittest.TestCase):
    EVIL = '<img src=x onerror="alert(1)"> & "quoted" </script><script>alert(2)</script>'

    def _evil(self) -> explorer.ExplorerSpec:
        data = _spec_dict()
        data["title"] = self.EVIL
        data["root"]["children"][0]["name"] = self.EVIL
        data["root"]["children"][0]["summary"] = self.EVIL
        data["root"]["children"][0]["kicker"] = self.EVIL
        data["root"]["children"][0]["facts"] = [[self.EVIL, self.EVIL]]
        data["root"]["children"][0]["lists"] = [{"title": self.EVIL, "items": [self.EVIL]}]
        data["root"]["children"][0]["refs"] = [{"label": self.EVIL, "href": "#sec-ok"}]
        data["documents"][0]["title"] = self.EVIL
        data["documents"][0]["sources"] = [self.EVIL]
        data["documents"][0]["blocks"] = [
            {"t": "h", "text": self.EVIL}, {"t": "p", "text": self.EVIL}, {"t": "ul", "items": [self.EVIL]},
            {"t": "kv", "rows": [[self.EVIL, self.EVIL]]}, {"t": "table", "head": [self.EVIL], "rows": [[self.EVIL]]}, {"t": "code", "text": self.EVIL},
        ]
        short = '"><img src=x onerror=1>'
        data["statuses"][0]["label"] = short
        data["statuses"][0]["detail"] = self.EVIL
        data["kinds"][0]["label"] = short
        return explorer.spec_from_dict(data)

    def test_no_string_of_a_spec_becomes_markup(self) -> None:
        html = explorer.render(self._evil())
        self.assertNotIn("<img", html)
        self.assertNotIn("<script>alert", html)
        self.assertNotIn('onerror="', html)
        self.assertEqual(html.count("<script"), 1, "exactly one script block: the data")
        self.assertEqual(html.count("</script>"), 1)
        # the one data block is JSON that cannot end itself early and still round-trips
        match = re.search(r'<script type="application/json" class="ve-ex-data">(.*?)</script>', html, re.DOTALL)
        assert match
        self.assertNotIn("<", match.group(1))
        data = json.loads(match.group(1))
        self.assertEqual(data["nodes"]["api"]["n"], self.EVIL)

    def test_every_tone_that_reaches_a_class_is_from_the_closed_vocabulary(self) -> None:
        html = explorer.render(_spec())
        used = set(re.findall(r"\btone-([a-z]+)\b", html))
        self.assertTrue(used <= set(TONES), used)
        self.assertTrue(used, "the legend and the tiles are coloured")

    def test_the_markup_is_deterministic(self) -> None:
        self.assertEqual(explorer.render(_spec()), explorer.render(_spec()))

    def test_ids_the_page_will_scope_already_carry_the_figure_scope(self) -> None:
        html = explorer.render(_spec())
        ids = re.findall(r'(?<![\w-])id="([^"]+)"', html)
        self.assertTrue(ids)
        for i in ids:
            self.assertTrue(i.startswith("fig-explorer"), i)

    def test_every_part_is_a_focusable_labelled_tile_and_the_world_has_one_per_part(self) -> None:
        spec = _spec()
        html = explorer.render(spec)
        tiles = re.findall(r'<rect class="ve-n[^"]*" data-id="([^"]+)"[^>]*aria-label="([^"]+)"', html)
        parts = [n.id for n, d, _p in explorer.walk(spec.root) if d > 0]
        self.assertEqual([t[0] for t in tiles], parts)
        self.assertIn("Ingress &amp; API, Module, 12,000 lines of code, leaky", [t[1] for t in tiles])
        self.assertIn("Contract bank, Module, not built", [t[1] for t in tiles])


class AStaticOutlineCarriesEverythingTheMapDoes(unittest.TestCase):
    def test_every_part_name_value_status_summary_connection_and_document_is_in_the_outline(self) -> None:
        spec = _spec()
        html = explorer.render(spec)
        outline = re.search(r'<div class="ve-ex-fallback">(.*)</div></div><script', html, re.DOTALL)
        assert outline
        text = outline.group(1)
        for n, _d, _p in explorer.walk(spec.root):
            self.assertIn(f'data-id="{n.id}"', text, n.id)
        for needle in ("Ingress &amp; API", "12,000 lines of code", "leaky", "The public door.", "Connects to:", "Persistence (12, declared)",
                       "Connected from:", "Ingress &amp; API — dossier", "Section 8", "Enters only through a port.", "Files"):
            self.assertIn(needle, text, needle)
        self.assertIn('id="fig-explorer-doc-d-api"', text, "the document is written out once, where the outline links to it")
        self.assertEqual(text.count('data-doc="d-api"'), 1)

    def test_a_document_nothing_points_at_is_not_embedded(self) -> None:
        data = _spec_dict()
        data["documents"].append({"id": "orphan", "title": "Nobody opens me", "blocks": [{"t": "p", "text": "x"}]})
        html = explorer.render(explorer.spec_from_dict(data))
        self.assertNotIn("Nobody opens me", html.split('<script type="application/json"')[0])

    def test_the_machine_record_is_the_whole_hierarchy(self) -> None:
        rec = explorer.record(_spec())
        self.assertEqual(rec["kind"], "explorer")
        self.assertEqual([n["id"] for n in rec["nodes"]], ["system", "api", "api.routes", "api.deps", "db", "db.models", "bank"])
        api = next(n for n in rec["nodes"] if n["id"] == "api")
        self.assertEqual(api["calls"], [{"to": "db", "weight": 12.0, "kind": "declared"}])
        self.assertEqual(api["called_by"], [{"from": "db", "weight": 2.0, "kind": "leak"}])
        self.assertEqual(api["value"], 12000.0)
        self.assertEqual(rec["documents"][0]["blocks"][0], {"t": "h", "text": "What it is", "items": [], "rows": [], "head": []})

    def test_the_marks_table_lists_the_top_level_parts(self) -> None:
        rows = explorer.marks(_spec())
        self.assertEqual([r[0] for r in rows], ["Ingress & API", "Persistence", "Contract bank"])
        self.assertEqual(rows[0][1], "12,000 lines of code")


class TheDocumentBuildsAnExplorer(unittest.TestCase):
    out: Path
    html: str
    blueprint: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        scratch = _REPO / ".docgen"
        scratch.mkdir(exist_ok=True)
        cls.out = Path(tempfile.mkdtemp(dir=scratch))
        spec = _spec_dict()
        spec["id"] = "map"
        body = fixtures._DOC.split("## First section")[0] + "## 1. The map\n\nExplore [[fig:map]] below.\n\n<!-- figure:map -->\n"
        md = cls.out / "doc.md"
        md.write_text(body, encoding="utf-8")
        (cls.out / "doc_spec.json").write_text(json.dumps([spec]), encoding="utf-8")
        result = generator.build(md, formats=("html", "blueprint"), out_dir=cls.out)
        assert result.ok, [f.message for f in result.gate.findings]
        cls.html = result.outputs["html"].read_text(encoding="utf-8")
        cls.blueprint = json.loads(result.outputs["blueprint"].read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_the_explorer_is_a_numbered_anchored_figure(self) -> None:
        self.assertIn('<figure class="doc-figure" id="fig-map"', self.html)
        self.assertIn('data-fig-kind-name="explorer"', self.html)
        self.assertIn('<a class="fig-num" href="#fig-map" data-ref="fig-map">Fig. 1</a>', self.html)

    def test_it_sits_in_a_block_frame_not_a_sized_picture(self) -> None:
        frame = re.search(r'<div class="svgwrap[^"]*"[^>]*>', self.html)
        assert frame
        self.assertIn("svgwrap--block", frame.group(0))
        self.assertNotIn("--fw", frame.group(0))
        self.assertNotIn("svgwrap--grid", frame.group(0))

    def test_the_explorer_runtime_is_inlined_once_and_only_because_one_exists(self) -> None:
        self.assertEqual(self.html.count("docgen explorer runtime v1"), 1)
        self.assertEqual(self.html.count("docgen figure runtime v1"), 1)

    def test_a_document_without_an_explorer_does_not_carry_its_runtime(self) -> None:
        scratch = _REPO / ".docgen"
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            md = out / "doc.md"
            md.write_text(fixtures._DOC, encoding="utf-8")
            (out / "doc_spec.json").write_text(json.dumps(fixtures._spec_json()), encoding="utf-8")
            result = generator.build(md, formats=("html",), out_dir=out)
            html = result.outputs["html"].read_text(encoding="utf-8")
            self.assertNotIn("docgen explorer runtime v1", html)
            self.assertNotIn("ve-ex", html.split("<style>")[0])
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_the_blueprint_carries_the_hierarchy_for_a_machine(self) -> None:
        fig = self.blueprint["figures"][0]
        self.assertEqual(fig["kind"], "explorer")
        record = fig["record"]
        self.assertEqual(record["kind"], "explorer")
        self.assertEqual(len(record["nodes"]), 7)
        self.assertTrue(fig["how_to_read"].startswith("Each rectangle is a part"))

    def test_the_page_s_index_and_cards_know_the_explorer(self) -> None:
        index = json.loads(re.search(r'id="ve-doc-index">(.*?)</script>', self.html, re.DOTALL).group(1))  # type: ignore[union-attr]
        self.assertEqual(index["figures"]["fig-map"]["kind"], "explorer")
        self.assertEqual(index["figures"]["fig-map"]["docs"][0]["ref"], "docs/current-state/MODULE_MAP.json")

    def test_an_explorer_with_numbers_must_name_where_they_came_from(self) -> None:
        scratch = _REPO / ".docgen"
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            spec = _spec_dict()
            spec["id"] = "map"
            spec["data_sources"] = []
            md = out / "doc.md"
            md.write_text(fixtures._DOC.split("## First section")[0] + "## 1. The map\n\n<!-- figure:map -->\n", encoding="utf-8")
            (out / "doc_spec.json").write_text(json.dumps([spec]), encoding="utf-8")
            result = generator.build(md, formats=("html",), out_dir=out)
            self.assertFalse(result.ok)
            self.assertNotIn("html", result.outputs)
        finally:
            shutil.rmtree(out, ignore_errors=True)



class TheStylesheetCarriesTheExplorer(unittest.TestCase):
    """The CSS is generated inside a Python string: an escape written naively becomes a control character there."""

    css: str

    @classmethod
    def setUpClass(cls) -> None:
        from tools.docgen import tokens

        cls.css = tokens.build_css()

    def test_css_escapes_reach_the_stylesheet_as_css_escapes_not_python_ones(self) -> None:
        # `content: "\203A"` in the source of tokens.py is the three-character CSS escape; a lone `\203` would be Python's octal one.
        self.assertIn('content: "\\203A"', self.css)
        self.assertIn('content: "\\2630\\00a0\\00a0"', self.css)
        self.assertFalse([c for c in self.css if ord(c) < 32 and c not in "\n\r\t"], "a control character reached the stylesheet")

    def test_the_two_layers_out_rank_the_generic_svg_rule_that_would_resize_them(self) -> None:
        # `.svgwrap svg { height: auto }` (0,1,1) beats a bare class (0,1,0): the world's own box then follows the camera's viewBox aspect.
        self.assertIn(".ve-ex .ve-ex-world, .ve-ex .ve-ex-links {", self.css)
        rule = self.css.split(".ve-ex .ve-ex-world, .ve-ex .ve-ex-links {", 1)[1].split("}", 1)[0]
        for decl in ("height: 100%", "width: 100%", "max-width: none", "margin: 0"):
            self.assertIn(decl, rule)

    def test_the_block_frame_has_no_picture_chrome(self) -> None:
        rule = self.css.split(".svgwrap--block {", 1)[1].split("}", 1)[0]
        for decl in ("padding: 0", "border: 0", "overflow: visible"):
            self.assertIn(decl, rule)

    def test_the_map_is_hidden_without_script_and_the_outline_with_it(self) -> None:
        self.assertIn(".ve-ex:not([data-ve-js]) .ve-ex-main", self.css)
        self.assertIn(".ve-ex[data-ve-js] .ve-ex-fallback { display: none; }", self.css)

    def test_every_tone_a_part_can_wear_has_a_colour(self) -> None:
        from tools.docgen.assets.glyphs import TONES

        for tone in TONES:
            self.assertIn(f".ve-ex .tone-{tone} {{", self.css)

    def test_the_stage_ratio_is_the_world_ratio(self) -> None:
        self.assertIn(f"aspect-ratio: {explorer.WORLD_W:g} / {explorer.WORLD_H:g};", self.css)


class TheArrowWordingComesFromTheSpec(unittest.TestCase):
    """A documents explorer says "cites", not "calls": the legend, the guide and the spec agree, and a typo is refused."""

    words: ClassVar[dict[str, str]] = {"out": "cites", "in": "cited by", "out_detail": "the documents it cites", "in_detail": "the documents that cite it"}

    def test_without_the_key_the_wording_is_the_code_wording(self) -> None:
        spec = _spec()
        html = explorer.render(spec)
        self.assertIn(">calls</span>", html)
        self.assertIn(">called by</span>", html)
        self.assertEqual(explorer.how_to_read(spec), explorer.how_to_read())
        self.assertIn("blue for the parts it calls, pink for the parts that call it", explorer.how_to_read(spec))

    def test_with_the_key_the_legend_and_the_guide_use_it_and_not_the_default(self) -> None:
        spec = _spec(arrows=self.words)
        html = explorer.render(spec)
        self.assertIn(">cites</span>", html)
        self.assertIn(">cited by</span>", html)
        self.assertIn("hover a part: the documents it cites", html)
        self.assertIn("the documents that cite it", html)
        self.assertNotIn(">calls</span>", html)
        guide = explorer.how_to_read(spec)
        self.assertIn("blue for the documents it cites, pink for the documents that cite it", guide)
        self.assertNotIn("the parts it calls", guide)

    def test_one_changed_word_leaves_the_other_defaults(self) -> None:
        spec = _spec(arrows={"out": "imports"})
        self.assertEqual((spec.arrows.out, spec.arrows.into), ("imports", "called by"))

    def test_the_wording_is_escaped_in_the_legend(self) -> None:
        html = explorer.render(_spec(arrows={"out": "<b>x</b>"}))
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
        self.assertNotIn("<b>x</b>", html)

    def test_a_misspelt_key_an_empty_value_and_a_non_object_are_refused(self) -> None:
        for bad in ({"outt": "x"}, {"out": "  "}, {"out": 3}, "cites", ["cites"], {"out": "x" * 61}):
            with self.assertRaises(ExplorerError, msg=repr(bad)):
                _spec(arrows=bad)

    def test_the_sidecar_path_reaches_the_figure_page(self) -> None:
        guide = generator._present_explorer(_spec(arrows=self.words), Tier.PUBLIC).how_to_read
        self.assertIn("the documents that cite it", guide)


class AStrayEntryIsRefusedNotDropped(unittest.TestCase):
    """An edge, status or connection kind that is not an object used to be filtered out silently, so a schema typo built a diagram that looked
    complete and was missing a connection (found in review of the host's vendoring PR)."""

    def test_each_list_names_the_position_of_a_non_object_entry(self) -> None:
        for key, bad in (("edges", ["api->db"]), ("statuses", [3]), ("kinds", ["declared"])):
            data = _spec_dict()
            data[key] = list(data[key]) + bad
            with self.assertRaises(ExplorerError, msg=key) as ctx:
                explorer.spec_from_dict(data)
            self.assertIn(f"{key}[{len(data[key]) - 1}]", str(ctx.exception))

    def test_a_list_of_objects_still_builds(self) -> None:
        explorer.render(_spec())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
