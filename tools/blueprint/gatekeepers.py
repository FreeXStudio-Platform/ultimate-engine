"""Which gates guard each module — derived from the gates themselves, never from a table.

THE QUESTION THIS ANSWERS
=========================
*"If I change this module, what will refuse me?"* That is the question an agent actually has before
it edits anything, and before this module the map could not answer it: `blueprint/SYSTEM.md` listed
the guard names and the check ids as flat registries, with nothing tying either to the code they
read. So the answer was a full-tree grep — the cost this whole layer exists to remove.

HOW A GATEKEEPER IS DERIVED — FOUR ROUTES, NOT TWO
==================================================
A registered guard, health check or git hook is a gatekeeper of a module when it **reaches** that
module by any of:

1. **importing it** — resolved with ``ast``, because ``from tools.docgen import adjudication``
   spells neither the dotted id nor the path;
2. **importing a SUBSTANTIVE package that contains it** — a package whose ``__init__.py`` actually
   executes something. Measured, not assumed: ``tools/docgen/__init__.py`` and the root ``tools`` are
   docstring-only, and a verifier mutated the first and watched all eleven of its claimed gatekeepers
   pass, so crediting them was an artefact. ``tools/docgen/hooks/__init__.py`` runs an import (which
   is why the moat must keep it) and ``tools/lib/__init__.py`` runs the shared prose strippers, so
   both ARE reached and credited;
3. **running it as a subprocess** — ``python3 -m tools.docgen.cli`` executes the whole transitive
   import closure of that module, and ``BUILD-01`` really does turn red when any of the 14 renderers
   underneath is broken. A relation blind to this answers *"what will refuse me?"* with silence for
   every module a gate runs rather than imports;
4. **naming it** — the dotted id as a whole token, or its real repository path.

Re-derived from the gate's source on every build, so a gate that stops reaching a module stops
claiming to guard it, and one that starts says so without anybody remembering to update a list.

**What it does NOT claim.** Naming a module in CODE is evidence of a read, not proof of enforcement
— a gate that names a module by path or dotted id, or runs it with `-m`, is credited even if it does
not actually refuse a change to it; tracing what each check truly executes is a static-analysis
project, and a map that over-reports on that axis is cheaper than one that under-reports silently.
What is NOT counted, on any of the four routes, is a module named only in a COMMENT or a DOCSTRING:
all three text routes read a prose-free copy (`OG-216`, extended to the `-m` subprocess route in
`OG-225` after a verifier measured 36 phantom edges the first fix left there). The bound is stated
here rather than left for a verifier to discover, because an unstated bound is how `OG-193` happened.

THE SECOND DIRECTION: WHAT A MODULE EMITS
=========================================
A module that raises findings is itself a gatekeeper, and its gate tokens are the vocabulary the
precedence spine ranks. Those are read with ``_gate_labels_via_ast``, **imported from the health
checks rather than reimplemented**. That import is the whole point: `OG-195` was a gate that stayed
invisible because a second copy of this scan required a constant spelled ``_GATE`` while the real
one was ``GATE``, and its closure note says the resolver is imported by its probe "because that
helper had already been the second consumer of this same root twice". This is the third consumer.
It imports.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from tools.blueprint.model import tracked_paths

# The one AST gate-label resolver in the tree (`OG-195`). Private by name, imported on purpose:
# a third copy of this scan is exactly the defect that row records.
from tools.health.checks import _gate_labels_via_ast
from tools.lib import strip_shell_comments

_HOOKS = ("tools/hooks/pre-commit", "tools/hooks/pre-push")

# The check id an operator greps for, as `checks.py` spells it in every return: "STRUCT-01".
_ID_RE = re.compile(r'"([A-Z]{3,10}-\d{2})"')


def _module_file(root: Path, module_id: str) -> str:
    """The module's real repository path — ``x/y.py`` OR ``x/y/__init__.py`` for a package.

    The first version returned ``module_id.replace(".", "/") + ".py"`` unconditionally, so for
    every PACKAGE (``tools``, ``tools.docgen``, ``tools.corpus_check.guards`` …) it produced a path
    that does not exist and path matching silently never fired for any of them.
    """
    rel = module_id.replace(".", "/")
    if (root / f"{rel}.py").is_file():
        return f"{rel}.py"
    if (root / rel / "__init__.py").is_file():
        return f"{rel}/__init__.py"
    return f"{rel}.py"


def imported_modules(source: str) -> set[str]:
    """Every module a source file IMPORTS, resolved with ``ast`` rather than matched as text.

    **This is the half a substring test cannot see, and it was 15 real relationships wide.**
    ``from tools.docgen import adjudication`` contains neither the dotted id
    ``tools.docgen.adjudication`` nor the path ``tools/docgen/adjudication.py``, so a gate that
    imports and *executes* a module reported as guarding nothing. Measured on this tree: two health
    checks import and run ``adjudication`` — stubbing it turns both RED — while the map listed it
    as guarded by nobody.

    Both halves of a ``from`` are recorded (``a.b`` and ``a.b.c``) because the imported name may be
    a module or a symbol inside one, and only the module set decides which.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return out


# **AN ANCESTOR PACKAGE IS COUNTED ONLY WHEN IT EXECUTES SOMETHING.**
#
# `import tools.docgen.models` really does execute `tools/__init__.py`, so crediting every ancestor
# is *technically* true and produces the "everything guards everything" reading that says nothing:
# with full expansion the root `tools` collected 36 gatekeepers. Dropping ancestors entirely was the
# first correction, and it over-shot — a verifier measured the cost immediately: `tools.docgen.hooks`
# (**the git moat**) fell to `guarded_by: []` and its container dropped two rungs, because both
# hooks reach it by running `python3 -m tools.docgen.hooks.staged_content_scanner`, which imports
# and executes the package.
#
# The rule that matches reality is neither: credit an ancestor when its `__init__.py` has at least
# one non-docstring statement. Measured on this tree — the root `tools` and `tools/docgen` are
# docstring-only (ZERO executable statements), and a verifier proved the point by mutating
# `tools/docgen/__init__.py` and watching all eleven claimed gatekeepers pass; while
# `tools/docgen/hooks/__init__.py`, `tools/corpus_check/__init__.py` and `tools/lib/__init__.py`
# (which holds the shared string/comment strippers, kept in the `__init__` for the layout reason its
# own docstring states) DO run code and are credited.
_SUBPROCESS_RE = re.compile(r"-m[\"',\s]+((?:tools|docs)[\w.]*)")


def _substantive_packages(root: Path, module_ids: list[str]) -> set[str]:
    """Packages whose ``__init__.py`` executes something, so importing a child really reaches them."""
    out: set[str] = set()
    for module_id in module_ids:
        init = root / module_id.replace(".", "/") / "__init__.py"
        if not init.is_file():
            continue
        try:
            tree = ast.parse(init.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        if any(
            not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
            for n in tree.body
        ):
            out.add(module_id)
    return out


def _import_closure(root: Path, module_ids: list[str]) -> dict[str, set[str]]:
    """``{module -> every module it transitively imports}``.

    Needed for route 3. A gate that shells out to ``python3 -m tools.docgen.cli`` executes
    everything that module pulls in, and a relation that stopped at the entry point reported 14
    renderers as guarded by nothing while ``BUILD-01`` demonstrably fails when any of them breaks.
    """
    known = set(module_ids)
    direct: dict[str, set[str]] = {}
    for module_id in module_ids:
        rel = _module_file(root, module_id)
        try:
            source = (root / rel).read_text(encoding="utf-8")
        except OSError:
            continue
        direct[module_id] = {m for m in imported_modules(source) if m in known}

    # A PER-NODE walk with its own visited set. The first version memoised across nodes while
    # sharing one `seen` set as a cycle guard, which made a cached answer depend on the ORDER the
    # graph was traversed in — and `direct` holds sets, whose iteration order changes with
    # `PYTHONHASHSEED`. So `blueprint build` and `blueprint verify`, being separate processes,
    # disagreed about a committed artifact. Reachability is a well-defined set; computing it must
    # not depend on the order it is discovered in.
    closure: dict[str, set[str]] = {}
    for module_id in module_ids:
        reached: set[str] = set()
        seen = {module_id}
        stack = [module_id]
        while stack:
            node = stack.pop()
            for child in direct.get(node, ()):
                if child in seen:
                    continue
                seen.add(child)
                reached.add(child)
                stack.append(child)
        closure[module_id] = reached
    return closure


def _token_re(module_id: str) -> re.Pattern[str]:
    """The dotted id as a WHOLE token — never as the prefix of a longer one.

    ``tools.docgen`` must not match inside ``tools.docgen.cli``. The bare substring test did, which
    is why the root node ``tools`` collected 38 gatekeepers (every gate whose source contains the
    string ``tools`` anywhere, including in a path) and why the three gates ``SYSTEM.md`` printed
    for its highest-risk module were all prefix artefacts that never name it.
    """
    return re.compile(r"(?<![\w.])" + re.escape(module_id) + r"(?![\w.])")


def _prose_free(source: str, *, python: bool) -> str:
    """Source with COMMENTS (and, for Python, DOCSTRINGS) removed (`OG-216`).

    A module named only in a comment or a docstring must not manufacture a ``guarded_by`` edge — the
    same scan-text-not-structure class as `OG-166`/L-24, found by a Phase-7 verifier who added one
    comment to a check and watched an unrelated module gain a gatekeeper in the published map. **Code
    STRINGS are kept**: a ``"-m", "tools.x"`` in an actual call, or a path literal, is a real
    reference. `ast.unparse` drops comments for free (they are never in the AST); docstrings are the
    one prose form that survives it, so they are blanked first.
    """
    if python:
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            return source  # unparseable → fall back to raw, never LESS strict than before
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body[0] = ast.Expr(value=ast.Constant(value=Ellipsis))
        try:
            return ast.unparse(tree)
        except Exception:  # noqa: BLE001 — defensive: any unparse failure keeps the raw source
            return source
    # Shell: drop `#` comments at a real boundary — line start, or after whitespace/`;`/`&`/`|`/`(`/
    # `)` — via the shared stripper, which also preserves `$#`/`${#…}`. The old `\s#` strip saw only a
    # whitespace-preceded `#`, so a `;#` comment could still manufacture a `guarded_by` edge
    # (`OG-216`, the same class one language over from the JS/shell env-read fix). A `#` inside a
    # quoted string is not a comment, but a module id sitting there would still be a real mention.
    return strip_shell_comments(source)


def _names_module(
    source: str, module_id: str, module_rel: str, imports: set[str], *, inert: bool = False
) -> bool:
    """Does this gate reach that module — by import, by whole-token dotted id, or by real path?

    Three ways, because gates in this tree use all three: health checks import, guards cite paths in
    code, and the shell hooks invoke modules with ``python3 -m``. Any one is evidence of a read.

    **``source`` is passed COMMENT- and DOCSTRING-free** (`_prose_free`, `OG-216`): a module named
    only in prose no longer counts, because a comment fabricating a published ``guarded_by`` claim is
    the scan-text-not-structure defect this engine exists to catch. The import route reads the
    pre-computed AST set, which was always clean. What remains true: a real path literal or dotted id
    in actual code is a read.
    """
    if module_id in imports:
        return True
    if module_rel and module_rel in source:
        return True
    if inert:
        # An INERT package (its `__init__.py` runs nothing) reached only by TEXT is a false
        # positive: the string `tools.docgen` occurs in every `from tools.docgen import child`, so
        # a token match credits the parent for a claim about the child. Its real path still counts —
        # a gate naming `tools/docgen/__init__.py` means that file — but nothing else does, because
        # nothing can refuse a change to a file that executes no statements.
        return False
    if "." not in module_id:
        # A SINGLE-SEGMENT name is too generic to match as prose. `tools` appears as a bare
        # directory name in every gate that walks the tree (`ctx.root / "tools"`,
        # `(root / "tools").rglob("*.py")`), and matching those left the root node claiming 27
        # gatekeepers. Those gates read the tree; they do not read `tools/__init__.py`, which is
        # zero bytes. For a top-level package only an explicit import or its real file path counts.
        return False
    return bool(_token_re(module_id).search(source))


def _health_check_sources(root: Path) -> dict[str, str]:
    """Each health check's id mapped to its OWN source segment, not the whole 2,700-line module.

    Splitting by function matters: every check lives in one file, so a whole-file scan would report
    all 36 checks as gatekeepers of every module the file mentions anywhere — a map in which
    everything guards everything, which is the same as saying nothing.
    """
    path = root / "tools/health/checks.py"
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError):
        return {}

    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("check_"):
            continue
        segment = ast.get_source_segment(source, node) or ""
        # The check id is the one an operator greps for; the function name is an implementation
        # detail. `checks.py` writes the id as a quoted "STRUCT-01"-shaped literal in every return.
        ids = sorted(set(_ID_RE.findall(segment)))
        out[ids[0] if ids else node.name] = segment
    return out


def _guard_sources(root: Path) -> dict[str, str]:
    """Each registered guard's name mapped to its module source.

    The registry is imported rather than globbed, so a guard file that exists but is not registered
    is correctly absent: an unregistered guard does not run and therefore guards nothing.
    """
    try:
        from tools.corpus_check.guards import GUARDS
    except Exception:  # noqa: BLE001 — a registry that cannot import IS the finding, reported empty
        return {}
    out: dict[str, str] = {}
    for name, fn in GUARDS:
        module = getattr(fn, "__module__", "")
        rel = module.replace(".", "/") + ".py"
        try:
            out[name] = (root / rel).read_text(encoding="utf-8")
        except OSError:
            continue
    return out


def _hook_sources(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in _HOOKS:
        try:
            out["hook:" + Path(rel).name] = (root / rel).read_text(encoding="utf-8")
        except OSError:
            continue
    return out


def build(root: Path, module_ids: list[str]) -> dict[str, dict[str, Any]]:
    """``{module id -> {"guarded_by": [...], "emits": [...]}}`` for every module.

    Both directions in one record because they are the two halves of one question: what will stop
    me if I change this, and what does changing this stop for everybody else.
    """
    gates: dict[str, str] = {}
    gates.update({f"guard:{k}": v for k, v in _guard_sources(root).items()})
    gates.update({f"check:{k}": v for k, v in _health_check_sources(root).items()})
    gates.update(_hook_sources(root))

    emitted: dict[str, list[str]] = {}
    for rel in tracked_paths(root, "*.py"):
        try:
            labels = _gate_labels_via_ast((root / rel).read_text(encoding="utf-8"))
        except OSError:
            continue
        if labels:
            emitted[rel.removesuffix(".py").replace("/", ".").removesuffix(".__init__")] = sorted(labels)

    # Resolved ONCE per gate rather than once per (gate, module) pair: 40 gates x 105 modules would
    # otherwise re-parse every gate source 105 times.
    substantive = _substantive_packages(root, module_ids)
    # An INERT package — one whose `__init__.py` runs nothing — is never *read* in any sense that
    # can refuse a change, however many of its children a gate imports. `from tools.docgen import
    # adjudication` credits `tools.docgen` in any honest reading of the import statement, and a
    # verifier measured what that credit is worth: it mutated `tools/docgen/__init__.py` and ran all
    # eleven gates the map claimed guarded it. Zero refused. So the import-derived credit is dropped
    # for inert packages — while route 4 still applies, because a gate that NAMES the package by
    # path or dotted id is making a different, real claim about it.
    inert = {
        m for m in module_ids
        if (root / m.replace(".", "/") / "__init__.py").is_file()
    } - substantive
    closure = _import_closure(root, module_ids)
    known = set(module_ids)

    # Comment- and docstring-free once per gate, so a module named only in prose cannot manufacture
    # a `guarded_by` edge (`OG-216`). Route 1 (imports, resolved by `ast`) and route 2 (substantive
    # ancestors OF those imports) are structural and safe on the raw source. Routes 3 and 4 are TEXT
    # scans and read THIS stripped copy: a verifier measured **36 phantom edges** when route 3 read
    # the raw source — a `-m tools.docgen.cli` merely RECOUNTED inside `built_claims`'s docstring
    # credited that command's whole import closure with a text guard that executes nothing (`OG-225`,
    # the `OG-216` class surviving in the one route the first fix left reading text while its comment
    # claimed otherwise).
    prose_free = {
        name: _prose_free(src, python=not name.startswith("hook:"))
        for name, src in gates.items()
    }

    gate_reach: dict[str, set[str]] = {}
    for name, source in gates.items():
        reach = imported_modules(source)
        # Route 2 — a SUBSTANTIVE ancestor is genuinely executed by importing its child.
        for imported in list(reach):
            parts = imported.split(".")
            for i in range(1, len(parts)):
                ancestor = ".".join(parts[:i])
                if ancestor in substantive:
                    reach.add(ancestor)
        # Route 3 — `python3 -m X` executes X and everything X transitively imports. Read from the
        # PROSE-FREE source: a `-m X` inside a comment or docstring is a mention, not a run.
        for invoked in _SUBPROCESS_RE.findall(prose_free[name]):
            if invoked in known:
                reach.add(invoked)
                reach |= closure.get(invoked, set())
                for target in {invoked, *closure.get(invoked, set())}:
                    parts = target.split(".")
                    for i in range(1, len(parts)):
                        ancestor = ".".join(parts[:i])
                        if ancestor in substantive:
                            reach.add(ancestor)
        gate_reach[name] = reach - inert

    out: dict[str, dict[str, Any]] = {}
    for module_id in module_ids:
        rel = _module_file(root, module_id)
        guarded = sorted(
            name for name in gates
            if _names_module(prose_free[name], module_id, rel, gate_reach[name], inert=module_id in inert)
        )
        out[module_id] = {"guarded_by": guarded, "emits": emitted.get(module_id, [])}
    return out
