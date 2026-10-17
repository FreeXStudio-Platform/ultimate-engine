"""The corpus checker — `DOC_WRITING_DOCTRINE.md` §5's guard set, pointed at a real corpus.

**What this package is for, in one line:** *every expensive defect is a claim that was checkable and
wasn't checked* (doctrine §0), and roughly two-thirds of them are checkable by a script.

**What it is pointed at.** Not fixtures. `docs/CHARTER.md` purpose 2 makes this repository the
engine's own first corpus, so every guard runs over the tracked Markdown that `git ls-files`
reports. A guard that has only ever been run against three fixtures has been tested, not used.

**How it relates to `tools/health`.** `tools.health` asks *is the engine green?* — structure, rule
layer, build, suites. This package asks *is the corpus true?* — do its claims resolve against the
code and the built output. They overlap deliberately and never duplicate: `docs/plan/PHASE3_OVERLAP.md`
records, guard by guard, which `CONS` check already owns which question, and each guard's docstring
names the check it defers to. Health runs this package as a single check, so there is exactly one
command a session has to remember.

**Three rules every guard here obeys.**

1. *Read real source off disk; never compare a copied literal against itself* (doctrine §5).
2. *Report how much you examined.* `GuardResult.checked` and a declared floor — a clean guard that
   examined nothing is a FAILURE, not a pass (`LESSONS.md` L-19).
3. *Ship the input that makes you fail.* Every guard's counter-example lives in
   `tools/tests/test_corpus_check.py` and runs on every health run (`docs/process/RULES.md` Rule 1).

Stdlib only (RULEBOOK L23).
"""

from tools.corpus_check.model import Finding, GuardResult, Severity, Status

__all__ = ["Finding", "GuardResult", "Severity", "Status"]
