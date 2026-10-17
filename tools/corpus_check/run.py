"""Corpus-check runner + CLI.

    python3 -m tools.corpus_check                 # every guard, over this repository's corpus
    python3 -m tools.corpus_check --guard counts  # one guard (repeatable) — for falsification
    python3 -m tools.corpus_check --list          # the registry, without running anything
    python3 -m tools.corpus_check --json          # machine-readable report on stdout

**Exit code is the terminating condition** (`DOC_WRITING_DOCTRINE.md` §4): 0 only when every guard
that ran PASSED. A SKIP is never a pass — it means the guard could not run and its question is still
open — so a run containing one exits non-zero and says which. *"A script cannot get bored, cannot
agree with itself, and cannot be persuaded."*

Everything except a ``--json`` report goes to **stderr**, so stdout stays parseable.

**Fail-closed.** A guard that raises is a FAILURE, not a skip: an exception while checking is not
evidence that the corpus is clean. The traceback is carried into the report rather than printed and
lost, because the run that hits it is usually not the run a human is watching.

**Coverage history is advisory** (`P8-054`, `tools/corpus_check/runlog.py`): each guard's `checked`
count is recorded every run, and a PASS that checked far fewer claims than that guard's own
recorded high-water mark prints a WARN — visible here and in `--json` — without changing the exit
code. See `runlog`'s module docstring for why this is a warning and not a second hard gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from tools.corpus_check import runlog
from tools.corpus_check.corpus import Corpus, repo_root
from tools.corpus_check.guards import GUARDS, guard_names
from tools.corpus_check.model import Finding, GuardResult, Severity, Status, skipped

_MARK = {Status.PASS: "PASS", Status.FAIL: "FAIL", Status.SKIP: "SKIP"}


def run_all(corpus: Corpus, *, only: tuple[str, ...] = ()) -> list[GuardResult]:
    """Run the selected guards (all of them by default) and return one result each.

    A guard that raises becomes a FAIL carrying its traceback. Ordering is the registry's, which is
    cheap-and-textual first and *rendered-output last* — the one guard that has to build documents
    should not delay the eight findings a reader could already have been acting on.
    """
    results: list[GuardResult] = []
    for name, fn in GUARDS:
        if only and name not in only:
            continue
        if not corpus.available:
            results.append(
                skipped(
                    name,
                    "git ls-files unavailable — the corpus could not be listed",
                    evidence=(
                        "Every guard resolves against TRACKED content. Checking an empty corpus "
                        "would pass vacuously, which is the defect this package exists to catch."
                    ),
                )
            )
            continue
        try:
            results.append(fn(corpus))
        except Exception:  # noqa: BLE001 — deliberate: any guard failure is a FAIL, never a skip
            results.append(
                GuardResult(
                    guard=name,
                    status=Status.FAIL,
                    summary=f"{name}: the guard itself raised",
                    evidence=traceback.format_exc(limit=6).strip(),
                )
            )
    return results


def _report(
    results: list[GuardResult],
    *,
    root: Path,
    coverage_warnings: list[runlog.CoverageWarning],
) -> dict[str, object]:
    findings: list[Finding] = [f for r in results for f in r.sorted_findings()]
    return {
        "root": str(root),
        "coverage_warnings": [
            {"guard": w.guard, "checked": w.checked, "watermark": w.watermark}
            for w in coverage_warnings
        ],
        "guards": [
            {
                "guard": r.guard,
                "status": r.status.value,
                "summary": r.summary,
                "checked": r.checked,
                "floor": r.floor,
                "evidence": r.evidence,
                "findings": [
                    {
                        "path": f.path,
                        "line": f.line,
                        "severity": f.severity.value,
                        "message": f.message,
                        "evidence": f.evidence,
                    }
                    for f in r.sorted_findings()
                ],
            }
            for r in results
        ],
        "counts": {
            "guards": len(results),
            "passed": sum(1 for r in results if r.status is Status.PASS),
            "failed": sum(1 for r in results if r.status is Status.FAIL),
            "skipped": sum(1 for r in results if r.status is Status.SKIP),
            "findings": len(findings),
        },
        "by_severity": {
            s.value: sum(1 for f in findings if f.severity is s) for s in Severity
        },
        "clean": all(r.status is Status.PASS for r in results),
    }


def _print_human(
    results: list[GuardResult],
    report: dict[str, object],
    *,
    coverage_warnings: list[runlog.CoverageWarning],
) -> None:
    out = sys.stderr
    for r in results:
        print(f"  [{_MARK[r.status]}] {r.guard:<16} {r.summary}", file=out)
        if r.evidence and r.status is not Status.PASS:
            for line in r.evidence.splitlines():
                print(f"          {line}", file=out)
        for f in r.sorted_findings():
            print(f"      · {f.render()}", file=out)
    for w in coverage_warnings:
        print(f"  [WARN] {w.render()}", file=out)
    counts = report["counts"]
    assert isinstance(counts, dict)
    verdict = "CLEAN" if report["clean"] else "FINDINGS"
    print(
        f"\n{verdict} — {counts['passed']} passed, {counts['failed']} failed, "
        f"{counts['skipped']} skipped of {counts['guards']} guard(s); "
        f"{counts['findings']} finding(s)",
        file=out,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.corpus_check",
        description="Check this repository's documentation corpus against its own source.",
    )
    parser.add_argument(
        "--guard",
        action="append",
        default=[],
        metavar="NAME",
        help="run only this guard (repeatable). Use --list to see the names.",
    )
    parser.add_argument("--list", action="store_true", help="print the guard registry and exit")
    parser.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    parser.add_argument(
        "--root",
        default=None,
        help="repository root to check (default: the enclosing git repository)",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name, fn in GUARDS:
            first = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""
            print(f"{name:<16} {first}")
        return 0

    unknown = [g for g in args.guard if g not in guard_names()]
    if unknown:
        parser.error(
            f"unknown guard(s): {', '.join(unknown)}. Known: {', '.join(guard_names())}"
        )

    root = Path(args.root).resolve() if args.root else repo_root()
    corpus = Corpus(root=root)
    results = run_all(corpus, only=tuple(args.guard))
    # Read the watermark BEFORE recording this run — otherwise every guard is compared against a
    # history that already includes its own current number, and a real collapse could never be
    # more than "half of itself", which is never true.
    warnings = runlog.coverage_warnings(root, results)
    runlog.record(root, results)
    report = _report(results, root=root, coverage_warnings=warnings)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(results, report, coverage_warnings=warnings)

    return 0 if report["clean"] else 1
