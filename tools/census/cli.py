"""``python -m tools.census`` — measure, report, or draw one explorer.

    measure  PROFILE [--root DIR] [--today YYYY-MM-DD] --out census.json     the measurement as JSON (deterministic)
    report   PROFILE --out DIR [--root DIR] [--engine-root DIR] [--today D] [--local-preview]
                                                                               the measurement, then the document built by docgen
    inventory [--engine-root DIR]                                              how many figure models the engine can draw

``--root`` is the repository to measure (default: the current directory); the report is written under ``--out``, which must be
inside the host repository docgen builds in. Exit 0 on success, 2 on a refusal (bad profile, git failure, document refused).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.census import gitscan, inventory, measure, profile, report


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m tools.census", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure", help="measure a repository and write census.json")
    m.add_argument("profile", type=Path)
    m.add_argument("--root", type=Path, default=Path("."))
    m.add_argument("--today", default=None)
    m.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("report", help="measure, then build the census document with docgen")
    r.add_argument("profile", type=Path)
    r.add_argument("--root", type=Path, default=Path("."))
    r.add_argument("--today", default=None)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--engine-root", type=Path, default=None)
    r.add_argument("--formats", default="html,blueprint")
    r.add_argument("--local-preview", action="store_true", help="build a confidential or internal report for local reading (never exported), as docgen's own flag")
    i = sub.add_parser("inventory", help="count the figure models the engine can draw")
    i.add_argument("--engine-root", type=Path, default=Path("."))
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.cmd == "inventory":
            print(json.dumps(inventory.inventory(args.engine_root.resolve()), indent=1))
            return 0
        prof = profile.load(args.profile)
        root = args.root.resolve()
        data = measure.measure(root, prof, args.today)
        if args.cmd == "measure":
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"census: {data['documents']['total']} documents, {data['freshness']['updated']} of {data['freshness']['population']} live updated -> {args.out}")
            return 0
        inv = inventory.inventory((args.engine_root or Path(".")).resolve())
        outputs = report.build(data, prof, args.out.resolve(), inv, tuple(f for f in args.formats.split(",") if f), local_preview=args.local_preview)
        for kind, path in sorted(outputs.items()):
            print(f"census: wrote {kind}: {path}")
        return 0
    except (profile.ProfileError, gitscan.GitError, RuntimeError, ValueError, OSError) as exc:
        print(f"census: refused — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
