"""Engine health system — one command that answers "is everything actually green?".

The engine's checks were previously scattered across four entry points that nobody ran together
(``visual-engine`` npm test/simulate, ``mermaid-engine`` npm test, ``docgen cli check``,
``project_index verify``), so "the system is healthy" was a claim no single command could produce.

This package is that command. It runs checks in a **deliberate order** — foundation first, so a
broken foundation never produces a confusing cascade of downstream failures:

    1. STRUCTURE    do the files the system depends on exist?
    2. RULE_LAYER   does the governance data parse, and does the hash-gate hold?
    3. CONSISTENCY  does any file contradict another? ("no part lies to another part")
    4. BUILD        does a real document still build end to end?
    5. SUITES       the full test suites (slow; --full only)

**Fail-closed.** A check that raises is a FAIL, never a skip — an error while checking is not
evidence of health. A check that genuinely cannot run in this environment reports SKIP with a
stated cause, and SKIP never counts as PASS.

**Stdlib only** (RULEBOOK L23): no new dependency, works offline, runs from a fresh clone.

Adding a check is a single entry in ``CHECKS`` — see ``tools/health/checks.py``.
"""

from tools import gitenv
from tools.health.model import CheckResult, Status

# A hook run from a linked worktree exports GIT_DIR; the probes and suites below run `git init` in scratch directories (OG-291).
gitenv.scrub()

__all__ = ["CheckResult", "Status"]
