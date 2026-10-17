"""`SUITE-04` — the lint/type ceiling — proven, `OG-177`.

**Why this file exists.** A Pass-8 verifier mutation-tested the retained counter-examples and found
`check_lint_baseline` had **none**: the whole check could be replaced with an unconditional PASS and
all 196 tests stayed green. It also found three ways past it, each fixed and each probed here:

* `OG-174` — the ceiling was an uncompared number in an editable JSON. Raising `max_errors` turned a
  real error green in one edit, invisible in review as a "baseline update".
* `OG-175` — `invocations` is data the guard executes verbatim. Narrowing its scope by one path
  segment keeps the headline `0/22` intact while deleting most of the analysed surface.
* `OG-176` — only the ruff arm had a clean-output case, so driving mypy `--strict` to ZERO — the
  destination the baseline's own "may only go DOWN" contract points at — turned the check RED and
  reported it as "baseline exceeded".

These probe the check's LOGIC against synthetic baselines rather than running `uvx`, so they are
fast and deterministic; `SUITE-04` itself does the real measurement.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.health import checks
from tools.health.model import Status


class LintCeilingCannotBeLoosenedByEditingTheBaseline(unittest.TestCase):
    """`OG-174` — the ceiling has a ceiling, and it lives in code."""

    def _ctx_with_baseline(
        self, ceilings: dict[str, int], invocations: dict[str, str] | None = None
    ) -> checks.Ctx:
        tmp = tempfile.TemporaryDirectory(prefix="suite04-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "tools" / "health").mkdir(parents=True)
        (root / "tools" / "health" / "lint_baseline.json").write_text(
            json.dumps(
                {
                    "invocations": invocations
                    or {"ruff": "uvx ruff check tools/", "mypy": "uvx mypy --strict tools/"},
                    "max_errors": ceilings,
                }
            ),
            encoding="utf-8",
        )
        return checks.Ctx(root=root, doc_system=root / "docs", full=True)

    def test_a_raised_ceiling_is_refused(self) -> None:
        """The measured half is irrelevant here — declaring the higher bound is itself the defect."""
        for key, raised in (("ruff", 5), ("mypy_strict", 999)):
            with self.subTest(key=key):
                ceilings = dict(checks._LINT_HARD_CEILING)
                ceilings[key] = raised
                result = self._ctx_with_baseline(ceilings)
                got = checks.check_lint_baseline(result)
                self.assertEqual(got.status, Status.FAIL, str(got.detail))
                self.assertIn("may only go DOWN", str(got.detail))

    def test_a_lowered_ceiling_is_accepted(self) -> None:
        """Two-sided: the contract is "may only go DOWN", so down must be allowed."""
        ceilings = {"ruff": 0, "mypy_strict": 0}
        got = checks.check_lint_baseline(self._ctx_with_baseline(ceilings))
        self.assertNotIn("may only go DOWN", str(got.detail))

    def test_a_narrowed_invocation_is_refused(self) -> None:
        """`OG-175` — the scope-narrowing route that never touches the number a reviewer reads."""
        got = checks.check_lint_baseline(
            self._ctx_with_baseline(
                dict(checks._LINT_HARD_CEILING),
                {"ruff": "uvx ruff check tools/lib/", "mypy": "uvx mypy --strict tools/lib/"},
            )
        )
        self.assertEqual(got.status, Status.FAIL, str(got.detail))
        self.assertIn("does not analyse tools/", str(got.detail))


class BothToolArmsAcceptACleanRun(unittest.TestCase):
    """`OG-176` — reaching the goal must not be reported as breaking the rule."""

    def test_the_check_recognises_each_tool_s_clean_output(self) -> None:
        import inspect

        source = inspect.getsource(checks.check_lint_baseline)
        for marker in ("All checks passed", "Success: no issues found"):
            with self.subTest(marker=marker):
                self.assertIn(
                    marker, source,
                    f"{marker!r} is not recognised, so a tool reporting zero errors would be read "
                    "as an unparseable output and fail the check",
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
