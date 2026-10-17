"""Counter-examples for the draft gate.

**This gate answered CLEAN for every possible input, twice, for two different reasons**, before
these probes existed. Both failures were silent and both looked exactly like success. That is the
worst failure mode a gate has, so the probes below are weighted toward *proving it can still see*
rather than toward proving it can still judge.

1. The throwaway copy was an unpacked archive with no ``.git``. ``Corpus`` enumerates documents with
   ``git ls-files``, so it enumerated nothing, every guard reported ``checked=0``, and the verdict
   was CLEAN for a probe naming a nonexistent module.
2. Fixed that, and the candidate document was written into the copy but never **staged** — so
   ``git ls-files`` still could not see it and the candidate run was byte-identical to the baseline.
   CLEAN again, for the same input, for a different reason.

The third failure was the opposite shape and is `OG-244`: no verdict at all. Building the baseline
as a repository and then copying it copied a LIVE object database, which the detached ``gc --auto``
behind ``git commit`` was already unlinking — so ``shutil.copytree`` raised before a guard ran. It
reproduced 3/3 on a 1,046-file host and 0/3 on this repository, which is why every self-check
passed: the gate crashed on exactly the projects big enough to need it. Its probes are in
``TheLabsMustBeBuildableWithoutRacingGit`` and they assert the MECHANISM (nothing copies a live
object database; no lab runs a collector), because the failure itself is a race and a probe that
has to win a race to go red is not a probe.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tools.draft import gate

_ROOT = Path(__file__).resolve().parents[2]

_CLEAN_DRAFT = """<!-- title: PROBE CLEAN -->
# A candidate that states nothing checkable

It describes its own purpose and cites nothing the corpus does not contain.
"""

# Three defects, each caught by a DIFFERENT guard, so one guard regressing cannot mask the others.
_BAD_DRAFT = """<!-- title: PROBE BAD -->
# A candidate carrying the defects the guards exist to catch

The checker lives at `tools/corpus_check/nonexistent_module.py`.
Run it with `python3 -m tools.definitely_not_a_module verify`.
"""


class TheGateMustBeAbleToSeeTheCorpus(unittest.TestCase):
    """The anti-vacuity half. A zero means *no visibility*, never *no problems*."""

    def test_a_copy_that_is_not_a_git_repository_is_REFUSED_not_reported_clean(self) -> None:
        """Failure #1, retained. Without this the gate is a function returning CLEAN."""
        with tempfile.TemporaryDirectory(prefix="draft-novcs-") as tmp:
            dest = Path(tmp) / "repo"
            dest.mkdir()
            tar = subprocess.run(["git", "-C", str(_ROOT), "archive", "HEAD"],
                                 capture_output=True, check=True, timeout=180).stdout
            subprocess.run(["tar", "-x", "-C", str(dest)], input=tar, check=True, timeout=180)
            self.assertFalse((dest / ".git").exists(), "this probe requires a NON-repository")

            with self.assertRaises(gate.EmptyCorpusError) as caught:
                gate._findings(dest)
            self.assertIn("invisible", str(caught.exception).lower())

    def test_the_assertion_names_the_cause_rather_than_just_failing(self) -> None:
        """A gate that fails without saying why costs the next reader the same hour it cost me."""
        with self.assertRaises(gate.EmptyCorpusError) as caught:
            gate._assert_sees_the_corpus([("register", 0), ("symbols", 0)])
        message = str(caught.exception)
        self.assertIn("git ls-files", message)
        self.assertIn("0 claims", message)

    def test_a_corpus_the_guards_CAN_see_does_not_trip_the_assertion(self) -> None:
        """Two-sided: the assertion must not fire on a healthy run."""
        gate._assert_sees_the_corpus([("register", 400), ("symbols", 0)])

    def test_the_materialised_copy_is_a_repository_the_guards_can_read(self) -> None:
        """Failure #1's fix, asserted directly rather than inferred from a passing verdict."""
        with tempfile.TemporaryDirectory(prefix="draft-mat-") as tmp:
            dest = Path(tmp) / "repo"
            gate._materialise(_ROOT, dest)
            self.assertTrue((dest / ".git").is_dir())
            listed = subprocess.run(["git", "ls-files"], cwd=dest, capture_output=True,
                                    text=True, check=True, timeout=120).stdout.split()
            self.assertGreater(len(listed), 100,
                               "the copy must enumerate the tracked corpus, not a handful of files")


class TheLabsMustBeBuildableWithoutRacingGit(unittest.TestCase):
    """`OG-244`. Two mechanisms, both measured, both retained.

    Measured on a 1,046-file host: 255 loose object directories immediately after ``_init_repo``'s
    commit, **zero** three seconds later — a detached ``gc --auto`` packing and pruning them while
    the caller was still reading the lab. The repair is not a retry: it is to never copy an object
    database, and to switch the collector off in a directory that lives for one run.
    """

    def test_no_live_object_database_is_ever_copied(self) -> None:
        """The candidate lab is copied from a WORKTREE, before either root owns a ``.git``.

        Asserted at the copy rather than through a passing verdict, because the old order failed
        only when the collector happened to be mid-prune — a verdict-level probe would have been
        green most runs and told the next reader nothing.
        """
        sources_had_git: list[bool] = []
        # `gate` does `import shutil` and calls `shutil.copytree`, so patching the module attribute
        # is the same object the gate resolves at call time — no reach into the module under test.
        real_copytree = shutil.copytree

        def spy(src: str | Path, dst: str | Path, *args: Any, **kwargs: Any) -> str:
            sources_had_git.append((Path(src) / ".git").exists())
            return str(real_copytree(src, dst, *args, **kwargs))

        with mock.patch.object(shutil, "copytree", spy):
            gate.check("docs/process/RULES.md", root=_ROOT,
                       source=_ROOT / "docs/process/RULES.md")

        self.assertTrue(sources_had_git,
                        "check() no longer copies a lab at all — re-point this probe at whatever "
                        "builds the candidate root, or the regression is unguarded")
        self.assertFalse(
            any(sources_had_git),
            "a lab was copied from a root that already had a .git: `gc --auto` unlinks loose "
            "objects under it, and copytree raises on the paths it just listed",
        )

    def test_a_materialised_lab_does_not_run_a_background_collector(self) -> None:
        """``gc.auto=0``, set before the commit that would otherwise launch the collector.

        Every git command a guard runs against a lab — ``git ls-files``, ``git cat-file`` — would
        otherwise race a process deleting the objects it reads. A lab is deleted after one run and
        never needs packing, so the collector has nothing to win here and a whole class to lose.
        """
        with tempfile.TemporaryDirectory(prefix="draft-gc-") as tmp:
            dest = Path(tmp) / "repo"
            gate._materialise(_ROOT, dest)
            got = subprocess.run(["git", "config", "--get", "gc.auto"], cwd=dest,
                                 capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(got.stdout.strip(), "0",
                             "the lab inherited the ambient gc policy instead of disabling it")


class TheGateMustActuallyJudge(unittest.TestCase):
    """The judging half — and the reason the candidate has to be STAGED, not merely written."""

    def _check(self, body: str, target: str = "docs/process/PROBE_DRAFT.md") -> gate.DraftReport:
        tmp = tempfile.TemporaryDirectory(prefix="draft-src-")
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "candidate.md"
        src.write_text(body, encoding="utf-8")
        return gate.check(target, root=_ROOT, source=src)

    def test_a_candidate_with_defects_is_CAUGHT(self) -> None:
        """Failure #2, retained: an unstaged candidate is invisible and this goes green."""
        report = self._check(_BAD_DRAFT)
        self.assertFalse(report.clean, "the gate reported CLEAN on a candidate with three defects")
        blob = " ".join(f.message for f in report.on_the_draft)
        self.assertIn("nonexistent_module", blob)
        self.assertIn("definitely_not_a_module", blob)

    def test_a_clean_candidate_is_CLEAN(self) -> None:
        """The control. Without it, `return not clean` would pass every probe above.

        It re-checks an EXISTING document, unchanged, rather than adding a new one — and that
        distinction is itself a finding. Adding any new Markdown file moves the tracked-document
        count that the charter states, so a brand-new document can never come back CLEAN no matter
        how careful its prose is. That is the corpus working correctly (the count is derived and
        guarded), and it means *"you must also update the count"* is part of the honest answer to
        "would this be accepted". A control that ignored it would be testing a state the gate
        cannot produce.
        """
        body = (_ROOT / "docs/process/RULES.md").read_text(encoding="utf-8")
        report = self._check(body, target="docs/process/RULES.md")
        self.assertTrue(
            report.clean,
            "re-checking an unchanged, committed document reported findings: "
            + "; ".join(f.render() for f in report.introduced[:3]),
        )

    def test_adding_a_NEW_document_reports_the_count_it_moves(self) -> None:
        """The other side of the control, stated as a promise rather than left as a surprise."""
        report = self._check(_CLEAN_DRAFT, target="docs/process/PROBE_NEW.md")
        self.assertFalse(report.clean)
        self.assertTrue(
            any("tracked" in f.message for f in report.elsewhere),
            "adding a document no longer reports the count it moves — either the charter stopped "
            "stating it, or the counts family stopped deriving it: "
            + "; ".join(f.render() for f in report.introduced[:3]),
        )

    def test_findings_on_OTHER_documents_are_reported(self) -> None:
        """The reason this compares two corpora instead of filtering one.

        Adding a document moves facts other documents state — a tracked-document count is the
        cheapest example. Those findings land on paths the candidate never mentions, so
        `corpus_check | grep <path>` misses every one, and they are exactly the class that made
        earlier sessions expensive: a document written in isolation, correct on its own terms,
        that silently falsified a sentence somewhere else.
        """
        report = self._check(_BAD_DRAFT)
        self.assertTrue(
            report.elsewhere,
            "adding a document to the corpus introduced no finding anywhere else — if a stated "
            "count no longer moves, this probe's premise has gone and it is testing nothing",
        )
        self.assertTrue(all(f.path != report.target for f in report.elsewhere))

    def test_the_live_tree_is_never_modified(self) -> None:
        """The gate runs on throwaway copies. A checker that dirties the repo is not usable."""
        before = subprocess.run(["git", "status", "--porcelain"], cwd=_ROOT,
                                capture_output=True, text=True, check=True, timeout=120).stdout
        self._check(_BAD_DRAFT)
        after = subprocess.run(["git", "status", "--porcelain"], cwd=_ROOT,
                               capture_output=True, text=True, check=True, timeout=120).stdout
        self.assertEqual(before, after, "the draft gate changed the working tree")

    def test_a_missing_candidate_is_an_error_not_a_pass(self) -> None:
        with self.assertRaises(FileNotFoundError):
            gate.check("docs/process/NO_SUCH_DRAFT.md", root=_ROOT)


if __name__ == "__main__":
    unittest.main()
