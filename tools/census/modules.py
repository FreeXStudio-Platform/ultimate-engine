"""A Python source tree as a hierarchy: package -> submodule, with sizes and the imports between packages.

Read with ``ast`` (never imported, never executed). A "package" is an immediate child of a code root (a directory, or a single
``.py`` file); a "submodule" is an immediate child of a package. An import counts as an edge from the importing package to the
package it names when both are under the code roots; imports of anything else are not edges. Relative imports are resolved against
the importing file. A file that does not parse is counted in the sizes and reported in ``unparsed``, never silently skipped.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any


def _parts(root_dir: str, path: str) -> list[str]:
    rel = path[len(root_dir) + 1 :]
    parts = rel.split("/")
    parts[-1] = parts[-1][:-3]
    if parts[-1] == "__init__":
        parts.pop()
    return parts


def _top(root_dir: str, parts: list[str]) -> str | None:
    if parts and parts[0] == root_dir.split("/")[-1] and len(parts) > 1:
        return parts[1]
    return parts[0] if parts else None


def read_modules(root: Path, code_roots: tuple[str, ...], files: list[str]) -> dict[str, Any]:
    """The hierarchy and import edges of every ``.py`` file under ``code_roots`` (paths relative to the repository root)."""
    packages: dict[str, dict[str, Any]] = {}
    sources: list[tuple[str, str, str]] = []  # (root_dir, path, text)
    unparsed: list[str] = []
    for root_dir in code_roots:
        prefix = root_dir.rstrip("/") + "/"
        for path in files:
            if not (path.startswith(prefix) and path.endswith(".py")):
                continue
            try:
                text = (root / path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            parts = _parts(root_dir.rstrip("/"), path)
            if not parts:
                continue
            pkg = parts[0]
            rec = packages.setdefault(pkg, {"name": pkg, "root": root_dir.rstrip("/"), "files": 0, "loc": 0, "subs": {}})
            lines = text.count("\n") + (1 if text else 0)
            rec["files"] += 1
            rec["loc"] += lines
            sub = parts[1] if len(parts) > 1 else "(package root)"
            s = rec["subs"].setdefault(sub, {"name": sub, "files": 0, "loc": 0})
            s["files"] += 1
            s["loc"] += lines
            sources.append((root_dir.rstrip("/"), path, text))
    edges: Counter[tuple[str, str]] = Counter()
    sub_edges: Counter[tuple[str, str, str]] = Counter()
    for root_dir, path, text in sources:
        parts = _parts(root_dir, path)
        if not parts:
            continue
        src = parts[0]
        sub = parts[1] if len(parts) > 1 else "(package root)"
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            unparsed.append(path)
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = parts[: max(0, len(parts) - node.level)] if not path.endswith("__init__.py") else parts[: max(0, len(parts) - node.level + 1)]
                    names = [".".join(base + ([node.module] if node.module else []))]
                elif node.module:
                    names = [node.module]
            for name in names:
                segs = name.split(".")
                head = _top(root_dir, segs)
                if head and head in packages and head != src:
                    edges[(src, head)] += 1
                    sub_edges[(src, sub, head)] += 1
    ordered = sorted(packages.values(), key=lambda p: (-p["loc"], p["name"]))
    fan_in: Counter[str] = Counter()
    fan_out: Counter[str] = Counter()
    for (a, b), n in edges.items():
        fan_out[a] += n
        fan_in[b] += n
    return {
        "roots": [r.rstrip("/") for r in code_roots],
        "packages": [
            {"name": p["name"], "root": p["root"], "files": p["files"], "loc": p["loc"], "fan_in": fan_in.get(p["name"], 0), "fan_out": fan_out.get(p["name"], 0),
             "subs": sorted(p["subs"].values(), key=lambda s: (-s["loc"], s["name"]))}
            for p in ordered
        ],
        "edges": [[a, b, n] for (a, b), n in sorted(edges.items(), key=lambda kv: (-kv[1], kv[0]))],
        "sub_edges": [[p, s, d, n] for (p, s, d), n in sorted(sub_edges.items(), key=lambda kv: (-kv[1], kv[0]))],
        "loc": sum(p["loc"] for p in ordered),
        "files": sum(p["files"] for p in ordered),
        "unparsed": sorted(unparsed),
    }


def documented(mods: dict[str, Any], text: str) -> list[str]:
    """Packages a body of text names as ``<root>/<package>`` or ``<root.dotted>.<package>``."""
    out = []
    for p in mods["packages"]:
        root = p["root"]
        slash = re.escape(f"{root}/{p['name']}")
        dotted = re.escape(f"{root.replace('/', '.')}.{p['name']}")
        if re.search(rf"(?<![\w/.-])(?:{slash}|{dotted})(?![\w])", text):
            out.append(p["name"])
    return out
