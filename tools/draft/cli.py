"""``python3 -m tools.draft check <path>`` — would this document be accepted if it landed now?"""

from __future__ import annotations

import argparse
import sys

from tools.draft.gate import check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools.draft",
        description="Run the corpus guards on a candidate document BEFORE it enters the corpus.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="report what this candidate would introduce")
    c.add_argument("path", help="repo-relative path the document will occupy")
    c.add_argument("--quiet", action="store_true", help="print only the verdict line")
    args = parser.parse_args(argv)

    try:
        report = check(args.path)
    except FileNotFoundError as exc:
        print(f"draft: {exc}", file=sys.stderr)
        return 2

    if report.clean:
        print(f"draft: CLEAN — '{report.target}' introduces no findings "
              f"({report.candidate_count} in the corpus, unchanged)")
        return 0

    print(f"draft: {len(report.introduced)} finding(s) INTRODUCED by '{report.target}' "
          f"(corpus {report.baseline_count} → {report.candidate_count})", file=sys.stderr)
    if not args.quiet:
        for f in report.on_the_draft:
            print(f"  · {f.render()}", file=sys.stderr)
        if report.elsewhere:
            # The findings a `grep <path>` would never have shown you, which is the whole reason
            # this compares two corpora instead of filtering one.
            print("  — and these land on OTHER documents, because adding this one moved a fact "
                  "they state:", file=sys.stderr)
            for f in report.elsewhere:
                print(f"  · {f.render()}", file=sys.stderr)
    print("  Fix these BEFORE committing. Repairing prose after it lands is the measured cost "
          "this gate exists to avoid (RULES.md Rule 3).", file=sys.stderr)
    return 1
