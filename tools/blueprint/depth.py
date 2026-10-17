"""How deep each node actually is — the C4 ladder of `BUILD_PLAN.md` D4, derived from evidence.

THE LADDER, AND THE ONE RULE THAT MAKES IT MEAN ANYTHING
========================================================
`BUILD_PLAN.md` D4 adopts the C4 depth ladder and states the rule this module implements:

    A node's depth is the **highest level for which its evidence exists** — not what someone
    asserted.

Every level below is a *measurement* — with **one stated exception at rung 5**, called out here
rather than left for a verifier to find (`OG-193`'s lesson: a module must not claim a property it
does not have):

===== ============== ================================================================
level name           the evidence that proves it, and nothing else counts
===== ============== ================================================================
0     ``sketch``     the node exists in the tree
1     ``shape``      it says what it is for — a non-empty module docstring
2     ``modules``    what is inside is enumerable — a package has children; a leaf has
                     at least one public top-level definition
3     ``connections`` a registered gate reads it, **or** it is itself a gate (it
                     emits at least one gate token). Its edges are already known
                     for every node, so they discriminate nothing and are not
                     tested.
4     ``internals``  a retained counter-example names it, so its behaviour is pinned
5     ``detail``     its owning document is governed AND its header CLAIMS
                     ``verified_state: verified``. **This rung reads a written
                     claim, not evidence** — see the bound below.
===== ============== ================================================================

**Depth is CONTIGUOUS: the highest level whose evidence exists and all of whose lower levels also
hold.** A ladder is climbed, not sampled. Without contiguity a module with a test but no docstring
would report ``internals``, which reads as "we went deep here" when what actually happened is that
somebody skipped writing down what the thing is for. The whole value of a completeness report is
that it says *where we stopped*, and a non-contiguous maximum cannot say that.

RUNG 5 READS A CLAIM, AND THE ADJUDICATION LIVES ELSEWHERE
=========================================================
**Stated plainly because the first version of this docstring got it wrong.** It said rung 5 required
a verified state *"that the identity guard has not refuted"*, and that second conjunct was never
implemented — ``derive`` does not consult the identity guard. An independent verifier proved the
gap: it added ``verified_state: verified`` to a container-owning document in a throwaway tree, and
`tools/corpus_check`'s ``identity`` guard reported CRITICAL *"verified_state: verified with no
content-certifying stamp"* while this module simultaneously reported those nodes at depth 5.

The claim is corrected rather than the code, because the division is the right one: **the map
REPORTS what a header declares; the ``identity`` guard ADJUDICATES it, at CRITICAL, on every corpus
run.** Two enforcers of one rule is the defect this engine exists to catch. What was wrong was a
module claiming an adjudication it does not perform.

WHY NOTHING REPORTS ``detail`` TODAY — the real cause, not the one first written
===============================================================================
The first version blamed "no governed document yet declares a verified state". True, and not the
operative constraint. The actual reason is one step earlier: **none of the container-owning
documents carries front matter at all.** The corpus has 4 governed documents and every one of them
is a sample or a gallery; no document that owns a container is governed, so rung 5 could not be
reached even by a document that wanted to claim it. Rung 5 is nonetheless live and reachable —
a verifier demonstrated it by adding front matter to a container-owning document, and three modules
moved to ``detail`` immediately.

A map that says "we stopped at 4" is worth having. A map that says "5" because 5 was easy to claim
is the failure mode.

THE BOUND, STATED HERE RATHER THAN LEFT FOR A VERIFIER
======================================================
Level 4's evidence is *a test names this module*, not *this module is well tested*. Coverage is a
different measurement with a different instrument. This one is honest about being a floor: a module
no probe mentions is definitely not pinned; a module some probe mentions may still be thinly
covered.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from tools.blueprint.gatekeepers import _module_file, imported_modules
from tools.blueprint.model import _UNGOVERNED, tracked_paths

LEVELS: tuple[str, ...] = ("sketch", "shape", "modules", "connections", "internals", "detail")


def _public_definitions(root: Path, module_id: str) -> int:
    """Top-level public defs and classes. ``ast`` because a regex counts them inside strings too."""
    rel = module_id.replace(".", "/") + ".py"
    path = root / rel
    if not path.is_file():
        path = root / (module_id.replace(".", "/") + "/__init__.py")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return 0
    return sum(
        1
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")
    )


def _docstring(root: Path, module_id: str) -> str:
    rel = module_id.replace(".", "/") + ".py"
    path = root / rel
    if not path.is_file():
        path = root / (module_id.replace(".", "/") + "/__init__.py")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return ""
    return (ast.get_docstring(tree) or "").strip()


def _verified_documents(documents: list[dict[str, str]]) -> set[str]:
    """Document paths whose header CLAIMS a verified state.

    A claim, not a verdict — and the distinction is load-bearing enough to be in the name of what
    this returns. Whether the claim is *true* is the ``identity`` guard's question, and it answers
    it at CRITICAL on every corpus run by comparing the claim against a content-certifying stamp.

    Read from the model's own document records rather than re-parsing: the model already asked
    every document for its header, and asking twice is how two readers of one fact start to
    disagree (`RULES.md` Rule 2, applied to code rather than prose).
    """
    return {
        d["path"]
        for d in documents
        if d.get("tier") and d.get("tier") != _UNGOVERNED and d.get("verified_state") == "verified"
    }


def derive(
    root: Path,
    module_ids: list[str],
    *,
    gatekeepers: dict[str, dict[str, Any]],
    owner: dict[str, str],
    container_document: dict[str, str],
    documents: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    """``{module id -> {"depth": int, "level": str, "evidence": {...}, "stopped_because": str}}``."""
    children: dict[str, int] = {}
    for module_id in module_ids:
        parent = module_id.rsplit(".", 1)[0] if "." in module_id else ""
        if parent:
            children[parent] = children.get(parent, 0) + 1

    # A probe "pins" a module when it IMPORTS it or names it by dotted id / real path. Imports are
    # resolved with `ast` for the same reason the gatekeeper map does it: `from tools.corpus_check
    # .guards import identity` spells neither `tools.corpus_check.guards.identity` nor its path, so
    # a substring test reported 22 modules as unpinned while a retained counter-example was
    # demonstrably exercising them — including all nine corpus-check guards.
    test_sources = [
        (root / rel).read_text(encoding="utf-8", errors="replace")
        for rel in tracked_paths(root, "tools/tests/*.py")
        if (root / rel).is_file()
    ]
    test_blob = "".join(test_sources)
    test_imports: set[str] = set()
    for source in test_sources:
        test_imports |= imported_modules(source)
    verified = _verified_documents(documents)

    out: dict[str, dict[str, Any]] = {}
    for module_id in module_ids:
        rel = _module_file(root, module_id)
        gate = gatekeepers.get(module_id, {})
        doc = container_document.get(owner.get(module_id, ""), "")

        evidence = {
            "exists": True,
            "purpose": bool(_docstring(root, module_id)),
            "enumerable": bool(children.get(module_id, 0)) or _public_definitions(root, module_id) > 0,
            # Documented at rung 3 as "a gate reads it OR it is itself a gate". Both count on
            # purpose — a module that RAISES findings is as connected to the gate layer as one that
            # is read by it — but the docstring now says so, because it previously described only
            # the first half while the code accepted both.
            "gated": bool(gate.get("guarded_by")) or bool(gate.get("emits")),
            # IMPORT or PATH only — a name in a test COMMENT is not a counter-example.
            #
            # The loose token match published six modules at `internals` on evidence that never
            # executes them, `tools.lib.md_table` among them (pinned by a comment). It also lacked
            # the single-segment guard its sibling in `gatekeepers` carries, so `_token_re("tools")`
            # matched the bare English word in every test docstring. Rung 4's whole claim is that a
            # retained probe PINS the module's behaviour; mentioning it does not.
            "pinned": (module_id in test_imports) or (rel in test_blob),
            "verified": bool(doc) and doc in verified,
        }
        ladder = ["exists", "purpose", "enumerable", "gated", "pinned", "verified"]

        depth = 0
        stopped = ""
        for i, key in enumerate(ladder):
            if evidence[key]:
                depth = i
            else:
                stopped = key
                break
        else:
            stopped = ""
        out[module_id] = {
            "depth": depth,
            "level": LEVELS[depth],
            "evidence": evidence,
            "stopped_because": stopped,
        }
    return out


def container_depth(
    module_depths: dict[str, dict[str, Any]], owner: dict[str, str], container_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """A container is only as deep as its shallowest module.

    **Minimum, not average and not maximum.** "How well is this container understood" is decided by
    the part nobody wrote down, exactly as a chain is decided by its weakest link. A mean would let
    thirty well-documented modules hide one that says nothing, which is precisely the shape a
    completeness report exists to surface.
    """
    out: dict[str, dict[str, Any]] = {}
    for cid in container_ids:
        mods = [m for m, c in owner.items() if c == cid]
        depths = [module_depths[m]["depth"] for m in mods if m in module_depths]
        if not depths:
            out[cid] = {"depth": 0, "level": LEVELS[0], "modules": 0, "shallowest": []}
            continue
        low = min(depths)
        at_min = sorted(m for m in mods if module_depths[m]["depth"] == low)
        out[cid] = {
            "depth": low,
            "level": LEVELS[low],
            "modules": len(mods),
            # The TRUE count travels beside the sample, so a renderer can disclose its own overflow
            # instead of printing a truncated list that reads as exhaustive.
            "modules_at_min": len(at_min),
            "shallowest": at_min[:5],
        }
    return out
