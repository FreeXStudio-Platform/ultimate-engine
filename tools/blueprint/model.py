"""Derive the system model from the tree — the map an agent reads INSTEAD of the tree.

WHY THIS EXISTS, measured
=========================
This engine's purpose is to stop agents burning tokens re-deriving a project they were handed.
Measured on this repository 2026-08-23, while building this engine: ``PROJECT_INDEX.json`` held
**1** artifact for 295 tracked files, ``CONTENT_INDEX.json`` had never been generated, and
``graphify-out/deps.json`` reported **0 nodes** across ~77 real modules — and the directory holding
it is gitignored, so nothing survived to the next session anyway. Every dispatched agent therefore
started from ``git ls-files`` and grepped the whole tree: measured **200-350k tokens each**, across
roughly thirty agents. The navigation layer the engine exists to provide was empty, so the engine
was paying full price for its own territory.

WHAT THIS PRODUCES
==================
One derived model, rendered three ways and **committed**, so the next session inherits it:

* ``blueprint/SYSTEM.json``  — the machine model (stable keys, for tools and agents)
* ``blueprint/SYSTEM.md``    — the compact orientation map (the agent's FIRST read)
* ``blueprint/system.mmd``   — the dependency graph as mermaid (renders in the doc pipeline)

THE RULE THIS FILE OBEYS
========================
**Nothing here is hand-kept.** Every fact is derived from the artifact that owns it — the guard
registry from ``GUARDS``, the check registry from ``CHECKS``, the gate spine from ``PRECEDENCE``,
the import graph from Python's own ``ast``, the document set from each document's front matter, the
open work from the register's own table. That is ``RULES.md`` Rule 2 applied to the map itself: a
blueprint that restates facts would rot exactly as the documents it replaces did, and it would rot
silently, because a map is consulted rather than read.

``blueprint_files()`` is the ONE description of what ``blueprint/`` contains. The writer and the
verifier both call it, so they cannot drift apart — that failure happened today, in this session,
between ``theme-adapter.mjs`` and the health check written to verify it, and cost a full debugging
pass on a tree where nothing was actually wrong.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any

_EXCLUDED_DIRS = ("node_modules/", ".git/", "graphify-out/", "__pycache__/")


def _tracked(root: Path, *patterns: str) -> list[str]:
    """Git's own answer to "what is in this project", minus vendored trees.

    Deliberately ``git ls-files`` rather than a filesystem walk: the tracked set is the thing a
    reviewer, a hook and a fresh clone all agree on, and it excludes build residue for free.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", *patterns],
            capture_output=True, text=True, check=False, timeout=60,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [p for p in out.splitlines() if p and not any(d in p for d in _EXCLUDED_DIRS)]


def tracked_paths(root: Path, *patterns: str) -> list[str]:
    """Public name for "what does git say is in this project", for callers outside this module.

    ``_tracked`` stays the internal call site; this is the same query under a name other modules
    may depend on. It exists because the spec layer has to ask git — not the filesystem — whether
    an owning document resolves: an untracked file is present for its author and absent for
    everybody else, and a map is written for everybody else.
    """
    return _tracked(root, *patterns)


# ── the import graph ────────────────────────────────────────────────────────────────────────────
def _module_id(rel: str) -> str:
    mod = rel.removesuffix(".py").replace("/", ".")
    return mod.removesuffix(".__init__")


def import_graph(root: Path) -> dict[str, Any]:
    """Every internal import edge, via ``ast`` rather than a regex.

    ``ast`` is used instead of line matching because it is the only reader that agrees with the
    interpreter: it sees multi-line and parenthesised imports, ignores the word ``import`` inside a
    string or comment, and resolves ``from . import x`` by its real level. The sibling JS builder
    (``tools/graphify/build-deps.mjs``) matches lines with a regex and is the interactive viewer;
    this is the committed source of truth. Their overlap is recorded in the register rather than
    hidden, because two derivations of one fact is the defect this engine exists to catch.
    """
    files = [f for f in _tracked(root, "*.py") if not f.endswith("__pycache__")]
    known = {_module_id(f) for f in files}
    for mod in list(known):
        parts = mod.split(".")
        for i in range(1, len(parts)):
            known.add(".".join(parts[:i]))

    def snap(target: str) -> str | None:
        m = target
        while m and m not in known and "." in m:
            m = m.rsplit(".", 1)[0]
        return m if m in known else None

    edges: set[tuple[str, str]] = set()
    unparsed: list[str] = []
    for rel in files:
        mod = _module_id(rel)
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            # Named, never swallowed: a file the model could not read is a HOLE in the map, and a
            # map with a silent hole is worse than one that admits it.
            unparsed.append(f"{rel}: {type(exc).__name__}")
            continue
        pkg = mod.rsplit(".", 1)[0] if "." in mod else mod
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = pkg
                    for _ in range(node.level - 1):
                        base = base.rsplit(".", 1)[0] if "." in base else base
                    targets = [f"{base}.{node.module}" if node.module else base]
                elif node.module:
                    targets = [node.module]
            for t in targets:
                hit = snap(t)
                if hit and hit != mod:
                    edges.add((mod, hit))

    indeg: dict[str, int] = {}
    outdeg: dict[str, int] = {}
    for src, dst in edges:
        outdeg[src] = outdeg.get(src, 0) + 1
        indeg[dst] = indeg.get(dst, 0) + 1
    nodes = sorted({_module_id(f) for f in files})
    return {
        "nodes": [
            {"id": n, "in": indeg.get(n, 0), "out": outdeg.get(n, 0),
             "package": n.rsplit(".", 1)[0] if "." in n else n}
            for n in nodes
        ],
        "edges": sorted(f"{a} -> {b}" for a, b in edges),
        "unparsed": unparsed,
    }


# ── the registries, each read from the module that owns it ──────────────────────────────────────
def registries(root: Path) -> dict[str, Any]:
    """Guards, health checks and the gate spine — imported, not parsed.

    Importing is the point: a registry that cannot be imported is broken, and this map should say
    so rather than reporting a stale copy scraped out of the source text.
    """
    out: dict[str, Any] = {}
    try:
        from tools.corpus_check.guards import GUARDS
        out["corpus_guards"] = [name for name, _ in GUARDS]
    except Exception as exc:  # noqa: BLE001 — the failure IS the finding
        out["corpus_guards_error"] = f"{type(exc).__name__}: {exc}"
    try:
        from tools.health.checks import CHECKS
        ids = []
        for fn in CHECKS:
            m = re.search(r'"([A-Z]+-\d+)"', (fn.__doc__ or "") + (fn.__name__ or ""))
            ids.append(m.group(1) if m else fn.__name__)
        out["health_checks"] = ids
    except Exception as exc:  # noqa: BLE001
        out["health_checks_error"] = f"{type(exc).__name__}: {exc}"
    try:
        from tools.docgen.export_sanitizer import PRECEDENCE
        out["gate_spine"] = list(PRECEDENCE)
    except Exception as exc:  # noqa: BLE001
        out["gate_spine_error"] = f"{type(exc).__name__}: {exc}"
    try:
        vj = json.loads((root / "docs/design/doc-system/VERSION.json").read_text(encoding="utf-8"))
        out["rulebook_version"] = vj.get("version")
        out["locked_files"] = vj.get("rulebook_files", [])
    except (OSError, ValueError) as exc:
        out["rulebook_error"] = f"{type(exc).__name__}: {exc}"
    return out


# ── the governed documents ──────────────────────────────────────────────────────────────────────
# NOT "(no front matter)", which was measured false for six documents: every `skills/*/SKILL.md`
# opens with a `---` YAML block. What they lack is a DOC-SYSTEM header — an `id` and a
# `classification` — which is a different statement, and the one this label actually reports.
_UNGOVERNED = "(no doc-system header)"


def documents(root: Path) -> list[dict[str, str]]:
    """Every tracked Markdown document with its declared identity, from its own front matter.

    ⚠ **A document with no front matter is UNGOVERNED, not SECRET.** ``parse_header`` is fail-closed
    by design: handed a file with no YAML header it returns the sentinel id ``UNKNOWN`` and
    ``Tier.SECRET``, so that an unheadered document can never be exported as public. That is exactly
    right for the export gate and exactly wrong to copy into a map. The first build of this module
    did copy it, and reported **54 secret documents** in a repository that has none — a false fact,
    stated confidently, in the artifact every agent is told to read first. The sentinel is a refusal
    to answer, not an answer.
    """
    from tools.docgen.classification import parse_header

    docs: list[dict[str, str]] = []
    for rel in _tracked(root, "*.md"):
        header = None
        try:
            header = parse_header((root / rel).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — an unparseable header is reported, not fatal
            header = None

        doc_id = str(getattr(header, "id", "") or "") if header is not None else ""
        if header is None or doc_id in ("", "UNKNOWN"):
            docs.append({
                "path": rel, "id": "", "tier": _UNGOVERNED, "status": "", "title": "",
                "version": "", "revision": "", "produced_by": "", "verified_state": "",
                "last_reviewed": "", "surface": "",
            })
            continue

        tier = getattr(header, "classification", None)
        docs.append({
            "path": rel,
            "id": doc_id,
            # `.value` — `str(Tier.PUBLIC)` renders as "Tier.PUBLIC", which is the enum's repr and
            # not the vocabulary the rest of the engine speaks.
            "tier": str(getattr(tier, "value", tier) or ""),
            "status": str(getattr(header, "status", "") or ""),
            "title": str(getattr(header, "title", "") or ""),
            # Phase-4 document identity, carried into the map so the depth ladder can read the
            # top rung from the header that owns it rather than re-parsing every document.
            "version": str(getattr(header, "version", "") or ""),
            "revision": str(getattr(header, "revision", "") if getattr(header, "revision", None) is not None else ""),
            "produced_by": str(getattr(header, "produced_by", "") or ""),
            # Read as FIELDS, because the lifecycle report checked `date` and `tag` by scanning the
            # document's text and reported complete for a field that was absent, empty, or merely
            # discussed in prose.
            "last_reviewed": str(getattr(header, "last_reviewed", "") or ""),
            "surface": str(
                getattr(getattr(header, "surface", ""), "value", getattr(header, "surface", "")) or ""
            ),
            # `.value` for the same reason `tier` uses it two lines up: `str(VerifiedState.
            # UNVERIFIED)` renders as "VerifiedState.UNVERIFIED", which is the enum's repr and not
            # the vocabulary anything else in the engine speaks. Measured here, not guessed — the
            # first version of this line emitted exactly that string into the map.
            "verified_state": str(
                getattr(getattr(header, "verified_state", ""), "value", getattr(header, "verified_state", "")) or ""
            ),
        })
    return sorted(docs, key=lambda d: d["path"])


# ── the open work ───────────────────────────────────────────────────────────────────────────────
_ROW = re.compile(r"^\|\s*(OG-\d+)\s*\|\s*([A-Z]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")


def open_work(root: Path) -> list[dict[str, str]]:
    """Open register rows, parsed from the register's own Open table."""
    try:
        text = (root / "docs/process/OPEN_GATES.md").read_text(encoding="utf-8")
    except OSError:
        return []
    rest = text.partition("\n## Open")[2]
    body = rest.partition("\n## Closed")[0] if rest else ""
    rows = []
    for line in body.splitlines():
        m = _ROW.match(line)
        if m:
            rows.append({"id": m.group(1), "severity": m.group(2),
                         "disposition": m.group(3), "title": m.group(4)})
    return rows


def build_model(root: Path) -> dict[str, Any]:
    """The whole model. Pure derivation — call it twice on one tree and get the same bytes.

    **Phase 5 added the authored half and four derived layers on top of it.** The containers come
    from the system spec, which is the only hand-written input in this file's world; ownership,
    depth, gatekeepers and the six surfaces are all derived from the artifacts that own them, and
    every fact the spec asserts is checked against the tree by ``blueprint verify``.

    The ELK layout is deliberately **not** part of this model. It needs ``node``, and a model whose
    bytes depend on whether a binary is installed could not be compared against a committed copy on
    a machine without it — the freshness check would report drift where none exists. Layout is its
    own artifact with its own check and its own SKIP contract (`LESSONS.md` L-25).
    """
    from tools.blueprint import depth as depth_mod
    from tools.blueprint import gatekeepers as gate_mod
    from tools.blueprint import spec as spec_mod
    from tools.blueprint import surfaces as surfaces_mod

    graph = import_graph(root)
    docs = documents(root)
    reg = registries(root)
    work = open_work(root)
    module_ids = [n["id"] for n in graph["nodes"]]

    try:
        spec = spec_mod.load_spec(root)
        spec_error = ""
    except spec_mod.SpecError as exc:
        # Named, never swallowed. A map that silently renders "no containers" when the spec is
        # unreadable looks complete and asserts nothing — the same shape as the 0-node dependency
        # graph this whole layer replaced.
        spec = spec_mod.Spec(name="", purpose="", document="", containers=())
        spec_error = str(exc)

    assignment = spec_mod.assign(spec, module_ids)
    gates = gate_mod.build(root, module_ids)
    container_document = {c.id: c.document for c in spec.containers}
    module_depth = depth_mod.derive(
        root, module_ids,
        gatekeepers=gates, owner=assignment.owner,
        container_document=container_document, documents=docs,
    )
    container_depths = depth_mod.container_depth(
        module_depth, assignment.owner, [c.id for c in spec.containers]
    )
    containers = [
        {
            "id": c.id, "name": c.name, "purpose": c.purpose, "document": c.document,
            "packages": list(c.packages), "modules_declared": list(c.modules),
            "depth_floor": c.depth_floor,
            **container_depths.get(c.id, {}),
        }
        for c in spec.containers
    ]
    ladder: dict[str, int] = {}
    for rec in module_depth.values():
        ladder[rec["level"]] = ladder.get(rec["level"], 0) + 1
    tiers: dict[str, int] = {}
    for d in docs:
        tiers[d["tier"] or "(no header)"] = tiers.get(d["tier"] or "(no header)", 0) + 1
    model: dict[str, Any] = {
        "_readme": (
            "GENERATED by `python3 -m tools.blueprint build` — never hand-edit. This is the "
            "orientation map for an agent opening this repository cold: read blueprint/SYSTEM.md "
            "FIRST, then open only the files it points at. Every value here is derived from the "
            "artifact that owns it; nothing is restated."
        ),
        "counts": {
            "tracked_files": len(_tracked(root)),
            "python_modules": len(graph["nodes"]),
            "import_edges": len(graph["edges"]),
            "documents": len(docs),
            "corpus_guards": len(reg.get("corpus_guards", [])),
            "health_checks": len(reg.get("health_checks", [])),
            "gate_spine": len(reg.get("gate_spine", [])),
            "open_rows": len(work),
            "blocking_rows": sum(1 for r in work if r["disposition"].startswith("BLOCKS_PHASE")),
            "containers": len(containers),
            "modules_owned": len(assignment.owner),
            "modules_unassigned": len(assignment.unassigned),
        },
        "graph": graph,
        "registries": reg,
        "documents": docs,
        "document_tiers": dict(sorted(tiers.items())),
        "open_work": work,
        "system": {"name": spec.name, "purpose": spec.purpose, "document": spec.document,
                   "spec_error": spec_error},
        "containers": containers,
        "ownership": {
            "owner": assignment.owner,
            "unassigned": list(assignment.unassigned),
            "ambiguous": {k: list(v) for k, v in sorted(assignment.ambiguous.items())},
        },
        "depth": {"levels": list(depth_mod.LEVELS), "modules": module_depth,
                  "distribution": dict(sorted(ladder.items()))},
        "gatekeepers": gates,
        "surfaces": surfaces_mod.build(root),
    }
    # The completeness report reads the model rather than re-deriving anything, so it is computed
    # last and folded in — `BUILD_PLAN.md` row 6, and the reason it is here rather than in its own
    # command is `RULES.md` Rule 6: it is derived work, so it is committed and ratcheted like the
    # rest of the map instead of being regenerated on demand and trusted.
    from tools.blueprint import completeness as completeness_mod

    model["completeness"] = completeness_mod.build(root, model)
    return model
