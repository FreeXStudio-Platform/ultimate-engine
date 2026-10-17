"""Health runner + CLI.

    python3 -m tools.health               # fast: structure, rule layer, consistency, build
    python3 -m tools.health --full        # everything, including the npm suites
    python3 -m tools.health --json        # machine-readable report on stdout
    python3 -m tools.health --log PATH    # also write the full JSON report to PATH (overwrites)
    python3 -m tools.health --run-log P   # append-only JSONL history (default: .health/runs.jsonl)
    python3 -m tools.health --no-run-log  # do not append to the history

**Exit code, stated exactly, because this module computes it** (`OG-117`). Exit is 0 when no check
FAILED **and** either nothing was skipped or the run is neither ``--full`` nor ``--strict``. In
other words: a default run is green over SKIPs; ``--full`` and ``--strict`` turn any SKIP into a
failure, for use where "unknown" is unacceptable.

That is `healthy = not failed and (not skipped or not (strict or ctx.full))` — read it there, not
here. This paragraph previously asserted *"A SKIP never counts as a pass"* as an unconditional
property, which is the retired contract and is false of the predicate ten lines below it. `OG-83`
recorded that wording as corrected in two places; this was the third, in the file that OWNS the
exit code, and it was left behind — including its broken grammar ("``--full`` and ``--strict``\n
turns"), which is what a half-applied edit looks like. Measured in a pristine lab: **HEALTHY — 26
passed, 0 failed, 7 skipped, exit 0**.

**Two logs, two questions.** ``--log`` overwrites one full report: *what is true now*. The run log
appends one line per run: *what has been true* — so a check that started failing three runs ago,
or a suite that has been getting slower, is visible at all. It is on by DEFAULT because a log
nobody remembers to switch on records nothing (``OPEN_GATES.md`` OG-14).

Everything except the report itself goes to **stderr**, so ``--json`` stdout stays parseable.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from tools.health.checks import CHECKS, Ctx
from tools.health.model import CheckResult, Stage, Status

_MARK = {Status.PASS: "PASS", Status.FAIL: "FAIL", Status.SKIP: "SKIP"}

# Gitignored: it is this checkout's own history, not a shared artifact. Committing it would
# attribute one machine's runs to every clone.
_RUN_LOG_RELATIVE = Path(".health") / "runs.jsonl"


def _git_state(root: Path) -> tuple[str | None, bool | None]:
    """``(commit sha, working-tree-dirty)`` for the run log, or ``(None, None)`` outside git.

    Never raises and never blocks a health run. An unknown state is recorded as ``null``, never
    guessed: ``"dirty": false`` on a tree we could not inspect is a lie that a later reader would
    treat as evidence — the exact failure this project's registers exist to prevent.
    """

    def _git(*argv: str) -> str | None:
        try:
            # Fixed argv, no shell, no user-supplied input.
            proc = subprocess.run(
                ("git", "-C", str(root), *argv),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            # ValueError covers UnicodeDecodeError from text=True on undecodable git output. It is
            # not an OSError and not a SubprocessError, so without it a branch or path with odd
            # bytes would kill a health run AFTER its verdict had already been printed.
            return None
        return proc.stdout.strip() if proc.returncode == 0 else None

    sha = _git("rev-parse", "HEAD")
    if sha is None:
        return None, None
    status = _git("status", "--porcelain")
    return sha, (bool(status) if status is not None else None)


def _append_run_log(
    path: Path, report: dict[str, object], *, root: Path, duration_s: float
) -> None:
    """Append exactly one JSON line to the append-only run log. Never changes the exit code.

    Failure is **announced on stderr and tolerated**: a full disk must not turn a green engine
    red. Silence would be worse than either — a log that quietly stops writing reopens OG-14
    invisibly, which is how it came to be open in the first place.
    """
    counts_obj = report.get("counts")
    counts: dict[str, object] = counts_obj if isinstance(counts_obj, dict) else {}
    checks_obj = report.get("checks")
    checks: list[object] = checks_obj if isinstance(checks_obj, list) else []

    def _ids(status: str) -> list[str]:
        return [
            str(c["id"])
            for c in checks
            if isinstance(c, dict) and c.get("status") == status and "id" in c
        ]

    commit, dirty = _git_state(root)
    line = {
        "at": report.get("generated_at"),
        "commit": commit,
        "dirty": dirty,
        "full": report.get("full"),
        "strict": report.get("strict"),
        "healthy": report.get("healthy"),
        "duration_s": round(duration_s, 3),
        "total": counts.get("total"),
        "pass": counts.get("pass"),
        "fail": counts.get("fail"),
        "skip": counts.get("skip"),
        "failed_ids": _ids(Status.FAIL.value),
        "skipped_ids": _ids(Status.SKIP.value),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, sort_keys=True) + "\n")
    except OSError as exc:
        sys.stderr.write(f"health: run log NOT written to {path}: {exc}\n")


def run_all(ctx: Ctx) -> list[CheckResult]:
    """Run every check in registry order, in stage order.

    Fail-closed: a check that raises becomes a FAIL carrying the exception. An error while checking
    is never evidence of health.
    """
    results: list[CheckResult] = []
    for fn in CHECKS:
        try:
            results.append(fn(ctx))
        except Exception as exc:  # noqa: BLE001 - a raising check is a failing check, never a skip
            # Recover the DOCUMENTED id and stage from the function's own source. Using
            # `fn.__name__` printed `check_ci_cost_control check raised AttributeError` — a line no
            # register, brief or state document can be grepped for, because the id an operator
            # knows the check by (`STRUCT-05`) never appeared. A failure that cannot be looked up
            # is a failure that gets ignored.
            results.append(
                CheckResult(
                    check_id=_check_id_of(fn),
                    stage=_stage_of(fn),
                    status=Status.FAIL,
                    summary=f"check raised {type(exc).__name__}",
                    evidence=str(exc),
                )
            )
    _flag_duplicate_check_ids(results)
    return results


def _flag_duplicate_check_ids(results: list[CheckResult]) -> None:
    """Two registered checks reporting the SAME ``check_id`` was never detected (`P8-089`).

    Nothing in `run_all` asserted uniqueness before this, and the id is load-bearing well past this
    module: `_report`'s ``checks`` list is keyed by it, the run log's ``failed_ids``/``skipped_ids``
    are built from it, and every document in this corpus that cites a gate cites it by this exact
    string. A second check silently registered under an id already in use would run, report, and
    be indistinguishable from the first one in every consumer that indexes by id — including a
    human grepping for ``STRUCT-09`` and finding two unrelated answers under the same name.

    Mutates ``results`` IN PLACE by inserting a synthetic FAIL, rather than raising: raising here
    would crash the whole run over a registry defect this function exists to REPORT, the same
    "an error is never silent, but must still produce a result" discipline `run_all`'s own
    docstring states for one raising check.
    """
    seen: dict[str, int] = {}
    for r in results:
        seen[r.check_id] = seen.get(r.check_id, 0) + 1
    dupes = sorted(cid for cid, count in seen.items() if count > 1)
    if dupes:
        # Inserted at the FRONT, not appended: `_print_human` groups consecutive results by
        # stage, so appending a `Stage.STRUCTURE` entry after every later stage had already
        # printed would reopen a "STRUCTURE" header at the bottom of the report.
        results.insert(
            0,
            CheckResult(
                check_id="REGISTRY-DUP",
                stage=Stage.STRUCTURE,
                status=Status.FAIL,
                summary=f"{len(dupes)} check id(s) reported by more than one registered check",
                evidence="; ".join(dupes) + " — every consumer keyed by check_id "
                "(the run log, this report, every citation in this corpus) can no longer tell "
                "the colliding checks apart",
                detail=dupes,
            )
        )


# `P8-121`: this used to hardcode the five prefixes in use AT THE TIME
# (`STRUCT|RULE|CONS|BUILD|SUITE`), so a check registered under any other prefix (a probe used to
# reproduce this: `MOAT-01`) fell through to the `fn.__name__` fallback below — reporting
# `check_probe_newprefix check raised RuntimeError` instead of the id an operator would actually
# grep for, exactly the defect this recovery path exists to prevent (see `run_all`'s comment).
# Widened to the same character class `test_refs._ID_RE` uses for a citable id anywhere in this
# corpus (`[A-Z][A-Z0-9]{1,9}-\d{1,3}`, backticked there / quoted here) rather than re-deriving
# the vocabulary from the whole tracked tree on every raised exception — that scan belongs to a
# corpus guard that runs once per health run, not to an exception-recovery path in the hot loop.
_CHECK_ID_RE = re.compile(r'"([A-Z][A-Z0-9]{1,9}-\d{1,3})"')
_STAGE_RE = re.compile(r"Stage\.([A-Z_]+)")


def _check_id_of(fn: object) -> str:
    """The check id a function reports, read from its own source. Falls back to its name."""
    try:
        found = _CHECK_ID_RE.search(inspect.getsource(fn))  # type: ignore[arg-type]
    except (OSError, TypeError):
        found = None
    return found.group(1) if found else str(getattr(fn, "__name__", "unknown"))


def _stage_of(fn: object) -> Stage:
    try:
        found = _STAGE_RE.search(inspect.getsource(fn))  # type: ignore[arg-type]
    except (OSError, TypeError):
        found = None
    if found:
        try:
            return Stage[found.group(1)]
        except KeyError:
            pass
    return Stage.STRUCTURE


def _report(results: list[CheckResult], ctx: Ctx, *, strict: bool) -> dict[str, object]:
    failed = [r for r in results if r.status is Status.FAIL]
    skipped = [r for r in results if r.status is Status.SKIP]
    # A SKIP is an unanswered question. It is tolerable in fast mode, where the npm suites are
    # deliberately not requested — but NOT under --full, whose whole meaning is "run everything":
    # a skip there means the run did not deliver what was asked for. Measured motivation: on a
    # clone with only one of the two npm packages installed, `--full` reported HEALTHY and exit 0
    # while the flagship documented example could not build, and the pre-push moat certified that
    # green. --strict keeps its stronger meaning: fail on a skip in any mode.
    healthy = not failed and (not skipped or not (strict or ctx.full))
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "root": str(ctx.root),
        "full": ctx.full,
        "strict": strict,
        "healthy": healthy,
        "counts": {
            "total": len(results),
            "pass": sum(1 for r in results if r.status is Status.PASS),
            "fail": len(failed),
            "skip": len(skipped),
        },
        "checks": [
            {
                "id": r.check_id,
                "stage": r.stage.value,
                "status": r.status.value,
                "summary": r.summary,
                "evidence": r.evidence,
                "detail": r.detail,
            }
            for r in results
        ],
    }


def _print_human(results: list[CheckResult], report: dict[str, object]) -> None:
    current: str | None = None
    for r in results:
        if r.stage.value != current:
            current = r.stage.value
            sys.stdout.write(f"\n── {current.split('-', 1)[1].upper()} " + "─" * (46 - len(current)) + "\n")
        line = f"  [{_MARK[r.status]}] {r.check_id:<10} {r.summary}"
        sys.stdout.write(line + "\n")
        if r.status is not Status.PASS and r.evidence:
            sys.stdout.write(f"         └─ {r.evidence[:300]}\n")
    counts = report["counts"]
    assert isinstance(counts, dict)
    verdict = "HEALTHY" if report["healthy"] else "UNHEALTHY"
    sys.stdout.write(
        f"\n{verdict} — {counts['pass']} passed, {counts['fail']} failed, {counts['skip']} skipped "
        f"of {counts['total']}\n"
    )
    # A skip is an UNANSWERED question, and a bare "HEALTHY" over skipped checks reads as full
    # coverage. Say what is still unknown, every time, so a partial run cannot be quoted as a
    # clean bill of health.
    if counts["skip"]:
        skipped_ids = ", ".join(r.check_id for r in results if r.status is Status.SKIP)
        sys.stdout.write(
            f"NOT A FULL PASS: {counts['skip']} check(s) did not run ({skipped_ids}). "
            "A skip is unknown, not green — use --full to run everything, or --strict to fail on it.\n"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.health",
        description="Engine health: structure, rule layer, cross-file consistency, build, suites.",
    )
    parser.add_argument("--full", action="store_true", help="also run the npm test suites (slow)")
    parser.add_argument("--json", action="store_true", help="emit the JSON report on stdout")
    parser.add_argument("--strict", action="store_true", help="treat SKIP as failure (unknown is not green)")
    parser.add_argument(
        "--log", type=Path, default=None, help="write the full JSON report to this path (overwrites)"
    )
    parser.add_argument(
        "--run-log",
        dest="run_log",
        type=Path,
        default=None,
        help=f"append-only JSONL run history (default: {_RUN_LOG_RELATIVE})",
    )
    parser.add_argument(
        "--no-run-log",
        dest="no_run_log",
        action="store_true",
        help="do not append to the run history (it is written by default)",
    )
    parser.add_argument("--root", type=Path, default=None, help="engine root (default: auto-detect)")
    args = parser.parse_args(argv)

    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    from tools.docgen import engine_config

    # The rule layer must follow `--root`. It used to come from `engine_config.doc_system_dir()`,
    # which resolves against the ENGINE's own location — so `tools.health --root <other tree>` moved
    # every other check onto the target while the L9 hash gate kept validating THIS repository's
    # rulebook, and reported `[PASS] RULE-01 hash-gate holds — no undeclared rulebook drift` over a
    # target whose RULEBOOK carried an attacker-authored rule. A false green that gets louder the
    # more deliberately you use the flag.
    default_root = engine_config.host_root().resolve()
    if root.resolve() == default_root:
        doc_system = engine_config.doc_system_dir()
    else:
        doc_system = root / engine_config.doc_system_dir().relative_to(default_root)
    ctx = Ctx(root=root, doc_system=doc_system, full=args.full)

    started = time.perf_counter()
    results = run_all(ctx)
    duration_s = time.perf_counter() - started
    report = _report(results, ctx, strict=args.strict)

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    else:
        _print_human(results, report)

    # The DURABLE record first. This used to run after the --log write, which was unguarded: a bad
    # --log path (a read-only CI mount, a typo) raised out of main() after the verdict had already
    # been printed, turning a healthy engine UNHEALTHY for every caller reading the exit code — the
    # pre-push hook included — and destroying the run-log entry that would have shown what happened.
    # The asymmetry was the defect: the append below was carefully hardened while the identical
    # write-to-a-user-named-path directly above it was not.
    if not args.no_run_log:
        _append_run_log(
            args.run_log or (root / _RUN_LOG_RELATIVE),
            report,
            root=root,
            duration_s=duration_s,
        )

    if args.log is not None:
        try:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            args.log.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            # Announced, never fatal: an optional report artifact must not change the verdict.
            sys.stderr.write(f"health: report NOT written to {args.log}: {exc}\n")
        else:
            # stderr, not stdout: under --json, stdout must stay parseable JSON and nothing else.
            sys.stderr.write(f"report written: {args.log}\n")

    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
