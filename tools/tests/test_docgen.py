"""Counter-examples for the docgen build path: figure sidecars, figure dispatch, the theme
comment, the declared-tool contract, and the L9 re-baseline.

Every case here is a defect that was measured on this tree, not a hypothetical. Each test is
written so that REVERTING its fix turns it red — that is the only property that makes a test a
gate rather than a description.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.docgen import components, generator, validate_doc_system, visual
from tools.docgen.generator import BuildBlockedError, _load_sibling_figure
from tools.docgen.models import VisualSpec

_REPO = Path(__file__).resolve().parents[2]


class GeneratedHtmlIsDiffClean(unittest.TestCase):
    """`OG-245` — an optional row that renders empty must not become a whitespace-only line.

    The template indents its rows, so interpolating an empty ``legend_block`` left a line holding
    two spaces and nothing else. `git diff --check` calls that a whitespace error, and it landed in
    a GENERATED file — 15 lines of it in the tracked `examples/capability-gallery.html` — where no
    author could fix it at the source. Every combination is asserted rather than the empty one
    alone, because the repair moves the newlines and the two populated shapes are what would break.
    """

    def _assert_diff_clean(self, rendered: str, shape: str) -> None:
        offenders = [line for line in rendered.splitlines() if line.rstrip() != line]
        self.assertEqual(offenders, [], f"{shape} figure emits {len(offenders)} whitespace line(s)")

    def test_every_optional_row_combination_renders_without_trailing_whitespace(self) -> None:
        self._assert_diff_clean(components.figure("<svg/>", "cap"), "bare")
        self._assert_diff_clean(components.figure("<svg/>", "cap", reader_question="q?"),
                                "insight-only")
        self._assert_diff_clean(components.figure("<svg/>", "cap", "<b>legend</b>"), "legend-only")
        self._assert_diff_clean(
            components.figure("<svg/>", "cap", "<b>legend</b>", reader_question="q?",
                              insight="what it shows"),
            "fully populated")

    def test_the_populated_rows_are_still_emitted(self) -> None:
        """The control: dropping the empty rows must not drop the ones carrying content."""
        rendered = components.figure("<svg/>", "cap", "<b>legend</b>", reader_question="q?",
                                     insight="what it shows")
        self.assertIn('<div class="figure-legend"><b>legend</b></div>', rendered)
        self.assertIn('<div class="figure-reader-question">q?</div>', rendered)
        self.assertIn('<div class="figure-insight">what it shows</div>', rendered)


def _figure(fig_id: str) -> dict[str, Any]:
    """The smallest sidecar entry that parses and renders (kind defaults to ``flowchart``)."""
    return {
        "id": fig_id,
        "title": "t",
        "caption": "c",
        "nodes": [{"id": "n1", "type": "source", "label": "n", "x": 10.0, "y": 10.0}],
        "edges": [],
    }


def _write_pair(root: Path, *, body: str, spec: object | None) -> Path:
    md = root / "doc.md"
    md.write_text(body, encoding="utf-8")
    if spec is not None:
        (root / "doc_spec.json").write_text(json.dumps(spec), encoding="utf-8")
    return md


class FigureSidecarGatesRefuseASilentlyChangedDocument(unittest.TestCase):
    """`P8-036` / `P8-085`. The sidecar gates in ``_load_sibling_figure`` had NO retained
    counter-example at all — ``grep -rn BuildBlockedError tools/tests/*.py`` returned nothing —
    so both directions of "the document and its sidecar disagree" were guarded by code nobody
    was re-running. One of the two directions was not guarded at all.

    Each failure mode below produced a build that reported SUCCESS while silently dropping (or
    silently ignoring) a figure the author wrote.
    """

    def test_a_matching_pair_loads_this_is_the_positive_control(self) -> None:
        """Guard against the vacuous pass: if the loader raised on everything, every assertion
        below would be trivially true (LESSONS.md L-19)."""
        with tempfile.TemporaryDirectory() as td:
            md = _write_pair(Path(td), body="<!-- figure:F1 -->\n", spec=[_figure("F1")])
            figures = _load_sibling_figure(md)
            self.assertEqual(sorted(figures), ["F1"])

    def test_a_document_with_no_figures_and_no_sidecar_is_fine(self) -> None:
        """The second control: absence of a sidecar is legitimate and must NOT block."""
        with tempfile.TemporaryDirectory() as td:
            md = _write_pair(Path(td), body="# plain document\n", spec=None)
            self.assertEqual(_load_sibling_figure(md), {})

    def test_a_referenced_figure_with_no_sidecar_at_all_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            md = _write_pair(Path(td), body="<!-- figure:F1 -->\n", spec=None)
            with self.assertRaises(BuildBlockedError) as caught:
                _load_sibling_figure(md)
            self.assertIn("F1", str(caught.exception))

    def test_a_sidecar_missing_the_referenced_id_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            md = _write_pair(Path(td), body="<!-- figure:F1 -->\n", spec=[_figure("F2")])
            with self.assertRaises(BuildBlockedError) as caught:
                _load_sibling_figure(md)
            self.assertIn("F1", str(caught.exception))

    def test_a_sidecar_id_no_directive_references_blocks(self) -> None:
        """`P8-085`, the direction that was NOT guarded. ``missing`` was computed one-way, so an
        orphan entry — the same rename typo, made in the other file — was parsed, rendered by
        nothing, and the build reported success."""
        with tempfile.TemporaryDirectory() as td:
            md = _write_pair(
                Path(td), body="<!-- figure:F1 -->\n", spec=[_figure("F1"), _figure("ORPHAN")]
            )
            with self.assertRaises(BuildBlockedError) as caught:
                _load_sibling_figure(md)
            self.assertIn("ORPHAN", str(caught.exception))

    def test_the_same_id_declared_twice_blocks(self) -> None:
        """The NEW edge the orphan check opens: two entries sharing an id are neither missing nor
        orphaned, and ``figures[spec.id] = ...`` kept the last one silently."""
        with tempfile.TemporaryDirectory() as td:
            md = _write_pair(
                Path(td), body="<!-- figure:F1 -->\n", spec=[_figure("F1"), _figure("F1")]
            )
            with self.assertRaises(BuildBlockedError) as caught:
                _load_sibling_figure(md)
            self.assertIn("F1", str(caught.exception))

    def test_an_unknown_kind_blocks_rather_than_rendering_a_flowchart(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            entry = _figure("F1")
            entry["kind"] = "flowcart"  # a typo, not a kind
            md = _write_pair(Path(td), body="<!-- figure:F1 -->\n", spec=[entry])
            with self.assertRaises(BuildBlockedError) as caught:
                _load_sibling_figure(md)
            self.assertIn("flowcart", str(caught.exception))

    def test_the_live_corpus_is_clean_under_both_directions(self) -> None:
        """The cost of the new direction, measured rather than assumed: every authored sidecar in
        this repository must still load. A gate that floods the real corpus is a defect."""
        sidecars = sorted(
            p for p in _REPO.rglob("*_spec.json")
            if ".git" not in p.parts and "node_modules" not in p.parts
        )
        self.assertGreaterEqual(len(sidecars), 3, "vacuity guard: the corpus scan found nothing")
        for sidecar in sidecars:
            md = sidecar.with_name(sidecar.name[: -len("_spec.json")] + ".md")
            if not md.is_file():
                continue
            with self.subTest(sidecar=str(sidecar.relative_to(_REPO))):
                _load_sibling_figure(md)


class FigureDispatchIsOneTableNotTwoChains(unittest.TestCase):
    """`P8-090`. Parsing dispatched on ``kind == "..."`` and rendering on
    ``isinstance(spec, ...Spec)`` — two hand-maintained chains, no test asserting they stayed in
    bijection, and a ``visual.render`` fallback that turned any disagreement into a
    silently-wrong FLOWCHART instead of a failure.
    """

    def _fn_source(self, name: str) -> ast.FunctionDef:
        tree = ast.parse(Path(generator.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise AssertionError(f"{name} not found in generator.py")

    def test_the_table_is_populated(self) -> None:
        """Vacuity guard: an empty table would satisfy every assertion below."""
        self.assertGreater(len(generator._FIGURE_KINDS), 10)

    def test_every_kind_carries_a_loader_and_a_renderer(self) -> None:
        for kind, handler in generator._FIGURE_KINDS.items():
            with self.subTest(kind=kind):
                self.assertTrue(callable(handler.load))
                self.assertTrue(callable(handler.render))

    def test_the_visual_spec_family_is_derived_not_copied(self) -> None:
        for kind, renderer in generator._FIGURE_RENDERERS.items():
            self.assertIs(generator._FIGURE_KINDS[kind].render, renderer)

    def test_only_flowchart_renders_through_visual_render(self) -> None:
        """The old fallback was ``_FIGURE_RENDERERS.get(_kind, visual.render)``: any kind the
        render chain did not know rendered as a flowchart. If a second kind ever points at
        ``visual.render`` again, that is the fallback growing back."""
        through_visual = [
            k for k, h in generator._FIGURE_KINDS.items() if h.render is visual.render
        ]
        self.assertEqual(through_visual, ["flowchart"])

    def test_neither_consumer_carries_its_own_dispatch_chain(self) -> None:
        """Parsed with ``ast``, not grepped: a substring scan for ``isinstance`` would match this
        test's own docstring, and a source file can always satisfy a substring check about itself
        (LESSONS.md L-24)."""
        for fn_name in ("_load_sibling_figure", "_render_markdown_body"):
            fn = self._fn_source(fn_name)
            with self.subTest(function=fn_name):
                reads_table = [
                    n for n in ast.walk(fn)
                    if isinstance(n, ast.Name) and n.id == "_FIGURE_KINDS"
                ]
                self.assertTrue(reads_table, f"{fn_name} must dispatch through _FIGURE_KINDS")
                spec_isinstance = [
                    n for n in ast.walk(fn)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "isinstance"
                    and n.args
                    and isinstance(n.args[0], ast.Name)
                    and n.args[0].id == "spec"
                    and isinstance(n.args[-1], ast.Name)
                    and n.args[-1].id.endswith("Spec")
                    and n.args[-1].id != "EChartsFigureSpec"
                ]
                self.assertEqual(
                    [ast.unparse(n) for n in spec_isinstance], [],
                    f"{fn_name} grew a second dispatch chain beside _FIGURE_KINDS",
                )


class ThemeCommentIsEmittedOnlyWhenAThemeIsPinned(unittest.TestCase):
    """`P8-050`. ``_defs_css(theme: str)`` was called with ``str | None``; the mismatch sat in the
    mypy baseline labelled "annotation debt with no behavioural consequence". It had one: the
    f-string stringified ``None``, so every unthemed figure carried the literal
    ``/* theme:None */`` — 4 of 4 native figures in the tracked ``examples/capability-gallery.html``.
    """

    def _spec(self) -> VisualSpec:
        return VisualSpec(id="probe", title="Probe", caption="", nodes=[], edges=[])

    def test_an_unthemed_figure_names_no_theme_at_all(self) -> None:
        svg = visual.render(self._spec())
        self.assertNotIn("theme:None", svg)
        self.assertNotIn("/* theme:", svg)

    def test_a_pinned_theme_is_still_stamped(self) -> None:
        """Two-sided: removing the comment entirely would also pass the test above."""
        self.assertIn("/* theme:dark */", visual.render(self._spec(), theme="dark"))

    def test_an_empty_theme_name_is_not_a_theme(self) -> None:
        """The new edge after narrowing: ``theme=""`` is falsy, and stamping ``/* theme: */``
        would be the same defect with a shorter payload."""
        self.assertNotIn("/* theme:", visual.render(self._spec(), theme=""))

    def test_a_freshly_built_document_carries_no_leak(self) -> None:
        """The probe belongs in the artifact the gate certifies, so it goes end-to-end: build a
        real document and read the rendered HTML. Unit-testing ``_defs_css`` alone would not have
        caught this, since the defect only appears once ``render`` passes its own ``theme=None``
        down. ``sample.md`` is used rather than the flagship gallery because its figure is
        native — the gallery also embeds mermaid/ECharts figures, whose renderers need
        ``npm install``, and an absent node_modules is an environment fact, not a finding about
        the artifact (LESSONS.md L-25).

        NOTE: the COMMITTED ``examples/capability-gallery.html`` still carries 4 copies of the old
        ``/* theme:None */`` and will until it is rebuilt (``python3 -m tools.docgen.cli build
        examples/capability-gallery.md -o examples``). That file is a build product; this test
        asserts the producer, which is what a rebuild copies from.
        """
        out_root = _REPO / ".docgen"  # gitignored build scratch; never a repository file
        out_root.mkdir(exist_ok=True)
        out_dir = Path(tempfile.mkdtemp(dir=out_root))
        try:
            result = generator.build(_REPO / "tools" / "docgen" / "sample.md",
                                     formats=("html",), out_dir=out_dir)
            self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
            html = result.outputs["html"].read_text(encoding="utf-8")
            self.assertIn("fig-figure", html, "vacuity guard: no figure was rendered at all")
            self.assertNotIn("theme:None", html)
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


class EveryDeclaredToolFieldIsReadBySomething(unittest.TestCase):
    """`P8-092`. ``engine.config.json`` declared ``onMissing`` on all four tool blocks, described
    it in the section's own ``_readme`` as part of the discovery order, and NOTHING read it:
    ``git grep '"onMissing"' -- '*.py' '*.mjs'`` returned nothing. A configuration field an
    operator can set and no code consults is worse than an absent one — it documents behaviour
    that does not exist.

    The invariant is stated as "declared implies read", not as "``onMissing`` is gone", so it
    holds whichever way the field is resolved: delete it, or wire it up.
    """

    _DOC_ONLY = frozenset({"_readme", "usedBy"})

    def _config(self) -> dict[str, Any]:
        data: dict[str, Any] = json.loads((_REPO / "engine.config.json").read_text(encoding="utf-8"))
        return data

    def _sources(self) -> str:
        """CODE, with comments and docstrings stripped, and ``tools/tests`` excluded.

        A raw ``grep`` over the tree is not a reader scan: this very test file names
        ``onMissing`` in its own docstring, and so does the sibling guard in
        ``test_cli_surface.py`` — so a plain substring search reports the field as "read" because
        the tests that assert it is unread mention it (LESSONS.md L-24: a guard's own
        documentation can recreate the defect it documents). Python is parsed with ``ast`` and
        only non-docstring string constants survive; JS has its comments removed.
        """
        parts: list[str] = []
        for path in sorted((_REPO / "tools").rglob("*.py")):
            if {"node_modules", "__pycache__", "tests"} & set(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:  # pragma: no cover - a broken source is another gate's problem
                continue
            docstrings = {
                id(node.body[0].value)
                for node in ast.walk(tree)
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef))
                and node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            }
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if id(node) not in docstrings:
                        parts.append(f'"{node.value}"')
                elif isinstance(node, ast.Attribute):
                    parts.append(f'"{node.attr}"')
        block_comment = re.compile(r"/\*.*?\*/", re.DOTALL)
        line_comment = re.compile(r"(?m)//.*$")
        for path in sorted((_REPO / "tools").rglob("*.mjs")):
            if {"node_modules", "tests"} & set(path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            parts.append(line_comment.sub("", block_comment.sub("", text)))
        return "\n".join(parts)

    def test_the_tools_section_is_populated(self) -> None:
        blocks = [k for k in self._config().get("tools", {}) if not k.startswith("_")]
        self.assertGreaterEqual(len(blocks), 3, "vacuity guard: no tool blocks found")

    def test_the_scan_sees_the_fields_that_are_known_to_be_read(self) -> None:
        """Vacuity guard for the reader scan itself: if the corpus read came back empty, every
        field would look unread and the assertion below would fire for the wrong reason — or,
        with the sense flipped, pass for the wrong reason."""
        sources = self._sources()
        for known in ('"envVar"', '"pathFallback"', '"installHint"'):
            self.assertIn(known, sources, f"{known} is read by engine_config; the scan missed it")

    def test_no_tool_field_is_declared_without_a_reader(self) -> None:
        sources = self._sources()
        unread: list[str] = []
        for tool, block in self._config().get("tools", {}).items():
            if tool.startswith("_") or not isinstance(block, dict):
                continue
            for field in block:
                if field in self._DOC_ONLY:
                    continue
                if f'"{field}"' not in sources:
                    unread.append(f"tools.{tool}.{field}")
        self.assertEqual(sorted(set(unread)), [])


class RebaseliningTheRulebookRequiresAVersionBump(unittest.TestCase):
    """`P8-068`. The sanctioned two-step re-baseline accepted ANY rewrite of the locked rule set
    for free: drop ``tools/hooks/pre-push`` from ``rulebook_files``, set the ``PENDING`` sentinel,
    run ``--write-hash`` — three line-edits, ``version`` untouched, no changelog entry, and every
    gate green over the moat's own executable leaving the lock.
    """

    def _fixture(self, tmp: Path, *, version: str = "1.0.0") -> tuple[Path, Path]:
        rules = tmp / "docs" / "design" / "doc-system"
        rules.mkdir(parents=True)
        rule = rules / "RULE.md"
        rule.write_text("# locked rule\noriginal text\n", encoding="utf-8")
        version_json = rules / "VERSION.json"
        version_json.write_text(json.dumps({
            "version": version,
            "rulebook_files": ["docs/design/doc-system/RULE.md"],
            "rulebook_sha256": hashlib.sha256(rule.read_bytes()).hexdigest(),
        }, indent=2) + "\n", encoding="utf-8")
        for argv in (["init", "-q", "."], ["add", "-A"],
                     ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", "-C", str(tmp), *argv], check=True, capture_output=True)
        return rules, version_json

    def _set(self, version_json: Path, **fields: object) -> None:
        data = json.loads(version_json.read_text(encoding="utf-8"))
        data.update(fields)
        version_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_an_unchanged_rule_set_may_be_rebaselined_without_a_bump(self) -> None:
        """Positive control. A re-baseline that changes no locked content has nothing to declare,
        and blocking it would only teach operators to work around the gate."""
        with tempfile.TemporaryDirectory() as td:
            rules, version_json = self._fixture(Path(td))
            self._set(version_json, rulebook_sha256="PENDING")
            result = validate_doc_system.check(rules, version_json_path=version_json,
                                              write_hash=True)
            self.assertFalse(result.blocked, [f.message for f in result.findings])

    def test_changed_rule_content_without_a_bump_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rules, version_json = self._fixture(Path(td))
            (rules / "RULE.md").write_text("# locked rule\nsomeone else's text\n", encoding="utf-8")
            self._set(version_json, rulebook_sha256="PENDING")
            result = validate_doc_system.check(rules, version_json_path=version_json,
                                              write_hash=True)
            self.assertTrue(result.blocked)
            self.assertIn("version", result.findings[0].message)
            self.assertEqual(
                json.loads(version_json.read_text(encoding="utf-8"))["rulebook_sha256"], "PENDING",
                "a refused re-baseline must not have written anything",
            )

    def test_dropping_a_file_from_the_locked_set_without_a_bump_is_refused(self) -> None:
        """The measured attack: the file set shrinks, so no individual file's bytes changed."""
        with tempfile.TemporaryDirectory() as td:
            rules, version_json = self._fixture(Path(td))
            self._set(version_json, rulebook_files=[], rulebook_sha256="PENDING")
            result = validate_doc_system.check(rules, version_json_path=version_json,
                                              write_hash=True)
            self.assertTrue(result.blocked)

    def test_a_bumped_version_completes_the_rebaseline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rules, version_json = self._fixture(Path(td))
            (rules / "RULE.md").write_text("# locked rule\ndeclared new text\n", encoding="utf-8")
            self._set(version_json, rulebook_sha256="PENDING", version="1.1.0")
            result = validate_doc_system.check(rules, version_json_path=version_json,
                                              write_hash=True)
            self.assertFalse(result.blocked, [f.message for f in result.findings])
            written = json.loads(version_json.read_text(encoding="utf-8"))["rulebook_sha256"]
            self.assertRegex(written, r"^[0-9a-f]{64}$")

    def test_a_version_moved_backwards_is_not_a_bump(self) -> None:
        """The new edge: "the version changed" is not the invariant — "the version advanced" is."""
        with tempfile.TemporaryDirectory() as td:
            rules, version_json = self._fixture(Path(td), version="1.2.0")
            (rules / "RULE.md").write_text("# locked rule\nquietly different\n", encoding="utf-8")
            self._set(version_json, rulebook_sha256="PENDING", version="1.1.0")
            result = validate_doc_system.check(rules, version_json_path=version_json,
                                              write_hash=True)
            self.assertTrue(result.blocked)

    def test_an_unverifiable_rebaseline_fails_closed(self) -> None:
        """No git history means the previous rule set cannot be recovered, so the bump cannot be
        checked. "I could not verify" is not "verified"."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rules = tmp / "docs" / "design" / "doc-system"
            rules.mkdir(parents=True)
            (rules / "RULE.md").write_text("# locked rule\n", encoding="utf-8")
            version_json = rules / "VERSION.json"
            version_json.write_text(json.dumps({
                "version": "1.0.0",
                "rulebook_files": ["docs/design/doc-system/RULE.md"],
                "rulebook_sha256": "PENDING",
            }, indent=2) + "\n", encoding="utf-8")
            result = validate_doc_system.check(rules, version_json_path=version_json,
                                              write_hash=True)
            self.assertTrue(result.blocked)
            self.assertRegex(result.findings[0].message, r"(?i)refused")

    def test_the_plain_check_path_is_untouched_by_this_change(self) -> None:
        """Two-sided at the API boundary: the refusal is bolted onto ``--write-hash`` ONLY.
        An ordinary check of a consistent rule layer must still pass with no version bump in
        sight, or every health run would start failing on a rule layer nobody edited.

        (Deliberately run against a hermetic fixture rather than the live tree: whether the real
        rule layer is currently drifting is a property of somebody's uncommitted work, not of this
        gate — ``tools.health`` RULE-01 owns that question. LESSONS.md L-25.)
        """
        with tempfile.TemporaryDirectory() as td:
            rules, version_json = self._fixture(Path(td))
            result = validate_doc_system.check(rules, version_json_path=version_json)
            self.assertFalse(result.blocked, [f.message for f in result.findings])


class VersionBumpArithmetic(unittest.TestCase):
    """The comparison ``_is_bumped`` performs, in isolation from git."""

    def test_a_higher_dotted_version_is_a_bump(self) -> None:
        self.assertTrue(validate_doc_system._is_bumped("1.2.9", "1.3.0"))
        self.assertTrue(validate_doc_system._is_bumped("1.2.9", "1.2.10"))

    def test_an_equal_or_lower_version_is_not(self) -> None:
        self.assertFalse(validate_doc_system._is_bumped("1.2.9", "1.2.9"))
        self.assertFalse(validate_doc_system._is_bumped("1.2.9", "1.2.8"))
        self.assertFalse(validate_doc_system._is_bumped("1.10.0", "1.9.0"))

    def test_an_unparseable_scheme_falls_back_to_inequality(self) -> None:
        self.assertTrue(validate_doc_system._is_bumped("2026-08-01", "2026-08-02"))
        self.assertFalse(validate_doc_system._is_bumped("2026-08-01", "2026-08-01"))

    def test_no_previous_version_is_always_a_bump(self) -> None:
        self.assertTrue(validate_doc_system._is_bumped(None, "1.0.0"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
