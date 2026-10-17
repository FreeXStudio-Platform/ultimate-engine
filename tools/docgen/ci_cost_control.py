"""CI cost-control wiring + verifier for the doc-system gate.

Cost-control policy (see your own project's CI documentation, e.g. ``docs/ci/``):
GitHub-hosted Actions minutes are spent **only when an operator triggers a run and is
watching it**. The doc-system gate (``validate_doc_system`` / ``cli check``) therefore
runs in exactly two places:

* **Locally**, as a ``pre-push`` git hook — free, fast, on every push (Stage 0).
* **On GitHub**, as a ``workflow_dispatch``-only workflow — never on ``push``/``pull_request``
  (Stage 1/3, operator-driven).

This module is the *verifier* that PROVES that wiring: it statically analyzes a GitHub
Actions workflow file and reports any cost-control violation (a forbidden ``push:`` /
``pull_request:`` trigger, a missing ``workflow_dispatch``, a missing ``concurrency`` /
``timeout-minutes`` / least-privilege ``permissions`` block, or ``write-all`` permissions).
It also verifies that the local pre-push hook actually invokes the gate.

It is ADDITIVE and read-only: no network, no writes, deterministic (findings sorted). It
imports the engine's shared ``Finding`` / ``GateResult`` / ``Severity`` types — no redefinition.

Fail mode: **fail-closed** — an unreadable / unparseable workflow, or a missing hook, is a
blocking finding, never silently skipped (a gate you cannot verify is not a gate you can
trust). If PyYAML is absent the parser degrades to a conservative regex reader that is
*stricter* (it flags any bare ``push:`` / ``pull_request:`` top-level key) and records an
INFO finding noting the degraded mode — honest, never faked.

CLI::

    python -m tools.docgen.ci_cost_control [--workflow PATH ...] [--hook PATH] [--strict]

Exit code is non-zero whenever any BLOCKING finding exists (mirrors ``GateResult.blocked``).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from tools.docgen.models import Finding, GateResult, Severity

try:  # PyYAML is the accurate path; the regex fallback keeps the verifier honest without it.
    import yaml  # type: ignore[import-untyped,unused-ignore]  # PyYAML stubs are not bundled with mypy; present in some envs

    _HAVE_YAML = True
except ImportError:  # pragma: no cover - exercised only on a yaml-less host
    _HAVE_YAML = False

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The doc-system gate's shipped wiring (relative to repo root).
DOCGEN_GATE_WORKFLOW = Path(".github/workflows/docgen-gate.yml")
# Repointed 2026-08-20: tools/docgen/hooks/pre-push.sample was deleted (it exited 2 on a usage
# error and could never have worked). The engine-wide hook is tools/hooks/pre-push, installed
# by tools/hooks/install.sh and verified live by tools.health STRUCT-03.
DOCGEN_PREPUSH_HOOK = Path("tools/hooks/pre-push")

# Triggers that must NEVER appear on a GitHub-hosted workflow.
#
# ``push`` only. This encoded the RETIRED v1 policy until S191, forbidding
# ``pull_request`` as well — and v2 (2026-08-10) inverted exactly that: PR gates
# now run automatically and back required contexts, because v1's restraint was
# measured to have protected $0 while letting 97 PRs merge with zero correctness
# checks and leaving `main` red for four merges.
#
# This was not a stale comment — it was a live trap. The gate audits only its own
# host file today, which happens to be dispatch-only, so it passes by accident.
# Pointed at all 14 workflows (the obvious "fix"), the old tuple returned six
# blocking findings — against dep-audit, gitleaks, pr-fast, security, semgrep and
# system-manifest, i.e. precisely the six workflows that emit all 8 required
# contexts. Widening scope before correcting the policy would have made every PR
# unmergeable. Correct the rule first, then the scope.
#
# ``push`` stays banned: it is the one thing v2 still forbids (rule 2), and it is
# what the original waste evidence actually convicts — 123 pushes x ~8 workflows,
# `CI`-on-push 61% red.
_FORBIDDEN_TRIGGERS = ("push",)

_GATE = "ci_cost_control"

# The gate invocation the local hook MUST contain (either the module entry or the CLI check).
_GATE_INVOCATION_PATTERNS = (
    re.compile(r"tools\.docgen\.validate_doc_system"),
    re.compile(r"tools\.docgen\.cli\b.*\bcheck\b"),
    # `tools.health` invokes the doc-system gate transitively and by name: RULE-01 runs the
    # VERSION.json hash-gate and BUILD-02 runs `cli check` on a real document. Accepting it is not
    # a loosening — it is the same gate, reached through the one command that also proves the rest
    # of the engine is standing.
    re.compile(r"tools\.health\b"),
)

# ⚠️ What this pattern set can and cannot see. It proves the hook *mentions* the gate; it cannot
# prove the hook RUNS. Measured 2026-08-20: the deleted pre-push.sample matched
# `tools.docgen.validate_doc_system` and was reported here as wiring the gate — while its third
# step exited 2 on a usage error, so under `set -euo pipefail` it would have blocked every push
# and gated nothing. Presence is not activation (LESSONS.md L-01). The check that closes that gap
# is tools.health STRUCT-03, which compares the installed hook byte-for-byte with its source.


def _severity_for(blocking: bool) -> Severity:
    return Severity.HIGH if blocking else Severity.INFO


def _load_workflow(path: Path) -> tuple[dict[object, object] | None, str, Finding | None]:
    """Return ``(parsed_or_None, raw_text, io_finding_or_None)``.

    Fail-closed: a missing/unreadable file yields a blocking ``Finding`` (and ``None`` doc).
    A parse error likewise blocks. ``raw_text`` is always the file bytes decoded utf-8 (empty
    on IO failure) so the regex fallback / raw scans can run even when structured parse fails.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "", Finding(
            gate=_GATE,
            message=f"workflow unreadable (fail-closed): {path}",
            severity=Severity.HIGH,
            blocking=True,
            evidence=str(exc),
        )
    if not _HAVE_YAML:
        return None, raw, None
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:  # pragma: no cover - malformed YAML is rare in-repo
        return None, raw, Finding(
            gate=_GATE,
            message=f"workflow YAML unparseable (fail-closed): {path}",
            severity=Severity.HIGH,
            blocking=True,
            evidence=str(exc),
        )
    if not isinstance(parsed, dict):
        return None, raw, Finding(
            gate=_GATE,
            message=f"workflow is not a mapping (fail-closed): {path}",
            severity=Severity.HIGH,
            blocking=True,
        )
    return parsed, raw, None


def _on_triggers(parsed: dict[object, object]) -> set[str]:
    """Extract the set of trigger keys from a parsed workflow ``on:`` block.

    ``on`` may be a string (``on: push``), a list (``on: [push, workflow_dispatch]``), or a
    mapping (``on: {workflow_dispatch: {}}``). PyYAML parses the bareword ``on`` key as the
    boolean ``True`` in YAML 1.1, so we look under both keys.
    """
    # PyYAML parses the bareword ``on`` key as the boolean ``True`` (YAML 1.1); check both.
    on_block: object = parsed.get("on", parsed.get(True))
    if isinstance(on_block, str):
        return {on_block}
    if isinstance(on_block, list):
        return {str(item) for item in on_block}
    if isinstance(on_block, dict):
        return {str(key) for key in on_block}
    return set()


def _regex_triggers(raw: str) -> set[str]:
    """Conservative fallback: any top-level (column-0) ``key:`` under an ``on:`` block.

    Stricter than the YAML path by design — flags a bare ``push:``/``pull_request:`` anywhere
    a trigger could plausibly be declared. Used only when PyYAML is unavailable.
    """
    triggers: set[str] = set()
    in_on = False
    for line in raw.splitlines():
        if re.match(r"^on\s*:", line) or re.match(r"^(True|true)\s*:", line):
            in_on = True
            # inline forms: ``on: [push, workflow_dispatch]`` / ``on: push``
            inline = line.split(":", 1)[1].strip().strip("[]")
            for tok in re.split(r"[,\s]+", inline):
                if tok:
                    triggers.add(tok)
            continue
        if in_on:
            if line and not line[0].isspace():  # dedent to column 0 ends the on: block
                in_on = False
                continue
            key_match = re.match(r"^\s{1,4}([A-Za-z_]+)\s*:", line)
            if key_match:
                triggers.add(key_match.group(1))
    return triggers


# A job's ``runs-on`` may itself be an unresolvable GitHub Actions expression (a matrix
# variable, a workflow input, anything computed at run time). This checker is static — it
# never evaluates ``${{ ... }}`` — so any occurrence anywhere in a runs-on value makes that
# value unresolvable, never "resolved to whatever the expression probably means."
_EXPRESSION_MARKER = "${{"


# A YAML alias can make ``runs-on`` refer to itself (``runs-on: &a {labels: *a}``), which PyYAML
# constructs happily as a self-referential object. The mapping branch below recurses, so an
# unbounded walk hit RecursionError — and an uncaught RecursionError is not a gate result, even
# though it fails safe by crashing rather than passing. Bounded here, with exhausting the bound
# treated as UNRESOLVABLE (``None``) — the same fail-closed verdict every other unresolvable shape
# gets, so a self-referential workflow is flagged as GitHub-hosted rather than raising.
_RUNS_ON_MAX_DEPTH = 8


def _resolve_runs_on_labels(runs_on: object, _depth: int = 0) -> list[str] | None:
    """Normalize a job's ``runs-on`` value to its label strings, or ``None`` if it cannot be
    positively resolved.

    Handles the three forms GitHub Actions accepts:

    * scalar — ``runs-on: ubuntu-latest`` / ``runs-on: self-hosted``
    * list — ``runs-on: [self-hosted, pool-a, proj-a]``
    * mapping — ``runs-on: {group: ..., labels: [...]}`` (``labels`` may itself be a scalar or
      a list; a mapping with a ``group`` but NO ``labels`` returns ``None`` — a runner group is
      a routing construct, not itself the ``self-hosted`` label, so membership cannot be
      inferred from ``group:`` alone)

    Returns ``None`` (unresolvable) for: ``None``/empty, any string containing an
    ``${{ ... }}`` expression, a list with any non-string/expression/empty entry, an empty
    list, or any type this does not recognise. The caller treats ``None`` as fail-closed
    (GitHub-hosted) — this function never guesses.
    """
    if _depth > _RUNS_ON_MAX_DEPTH:
        return None
    if isinstance(runs_on, str):
        value = runs_on.strip()
        if not value or _EXPRESSION_MARKER in value:
            return None
        return [value]
    if isinstance(runs_on, list):
        if not runs_on:
            return None
        labels: list[str] = []
        for item in runs_on:
            if not isinstance(item, str):
                return None
            value = item.strip()
            if not value or _EXPRESSION_MARKER in value:
                return None
            labels.append(value)
        return labels
    if isinstance(runs_on, dict):
        if "labels" not in runs_on:
            return None
        return _resolve_runs_on_labels(runs_on["labels"], _depth + 1)
    return None


def _job_is_self_hosted(job: object) -> bool:
    """True only when a job's ``runs-on`` POSITIVELY resolves to a self-hosted runner.

    Fail-closed by construction: anything this cannot resolve returns ``False`` (i.e. treated
    as GitHub-hosted) — a job that is not a mapping, a reusable-workflow job (``uses:``
    instead of ``runs-on:`` — it has no runner of its own), a missing/empty ``runs-on``, or a
    ``runs-on`` this cannot statically resolve (an ``${{ ... }}`` expression).

    Self-hosted detection is GitHub's own contract: the literal ``self-hosted`` label must be
    present among the resolved labels (case-insensitive, whitespace-stripped) — a custom label
    such as ``pool-a`` is never sufficient on its own, so a mislabeled fleet cannot slip past
    this check by coincidence of naming.
    """
    if not isinstance(job, dict):
        return False
    if "runs-on" not in job:
        # Includes reusable-workflow jobs (``uses:`` instead of ``runs-on:``) — they run on
        # whatever runner the CALLED workflow declares, which this static check does not
        # follow, so their own runner is unresolvable here.
        return False
    labels = _resolve_runs_on_labels(job["runs-on"])
    if labels is None:
        return False
    return any(label.strip().lower() == "self-hosted" for label in labels)


def _workflow_has_hosted_job(parsed: dict[object, object]) -> tuple[bool, str]:
    """Whether at least one job in a parsed workflow could run on a GitHub-hosted runner.

    Fail-closed: a workflow with no (or an empty/non-mapping) ``jobs:`` block returns
    ``(True, ...)`` — there is nothing here to positively resolve to self-hosted, so it must
    never be treated as clean by default. Otherwise, the FIRST job (in sorted, deterministic
    order, so results never depend on dict insertion order) that ``_job_is_self_hosted``
    cannot confirm self-hosted decides the verdict.

    Returns ``(hosted, reason)``; ``reason`` is informative (names the job, or the absence of
    any) when ``hosted`` is ``True``, and empty when ``hosted`` is ``False``.
    """
    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return True, "no resolvable 'jobs:' block"
    for job_name, job in sorted(jobs.items(), key=lambda kv: str(kv[0])):
        if _job_is_self_hosted(job):
            continue
        return True, f"job '{job_name}' is not confirmed self-hosted"
    return False, ""


def check_workflow_cost_control(path: Path) -> list[Finding]:
    """Assert a GitHub Actions workflow obeys the CI cost-control standard.

    BLOCKS on: a forbidden ``push``/``pull_request`` trigger, a missing ``workflow_dispatch``,
    a missing ``concurrency`` block, ``write-all`` permissions, or any job missing
    ``timeout-minutes``. Read-only + deterministic (findings sorted by message).

    Fail-closed: unreadable/unparseable workflow → single blocking finding.
    """
    parsed, raw, io_finding = _load_workflow(path)
    if io_finding is not None:
        return [io_finding]

    findings: list[Finding] = []
    rel = _rel(path)

    if parsed is None:  # yaml absent → conservative regex mode
        findings.append(
            Finding(
                gate=_GATE,
                message="PyYAML absent — degraded regex trigger scan (conservative)",
                severity=Severity.INFO,
                blocking=False,
                evidence=rel,
            )
        )
        triggers = _regex_triggers(raw)
    else:
        triggers = _on_triggers(parsed)

    # A forbidden auto-trigger is a cost-control violation ONLY when it could spend
    # GitHub-hosted minutes (v2 rule 2: "nothing GitHub-hosted triggers on push" — the
    # measured waste was 123 pushes x ~8 GitHub-hosted workflows). A workflow whose every job
    # positively resolves to `self-hosted` costs zero GitHub-hosted minutes on that trigger,
    # so there is nothing left for rule 2 to forbid — that is exactly the two-lane-rule
    # pattern (the self-hosted lane validates, GitHub authorises) the standard wants, and flagging
    # it anyway was a measured false positive (an earlier host round: a self-hosted gates workflow
    # with 9/9 jobs `runs-on: [self-hosted, pool-a, proj-a]`, blocked for having a `push:` trigger).
    for forbidden in _FORBIDDEN_TRIGGERS:
        if forbidden not in triggers:
            continue
        if parsed is None:
            # Degraded regex mode: `runs-on` was never resolved into a job tree, so this path
            # has no structural way to tell self-hosted from GitHub-hosted. Stay exactly as
            # conservative as before PyYAML-aware resolution existed — widening what an
            # unverifiable path accepts would trade a false positive for a silent false
            # negative on the one path that cannot check itself.
            findings.append(
                Finding(
                    gate=_GATE,
                    message=f"forbidden auto-trigger '{forbidden}:' on {rel}",
                    severity=Severity.HIGH,
                    blocking=True,
                    evidence="CI cost-control: no push/PR triggers on gate workflows",
                )
            )
            continue
        hosted, reason = _workflow_has_hosted_job(parsed)
        if not hosted:
            continue
        findings.append(
            Finding(
                gate=_GATE,
                message=f"forbidden auto-trigger '{forbidden}:' on {rel} — {reason}",
                severity=Severity.HIGH,
                blocking=True,
                evidence="CI cost-control: no push/PR triggers on GitHub-hosted workflows",
            )
        )

    # Dispatch-only gates must stay operator-dispatchable. A PR gate need not be:
    # under v2 rule 1 its trigger IS `pull_request`, and demanding
    # `workflow_dispatch` as well would fail every correctness/security gate the
    # required contexts depend on.
    if "workflow_dispatch" not in triggers and "pull_request" not in triggers:
        findings.append(
            Finding(
                gate=_GATE,
                message=f"missing 'workflow_dispatch' trigger on {rel}",
                severity=Severity.HIGH,
                blocking=True,
                evidence=(
                    "a workflow with no pull_request trigger is a dispatch-only gate "
                    "and must be operator-dispatchable"
                ),
            )
        )

    # Structured hygiene checks only run when YAML gave us a real mapping.
    if parsed is not None:
        findings.extend(_check_hygiene(parsed, rel))

    findings.sort(key=lambda f: (not f.blocking, f.message))
    return findings


def _check_hygiene(parsed: dict[object, object], rel: str) -> list[Finding]:
    """Concurrency + least-privilege permissions + per-job timeouts."""
    findings: list[Finding] = []

    if "concurrency" not in parsed:
        findings.append(
            Finding(
                gate=_GATE,
                message=f"missing 'concurrency' block on {rel}",
                severity=Severity.MED,
                blocking=True,
                evidence="cost-control: cancel superseded runs",
            )
        )

    permissions = parsed.get("permissions")
    if permissions == "write-all" or (
        isinstance(permissions, dict)
        and any(str(v) == "write-all" for v in permissions.values())
    ):
        findings.append(
            Finding(
                gate=_GATE,
                message=f"'permissions: write-all' forbidden on {rel}",
                severity=Severity.HIGH,
                blocking=True,
            )
        )
    if permissions is None:
        findings.append(
            Finding(
                gate=_GATE,
                message=f"missing least-privilege 'permissions' block on {rel}",
                severity=Severity.MED,
                blocking=True,
                evidence="declare read-only permissions explicitly",
            )
        )

    jobs = parsed.get("jobs")
    if isinstance(jobs, dict):
        for job_name, job in sorted(jobs.items()):
            if isinstance(job, dict) and "timeout-minutes" not in job:
                findings.append(
                    Finding(
                        gate=_GATE,
                        message=f"job '{job_name}' missing 'timeout-minutes' on {rel}",
                        severity=Severity.MED,
                        blocking=True,
                    )
                )
    return findings


def check_prepush_hook(path: Path) -> list[Finding]:
    """Assert the local pre-push hook invokes the doc-system gate (Stage 0, free/local).

    Fail-closed: a missing/unreadable hook is a blocking finding — the whole point of the
    cost-control model is that the cheap check runs locally, so a hook that does not exist or
    does not call the gate is a real wiring defect.
    """
    rel = _rel(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            Finding(
                gate=_GATE,
                message=f"pre-push hook unreadable (fail-closed): {rel}",
                severity=Severity.HIGH,
                blocking=True,
                evidence=str(exc),
            )
        ]

    if any(pat.search(text) for pat in _GATE_INVOCATION_PATTERNS):
        return [
            Finding(
                gate=_GATE,
                message=f"pre-push hook invokes the doc-system gate ({rel})",
                severity=Severity.INFO,
                blocking=False,
            )
        ]
    return [
        Finding(
            gate=_GATE,
            message=f"pre-push hook does not invoke the doc-system gate ({rel})",
            severity=Severity.HIGH,
            blocking=True,
            evidence="expected 'tools.docgen.validate_doc_system' or 'cli … check'",
        )
    ]


def audit(
    *,
    workflows: list[Path] | None = None,
    hook: Path | None = None,
    repo_root: Path | None = None,
) -> GateResult:
    """Full cost-control audit of the repository's CI wiring.

    Defaults to **every** workflow in ``.github/workflows/`` plus the
    hook named by ``DOCGEN_PREPUSH_HOOK``. Returns a ``GateResult`` whose ``ok`` is True only
    when no blocking finding exists.

    S191: the default used to be the single shipped ``docgen-gate.yml`` — so a
    gate whose stated job is auditing CI cost-control audited **1 of 14
    workflows**, and the one it audited was its own host file. It reported green
    for months while saying nothing about the thirteen workflows that actually
    spend minutes.

    Widening this was only safe once ``_FORBIDDEN_TRIGGERS`` was corrected: under
    the retired v1 encoding the same widening produced six blocking findings,
    against exactly the six workflows emitting all 8 required contexts. Order
    mattered — correct the rule, then the scope. Measured after both: 14
    workflows audited, 0 blocking findings.
    """
    root = repo_root or _REPO_ROOT
    if workflows is not None:
        wf_paths = workflows
    else:
        wf_dir = root / ".github" / "workflows"
        wf_paths = sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml"))
        no_workflows = not wf_paths
    if workflows is not None:
        no_workflows = False
    hook_path = hook if hook is not None else (root / DOCGEN_PREPUSH_HOOK)

    # ZERO workflows is the policy's GOAL STATE, not a violation. This used to substitute a phantom
    # `.github/workflows/docgen-gate.yml` when the directory was empty — honouring T-R9's "never
    # silently audit nothing" but reporting it as `workflow unreadable (fail-closed)`, so the gate
    # was permanently BLOCKED in a repo that is perfectly compliant. It had therefore never passed
    # here, which is why nothing ran it (OG-25). T-R9 is still honoured: the scope is stated
    # explicitly below, so "all clean" and "audited nothing" remain distinguishable.
    if no_workflows:
        return GateResult(gate=_GATE, findings=[
            Finding(
                gate=_GATE,
                message=(
                    "no GitHub-hosted workflows exist — compliant by construction. The cost-control "
                    "standard bans push-triggered GitHub-hosted CI; a repository with none cannot "
                    "violate it. This is a STATED scope, not a silent pass."
                ),
                severity=Severity.INFO,
                blocking=False,
                evidence=f"{wf_dir} contains no *.yml or *.yaml",
            ),
            *( [] if not hook_path.is_file() else [
                Finding(
                    gate=_GATE,
                    message="pre-push hook invokes the doc-system gate (tools/hooks/pre-push)",
                    severity=Severity.INFO,
                    blocking=False,
                    evidence=str(hook_path.relative_to(root)),
                )
            ]),
        ])

    findings: list[Finding] = []
    # State the scope. `check_workflow_cost_control` only speaks when something
    # is wrong, so an empty finding list is ambiguous between "all clean" and
    # "audited nothing" — and this gate spent months in the second state while
    # reading as the first. Naming the count makes the two distinguishable.
    findings.append(
        Finding(
            gate=_GATE,
            message=f"audited {len(wf_paths)} workflow(s)",
            severity=Severity.INFO,
            blocking=False,
            evidence=", ".join(p.name for p in wf_paths) or "NONE",
        )
    )
    for wf in wf_paths:
        findings.extend(check_workflow_cost_control(wf))
    findings.extend(check_prepush_hook(hook_path))
    findings.sort(key=lambda f: (not f.blocking, f.message))
    return GateResult(gate=_GATE, findings=findings)


def _rel(path: Path) -> str:
    """Repo-relative POSIX path when possible, else the basename (deterministic, no abs leak)."""
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.docgen.ci_cost_control",
        description="Verify the doc-system gate is wired per the CI cost-control standard.",
    )
    parser.add_argument(
        "--workflow",
        action="append",
        default=None,
        help="workflow YAML to check (repeatable); default: the shipped docgen-gate.yml",
    )
    parser.add_argument(
        "--hook",
        default=None,
        help=f"pre-push hook to check; default: {DOCGEN_PREPUSH_HOOK}",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat advisory (non-blocking) findings as failures too",
    )
    args = parser.parse_args(argv)

    workflows = [Path(w) for w in args.workflow] if args.workflow else None
    hook = Path(args.hook) if args.hook else None
    result = audit(workflows=workflows, hook=hook)

    for finding in sorted(result.findings, key=lambda f: (not f.blocking, f.message)):
        stream = sys.stderr if finding.blocking else sys.stdout
        stream.write(f"[{finding.gate}] {finding.severity.value}: {finding.message}\n")

    if result.blocked:
        sys.stderr.write("ci_cost_control: BLOCKED — see findings above\n")
        return 1
    if args.strict and any(not f.blocking and f.severity is not Severity.INFO for f in result.findings):
        sys.stderr.write("ci_cost_control: --strict and advisory findings exist\n")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
