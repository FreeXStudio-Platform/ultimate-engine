"""The census counts what is in the tree, and says what it could not count (``tools.census``).

A small repository is built with dated commits, so every number the census reports has an expected value written down here, derived by
hand from the fixture and not from the code under test. The same fixture is then measured twice (determinism), with a hostile ``GIT_DIR``
(it must read the repository it was pointed at), and under an invalid profile (refusal).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Any

from tools import gitenv
from tools.census import (
    explorer_specs,
    gitscan,
    inventory,
    measure,
    modules,
    profile,
    report,
)

_TODAY = "2026-03-10"


def _git(root: Path, *args: str, when: str | None = None) -> str:
    env = gitenv.clean_env()
    if when:
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = f"{when}T12:00:00+0000"
    return subprocess.run(
        ("git", "-c", "user.email=t@x", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args), cwd=root, env=env, capture_output=True, text=True, check=True
    ).stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(root: Path) -> None:
    """Four dated commits: the tree, the first stamps, a deletion and an edit."""
    _git(root, "init", "-q", "-b", "main")
    _write(root, "README.md", "# Proj\n\nSee [guide](docs/guide.md) and [gone](docs/tmp/gone.md).\n")
    _write(root, "docs/guide.md", "# Guide\n\nSee [plan](plan.md) and [missing](./missing.md).\n")
    _write(root, "docs/plan.md", "# Plan\n\nThe source of truth for planning.\n")
    _write(root, "docs/archive/old.md", "# Old\n")
    _write(root, "docs/tmp/gone.md", "# Gone\n")
    _write(root, "src/pkg_a/__init__.py", "")
    _write(root, "src/pkg_a/core.py", "from pkg_b import util\nimport os\n")
    _write(root, "src/pkg_b/__init__.py", "")
    _write(root, "src/pkg_b/util.py", "x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "c1", when="2026-01-10")
    _write(root, "docs/design/spec.md", "# Spec\n\nbody v1\n")
    _write(root, "docs/design/drift.md", "# Drift\n\nv1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "c2", when="2026-02-01")
    c2 = _git(root, "rev-parse", "--short=8", "HEAD")
    _write(root, "docs/design/spec.md", f"<!-- artifact-hardened: Approved @ {c2} on 2026-02-01 via three-pass-v1 -->\n# Spec\n\nbody v1\n")
    _write(root, "docs/design/drift.md", f"<!-- artifact-hardened: Approved @ {c2} on 2026-02-01 via three-pass-v1 -->\n# Drift\n\nv2 edited after the stamp\n")
    _write(root, "docs/design/inval.md", f"<!-- artifact-hardened: STAMP INVALIDATED (was Approved) @ {c2} on 2026-02-01 via three-pass-v1 -->\n# Inval\n")
    _write(root, "docs/retired.md", "# Retired\n\n> Status: Superseded by plan.md\n\ntext\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "c3", when="2026-02-02")
    _write(root, "docs/plan.md", "# Plan\n\nThe source of truth for planning.\n\nmore\n")
    _git(root, "rm", "-q", "docs/tmp/gone.md")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "c4", when="2026-03-01")


def _profile(**over: Any) -> profile.Profile:
    base: dict[str, Any] = {"project": "Fixture", "doc_globs": ["docs/**", "*.md"], "archive_globs": ["docs/archive/**"], "code_roots": ["src"], "index_doc": None,
                            "today": _TODAY, "explorer_depth": 2, "layers": [{"label": "Design", "areas": ["docs/design"]}, {"label": "Guides", "areas": ["docs"]}]}
    base.update(over)
    return profile.from_dict(base)


class CensusFixture(unittest.TestCase):
    tmp: tempfile.TemporaryDirectory[str]
    root: Path
    result: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="census-")
        cls.root = Path(cls.tmp.name)
        build_fixture(cls.root)
        cls.result = measure.measure(cls.root, _profile())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()


class TheCountsAreTheFixturesCounts(CensusFixture):
    def test_documents(self) -> None:
        d = self.result["documents"]
        self.assertEqual((d["total"], d["live"], d["archived"]), (8, 7, 1))
        self.assertEqual(self.result["head"]["date"], "2026-03-01")

    def test_updated_and_outdated_count_live_unmarked_documents_only(self) -> None:
        f = self.result["freshness"]
        # README, guide, plan, spec, drift, inval are live and unmarked; retired is marked and old/old.md is archived.
        self.assertEqual(f["population"], 6)
        self.assertEqual((f["fresh"], f["recent"], f["updated"], f["outdated"]), (0, 1, 1, 5))
        self.assertEqual(f["oldest"][0]["p"], "README.md")  # 59 days; ties in age break by path

    def test_crossed_out_is_archived_marked_and_deleted(self) -> None:
        lc = self.result["lifecycle"]
        self.assertEqual((lc["archived"], lc["marked"], lc["marked_but_live"], lc["removed"]), (1, 1, 1, 1))
        self.assertEqual(lc["crossed_out_in_tree"], 2)
        self.assertEqual(lc["crossed_out_total"], 3)

    def test_stamps_are_judged_on_the_body_not_on_the_file(self) -> None:
        states = {s["path"]: s["state"] for s in self.result["truth"]["stamps"]}
        self.assertEqual(states, {"docs/design/spec.md": "VALID", "docs/design/drift.md": "DRIFTED", "docs/design/inval.md": "INVALIDATED"})

    def test_authoritative_is_stamped_or_labelled_and_wired_means_cited_by_a_live_document(self) -> None:
        t = self.result["truth"]
        self.assertEqual((t["stamped"], t["labelled"], t["authoritative"]), (3, 1, 4))
        self.assertEqual(t["wired"], 1)  # only plan.md is cited (by guide.md)
        self.assertEqual(t["window"]["since"], "2026-02-03")
        self.assertEqual((t["window"]["commits"], t["window"]["doc_commits"], t["window"]["authoritative_commits"]), (1, 1, 1))

    def test_links_count_the_dangling_ones(self) -> None:
        self.assertEqual(self.result["links"], {"relative": 4, "dangling": 2})

    def test_completeness_is_a_list_of_counts_and_never_a_single_number(self) -> None:
        dims = {x["id"]: (x["covered"], x["of"]) for x in self.result["completeness"]["dimensions"]}
        self.assertEqual(dims["titled"], (8, 8))
        self.assertEqual(dims["links"], (2, 4))
        self.assertEqual(dims["updated"], (1, 6))
        self.assertEqual(dims["stamps"], (1, 3))
        self.assertEqual(dims["cross_out"], (0, 1))
        self.assertEqual(dims["modules"], (0, 2))  # no live document names src/pkg_a or src/pkg_b
        self.assertNotIn("score", json.dumps(self.result["completeness"]).lower())

    def test_history_is_followed_through_the_months(self) -> None:
        h = self.result["history"]
        self.assertEqual(h["months"], ["2026-01", "2026-02", "2026-03"])
        self.assertEqual(h["added"], [4, 4, 0])
        self.assertEqual(h["removed"], [0, 0, 1])

    def test_the_code_hierarchy_and_its_one_import_edge(self) -> None:
        m = self.result["modules"]
        self.assertEqual([p["name"] for p in m["packages"]], ["pkg_a", "pkg_b"])
        self.assertEqual(m["edges"], [["pkg_a", "pkg_b", 1]])
        self.assertEqual(m["unparsed"], [])


class TheMeasurementIsTrustworthy(unittest.TestCase):
    def test_it_is_deterministic_and_does_not_read_the_wall_clock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="census-") as td:
            root = Path(td)
            build_fixture(root)
            a = measure.measure(root, _profile())
            b = measure.measure(root, _profile())
            self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
            later = measure.measure(root, _profile(today="2027-03-10"))
            self.assertEqual(later["today"], "2027-03-10")
            self.assertEqual(later["freshness"]["updated"], 0)

    def test_it_reads_the_repository_it_was_pointed_at_under_a_hostile_git_dir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="census-") as td, tempfile.TemporaryDirectory(prefix="census-other-") as other:
            root, elsewhere = Path(td), Path(other)
            build_fixture(root)
            _git(elsewhere, "init", "-q", "-b", "main")
            saved = {k: os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE")}
            os.environ["GIT_DIR"] = str(elsewhere / ".git")
            os.environ["GIT_WORK_TREE"] = str(elsewhere)
            try:
                got = measure.measure(root, _profile())
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            self.assertEqual(got["documents"]["total"], 8)

    def test_a_dirty_tree_is_reported_not_hidden(self) -> None:
        with tempfile.TemporaryDirectory(prefix="census-") as td:
            root = Path(td)
            build_fixture(root)
            (root / "README.md").write_text("# changed\n", encoding="utf-8")
            self.assertTrue(measure.measure(root, _profile())["dirty"])


class TheProfileRefusesWhatItCannotMeasure(unittest.TestCase):
    def test_each_refusal_names_the_key(self) -> None:
        cases: list[tuple[dict[str, Any], str]] = [({"nope": 1}, "unknown profile key"), ({"fresh_days": 40, "outdated_days": 35}, "fresh_days must be smaller"), ({"doc_exts": ["md"]}, "dot"),
                 ({"stamp_patterns": ["(unclosed"]}, "not a regular expression"), ({"area_depth": 9}, "area_depth"), ({"today": "10/03/2026"}, "today"),
                 ({"report": {"bogus": 1}}, "report")]
        for data, needle in cases:
            with self.assertRaises(profile.ProfileError, msg=str(data)) as ctx:
                profile.from_dict(dict(data))
            self.assertIn(needle, str(ctx.exception))

    def test_a_missing_profile_file_is_an_error_not_the_defaults(self) -> None:
        with self.assertRaises(profile.ProfileError):
            profile.load(Path("/nonexistent/census.profile.json"))

    def test_globs_cross_directories_only_with_two_stars(self) -> None:
        m = profile.matcher(("docs/**", "*.md"))
        self.assertTrue(m("docs/a/b/c.md"))
        self.assertTrue(m("README.md"))
        self.assertFalse(m("src/x.md"))
        self.assertFalse(m("a/README.md"))


class TheExplorersAreValidSpecs(CensusFixture):
    def test_both_specs_pass_the_explorer_s_own_validation(self) -> None:
        from tools.docgen import explorer

        docs = explorer_specs.docs_explorer(self.result, _profile())
        code = explorer_specs.modules_explorer(self.result)
        self.assertIsNotNone(code)
        for spec in (docs, code):
            assert spec is not None
            explorer.render(explorer.spec_from_dict(spec))

    def test_the_docs_explorer_has_one_dossier_per_folder_and_a_status_for_every_part(self) -> None:
        spec = explorer_specs.docs_explorer(self.result, _profile())
        statuses = {s["key"] for s in spec["statuses"]}

        def walk(n: dict[str, Any]) -> list[dict[str, Any]]:
            return [n] + [x for c in n.get("children", []) for x in walk(c)]

        parts = walk(spec["root"])[1:]
        self.assertTrue(parts)
        for part in parts:
            self.assertIn(part.get("status"), statuses, part["id"])
        self.assertTrue(spec["documents"])

    def test_the_arrows_say_cites_for_documents_and_imports_for_code(self) -> None:
        docs = explorer_specs.docs_explorer(self.result, _profile())
        code = explorer_specs.modules_explorer(self.result)
        assert code is not None
        self.assertEqual((docs["arrows"]["out"], docs["arrows"]["in"]), ("cites", "cited by"))
        self.assertEqual((code["arrows"]["out"], code["arrows"]["in"]), ("imports", "imported by"))

    def test_a_folder_that_holds_almost_everything_is_opened_up_on_the_first_map(self) -> None:
        top = [c["name"] for c in explorer_specs.docs_explorer(self.result, _profile())["root"]["children"]]
        self.assertNotEqual(top, ["docs"], "one rectangle that is the whole map teaches nothing")
        self.assertIn("design", top)
        self.assertIn("docs (loose files)", top)

    def test_below_the_share_nothing_is_lifted_and_the_citations_still_land(self) -> None:
        from tools.docgen import explorer

        with unittest.mock.patch.object(explorer_specs, "_FLATTEN_SHARE", 1.01):
            spec = explorer_specs.docs_explorer(self.result, _profile())
        self.assertIn("docs", [c["name"] for c in spec["root"]["children"]])
        explorer.render(explorer.spec_from_dict(spec))  # every edge endpoint is a drawn part
        lifted = explorer_specs.docs_explorer(self.result, _profile())
        explorer.render(explorer.spec_from_dict(lifted))


class TheReportBuildsAndNamesItsLimits(CensusFixture):
    def test_the_report_has_the_figures_the_census_promises_and_prints_its_limits(self) -> None:
        md, figs = report.compose(self.result, _profile())
        kinds = {f["kind"] for f in figs}
        # five different kinds of figure, each answering a different question
        self.assertTrue({"sankey", "echarts", "heatmap", "bar", "pie", "radar", "timeline", "mermaid", "layered_workflow", "explorer"} <= kinds, kinds)
        self.assertIn("What this census could not verify", md)
        self.assertIn("No composite completeness number", md)
        for f in figs:
            self.assertIn(f"<!-- figure:{f['id']} -->", md)

    def test_the_flow_names_each_age_band_as_a_band_and_the_heat_map_has_no_empty_row(self) -> None:
        _md, figs = report.compose(self.result, _profile())
        flow = next(f for f in figs if f["kind"] == "sankey")
        labels = {n["label"] for n in flow["nodes"]}
        self.assertIn("Touched 8–35 days ago", labels)
        self.assertNotIn("Touched within 35 days", labels, "the bands are disjoint: 'within 35' would double-count the first")
        heat = next((f for f in figs if f["kind"] == "heatmap"), None)
        if heat:
            for name, row in zip(heat["row_labels"], heat["matrix"], strict=True):
                self.assertGreater(sum(row), 0, f"{name} has no live document and should not be a row")

    def test_every_number_in_the_answers_table_is_in_the_measurement(self) -> None:
        md, _figs = report.compose(self.result, _profile())
        row = next(line for line in md.split("\n") if line.startswith("| How many documents?"))
        self.assertIn("**8**", row)
        self.assertIn("7 live", row)

    def test_the_document_engine_accepts_it(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        scratch = repo / ".docgen"
        scratch.mkdir(exist_ok=True)
        out = Path(tempfile.mkdtemp(dir=scratch))
        try:
            prof = _profile(report={"id": "WF-903", "classification": "public", "surface": "web", "audience": "technical", "owner": "doc-system", "status": "draft", "export_allowed": True})
            outputs = report.build(self.result, prof, out, None, ("html",))
            self.assertTrue(outputs["html"].is_file())
            self.assertIn("data-ve-explorer", outputs["html"].read_text(encoding="utf-8"))
        finally:
            import shutil

            shutil.rmtree(out, ignore_errors=True)


class TheReportNamesOnlyFiguresItDraws(unittest.TestCase):
    """A report that points at a figure it did not build is refused by the document generator, so a valid census of a repository with no live
    unmarked document used to fail at build time (found in review of the host's vendoring PR)."""

    def test_an_archive_only_repository_references_no_missing_figure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="census-arch-") as tmp:
            root = Path(tmp)
            _git(root, "init", "-q", "-b", "main")
            _write(root, "README.md", "# Proj\n")
            _write(root, "docs/archive/old.md", "# Old\n\ntext\n")
            _write(root, "docs/archive/older.md", "# Older\n\ntext\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "c1", when="2026-01-10")
            prof = _profile(doc_globs=["docs/**"], archive_globs=["docs/archive/**"], layers=[], code_roots=[], explorer_depth=2)
            md, figs = report.compose(measure.measure(root, prof), prof)
        have = {f["id"] for f in figs}
        referenced = set(re.findall(r"<!-- figure:([a-z0-9-]+) -->", md))
        self.assertNotIn("census-age-heat", have, "no live document, so no age heat map")
        self.assertEqual(referenced - have, set(), "every directive in the report names a figure the report builds")


class GitScanFollowsRenames(unittest.TestCase):
    def test_a_moved_document_keeps_its_first_added_date_and_is_not_a_removal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="census-") as td:
            root = Path(td)
            _git(root, "init", "-q", "-b", "main")
            _write(root, "docs/a.md", "# A\n\nsome words that make the file big enough to be recognised as a rename\n" * 5)
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "one", when="2026-01-01")
            _git(root, "mv", "docs/a.md", "docs/b.md")
            _git(root, "commit", "-q", "-m", "two", when="2026-02-01")
            h = gitscan.history(root, {"docs/b.md"})
            self.assertEqual(h.first_seen["docs/b.md"], "2026-01-01")
            self.assertEqual(h.last_touch["docs/b.md"], "2026-02-01")
            self.assertEqual(h.removed, {})
            self.assertEqual(h.renamed, 1)


class ModulesAreReadWithAstAndNeverImported(unittest.TestCase):
    def test_relative_imports_resolve_and_a_file_that_does_not_parse_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="census-") as td:
            root = Path(td)
            _write(root, "src/a/__init__.py", "")
            _write(root, "src/a/x.py", "from ..b import y\n")
            _write(root, "src/b/__init__.py", "")
            _write(root, "src/b/y.py", "def f(:\n")
            files = ["src/a/__init__.py", "src/a/x.py", "src/b/__init__.py", "src/b/y.py"]
            m = modules.read_modules(root, ("src",), files)
            self.assertEqual(m["unparsed"], ["src/b/y.py"])
            self.assertEqual(m["edges"], [["a", "b", 1]])


_REPO = Path(__file__).resolve().parents[2]


class TheShippedFilesAreValidAndGeneric(unittest.TestCase):
    def test_the_example_profile_loads_and_names_every_documented_key(self) -> None:
        prof = profile.load(_REPO / "examples" / "census.profile.example.json")
        self.assertEqual(prof.project, "Example Project")
        raw = json.loads((_REPO / "examples" / "census.profile.example.json").read_text(encoding="utf-8"))
        for key in ("doc_globs", "archive_globs", "stamp_patterns", "authority_docs", "index_doc", "code_roots", "layers", "report"):
            self.assertIn(key, raw)

    def test_the_example_report_block_uses_a_tier_the_engine_accepts(self) -> None:
        """The example's `report.classification` was `internal`, which the engine's own tier law (public, confidential, secret) refuses:
        a plain tree built from the example read it as `secret` and refused the report. A shipped example must build where it ships."""
        from tools.docgen.models import Tier

        report = json.loads((_REPO / "examples" / "census.profile.example.json").read_text(encoding="utf-8"))["report"]
        self.assertIn(report["classification"], {tier.value for tier in Tier})
        if report["classification"] != Tier.PUBLIC.value:
            self.assertFalse(report["export_allowed"], "only a public report may be export-allowed")

    def test_the_census_names_no_project(self) -> None:
        files = [*sorted((_REPO / "tools" / "census").glob("*.py")), _REPO / "docs" / "design" / "PROJECT_CENSUS.md", _REPO / "skills" / "project-census" / "SKILL.md",
                 _REPO / "examples" / "census.profile.example.json"]
        # The forbidden names are assembled from fragments so this test file itself stays name-free.
        forbidden = "audit" + r"[ _-]?" + "hunt" + "|free" + "xstudio" + "|crypto" + "sours"
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(forbidden, text, re.IGNORECASE), f"{path.name} names a project: the census is generic")


class TheInventoryCountsTheEnginesOwnRegistries(unittest.TestCase):
    def test_the_headline_is_the_sum_of_the_registries(self) -> None:
        inv = inventory.inventory(_REPO)
        de, ce, me = inv["document_engine"], inv["chart_engine"], inv["mermaid_engine"]
        self.assertEqual(inv["implementations"], len(de["native"]) + len(de["blocks"]) + ce["count"] + me["count"])
        self.assertEqual(ce["count"], len(ce["visuals"]))
        self.assertLessEqual(inv["distinct_after_merging_names"], inv["implementations"])
        for kind in ("sankey", "radar", "layered_workflow", "explorer"):
            self.assertIn(kind, de["native"] + de["blocks"])
        self.assertIn("stateDiagram-v2", me["types"])
        self.assertIn("bar_stacked", ce["visuals"])
        self.assertEqual(de["bridges"], ["echarts", "mermaid"])


if __name__ == "__main__":
    unittest.main()
