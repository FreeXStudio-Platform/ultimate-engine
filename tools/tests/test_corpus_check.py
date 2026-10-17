"""Retained counter-examples for every guard in `tools/corpus_check/`.

`docs/process/RULES.md` **Rule 1**: *anything that can fail ships with the input that makes it fail,
committed as a test that runs on every health run. A falsification performed once by hand and not
retained does not count.*

**Two-sided, every time.** "Does it refuse a bad corpus?" passes vacuously for a guard that refuses
everything, so each guard is asserted to **accept this repository as it stands** and to **refuse a
planted defect**. The clean half is not a formality: it is what makes a red mean something.

**The probe covers the CLASS, not the instance.** Rule 1's hardest clause, earned when a critic
found that four of four serious fixes had *moved* a hole rather than closed it. So `register` is
probed with a duplicate id **and** a ragged row **and** an undeclared term; `built-claims` with a
bad module **and** a bad subcommand **and** a bad flag.

**Two probes exist because a guard silently stopped working while being written**, and they are the
most valuable tests in this file:

* `test_over_broad_exemption_does_not_disarm_present_tense` — a bare ``" deliberately"`` in the
  exemption list matched *"deliberately falsified"* in `BUILD_PLAN.md`'s Phase 3 row and switched
  the guard off on the single row it existed to catch.
* `test_one_declared_drift_is_not_a_blanket_amnesty` — `stamps` treated any handover carrying
  ``NEEDS RE-HARDENING`` as excusing every drifted stamp in the corpus.

Both went green while being wrong. Neither would have been caught by a test that only asked "does
the guard fire on an obvious defect?"
"""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Protocol, cast

from tools.corpus_check.corpus import Corpus, repo_root
from tools.corpus_check.guards import (
    GUARDS,
    built_claims,
    counts,
    cross_doc,
    crossrefs,
    guard_names,
    present_tense,
    register,
    rendered_output,
    stamps,
    symbols,
    test_refs,
)
from tools.corpus_check.model import GuardResult, Severity, Status
from tools.tests import lab

_ROOT = repo_root()

class _GuardModule(Protocol):
    """The shape every guard module exposes: a name and a runner.

    Declared so the derived guard set (`OG-80`) stays `mypy --strict` clean — `inspect.getmodule`
    returns `ModuleType`, which has no `GUARD`/`run`, and typing the list as `object` merely moved
    the error into six attribute accesses.
    """

    GUARD: str

    def run(self, corpus: Corpus) -> GuardResult: ...



# The lab helpers live in `tools/tests/lab.py` — ONE implementation, imported by every probe
# module that needs a throwaway repository. They were duplicated here and in the Phase-5 probes,
# and the two copies had already drifted (`RULES.md` Rule 1). These aliases keep this file's
# existing call sites unchanged while the implementation stays single.
_git = lab.git
_commit_all = lab.commit_all
_build_lab = lab.build_lab
_force_rmtree = lab.force_rmtree


class _LabCase(lab.LabCase):
    """Base class owning one faithful copy of the corpus (`tools/tests/lab.py`)."""

    lab_prefix = "corpus-lab-"

    def corpus(self) -> Corpus:
        """A FRESH corpus each call — `Corpus` caches file text and the tracked listing."""
        return Corpus(root=self.lab)

    def plant(self, rel: str, body: str) -> None:
        """Write a document into the lab and track it, so guards can see it."""
        path = self.lab / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        _git(self.lab, "add", rel)

    def remove(self, rel: str) -> None:
        _git(self.lab, "rm", "-q", "-f", rel)

    def assert_finds(self, result: object, needle: str) -> None:
        assert isinstance(result, object)
        findings = getattr(result, "findings", [])
        blob = " ".join(f"{f.path}:{f.line} {f.message} {f.evidence}" for f in findings)
        self.assertEqual(
            getattr(result, "status", None),
            Status.FAIL,
            f"guard passed on a planted defect; it examined "
            f"{getattr(result, 'checked', '?')} claim(s)",
        )
        self.assertIn(needle, blob)


# =================================================================================================
# The clean half — every guard accepts this repository as it stands.
# =================================================================================================


class CleanCorpusIsAccepted(_LabCase):
    """A guard that refuses everything is not a guard. Each must pass on the real corpus."""

    @staticmethod
    def _textual_guards() -> list[_GuardModule]:
        """Every registered guard except the one that builds — derived from `GUARDS` (`OG-80`).

        `rendered-output` is excluded by NAME rather than by omission from a list, so registering a
        new guard puts it under these assertions immediately and only a deliberate, visible edit can
        take it back out.
        """
        import inspect

        modules: list[_GuardModule] = []
        for name, fn in GUARDS:
            if name == rendered_output.GUARD:
                continue
            module = inspect.getmodule(fn)
            if module is not None:
                modules.append(cast("_GuardModule", module))
        return modules

    def test_the_registry_is_covered_and_nonempty(self) -> None:
        """The derivation itself must not silently shrink."""
        self.assertEqual(len(GUARDS), len(guard_names()))
        self.assertGreaterEqual(len(GUARDS), 10, "the registry lost a guard")
        self.assertEqual(len(self._textual_guards()), len(GUARDS) - 1)

    def test_every_textual_guard_passes_on_the_real_corpus(self) -> None:
        """**The guard set is DERIVED from `GUARDS`, never listed here.**

        `tools/corpus_check/guards/__init__.py` says "add a guard by adding one line to `GUARDS`" —
        but this file used to iterate a hand-written tuple, so a newly registered guard was covered
        by nothing. A Pass-6 verifier registered a guard returning `checked=0` in a lab: it appeared
        in `--list`, it ran, and every test still passed. A guard that examines nothing shipped
        green, which is the vacuous pass this whole package exists to catch (`OG-80`).
        """
        for module in self._textual_guards():
            with self.subTest(guard=module.GUARD):
                result = module.run(self.corpus())
                if result.status is Status.SKIP:
                    # A lab is a FRESH git history, so a stamp naming a real upstream commit is
                    # unverifiable here through no fault of the corpus. `stamps` reports that as a
                    # SKIP with its cause named, which is the honest answer (`L-25`) — but a SKIP
                    # is never a pass, so it is accepted only when the guard says WHY.
                    self.assertTrue(
                        result.summary.strip(),
                        f"{module.GUARD} skipped without naming a cause",
                    )
                    continue
                self.assertEqual(
                    result.status, Status.PASS,
                    f"{module.GUARD} failed on the clean corpus: {result.summary}\n"
                    + "\n".join(f.render() for f in result.sorted_findings()[:6]),
                )

    def test_no_guard_passes_vacuously(self) -> None:
        """Every guard must have examined at least its own declared floor.

        `LESSONS.md` L-19: a check that validates only the claims it can find passes over a
        document containing none. The floor is the guard's own declaration of how much it must see
        before its green means anything.
        """
        for module in self._textual_guards():
            with self.subTest(guard=module.GUARD):
                result = module.run(self.corpus())
                if result.status is Status.SKIP:
                    # The floor asks "did a PASS see enough to mean anything?". A SKIP is already
                    # not a pass, and demanding a floor of it would force the guard to fake a
                    # count — the exact dishonesty this test exists to prevent.
                    continue
                # **The floor itself must be positive** (`OG-122`). This assertion compares
                # `checked` against a number the guard under test SUPPLIES, so a guard declaring
                # `floor=0` satisfied it with `checked=0` — vacuous, and green. Measured: a
                # `probe-guard` returning `passed(..., checked=0, floor=0)` was registered in a lab
                # and the full Python suite exited 0. `OG-80` derived the guard LIST from `GUARDS`
                # so a new guard cannot escape the suite; this is the same defect one level in —
                # the guard escaping the assertion's meaning rather than its coverage.
                self.assertGreaterEqual(
                    result.floor, 1,
                    f"{module.GUARD} declares floor={result.floor}: a floor of zero makes this "
                    "assertion unfalsifiable, so the guard could examine nothing and still pass",
                )
                self.assertGreaterEqual(
                    result.checked, result.floor,
                    f"{module.GUARD} examined {result.checked} claim(s), floor {result.floor}",
                )


# =================================================================================================
# The dirty half — one class-representative probe per failure mode.
# =================================================================================================


class RegisterIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_REGISTER.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_duplicate_id_is_refused(self) -> None:
        """The defect this guard was written for: eleven ids naming two rows each."""
        self.plant(self._REL, "# probe\n\n| id | note |\n|---|---|\n| PB-01 | first |\n| PB-01 | second |\n")
        self.assert_finds(register.run(self.corpus()), "duplicate register id 'PB-01'")

    def test_ragged_row_is_refused(self) -> None:
        """A row short of a column does not error — it shifts every later cell left."""
        self.plant(self._REL, "# probe\n\n| id | a | b |\n|---|---|---|\n| PB-02 | x |\n")
        self.assert_finds(register.run(self.corpus()), "the header declares 3")

    def test_undeclared_vocabulary_term_is_refused(self) -> None:
        """A row carrying a term its own document never defines cannot be classified."""
        self.plant(
            self._REL,
            "# probe\n\n| disposition | meaning |\n|---|---|\n| OPEN | still open |\n\n"
            "| id | disposition |\n|---|---|\n| PB-03 | INVENTED |\n",
        )
        self.assert_finds(register.run(self.corpus()), "'INVENTED' is not declared")


class CrossrefsIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_LINKS.md"

    def test_a_reference_style_link_with_no_definition_is_refused(self) -> None:
        """`OG-111` / `P6-67` — recorded in Pass 6, not fixed, found again in Pass 7.

        `[text][label]` with no `[label]: target` renders LITERALLY: the reader sees the brackets
        on the page. `_LINK_RE` is anchored on `](`, so this whole form was invisible, and the
        guard reported "all 1 internal link target(s) resolve across 58 documents" — a green whose
        own coverage number said it was seeing almost nothing.
        """
        self.plant(self._REL, "# probe\n\nSee [the plan][no_such_label] for details.\n")
        self.assert_finds(crossrefs.run(self.corpus()), "no_such_label")

    def test_a_defined_reference_style_link_is_accepted(self) -> None:
        """Two-sided: reporting every reference-style link would be its own defect."""
        self.plant(
            self._REL,
            "# probe\n\nSee [the charter][ch] for details.\n\n[ch]: docs/CHARTER.md\n",
        )
        result = crossrefs.run(self.corpus())
        self.assertNotIn("PROBE_LINKS", " ".join(f.path for f in result.findings))

    def test_css_selectors_and_js_indexing_in_a_built_page_are_not_reference_links(self) -> None:
        """`OG-264`. A tracked HTML page's `<style>`, `<script>` and `<svg>` are code, and `[a][b]` is everyday syntax in
        them (`[data-k="node"][data-id="n0"]`, `rows[i][j]`): the flagship gallery reported 221 dead reference-style
        links the day its figures gained scoped hover CSS."""
        self.plant(
            "docs/process/PROBE_PAGE.html",
            "<html><head><style>svg[data-fig=\"a\"] [data-k=\"node\"][data-id=\"n0\"]:hover{opacity:1}</style></head>"
            "<body><script>const x = rows[i][j];</script>"
            "<svg><style>[data-k=\"edge\"][data-id=\"e0\"]{stroke:red}</style></svg><p>fine</p></body></html>\n",
        )
        try:
            result = crossrefs.run(self.corpus())
            self.assertNotIn("PROBE_PAGE", " ".join(f.path for f in result.findings))
        finally:
            self.remove("docs/process/PROBE_PAGE.html")

    def test_an_unrendered_reference_link_in_a_page_text_node_is_still_refused(self) -> None:
        """Two-sided: masking code regions must not blind the check to the thing it exists for — the reader seeing
        `[text][label]` on the page."""
        self.plant("docs/process/PROBE_PAGE2.html", "<html><body><p>See [the plan][never_defined] for details.</p></body></html>\n")
        try:
            self.assert_finds(crossrefs.run(self.corpus()), "never_defined")
        finally:
            self.remove("docs/process/PROBE_PAGE2.html")

    def test_a_dead_html_href_is_refused(self) -> None:
        """A dead `href` in a built page survives longer than a dead Markdown link, because
        nothing renders it differently — doctrine §8.4's class seen from the other side."""
        self.plant(
            self._REL,
            '# probe\n\n<a href="docs/plan/NO_SUCH_PLAN_HTML.md">this</a>\n',
        )
        self.assert_finds(crossrefs.run(self.corpus()), "NO_SUCH_PLAN_HTML.md")

    def test_a_quoted_dead_link_in_a_dated_record_is_not_reported(self) -> None:
        """`VERIFICATION_LOG.md` quotes the probes a pass ran, dead links and all.

        Reporting those is reporting the log for recording what it found — the failure mode that
        makes people switch a gate off. Same dated-heading test the rest of the package uses.
        """
        self.plant(
            self._REL,
            "<!-- record: append-only -->\n# probe\n\n## Pass 99 — 2026-08-22\n\n"
            "The probe used [the plan][gone_label].\n",
        )
        result = crossrefs.run(self.corpus())
        self.assertNotIn("PROBE_LINKS", " ".join(f.path for f in result.findings))

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_dead_link_target_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\nSee [the plan](docs/plan/NO_SUCH_PLAN.md) for detail.\n")
        self.assert_finds(crossrefs.run(self.corpus()), "docs/plan/NO_SUCH_PLAN.md")

    def test_dead_anchor_is_refused(self) -> None:
        """The rot this guard is really for: a heading renamed three documents away."""
        self.plant(self._REL, "# probe\n\n## Real heading\n\nSee [above](#a-heading-that-was-renamed).\n")
        self.assert_finds(crossrefs.run(self.corpus()), "a-heading-that-was-renamed")

    def test_dead_anchor_in_another_document_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\nSee [the charter](docs/CHARTER.md#no-such-section).\n")
        self.assert_finds(crossrefs.run(self.corpus()), "no-such-section")


class SymbolsIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_SYMBOLS.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_nonexistent_module_path_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\nThe work happens in `tools.docgen.no_such_module`.\n")
        self.assert_finds(symbols.run(self.corpus()), "tools.docgen.no_such_module")

    def test_nonexistent_symbol_in_a_real_module_is_refused(self) -> None:
        """The `CONS-07` defect one document over: a real module, a fabricated symbol.

        The probe cites the module's PATH as well as the symbol, because that is the guard's
        stated contract — a bare ``foo.bar`` is only judged where the document is demonstrably
        about ``foo``. The first version of this probe omitted the path and the guard correctly
        said nothing, which is a test that would have passed for the wrong reason.
        """
        self.plant(
            self._REL,
            "# probe\n\nThe gate spine lives in `tools/docgen/export_sanitizer.py`, and its order "
            "is `export_sanitizer.NO_SUCH_CONSTANT`.\n",
        )
        self.assert_finds(symbols.run(self.corpus()), "NO_SUCH_CONSTANT")

    def test_a_gate_label_is_not_read_as_a_module_attribute(self) -> None:
        """Seventeen gates are named with a dot, so every one matches the module-symbol pattern.

        Measured 2026-08-29: a row added to `OPEN_GATES.md` named `tools/docgen/visual.py`, which
        made the document "about" `visual` and switched on checking for a `visual.collision`
        written months earlier as a GATE TOKEN. The guard then reported, correctly by its own rule
        and wrongly in fact, that `visual.py` defines no `collision`.

        The probe cites the module path deliberately, because without it the guard would stay quiet
        for the *wrong* reason and the test would pass while proving nothing.
        """
        self.plant(
            self._REL,
            "# probe\n\nThe renderer is `tools/docgen/visual.py`, and its gate is "
            "`visual.collision`.\n",
        )
        result = symbols.run(self.corpus())
        self.assertNotIn("PROBE_SYMBOLS", " ".join(f.path for f in result.findings))

    def test_the_gate_label_exemption_does_not_blanket_the_check(self) -> None:
        """The NEW edge of the narrowing above — the widest input that still gets through.

        `RULES.md` Rule 1's corollary: after narrowing anything, attack its new boundary. The
        exemption is by EXACT gate token, so a dotted citation on the same module that is *not* a
        gate must still be refused. Without this, the fix would have been indistinguishable from
        switching the guard off for every module whose name appears in a gate label.
        """
        self.plant(
            self._REL,
            "# probe\n\nThe renderer is `tools/docgen/visual.py`, and it exposes "
            "`visual.no_such_function`.\n",
        )
        self.assert_finds(symbols.run(self.corpus()), "no_such_function")

    def test_a_basename_collision_is_not_read_as_a_citation(self) -> None:
        """The other side of the same rule, and a real false positive it produced.

        `vault-graph-engine/VAULT_GRAPH_SPEC.md` describes a data field ``counts.totp``. The day
        this package added a module called `counts`, the guard reported a JSON key as a missing
        Python symbol — at HIGH, in a document that has nothing to do with the module.
        """
        self.plant(self._REL, "# probe\n\nThe payload carries `counts.totp` and `counts.hotp`.\n")
        result = symbols.run(self.corpus())
        self.assertNotIn("PROBE_SYMBOLS", " ".join(f.path for f in result.findings))

    def test_a_bare_filename_that_resolves_to_NOTHING_is_refused(self) -> None:
        """`OG-98` — `CONS-06` needs a directory prefix, so a bare filename is invisible to it.

        This guard is the only thing that can see `` `ghost_module.py` `` written without a path,
        and it covered exactly three extensions — `py`, `mjs`, `sh`. A Pass-7 probe walked bare
        `.js`, `.ts`, `.md` and `.json` citations straight past it, and the widened pattern then
        found **18 live bare citations in the corpus resolving to nothing**, one of them in the
        engine's own README. The hole had moved one extension over, which is `LESSONS.md` L-26.

        Derived from `_BARE_SOURCE_RE` itself, so an extension added later is probed rather than
        silently trusted — the failure this test exists to prevent, applied to the test.
        """
        extensions = re.findall(r"[a-z0-9]+", symbols._BARE_SOURCE_RE.pattern.split("(?:")[1])
        self.assertGreaterEqual(len(extensions), 3, "extension list unreadable; probe is vacuous")
        for ext in extensions:
            with self.subTest(extension=ext):
                self.plant(
                    self._REL,
                    f"# probe\n\nSee `no_such_ghost_file.{ext}` for the details.\n",
                )
                self.assert_finds(symbols.run(self.corpus()), f"no_such_ghost_file.{ext}")

    def test_a_bare_filename_that_DOES_resolve_is_not_reported(self) -> None:
        """Two-sided: the widened pattern must not start reporting real files.

        Without this, deleting the resolution step would satisfy the probe above.
        """
        self.plant(self._REL, "# probe\n\nSee `materialise.py` and `install.sh` for the details.\n")
        result = symbols.run(self.corpus())
        self.assertNotIn(
            "PROBE_SYMBOLS", " ".join(f.path for f in result.findings),
            "a bare citation of a file that really exists was reported",
        )

    def test_a_filename_is_not_read_as_a_symbol(self) -> None:
        """The false-positive class that produced 61 of 67 findings on the first real run."""
        self.plant(self._REL, "# probe\n\nThe gate lives in `validate_doc_system.py`.\n")
        result = symbols.run(self.corpus())
        blob = " ".join(f.message for f in result.findings)
        self.assertNotIn("defines no `py`", blob)

    def test_fallback_a_symbol_named_only_in_a_comment_does_not_satisfy_a_citation(self) -> None:
        """`OG-219` — the text FALLBACK (used for a `.mjs`/`.sh` that won't parse as Python, or a
        definition-free Python module) searched the RAW source, so a symbol named only in a `//` or
        `#` comment satisfied a citation. A verifier cited a symbol living only in an `.mjs` comment
        and it passed. The fallback now strips comments per language first; these plant that exact
        shape against `_names_or_text` directly, so the probe cannot share the fallback's blind spot.
        """
        # A `.mjs` module: unparseable as Python -> fallback. Comment mention must NOT satisfy…
        self.assertFalse(
            symbols._names_or_text("// exports DETERMINISM someday\nexport const x = 1;\n",
                                   "DETERMINISM", suffix=".mjs"))
        # …but a real export must.
        self.assertTrue(
            symbols._names_or_text("export function DETERMINISM() {}\n", "DETERMINISM", suffix=".mjs"))
        # A definition-free Python module: `_defined_names` is empty -> fallback. A docstring or a
        # `#` comment mention must NOT satisfy; a real binding must.
        self.assertFalse(
            symbols._names_or_text('"""names RULEBOOK in prose only"""\n', "RULEBOOK", suffix=".py"))
        self.assertFalse(
            symbols._names_or_text("# RULEBOOK is referenced here\nx = 1\n", "RULEBOOK", suffix=".py"))
        self.assertTrue(
            symbols._names_or_text("RULEBOOK = 1\n", "RULEBOOK", suffix=".py"))
        # A `.sh` module: a symbol only in a `#` comment must not satisfy.
        self.assertFalse(
            symbols._names_or_text("echo hi # DETERMINISM is legacy\n", "DETERMINISM", suffix=".sh"))
        # OG-224 round 3: a REAL definition after a URL string on the same line must still resolve —
        # the round-2 stripper stripped the `//` in the URL as a comment and ate the definition,
        # so the guard fabricated a HIGH "defines no REAL_DEF" against a true citation.
        self.assertTrue(
            symbols._names_or_text('const u = "https://x.example"; export const REAL_DEF = 7;\n',
                                   "REAL_DEF", suffix=".mjs"))


class TestRefsIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_TESTREFS.md"

    def test_a_false_test_citation_in_a_LIVE_document_is_refused(self) -> None:
        """The live half — an undated document claiming a test that does not exist."""
        self.plant(
            self._REL,
            "# probe\n\nGuarded by `test_no_such_retained_counter_example_exists`.\n",
        )
        self.assert_finds(
            test_refs.run(self.corpus()), "test_no_such_retained_counter_example_exists"
        )

    def test_the_same_citation_under_a_DATED_heading_is_a_record(self) -> None:
        """`OG-137` — `VERIFICATION_LOG.md` records each pass against the commit it ran on, and a
        pass's whole job is to name the tests it found, including ones a later fix renamed. The
        guard reported the append-only history for accurately recording what it saw.

        Both halves together pin the boundary: a live claim must resolve, a dated record need not.
        """
        self.plant(
            self._REL,
            "<!-- record: append-only -->\n# probe\n\n## Pass 99 — 2026-08-23, commit `abc1234`\n\n"
            "The pass found `test_no_such_retained_counter_example_exists` passing for the "
            "wrong reason.\n",
        )
        result = test_refs.run(self.corpus())
        self.assertNotIn(
            "PROBE_TESTREFS", " ".join(f.path for f in result.findings),
            "a dated verification record was reported for naming a test that has since been renamed",
        )

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_nonexistent_check_id_is_refused(self) -> None:
        """`CONS-99` uses a prefix the source really defines, so it IS a check citation."""
        self.plant(self._REL, "# probe\n\nGuarded by `CONS-99` on every run.\n")
        self.assert_finds(test_refs.run(self.corpus()), "CONS-99")

    def test_nonexistent_test_name_is_refused(self) -> None:
        """The doctrine's opening example: a document claiming a test that never existed."""
        self.plant(self._REL, "# probe\n\nDrift is prevented by `test_no_such_guard`.\n")
        self.assert_finds(test_refs.run(self.corpus()), "test_no_such_guard")

    def test_a_register_key_is_not_read_as_a_check_id(self) -> None:
        """`OG-*` is not a source-defined prefix, so it is `cross-doc`'s question, not this one."""
        self.plant(self._REL, "# probe\n\nRecorded as `OG-06`.\n")
        result = test_refs.run(self.corpus())
        self.assertNotIn("OG-06", " ".join(f.message for f in result.findings))

    def test_a_SHELL_COMMENT_does_not_widen_the_id_vocabulary(self) -> None:
        """`P8-053` — `.sh` sources were harvested with raw full-text regex, no comment stripping.

        Live reproduction at `e8c32ba`: appending ``# coverage note: see "SUITE-99" in the
        register`` to `tools/hooks/install.sh` flipped a genuinely-refused citation to a clean
        pass. Same shape as the docstring hole `.py` was fixed for — a comment is prose about the
        code, not a definition — applied to the one source family that has no docstring concept
        but does have comments.
        """
        self.plant(self._REL, '# probe\n\nCoverage is asserted by `SUITE-99`.\n')
        self.assert_finds(test_refs.run(self.corpus()), "SUITE-99")

        rel = "tools/hooks/install.sh"
        original = self.lab.joinpath(rel).read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plant(rel, original))
        self.plant(rel, original + '\n# coverage note: see "SUITE-99" in the register\n')

        self.assert_finds(test_refs.run(self.corpus()), "SUITE-99")

    def test_a_JS_COMMENT_does_not_widen_the_id_vocabulary(self) -> None:
        """The other non-`.py`, non-`.sh` source family this guard scans textually.

        `//` and `/* */` comments carry the identical risk a `.sh` `#` comment does, and neither
        has a docstring `ast` can strip.
        """
        self.plant(self._REL, '# probe\n\nCoverage is asserted by `SUITE-98`.\n')
        self.assert_finds(test_refs.run(self.corpus()), "SUITE-98")

        rel = "tools/mermaid-engine/render.mjs"
        original = self.lab.joinpath(rel).read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plant(rel, original))
        self.plant(
            rel,
            original + '\n// coverage note: see "SUITE-98" in the register\n'
            '/* also claimed here: "SUITE-98" */\n',
        )

        self.assert_finds(test_refs.run(self.corpus()), "SUITE-98")


# One synthetic sentence per `counts` claim family, in the shape the corpus really writes them.
# Used to prove each pattern can still fire — six families match nothing in this corpus today, and
# a dead regex is indistinguishable from an absent claim at runtime (`OG-87`).
_SAMPLE_CLAIM = {
    "tracked documents": "This repository holds {n} tracked Markdown documents.",
    "governed documents": "Of those, {n} governed by the engine.",
    "manifest rows": "The manifest ships {n} manifest rows.",
    "doc-type prefixes": "The taxonomy registers {n} doc-type prefixes.",
    "L11 rows": "The matrix carries {n} L11 tie-breaker rows.",
    "locked rulebook files": "The hash covers {n} locked rulebook files.",
    "highest law": "The rulebook is L1-L{n}, generic.",
    "registered health checks": "The engine runs {n} health checks.",
    "registered corpus guards": "The checker has {n} registered guards.",
    "retained counter-examples": "The suite holds {n} retained counter-examples.",
    "open blocking rows": "The register carries {n} open blocking rows.",
    "gate functions": "The sanitizer defines {n} gate functions.",
    "gate labels": "The spine orders {n} gate labels.",
}


class CountsIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_COUNTS.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_wrong_document_count_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\nThis repository holds 9999 tracked Markdown documents.\n")
        self.assert_finds(counts.run(self.corpus()), "states 9999 tracked documents")

    def test_wrong_law_range_is_refused(self) -> None:
        """`OG-27`'s class: a stated spine length that the source contradicts."""
        self.plant(self._REL, "# probe\n\nThe rulebook is L1-L99, generic.\n")
        self.assert_finds(counts.run(self.corpus()), "highest law")

    def test_every_claim_family_pattern_still_matches_something(self) -> None:
        """**Each pattern is proven capable, because runtime cannot prove it** (`OG-87`).

        Six of nine families match zero lines in this corpus — which is Rule 2 being *obeyed*, not a
        defect: the documents genuinely do not restate those facts. But a family that matches
        nothing is indistinguishable at runtime from a family whose regex silently broke, and the
        guard used to report all nine as "measurable" either way.

        So each family gets a synthetic claim built from its own derived truth, plus a wrong one.
        The pattern must find the number in both — proving it can still fire — and the guard must
        report the wrong one.
        """
        from tools.corpus_check.guards.counts import CLAIMS, _stated

        corpus = self.corpus()
        exercised = 0
        for claim in CLAIMS:
            with self.subTest(family=claim.name):
                real = claim.derive(corpus)
                self.assertIsNotNone(
                    real, f"{claim.name}: ground truth is not derivable from this corpus"
                )
                sample = _SAMPLE_CLAIM[claim.name]
                assert real is not None
                # `real + 7`, never a fixed literal: most family patterns cap the number at three
                # digits (`highest law` at two), so a `9999` probe silently fails to match and the
                # test would prove nothing. +7 also survives the truth shifting by one when a probe
                # document is planted, which is what makes the "tracked documents" family testable
                # at all.
                for value in (real, real + 7):
                    text = sample.format(n=value)
                    match = claim.pattern.search(text)
                    self.assertIsNotNone(
                        match, f"{claim.name}: pattern no longer matches its own claim shape: {text!r}"
                    )
                    assert match is not None
                    self.assertEqual(_stated(match), value, f"{claim.name}: wrong number extracted")
                exercised += 1
        self.assertEqual(exercised, len(CLAIMS), "a family was skipped")

    def test_a_wrong_count_is_refused_for_every_family(self) -> None:
        """The other side: each family, planted wrong in a real document, must go red."""
        from tools.corpus_check.guards.counts import CLAIMS

        for claim in CLAIMS:
            with self.subTest(family=claim.name):
                real = claim.derive(self.corpus())
                assert real is not None
                wrong = real + 7
                self.plant(self._REL, "# probe\n\n" + _SAMPLE_CLAIM[claim.name].format(n=wrong) + "\n")
                # The FAMILY-SPECIFIC message, not just the number: planting a document changes the
                # tracked-document count, so other families legitimately fire too and a bare
                # number-match would pass on someone else's finding.
                self.assert_finds(counts.run(self.corpus()), f"states {wrong} {claim.name}")

    def test_a_dated_claim_is_read_as_history_not_as_a_lie(self) -> None:
        """A release note that was accurate when written must not be reported as stale."""
        self.plant(
            self._REL,
            "# probe\n\n## [9.9.9] - 2020-01-01\n\nAt the time this held 4 tracked documents.\n",
        )
        result = counts.run(self.corpus())
        self.assertNotIn("PROBE_COUNTS", " ".join(f.path for f in result.findings))

    def test_the_word_and_bold_digit_spellings_are_recognized_and_true(self) -> None:
        """`P8-042` — the two alternative spellings must be readable, and resolve to what they spell.

        Not run through `counts.run()`: planting ANY new tracked document shifts the "tracked
        documents" ground truth by one, which independently mismatches other live claims — a real,
        unrelated side effect, not a defect in this fix. Testing the claim's own pattern directly
        isolates the one thing this test is about.

        **Rewritten 2026-08-24, and the reason is the probe's own subject** (`LESSONS.md` L-37).
        It used to assert that each sample spelling resolved to the LIVE guard count, which held
        only while that count was exactly ten. Phase 4 registered an eleventh guard and the probe
        went red — not because a spelling stopped being readable, but because the corpus improved
        underneath a borrowed number. What is durable is that a spelling resolves to the number it
        SPELLS; that the live count is readable is asserted separately, from the live count.
        """
        from tools.corpus_check.guards.counts import CLAIMS, _stated

        claim = next(c for c in CLAIMS if c.name == "registered corpus guards")
        real = claim.derive(self.corpus())
        assert real is not None

        for text, spelled in (
            ("The engine ships ten guards over its own corpus.", 10),
            ("Stats: **10 guards** across the checker.", 10),
        ):
            with self.subTest(text=text):
                match = claim.pattern.search(text)
                self.assertIsNotNone(match, f"pattern does not match the wording {text!r}")
                assert match is not None
                self.assertEqual(_stated(match), spelled, f"{text!r} did not resolve to {spelled}")

        # ...and the family can still read a sentence stating the count the corpus actually has,
        # whatever that is today. Built FROM the derived value, so it can never go stale.
        live = f"Stats: **{real} guards** across the checker."
        match = claim.pattern.search(live)
        self.assertIsNotNone(match, f"pattern cannot read the live count spelled as {live!r}")
        assert match is not None
        self.assertEqual(_stated(match), real)

    def test_an_added_guard_exposes_every_document_that_restates_the_count(self) -> None:
        """`P8-042`'s own reproduction recipe, run in this lab rather than the live tree.

        Live evidence at `e8c32ba`: adding a `GUARDS` entry moved the ast-derived ground truth
        (`OG-179`'s fix) to one more than before, but `python3 -m tools.corpus_check` still
        reported `registered corpus guards` with zero matches — the real sentences that now
        disagreed with reality were invisible to the claim pattern, so nothing went red. This
        plants the identical extra-entry mutation and requires every stale sentence to be named.

        **Both of this probe's conditions are now created or derived, not borrowed** (`L-37`).
        The baseline count is measured rather than written down — the literal `11` here went red
        the moment Phase 4 registered an eleventh guard, which is the corpus improving, not a
        defect. And the stale sentence is PLANTED: the live documents that used to carry one were
        corrected under Rule 2, so a probe that waits for the corpus to keep a stale claim around
        is a probe that retires itself the day the rule it enforces is obeyed.
        """
        from tools.corpus_check.guards.counts import _corpus_guards
        from tools.corpus_check.text import is_append_only_record

        rel = "tools/corpus_check/guards/__init__.py"
        original = (self.lab / rel).read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plant(rel, original))
        marker = "(register.GUARD, register.run),"
        self.assertIn(marker, original, "the registry's own shape changed under this test")

        baseline = _corpus_guards(self.corpus())
        assert baseline is not None
        self.assertGreater(baseline, 0, "no guards are registered, so this probe measured nothing")

        # A document stating the count that is true RIGHT NOW — and about to stop being true.
        self.plant(self._REL, f"# probe\n\nStats: **{baseline} guards** across the checker.\n")
        self.plant(rel, original.replace(marker, marker + "\n    " + marker, 1))

        corpus = self.corpus()
        self.assertEqual(
            _corpus_guards(corpus), baseline + 1, "the ast-derived ground truth did not move"
        )

        result = counts.run(corpus)
        blob = " ".join(f"{f.path}:{f.line} {f.message}" for f in result.findings)

        # The planted sentence must be caught...
        self.assertIn(
            self._REL, blob,
            "a document stating the pre-mutation guard count went unnoticed after another guard "
            "landed; the claim pattern can no longer read the sentence it exists for",
        )
        # ...and so must any live document that still restates the count. Derived, never listed:
        # matching the phrasing documents use, not the claim family's internal NAME, and skipping
        # append-only records, which quote a past count as history rather than asserting one.
        stale = sorted(
            other for other in corpus.markdown
            if other != self._REL
            and not is_append_only_record(corpus.text(other))
            and re.search(rf"\b(?:{baseline}|ten)\s+guards?\b", corpus.text(other), re.IGNORECASE)
        )
        for stale_doc in stale:
            self.assertIn(stale_doc, blob, f"{stale_doc}'s stale guard-count claim went unnoticed")


class ThePhaseGateSentenceIsDerived(_LabCase):
    """`GAP-BUILD_PLAN` — the one sentence a next-phase session reads before deciding it may start.

    At `cdab0ad`, `docs/plan/BUILD_PLAN.md` asserted *"carries zero rows marked `BLOCKS_PHASE_*`"*
    while `docs/process/OPEN_GATES.md` carried `OG-181` with disposition `BLOCKS_PHASE_4`. The
    document told the reader *"do not trust this sentence; re-derive it from `OPEN_GATES.md`"* —
    and no code did. `register` validated that `BLOCKS_PHASE_N` was a legal SPELLING; nothing
    counted the ROWS.

    These probe the artifact the gate certifies — the live `BUILD_PLAN.md` and the live
    `OPEN_GATES.md`, copied into the lab — not a hand-written fixture (`DOC_WRITING_DOCTRINE.md`
    §5).
    """

    _REL = "docs/process/PROBE_PHASEGATE.md"
    _REGISTER = "docs/process/OPEN_GATES.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def _plant_extra_blocker(self) -> str:
        """Add a `BLOCKS_PHASE_N` row to the register's `## Open` table. Returns the original.

        ⚠ **SYNTHESISED, never copied from a live row.** The first version of this helper located an
        existing `BLOCKS_PHASE` row and duplicated it, which silently made every probe in this class
        depend on the register *currently having a blocker*. The day `OG-181` was closed — the day
        the gate did the thing it exists to do — three of these tests broke with
        "the register no longer carries a BLOCKS_PHASE row to copy". A counter-example that fails
        when the measured state legitimately changes is not testing the mechanism, it is pinning a
        snapshot; `0` is the state this project should spend most of its life in.
        """
        original = (self.lab / self._REGISTER).read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plant(self._REGISTER, original))
        lines = original.splitlines(keepends=True)
        # Anchor on the ## Open table's separator, which is structural and always present, rather
        # than on a data row, whose existence is exactly what varies.
        header = next(
            i for i, line in enumerate(lines)
            if line.startswith("| id | sev | disposition |")
        )
        lines.insert(
            header + 2,
            "| OG-999 | HIGH | BLOCKS_PHASE_5 | planted | planted | planted |\n",
        )
        self.plant(self._REGISTER, "".join(lines))
        return original

    def test_the_live_register_is_read_not_the_vocabulary_table_above_it(self) -> None:
        """The ground truth must be 1, and `1` is the answer only if the right table was found.

        `OPEN_GATES.md` opens with a table headed ``| disposition | meaning |`` that *defines* the
        vocabulary, three rows, one of them literally `BLOCKS_PHASE_N`. A `find_table` asking only
        for a ``disposition`` column binds to THAT table and returns 0 — a confident, silent
        "the gate is clear", which is the worst answer this derivation could give.
        """
        from tools.corpus_check.guards.counts import _open_blocking_rows

        register = (self.lab / self._REGISTER).read_text(encoding="utf-8")
        open_table = register.partition("\n## Open")[2].partition("\n## Closed")[0]
        independent = len(re.findall(r"^\|[^|]+\|[^|]+\|\s*BLOCKS_PHASE_\d+\s*\|",
                                     open_table, re.MULTILINE))

        derived = _open_blocking_rows(self.corpus())
        self.assertIsNotNone(
            derived, "the derivation found no table at all — `None` means it matched nothing")
        self.assertEqual(
            derived, independent,
            f"the derivation says {derived}, an independent scan of the ## Open table says "
            f"{independent}. A disagreement here usually means it bound to the VOCABULARY table "
            "at the top of the register — three rows, one of them literally the disposition name — "
            "which yields a confident, silent answer about the wrong table.",
        )
        # And prove the vocabulary table really is a live hazard rather than a hypothetical: it is
        # present, and it does contain the token, so only the column requirement separates them.
        self.assertIn("BLOCKS_PHASE_N", register.partition("\n## Open")[0],
                      "the vocabulary table no longer defines the token — this probe's premise moved")

    def test_a_closed_blocker_is_not_counted_as_open(self) -> None:
        """`## Closed` is full of rows that WERE blockers. Counting them reports a permanent block."""
        from tools.corpus_check.guards.counts import _open_blocking_rows

        original = (self.lab / self._REGISTER).read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plant(self._REGISTER, original))
        before = _open_blocking_rows(self.corpus())
        marker = "\n## Closed\n"
        self.assertIn(marker, original, "the register's own shape changed under this test")
        self.plant(
            self._REGISTER,
            original.replace(
                marker,
                marker + "\n| OG-998 | 2026-01-01 | BLOCKS_PHASE_6 | closed long ago |\n",
                1,
            ),
        )
        self.assertEqual(
            _open_blocking_rows(self.corpus()), before,
            "a row under ## Closed moved the OPEN blocker count",
        )

    def test_a_new_blocker_turns_the_live_BUILD_PLAN_sentence_red(self) -> None:
        """**The retained counter-example for the gate itself.**

        A second `BLOCKS_PHASE_N` row lands in the register — exactly what happens the day someone
        records a new blocker — and `BUILD_PLAN.md`'s own live sentence must be named. Nothing is
        planted in `BUILD_PLAN.md`: the sentence under test is the real one.

        **This test, not the guard, is what pins the sentence in place.** `counts` can only compare
        numbers that are *stated*; it is green over a document that states nothing, which is Rule 2
        being obeyed and is exactly right for every other family. For this one claim that is a hole,
        because the phase gate is *supposed* to be asserted somewhere a reader will find it. Both
        ways of quietly reopening it were measured against this probe and both turn it red: deleting
        the sentence (guard stays green, this fails) and hiding the number inside backticks, which
        `run()` blanks before matching (guard stays green, this fails).
        """
        from tools.corpus_check.guards.counts import _open_blocking_rows

        before = _open_blocking_rows(self.corpus())
        self._plant_extra_blocker()
        corpus = self.corpus()
        # RELATIVE, not absolute. Asserting the literal `2` encoded "the register currently has
        # exactly one blocker" into a probe about the MECHANISM, and it broke the day the last
        # blocker was legitimately closed — which is the state this project should normally be in.
        self.assertEqual(_open_blocking_rows(corpus), (before or 0) + 1,
                         "planting a BLOCKS_PHASE row did not move the derived count")

        result = counts.run(corpus)
        blob = " ".join(f"{f.path}:{f.line} {f.message}" for f in result.findings)
        self.assertIn(
            "docs/plan/BUILD_PLAN.md", blob,
            "a second phase blocker landed and BUILD_PLAN.md's phase-gate sentence stayed green — "
            "either the sentence no longer states the count in prose the pattern can read, or the "
            "claim family was removed",
        )
        self.assertIn("open blocking rows", blob)

    def test_the_cdab0ad_wording_is_caught_even_with_the_label_in_backticks(self) -> None:
        """The exact false sentence from `cdab0ad`, which was unreadable twice over.

        `run()` blanks inline code before matching, so `` `BLOCKS_PHASE_*` `` is a run of spaces by
        the time a pattern sees it — a family anchored on the LABEL could never have read this
        sentence. It is matched on `rows marked` instead, and this probe keeps the two spellings
        honest: reverting `BUILD_PLAN.md` to the old wording must NOT switch the guard off.
        """
        # Plant a blocker FIRST, so the ground truth is non-zero and the "zero" wording is
        # genuinely false. Without this the probe silently stopped testing anything the moment the
        # register reached zero blockers: the old sentence became *true*, no finding fired, and the
        # assertion failed for the one reason that is not a defect. A probe must create the
        # condition it claims to detect rather than borrow it from the live state.
        self._plant_extra_blocker()
        self.plant(
            self._REL,
            "# probe\n\nThe register carries zero rows marked `BLOCKS_PHASE_*` today.\n",
        )
        self.assert_finds(counts.run(self.corpus()), "states 0 open blocking rows")

    def test_the_zero_state_is_spellable_in_words_and_still_checked(self) -> None:
        """The day the gate clears, the sentence reads "no open blocking rows" — in words.

        A family that only parses digits goes blind at precisely the moment its answer starts
        authorising work, which is the failure mode of a check that exists only for the bad state.
        """
        from tools.corpus_check.guards.counts import CLAIMS, _stated

        claim = next(c for c in CLAIMS if c.name == "open blocking rows")
        for text, expected in (
            ("The register carries no open blocking rows.", 0),
            ("The register carries zero open blocking rows.", 0),
            ("The register carries one open blocking row.", 1),
            ("The register carries **1 open blocking row**.", 1),
        ):
            with self.subTest(text=text):
                match = claim.pattern.search(text)
                self.assertIsNotNone(match, f"pattern cannot read {text!r}")
                assert match is not None
                self.assertEqual(_stated(match), expected)


class GateCountsAreDerived(_LabCase):
    """`F10` — the gate count is the number this project has watched go stale twice (`OG-27`).

    Two different universes, and conflating them is how `OG-27` was wrong twice: `gate_*`
    FUNCTIONS in `export_sanitizer.py`, and LABELS in `PRECEDENCE`. They are not the same number
    and never have been.
    """

    _REL = "docs/process/PROBE_GATECOUNT.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_the_function_count_matches_the_set_CONS_04_computes(self) -> None:
        """Derived by the identical expression the health check uses, so the two cannot disagree.

        If this ever fails, one of the two widened its definition of "a gate function" without the
        other — which would leave the guard certifying a number `CONS-04` does not recognise.
        """
        import ast as _ast

        from tools.corpus_check.guards.counts import _gate_functions

        source = (self.lab / "tools/docgen/export_sanitizer.py").read_text(encoding="utf-8")
        cons_04_set = {
            n.name
            for n in _ast.walk(_ast.parse(source))
            if isinstance(n, _ast.FunctionDef) and n.name.startswith("gate_")
        }
        self.assertEqual(_gate_functions(self.corpus()), len(cons_04_set))
        self.assertGreater(len(cons_04_set), 0, "the sanitizer defines no gate functions at all")

    def test_the_two_gate_universes_are_kept_apart(self) -> None:
        """`PRECEDENCE` carries labels that are not `gate_*` functions — `hash_gate`, `build`, `pdf`.

        A single "how many gates" family would have to call one of two true sentences a lie.
        """
        from tools.corpus_check.guards.counts import _gate_functions, _precedence_labels

        functions = _gate_functions(self.corpus())
        labels = _precedence_labels(self.corpus())
        self.assertIsNotNone(functions)
        self.assertIsNotNone(labels)
        assert functions is not None and labels is not None
        self.assertNotEqual(
            functions, labels,
            "the two gate universes coincided; if that is now genuinely true, the separate "
            "families still stand — but the reason for them recorded in counts.py has changed",
        )

    def test_a_deleted_gate_function_turns_a_stated_count_red(self) -> None:
        """Delete a gate from the sanitizer; every document stating the old number must go red.

        The mutation is real — the `def` line is renamed out of the `gate_` namespace — so the
        ground truth moves the way it would on the day someone removes a gate.
        """
        from tools.corpus_check.guards.counts import _gate_functions

        rel = "tools/docgen/export_sanitizer.py"
        original = (self.lab / rel).read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plant(rel, original))
        before = _gate_functions(self.corpus())
        assert before is not None
        marker = "def gate_wcag_contrast("
        self.assertIn(marker, original, "the sanitizer's own shape changed under this test")
        self.plant(rel, original.replace(marker, "def retired_wcag_contrast(", 1))

        corpus = self.corpus()
        self.assertEqual(_gate_functions(corpus), before - 1, "the ground truth did not move")

        self.plant(self._REL, f"# probe\n\nThe sanitizer defines {before} gate functions.\n")
        self.assert_finds(counts.run(self.corpus()), f"states {before} gate functions")


class CrossDocIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_CROSSDOC.md"
    _PLAN = "docs/plan/PROBE_PLAN.md"

    # A probe-owned plan, so the deferral tests below depend on NOTHING about which phases the real
    # plan has finished. Both of them used to, and both broke the day Phase 4 was correctly marked
    # complete (`OG-210`): the refusal probe started failing for the wrong reason — the guard's
    # COMPLETE branch fires before the does-not-name-it branch — and the acceptance probe, which
    # borrowed the live row `OG-07`, began passing **vacuously** the moment that row was closed,
    # because `assertNotIn` is satisfied by absence. That is `L-37` exactly: a probe that borrows
    # its condition from the corpus breaks when the corpus improves, and the quieter half of the
    # break is the one that keeps reporting green.
    _PLAN_BODY = (
        "# probe plan\n\n"
        "| # | phase | deliverables | exit condition |\n"
        "|---|---|---|---|\n"
        "| 8 | declares OTHER work | something unrelated to any probe row | per its own set |\n"
        "| 9 | accepts `PB-72` | the work `PB-72` names | per its own set |\n"
        "| 10 | a phase that has ended | DONE `deadbee` | shipped |\n"
    )
    # Rows 8 and 9 must carry NO word from the completion vocabulary, which is wider than it looks:
    # the first draft ended both with *when it is done*, and `\bDONE\b` is in it, case-insensitively.
    # Every row read as COMPLETE and the two probes failed for a reason that had nothing to do with
    # what they test. A fixture is subject to the guard's own vocabulary, and seven spellings is
    # enough that "surely this reads as unfinished" is not a safe assumption (`OG-99`).

    def _rows(self, *rows: str) -> None:
        """Plant the probe plan and a register table carrying ``rows``."""
        self.plant(self._PLAN, self._PLAN_BODY)
        self.plant(
            self._REL,
            "# probe\n\n| id | sev | disposition | title | evidence | closing it means |\n"
            "|---|---|---|---|---|---|\n" + "".join(rows),
        )

    def test_a_deferral_the_named_phase_does_not_ACCEPT_is_refused(self) -> None:
        """`OG-171` — `OPEN_GATES` rule 6, made mechanical.

        The rule is *"A SCHEDULED row must name the phase AND that phase must name the work."* The
        guard proved only the first half: that the cited phase exists and is not complete. Measured
        at `ba0294a`, all four live deferrals passed while `BUILD_PLAN.md`'s phase rows named
        **zero** of them — and one deferred figure-provenance work to a phase whose row is about
        document identity and archiving.

        *Does this phase declare that work?* is a semantic question no grep answers. **The phase row
        must name the key** is the exact mechanical form of it, and it makes a deferral a two-sided
        agreement that neither side can move alone.
        """
        self._rows("| PB-71 | LOW | SCHEDULED (Phase 8) | a deferral phase 8 never accepted | see "
                   "`docs/plan/PROBE_PLAN.md` | nothing |\n")
        self.assert_finds(cross_doc.run(self.corpus()), "does not name it")

    def test_a_deferral_the_phase_DOES_accept_is_allowed(self) -> None:
        """Two-sided **in one run**: without this, refusing every deferral would satisfy the probe
        above — and an acceptance probe on its own passes for free the moment its subject stops
        existing, which is how the previous version of this test died quietly.

        So both rows are planted together. The refused one proves the guard is live in this very
        run; the accepted one proves it is not simply refusing everything.
        """
        self._rows(
            "| PB-71 | LOW | SCHEDULED (Phase 8) | a deferral phase 8 never accepted | see "
            "`docs/plan/PROBE_PLAN.md` | nothing |\n",
            "| PB-72 | LOW | SCHEDULED (Phase 9) | a deferral phase 9 DOES accept | see "
            "`docs/plan/PROBE_PLAN.md` | nothing |\n",
        )
        messages = " ".join(f.message for f in cross_doc.run(self.corpus()).findings)
        self.assertIn("'PB-71' defers", messages,
                      "the guard found nothing at all, so the acceptance below proves nothing")
        self.assertNotIn("'PB-72' defers", messages,
                         "a deferral the plan explicitly accepts was refused")

    def test_a_deferral_to_a_phase_the_plan_marks_COMPLETE_is_refused(self) -> None:
        """The branch that had been dead since Phase 4 (`OG-210`), pinned on an owned fixture.

        `tools/tests/test_phase_completion.py` drives the same branch against the real plan, which
        is what proves the marker is load-bearing. This one proves the branch itself works on a plan
        this probe controls, so the two cannot fail for the same reason.
        """
        self._rows("| PB-73 | LOW | SCHEDULED (Phase 10) | a deferral to finished work | see "
                   "`docs/plan/PROBE_PLAN.md` | nothing |\n")
        self.assert_finds(cross_doc.run(self.corpus()), "which the plan marks COMPLETE")

    def tearDown(self) -> None:
        for rel in (self._REL, self._PLAN):
            if (self.lab / rel).exists():
                self.remove(rel)

    def test_citation_to_a_nonexistent_register_key_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\nSee `OG-998` for the decision.\n")
        self.assert_finds(cross_doc.run(self.corpus()), "OG-998")

    def test_a_deferral_that_names_no_plan_is_refused(self) -> None:
        """The phase gate's own integrity: the only legal deferral is one a plan declares."""
        self.plant(
            self._REL,
            "# probe\n\n| id | disposition | note |\n|---|---|---|\n"
            "| PB-07 | SCHEDULED (Phase 5) | parked with no plan behind it |\n",
        )
        self.assert_finds(cross_doc.run(self.corpus()), "cites no plan document")

    def test_a_deferral_to_a_COMPLETED_phase_is_refused(self) -> None:
        """A deferral to finished work is parked forever — the phase that would close it has ended.

        `OG-88`. The first version of this check searched the cited document for the literal
        "Phase N" anywhere, so it could not tell a live phase from a finished one, could not tell a
        real table row from a passing mention, and stayed green when a verifier re-pointed a row at
        an unrelated phase. `BUILD_PLAN.md` marks completed phases with a tick and a sha.
        """
        self.plant(
            self._REL,
            "# probe\n\n| id | disposition | note |\n|---|---|---|\n"
            "| PB-09 | SCHEDULED (Phase 1) | see `BUILD_PLAN.md` |\n",
        )
        self.assert_finds(cross_doc.run(self.corpus()), "which the plan marks COMPLETE")

    def test_a_deferral_to_a_phase_the_plan_lacks_is_refused(self) -> None:
        self.plant(
            self._REL,
            "# probe\n\n| id | disposition | note |\n|---|---|---|\n"
            "| PB-08 | SCHEDULED (Phase 91) | see `BUILD_PLAN.md` |\n",
        )
        self.assert_finds(cross_doc.run(self.corpus()), "Phase 91")

    def test_a_closed_row_with_no_disposition_column_still_catches_an_unbuilt_deferral(self) -> None:
        """`P8-028` — a `SCHEDULED` deferral hiding in a table check 2 was never built to see.

        `OPEN_GATES.md`'s own `## Closed` table (``| id | closed | title | how |``) carries no
        `disposition` column, so a row phrased exactly like a live deferral — names a phase, calls
        itself scheduled, and admits the work is not built — passed through check 2 unexamined.
        Reproduced live at `e8c32ba`: `python3 -m tools.corpus_check` was CLEAN while `OG-136` sat
        in that table reading '...scheduled, not a defect...belongs to Phase 7...Deliberately not
        built now.'
        """
        self.plant(
            self._REL,
            "# probe\n\n| id | closed | title | how |\n|---|---|---|---|\n"
            "| PB-50 | 2026-08-01 | a runner gate closed on paper | belongs to **Phase 9**. "
            "**scheduled**, not a defect. Deliberately not built now. |\n",
        )
        self.assert_finds(cross_doc.run(self.corpus()), "no `disposition` column")

    def test_two_of_three_markers_in_a_disposition_less_table_is_not_enough(self) -> None:
        """The new check's own edge: phase + scheduled alone must NOT fire.

        This corpus's `## Closed` table mentions "Phase N" in 9 rows and "scheduled" in 5 while
        narrating what a rule now does, not deferring anything — a check that fired on either
        marker alone would flood the real corpus. All three markers, in the SAME row, are required,
        so a row that is merely built-and-shipped while mentioning a phase must be let through.
        """
        self.plant(
            self._REL,
            "# probe\n\n| id | closed | title | how |\n|---|---|---|---|\n"
            "| PB-51 | 2026-08-01 | a rule that discusses scheduling | belongs to **Phase 9**, "
            "**scheduled** ahead of the release, fully built and shipped |\n",
        )
        result = cross_doc.run(self.corpus())
        self.assertNotIn(
            "PB-51", " ".join(f.message for f in result.findings),
            "two of three markers alone should not read as an unbuilt deferral",
        )

    def test_a_declared_record_under_its_dated_heading_is_still_exempt(self) -> None:
        """The same record exemption check 1 already relies on.

        `VERIFICATION_LOG.md` quotes this very defect's `OG-136` evidence verbatim, under a dated
        `## Pass 8` heading, and must not be reported for accurately recording what a verifier
        found — the failure mode `OG-137` and `OG-159` were closed for.
        """
        self.plant(
            self._REL,
            "<!-- record: append-only -->\n# probe record\n\n"
            "## 2026-01-01 — quoted evidence\n\n"
            "| id | closed | title | how |\n|---|---|---|---|\n"
            "| PB-52 | 2026-08-01 | a quoted OG row | belongs to **Phase 9**. **scheduled**, not "
            "a defect. Deliberately not built now. |\n",
        )
        result = cross_doc.run(self.corpus())
        self.assertNotIn(
            "PB-52", " ".join(f.message for f in result.findings),
            "a row quoted under its own document's dated record heading was reported",
        )

    def test_a_declared_record_OUTSIDE_its_dated_heading_still_fires(self) -> None:
        """The exemption is per-line, not per-document (`OG-140`).

        Declaring a file a record does not blanket-exempt every row in it — only the ones sitting
        under a DATED heading do. A live deferral parked in an undated section of a record-declared
        file must still be caught.
        """
        self.plant(
            self._REL,
            "<!-- record: append-only -->\n# probe record\n\n"
            "## live section, no date\n\n"
            "| id | closed | title | how |\n|---|---|---|---|\n"
            "| PB-53 | 2026-08-01 | a live row masquerading as history | belongs to **Phase 9**. "
            "**scheduled**, not a defect. Deliberately not built now. |\n",
        )
        self.assert_finds(cross_doc.run(self.corpus()), "PB-53")


class PresentTenseIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_TENSE.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_unbuilt_path_in_the_present_tense_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\n`tools/not_built_yet/` is the checker for this phase.\n")
        self.assert_finds(present_tense.run(self.corpus()), "tools/not_built_yet/")

    def test_over_broad_exemption_does_not_disarm_present_tense(self) -> None:
        """**Regression probe.** A bare ``" deliberately"`` exemption once matched *"deliberately
        falsified"* and switched this guard off on `BUILD_PLAN.md`'s Phase 3 row — the single row
        it existed to catch. The word must not, by itself, excuse a paragraph.
        """
        self.plant(
            self._REL,
            "# probe\n\n`tools/not_built_yet/` is the checker, with every guard deliberately "
            "falsified first and shown red.\n",
        )
        self.assert_finds(present_tense.run(self.corpus()), "tools/not_built_yet/")

    def test_no_exemption_marker_excuses_a_claim_in_ANOTHER_sentence(self) -> None:
        """**Derived from the live lists, so it cannot go stale — and that is the point.**

        The probe that stood here looped over `if`, `when`, `after`, `until`, `may`, `should`,
        `could` and asserted each still got caught. Every one of those words had already been
        REMOVED from `_FUTURE_MARKERS` when the test was written, so it exercised nothing: it
        proved the guard ignores words the guard does not know. A counter-example that loops over
        what a fix DELETED passes for free, forever, and reports the hole as closed — which is the
        failure `docs/process/RULES.md` Rule 1 names, one level up: the assertion must cover the
        CLASS, and the class here is *"a marker excuses a claim it does not belong to"*.

        So this iterates `_FUTURE_MARKERS + _ABSENCE_MARKERS` **as they are at run time**. Add a
        marker and it is probed automatically; remove one and nothing silently keeps passing.

        Each case puts the marker in its own complete sentence and the false claim in a separate
        one. The marker is legitimate where it stands — some other thing really is planned or
        absent — and it must not reach across the full stop.
        """
        markers = present_tense._FUTURE_MARKERS + present_tense._ABSENCE_MARKERS
        self.assertGreater(len(markers), 10, "marker lists emptied; this probe would be vacuous")
        for marker in markers:
            with self.subTest(marker=marker):
                self.plant(
                    self._REL,
                    f"# probe\n\nThe migration step is{marker}scheduled for a later phase. "
                    "`tools/not_built_yet/` is the checker that runs today.\n",
                )
                self.assert_finds(present_tense.run(self.corpus()), "tools/not_built_yet/")

    def test_a_marker_still_excuses_a_claim_in_its_OWN_sentence(self) -> None:
        """The other direction — narrowing must not become a guard that flags correct prose.

        Without this, the test above is satisfied by deleting the exemption lists entirely, and
        the guard would report `ABSENT_PATHS.md`-style declarations for doing their job. Both
        assertions together pin the scope to exactly one sentence.
        """
        self.plant(
            self._REL,
            "# probe\n\n`docs/design/NO_SUCH_LAW.md` is deliberately absent from this package.\n",
        )
        result = present_tense.run(self.corpus())
        self.assertNotIn("PROBE_TENSE", " ".join(f.path for f in result.findings))

    def test_a_present_tense_instruction_word_is_not_a_past_tense_marker(self) -> None:
        """`_PAST_MARKERS` is the THIRD list of this shape found too broad, and the widest.

        Every entry switches `counts`, `symbols` AND `present-tense` off, so a word that is not
        actually about the past is a hole in three guards at once. `" until "` and `" before "`
        were removed for that reason: *"until you run it"* and *"before you push"* are
        present-tense instructions, and this corpus is full of them.

        The probe asserts the property, not the two words — each is used in an ordinary
        present-tense instruction next to a false claim, and the claim must still be caught.
        """
        for word in ("until", "before", "after", "when", "if", "while", "unless"):
            with self.subTest(word=word):
                self.plant(
                    self._REL,
                    f"# probe\n\n`tools/not_built_yet/` is the checker; run it {word} you push.\n",
                )
                self.assert_finds(present_tense.run(self.corpus()), "tools/not_built_yet/")

    def test_a_genuine_past_tense_marker_still_exempts_its_own_sentence(self) -> None:
        """Two-sided: emptying `_PAST_MARKERS` would satisfy the probe above.

        Derived from the live list, so the pair pins the boundary rather than two chosen words.
        """
        from tools.corpus_check.text import _PAST_MARKERS

        self.assertTrue(_PAST_MARKERS, "the past-marker list is empty; the probe is vacuous")
        for marker in _PAST_MARKERS:
            with self.subTest(marker=marker):
                self.plant(
                    self._REL,
                    f"# probe\n\n`tools/not_built_yet/`{marker}the checker for that phase.\n",
                )
                result = present_tense.run(self.corpus())
                self.assertNotIn(
                    "PROBE_TENSE", " ".join(f.path for f in result.findings),
                    f"{marker!r} no longer exempts a genuine record of what WAS",
                )

    def test_a_genuine_future_tense_marker_still_exempts_its_own_sentence(self) -> None:
        """`P8-097` + `P8-103` — the same two-sided pair `_PAST_MARKERS` has, for `_FUTURE_MARKERS`.

        `P8-097`: nothing iterated `_FUTURE_MARKERS` itself the way the test above iterates
        `_PAST_MARKERS` — a per-entry proof that each one still exempts a genuine forward-looking
        claim in its OWN sentence, derived at run time so a future edit to the list is covered
        automatically rather than by a test someone remembers to update.

        `P8-103`: measured on the LIVE corpus, every entry in `_FUTURE_MARKERS` currently
        suppresses zero organic findings — no tracked document's own prose happens to use any of
        these eleven phrasings next to an unbuilt-path claim today. Deleting the list outright was
        rejected: it would leave nothing for this very test to iterate, and the list's structural
        reasoning (`present_tense.py`'s own module comment — "constructions that cannot describe a
        thing as present") is sound even where today's prose does not happen to exercise it. This
        test is the "make it mechanical" alternative the finding itself offers: each entry is
        proven, by a retained counter-example, to actually suppress a real unbuilt-path claim when
        planted — converting an untested list that could silently rot into one where every entry
        is known to work, so a marker that stops mattering is a visible, deliberate deletion rather
        than a silent hole.
        """
        self.assertTrue(
            present_tense._FUTURE_MARKERS, "the future-marker list is empty; the probe is vacuous"
        )
        for marker in present_tense._FUTURE_MARKERS:
            with self.subTest(marker=marker):
                self.plant(
                    self._REL,
                    f"# probe\n\n`tools/not_built_yet/`{marker}the checker for a later phase.\n",
                )
                result = present_tense.run(self.corpus())
                self.assertNotIn(
                    "PROBE_TENSE", " ".join(f.path for f in result.findings),
                    f"{marker!r} no longer exempts a genuine unbuilt-path claim in its own sentence",
                )

    def test_a_gitignored_path_that_does_not_EXIST_is_still_unbuilt(self) -> None:
        """`OG-115` — "untracked is not unbuilt" is true only when the thing is actually there.

        The exemption asked `git check-ignore`, which answers *"would this be untracked?"* — a
        question about a rule, not about reality. So a claim naming a file nobody has written,
        inside a gitignored tree, passed: *"`docs/confidential/POLICY.md` is the live security
        policy every reviewer follows."*
        """
        self.plant(
            self._REL,
            "# probe\n\n`docs/confidential/POLICY.md` is the live security policy every "
            "reviewer follows.\n",
        )
        self.assert_finds(present_tense.run(self.corpus()), "docs/confidential/POLICY.md")

    def test_the_runtime_vault_itself_is_still_describable(self) -> None:
        """Two-sided control. `docs/confidential/` is created on demand by
        `engine_config.confidential_dir()`, so it is legitimately absent from a clean checkout
        while `CLASSIFICATION.md` describes it in the present tense — correctly. Without this,
        the probe above is satisfied by a guard that flags the vault too, which it did for one
        iteration and produced three findings on true sentences.
        """
        self.plant(self._REL, "# probe\n\n`docs/confidential/` is the vault, and it is gitignored.\n")
        result = present_tense.run(self.corpus())
        self.assertNotIn("PROBE_TENSE", " ".join(f.path for f in result.findings))

    def test_the_absence_registry_is_exempt_ROW_BY_ROW_not_wholesale(self) -> None:
        """`OG-115` — "this document may declare absence" never meant "nothing here is a claim".

        The whole FILE was skipped, so a false present-tense claim planted in `ABSENT_PATHS.md`'s
        prose passed. The exemption is now per table row, which is the granularity the registry
        actually needs.
        """
        registry = "docs/process/ABSENT_PATHS.md"
        original = (self.lab / registry).read_text(encoding="utf-8")
        self.addCleanup(
            lambda: (self.lab / registry).write_text(original, encoding="utf-8")
        )
        self.plant(
            registry,
            original + "\n`tools/not_built_yet/` is the checker this project ships today.\n",
        )
        self.assert_finds(present_tense.run(self.corpus()), "tools/not_built_yet/")

    def test_punctuation_cannot_hide_an_absence_marker(self) -> None:
        """A marker wrapped in emphasis, backticks or PARENTHESES is still the marker.

        Two instances of this were fixed one after the other — `**not bundled here**`, then
        `(not bundled here)` — before the normalisation was widened to all punctuation at once.
        """
        for wrap in ("**{}**", "({})", "`{}`", "— {} —"):
            with self.subTest(wrap=wrap):
                marker = wrap.format("not bundled here")
                self.plant(
                    self._REL,
                    f"# probe\n\nThose belong to the source project and are {marker} — "
                    "`docs/design/NO_SUCH_LAW.md` is one of them.\n",
                )
                result = present_tense.run(self.corpus())
                self.assertNotIn("PROBE_TENSE", " ".join(f.path for f in result.findings))

    def test_a_declared_absence_is_not_reported(self) -> None:
        """A paragraph whose purpose is to say a file is missing must not be flagged for it."""
        self.plant(
            self._REL,
            "# probe\n\nThose documents belong to the engine's source project and are **not\n"
            "bundled here** - `docs/design/NO_SUCH_LAW.md` is one of them.\n",
        )
        result = present_tense.run(self.corpus())
        self.assertNotIn("PROBE_TENSE", " ".join(f.path for f in result.findings))

    def test_a_gitignored_location_is_not_reported(self) -> None:
        """Untracked is not unbuilt: `docs/confidential/` is real and deliberately not tracked."""
        self.plant(self._REL, "# probe\n\n`docs/confidential/` is the vault non-public docs live in.\n")
        result = present_tense.run(self.corpus())
        self.assertNotIn("PROBE_TENSE", " ".join(f.path for f in result.findings))


class BuiltClaimsIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_COMMANDS.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def test_nonexistent_module_is_refused(self) -> None:
        """`OG-58`'s class: a documented command that fails on its first line."""
        self.plant(self._REL, "# probe\n\nRun `python3 -m tools.no_such_package build`.\n")
        self.assert_finds(built_claims.run(self.corpus()), "tools.no_such_package")

    def test_nonexistent_subcommand_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\nRun `python3 -m tools.docgen.cli frobnicate`.\n")
        self.assert_finds(built_claims.run(self.corpus()), "frobnicate")

    def test_nonexistent_flag_is_refused(self) -> None:
        """argparse exits 2 on an undefined flag, so a documented one is a broken instruction."""
        self.plant(self._REL, "# probe\n\nRun `python3 -m tools.health --no-such-flag`.\n")
        self.assert_finds(built_claims.run(self.corpus()), "--no-such-flag")

    def test_nonexistent_npm_script_is_refused(self) -> None:
        self.plant(self._REL, "# probe\n\nRun `npm run no-such-script` in the engine.\n")
        self.assert_finds(built_claims.run(self.corpus()), "no-such-script")

    def test_a_narrative_past_tense_word_does_not_exempt_a_command_line(self) -> None:
        """**Near-miss probe.** The launch command is ONE 5,600-character line whose prompt narrates
        project history — *"Phase 2 was reported complete…"*. When this guard was made
        record-aware it briefly used the broad `is_historical`, and that single `" was "` exempted
        the most-executed line in the repository from command checking. `CONS-08` learned the
        identical lesson: a whole-line exemption fired by one incidental word.
        """
        self.plant(
            self._REL,
            "# probe\n\n```bash\nclaude --effort max \"run `python3 -m tools.no_such_package build` "
            "because Phase 2 was reported complete and falsified four ways\"\n```\n",
        )
        self.assert_finds(built_claims.run(self.corpus()), "tools.no_such_package")

    def test_a_dead_command_in_TRACKED_BUILT_OUTPUT_is_refused(self) -> None:
        """`OG-91`: seven instructions for a deleted script survived in tracked rendered HTML.

        `built-claims` read Markdown only, so the source was clean and the artifact was not — the
        asymmetry `LESSONS.md` `L-21` names, and `DOC_WRITING_DOCTRINE.md` §8.4's "grep the outputs"
        applied to commands rather than to markup.
        """
        rel = "tools/docgen/demo/probe.html"
        self.plant(
            rel,
            "<html><body><pre><code>python3 -m tools.no_such_package build</code></pre></body></html>",
        )
        self.addCleanup(lambda: self.remove(rel) if (self.lab / rel).exists() else None)
        self.assert_finds(built_claims.run(self.corpus()), "tools.no_such_package")

    def test_an_incidental_date_does_not_exempt_a_command_line(self) -> None:
        """`OG-97`: the date exemption was whole-LINE, and that cost 34% of this guard's coverage.

        Pass 7 measured 304 claims with the old rule and 231 with the new one, then re-exempted the
        5,757-character launch line by injecting a single ISO date into it. A command is not made
        historical by mentioning a date — only by living under a dated record heading.
        """
        for token in ("2026-08-22", "03:05"):
            with self.subTest(token=token):
                self.plant(
                    self._REL,
                    f"# probe\n\nOn {token} we ran `python3 -m tools.no_such_package build`.\n",
                )
                self.assert_finds(built_claims.run(self.corpus()), "tools.no_such_package")

    def test_a_command_in_a_non_markdown_surface_is_refused(self) -> None:
        """`OG-97`: `OG-91` widened `.md` to `.md`+`.html`, and the hole moved one extension over.

        Pass 7 planted the identical broken command in `CAPABILITIES.json`, `install.sh` and
        `run.py` and watched all three escape — while `CAPABILITIES.json` carries live commands.
        """
        for name, body in (
            ("PROBE_CMD.json", '{"cmd": "python3 -m tools.no_such_package build"}\n'),
            ("PROBE_CMD.sh", "#!/bin/sh\npython3 -m tools.no_such_package build\n"),
            ("PROBE_CMD.txt", "run python3 -m tools.no_such_package build\n"),
        ):
            with self.subTest(surface=name):
                rel = f"docs/process/{name}"
                self.plant(rel, body)
                self.addCleanup(lambda r=rel: self.remove(r) if (self.lab / r).exists() else None)  # type: ignore[misc]
                self.assert_finds(built_claims.run(self.corpus()), "tools.no_such_package")

    def test_a_dated_record_quoting_a_dead_command_is_not_reported(self) -> None:
        """The other side: an append-only log quotes the commands a pass found broken."""
        self.plant(
            self._REL,
            "<!-- record: append-only -->\n# probe\n\n"
            "## Pass 9 — a verification pass, 2020-01-01, commit `abc1234`\n\n"
            "The pass found `python3 tools/docgen/no_such_script.py` still documented.\n",
        )
        result = built_claims.run(self.corpus())
        self.assertNotIn("PROBE_COMMANDS", " ".join(f.path for f in result.findings))

    def test_a_DATED_HEADING_ALONE_does_not_make_a_document_a_record(self) -> None:
        """`OG-140` — the other half of the boundary, and the reason this pair exists.

        Record-ness used to be INFERRED from a date in any enclosing heading. Measured on the live
        corpus that exempted **2458 of 8307 prose lines — 29.6%** from five guards and from
        health's `CONS-06`, which `tools/hooks/pre-push` runs. Three live normative policies were
        78-88% exempt for one reason: each carries a version strapline as an `###` heading, and
        every line beneath a subtitle is structurally beneath a dated heading.

        A subtitle is not a record. Without the declaration, the dated heading exempts nothing.
        """
        self.plant(
            self._REL,
            "# probe\n\n### a strapline · 2026-08-23 · v1.0.0\n\n"
            "Run `python3 tools/docgen/no_such_script.py` to rebuild.\n",
        )
        self.assert_finds(built_claims.run(self.corpus()), "no_such_script.py")

    def test_a_module_is_not_judged_by_its_siblings_parsers(self) -> None:
        """`tools.docgen.i18n` is a module; `cli.py`'s subcommands are not its contract."""
        self.plant(self._REL, "# probe\n\nRun `python3 -m tools.docgen.i18n en`.\n")
        result = built_claims.run(self.corpus())
        self.assertNotIn("PROBE_COMMANDS", " ".join(f.path for f in result.findings))

    def test_an_external_reference_exempts_ALL_FOUR_command_families_not_just_one(self) -> None:
        """`P8-052` — the `_EXTERNAL_REF_RE` `continue` sat AFTER the `python3 -m` loop and
        BEFORE the other three, so a line naming all four families plus one URL had its
        `python3 -m` finding fire while the identical bogus `python3 <script>.py` and `npm run
        …` claims on the SAME line, under the SAME external attribution, went unreported.

        Live evidence at `e8c32ba`: appending exactly this sentence to `RULES.md` produced ONE
        finding (`python3 -m tools.ghost.run`) while the script-path and npm-run claims on the
        identical line were silently suppressed by the URL.
        """
        line = (
            "python3 tools/ghost/run.py, npm run ghostbuild, and python3 -m tools.ghost.run "
            "(see https://example.com/docs) all name nothing real."
        )
        self.plant(self._REL, f"# probe\n\n{line}\n")
        result = built_claims.run(self.corpus())
        self.assertEqual(
            [f.message for f in result.findings], [],
            "a line attributed to an external URL was still judged against our own package.json "
            "for some but not all of its command families",
        )

    def test_the_same_line_WITHOUT_the_url_still_fires_on_all_three(self) -> None:
        """Two-sided control: without this, moving the `continue` earlier could satisfy the probe
        above by exempting everything unconditionally rather than by treating the four families
        uniformly.
        """
        line = (
            "python3 tools/ghost/run.py, npm run ghostbuild, and python3 -m tools.ghost.run "
            "all name nothing real."
        )
        self.plant(self._REL, f"# probe\n\n{line}\n")
        result = built_claims.run(self.corpus())
        blob = " ".join(f.message for f in result.findings)
        for needle in ("tools/ghost/run.py", "ghostbuild", "tools.ghost.run"):
            self.assertIn(needle, blob, f"{needle!r} was not reported once the URL is gone")

    def test_a_command_hiding_in_the_evidence_catalogue_is_still_refused(self) -> None:
        """`P8-077` — the whole `/knowledge/` and `/evidence/` DIRECTORIES were excluded from
        scanning, to protect `SOURCE_REGISTRY.json`'s bare `owner/repo:` third-party attributions
        from being judged against our own `package.json`. But `tools/visual-engine/evidence/
        release/acceptance-simulations.json` lives under the same directory and documents OUR OWN
        `npm run simulate` — a path-segment exclusion blinded 22 other tracked files to protect
        the one that actually needed it.

        Live reproduction at `e8c32ba`: rewriting that file's `"run"` field to a nonexistent
        script name still passed clean.
        """
        rel = "tools/visual-engine/evidence/release/acceptance-simulations.json"
        original = self.lab.joinpath(rel).read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plant(rel, original))
        import json as _json

        data = _json.loads(original)
        data["run"] = "npm run simulate-probe-does-not-exist"
        self.plant(rel, _json.dumps(data, indent=2))

        result = built_claims.run(self.corpus())
        self.assertTrue(
            any("simulate-probe-does-not-exist" in f.message for f in result.findings),
            f"a broken command in the evidence catalogue was not reported: {result.findings}",
        )

    def test_the_genuine_third_party_attribution_is_still_exempt(self) -> None:
        """Two-sided control: `SOURCE_REGISTRY.json`'s own bare `apache/echarts-mcp: … npm run
        dev runner` line must stay exempt — the fix narrows the exclusion to the one file that
        needs it, it does not delete the exemption itself.
        """
        result = built_claims.run(self.corpus())
        self.assertNotIn(
            "SOURCE_REGISTRY", " ".join(f.path for f in result.findings),
            "the genuine third-party attribution was judged against our own package.json",
        )

    def test_an_argparse_builtin_flag_is_not_read_as_undocumented(self) -> None:
        """`P8-127` — `_ARGPARSE_BUILTINS` (`--help`) had zero coverage: nothing proved argparse's
        own automatic flag was actually load-bearing rather than a dead entry.
        """
        self.plant(self._REL, "# probe\n\nRun `python3 -m tools.health --help`.\n")
        result = built_claims.run(self.corpus())
        self.assertNotIn(
            "PROBE_COMMANDS", " ".join(f.path for f in result.findings),
            "--help was reported as an undefined flag",
        )

    def test_WITHOUT_the_exemption_help_would_be_refused(self) -> None:
        """Two-sided: without this, deleting `_ARGPARSE_BUILTINS` entirely would satisfy the probe
        above by accident — `--help` would then be a genuine (wrong) finding, not a non-finding.
        """
        original = built_claims._ARGPARSE_BUILTINS
        built_claims._ARGPARSE_BUILTINS = frozenset()
        self.addCleanup(lambda: setattr(built_claims, "_ARGPARSE_BUILTINS", original))
        self.plant(self._REL, "# probe\n\nRun `python3 -m tools.health --help`.\n")
        self.assert_finds(built_claims.run(self.corpus()), "--help")


class StampsIsFalsified(_LabCase):
    _REL = "docs/process/PROBE_STAMP.md"

    def tearDown(self) -> None:
        if (self.lab / self._REL).exists():
            self.remove(self._REL)

    def _plant_drifted_stamp(self, body_extra: str) -> None:
        self.plant(self._REL, "# probe\n\nplaceholder\n")
        sha = _commit_all(self.lab, "probe stamp base")
        (self.lab / self._REL).write_text(
            f"<!-- artifact-hardened: APPROVED @ {sha} on 2026-08-22 via three-pass-v1 -->\n"
            f"# probe\n\nplaceholder\n{body_extra}\n",
            encoding="utf-8",
        )

    def test_a_stamp_on_an_edited_body_is_refused(self) -> None:
        """Doctrine §8.2, the rule this guard exists for."""
        self._plant_drifted_stamp("a paragraph added after the stamp was applied")
        self.assert_finds(stamps.run(self.corpus()), "no longer covers this file's body")

    def test_a_document_a_handover_merely_NAMES_is_not_excused(self) -> None:
        """**The probe three independent verifiers used to break this guard.**

        `HANDOFF.md` carries `NEEDS RE-HARDENING` on one line *about `PROVENANCE.md`* and quotes the
        rule verbatim on another, while its document index names sixteen other documents elsewhere
        in the file. The first version of the amnesty accepted the marker and the filename appearing
        anywhere in the same file, so **14 of 57 documents were auto-excused** and a genuinely
        drifted stamp on `docs/process/SESSION_STATE.md` was reported compliant.

        The previous probe below could never see it: it plants its drift on `PROBE_STAMP.md`, a name
        no handover contains. This one plants it on a document `HANDOFF.md` DOES name — which is the
        sibling that was standing.
        """
        rel = "docs/process/THREAT_MODEL.md"
        original = (self.lab / rel).read_text(encoding="utf-8")
        self.addCleanup(lambda: (self.lab / rel).write_text(original, encoding="utf-8"))
        sha = _commit_all(self.lab, "base for the named-document probe")
        self.assertIn(rel.rsplit("/", 1)[-1], (self.lab / "HANDOFF.md").read_text(encoding="utf-8"),
                      "the probe is only meaningful if the handover really names this document")
        (self.lab / rel).write_text(
            f"<!-- artifact-hardened: APPROVED @ {sha} on 2026-08-22 via three-pass-v1 -->\n"
            + original + "\n\nan edit made after the stamp\n",
            encoding="utf-8",
        )
        self.assert_finds(stamps.run(self.corpus()), "no longer covers this file's body")

    def test_a_session_state_stamp_is_not_judged_on_body_drift(self) -> None:
        """The other half: two stamp CONTRACTS, and applying one to the other asks the wrong question.

        `docs/process/SESSION_STATE.md` declares its own stamp *"deliberately weaker than the
        hardening stamp in `PROVENANCE.md`, which invalidates on any edit to its own body"* — the
        record is written after the work it describes and normally lands a commit later, so drifting
        from its own stamp is its designed behaviour. `STRUCT-06` owns its mechanical half.
        """
        rel = "docs/process/PROBE_SESSION.md"
        self.plant(rel, "# probe\n\nplaceholder\n")
        sha = _commit_all(self.lab, "base for the session-state contract probe")
        self.addCleanup(lambda: self.remove(rel) if (self.lab / rel).exists() else None)
        (self.lab / rel).write_text(
            f"<!-- session-state: VERIFIED @ {sha} on 2026-08-22 via probe -->\n"
            "# probe\n\nplaceholder\n\nedited after the stamp, which this contract permits\n",
            encoding="utf-8",
        )
        result = stamps.run(self.corpus())
        self.assertNotIn("PROBE_SESSION", " ".join(f.path for f in result.findings))

    def test_one_declared_drift_is_not_a_blanket_amnesty(self) -> None:
        """**Regression probe.** `HANDOFF.md` honestly declares `PROVENANCE.md`'s stamp stale.
        That must not exempt a *different* document whose stamp has also drifted, which is what
        the first version of this guard did — one note excusing the whole corpus.
        """
        self._plant_drifted_stamp("drifted, and nothing anywhere declares it")
        handoff = (self.lab / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("NEEDS RE-HARDENING", handoff, "the lab must carry the real handover note")
        self.assert_finds(stamps.run(self.corpus()), "PROBE_STAMP.md")

    def test_a_drift_declared_IN_A_HANDOVER_is_accepted(self) -> None:
        """The rule offers two compliant states; declaring the drift is one of them.

        **Declared in a HANDOVER, not in the document itself.** The self-declaration hatch was
        removed (`OG-96`): a document quoting doctrine §8.2 and a document declaring its own drift
        are the same string, and only a reader can tell them apart —
        `docs/framework/DOC_WRITING_DOCTRINE.md` quotes that rule verbatim and excused itself.
        `PROVENANCE.md`'s real drift is declared in `HANDOFF.md`, which is where the reader who must
        decide whether to trust it actually looks.
        """
        rel = "docs/process/PROBE_DECLARED.md"
        self.plant(rel, "# probe\n\nplaceholder\n")
        sha = _commit_all(self.lab, "base for the declared-drift probe")
        self.addCleanup(lambda: self.remove(rel) if (self.lab / rel).exists() else None)
        (self.lab / rel).write_text(
            f"<!-- artifact-hardened: APPROVED @ {sha} on 2026-08-22 via three-pass-v1 -->\n"
            "# probe\n\nplaceholder\n\nedited after the stamp\n",
            encoding="utf-8",
        )
        handoff = self.lab / "HANDOFF.md"
        original = handoff.read_text(encoding="utf-8")
        self.addCleanup(lambda: handoff.write_text(original, encoding="utf-8"))
        handoff.write_text(
            original + f"\n| drift | **NEEDS RE-HARDENING** — `{rel}` was edited after its stamp |\n",
            encoding="utf-8",
        )
        result = stamps.run(self.corpus())
        self.assertNotIn("PROBE_DECLARED", " ".join(f.path for f in result.findings))

    def test_a_document_that_merely_QUOTES_the_rule_does_not_excuse_itself(self) -> None:
        """`OG-96`, found by three Pass-7 agents. The hatch that made this possible is gone.

        `docs/framework/DOC_WRITING_DOCTRINE.md` §8.2 reads *"Re-harden, or mark NEEDS
        RE-HARDENING"*. While the escape accepted the marker anywhere in the document, a drifted
        stamp on the law file that DEFINES the rule excused itself by containing the rule.
        """
        rel = "docs/process/PROBE_QUOTES.md"
        self.plant(rel, "# probe\n\nplaceholder\n")
        sha = _commit_all(self.lab, "base for the rule-quoting probe")
        self.addCleanup(lambda: self.remove(rel) if (self.lab / rel).exists() else None)
        (self.lab / rel).write_text(
            f"<!-- artifact-hardened: APPROVED @ {sha} on 2026-08-22 via three-pass-v1 -->\n"
            "# probe\n\nA stamp on an edited body is invalid. Re-harden, or mark "
            "**NEEDS RE-HARDENING**.\n\nedited after the stamp\n",
            encoding="utf-8",
        )
        self.assert_finds(stamps.run(self.corpus()), "PROBE_QUOTES")

    def test_an_ambiguous_BASENAME_does_not_carry_a_declaration(self) -> None:
        """`OG-96`: `HANDOFF.md`'s honest declaration about the root `PROVENANCE.md` excused an
        unrelated `tools/graphify/vendor/PROVENANCE.md`. A basename only names a document when it
        is unique.
        """
        twin = "docs/process/PROBE_TWIN.md"
        other = "docs/plan/PROBE_TWIN.md"
        self.plant(twin, "# twin one\n")
        self.plant(other, "# twin two\n")
        sha = _commit_all(self.lab, "base for the basename-collision probe")
        for rel in (twin, other):
            self.addCleanup(lambda r=rel: self.remove(r) if (self.lab / r).exists() else None)  # type: ignore[misc]
        (self.lab / other).write_text(
            f"<!-- artifact-hardened: APPROVED @ {sha} on 2026-08-22 via three-pass-v1 -->\n"
            "# twin two\n\nedited after the stamp\n",
            encoding="utf-8",
        )
        handoff = self.lab / "HANDOFF.md"
        original = handoff.read_text(encoding="utf-8")
        self.addCleanup(lambda: handoff.write_text(original, encoding="utf-8"))
        handoff.write_text(
            original + "\n| drift | **NEEDS RE-HARDENING** — `PROBE_TWIN.md` drifted |\n",
            encoding="utf-8",
        )
        self.assert_finds(stamps.run(self.corpus()), "PROBE_TWIN")



# A corpus of strings that between them exhibit every residue class the guard names. Used to prove
# each declared pattern is REACHABLE — see `test_every_residue_pattern_can_actually_match`.
_RESIDUE_SAMPLES = (
    "a `literal backtick` in prose",
    "**not actually bold**",
    "| a | b |",
    "total: [object Object]",
    "value is undefined here",
    "score NaN reported",
    # `_RAW_PATTERNS`' member. It searches the unstripped html because a comment is invisible once
    # tags are removed, which is also why the reachability probe has to cover BOTH tuples.
    "<!-- figure: architecture-overview -->",
)


def _matches_something(pattern: re.Pattern[str]) -> bool:
    return any(pattern.search(sample) for sample in _RESIDUE_SAMPLES)


class RenderedOutputIsFalsified(unittest.TestCase):
    """Falsified against **real built bytes**, never a hand-written HTML literal.

    `LESSONS.md` L-15: the probe goes only into the artifact the gate certifies. A test that wrote
    its own HTML would be comparing a literal against itself — `DOC_WRITING_DOCTRINE.md` §5's flat
    prohibition — and would have passed just as happily while the guard read the wrong thing.
    """

    built: str
    build_skip: str
    _env_tmp: tempfile.TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        # A lab with the corpus but WITHOUT either engine's node_modules — the shape of a fresh
        # clone, and of every `git archive` verification lab.
        cls._env_tmp = tempfile.TemporaryDirectory(
            prefix="corpus-noengine-", ignore_cleanup_errors=True
        )
        lab = Path(cls._env_tmp.name) / "repo"
        lab.mkdir(parents=True)
        _build_lab(lab)
        for engine in ("tools/visual-engine", "tools/mermaid-engine"):
            _force_rmtree(lab / engine / "node_modules")

        # **Never `raise SkipTest` from `setUpClass`.** unittest then drops the whole class from
        # the run COUNT — not "7 skipped", but 7 tests that never appear — which is exactly the
        # shape of the defect `SUITE-05` exists to catch ("a broken import makes unittest skip a
        # whole module, and the run stays green with the tests simply absent"). Measured: it turned
        # a lab health run red on `111 defined but only 104 ran`. Each test skips itself instead,
        # and a self-skip IS counted.
        cls.built = ""
        cls.build_skip = ""
        corpus = Corpus(root=_ROOT)
        out = _ROOT / ".docgen" / "corpus_check_probe"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True, exist_ok=True)
        code, log = rendered_output._build(_ROOT, corpus.governed[:1], out)
        pages = sorted(out.glob("*.html"))
        if code != 0:
            cls.build_skip = f"the governed corpus did not build here: {log[-200:]}"
        elif not pages:
            cls.build_skip = "the build wrote no HTML"
        else:
            cls.built = pages[0].read_text(encoding="utf-8", errors="replace")
        shutil.rmtree(out, ignore_errors=True)

    def _require_built(self) -> str:
        """The real built bytes, or a counted skip when this environment cannot build."""
        if self.build_skip:
            self.skipTest(self.build_skip)
        return self.built

    @classmethod
    def tearDownClass(cls) -> None:
        _force_rmtree(Path(cls._env_tmp.name))
        cls._env_tmp.cleanup()

    def test_an_absent_render_engine_skips_rather_than_failing(self) -> None:
        """**Regression probe, and the most expensive defect of this phase.**

        `node_modules` is gitignored by design, so it is absent in a fresh clone and in every
        `git archive` verification lab. The first version of this guard treated the resulting build
        failure as a CRITICAL corpus finding — `CONS-11` went red, `tools.health` went red, and
        because the pre-push hook *runs health*, **the moat refused a clean push**. The moat attack
        harness caught it on its positive control, "a clean commit and push are accepted".

        An environment fact is not a finding about the corpus. This asserts the guard SKIPs — which
        is still not a pass, and `--full`/`--strict` still fail on it.
        """
        lab = Path(self._env_tmp.name) / "repo"
        result = rendered_output.run(Corpus(root=lab))
        self.assertEqual(
            result.status, Status.SKIP,
            f"expected SKIP with no render engine present, got {result.status}: {result.summary}",
        )
        # Degraded, not absent: with no engines the guard inspects the TRACKED docgen-built
        # artifacts instead of checking nothing, and still reports SKIP because a committed
        # snapshot cannot show a defect introduced since it was committed.
        self.assertIn("render engines absent", result.summary)
        self.assertIn("TRACKED built artifact", result.summary)
        made = re.search(r"(\d+) assertion", result.summary)
        self.assertIsNotNone(made, f"the fallback must report its assertion count: {result.summary}")
        assert made is not None
        self.assertGreater(
            int(made.group(1)), 0,
            "the fallback must make real assertions, not merely announce itself",
        )

    def test_the_real_build_is_clean(self) -> None:
        findings, checked = rendered_output.inspect_residue("probe.html", self._require_built())
        self.assertEqual(findings, [], "the real build carries unrendered markup")
        self.assertGreater(checked, 0)

    def test_a_backtick_planted_in_the_OUTPUT_is_refused(self) -> None:
        """The 118-backticks defect: inline code that never became code, invisible in the source."""
        built = self._require_built()
        probed = built.replace("</body>", "<p>a `literal backtick` in the body</p></body>")
        self.assertNotEqual(probed, built, "the probe did not attach")
        findings, _ = rendered_output.inspect_residue("probe.html", probed)
        self.assertTrue(any("backtick" in f.message for f in findings))

    def test_unrendered_bold_planted_in_the_OUTPUT_is_refused(self) -> None:
        built = self._require_built()
        probed = built.replace("</body>", "<p>**not actually bold**</p></body>")
        findings, _ = rendered_output.inspect_residue("probe.html", probed)
        self.assertTrue(any("bold" in f.message for f in findings))

    def test_backticks_inside_code_are_content_not_residue(self) -> None:
        """A guard that cannot tell content from residue reports the flagship's own samples."""
        built = self._require_built()
        probed = built.replace("</body>", "<pre><code>`ls -la`</code></pre></body>")
        findings, _ = rendered_output.inspect_residue("probe.html", probed)
        self.assertEqual(findings, [])

    def test_contrast_is_measured_on_the_built_stylesheet(self) -> None:
        """`OG-49`: every caller passed ``pairs=None``, so Gate 10 only ever saw design tokens."""
        clean, checked, pairs = rendered_output.inspect_contrast(
            "probe.html", self._require_built()
        )
        self.assertEqual(clean, [], "the real build has an illegible declared text pairing")
        # **`pairs`, not `checked`** (`OG-113`). This asserted `checked > 0` under the message
        # "no pairs were derived from the built document" — but `checked` also counts one
        # assertion per declared role, so it is >= 8 before a single pair exists. Measured:
        # deleting every ink role from the real built bytes gives `checked = 8, pairs = 0`, and
        # the assertion passed while its own message claimed the opposite. A test that cannot
        # fail for the reason it names is not a test.
        self.assertGreater(pairs, 0, "no pairs were derived from the built document")
        self.assertGreater(checked, pairs, "role assertions are no longer counted")

    def test_an_illegible_pair_planted_in_the_BUILT_stylesheet_is_refused(self) -> None:
        built = self._require_built()
        probed = built.replace(
            "</style>", ":root{--fg:#777777;--paper:#7A7A7A;}</style>", 1
        )
        self.assertNotEqual(probed, built, "the probe did not attach")
        findings, _, _pairs = rendered_output.inspect_contrast("probe.html", probed)
        self.assertTrue(findings, "an illegible pair in the built stylesheet was not refused")

    def test_every_residue_pattern_can_actually_match(self) -> None:
        """`OG-104` — a pattern with no counter-example is a pattern nobody has ever seen fire.

        `\\b` binds to WORD characters, and `]` is not one. Written
        `\\b(?:undefined|NaN|\\[object Object\\])\\b`, the trailing boundary sat between `]` and
        whatever followed — two non-word characters, never a boundary — so the `[object Object]`
        arm could not match any input at all. The guard advertised the most recognisable
        JavaScript sentinel of the three and had never been able to see it.

        Derived from `_RESIDUE_PATTERNS`, so a pattern added later is probed automatically rather
        than inheriting this same silence.
        """
        for pattern, label, _sev in (
            rendered_output._RAW_PATTERNS + rendered_output._RESIDUE_PATTERNS
        ):
            with self.subTest(pattern=pattern.pattern):
                self.assertTrue(
                    _matches_something(pattern),
                    f"{label}: no sample in the probe corpus matches {pattern.pattern!r} — the "
                    "pattern is unreachable and the check it advertises does not exist",
                )

    def test_a_javascript_sentinel_in_the_OUTPUT_is_refused(self) -> None:
        """The concrete half of the above, through the real built document."""
        built = self._require_built()
        for sentinel in ("[object Object]", "undefined", "NaN"):
            with self.subTest(sentinel=sentinel):
                probed = built.replace("</body>", f"<p>total: {sentinel}</p></body>")
                self.assertNotEqual(probed, built, "the probe did not attach")
                findings, _ = rendered_output.inspect_residue("probe.html", probed)
                self.assertTrue(
                    any("sentinel" in f.message for f in findings),
                    f"{sentinel!r} leaked into visible text and was not refused",
                )

    def test_an_unresolved_figure_placeholder_in_the_OUTPUT_is_refused(self) -> None:
        """`OG-81`'s CRITICAL pattern, which had no probe of its own.

        `<!-- figure: … -->` is the marker a figure leaves when the renderer never replaced it, and
        it is the only CRITICAL in either pattern tuple — a document shipping one has a hole where
        a diagram should be. It searches the RAW html rather than the visible text (a comment is
        invisible once tags are stripped), so it lives in `_RAW_PATTERNS` and the reachability
        probe above, which iterated `_RESIDUE_PATTERNS` alone, could not see it either. Both tuples
        are now covered there, and this plants the real thing.
        """
        built = self._require_built()
        probed = built.replace("</body>", "<!-- figure: architecture-overview --></body>")
        self.assertNotEqual(probed, built, "the probe did not attach")
        findings, _ = rendered_output.inspect_residue("probe.html", probed)
        self.assertTrue(
            any(f.severity is Severity.CRITICAL for f in findings),
            f"an unresolved figure placeholder was not refused as CRITICAL: "
            f"{[(f.severity, f.message) for f in findings]}",
        )

    def test_a_role_that_never_reaches_a_COMPARISON_is_refused(self) -> None:
        """`OG-105` — present is not checked.

        Contrast is computed only inside a theme block declaring both an ink and a ground. A role
        that appears only in single-sided blocks satisfied the presence assertion while never being
        compared against anything, so its readability was unasserted and the summary still counted
        the document as checked. Same shape as `OG-64`, which this guard exists to close.

        The probe moves one ink role out of every two-sided block into a ground-only block: still
        present, no longer compared.
        """
        ink = rendered_output._INK_ROLES[0]
        built = self._require_built()
        stripped = re.sub(rf"--{re.escape(ink)}\s*:\s*#[0-9a-fA-F]{{3,8}}\s*;", "", built)
        probed = stripped.replace(
            "</style>", f".lonely{{--{ink}:#101010;}}</style>", 1
        )
        self.assertNotEqual(probed, built, "the probe did not attach")
        findings, _, _pairs = rendered_output.inspect_contrast("probe.html", probed)
        self.assertTrue(
            any("never reach a contrast comparison" in f.message for f in findings),
            f"--{ink} was declared but never compared, and the guard reported clean",
        )

    def test_a_document_with_no_theme_block_does_not_CRASH_the_guard(self) -> None:
        """`OG-135` — an early return that still yielded the OLD tuple shape.

        `inspect_contrast` gained a third return value (the pair count, `OG-113`) and one exit was
        left at two: the path taken when a built document declares no colour custom properties.
        Every caller unpacks three, so that path raised `ValueError: too many values to unpack` —
        a crash, not a finding, in the guard whose job is to report exactly that condition.

        Found by `mypy --strict`, not by any test, which is the argument for the type gate being a
        health check rather than a nicety. Probed here so it cannot return silently.
        """
        findings, checked, pairs = rendered_output.inspect_contrast(
            "probe.html", "<html><body>no stylesheet at all</body></html>"
        )
        self.assertEqual(pairs, 0)
        self.assertTrue(findings, "a document with no colour properties must be reported")
        self.assertGreater(checked, 0)

    def test_the_probes_above_are_not_satisfied_by_a_guard_that_flags_everything(self) -> None:
        """Two-sided control. Every probe here plants a defect and demands a finding; without this
        one, deleting the guard's exemptions would satisfy all of them.
        """
        built = self._require_built()
        residue, _ = rendered_output.inspect_residue("probe.html", built)
        contrast, _, _pairs = rendered_output.inspect_contrast("probe.html", built)
        self.assertEqual(residue + contrast, [], "the unmodified build is reported as defective")

    def _skip_unless_run_itself_can_build(self) -> None:
        """`run()` returns SKIP by design when an engine's node_modules is absent, and the class
        build above can still succeed (its first governed document may carry no figure). The two
        tests that assert PASS/FAIL from `run()` itself must skip on the SAME predicate `run()`
        uses, or they measure the environment instead of the guard."""
        if self.build_skip:
            self.skipTest(self.build_skip)
        missing = [e for e in rendered_output._ENGINES if not (_ROOT / e / "node_modules").is_dir()]
        if missing:
            self.skipTest(
                f"render engine deps absent ({', '.join(missing)}): run() SKIPs by design, so "
                "there is no PASS or FAIL to assert"
            )

    def test_run_itself_fails_on_a_real_build_carrying_planted_residue(self) -> None:
        """`P8-037` — every test above drives `inspect_residue`/`inspect_contrast` directly.

        `run()` is the function every CLI invocation and `tools.health` actually call, and nothing
        drove it end to end (build, read the written bytes, inspect) to a real FAIL.
        `CleanCorpusIsAccepted._textual_guards()` excludes `rendered-output` by NAME because it
        needs a real build, so nothing else in this suite proves `run()` can fail at all — a guard
        with an `if findings: return failed(...)` branch that is never exercised is a branch
        nobody has ever seen taken.

        The build itself is real (this environment's own node_modules, skipped via `self.skipTest`
        when absent, never faked) — only the ONE byte-for-byte defect layered on top, in the
        written OUTPUT file, is planted, exactly as `LESSONS.md` L-15 requires: the probe goes into
        the artifact the gate certifies, not a hand-written literal compared against itself.
        """
        self._skip_unless_run_itself_can_build()
        corpus = Corpus(root=_ROOT)
        real_build = rendered_output._build

        def _poisoned_build(root: Path, docs: tuple[str, ...], out: Path) -> tuple[int, str]:
            code, log = real_build(root, docs, out)
            if code == 0:
                pages = sorted(out.glob("*.html"))
                self.assertTrue(pages, "the real build wrote no HTML to poison")
                target = pages[0]
                text = target.read_text(encoding="utf-8")
                target.write_text(
                    text.replace(
                        "</body>", "<p>a `literal backtick` in the body</p></body>", 1
                    ),
                    encoding="utf-8",
                )
            return code, log

        with unittest.mock.patch.object(rendered_output, "_build", _poisoned_build):
            result = rendered_output.run(corpus)
        self.assertEqual(
            result.status, Status.FAIL,
            f"run() did not fail on a real build carrying planted residue: {result.summary}",
        )
        self.assertTrue(
            any("backtick" in f.message for f in result.findings),
            f"the planted backtick was not among run()'s own findings: {result.findings}",
        )

    def test_run_itself_passes_on_the_real_corpus_when_it_can_build(self) -> None:
        """Two-sided: without this, a `run()` that always failed would satisfy the probe above.

        Also the "parallel derived assertion set" the finding asks for: `rendered-output` is
        excluded BY NAME from `CleanCorpusIsAccepted._textual_guards()` because it needs a real
        build, so nothing else in the suite ever asserts it passes on the real, unpoisoned corpus.
        This does, whenever the environment can actually build.
        """
        self._skip_unless_run_itself_can_build()
        result = rendered_output.run(Corpus(root=_ROOT))
        self.assertEqual(
            result.status, Status.PASS,
            f"rendered-output failed on the real, unmodified corpus: {result.summary}\n"
            + "\n".join(f.render() for f in result.sorted_findings()[:6]),
        )
        self.assertIn(rendered_output.GUARD, guard_names(), "rendered-output fell out of GUARDS")

    def test_an_environment_failure_log_skips_not_fails(self) -> None:
        """`P8-098` — the `_ENV_SIGNATURES` branch (a partially-installed engine: `node_modules`
        exists but a needed package inside it does not) was reachable only by `_build` actually
        failing that exact way; nothing ever drove it. Iterated at run time so a signature added
        later is covered automatically.
        """
        corpus = Corpus(root=_ROOT)
        self.assertTrue(
            rendered_output._ENV_SIGNATURES, "the signature list is empty; the probe is vacuous"
        )
        for sig in rendered_output._ENV_SIGNATURES:
            with self.subTest(sig=sig):
                fake = lambda root, docs, out, sig=sig: (1, f"build error: {sig} somewhere in the log")
                with unittest.mock.patch.object(rendered_output, "_build", fake):
                    result = rendered_output.run(corpus)
                self.assertEqual(
                    result.status, Status.SKIP,
                    f"{sig!r} in the build log did not SKIP: {result.status}, {result.summary}",
                )

    def test_a_non_environment_build_failure_still_fails_critical(self) -> None:
        """Two-sided control: without this, treating EVERY build failure as an environment fact
        would satisfy the probe above and hide a real corpus defect behind a false SKIP.
        """
        # SKIP WITH THE CAUSE NAMED, on the guard's OWN precondition (`L-25`). `run()` returns SKIP
        # before it ever calls `_build` when a vendored engine's `node_modules` is missing — which
        # is the normal state of a fresh clone, a CI runner, and the moat harness's own lab, since
        # `node_modules` is gitignored by design. Patching `_build` in that environment tests
        # nothing: the patched function is never reached, and the probe fails for the one reason
        # that is not a defect. Measured 2026-08-23 — this probe, written earlier the same day, was
        # the single reason the harness's clean-commit CONTROL was refused.
        missing = [e for e in rendered_output._ENGINES
                   if not (_ROOT / e / "node_modules").is_dir()]
        if missing:
            raise unittest.SkipTest(
                f"{', '.join(missing)} has no node_modules, so `run()` SKIPs before reaching "
                "`_build` — run `npm install` in each engine to exercise this path"
            )

        corpus = Corpus(root=_ROOT)
        fake = lambda root, docs, out: (1, "a real problem in the governed markdown source")
        with unittest.mock.patch.object(rendered_output, "_build", fake):
            result = rendered_output.run(corpus)
        self.assertEqual(result.status, Status.FAIL)
        self.assertTrue(
            any(f.severity is Severity.CRITICAL for f in result.findings),
            "a non-environment build failure was not reported at CRITICAL",
        )

    def test_two_block_elements_each_carrying_half_a_split_token_produce_no_false_bold_finding(
        self,
    ) -> None:
        """`P8-128` — `_BLOCK_TAGS`/`_BLOCK_TAG_RE` had zero direct coverage.

        Each block-level tag becomes a NEWLINE in `_visible_text`, specifically so two
        independent paragraphs that each carry an unmatched `**` are never concatenated into one
        false unrendered-bold finding — the bold pattern excludes newlines (`[^*\\n]`) exactly so
        a block boundary between them defeats it.
        """
        html = "<html><body><p>Alpha **beta</p><p>gamma** delta</p></body></html>"
        findings, _ = rendered_output.inspect_residue("probe.html", html)
        self.assertEqual(
            findings, [], f"two separate paragraphs were falsely joined into one bold match: {findings}"
        )

    def test_the_same_fragments_WITHOUT_a_block_boundary_DO_produce_a_finding(self) -> None:
        """Two-sided control: without this, a guard that never matches ANYTHING would satisfy the
        probe above for free.
        """
        html = "<html><body><span>Alpha **beta</span><span>gamma** delta</span></body></html>"
        findings, _ = rendered_output.inspect_residue("probe.html", html)
        self.assertTrue(
            any("bold" in f.message for f in findings),
            "the same fragments without a block boundary between them were not caught",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
