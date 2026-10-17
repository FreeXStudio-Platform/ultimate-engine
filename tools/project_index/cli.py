"""``python3 -m tools.project_index.cli`` — command-line access to the project index.

Subcommands: ``register``, ``list``, ``search``, ``stats``, ``remove``, ``dashboard``
(writes a self-contained HTML view — see dashboard.py).
"""

from __future__ import annotations

import argparse
import json
import sys

from tools.project_index import dashboard, index


def _cmd_register(args: argparse.Namespace) -> int:
    artifact = index.Artifact(
        id=args.id,
        path=args.path,
        type=args.type,
        title=args.title,
        section=args.section or "",
        summary=args.summary or "",
        tags=args.tags.split(",") if args.tags else [],
        status=args.status,
        created=args.created or "",
        updated=args.updated or args.created or "",
        engine=args.engine or "",
    )
    index.register_artifact(artifact)
    print(f"registered: {artifact.id} ({artifact.type}) -> {artifact.path}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    rows = index.list_artifacts(section=args.section, type=args.type, tag=args.tag)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        if not rows:
            print("(no artifacts registered yet)")
        for a in rows:
            print(f"[{a.get('type','?'):10}] {a.get('id','?'):24} {a.get('title','')}  ({a.get('path','')})")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    rows = index.search_artifacts(args.query)
    if not rows:
        print(f"no matches for '{args.query}'")
    for a in rows:
        print(f"[{a.get('type','?'):10}] {a.get('id','?'):24} {a.get('title','')}  ({a.get('path','')})")
    return 0


def _cmd_stats(_args: argparse.Namespace) -> int:
    print(json.dumps(index.stats(), indent=2))
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    removed = index.remove_artifact(args.id)
    print(f"{'removed' if removed else 'not found'}: {args.id}")
    return 0 if removed else 1


def _cmd_dashboard(args: argparse.Namespace) -> int:
    try:
        out_path = dashboard.write_dashboard(args.out)
    except dashboard.WriteBlockedError as exc:
        sys.stderr.write(f"⛔ project_index dashboard: {exc}\n")
        return 2
    print(f"wrote dashboard: {out_path}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Report where the index and the filesystem disagree. Exits non-zero on a real problem
    (a missing file or a duplicate path) so this can be used as a gate in a checkout script;
    ``--scan`` findings are advisory and never affect the exit code."""
    report = index.verify(scan=args.scan)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    print(f"index: {report['index_path']}")
    print(f"paths resolved against: {report['artifact_root']}")
    print(f"{report['total']} artifact(s) registered")
    for m in report["missing"]:
        print(f"  MISSING     {m['id']}: {m['path'] or '(no path)'} — {m['reason']}")
    for d in report["duplicate_paths"]:
        print(f"  DUPLICATE   {d['path']} claimed by {', '.join(d['ids'])}")
    for u in report["unregistered"]:
        print(f"  unregistered (advisory)  {u}")
    if report["ok"] and not report["unregistered"]:
        print("OK — every registered artifact resolves to a real file, no duplicates.")
    elif report["ok"]:
        print(f"OK — index is consistent; {len(report['unregistered'])} unregistered file(s) noted above.")
    else:
        print(
            f"PROBLEM — {len(report['missing'])} missing, {len(report['duplicate_paths'])} duplicate. "
            "Update the entry if it moved, or `remove` it if the artifact is gone."
        )
    return 0 if report["ok"] else 1


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project-index")
    sub = parser.add_subparsers(dest="command", required=True)

    p_register = sub.add_parser("register", help="add or update one artifact")
    p_register.add_argument("--id", required=True)
    p_register.add_argument("--path", required=True)
    p_register.add_argument("--type", required=True, help="document|chart|graph|diagram|map|mermaid|other")
    p_register.add_argument("--title", required=True)
    p_register.add_argument("--section", default="")
    p_register.add_argument("--summary", default="")
    p_register.add_argument("--tags", default="", help="comma-separated")
    p_register.add_argument("--status", default="draft")
    p_register.add_argument("--created", default="")
    p_register.add_argument("--updated", default="")
    p_register.add_argument("--engine", default="")
    p_register.set_defaults(func=_cmd_register)

    p_list = sub.add_parser("list", help="list artifacts, optionally filtered")
    p_list.add_argument("--section", default=None)
    p_list.add_argument("--type", default=None)
    p_list.add_argument("--tag", default=None)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=_cmd_list)

    p_search = sub.add_parser("search", help="substring search across title/summary/tags/section/path")
    p_search.add_argument("query")
    p_search.set_defaults(func=_cmd_search)

    p_stats = sub.add_parser("stats", help="counts by type/section/status")
    p_stats.set_defaults(func=_cmd_stats)

    p_remove = sub.add_parser("remove", help="remove one artifact by id")
    p_remove.add_argument("id")
    p_remove.set_defaults(func=_cmd_remove)

    p_dash = sub.add_parser("dashboard", help="write a self-contained HTML dashboard")
    p_dash.add_argument("--out", default=None, help="output path (default: PROJECT_INDEX.html next to the index)")
    p_dash.set_defaults(func=_cmd_dashboard)

    p_verify = sub.add_parser(
        "verify",
        help="check the index against the filesystem (missing files, duplicate paths); exit 1 on a problem",
    )
    p_verify.add_argument(
        "--scan",
        default=None,
        metavar="DIR",
        help="also list .html/.svg/.png/.pdf files under DIR that no artifact claims (advisory only)",
    )
    p_verify.add_argument("--json", action="store_true", help="machine-readable output")
    p_verify.set_defaults(func=_cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except index.RegistrationRefused as exc:
        # Deliberately the SAME shape as the IndexUnreadable branch below: a refusal is the correct
        # ANSWER, not a crash, and exit 2 keeps it distinguishable from `verify`'s exit 1 ("the
        # index and the filesystem disagree"). A traceback here would read as an engine bug and
        # invite a retry with `--path` spelled differently.
        sys.stderr.write(f"⛔ project-index: {exc}\n")
        return 2
    except index.IndexUnreadable as exc:
        # A refusal is the correct ANSWER here, not a crash. `verify` deliberately fails closed on
        # an index it cannot read — reporting "OK" over a payload it never parsed was the defect —
        # but a raw traceback is the wrong way to say so: it reads as an engine bug rather than as
        # the finding it is, and exit code 1 would be indistinguishable from "verification failed".
        sys.stderr.write(f"⛔ project-index: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
