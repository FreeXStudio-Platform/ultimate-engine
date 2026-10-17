"""Counter-examples for the CI cost-control workflow checker's runs-on resolution.

A MEDIUM, verified false positive: `check_workflow_cost_control` flagged a
forbidden `push:` trigger without ever reading a job's `runs-on`, blocking a
self-hosted gates workflow — nine jobs, every one `runs-on: [self-hosted, pool-a, proj-a]`,
zero GitHub-hosted minutes — for doing exactly what the cost-control standard (v2 rule 2:
ban GitHub-hosted push triggers, not self-hosted ones) wants.

The fix makes the checker resolve each job's `runs-on` and flag a forbidden trigger only
when at least one job in the workflow is GitHub-hosted. Every case below is written so
that reverting the fix (i.e. going back to "flag on trigger text alone") turns it red —
that is what makes a test a gate rather than a description (per this engine's own
LESSONS.md L-19: a test that cannot fail proves nothing).

Style follows ``test_docgen.py``: ``unittest.TestCase`` subclasses, ``tempfile`` for
on-disk fixtures, one behavior per test, defect id cited in the docstring.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.docgen import ci_cost_control
from tools.docgen.ci_cost_control import check_workflow_cost_control
from tools.docgen.models import Finding, Severity


def _write_workflow(tmp_dir: Path, body: str, name: str = "workflow.yml") -> Path:
    path = tmp_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def _forbidden_trigger_findings(path: Path) -> list[Finding]:
    """Isolate just the forbidden-auto-trigger findings — the hygiene checks (concurrency,
    permissions, timeout-minutes, workflow_dispatch) are out of scope for this file and must
    not make these assertions brittle against them."""
    return [f for f in check_workflow_cost_control(path) if "forbidden auto-trigger" in f.message]


# ---------------------------------------------------------------------------------------
# Fixture bodies. Each is a complete, independently-readable workflow so a diff between
# cases is visible by eye rather than hidden inside string surgery.
# ---------------------------------------------------------------------------------------

_ALL_SELF_HOSTED_LIST_FORM = """\
name: selfhosted-gates
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: [self-hosted, pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
  fast-check:
    runs-on: [self-hosted, pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo fast-check
"""

_ONE_HOSTED_JOB = """\
name: mixed-gates
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: [self-hosted, pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
  fast-check:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: echo fast-check
"""

_MATRIX_RUNS_ON = """\
name: matrix-gates
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: [self-hosted, pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
  fast-check:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest]
    timeout-minutes: 10
    steps:
      - run: echo fast-check
"""

_MATRIX_RUNS_ON_INPUT_EXPR = """\
name: input-expr-gates
on:
  push:
    branches-ignore: [main]
  workflow_dispatch:
    inputs:
      runner:
        type: string
        default: "ubuntu-latest"
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  fast-check:
    runs-on: ${{ inputs.runner }}
    timeout-minutes: 10
    steps:
      - run: echo fast-check
"""

_MISSING_RUNS_ON = """\
name: missing-runs-on
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: [self-hosted, pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
  fast-check:
    timeout-minutes: 10
    steps:
      - run: echo fast-check
"""

_REUSABLE_WORKFLOW_JOB = """\
name: reusable-job
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: [self-hosted, pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
  reuse:
    uses: ./.github/workflows/other.yml
    secrets: inherit
"""

_SCALAR_SELF_HOSTED = """\
name: scalar-self-hosted
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: self-hosted
    timeout-minutes: 10
    steps:
      - run: echo scan
"""

_NO_PUSH_TRIGGER = """\
name: no-push
on:
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: echo scan
"""

_MAPPING_FORM_SELF_HOSTED = """\
name: mapping-self-hosted
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on:
      group: pool-a-group
      labels: [self-hosted, pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
"""

_MAPPING_FORM_GROUP_ONLY = """\
name: mapping-group-only
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on:
      group: pool-a-group
    timeout-minutes: 10
    steps:
      - run: echo scan
"""

_CUSTOM_LABEL_ONLY_NO_SELF_HOSTED = """\
name: custom-label-only
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: [pool-a, proj-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
"""

_CASE_AND_WHITESPACE_INSENSITIVE_LABEL = """\
name: case-insensitive-label
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs:
  scan:
    runs-on: ["  Self-Hosted  ", pool-a]
    timeout-minutes: 10
    steps:
      - run: echo scan
"""

_EMPTY_JOBS_BLOCK = """\
name: empty-jobs
on:
  push:
    branches-ignore: [main]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: g-${{ github.ref }}
  cancel-in-progress: true
jobs: {}
"""


class ForbiddenTriggerRespectsRunsOn(unittest.TestCase):
    """The checker must resolve `runs-on` (scalar / list / group+labels mapping) before
    deciding a `push:` trigger is a cost-control violation, and must fail CLOSED (treat as
    GitHub-hosted, i.e. still flag) on anything it cannot positively resolve."""

    def test_all_jobs_self_hosted_list_form_is_clean(self) -> None:
        """(a) clean: every job `runs-on: [self-hosted, pool-a, proj-a]` -> no finding."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _ALL_SELF_HOSTED_LIST_FORM)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(findings, [], f"unexpected forbidden-trigger finding(s): {findings}")

    def test_one_hosted_job_is_flagged(self) -> None:
        """(b) flagged: same shape, one job's `runs-on` switched to `ubuntu-latest`."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _ONE_HOSTED_JOB)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)
            self.assertIs(findings[0].severity, Severity.HIGH)
            self.assertIn("push", findings[0].message)

    def test_matrix_expression_runs_on_fails_closed(self) -> None:
        """(c) flagged, fail-closed: `runs-on: ${{ matrix.os }}` cannot be resolved statically,
        so it must be treated as GitHub-hosted rather than silently passed."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _MATRIX_RUNS_ON)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)

    def test_input_expression_runs_on_fails_closed(self) -> None:
        """Same fail-closed contract for a `${{ inputs.* }}` expression, not just `matrix.*`."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _MATRIX_RUNS_ON_INPUT_EXPR)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)

    def test_missing_runs_on_fails_closed(self) -> None:
        """(d) flagged, fail-closed: a job with no `runs-on` key at all."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _MISSING_RUNS_ON)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)

    def test_reusable_workflow_job_fails_closed(self) -> None:
        """(d) flagged, fail-closed: a `uses:` reusable-workflow job has no runner of its own
        and must not be silently treated as self-hosted."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _REUSABLE_WORKFLOW_JOB)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)

    def test_scalar_self_hosted_form_is_clean(self) -> None:
        """(e) the bare scalar `runs-on: self-hosted` resolves to self-hosted -> clean."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _SCALAR_SELF_HOSTED)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(findings, [])

    def test_no_push_trigger_is_unaffected_hosted_or_not(self) -> None:
        """(f) a workflow with no `push:` trigger at all never produces a forbidden-trigger
        finding, regardless of what `runs-on` says -- this exercises the trigger gate, not
        the runs-on gate, and must stay true either way the runs-on logic goes."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _NO_PUSH_TRIGGER)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(findings, [])

    def test_mapping_form_group_and_labels_self_hosted_is_clean(self) -> None:
        """GitHub's `runs-on: {group: ..., labels: [...]}` mapping form must be treated the
        same as the list form: a `self-hosted` entry under `labels:` is clean."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _MAPPING_FORM_SELF_HOSTED)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(findings, [])

    def test_mapping_form_group_only_fails_closed(self) -> None:
        """A `runs-on: {group: ...}` with NO `labels:` at all cannot be positively resolved to
        self-hosted -- a runner group is a routing construct, not itself the `self-hosted`
        label -- so it must fail closed (flagged), not be inferred clean."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _MAPPING_FORM_GROUP_ONLY)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)

    def test_custom_label_alone_is_not_self_hosted(self) -> None:
        """A custom label like `pool-a` with no literal `self-hosted` entry must NOT be inferred
        as self-hosted -- GitHub's own contract is the `self-hosted` label, never a house
        label. `runs-on: [pool-a, proj-a]` (no `self-hosted`) must still flag."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _CUSTOM_LABEL_ONLY_NO_SELF_HOSTED)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)

    def test_self_hosted_label_matched_case_and_whitespace_insensitively(self) -> None:
        """`self-hosted` detection compares case-insensitively after stripping whitespace, so
        `"  Self-Hosted  "` still counts."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _CASE_AND_WHITESPACE_INSENSITIVE_LABEL)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(findings, [])

    def test_empty_jobs_block_fails_closed(self) -> None:
        """An empty `jobs: {}` block (or a missing one) has nothing to positively resolve to
        self-hosted, so a forbidden trigger on it must still flag rather than pass by
        default -- the single most important property this fix must hold (never `except:
        return safe`)."""
        with tempfile.TemporaryDirectory() as td:
            path = _write_workflow(Path(td), _EMPTY_JOBS_BLOCK)
            findings = _forbidden_trigger_findings(path)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].blocking)


if __name__ == "__main__":  # pragma: no cover - direct-run convenience
    unittest.main()


class SelfReferentialRunsOnIsUnresolvableNotACrash(unittest.TestCase):
    """A YAML alias can make ``runs-on`` refer to itself; that must FLAG, never raise.

    ``runs-on: &a {labels: *a}`` is a self-referential object once PyYAML constructs it, and the
    mapping branch of ``_resolve_runs_on_labels`` recurses. Unbounded, that raised
    ``RecursionError`` — which fails safe (it crashes rather than passing something unsafe) but is
    still not a gate RESULT. The bound turns it into the ordinary unresolvable verdict.
    """

    def test_a_self_referential_runs_on_resolves_to_unresolvable(self) -> None:
        runs_on: dict[str, object] = {}
        runs_on["labels"] = runs_on
        self.assertIs(runs_on["labels"], runs_on, "fixture is not actually self-referential")
        self.assertIsNone(
            ci_cost_control._resolve_runs_on_labels(runs_on),
            "a self-referential runs-on must be UNRESOLVABLE (None), not resolved and not raised",
        )

    def test_a_self_referential_job_is_treated_as_github_hosted(self) -> None:
        runs_on: dict[str, object] = {}
        runs_on["labels"] = runs_on
        self.assertFalse(
            ci_cost_control._job_is_self_hosted({"runs-on": runs_on}),
            "unresolvable must fail CLOSED — treated as GitHub-hosted, therefore flagged",
        )

    def test_deep_but_finite_nesting_is_also_unresolvable_rather_than_raising(self) -> None:
        """Beyond the bound the answer is 'cannot resolve', not a crash and not a guess."""
        nested: object = ["self-hosted"]
        for _ in range(ci_cost_control._RUNS_ON_MAX_DEPTH + 3):
            nested = {"labels": nested}
        self.assertIsNone(ci_cost_control._resolve_runs_on_labels(nested))

