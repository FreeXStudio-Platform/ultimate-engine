"""Counter-examples for `CONS-13` — the check that keeps the deferral guard's eyes open.

WHAT WENT WRONG, AND WHY THESE PROBES ARE SHAPED LIKE THIS
==========================================================
`tools/corpus_check/guards/cross_doc.py` refuses a ``SCHEDULED (Phase N)`` register row whose phase
the plan marks COMPLETE, because a deferral to finished work is parked forever. It answers *is N
complete?* by looking for a completion marker **inside phase N's own table row**.

Phases 1-3 carry one. Phases 4, 5 and 6 shipped without one — completion had migrated into the
status paragraph at the top of the plan — so the branch could not fire for two whole phases, and
`OG-07` and `OG-63` sat in the register's ``## Open`` table long after the phase that finished them
had ended. The guard reported clean throughout. That is `OG-210`.

So the probes below do two different jobs, and both are needed:

* most of them drive ``CONS-13`` itself, in both directions, over a lab whose plan has been mutated;
* :meth:`PhaseCompletionBlindnessTest.test_phase_completion_marker_is_what_the_deferral_guard_reads`
  drives the **relationship that actually broke** — remove a marker and watch `cross-doc` go blind
  on a real deferral, restore it and watch the finding come back. A probe that only tested
  ``CONS-13`` in isolation would pass just as happily if someone changed what `cross_doc` reads.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.corpus_check.guards.cross_doc import _phase_row, marks_complete, phase_rows
from tools.health.checks import Ctx, check_phase_completion_markers
from tools.health.model import Status
from tools.tests.lab import ROOT, LabCase

PLAN = "docs/plan/BUILD_PLAN.md"
REGISTER = "docs/process/OPEN_GATES.md"

# The real rows, as this plan spells them. Anchored on the phase cell so a probe fails loudly if the
# plan is restructured, rather than silently mutating nothing and asserting against an unchanged
# file — which is how a counter-example quietly stops being one.
MARKED_6 = "| **6** ✅ | **Procedure encoding** — DONE `aaee4d1` |"
UNMARKED_6 = "| **6** | **Procedure encoding** |"
MARKED_4 = "| **4** ✅ | **Document identity + archive** — DONE `23e6354` |"
UNMARKED_4 = "| **4** | **Document identity + archive** |"
# Phase 7 closed the build, so the plan now marks all seven and the prose reads "Phases 1–7".
# (Before the Phase-7 close it read "Phases 1–6" and row 7 was unmarked; these anchors moved with
# the completion the launch prompt required — `CONS-13` verifies both sides agree.)
PROSE = "Phases 1–7 are complete"


def _ctx(root: Path) -> Ctx:
    return Ctx(root=root, doc_system=root / "docs" / "design" / "doc-system", full=False)


class PhaseCompletionCheckTest(LabCase):
    """`CONS-13` over a lab whose plan is mutated one way at a time."""

    lab_prefix = "lab-phase-completion-"

    def setUp(self) -> None:
        self.plan = self.lab / PLAN
        self.original = self.plan.read_text(encoding="utf-8")
        self.addCleanup(lambda: self.plan.write_text(self.original, encoding="utf-8"))

    def _rewrite(self, *pairs: tuple[str, str]) -> None:
        text = self.plan.read_text(encoding="utf-8")
        for old, new in pairs:
            self.assertIn(old, text, f"anchor absent from the plan: {old[:60]!r}")
            text = text.replace(old, new, 1)
        self.plan.write_text(text, encoding="utf-8")

    def _run(self) -> tuple[Status, list[str]]:
        result = check_phase_completion_markers(_ctx(self.lab))
        return result.status, list(result.detail or []) or [result.summary]

    def test_phase_completion_passes_on_the_unmutated_tree(self) -> None:
        """The positive control. Without it, every probe below could be passing for free."""
        status, detail = self._run()
        self.assertIs(status, Status.PASS, detail)

    def test_phase_completion_catches_a_complete_phase_whose_row_is_unmarked(self) -> None:
        """**The measured defect.** Prose says finished; the row does not; `cross-doc` goes blind."""
        self._rewrite((MARKED_6, UNMARKED_6))
        status, detail = self._run()
        self.assertIs(status, Status.FAIL, detail)
        self.assertTrue(
            any("Phase 6" in d and "no completion marker" in d for d in detail),
            f"the finding must name the unmarked phase: {detail}",
        )

    def test_phase_completion_catches_a_marker_the_prose_does_not_support(self) -> None:
        """The other direction: a row claiming a completion the plan's status never states.

        Row 7 is now legitimately marked (the build is done), so the mismatch is manufactured from
        the PROSE side instead: drop Phase 7 from the status sentence while its row keeps its ✅.
        `CONS-13` must then name the row the prose has stopped supporting.
        """
        self._rewrite((PROSE, "Phases 1–6 are complete"))
        status, detail = self._run()
        self.assertIs(status, Status.FAIL, detail)
        self.assertTrue(
            any("Phase 7" in d and "status prose does not say so" in d for d in detail), detail
        )

    def test_phase_completion_catches_a_gap_in_the_completed_prefix(self) -> None:
        """Both sides agree and are still wrong: phase 6 finished while 4 and 5 did not.

        Isolated deliberately — prose and rows are moved together, so the only thing left to fail
        on is contiguity. A phased plan cannot finish a phase before the one it is built on.
        """
        self._rewrite(
            (PROSE, "Phases 1–3 are complete, and Phase 6 is complete"),
            (MARKED_4, UNMARKED_4),
            ("| **5** ✅ | **The blueprint layer** — DONE `d90722c` |",
             "| **5** | **The blueprint layer** |"),
        )
        status, detail = self._run()
        self.assertIs(status, Status.FAIL, detail)
        self.assertTrue(any("contiguous prefix" in d for d in detail), detail)

    def test_phase_completion_fails_rather_than_passes_with_no_prose_claim(self) -> None:
        """`LESSONS.md` L-37: a probe that derives its own subject set must refuse an empty one.

        If the status sentence is reworded past this check's vocabulary, the derived prose set is
        empty. Passing there would rebuild the very blindness the check exists to remove, one layer
        up — so the check must fail, loudly, and say which side it could not read.
        """
        self._rewrite((PROSE, "Phases 1–6 have been delivered"))
        status, detail = self._run()
        self.assertIs(status, Status.FAIL, detail)
        self.assertTrue(any("no phase-completion claim" in d for d in detail), detail)

    def test_phase_completion_fails_when_the_plan_carries_no_phase_table(self) -> None:
        """No rows means nothing to reconcile — and means `cross_doc` has nothing to read either."""
        text = self.plan.read_text(encoding="utf-8")
        self.plan.write_text(
            "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("|")),
            encoding="utf-8",
        )
        status, detail = self._run()
        self.assertIs(status, Status.FAIL, detail)
        self.assertTrue(any("no phase table" in d for d in detail), detail)


class PhaseCompletionBlindnessTest(LabCase):
    """The relationship `OG-210` broke: the marker is what the deferral guard actually reads."""

    lab_prefix = "lab-phase-blindness-"

    def _cross_doc(self) -> list[str]:
        proc = subprocess.run(
            (sys.executable, "-m", "tools.corpus_check", "--guard", "cross-doc",
             "--json", "--root", str(self.lab)),
            cwd=str(ROOT), capture_output=True, text=True, timeout=300, check=False,
        )
        report = json.loads(proc.stdout)
        return [f["message"] for g in report["guards"] for f in g["findings"]]

    def test_phase_completion_marker_is_what_the_deferral_guard_reads(self) -> None:
        """Plant a live deferral to a finished phase, then take the marker away.

        With the marker, `cross-doc` names the row. Without it, the guard says nothing at all —
        which is precisely the two-phase silence `OG-210` records. Asserting both halves pins the
        dependency, so a change to either side that re-opens the hole fails here.
        """
        plan = self.lab / PLAN
        register = self.lab / REGISTER
        original_plan = plan.read_text(encoding="utf-8")

        # A real deferral to Phase 4 — the shape `OG-07` and `OG-63` carried while nothing saw them.
        rows = register.read_text(encoding="utf-8")
        header = "| id | sev | disposition | title | evidence | closing it means |\n|---|---|---|---|---|---|\n"
        self.assertIn(header, rows, "the register's Open table header has moved")
        planted = (
            "| OG-901 | LOW | SCHEDULED (Phase 4) | a planted deferral to a finished phase | "
            "`docs/plan/BUILD_PLAN.md` | it should be refused, because Phase 4 has ended |\n"
        )
        register.write_text(rows.replace(header, header + planted, 1), encoding="utf-8")

        with_marker = self._cross_doc()
        self.assertTrue(
            any("OG-901" in m and "COMPLETE" in m for m in with_marker),
            f"a deferral to a completed phase must be refused: {with_marker}",
        )

        plan.write_text(original_plan.replace(MARKED_4, UNMARKED_4, 1), encoding="utf-8")
        self.assertNotIn(MARKED_4, plan.read_text(encoding="utf-8"))
        without_marker = self._cross_doc()
        self.assertFalse(
            any("OG-901" in m and "COMPLETE" in m for m in without_marker),
            "removing the marker is what blinded the guard for two phases; if this now fails, "
            "cross_doc no longer depends on the marker and CONS-13's premise needs rewriting",
        )


class PhaseRowDefinitionTest(LabCase):
    """One definition of "a phase row", per `RULES.md` Rule 1 — not two that can drift apart."""

    lab_prefix = "lab-phase-rows-"

    def test_phase_completion_readers_share_one_row_definition(self) -> None:
        """`phase_rows` and the single-row reader must never answer differently."""
        text = (self.lab / PLAN).read_text(encoding="utf-8")
        rows = phase_rows(text)
        self.assertTrue(rows, "the plan must yield phase rows for anything below to mean anything")
        for number, row in rows.items():
            self.assertEqual(_phase_row(text, number), row)
        self.assertIsNone(_phase_row(text, "999"))

    def test_phase_completion_marker_vocabulary_is_not_a_single_spelling(self) -> None:
        """`OG-99` grew the vocabulary from two spellings to seven; hold that open.

        A `marks_complete` that knew only ``✅`` would let ``**COMPLETE** … shipped`` through, which
        is exactly what a verifier demonstrated at `P7-21`.
        """
        for spelling in ("| 4 ✅ | x |", "| 4 | x — DONE `deadbee` |",
                         "| 4 | **COMPLETE — x** |", "| 4 | x, shipped |"):
            self.assertTrue(marks_complete(spelling), spelling)
        self.assertFalse(marks_complete("| 4 | **Document identity + archive** | planned |"))

