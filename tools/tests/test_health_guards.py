"""Counter-examples for the health checks' own vacuity guards.

Every check here passed over *nothing* before its guard existed. A check that cannot fail is
indistinguishable from one that did not run.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Any

from tools.health import checks
from tools.health import run as run_module
from tools.health.model import CheckResult, Stage, Status

_REPO = Path(__file__).resolve().parents[2]


class ExecutableTextStripsComments(unittest.TestCase):
    """A marker hidden in a comment satisfied the hook-integrity test. A WHOLE-line strip was not
    enough — a TRAILING comment on `exit 0` defeated it just as well."""

    def test_whole_line_comment_is_stripped(self) -> None:
        self.assertNotIn("MARKER", checks._executable_text(b"# MARKER\nexit 0\n"))

    def test_trailing_comment_is_stripped(self) -> None:
        self.assertNotIn("MARKER", checks._executable_text(b"exit 0  # MARKER\n"))

    def test_a_hash_inside_quotes_is_NOT_treated_as_a_comment(self) -> None:
        """Over-stripping is its own defect: a real invocation containing `#` must survive."""
        self.assertIn("colour#1", checks._executable_text(b'echo "colour#1"\n'))

    def test_real_executable_content_survives(self) -> None:
        self.assertIn("tools.health", checks._executable_text(b'"$PY" -m tools.health\n'))


class VacuityGuards(unittest.TestCase):
    """Behavioural, not textual.

    The first draft of these two tests grepped `checks.py` for a constant NAME — which is Rule 2
    violated inside the tests themselves: a test restating a fact the code owns breaks when the code
    is renamed and proves nothing when it passes. It broke on the very next rename. These run the
    checks instead.
    """

    def _ctx(self, root: Path) -> checks.Ctx:
        return checks.Ctx(root=root, doc_system=root / "docs" / "design" / "doc-system", full=False)

    def _skeleton(self, root: Path) -> None:
        """A tree that satisfies STRUCT-01, so the failures below are caused by the mutation only."""
        for rel in checks._CORE_DOCS:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("0.0.1" if rel == "PROJECT_VERSION" else ("x" * 400), encoding="utf-8")

    def test_baseline_skeleton_passes(self) -> None:
        """Guard against a vacuous test: if the skeleton did not pass, the failures below would
        prove nothing about the mutation."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._skeleton(root)
            self.assertIs(checks.check_core_docs(self._ctx(root)).status, Status.PASS)

    def test_an_emptied_core_document_fails(self) -> None:
        """Truncating the handover to zero bytes left this check green — it asserted EXISTENCE."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._skeleton(root)
            (root / "HANDOFF.md").write_text("", encoding="utf-8")
            result = checks.check_core_docs(self._ctx(root))
            self.assertIs(result.status, Status.FAIL)
            self.assertIn("HANDOFF.md", result.evidence)

    def test_a_non_semver_project_version_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._skeleton(root)
            (root / "PROJECT_VERSION").write_text("not-a-version", encoding="utf-8")
            self.assertIs(checks.check_core_docs(self._ctx(root)).status, Status.FAIL)

    def test_a_short_version_file_is_NOT_treated_as_empty(self) -> None:
        """The first draft used one flat byte floor for every core file and immediately failed on
        `PROJECT_VERSION`, which legitimately holds five bytes. A blanket threshold across
        heterogeneous artifacts is a false-positive generator, and a check that cries wolf gets
        bypassed — which is worse than the gap it closes."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._skeleton(root)
            (root / "PROJECT_VERSION").write_text("9.9.9", encoding="utf-8")
            self.assertIs(checks.check_core_docs(self._ctx(root)).status, Status.PASS)


class NodeSuiteCountsAreParsed(unittest.TestCase):
    """`expected 30/30` was a display literal that was never compared to anything, so the check was
    blind to tests that had been deleted or skipped."""

    def test_the_count_regex_reads_a_real_node_summary(self) -> None:
        sample = "ℹ tests 30\nℹ pass 30\nℹ fail 0\nℹ skipped 0\n"
        counts = dict(checks._NODE_COUNT_RE.findall(sample))
        self.assertEqual(counts.get("pass"), "30")
        self.assertEqual(counts.get("skipped"), "0")

    def test_the_glyph_prefix_does_not_defeat_the_anchor(self) -> None:
        """The leading marker glyph is a WORD character to Python's `re`, so an anchored `\\W*`
        prefix silently never matched and every count went unchecked."""
        self.assertTrue(re.match(r"^[ \t]*\S*[ \t]*", "ℹ pass 30"))


class NestingMarkIsNotABypassSwitch(unittest.TestCase):
    """`OG-103` — a recursion guard must not double as a way to switch checks off.

    `ENGINE_IN_HOOK_PROBE` exists so a health run nested inside a hook probe does not re-run the
    ~72 s behavioural probe and the counter-example suite that the outer run is already executing.
    It was compared against the literal `"1"`, and it gated **`STRUCT-04`'s behavioural probe and
    the whole of `SUITE-05`**. Anyone with that variable exported — an operator who set it once
    while debugging, a CI job that inherited it — got a health run in which the hooks are never
    exercised and no counter-example runs, reported as SKIP, and the pre-push moat does not use
    `--full`, so SKIP was not fatal there.

    A guard whose OFF state is one `export` away is a bypass switch. The mark is now a random
    token plus a marker file the minting process owns, so a genuine nesting proves itself and a
    stale variable proves nothing — failing toward *running the checks*, which is the safe side.
    """

    def test_a_forged_mark_does_not_count_as_nesting(self) -> None:
        import os as _os

        from tools.health.checks import _inside_hook_probe

        forgeries = (
            {"ENGINE_IN_HOOK_PROBE": "1"},
            {"ENGINE_IN_HOOK_PROBE": "true"},
            {"ENGINE_IN_HOOK_PROBE": "1", "ENGINE_HOOK_PROBE_MARKER": "/nonexistent/x.marker"},
            {"ENGINE_IN_HOOK_PROBE": "", "ENGINE_HOOK_PROBE_MARKER": ""},
        )
        for env in forgeries:
            with self.subTest(env=env), unittest.mock.patch.dict(_os.environ, env):
                self.assertFalse(
                    _inside_hook_probe(),
                    f"{env} was accepted as a live nesting — STRUCT-04's behavioural probe and "
                    "SUITE-05 would both be skipped in an ordinary health run",
                )

    def test_a_genuine_mark_is_still_honoured(self) -> None:
        """The other side: refusing every mark would restore the timeout this guard exists to stop.

        `SUITE-06` replays ~20 lab pushes, each of which runs health; without a working nesting
        mark that nests the 72 s probe twenty deep and the check reports TIMEOUT instead of a
        result.
        """
        import os as _os

        from tools.health.checks import _inside_hook_probe, _mint_probe_marker

        env: dict[str, str] = {}
        marker = _mint_probe_marker(env)
        try:
            with unittest.mock.patch.dict(_os.environ, env):
                self.assertTrue(_inside_hook_probe(), "a freshly minted mark was not honoured")
        finally:
            marker.cleanup()
        # Once the outer run exits its marker is gone, and the mark stops applying.
        with unittest.mock.patch.dict(_os.environ, env):
            self.assertFalse(_inside_hook_probe(), "a dead marker still counted as nesting")


class LockedFileTableFailsClosed(unittest.TestCase):
    """`CONS-03` — `OG-85`/`OG-94`. Every exit fails CLOSED, and none of them had a probe.

    The check compares `RULEBOOK.md`'s human-readable locked-file table against `VERSION.json`'s
    `rulebook_files`, in both directions. Its failure mode is not a wrong answer but **no answer**:
    four of its exits used to `SKIP`, and a verifier drove the full documented attack — rename the
    table's heading, drop `tools/hooks/pre-commit` from `rulebook_files`, complete the L9
    re-baseline — and watched the engine report HEALTHY with a file silently removed from the lock.

    Pass 6 converted two of the four exits and left two. Pass 7 walked through the two that
    remained. That is `LESSONS.md` L-26 in its purest form, and the reason this class enumerates
    **every** exit rather than the one that was reported.
    """

    @staticmethod
    def _text(result: CheckResult) -> str:
        """Everything the check said, as one string.

        `detail` is a list on the exits that report several problems and a string on the rest;
        asserting against it directly reads element membership on one and substring on the other,
        which is how these probes first passed on three exits and failed on two for a reason that
        had nothing to do with the behaviour under test.
        """
        return " | ".join(str(part) for part in (result.summary, result.detail))

    def _lab(self, version_json: str | None, rulebook: str | None) -> CheckResult:
        tmp = tempfile.TemporaryDirectory(prefix="cons03-")
        self.addCleanup(tmp.cleanup)
        doc_system = Path(tmp.name) / "docs" / "design" / "doc-system"
        doc_system.mkdir(parents=True)
        if version_json is not None:
            (doc_system / "VERSION.json").write_text(version_json, encoding="utf-8")
        if rulebook is not None:
            (doc_system / "RULEBOOK.md").write_text(rulebook, encoding="utf-8")
        ctx = checks.Ctx(root=Path(tmp.name), doc_system=doc_system, full=False)
        return checks.check_rulebook_locked_table(ctx)

    _MATCHING_RULEBOOK = (
        "# RULEBOOK\n\n## Locked-file set\n\n"
        "| # | File | why |\n|---|---|---|\n"
        "| 1 | `RULEBOOK.md` | the rules |\n"
        "| 2 | `VERSION.json` | the digest |\n"
    )
    _MATCHING_VERSION = '{"rulebook_files": ["RULEBOOK.md", "VERSION.json"]}'

    def test_the_same_files_in_a_different_ORDER_are_caught(self) -> None:
        """`P8-067`. Membership was bidirectional; order was never examined.

        The section above the table states the files are listed in `rulebook_files` order, and the
        L9 digest is computed over that sequence — so the order is a load-bearing claim, not
        presentation. Measured on the live tree before this existed: `VERSION.json` positions 8-10
        read install.sh / pre-push / pre-commit while the table read pre-push / pre-commit /
        install.sh, and CONS-03 reported the two "match exactly". Same set, wrong sequence, green.
        """
        reordered = (
            "# RULEBOOK\n\n## Locked-file set\n\n"
            "| # | File | why |\n|---|---|---|\n"
            "| 1 | `VERSION.json` | the digest |\n"
            "| 2 | `RULEBOOK.md` | the rules |\n"
        )
        result = self._lab(self._MATCHING_VERSION, reordered)
        self.assertIs(result.status, Status.FAIL, self._text(result))
        self.assertIn("ORDER", self._text(result))
        self.assertIn("position 1", self._text(result))

    def test_order_is_checked_only_after_membership_so_the_specific_message_survives(self) -> None:
        """A missing row must still report as missing, not as a position mismatch.

        Dropping a row shifts every later index, so an order check running first would bury the
        precise "documented as locked but NOT in rulebook_files" message under position noise —
        the same ordering mistake `OG-171` records.
        """
        missing_row = (
            "# RULEBOOK\n\n## Locked-file set\n\n"
            "| # | File | why |\n|---|---|---|\n"
            "| 1 | `RULEBOOK.md` | the rules |\n"
        )
        result = self._lab(self._MATCHING_VERSION, missing_row)
        self.assertIs(result.status, Status.FAIL, self._text(result))
        self.assertIn("locked but undocumented", self._text(result))
        self.assertNotIn("ORDER", self._text(result))

    def test_a_matching_pair_passes(self) -> None:
        """Two-sided control. Without it, a check that always failed would satisfy every probe."""
        result = self._lab(self._MATCHING_VERSION, self._MATCHING_RULEBOOK)
        self.assertEqual(result.status, Status.PASS, self._text(result))

    def test_a_bare_basename_row_still_matches_its_full_declared_path(self) -> None:
        """A cell with no directory (the table's convention for most rows, including files that
        live OUTSIDE `docs/design/doc-system/`) must still match — this is the control that proves
        the `P8-119` fix did not simply start requiring full paths everywhere."""
        result = self._lab(
            '{"rulebook_files": ["docs/framework/DOC_WRITING_DOCTRINE.md"]}',
            "# RULEBOOK\n\n## Locked-file set\n\n| # | File | why |\n|---|---|---|\n"
            "| 1 | `DOC_WRITING_DOCTRINE.md` | the method law |\n",
        )
        self.assertEqual(result.status, Status.PASS, self._text(result))

    def test_a_hook_retargeted_to_another_directory_is_refused(self) -> None:
        """`P8-119`'s counter-example: the WIDEST input that used to get through.

        Basename-only comparison let a table cell impersonate ANY declared file sharing its
        trailing name — `tools/hooks/pre-push` retargeted to `attacker/elsewhere/pre-push` kept
        comparing equal on `Path(...).name` alone. Measured before this fix, on exactly this input:
        `[PASS] RULEBOOK locked-file table matches VERSION.json exactly (1 file(s))`. A cell that
        itself spells a directory must now match that declared file's FULL path.
        """
        result = self._lab(
            '{"rulebook_files": ["tools/hooks/pre-push"]}',
            "# RULEBOOK\n\n## Locked-file set\n\n| # | File | why |\n|---|---|---|\n"
            "| 1 | `attacker/elsewhere/pre-push` | the moat |\n",
        )
        self.assertEqual(result.status, Status.FAIL, self._text(result))
        self.assertIn("tools/hooks/pre-push", self._text(result))

    def test_the_heading_is_not_load_bearing(self) -> None:
        """`OG-85`'s attack, first move: rename the section the check used to `split()` on.

        The literal `## Locked-file set` in Python was a restatement of a fact `RULEBOOK.md` owns
        (`docs/process/RULES.md` Rule 2), guarding a check whose entire job is to notice that
        document changing. The table is now located by its `File` header anywhere in the file.
        """
        renamed = self._MATCHING_RULEBOOK.replace("## Locked-file set", "## The locked-file set")
        self.assertNotIn("## Locked-file set", renamed, "the probe did not attach")
        result = self._lab(self._MATCHING_VERSION, renamed)
        self.assertEqual(
            result.status, Status.PASS,
            f"renaming the heading broke the check instead of being ignored: {result.detail}",
        )

    def test_the_full_OG85_attack_chain_is_refused(self) -> None:
        """Heading renamed AND a file dropped from `rulebook_files` — the measured attack.

        At `66e39cc` this FAILED; after the column was located by name it SKIPPED, and the engine
        reported HEALTHY with `tools/hooks/pre-commit` removed from the lock.
        """
        result = self._lab(
            '{"rulebook_files": ["RULEBOOK.md"]}',
            self._MATCHING_RULEBOOK.replace("## Locked-file set", "## The locked-file set"),
        )
        self.assertEqual(result.status, Status.FAIL, self._text(result))
        self.assertIn("VERSION.json", self._text(result))

    def test_an_unreadable_table_FAILS_rather_than_skips(self) -> None:
        result = self._lab(self._MATCHING_VERSION, "# RULEBOOK\n\nNo table at all here.\n")
        self.assertEqual(result.status, Status.FAIL, self._text(result))

    def test_a_table_without_a_File_column_FAILS_rather_than_skips(self) -> None:
        result = self._lab(
            self._MATCHING_VERSION,
            "# RULEBOOK\n\n## Locked-file set\n\n| # | path | why |\n|---|---|---|\n"
            "| 1 | `RULEBOOK.md` | the rules |\n",
        )
        self.assertEqual(result.status, Status.FAIL, self._text(result))

    def test_either_file_going_missing_FAILS_rather_than_skips(self) -> None:
        """Both are members of the locked set, so neither can vanish by accident."""
        for absent in ("VERSION.json", "RULEBOOK.md"):
            with self.subTest(absent=absent):
                result = self._lab(
                    None if absent == "VERSION.json" else self._MATCHING_VERSION,
                    None if absent == "RULEBOOK.md" else self._MATCHING_RULEBOOK,
                )
                self.assertEqual(result.status, Status.FAIL, self._text(result))

    def test_the_comparison_is_bidirectional(self) -> None:
        """Checking one direction made the lock SELF-CERTIFYING.

        `VERSION.json` declares both what is locked and the digest, and is not a member of its own
        locked set — so dropping an entry and re-baselining removed a file from the lock with every
        gate green. Both directions, every time.
        """
        with self.subTest(direction="locked but undocumented"):
            result = self._lab(
                '{"rulebook_files": ["RULEBOOK.md", "VERSION.json", "TAXONOMY.md"]}',
                self._MATCHING_RULEBOOK,
            )
            self.assertEqual(result.status, Status.FAIL, self._text(result))
            self.assertIn("TAXONOMY.md", self._text(result))
        with self.subTest(direction="documented but not locked"):
            result = self._lab(
                '{"rulebook_files": ["RULEBOOK.md"]}',
                self._MATCHING_RULEBOOK,
            )
            self.assertEqual(result.status, Status.FAIL, self._text(result))
            self.assertIn("VERSION.json", self._text(result))

    def test_no_exit_of_this_check_can_return_SKIP(self) -> None:
        """The class-level assertion, above the individual instances.

        Every probe above names one exit. This one asserts the PROPERTY they share — derived from
        the source, so an exit added later is covered without anyone remembering to add a probe.
        `docs/process/RULES.md` Rule 1: cover the class, not the instance.
        """
        import inspect

        source = inspect.getsource(checks.check_rulebook_locked_table)
        self.assertNotIn(
            "_skip(", source,
            "check_rulebook_locked_table has regained a SKIP exit — an unanswerable locked-file "
            "comparison IS the defect (OG-85/OG-94), never an environment fact",
        )


class StateFactExemptionsAreClauseScoped(unittest.TestCase):
    """`CONS-08` / `OG-123` — nobody opened this check in Pass 7, and it had the same defect.

    `OG-91` leaned on `CONS-08` to justify editing a hash-locked law file, so its correctness is
    load-bearing beyond itself. Its "bump" exemption — an instruction about a FUTURE change — was
    evaluated over the whole line, so it silenced every present-tense version claim sharing that
    line. Measured by appending one sentence to `HANDOFF.md`:

        "The rulebook is at version 9.9.9 today."                  -> FAIL   (correct)
        "The rulebook is at version 9.9.9 today; bump it later."   -> PASS   (silenced)

    A claim and an instruction on one line, and the CLAIM was the half that got silenced. The
    exemption had already been narrowed once, from skipping the entire line to skipping only the
    semver loop; the hole moved rather than closing (`LESSONS.md` L-26). It is now clause-scoped.
    """

    _VERSION_JSON = '{"version": "1.2.6", "rulebook_files": []}'

    def _lab(self, handover_extra: str = "") -> CheckResult:
        tmp = tempfile.TemporaryDirectory(prefix="cons08-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        doc_system = root / "docs" / "design" / "doc-system"
        doc_system.mkdir(parents=True)
        (doc_system / "VERSION.json").write_text(self._VERSION_JSON, encoding="utf-8")
        (root / "PROJECT_VERSION").write_text("0.4.1\n", encoding="utf-8")
        total = len(checks.CHECKS)
        # Enough true claims to clear the check's own anti-vacuity floor, so a FAIL below is
        # caused by the planted sentence and nothing else.
        body = "\n".join(
            [
                "# handover",
                "The rulebook is at version 1.2.6 and the project is at version 0.4.1.",
                f"Health reports {total} passed, 0 failed, 0 skipped.",
                "The rulebook 1.2.6 line is repeated so the floor is met.",
                "The project 0.4.1 line is repeated so the floor is met.",
                f"Confirm {total} passed, 0 failed, 0 skipped again.",
                handover_extra,
            ]
        )
        # DERIVED from the check's own tuple, never a second copy of it. The hardcoded list this
        # replaces went out of date the moment `SESSION_STATE.md` was added to `CONS-08`'s scope
        # (`OG-211`): the lab stopped writing one of the documents the check reads, and three
        # probes in this class failed for a reason that had nothing to do with clause scoping —
        # including the baseline whose entire job is to prove the others are not passing for free.
        self.assertTrue(checks.STATE_DOCS, "derived subject set is empty")
        for rel in checks.STATE_DOCS:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body + "\n", encoding="utf-8")
        return checks.check_state_docs_facts(
            checks.Ctx(root=root, doc_system=doc_system, full=False)
        )

    def test_the_baseline_lab_passes(self) -> None:
        """Without this, every assertion below would be satisfied by a check that always fails."""
        result = self._lab()
        self.assertEqual(result.status, Status.PASS, str(result.detail))

    def test_a_false_version_claim_is_refused(self) -> None:
        result = self._lab("The rulebook is at version 9.9.9 today.")
        self.assertEqual(result.status, Status.FAIL, str(result.detail))

    def test_bump_in_ANOTHER_clause_does_not_silence_the_claim(self) -> None:
        """The measured hole: one semicolon away from the instruction it belongs to."""
        result = self._lab("The rulebook is at version 9.9.9 today; bump it later.")
        self.assertEqual(
            result.status, Status.FAIL,
            "a 'bump' instruction in a later clause silenced a present-tense version claim",
        )

    def test_bump_in_the_SAME_clause_still_exempts(self) -> None:
        """Two-sided. Deleting the exemption would satisfy the probe above and produce a false red
        on the launch command, which really does say "bump PROJECT_VERSION to 0.4.0"."""
        result = self._lab("Next session, bump the rulebook to version 9.9.9.")
        self.assertEqual(result.status, Status.PASS, str(result.detail))

    def test_a_health_floor_claim_has_no_bump_exemption_at_all(self) -> None:
        """Floor claims were never exempt and must stay that way — the floor is the claim most
        likely to go stale, and it shares the launch line with the word "bump"."""
        result = self._lab("Run it and confirm 99 passed, 0 failed, 0 skipped, then bump it.")
        self.assertEqual(result.status, Status.FAIL, str(result.detail))

    def test_a_version_transition_record_is_still_exempt(self) -> None:
        result = self._lab("History: 1.0.0 -> 1.0.1 for the rulebook.")
        self.assertEqual(result.status, Status.PASS, str(result.detail))

class RootFlagMovesTheRuleLayer(unittest.TestCase):
    """`--root` moved every check onto the target tree EXCEPT the L9 hash gate, which kept
    validating this repository's own rulebook — so pointing health at a tree whose RULEBOOK carried
    an attacker-authored rule reported `[PASS] RULE-01 hash-gate holds`. A false green that gets
    louder the more deliberately you use the flag."""

    def test_a_foreign_root_gets_its_own_rule_layer(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "tree"
            target.mkdir()
            # The WORKING TREE, not `HEAD`. A gate exists to vet what is ABOUT to be committed;
            # a lab built from the last commit cannot see the change under test, so any edit
            # spanning both a checker and its subject failed until it was already committed —
            # backwards, and it cost a debugging pass on 2026-08-23 when the theme writer and
            # its verifier were changed together. `stash create` snapshots the worktree into a
            # dangling object WITHOUT touching the index, the worktree or the stash ref; it
            # returns empty when there is nothing to snapshot, hence the `or "HEAD"`.
            _snap = subprocess.run(["git", "-C", str(_REPO), "stash", "create"],
                                   capture_output=True, text=True, check=False,
                                   timeout=120).stdout.strip()
            tar = subprocess.run(["git", "-C", str(_REPO), "archive", _snap or "HEAD"],
                                 capture_output=True, check=True, timeout=120).stdout
            subprocess.run(["tar", "-x", "-C", str(target)], input=tar, check=True, timeout=120)
            rulebook = target / "docs" / "design" / "doc-system" / "RULEBOOK.md"
            rulebook.write_text(rulebook.read_text(encoding="utf-8") + "\n## L99 injected\n",
                                encoding="utf-8")
            # This test asserts where the RULE-01 hash gate points, nothing else. Left unmarked it
            # also paid for STRUCT-04's ~72 s behavioural hook probe and a nested run of this very
            # suite, which is what made the retained counter-examples take ~100 s to answer a
            # question about one line of routing. The mark skips those two with their reason
            # printed; every assertion below is unaffected.
            # The mark is a TOKEN backed by a marker file the caller owns, not the string "1" —
            # a literal was forgeable from any shell, and exporting it silently removed STRUCT-04's
            # behavioural probe and all of SUITE-05 from a real health run (`OG-103`). Minting it
            # through the same helper production uses keeps this test honest: if the mechanism
            # changes, this call fails to compile rather than quietly reverting to a slow run.
            import os as _os

            from tools.health.checks import _mint_probe_marker

            env = dict(_os.environ)
            marker = _mint_probe_marker(env)
            proc = subprocess.run(
                ["python3", "-m", "tools.health", "--root", str(target), "--no-run-log"],
                cwd=_REPO, capture_output=True, text=True, timeout=600, check=False, env=env,
            )
            marker.cleanup()
            self.assertIn("RULE-01", proc.stdout)
            self.assertNotIn("[PASS] RULE-01", proc.stdout,
                             "the hash gate must follow --root, not validate the engine's own tree")

def _covered_check_ids(id_by_name: dict[str, str], tests_dir: Path) -> set[str]:
    """Every check whose id or function name is referenced anywhere under ``tests_dir``.

    A pure, standalone scanner (no import of `tools.health.checks` inside it) so
    `RegistryCoverage.test_the_scanner_itself_distinguishes_named_from_unnamed` can drive it
    against a synthetic tree without touching the real registry.
    """
    covered: set[str] = set()
    for path in sorted(tests_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name, cid in id_by_name.items():
            if cid in covered:
                continue
            if name in text or f'"{cid}"' in text or f"'{cid}'" in text:
                covered.add(cid)
    return covered


class RegistryCoverage(unittest.TestCase):
    """`P8-047`: the registry declares 34 health checks (now 35 — `BUILD-04` was added closing
    `P8-044`) and, measured before this class existed, only a handful had ever been exercised as
    anything but a string in a register — the rest could regress silently forever with every
    citation of them still reading as though they were tested. `test_the_registry_is_covered_and_
    nonempty` catches exactly this for `GUARDS` (`tools/tests/test_corpus_check.py`); `CHECKS` had
    nothing analogous.

    This does not claim the backlog is closed. The floor is MEASURED, not invented, so it can only
    rise from here: a check gaining or losing test coverage becomes visible instead of silent,
    which is the actual defect this finding reports.
    """

    def test_the_scanner_itself_distinguishes_named_from_unnamed(self) -> None:
        """Counter-example for the scanner, on a synthetic tree — plant one covered and one
        uncovered id and confirm the split comes out right, before trusting it against the real
        registry below."""
        id_by_name = {"check_probe_named": "PROBE-01", "check_probe_unnamed": "PROBE-02"}
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp)
            (tests_dir / "test_probe.py").write_text(
                "from tools.health import checks\n"
                "checks.check_probe_named(None)\n",
                encoding="utf-8",
            )
            covered = _covered_check_ids(id_by_name, tests_dir)
        self.assertIn("PROBE-01", covered)
        self.assertNotIn("PROBE-02", covered)

    def test_the_scanner_also_recognises_a_bare_id_citation(self) -> None:
        """The other legitimate form: a test that asserts against the id string directly (as
        several of this file's own checks do) rather than calling the check function."""
        id_by_name = {"check_probe_cited": "PROBE-03"}
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp)
            (tests_dir / "test_probe.py").write_text(
                'self.assertIn("PROBE-03", result.check_id)\n', encoding="utf-8")
            covered = _covered_check_ids(id_by_name, tests_dir)
        self.assertIn("PROBE-03", covered)

    def test_registry_coverage_has_not_regressed(self) -> None:
        id_by_name = {fn.__name__: run_module._check_id_of(fn) for fn in checks.CHECKS}
        tests_dir = Path(__file__).resolve().parent
        covered = _covered_check_ids(id_by_name, tests_dir)
        total = len(checks.CHECKS)
        # Measured at the P8-047 fix: 11 of 35 (calling the function directly counts, and so does
        # asserting against its bare id, e.g. `RootFlagMovesTheRuleLayer`'s `"RULE-01"` check).
        # Never let it drop below that without noticing — raise this floor as coverage is added;
        # never lower it to make a regression quiet.
        self.assertGreaterEqual(
            len(covered), 11,
            f"only {len(covered)} of {total} registered health checks are named by any test "
            f"(covered ids: {sorted(covered)}) — a check with zero test coverage can regress "
            "silently forever (P8-047)",
        )


class MoatAttackCountIsNeverAStaleLiteral(unittest.TestCase):
    """`check_moat_attacks` (`P8-059`) hardcoded "seventeen"/"17" in its docstring and in the
    message for its "no result line" exit, after the harness had already grown past that count
    (live count at the time of writing: 21, `grep -c 'verdict ' tools/tests/hook_attacks.sh`).
    Drives the real "no result line" exit against a fake harness script with a KNOWN, chosen
    number of `verdict` calls and asserts the message reports THAT number, not a copied literal.
    """

    def test_the_no_result_line_message_names_the_live_derived_count_not_17(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_dir = root / "tools" / "tests"
            script_dir.mkdir(parents=True)
            script = script_dir / "hook_attacks.sh"
            # Three `verdict` calls, chosen to differ from both the old stale literal (17) and the
            # real harness's current count — and the script prints no "RESULT: N passed" line at
            # all, so `check_moat_attacks` takes its "no result line" exit.
            script.write_text(
                "#!/usr/bin/env bash\n"
                "verdict 1 0 'probe one'\n"
                "verdict 1 0 'probe two'\n"
                "verdict 1 0 'probe three'\n"
                "echo 'no result line printed on purpose'\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            ctx = checks.Ctx(root=root, doc_system=root / "docs" / "design" / "doc-system",
                             full=True)
            result = checks.check_moat_attacks(ctx)
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("3 refused attacks", result.evidence)
        self.assertNotIn("17 refused attacks", result.evidence)

    def test_the_docstring_no_longer_hardcodes_seventeen(self) -> None:
        """The class-level assertion: covers the source text itself, not one code path through
        it, so a literal reintroduced anywhere in the docstring or a message is caught."""
        import inspect

        source = inspect.getsource(checks.check_moat_attacks)
        self.assertNotIn("Seventeen", source)
        self.assertNotIn("17 refused attacks", source)


class RaisingCheckIdRecoveryIsNotAFixedVocabulary(unittest.TestCase):
    """`_check_id_of` (`P8-121`) used to look for a quoted id from a hardcoded five-prefix
    vocabulary (`STRUCT|RULE|CONS|BUILD|SUITE`) — the prefixes in use AT THE TIME it was written.
    A check registered under any other prefix that then raised was reported by its FUNCTION NAME
    instead, exactly the defect `run_all`'s own comment says this recovery path exists to prevent.
    Runs the real `run_all` against a raising check whose id uses an unlisted prefix, on real
    module source (`inspect.getsource` needs an importable module, not a dynamically built
    function), rather than only unit-testing the regex.
    """

    @staticmethod
    def _run_one_probe(source: str, fn_name: str) -> CheckResult:
        import importlib.util
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe_module.py"
            path.write_text(source, encoding="utf-8")
            spec = importlib.util.spec_from_file_location("health_probe_module", path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules["health_probe_module"] = module
            try:
                spec.loader.exec_module(module)
                fn = getattr(module, fn_name)
                with unittest.mock.patch.object(run_module, "CHECKS", (fn,)):
                    results = run_module.run_all(
                        checks.Ctx(root=_REPO, doc_system=_REPO, full=False))
            finally:
                sys.modules.pop("health_probe_module", None)
        assert len(results) == 1, [r.check_id for r in results]
        return results[0]

    def test_an_unlisted_prefix_is_still_recovered_by_id(self) -> None:
        result = self._run_one_probe(
            'def check_probe_newprefix(ctx):\n'
            '    """A prefix absent from the old hardcoded vocabulary."""\n'
            '    _ = "MOAT-01"\n'
            '    raise RuntimeError("boom")\n',
            "check_probe_newprefix",
        )
        self.assertEqual(result.check_id, "MOAT-01")
        self.assertNotEqual(result.check_id, "check_probe_newprefix")

    def test_a_previously_listed_prefix_still_works_too(self) -> None:
        """Contrast control: the widening must not have broken the prefixes already covered."""
        result = self._run_one_probe(
            'def check_probe_known(ctx):\n'
            '    """A prefix already in the old vocabulary."""\n'
            '    _ = "STRUCT-09"\n'
            '    raise RuntimeError("boom")\n',
            "check_probe_known",
        )
        self.assertEqual(result.check_id, "STRUCT-09")


class DuplicateCheckIdsAreDetected(unittest.TestCase):
    """`run_all` (`P8-089`) never asserted `check_id` uniqueness across the registry — two checks
    silently sharing an id would both run and both report, indistinguishable to every consumer
    keyed by id (the run log, the JSON report, every citation in this corpus by that exact
    string). Drives the REAL `run_all` against a registry that genuinely collides, rather than
    only unit-testing a helper in isolation."""

    @staticmethod
    def _probe(check_id: str, label: str) -> checks.CheckFn:
        def check_probe(ctx: checks.Ctx) -> CheckResult:
            return CheckResult(check_id=check_id, stage=Stage.STRUCTURE, status=Status.PASS,
                               summary=label, evidence="")
        return check_probe

    def test_two_distinct_checks_sharing_an_id_are_flagged(self) -> None:
        colliding = (self._probe("STRUCT-99", "a"), self._probe("STRUCT-99", "b"))
        with unittest.mock.patch.object(run_module, "CHECKS", colliding):
            results = run_module.run_all(checks.Ctx(root=_REPO, doc_system=_REPO, full=False))
        dup = next((r for r in results if r.check_id == "REGISTRY-DUP"), None)
        self.assertIsNotNone(dup, "a genuine id collision produced no REGISTRY-DUP result")
        assert dup is not None
        self.assertIs(dup.status, Status.FAIL)
        self.assertIn("STRUCT-99", dup.evidence)

    def test_a_clean_registry_with_no_collisions_is_not_flagged(self) -> None:
        """Two-sided control: without it, a detector that always fired would satisfy the probe
        above for the wrong reason."""
        clean = (self._probe("STRUCT-97", "a"), self._probe("STRUCT-98", "b"))
        with unittest.mock.patch.object(run_module, "CHECKS", clean):
            results = run_module.run_all(checks.Ctx(root=_REPO, doc_system=_REPO, full=False))
        self.assertNotIn("REGISTRY-DUP", [r.check_id for r in results])


def _rule03_baseline_change_types() -> dict[str, dict[str, object]]:
    """A fresh, valid `change_types` mapping every time — never a shared class-level literal, so
    a test that mutates its own copy can never leak state into another (RUF012)."""
    entry = {"description": "d", "dependent_doc_ids": ["x"], "public_sanitization_rule": "r"}
    return {
        ct: dict(entry, dependent_doc_ids=list(entry["dependent_doc_ids"]))
        for ct in (
            "DETECTOR_CHANGE",
            "VISUAL_STYLE_CHANGE",
            "USER_POLICY_CHANGE",
            "ARCHITECTURE_CHANGE",
            "RULE_CHANGE",
        )
    }


class ImpactMapDescriptionIsValidated(unittest.TestCase):
    """RULE-03 (`P8-120`): `check_impact_map` type-checked `dependent_doc_ids` and
    `public_sanitization_rule` on every raw entry but never `description` — a null or blank
    description passed as though it were real documentation, because `compute_change_impact`
    never reads that field either, so nothing anywhere was checking it."""

    def _lab(self, change_types: dict[str, Any]) -> CheckResult:
        import json as _json

        tmp = tempfile.TemporaryDirectory(prefix="rule03-")
        self.addCleanup(tmp.cleanup)
        doc_system = Path(tmp.name) / "docs" / "design" / "doc-system"
        doc_system.mkdir(parents=True)
        (doc_system / "update_impact_map.json").write_text(
            _json.dumps({"change_types": change_types}), encoding="utf-8")
        ctx = checks.Ctx(root=Path(tmp.name), doc_system=doc_system, full=False)
        return checks.check_impact_map(ctx)

    def test_the_baseline_fixture_passes(self) -> None:
        """Two-sided control: without it, a check that always failed would satisfy every probe."""
        result = self._lab(_rule03_baseline_change_types())
        self.assertEqual(result.status, Status.PASS, str(result.detail))

    def test_a_null_description_is_refused(self) -> None:
        mutated = {k: dict(v) for k, v in _rule03_baseline_change_types().items()}
        mutated["DETECTOR_CHANGE"]["description"] = None
        result = self._lab(mutated)
        self.assertEqual(result.status, Status.FAIL)
        self.assertIn("description", str(result.detail))

    def test_a_blank_description_is_refused(self) -> None:
        mutated = {k: dict(v) for k, v in _rule03_baseline_change_types().items()}
        mutated["RULE_CHANGE"]["description"] = "   "
        result = self._lab(mutated)
        self.assertEqual(result.status, Status.FAIL)
        self.assertIn("description", str(result.detail))

    def test_a_missing_description_key_is_refused(self) -> None:
        mutated = {k: dict(v) for k, v in _rule03_baseline_change_types().items()}
        del mutated["ARCHITECTURE_CHANGE"]["description"]
        result = self._lab(mutated)
        self.assertEqual(result.status, Status.FAIL)
        self.assertIn("description", str(result.detail))


class EngineConfigCheckHonoursTheOverride(unittest.TestCase):
    """STRUCT-08 (`P8-100`) used to hardcode `ctx.root / "engine.config.json"`, so it certified the
    DEFAULT file's contents while `ENGINE_CONFIG_PATH` pointed the rest of the engine somewhere
    else entirely — a broken or missing override file ran the engine on silent built-in defaults
    while this check kept reporting the untouched default as parsing fine."""

    def setUp(self) -> None:
        self._prev = os.environ.get("ENGINE_CONFIG_PATH")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self._prev is None:
            os.environ.pop("ENGINE_CONFIG_PATH", None)
        else:
            os.environ["ENGINE_CONFIG_PATH"] = self._prev

    def _ctx(self, root: Path) -> checks.Ctx:
        return checks.Ctx(root=root, doc_system=root / "docs" / "design" / "doc-system", full=False)

    def test_a_broken_override_file_fails_not_the_untouched_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "engine.config.json").write_text("{}", encoding="utf-8")
            broken = root / "broken.json"
            broken.write_text("{ this is not json", encoding="utf-8")
            os.environ["ENGINE_CONFIG_PATH"] = str(broken)
            result = checks.check_engine_config_parses(self._ctx(root))
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("broken.json", result.summary)
        self.assertNotIn("top-level key", result.summary,
                         "must not report the untouched default's key count as though it were "
                         "the file actually in force")

    def test_an_override_naming_a_missing_file_fails_rather_than_certifying_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "engine.config.json").write_text('{"a": 1}', encoding="utf-8")
            os.environ["ENGINE_CONFIG_PATH"] = str(root / "does-not-exist.json")
            result = checks.check_engine_config_parses(self._ctx(root))
        self.assertIs(result.status, Status.FAIL)

    def test_the_ordinary_no_override_case_still_passes_on_a_clean_default(self) -> None:
        os.environ.pop("ENGINE_CONFIG_PATH", None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "engine.config.json").write_text('{"a": 1}', encoding="utf-8")
            result = checks.check_engine_config_parses(self._ctx(root))
        self.assertIs(result.status, Status.PASS)


class ThemeBuildMatchesSource(unittest.TestCase):
    """BUILD-04 (`P8-044`): the six committed `tools/visual-engine/themes/*.json` files were
    write-only build residue — nothing regenerated `buildAllThemes()`/`loadTokens()` and compared
    the result, so a hand-patched theme file, a re-vendored `tokens.json`, or an edited adapter
    could all drift from what is committed with every other gate still green. Run on a REAL
    archive of this repository (not a synthetic tree), so a passing baseline actually proves the
    checked-in files are what the adapter produces today, not merely that the comparison compiles.
    """

    @staticmethod
    def _archive(tmp: Path) -> Path:
        target = tmp / "tree"
        target.mkdir()
        # The WORKING TREE, not `HEAD`. A gate exists to vet what is ABOUT to be committed;
        # a lab built from the last commit cannot see the change under test, so any edit
        # spanning both a checker and its subject failed until it was already committed —
        # backwards, and it cost a debugging pass on 2026-08-23 when the theme writer and
        # its verifier were changed together. `stash create` snapshots the worktree into a
        # dangling object WITHOUT touching the index, the worktree or the stash ref; it
        # returns empty when there is nothing to snapshot, hence the `or "HEAD"`.
        _snap = subprocess.run(["git", "-C", str(_REPO), "stash", "create"],
                               capture_output=True, text=True, check=False,
                               timeout=120).stdout.strip()
        tar = subprocess.run(["git", "-C", str(_REPO), "archive", _snap or "HEAD"],
                             capture_output=True, check=True, timeout=120).stdout
        subprocess.run(["tar", "-x", "-C", str(target)], input=tar, check=True, timeout=120)
        return target

    @staticmethod
    def _ctx(root: Path) -> checks.Ctx:
        return checks.Ctx(root=root, doc_system=root / "docs" / "design" / "doc-system", full=False)

    @unittest.skipUnless(shutil.which("node"), "requires node on PATH")
    def test_a_clean_checkout_matches_its_own_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            result = checks.check_theme_build_matches_source(self._ctx(root))
        self.assertIs(result.status, Status.PASS, result.evidence)

    @unittest.skipUnless(shutil.which("node"), "requires node on PATH")
    def test_a_hand_patched_theme_file_is_caught_as_drift(self) -> None:
        """The exact counter-example: one byte changed in a committed theme file, nothing else."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            theme_file = root / "tools" / "visual-engine" / "themes" / "project-theme.json"
            theme_file.write_text(
                theme_file.read_text(encoding="utf-8").replace(
                    '"backgroundColor"', '"attackerColor"', 1),
                encoding="utf-8",
            )
            result = checks.check_theme_build_matches_source(self._ctx(root))
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("project-theme.json", result.evidence)

    @unittest.skipUnless(shutil.which("node"), "requires node on PATH")
    def test_a_deleted_theme_file_is_caught_too(self) -> None:
        """The opposite edge: the build still wants to produce a file that is no longer committed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            (root / "tools" / "visual-engine" / "themes" / "print-theme.json").unlink()
            result = checks.check_theme_build_matches_source(self._ctx(root))
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("print-theme.json", result.evidence)


class ProjectIndexIsNotVacuous(unittest.TestCase):
    """SUITE-03 printed `"project index resolves"` over a registry of ONE row, and would have
    printed exactly the same line over ZERO — `verify` exits 0 on an empty index because every row
    it holds resolves, and it holds none. That is the vacuity `test_no_guard_passes_vacuously`
    exists to refuse, in the package that owns that test.

    These drive the REAL check against the REAL CLI, with the index relocated by the engine's own
    `ENGINE_PROJECT_INDEX_PATH`. Relocating it is the point: the first version of the fix read
    `ctx.root / "PROJECT_INDEX.json"` by hand while `verify` resolved the override, so the count
    and the titles came from two different files.
    """

    def setUp(self) -> None:
        self._saved = os.environ.get("ENGINE_PROJECT_INDEX_PATH")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self._saved is None:
            os.environ.pop("ENGINE_PROJECT_INDEX_PATH", None)
        else:
            os.environ["ENGINE_PROJECT_INDEX_PATH"] = self._saved

    @staticmethod
    def _ctx() -> checks.Ctx:
        # ctx.root stays the real repository: the check shells out to `python3 -m
        # tools.project_index.cli`, and the dashboard subcommand refuses an --out path outside it.
        return checks.Ctx(root=_REPO, doc_system=_REPO / "docs" / "design" / "doc-system",
                          full=False)

    def _index(self, tmp: Path, artifacts: list[dict[str, object]]) -> None:
        (tmp / "index.json").write_text(json.dumps({"artifacts": artifacts}), encoding="utf-8")
        os.environ["ENGINE_PROJECT_INDEX_PATH"] = str(tmp / "index.json")

    @staticmethod
    def _row(aid: str, path: str, title: str) -> dict[str, object]:
        return {"id": aid, "path": path, "type": "document", "title": title, "section": "",
                "summary": "", "tags": [], "status": "final", "created": "", "updated": "",
                "engine": ""}

    def test_a_populated_index_passes_and_the_count_is_in_the_line(self) -> None:
        """Positive control, and the ESCAPING edge in the same fixture: `dashboard.py` writes every
        cell through `html.escape`, so a title carrying `&` appears in the page as `&amp;`.
        Comparing the raw title reports a rendered row as 'silently omitted' — a false red on the
        first artifact anyone registers with an ampersand in its name."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "one.md").write_text("x\n", encoding="utf-8")
            (tmp / "two.md").write_text("y\n", encoding="utf-8")
            self._index(tmp, [self._row("a1", "one.md", "Themes & Tokens"),
                              self._row("a2", "two.md", "Second Row")])
            result = checks.check_project_index(self._ctx())
        self.assertIs(result.status, Status.PASS, result.evidence)
        self.assertIn("all 2 registered artifact(s)", result.summary)
        self.assertIn("not a coverage measure", result.summary)

    def test_an_EMPTY_index_is_a_hard_failure_not_a_green_line(self) -> None:
        """THE COUNTER-EXAMPLE. `verify` exits 0 and prints `0 artifact(s) registered`; the old
        check turned that into `project index resolves`."""
        with tempfile.TemporaryDirectory() as td:
            self._index(Path(td), [])
            result = checks.check_project_index(self._ctx())
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("registers no artifacts", result.summary)

    def test_a_row_pointing_at_a_file_that_is_gone_still_fails(self) -> None:
        """The pre-existing resolution guarantee must survive the rewrite: a non-empty index whose
        row does not resolve is still red, and for the `verify` reason, not the count reason."""
        with tempfile.TemporaryDirectory() as td:
            self._index(Path(td), [self._row("ghost", "nowhere.md", "Ghost")])
            result = checks.check_project_index(self._ctx())
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("verify failed", result.summary)


class HarnessCleansUpEverythingItCreates(unittest.TestCase):
    """`hook_attacks.sh` set two EXIT traps — `rm -rf "$ROOT"` at the top and `rm -f "$LAST_OUT"`
    forty lines down — and bash keeps only the LAST trap per signal, so the 13 MB lab (`repo/`,
    `remote.git`, `peer`, `other`, `fakebin`, `quietbin`) was leaked into `/var/folders` on every
    run of a harness whose job is to run ~20 pushes in a row.

    The assertion is DERIVED, not a literal: every variable this script assigns from `mktemp` must
    be named by the single EXIT trap. Adding a seventh temporary without extending the handler
    turns this red — which is the edge the one-line fix opened, and the reason a "there is exactly
    one trap" assertion alone would not have been enough.
    """

    _SCRIPT = _REPO / "tools" / "tests" / "hook_attacks.sh"
    _TRAP_RE = re.compile(r"^\s*trap\s+'([^']*)'\s+EXIT\s*$", re.MULTILINE)
    _MKTEMP_RE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)=\"?\$\(mktemp\b", re.MULTILINE)

    def test_bash_really_does_keep_only_the_last_trap(self) -> None:
        """The premise, executed rather than asserted from memory: two EXIT traps, one survivor."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            first, second = tmp / "first", tmp / "second"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")
            script = (f"trap 'rm -f {first}' EXIT\n"
                      f"trap 'rm -f {second}' EXIT\n"
                      "exit 0\n")
            subprocess.run(["bash", "-c", script], check=True, timeout=60, capture_output=True)
            self.assertTrue(first.exists(), "the FIRST trap should have been clobbered")
            self.assertFalse(second.exists(), "the LAST trap should have fired")

    def test_the_harness_has_exactly_one_exit_trap(self) -> None:
        traps = self._TRAP_RE.findall(self._SCRIPT.read_text(encoding="utf-8"))
        self.assertEqual(len(traps), 1, f"expected one EXIT trap, found {len(traps)}: {traps}")

    def test_that_one_trap_names_every_mktemp_the_script_makes(self) -> None:
        source = self._SCRIPT.read_text(encoding="utf-8")
        traps = self._TRAP_RE.findall(source)
        self.assertEqual(len(traps), 1)
        made = set(self._MKTEMP_RE.findall(source))
        self.assertTrue(made, "found no mktemp assignments — re-aim this probe")
        unswept = sorted(v for v in made if f'"${v}"' not in traps[0])
        self.assertEqual(unswept, [],
                         f"{unswept} are created with mktemp but not removed by the EXIT trap "
                         f"({traps[0]!r})")


class HarnessMintsItsOwnProbeMarker(unittest.TestCase):
    """The header documents `bash tools/tests/hook_attacks.sh`, and until this fix that invocation
    did not terminate: only `tools.health` minted the nesting marker that suppresses `STRUCT-04`'s
    ~72 s hook probe, so every one of the ~20 lab pushes re-ran it. Measured at HEAD,
    `timeout 600 bash tools/tests/hook_attacks.sh` reached 7 of 21 verdicts and was killed; with
    the harness minting its own marker the same 21 verdicts complete in about 90 s.

    These execute the REAL minting block, extracted from the script between its two sentinel
    comments — the probe belongs in the artifact the gate certifies, not in a paraphrase of it.
    """

    _SCRIPT = _REPO / "tools" / "tests" / "hook_attacks.sh"

    @classmethod
    def _mint_block(cls) -> str:
        source = cls._SCRIPT.read_text(encoding="utf-8")
        try:
            body = source.split("# >>> probe-marker mint\n", 1)[1]
            return body.split("# <<< probe-marker mint", 1)[0]
        except IndexError:  # pragma: no cover - the assertion below reports it
            return ""

    def _run_block(self, env_extra: dict[str, str], probe_dir: Path) -> dict[str, str]:
        """Run the extracted block and return the two variables it exports."""
        block = self._mint_block()
        self.assertIn("ENGINE_HOOK_PROBE_MARKER", block, "the mint sentinels moved")
        env = dict(os.environ)
        env.pop("ENGINE_IN_HOOK_PROBE", None)
        env.pop("ENGINE_HOOK_PROBE_MARKER", None)
        env["PROBE_DIR"] = str(probe_dir)
        env.update(env_extra)
        script = block + '\nprintf "%s\\n%s\\n" "${ENGINE_IN_HOOK_PROBE:-}" "${ENGINE_HOOK_PROBE_MARKER:-}"\n'
        out = subprocess.run(["bash", "-c", script], env=env, check=True, timeout=60,
                             capture_output=True, text=True).stdout.splitlines()
        return {"ENGINE_IN_HOOK_PROBE": out[0], "ENGINE_HOOK_PROBE_MARKER": out[1]}

    def test_the_documented_invocation_is_named_in_the_header(self) -> None:
        head = "\n".join(self._SCRIPT.read_text(encoding="utf-8").splitlines()[:40])
        self.assertIn("bash tools/tests/hook_attacks.sh", head)
        self.assertIn("python3 -m tools.health --full", head)

    def test_a_bare_run_mints_a_marker_the_health_checks_actually_honour(self) -> None:
        """`checks._inside_hook_probe()` is the consumer; it is what must say yes."""
        with tempfile.TemporaryDirectory() as td:
            probe_dir = Path(td)
            minted = self._run_block({}, probe_dir)
            self.assertTrue(minted["ENGINE_IN_HOOK_PROBE"], "no token was minted")
            self.assertTrue(Path(minted["ENGINE_HOOK_PROBE_MARKER"]).is_file())
            with unittest.mock.patch.dict(os.environ, minted, clear=False):
                self.assertTrue(checks._inside_hook_probe())

    def test_an_inherited_marker_is_never_clobbered(self) -> None:
        """SUITE-06 mints the marker and owns its lifetime; re-minting inside would point the
        variable at a file the outer run does not control and cannot clean up."""
        with tempfile.TemporaryDirectory() as td:
            probe_dir = Path(td)
            outer = probe_dir / "outer.marker"
            outer.write_text("outer-token", encoding="utf-8")
            minted = self._run_block(
                {"ENGINE_IN_HOOK_PROBE": "outer-token",
                 "ENGINE_HOOK_PROBE_MARKER": str(outer)}, probe_dir)
        self.assertEqual(minted["ENGINE_HOOK_PROBE_MARKER"], str(outer))
        self.assertEqual(minted["ENGINE_IN_HOOK_PROBE"], "outer-token")

    def test_a_stale_exported_variable_still_does_not_suppress_anything(self) -> None:
        """The marker is a token backed by a FILE for exactly this reason: an operator with
        `ENGINE_IN_HOOK_PROBE` left over in a shell must not silently switch a gate off."""
        with unittest.mock.patch.dict(
                os.environ,
                {"ENGINE_IN_HOOK_PROBE": "1", "ENGINE_HOOK_PROBE_MARKER": "/nonexistent/x.marker"},
                clear=False):
            self.assertFalse(checks._inside_hook_probe())



if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TimeoutIsNotATestFailure(unittest.TestCase):
    """`OG-212` — `_run` collapsed three different failures into one exit code.

    Measured 2026-08-29: an unrelated project put the machine at a load average of 36, the
    counter-example suite used its usual ~407 s of CPU but 783 s of wall-clock, and `SUITE-05`
    reported *"python counter-examples FAILED"*. **The suite was green.** Because the pre-push hook
    runs health, that false red blocks every push, and the wording sends the reader looking for a
    broken test instead of at the machine.

    `LESSONS.md` L-25: an environment fact must be NAMED, not folded into a verdict. The verdict
    stays FAIL — a timeout can also be a real hang — but the cause is now distinguishable.
    """

    def test_timeout_and_unlaunchable_do_not_share_an_exit_code(self) -> None:
        """The root. While these were both `127`, no caller could tell them apart."""
        timed_out, message = checks._run(["sleep", "3"], Path("."), timeout=1)
        self.assertEqual(timed_out, checks._EXIT_TIMEOUT)
        self.assertIn("TimeoutExpired", message)

        unlaunchable, _ = checks._run(["no-such-binary-xyz-9f2"], Path("."), timeout=10)
        self.assertEqual(unlaunchable, checks._EXIT_UNLAUNCHABLE)

        self.assertNotEqual(
            checks._EXIT_TIMEOUT, checks._EXIT_UNLAUNCHABLE,
            "collapsing these back into one code re-creates OG-212",
        )

    def test_a_timeout_is_worded_as_a_timeout_and_still_fails(self) -> None:
        """Both halves matter: the wording must name the cause, and the verdict must stay FAIL.

        Pure, so it costs nothing — a probe that had to wait out a real 600-second timeout to test
        this wording would never be run, and an unrun probe is not a probe.
        """
        result = checks._suite_failure("SUITE-05", "python counter-examples",
                                       checks._EXIT_TIMEOUT, "TimeoutExpired: ...", 600)
        self.assertEqual(result.status, Status.FAIL, "'it did not finish' is not a pass")
        self.assertIn("TIMEOUT", result.summary)
        self.assertNotIn("FAILED", result.summary)

    def test_a_real_test_failure_is_still_worded_as_one(self) -> None:
        """Two-sided: wording everything as a timeout would satisfy the probe above."""
        result = checks._suite_failure("SUITE-05", "python counter-examples", 1, "AssertionError", 600)
        self.assertEqual(result.status, Status.FAIL)
        self.assertIn("FAILED (exit 1)", result.summary)
        self.assertNotIn("TIMEOUT", result.summary)


class TheHardFloorsTrackTheirSuites(unittest.TestCase):
    """The 1.0.0 audit found `_PYTEST_HARD_FLOOR` at 190 against a suite of 575 — a gutting-backstop
    that had drifted to a third of the suite it guards, the exact "a written-down floor is stale the
    moment the suite grows" failure the floor's own comment warns about (it had already happened once
    at 30-vs-71). The DERIVED `ran >= defined` gate stayed sound; the coarse backstop certified a
    suite three-fifths smaller than reality, and nothing forced the ratchet the comment promised.

    This turns "raise the floor when the suite grows" into a gate instead of a hope (`RULES.md`
    Rule 1 — fix the class): each hard floor must sit in `[floor(0.80 * defined), defined]` — high
    enough to be a real backstop, never above what the suite can actually deliver. It was RED at 190
    (below 0.80 * 575) and is GREEN at 500, and it now covers the harness floor for the same reason.
    """

    def test_the_pytest_and_harness_floors_track_their_suites(self) -> None:
        tests_dir = _REPO / "tools" / "tests"
        defined_py = checks._defined_python_tests(tests_dir)
        self.assertGreaterEqual(defined_py, 1, "no python tests found — the count derivation is broken")
        lo_py = int(defined_py * 0.80)
        self.assertGreaterEqual(
            checks._PYTEST_HARD_FLOOR, lo_py,
            f"_PYTEST_HARD_FLOOR={checks._PYTEST_HARD_FLOOR} has drifted below 80% of the {defined_py} "
            f"tests it guards (must be >= {lo_py}) — raise it, the 190-vs-575 drift the audit found",
        )
        self.assertLessEqual(
            checks._PYTEST_HARD_FLOOR, defined_py,
            f"_PYTEST_HARD_FLOOR={checks._PYTEST_HARD_FLOOR} exceeds the {defined_py} tests defined — "
            "an unsatisfiable floor that fails every run",
        )

        harness = _REPO / "tools" / "tests" / "hook_attacks.sh"
        defined_atk = checks._defined_harness_attacks(harness)
        self.assertGreaterEqual(defined_atk, 1, "no harness attacks found — the count derivation is broken")
        lo_atk = int(defined_atk * 0.80)
        self.assertGreaterEqual(
            checks._HARNESS_HARD_FLOOR, lo_atk,
            f"_HARNESS_HARD_FLOOR={checks._HARNESS_HARD_FLOOR} has drifted below 80% of the "
            f"{defined_atk} attacks it guards (must be >= {lo_atk})",
        )
        self.assertLessEqual(
            checks._HARNESS_HARD_FLOOR, defined_atk,
            f"_HARNESS_HARD_FLOOR={checks._HARNESS_HARD_FLOOR} exceeds the {defined_atk} attacks defined",
        )


class ChildProcessesRunTheInterpreterHealthIsRunningOn(unittest.TestCase):
    """`OG-247` — a check must measure the engine, not whatever `python3` PATH resolves to.

    Seven checks shell out to the engine's own modules (`docgen`, `project_index`, the unittest
    suite) and every one of them needs the dependencies in `tools/docgen/requirements.txt`. While
    the child was spawned by NAME, health could run on an interpreter that has them and grade an
    interpreter that does not — and this machine carries both at once
    (`/opt/homebrew/bin/python3` with PyYAML, `/usr/local/bin/python3` without). The failure reads
    as a broken engine and costs the diagnosis: a field trial spent it on the engine rather than on
    the environment.

    The probe puts a hostile `python3` first on PATH. That is not a contrivance — it is the same
    condition as an ordering difference between two real installs, made deterministic.
    """

    def _sabotaged_path(self) -> str:
        shim_dir = Path(tempfile.mkdtemp(prefix="wrong-python3-"))
        self.addCleanup(shutil.rmtree, shim_dir, True)
        shim = shim_dir / "python3"
        shim.write_text(
            "#!/bin/sh\n"
            "echo 'ModuleNotFoundError: this interpreter is not the one health is running on' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)
        return f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"

    def test_no_check_spawns_python_by_name(self) -> None:
        """The class, not the instance (`RULES.md` Rule 1): all seven sites, asserted at once."""
        source = (_REPO / "tools" / "health" / "checks.py").read_text(encoding="utf-8")
        # Report the LINE NUMBERS, never the file: an assertion whose message is the whole module
        # is unreadable at exactly the moment someone needs to read it.
        by_name = [n for n, line in enumerate(source.splitlines(), 1)
                   if '_run(["python3"' in line]
        self.assertEqual(
            by_name, [],
            f"checks.py:{by_name} resolves the child interpreter by name again — "
            "use `_PY` (`sys.executable`)",
        )
        self.assertTrue(checks._PY, "_PY must never resolve empty; a bare name is what this fixes")

    def test_a_hostile_python3_on_PATH_does_not_fail_the_document_build(self) -> None:
        """BUILD-01, the cheapest of the seven, run for real against a poisoned PATH."""
        ctx = checks.Ctx(root=_REPO, doc_system=_REPO / "docs" / "design" / "doc-system",
                         full=False)
        with unittest.mock.patch.dict(os.environ, {"PATH": self._sabotaged_path()}):
            result = checks.check_sample_builds(ctx)
        self.assertNotEqual(
            result.status, Status.FAIL,
            "BUILD-01 graded the wrong interpreter: " + f"{result.summary} :: {result.detail}",
        )


class ChildProcessesKeepTheCallersPythonPath(unittest.TestCase):
    """`OG-247`, second half — a relative `PYTHONPATH` must survive the `cwd` a check imposes.

    Every check launches its child with `cwd` set to the HOST root, which is usually not where
    health was started. `PYTHONPATH=engine` — the shape `CONFIGURATION.md`'s foreign-host route
    produces — then means `<host>/engine` to the child and resolves to nothing. The variable itself
    is inherited; a field trial measured the resulting `ModuleNotFoundError`, diagnosed it as a
    LOST variable, and proposed passing `PYTHONPATH` to every child — a repair that would have
    changed nothing, because it was already being passed.
    """

    def test_a_relative_entry_is_pinned_to_the_directory_the_caller_wrote_it_in(self) -> None:
        with unittest.mock.patch.dict(
            os.environ, {"PYTHONPATH": os.pathsep.join(["engine", "/already/absolute"])}
        ):
            resolved = checks._child_env(None)["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(resolved[0], str(Path("engine").resolve()))
        self.assertEqual(resolved[1], "/already/absolute", "an absolute entry must not be rewritten")

    def test_an_empty_entry_is_left_alone(self) -> None:
        """An empty element asks for the CHILD's cwd. Rewriting it would be inventing intent."""
        with unittest.mock.patch.dict(os.environ, {"PYTHONPATH": os.pathsep.join(["", "engine"])}):
            resolved = checks._child_env(None)["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(resolved[0], "")

    def test_an_absent_pythonpath_is_not_invented(self) -> None:
        """The control: no PYTHONPATH in, no PYTHONPATH out."""
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            self.assertNotIn("PYTHONPATH", checks._child_env(None))

    def test_a_child_really_resolves_the_engine_from_a_relative_entry(self) -> None:
        """End to end, through `_run`, with the cwd moved out from under the relative path."""
        with (tempfile.TemporaryDirectory(prefix="foreign-host-") as td,
              unittest.mock.patch.dict(os.environ, {"PYTHONPATH": _REPO.name})):
            code, out = _run_from_parent(Path(td))
        self.assertEqual(code, 0, out)


def _run_from_parent(host: Path) -> tuple[int, str]:
    """Run `_run` from `_REPO`'s PARENT, so `PYTHONPATH=<repo name>` is the relative form."""
    original = Path.cwd()
    os.chdir(_REPO.parent)
    try:
        return checks._run([checks._PY, "-c", "import tools.health.checks"], host, timeout=120)
    finally:
        os.chdir(original)


class Suite06NamesTheClassOfVerdictThatActuallyFailed(unittest.TestCase):
    """A failed ATTACK and a failed POSITIVE CONTROL mean opposite things.

    An attack failing is a hole in the moat. A control failing — `verdict 0`, asserting a
    LEGITIMATE operation still succeeds — means the lab is broken or health is red for some
    unrelated reason; the pre-push hook runs health, so any red check fails the clean-push
    control. `check_moat_attacks` read two numbers and called every failure
    "N moat attack(s) are no longer refused", pointing at the moat in both cases.

    Measured twice, each costing a full misdiagnosis: once in an earlier host finding, and again
    in a later round where two controls failed because newly added modules were untracked and
    therefore absent from the harness's `git ls-files` lab — reported as two un-refused attacks.
    This suite fails the MESSAGE, not just the status, because the status was never wrong.
    """

    def _result_for(self, result_line: str, exit_code: int = 1) -> CheckResult:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_dir = root / "tools" / "tests"
            script_dir.mkdir(parents=True)
            script = script_dir / "hook_attacks.sh"
            script.write_text(
                "#!/usr/bin/env bash\n"
                + "".join(f"verdict 1 1 'probe {i}'\n" for i in range(23))
                + f"echo '{result_line}'\n"
                + f"exit {exit_code}\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            ctx = checks.Ctx(root=root, doc_system=root / "docs" / "design" / "doc-system",
                             full=True)
            return checks.check_moat_attacks(ctx)

    def test_a_failed_control_does_not_claim_the_moat_was_breached(self) -> None:
        result = self._result_for("RESULT: 22 passed, 1 failed (0 attack, 1 control)")
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("positive control", result.summary)
        self.assertIn("moat is NOT implicated", result.summary)
        self.assertNotIn(
            "no longer refused", result.summary,
            "a failed positive control was reported as a breached moat",
        )

    def test_a_failed_attack_still_says_the_moat_is_breached(self) -> None:
        """The other direction: the fix must not soften a real hole into a lab complaint."""
        result = self._result_for("RESULT: 22 passed, 1 failed (1 attack, 0 control)")
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("moat attack(s) are no longer refused", result.summary)
        self.assertNotIn("positive control", result.summary)

    def test_both_classes_failing_names_both_and_orders_the_fix(self) -> None:
        result = self._result_for("RESULT: 21 passed, 2 failed (1 attack, 1 control)")
        self.assertIn("moat attack(s) are no longer refused", result.summary)
        self.assertIn("positive control(s) failed", result.summary)
        self.assertIn("fix the control first", result.evidence)

    def test_a_harness_error_with_no_failed_verdict_is_not_a_moat_result(self) -> None:
        """The third class: the script died without any verdict failing — an import error, a
        missing tool, a trap after the last case. Reporting that as a moat breach is the same
        misnaming one level further out."""
        result = self._result_for("RESULT: 23 passed, 0 failed (0 attack, 0 control)")
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("every verdict passing", result.summary)
        self.assertNotIn("no longer refused", result.summary)

    def test_an_unclassified_result_line_is_reported_as_drift_not_as_a_breach(self) -> None:
        """Fail-closed on the check's own assumption: a harness older than this check prints no
        breakdown, and GUESSING that the failures were attacks is exactly the defect. Say so."""
        result = self._result_for("RESULT: 22 passed, 1 failed")
        self.assertIs(result.status, Status.FAIL)
        self.assertIn("did not report their class", result.summary)
        self.assertIn("misdiagnosis this check exists to prevent", result.evidence)
        self.assertNotIn("moat attack(s) are no longer refused", result.summary)

    def test_the_real_harness_reports_the_breakdown_this_check_requires(self) -> None:
        """The pairing. The two files must not drift apart silently — if the harness stops
        printing the class, every failure downstream becomes unclassifiable again."""
        text = (_REPO / "tools" / "tests" / "hook_attacks.sh").read_text(encoding="utf-8")
        self.assertIn("%d attack, %d control", text)
        self.assertIn("fail_attack=$((fail_attack+1))", text)
        self.assertIn("fail_control=$((fail_control+1))", text)
