"""Counter-examples for the blueprint layer — the map agents are told to read first.

A wrong map is worse than no map. An agent that greps the tree gets an expensive truth; an agent
that reads a confident, stale, or misinterpreted map gets a cheap falsehood and acts on it. These
probes exist because the first build of this layer produced exactly that: it reported **54 secret
documents** in a repository that has none.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.blueprint.model import _UNGOVERNED, build_model, documents, import_graph
from tools.blueprint.render import blueprint_files, render_markdown, render_mermaid

_ROOT = Path(__file__).resolve().parents[2]


class TheMapMustNotRestateAFailClosedSentinelAsAFact(unittest.TestCase):
    """The defect this whole file exists for.

    ``parse_header`` is fail-closed: handed a document with no YAML front matter it returns the
    sentinel id ``UNKNOWN`` and ``Tier.SECRET``, so an unheadered file can never leave the vault as
    public. That is correct for the export gate. Copying it into a map turns a **refusal to answer**
    into an **answer**, and the answer is alarming and false.
    """

    def _model_of(self, files: dict[str, str]) -> list[dict[str, str]]:
        tmp = tempfile.TemporaryDirectory(prefix="bp-sentinel-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
        for name, body in files.items():
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True,
                       capture_output=True)
        return documents(root)

    def test_a_document_with_no_front_matter_is_ungoverned_not_secret(self) -> None:
        docs = self._model_of({"NOTES.md": "# Just a heading\n\nordinary prose.\n"})
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["tier"], _UNGOVERNED)
        self.assertNotIn("secret", docs[0]["tier"].lower())
        self.assertEqual(docs[0]["id"], "")

    def test_a_genuinely_classified_document_still_reports_its_real_tier(self) -> None:
        """The other side. Suppressing the sentinel must not suppress a REAL classification."""
        body = (
            "---\n"
            "id: WF-777\ntitle: Board notes\nclassification: secret\naudience: board\n"
            "owner: sami\nstatus: final\nexport_allowed: false\nsurface: internal\n"
            "last_reviewed: 2026-08-01\n"
            "---\n\nbody\n"
        )
        docs = self._model_of({"SECRET.md": body})
        self.assertEqual(docs[0]["tier"], "secret",
                         "a real `classification: secret` must survive — suppressing the sentinel "
                         "must not suppress the genuine article")
        self.assertEqual(docs[0]["id"], "WF-777")

    def test_a_tier_is_rendered_as_its_vocabulary_not_its_enum_repr(self) -> None:
        """`str(Tier.PUBLIC)` is `Tier.PUBLIC` — a word the rest of the engine never uses."""
        for doc in documents(_ROOT):
            self.assertNotIn("Tier.", doc["tier"])


class TheMapMustBeDerivedNotHandKept(unittest.TestCase):
    def test_check_fails_when_a_committed_file_is_stale(self) -> None:
        """`blueprint check` is the whole guarantee: without it the map is prose again — so its
        FAILURE direction is what needs a red-first counter-example, and it had none.

        The 1.0.0 audit found this test named for the stale-map gate never invoked the gate: it
        wrote ``SYSTEM.md + "\\nline\\n"`` to a temp file and asserted the string differed from a
        fresh build — a tautology that stays green whatever `check` does. The real red-on-stale
        enforcement lived only in the POSITIVE-direction sibling
        (`test_the_committed_blueprint_matches_a_fresh_build`, which runs `check` against the
        already-current repo). This now builds a faithful lab, proves `check` is green while the
        committed map matches a fresh build, then stales one committed derived file and proves
        `check` goes RED (exit 1) and names the drifted file — the gate falsified in both
        directions, on the artifact it actually certifies (`LESSONS.md` L-15)."""
        from tools.tests.lab import build_lab, force_rmtree

        tmp = tempfile.TemporaryDirectory(prefix="bp-stale-", ignore_cleanup_errors=True)
        lab = Path(tmp.name) / "lab"
        self.addCleanup(lambda: force_rmtree(lab) if lab.exists() else None)
        self.addCleanup(tmp.cleanup)
        build_lab(lab)

        def check() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "-m", "tools.blueprint", "check"],
                cwd=lab, capture_output=True, text=True, check=False,
            )

        def commit(msg: str) -> None:
            subprocess.run(["git", "-C", str(lab), "add", "-A"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(lab), "-c", "user.name=lab", "-c", "user.email=lab@local",
                 "commit", "-q", "--allow-empty", "-m", msg],
                check=True, capture_output=True,
            )

        # Make the lab self-consistent w.r.t. its OWN tree before perturbing it — the lab copies the
        # working tree, which during a build session carries uncommitted changes that legitimately
        # stale the committed map. The test is about stale-DETECTION, not about whether the copied
        # blueprint happens to be current.
        subprocess.run([sys.executable, "-m", "tools.blueprint", "build"],
                       cwd=lab, capture_output=True, text=True, check=True)
        commit("rebuild the map so the lab is current")

        pristine = check()
        self.assertEqual(
            pristine.returncode, 0,
            f"a faithful lab must be current before it is broken:\n{pristine.stdout}\n{pristine.stderr}",
        )

        stale_target = lab / "blueprint" / "SYSTEM.md"
        stale_target.write_text(
            stale_target.read_text(encoding="utf-8") + "\nhand-edited line\n", encoding="utf-8")
        commit("stale the committed map")

        staled = check()
        self.assertNotEqual(
            staled.returncode, 0,
            "`blueprint check` passed on a committed map that no longer matches a fresh build — the "
            "map is prose again",
        )
        self.assertIn(
            "SYSTEM.md", staled.stdout + staled.stderr,
            f"`check` failed but did not name the drifted file:\n{staled.stdout}\n{staled.stderr}",
        )

    def test_the_committed_blueprint_matches_a_fresh_build(self) -> None:
        """The repository's own map must be current. This is the ratchet."""
        proc = subprocess.run(
            [sys.executable, "-m", "tools.blueprint", "check"],
            cwd=_ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0,
                         "blueprint/ is stale — run `python3 -m tools.blueprint build` and commit:\n"
                         + proc.stdout + proc.stderr)

    def test_one_function_describes_the_file_set(self) -> None:
        """Writer and verifier must share ONE shape.

        Two descriptions of one file set drifted within hours when it was tried elsewhere in this
        engine, and reported six files as corrupt on a clean tree.
        """
        files = blueprint_files(build_model(_ROOT))
        self.assertEqual(
            set(files),
            {"SYSTEM.json", "SYSTEM.md", "SURFACES.md", "COMPLETENESS.md",
             "system.mmd", "system.d2"},
        )


class TheMapMustNotBeVacuous(unittest.TestCase):
    """An empty map exits 0 and teaches nothing — the exact failure `deps.json` shipped with."""

    model: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.model = build_model(_ROOT)

    def test_the_import_graph_is_not_empty(self) -> None:
        g = self.model["graph"]
        self.assertGreater(len(g["nodes"]), 40, "this engine has ~75 Python modules")
        self.assertGreater(len(g["edges"]), 50, "a graph with no edges is not a graph")

    def test_every_registry_resolved(self) -> None:
        """A registry that failed to import is a hole; the model must not quietly omit it."""
        reg = self.model["registries"]
        for key in ("corpus_guards", "health_checks", "gate_spine"):
            self.assertIn(key, reg, f"{key} failed to import: {reg.get(key + '_error')}")
            self.assertTrue(reg[key], f"{key} resolved but is empty")

    def test_the_map_names_its_own_holes(self) -> None:
        """Unreadable files are listed, never skipped silently."""
        self.assertIn("unparsed", self.model["graph"])

    def test_the_markdown_stays_small_enough_to_be_worth_reading(self) -> None:
        """The map's value IS its size. Past ~400 lines it competes with the tree it replaces."""
        lines = render_markdown(self.model).splitlines()
        self.assertLess(len(lines), 400, f"SYSTEM.md is {len(lines)} lines — too long to orient from")

    def test_the_mermaid_is_package_level_and_renders(self) -> None:
        mmd = render_mermaid(self.model)
        self.assertTrue(mmd.startswith("graph LR"))
        self.assertNotIn("-->|0|", mmd, "a zero-weight edge means the collapse dropped its count")

    def test_the_model_is_json_serialisable_and_deterministic(self) -> None:
        """Two builds of one tree must produce identical bytes, or `check` is noise."""
        again = build_model(_ROOT)
        self.assertEqual(json.dumps(self.model, sort_keys=True),
                         json.dumps(again, sort_keys=True))


class TheImportGraphMustSeeWhatTheInterpreterSees(unittest.TestCase):
    """`ast`, not a regex — the reason the JS builder under-reported the risky core."""

    def _graph_of(self, files: dict[str, str]) -> dict[str, Any]:
        tmp = tempfile.TemporaryDirectory(prefix="bp-ast-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
        for name, body in files.items():
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
        return import_graph(root)

    def test_a_parenthesised_multiline_import_is_seen(self) -> None:
        """A line-matching regex misses this; the interpreter does not."""
        g = self._graph_of({
            "pkg/__init__.py": "",
            "pkg/a.py": "x = 1\n",
            "pkg/b.py": "from pkg.a import (\n    x,\n)\n",
        })
        self.assertIn("pkg.b -> pkg.a", g["edges"])

    def test_the_word_import_inside_a_string_is_not_an_edge(self) -> None:
        """A regex over lines invents this edge. The parser cannot."""
        g = self._graph_of({
            "pkg/__init__.py": "",
            "pkg/a.py": "x = 1\n",
            "pkg/b.py": 'DOC = "from pkg.a import x"\n',
        })
        self.assertNotIn("pkg.b -> pkg.a", g["edges"])

    def test_an_unparseable_file_becomes_a_named_hole_not_a_silent_skip(self) -> None:
        g = self._graph_of({"pkg/__init__.py": "", "pkg/broken.py": "def (\n"})
        self.assertTrue(any("broken.py" in u for u in g["unparsed"]),
                        f"unparsed={g['unparsed']}")


if __name__ == "__main__":
    unittest.main()
