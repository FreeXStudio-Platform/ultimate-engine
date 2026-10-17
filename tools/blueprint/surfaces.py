"""The six surfaces Phase 4 had to open the tree for — derived, so the map can answer them.

WHY THESE SIX, AND NOT SIX OTHERS
=================================
This module is not a guess about what an agent might want. Phase 4 was `blueprint/SYSTEM.md`'s
first real test and was told to record **what it had to open anyway**. Six things came back, and
every one of them is here:

======================== ==================================================================
surface                  what the map could not answer before
======================== ==================================================================
``schemas``              the JSON schemas under ``tools/docgen/schemas/`` — the map never
                         mentioned them at all
``configuration``        the configuration surface and its environment variables
``cli``                  the command and flag inventory, per entry point
``guards``               the guard contract, and what it costs to register one
``figure_kinds``         the figure-kind and sidecar-spec inventory
``health_checks``        what each check ASSERTS, where the map listed only its id
======================== ==================================================================

THE RULE EVERY SURFACE OBEYS
============================
**Each is derived from the artifact that owns it, and never from a copy.** The schemas are read as
JSON, the configuration from the config file plus the resolver's own source, the CLI from each
module's ``argparse`` calls, the guards from the imported registry, the figure kinds from
``_FIGURE_KINDS`` itself, and the checks from their own docstrings. Nothing here is a list somebody
maintains, which is the only reason it can be trusted a phase from now (`RULES.md` Rule 2).

WHY THE CLI IS READ WITH ``ast`` AND NOT BY IMPORTING EVERY PARSER
=================================================================
Exactly one entry point in this tree exposes a parser factory (``tools.docgen.cli.build_parser``);
the other ten build their parser inside ``main()``, where nothing can reach it without running the
program. Refactoring ten modules to expose a factory, so that one map could import them, would be
the map changing the system to suit itself. Reading the ``add_parser``/``add_argument`` calls
statically costs nothing and works for all eleven — including the ones added after this was
written.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from tools.blueprint.model import tracked_paths
from tools.lib import strip_js_comments, strip_js_strings, strip_shell_comments

# Schemas are found by PATTERN across the tracked tree, never by a pinned directory. The first
# version pinned `tools/docgen/schemas`, and an independent verifier measured the cost: four real
# draft-07 schemas under `tools/visual-engine/schemas/` were invisible under a section headed
# "JSON schemas" with no scoping caveat. A hardcoded scope inside a derived surface is the same
# defect as a hand-kept list — it just fails later and more quietly.
_SCHEMA_GLOB = "*.schema.json"


def _first_line(text: str | None) -> str:
    """The first SENTENCE of a docstring — what the thing asserts, without the essay under it.

    Sentence, not line. The first version took the first line and published
    *"SUITE-03 — the artifact index must resolve, over a NON-EMPTY set, and the dashboard must"* —
    a fragment stopping mid-clause, because the docstring wraps. One row of 36, and it was the row
    a reader would have had to open the source to finish.
    """
    lines: list[str] = []
    for line in (text or "").strip().splitlines():
        stripped = line.strip()
        if not stripped:
            break  # end of the leading paragraph
        lines.append(stripped)
    paragraph = " ".join(lines)
    for end in (". ", ".\t"):
        if end in paragraph:
            return paragraph.split(end, 1)[0] + "."
    return paragraph


# ── 1. schemas ──────────────────────────────────────────────────────────────────────────────────
def schemas(root: Path) -> list[dict[str, Any]]:
    """Every JSON schema, with the shape it documents.

    ``OG-39`` decided these are **documentation of a shape, not a validation layer** — nothing
    loads them, deliberately, because wiring ``jsonschema`` would add a second enforcer of rules
    three modules already enforce in code. That decision is exactly why they belong in the map: a
    reader who cannot see them assumes the shape is undocumented and re-derives it from the
    dataclass.
    """
    out: list[dict[str, Any]] = []
    for rel in sorted(tracked_paths(root, _SCHEMA_GLOB, f"*/{_SCHEMA_GLOB}")):
        try:
            doc = json.loads((root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            out.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
            continue
        props = doc.get("properties")
        required = [str(r) for r in doc.get("required", []) or []]
        where = "top level"
        if not required:
            # An ARRAY schema keeps its row shape in `$defs`, so reading only the top level
            # reported `doc_manifest.schema.json` as having no required fields — telling a reader
            # that DOC_MANIFEST rows are unconstrained, when they carry seven. That is exactly the
            # failure this section's own preamble says it exists to prevent.
            defs = doc.get("$defs") or doc.get("definitions") or {}
            # Prefer the definition the document actually REFERENCES. Taking the alphabetically
            # first `$defs` entry with a `required` list is arbitrary, and on a schema with two it
            # publishes the wrong one — a verifier planted exactly that.
            ref = ""
            items = doc.get("items")
            if isinstance(items, dict) and isinstance(items.get("$ref"), str):
                ref = items["$ref"].rsplit("/", 1)[-1]
            order = ([ref] if ref in defs else []) + sorted(k for k in defs if k != ref)
            for name in order:
                sub = defs.get(name)
                if isinstance(sub, dict) and sub.get("required"):
                    required = [str(r) for r in sub["required"]]
                    where = f"$defs.{name}"
                    break
        out.append({
            "path": rel,
            "title": str(doc.get("title", "")),
            "describes": str(doc.get("description", ""))[:200],
            "required": sorted(required),
            "required_from": where,
            "properties": sorted(props) if isinstance(props, dict) else [],
        })
    return out


# ── 2. configuration ────────────────────────────────────────────────────────────────────────────
# HOW AN ENVIRONMENT VARIABLE IS PROVEN LIVE — by a READ, in the language of the file, resolving
# the constant the read goes through. Never by its name appearing in text.
#
# **This is the OG-166/OG-195/L-24 class, found again in this surface (`OG-215`).** The first version
# scanned every file for the token `ENGINE_[A-Z_]+` and published `ENGINE_ROOT`, a JS const, as live.
# The rewrite after that applied one set of regexes — Python AND JS AND shell — to EVERY file at once,
# over raw text, and three defects survived, each measured by a verifier:
#   * **a phantom**: `ENGINE_VERSION` is `export const ENGINE_VERSION = …package.json…` in
#     `render.mjs`, used only in template literals `v${ENGINE_VERSION}` — and the SHELL pattern
#     `\$\{?NAME\b` matched that template literal, so a JS constant was published as an env override
#     that changes nothing (the exact class the previous fix claimed to have closed for `ENGINE_ROOT`);
#   * **a docstring**: `ENGINE_CONFIDENTIAL_DIR` was credited to `staged_content_scanner.py`, whose
#     only mention of it is a docstring quoting a past attack — L-24 verbatim, a ground truth widened
#     by prose;
#   * **invisible constant-name reads**: `ENGINE_CONFIG_PATH` — "the one to know" — is read through a
#     module constant (`os.environ.get(_CONFIG_PATH_ENV)`, `process.env[CONFIG_PATH_ENV]`), so the
#     literal string is nowhere near the call and the pattern missed the primary resolver entirely.
#
# So the read is now derived per language, from structure: Python via `ast` (which cannot see a
# docstring as a call and resolves a module constant to its value), JS via `process.env.X` /
# `process.env[X]` with light const resolution, shell via `$X`/`${X}`/`X=`. Each language's prose is
# removed first with the shared `tools.lib` strippers — a JS `//`/`/* */` comment or string, a
# shell `;#` or ` #` comment — so a name that only appears in prose matches nothing, in EVERY
# language and not just Python (`OG-215`: the first fix made Python structural and left JS and shell
# scanning raw text). A pattern applied to the wrong language matches nothing either.
_ENV_SOURCE_GLOBS = ("*.py", "*/*.py", "*/*/*.py", "*/*/*/*.py",
                     "*.mjs", "*/*.mjs", "*/*/*.mjs",
                     "*.js", "*/*.js", "*/*/*.js", "*.cjs", "*/*.cjs", "*/*/*.cjs",
                     "*.sh", "*/*.sh", "*/*/*.sh", "tools/hooks/*")


def _envvar_sections(root: Path) -> set[str]:
    """Config sections whose entries a resolver actually routes through their declared ``envVar``.

    Derived from both resolvers rather than listed: the Python side names its sections in
    ``_field``-family calls, the JS side in ``field('...')``, and both honour ``tools`` through
    their tool-path lookup. A section read by raw dictionary access — ``browsers``, ``security`` —
    never consults an ``envVar``, which is exactly why declaring one there produced a variable that
    changed nothing.
    """
    sections = {"tools"}  # tool_path / toolPath both consult cfg["envVar"]
    try:
        tree = ast.parse((root / "tools/docgen/engine_config.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "_doc_system_child":
                sections.add("docSystem")
            elif node.func.id in ("_field", "_path_field", "_safe_relative"):
                literals = [a.value for a in node.args if isinstance(a, ast.Constant)]
                if literals and isinstance(literals[0], str):
                    sections.add(literals[0])
    try:
        mjs = (root / "tools/lib/engine-config.mjs").read_text(encoding="utf-8")
    except OSError:
        mjs = ""
    sections.update(re.findall(r"field\(\s*['\"]([A-Za-z]+)['\"]", mjs))
    return sections


def _engine_names(candidates: set[str]) -> set[str]:
    """Keep only real `ENGINE_*` variable names — not a `ENGINE_SKIP_*` prose prefix."""
    return {n for n in candidates if n.startswith("ENGINE_") and not n.endswith("_")}


def _py_env_reads(source: str) -> set[str]:
    """`ENGINE_*` names a PYTHON module reads from the environment — from the AST, not the text.

    `ast` cannot mistake a docstring for a call (the L-24 defect that credited a scanner with a
    variable it only names in prose), and it resolves a module-level constant to its value, so
    `os.environ.get(_CONFIG_PATH_ENV)` is seen as a read of `ENGINE_CONFIG_PATH` even though the
    literal string is nowhere near the call (`OG-166`/`OG-195`: resolve, do not scan).

    STATED BOUNDS at the edge of the shapes covered (`OG-224`, all latent — a verifier confirmed no
    tracked file trips them). `_is_environ`/`_is_getenv` accept ANY attribute named `environ`/`getenv`
    on any object, so `cfg.environ["X"]` would over-count; and these are missed READS (false
    negatives, the safe direction): an aug-assign `os.environ["X"] += v` (its Subscript target is
    ctx=Store), `.setdefault(...)`, and `os.environ` bound to a local alias first. `.pop` is missed
    deliberately — counting it would re-credit test teardown as a "reader", the exact defect the
    `ctx is ast.Load` fix removed.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    consts = _module_string_constants(tree)

    def _literal(node: ast.expr | None) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name) and node.id in consts:
            return consts[node.id]
        return None

    def _is_environ(node: ast.expr) -> bool:
        # os.environ  OR  a bare `environ` imported from os
        return (isinstance(node, ast.Attribute) and node.attr == "environ") or (
            isinstance(node, ast.Name) and node.id == "environ"
        )

    def _is_getenv(node: ast.expr) -> bool:
        # os.getenv  OR  a bare `getenv` imported from os
        return (isinstance(node, ast.Attribute) and node.attr == "getenv") or (
            isinstance(node, ast.Name) and node.id == "getenv"
        )

    found: set[str] = set()
    for node in ast.walk(tree):
        # os.environ.get(X) / environ.get(X) / os.getenv(X) / getenv(X)
        if (
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                 and _is_environ(node.func.value))
                or _is_getenv(node.func)
            )
            and node.args
        ):
            name = _literal(node.args[0])
            if name:
                found.add(name)
        # os.environ[X] / environ[X] — a READ only. `os.environ["X"] = v` is a Subscript too, but
        # in Store context: it WRITES the variable, it does not read one (an adversarial verifier
        # found §6 crediting a test as a "reader" of two variables it only sets).
        elif (
            isinstance(node, ast.Subscript)
            and _is_environ(node.value)
            and isinstance(node.ctx, ast.Load)
        ):
            name = _literal(node.slice)
            if name:
                found.add(name)
        # X in os.environ / X not in os.environ
        elif isinstance(node, ast.Compare) and any(
            isinstance(op, (ast.In, ast.NotIn)) for op in node.ops
        ):
            if any(_is_environ(c) for c in node.comparators):
                name = _literal(node.left)
                if name:
                    found.add(name)
    return _engine_names(found)


_JS_CONST_RE = re.compile(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*['\"](ENGINE_[A-Z0-9_]+)['\"]")


def _js_env_reads(source: str) -> set[str]:
    """`ENGINE_*` names a JS module reads via `process.env` — including through a `const` alias.

    `process.env.X` and `process.env["X"]` are direct reads; `process.env[CONST]` where
    `const CONST = "ENGINE_X"` is the shape the primary JS resolver uses for `ENGINE_CONFIG_PATH`.
    A JS module CONSTANT used only in a template literal — `v${ENGINE_VERSION}` — is NOT a read.

    Comments and strings are removed first, in an order that matters (`OG-215`): a JS `//`/`/* */`
    comment or a string literal `"process.env.ENGINE_X"` must not manufacture a phantom read — but
    the bracket-key form `process.env["ENGINE_X"]` reads a name that IS a string, so those keys are
    captured BEFORE strings are blanked. A verifier proved the dot form and a string both slipped
    through the old raw-text scan; stripping strings first would then have erased the legitimate key.
    """
    no_comments = strip_js_comments(source)
    # The key literal of a bracket read IS the read — capture it before strings are blanked.
    found: set[str] = set(
        re.findall(r"""process\.env\[\s*['"](ENGINE_[A-Z0-9_]+)['"]\s*\]""", no_comments)
    )
    aliases = {alias: name for alias, name in _JS_CONST_RE.findall(no_comments)}
    # Now blank strings so a `process.env.X` sitting inside a string literal is not counted a read.
    code = strip_js_strings(no_comments)
    found |= set(re.findall(r"process\.env\.(ENGINE_[A-Z0-9_]+)\b", code))
    for alias in re.findall(r"process\.env\[\s*([A-Za-z_$][\w$]*)\s*\]", code):
        if alias in aliases:
            found.add(aliases[alias])
    return _engine_names(found)


# Shell reads: $X / ${X} / X=... at the start of a statement. Comments (`#` at a real boundary —
# line start, or after whitespace/`;`/`&`/`|`/`(`/`)`) are removed first so a shell file that merely
# names a variable in prose is not counted. The old strip only saw a whitespace-preceded ` #`, so a
# `;#` comment — a real shell comment — still manufactured a read (`OG-215`).
_SH_READ_RE = (
    re.compile(r"\$\{?(ENGINE_[A-Z0-9_]+)\b"),
    re.compile(r"(?m)^\s*(ENGINE_[A-Z0-9_]+)="),
)


def _sh_env_reads(source: str) -> set[str]:
    """`ENGINE_*` names a shell script reads, with `#` comments removed first (`strip_shell_comments`
    handles `;#` and preserves `$#`/`${#…}`)."""
    body = strip_shell_comments(source)
    found: set[str] = set()
    for pattern in _SH_READ_RE:
        found |= set(pattern.findall(body))
    return _engine_names(found)


def _env_reads_in_file(rel: str, source: str) -> set[str]:
    """Dispatch to the reader for THIS file's language. A pattern for another language matches
    nothing, which is the whole fix — a shell `${X}` pattern used to match a JS template literal."""
    suffix = Path(rel).suffix.lower()
    if suffix == ".py":
        return _py_env_reads(source)
    if suffix in (".mjs", ".js", ".cjs"):
        return _js_env_reads(source)
    if suffix == ".sh" or rel.startswith("tools/hooks/"):
        return _sh_env_reads(source)
    return set()


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "value"`` bindings.

    Needed because a scan that keeps only ``ast.Constant`` arguments cannot see a default supplied
    as a NAME — and that is not a hypothetical: `_safe_relative(section, key, _DEFAULT_BLUEPRINT_DIR,
    "The blueprint directory would resolve to…")` dropped the Name, shifted the positional args, and
    promoted the CONSEQUENCE SENTENCE into the `default` column for three rows. This is `OG-195`'s
    lesson — *resolve constants, do not scan for literals* — one module over from where it was
    first paid for.
    """
    constants: dict[str, str] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value
    return constants


def environment(root: Path) -> list[dict[str, Any]]:
    """Every ``ENGINE_*`` variable some file actually reads, with the files that read it.

    **Derived from the readers, never from a naming convention.** The first version synthesised
    ``ENGINE_<SECTION>_<KEY>`` for any config row without an explicit ``envVar``, and two
    independent verifiers measured the same result: 8 of 26 rows named a variable that changes
    nothing. Setting `ENGINE_BLUEPRINTDIR`, `ENGINE_BROWSERS_CHROME` or
    `ENGINE_SECURITY_ALLOWRUNTIMECDN` leaves the resolved value untouched, because both resolvers
    consult only a name the config file DECLARES.

    A documented control that does not exist is the same defect class the `built-claims` guard
    exists to catch — in the section whose whole purpose is answering *which variable controls Y*.
    """
    found: dict[str, set[str]] = {}
    for rel in sorted(set(tracked_paths(root, *_ENV_SOURCE_GLOBS))):
        try:
            source = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in _env_reads_in_file(rel, source):
            found.setdefault(name, set()).add(rel)

    # A name DECLARED as `envVar` in engine.config.json is live even though it appears as a literal
    # nowhere: the resolvers read `cfg["envVar"]` dynamically. Verified, not assumed —
    # `ENGINE_PYTHON_BIN` is a literal in no source file, and setting it moves `tool_path("python")`
    # from /opt/homebrew/bin/python3 to the value given.
    #
    # **But only for the sections a resolver actually routes that way**, and that set is derived
    # too. `browsers` and `security` are read by raw dictionary access in the JS resolver and never
    # consult an `envVar` at all, so admitting every declaration would re-create the very defect
    # this function exists to fix — a verifier proved it by adding one `envVar` key to
    # `security.allowRuntimeCDN` and watching a dead variable reappear as live.
    try:
        cfg = json.loads((root / "engine.config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    honoured = _envvar_sections(root)
    for section, body in cfg.items():
        if not isinstance(body, dict) or section not in honoured:
            continue
        for key, value in body.items():
            if isinstance(value, dict) and value.get("envVar"):
                found.setdefault(str(value["envVar"]), set()).add(
                    f"engine.config.json ({section}.{key}, read dynamically)"
                )
    return [
        {"env_var": name, "read_by": sorted(readers)}
        for name, readers in sorted(found.items())
    ]


def configuration(root: Path) -> list[dict[str, Any]]:
    """Every setting in ``engine.config.json``, and the variable that overrides it IF ONE EXISTS.

    Precedence is **env var > config file > built-in default**. An ``env_var`` of ``""`` means the
    setting has no environment override — which is the honest answer for most of them, and is not
    the same as a variable nobody has documented.
    """
    out: list[dict[str, Any]] = []
    try:
        cfg = json.loads((root / "engine.config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [{"error": f"engine.config.json unreadable: {type(exc).__name__}: {exc}"}]

    live = {row["env_var"] for row in environment(root)}

    for section, body in sorted(cfg.items()):
        if section.startswith(("$", "_")) or not isinstance(body, dict):
            continue
        for key, value in sorted(body.items()):
            if key.startswith("_"):
                continue
            env = ""
            default: Any = value
            if isinstance(value, dict):
                env = str(value.get("envVar", ""))
                default = value.get("value", value.get("path", None))
                if default is None and value.get("pathFallback"):
                    # `path: null` is not "no default" — it means "search these, in order".
                    default = "PATH search: " + ", ".join(str(x) for x in value["pathFallback"])
            out.append({
                "section": section,
                "key": key,
                "env_var": env if env in live else "",
                "default": "" if default is None else str(default),
            })

    # Paths the resolver defaults in CODE rather than in the config file.
    try:
        source = (root / "tools/docgen/engine_config.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError):
        return out
    constants = _module_string_constants(tree)

    def _literal(node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None

    known = {(r["section"], r["key"]) for r in out}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in ("_field", "_path_field", "_safe_relative", "_doc_system_child"):
            continue
        args = [_literal(a) for a in node.args]
        if node.func.id == "_doc_system_child" and len(args) >= 2:
            section, key, default = "docSystem", args[0], args[1]
        elif len(args) >= 3:
            section, key, default = args[0], args[1], args[2]
        elif len(args) >= 2:
            section, key, default = args[0], args[1], ""
        else:
            continue
        if not section or not key or (section, key) in known:
            continue
        known.add((section, key))
        out.append({
            "section": section,
            "key": key,
            "env_var": "",
            "default": default or "",
            "declared_in": "resolver default (no row in engine.config.json)",
        })
    return sorted(out, key=lambda r: (r["section"], r["key"]))


# ── 3. the CLI ──────────────────────────────────────────────────────────────────────────────────
def _parser_surface(source: str) -> tuple[list[str], list[dict[str, Any]]]:
    """``(global flags, [{command, help, flags}])`` from one module's argparse calls.

    Three shapes have to be handled, and the first version of this function got two of them wrong —
    both caught by reading its own output rather than by trusting it, which is why they are named
    here instead of silently fixed:

    * **assigned subparsers** — ``p_build = sub.add_parser("build")`` then
      ``p_build.add_argument("-o", ...)``. Tracked by variable, because the flags are the half a
      reader cannot guess and a scan that matched only ``add_parser`` lists commands with no flags.
    * **unassigned subparsers** — ``sub.add_parser("build", help="...")`` as a bare statement, which
      is how ``tools/blueprint/cli.py`` itself is written. The first version required an assignment
      and therefore reported this package as having **no commands at all**, in the map that exists
      to describe it.
    * **nested subparsers** — ``archive cut`` / ``archive list``. The first version flattened them
      to top level, so the map advertised a ``cut`` command that does not exist. A parser variable
      is now linked to the ``add_subparsers()`` call that produced it, so a child command is
      reported under its real invocation.

    Nodes are visited in **source order** (``lineno``), not ``ast.walk`` order, because the parent
    parser is always created before the subparsers object that hangs off it, and that ordering is
    what makes the nesting resolvable in one pass.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return [], []

    var_to_command: dict[str, str] = {}   # parser variable -> full command name
    subvar_to_parent: dict[str, str] = {}  # subparsers variable -> parent parser variable
    group_to_parser: dict[str, str] = {}   # argument-group variable -> the parser it belongs to
    commands: dict[str, dict[str, Any]] = {}
    root_vars: set[str] = set()

    def _register(call: ast.Call, assigned_to: str | None) -> None:
        func = call.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return
        holder = func.value.id
        names = [str(a.value) for a in call.args if isinstance(a, ast.Constant)]
        if not names:
            return
        parent_var = subvar_to_parent.get(holder, "")
        prefix = var_to_command.get(parent_var, "")
        full = f"{prefix} {names[0]}".strip()
        commands[full] = {"command": full, "help": _keyword_str(call, "help"), "flags": []}
        if assigned_to:
            var_to_command[assigned_to] = full

    for node in sorted(ast.walk(tree), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call, target = node.value, node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            func = call.func
            if isinstance(func, ast.Attribute) and func.attr == "add_parser":
                _register(call, target.id)
            elif isinstance(func, ast.Attribute) and func.attr == "add_subparsers":
                if isinstance(func.value, ast.Name):
                    subvar_to_parent[target.id] = func.value.id
            elif isinstance(func, ast.Attribute) and func.attr in (
                "add_mutually_exclusive_group", "add_argument_group"
            ):
                # A GROUP is not a parser, but the arguments hanging off it belong to the parser it
                # was created from. Without this, `tools/docgen/i18n.py` — whose entire interface is
                # three flags in a `add_mutually_exclusive_group(required=True)` — rendered with NO
                # interface at all: heading, then nothing. It is the only entry point in the tree
                # using a group, so the blind spot was narrow and total.
                if isinstance(func.value, ast.Name):
                    holder = func.value.id
                    group_to_parser[target.id] = group_to_parser.get(holder, holder)
            elif (isinstance(func, ast.Attribute) and func.attr == "ArgumentParser") or (
                isinstance(func, ast.Name) and func.id == "ArgumentParser"
            ):
                root_vars.add(target.id)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "add_parser":
                _register(call, None)

    global_flags: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument" or not isinstance(node.func.value, ast.Name):
            continue
        owner = node.func.value.id
        owner = group_to_parser.get(owner, owner)
        names = [str(a.value) for a in node.args if isinstance(a, ast.Constant)]
        if not names:
            continue
        # The `help=` argparse already carries. Discarding it made "which flag controls Y"
        # unanswerable from data that was sitting in the same call the section is derived from —
        # e.g. `--formats` rendered bare, while its real help reads
        # "comma-separated formats: html,json,pdf (default: html)".
        label = "/".join(names)
        helptext = _keyword_str(node, "help")
        entry = f"{label} — {helptext}" if helptext else label
        if owner in var_to_command:
            commands[var_to_command[owner]]["flags"].append(entry)
        elif owner in root_vars:
            global_flags.append(entry)
    for row in commands.values():
        row["flags"] = sorted(set(row["flags"]))
    return sorted(set(global_flags)), [commands[k] for k in sorted(commands)]


def _keyword_str(call: ast.Call, name: str) -> str:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return ""


def _constructs_parser(source: str) -> bool:
    """Does this module CONSTRUCT an ``ArgumentParser``, or merely mention one?

    ``ast``, not a substring, for the reason this file argues everywhere else: *this* module
    contains the text ``ArgumentParser(`` in four comments explaining how the scan works, and a
    substring test therefore nominated the scanner itself as an entry point.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    # Names bound to ArgumentParser, INCLUDING under an alias. `from argparse import ArgumentParser
    # as AP` then `AP(...)` was invisible to a check that only knew the bare name — a verifier
    # planted exactly that as a runnable entry point and it never appeared.
    bound = {"ArgumentParser"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "argparse":
            bound.update(a.asname or a.name for a in node.names if a.name == "ArgumentParser")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "ArgumentParser":
            return True
        if isinstance(func, ast.Name) and func.id in bound:
            return True
    return False


def _invocation(root: Path, rel: str) -> str:
    """How you ACTUALLY invoke the entry point in ``rel``.

    **The rule, and why it is a rule rather than a table.** ``python3 -m <package>`` works only when
    that package has a ``__main__.py``; otherwise Python refuses with *"cannot be directly
    executed"*. So the invocation is the package when a ``__main__.py`` exists beside the parser,
    and the module's own dotted id otherwise.

    The first version was a hand-written dict, and it published
    ``python3 -m tools.project_index`` — a command that **cannot run**, because that package has no
    ``__main__.py``. The map advertised a command that does not exist, which is the precise failure
    this whole layer exists to prevent. Deriving it also fixed the inverse: entry points added later
    appear without anybody remembering the dict.
    """
    module_id = rel.removesuffix(".py").replace("/", ".")
    package = module_id.rsplit(".", 1)[0]
    if module_id.endswith(".__main__"):
        return f"python3 -m {package}"
    main = root / package.replace(".", "/") / "__main__.py"
    if main.is_file():
        # The package slot belongs to the module `__main__.py` ACTUALLY RUNS, not to whichever
        # parser module sorts first. A verifier planted a second parser in `tools/health/` and it
        # took the `python3 -m tools.health` slot, publishing a flag that errors and hiding the
        # seven real ones. Ask `__main__.py` which module it delegates to.
        try:
            delegated = main.read_text(encoding="utf-8")
        except OSError:
            delegated = ""
        leaf = module_id.rsplit(".", 1)[-1]
        if module_id in delegated or f" {leaf}" in delegated or f".{leaf}" in delegated:
            return f"python3 -m {package}"
    return f"python3 -m {module_id}"


def cli(root: Path) -> list[dict[str, Any]]:
    """Every entry point's command and flag inventory, keyed by how you actually invoke it.

    The SET is derived: any tracked Python module that constructs an ``ArgumentParser`` is an entry
    point. A verifier proved the previous hand-written dict blind by adding a real, runnable module
    that never appeared in a fresh build.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in sorted(tracked_paths(root, "*.py", "*/*.py", "*/*/*.py", "*/*/*/*.py")):
        try:
            source = (root / rel).read_text(encoding="utf-8")
        except OSError:
            continue
        if rel.startswith("tools/tests/"):
            continue  # probes construct parsers to test them; they are not entry points
        if not _constructs_parser(source):
            continue
        flags, commands = _parser_surface(source)
        if not flags and not commands:
            continue
        invocation = _invocation(root, rel)
        if invocation in seen:
            continue
        seen.add(invocation)
        out.append({
            "invocation": invocation,
            "module": rel,
            "global_flags": flags,
            "commands": commands,
        })
    return sorted(out, key=lambda r: r["invocation"])


# ── 4. the guard contract ───────────────────────────────────────────────────────────────────────
def guards(root: Path) -> list[dict[str, Any]]:
    """Every registered guard, in run order, with what it checks.

    Run order is not alphabetical and is not incidental: the textual guards are milliseconds and
    their findings are actionable immediately, so they go first; ``rendered-output`` builds real
    documents and goes last. Preserving that order in the map is the difference between a registry
    and a list.
    """
    try:
        from tools.corpus_check.guards import GUARDS
    except Exception as exc:  # noqa: BLE001 — a registry that cannot import IS the finding
        return [{"error": f"{type(exc).__name__}: {exc}"}]

    out: list[dict[str, Any]] = []
    for order, (name, fn) in enumerate(GUARDS, 1):
        module = getattr(fn, "__module__", "")
        rel = module.replace(".", "/") + ".py"
        doc = ""
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
            doc = _first_line(ast.get_docstring(tree))
        except (OSError, SyntaxError, ValueError):
            pass
        out.append({"order": order, "guard": name, "module": rel, "checks": doc})
    return out


def guard_contract() -> dict[str, Any]:
    """What a guard IS, and what registering one costs — the half a signature does not tell you.

    The cost is stated as **two edits** because that is what the registry's own docstring measured
    and corrected (`OG-147`): it used to say "one line to ``GUARDS``", which is the optimistic half
    of a two-part edit. A map that repeated the optimistic number would recreate the defect the
    registry already fixed.
    """
    return {
        "signature": "run(corpus: Corpus) -> GuardResult",
        "module": "tools/corpus_check/model.py",
        "registry": "tools/corpus_check/guards/__init__.py",
        "to_register": [
            "add the import to `tools/corpus_check/guards/__init__.py`",
            "add the `(GUARD, run)` pair to `GUARDS`, in the run-order position it belongs in",
            (
                "run `python3 -m tools.blueprint build` and commit the regenerated `blueprint/` "
                "files — the guard registry is part of the derived map, so a new guard makes it "
                "stale and the retained suite fails the push until it is rebuilt"
            ),
        ],
        "cost_note": (
            "Three edits, not two. It was two until Phase 5 put the guard registry into the "
            "derived map — a verifier registered a guard with exactly the two documented edits and "
            "left the tree push-blocked, with `blueprint: STALE` on five files. The phase that "
            "invalidated the number is the phase that owes the correction."
        ),
        "results": ["passed(...)", "failed(...)", "skipped(...)"],
        "invariants": [
            "a finding names a line — `path:line`, or `path` with line 0 for a whole-file finding",
            (
                "a guard reports `checked`, and a `floor` below which a clean run is a FAILURE, "
                "because a guard that examined nothing has not passed (`LESSONS.md` L-19)"
            ),
            "SKIP is never a pass — it means the guard could not run and its question is open",
        ],
    }


# ── 5. figure kinds ─────────────────────────────────────────────────────────────────────────────
def figure_kinds() -> list[dict[str, Any]]:
    """Every figure ``kind``, its sidecar loader, its renderer, and whether it carries numbers.

    ``carries_data`` is the field RULEBOOK L16 turns into a gate: a kind that puts a number in
    front of a reader must name a resolvable source. It is declared per kind rather than inferred
    from the spec class, because ``VisualSpec`` is shared by four structural kinds that render no
    quantity at all — inferring would demand provenance from every flowchart in the corpus.
    """
    try:
        from tools.docgen.generator import _FIGURE_KINDS
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"{type(exc).__name__}: {exc}"}]
    out: list[dict[str, Any]] = []
    for kind, spec in sorted(_FIGURE_KINDS.items()):
        out.append({
            "kind": kind,
            "carries_data": bool(spec.carries_data),
            "loads_with": getattr(spec.load, "__qualname__", str(spec.load)),
            "renders_with": (
                f"{getattr(spec.render, '__module__', '')}."
                f"{getattr(spec.render, '__qualname__', str(spec.render))}"
            ),
        })
    return out


# ── 6. health checks ────────────────────────────────────────────────────────────────────────────
def health_checks(root: Path) -> list[dict[str, Any]]:
    """Every check's id and **what it asserts** — the gap the map's flat id list left open.

    Read from each function's own docstring, in ``CHECKS`` order, because execution order is part
    of the answer: a structure check failing explains three consistency checks failing after it.
    """
    try:
        from tools.health.checks import CHECKS
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"{type(exc).__name__}: {exc}"}]

    segments: dict[str, str] = {}
    try:
        source = (root / "tools/health/checks.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                segments[node.name] = ast.get_source_segment(source, node) or ""
    except (OSError, SyntaxError, ValueError):
        pass

    id_re = re.compile(r'"([A-Z]{3,10}-\d{2})"')
    out: list[dict[str, Any]] = []
    for order, fn in enumerate(CHECKS, 1):
        ids = sorted(set(id_re.findall(segments.get(fn.__name__, ""))))
        out.append({
            "order": order,
            "id": ids[0] if ids else fn.__name__,
            "function": fn.__name__,
            "asserts": _first_line(fn.__doc__),
        })
    return out


def build(root: Path) -> dict[str, Any]:
    """All six surfaces, in the order the measurement listed them."""
    return {
        "schemas": schemas(root),
        "configuration": configuration(root),
        "environment": environment(root),
        "cli": cli(root),
        "guards": guards(root),
        "guard_contract": guard_contract(),
        "figure_kinds": figure_kinds(),
        "health_checks": health_checks(root),
    }
