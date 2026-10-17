"""Shared, dependency-free helpers used by more than one tools/ package.

This package exists for code that both the **engine** (``tools.docgen``) and the checkers built on
top of it (``tools.health``, ``tools.corpus_check``) must agree about. Putting such code in either
one would make the other import *downward* into a layer it sits above; putting it here keeps the
dependency direction honest:

    tools.lib  <-  tools.docgen  <-  tools.health / tools.corpus_check

Nothing here may import from ``tools.docgen``, ``tools.health`` or ``tools.corpus_check`` — a helper
that reaches back up into its own callers is a cycle waiting for the first import-order change; the
helpers use the standard library only.

LANGUAGE-AWARE PROSE STRIPPING lives directly in this ``__init__`` — not a ``tools/lib/prose.py``
submodule — for a measured layout reason, not a stylistic one. Three derivations independently paid
for the same class and each fixed it in one language only (`OG-215` surfaces env-reads, `OG-216`
gatekeepers guarded-by edges, `OG-219` symbols' fallback): Python was made structural while JS and
shell kept scanning raw text, so a `//` comment or a `;#` comment could still manufacture a phantom.
The per-language stripper is ONE thing, in one place, so a blind spot closed for one consumer is
closed for all (`RULES.md` Rule 1).

**Why the `__init__` and not a submodule (`OG-224`).** The blueprint figure is drawn at PACKAGE
granularity — twelve nodes, one per package — and each package node's size grows with the number of
MODULES it contains. Measured on this tree: with the strippers here, `tools.lib` holds two modules
(`__init__`, `md_table`) and `blueprint layout` reports **zero** node-placement findings; splitting
them into a third module `tools/lib/prose.py` grows the `tools.lib` node enough that ELK places
`tools.blueprint` and `tools.corpus_check.guards` — both of which edge to `tools.lib` because they
import a stripper — into a sub-minimum **diagonal** gap (21px < the 22px floor), which no spacing
option clears and which `blueprint verify` refuses. A verifier's earlier "a stub `prose.py` is
byte-identical" was measured on a stub NOTHING imports (no package edges, no size change); the module
here is imported by three consumers, and the size change is real. A future tidy that splits this out
"for symmetry with `md_table.py`" would re-open that gap — leave it here. Consequence, stated because
the sibling `gatekeepers.py` prose depends on it: because this `__init__` now runs code, `tools.lib`
IS a substantive package (importing a child executes it), so gates that import a `tools.lib` child
are credited as its gatekeepers — correct, and the guarded-by edges follow.

It strips prose only; code STRINGS are left to each caller, which removes them when a name inside a
string is also not a real reference (an env read) and keeps them when it is (a `"-m mod"`).

STATED BOUNDS (regex is not a tokenizer; all latent on this tree, a verifier confirmed no live
read/edge/citation is wrong today — `OG-224`). JS: a name inside a REGEX LITERAL (`/process.env.X/`)
is not stripped, and a `process.env.X` read inside a TEMPLATE-LITERAL INTERPOLATION
(`` `${process.env.X}` ``) is dropped with the surrounding string. Shell: a `#` inside a QUOTED string
is treated as a comment (a real `$VAR` after it in the same string is over-stripped), and the `#`
after `>`/`<` — which bash comments in an already-invalid line — is kept. Closing these needs a real
per-language lexer, which the last phase of a build is not the place to add.
"""
from __future__ import annotations

import ast
import re

__all__ = [
    "strip_comments_any_lang",
    "strip_js_comments",
    "strip_js_strings",
    "strip_shell_comments",
]

_JS_SUFFIXES = {".mjs", ".js", ".cjs"}

# ONE pass over the tokens that can HIDE a `//` or `/* */`: a string literal, or a comment. Strings
# are matched FIRST, so a `//` inside a URL string or a `/*` inside a glob string is consumed as part
# of the string and never mistaken for a comment opener — the both-directions bug a verifier found
# when comments were stripped BEFORE strings (a `"http://x"` opened a phantom line comment that ate
# the rest of the line, and a later blanking pass then ran from the dangling quote across real code).
# Comments become a space (line structure preserved); strings are kept intact for the caller.
_JS_STRING_OR_COMMENT = re.compile(
    r"""(?P<s>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`)"""  # string literal
    r"|(?P<c>//[^\n]*|/\*.*?\*/)",  # line or block comment
    re.DOTALL,
)
_JS_STRING = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`", re.DOTALL)
# A shell comment opens at line start or after whitespace / ; & | ( ) — never `$#` (arg count) or
# `${#name}` (length), where the `#` is preceded by `$` or `{` and is not a comment.
_SH_COMMENT = re.compile(r"(?m)(?:^|(?<=[\s;&|()]))#.*$")
_PY_LINE_COMMENT = re.compile(r"(?m)#.*$")


def strip_js_comments(source: str) -> str:
    """JS/MJS with `//` and `/* */` comments removed, string literals KEPT. String-aware: a comment
    opener living inside a string is not a comment (`OG-224`)."""
    return _JS_STRING_OR_COMMENT.sub(lambda m: m.group("s") or " ", source)


def strip_js_strings(source: str) -> str:
    """JS with '…' / "…" / `…` string literals blanked. Call AFTER strip_js_comments so a `//`
    living inside a string is not first mistaken for a comment opener. A caller that reads a name
    OUT of a bracket-string key (`process.env["X"]`) must capture it BEFORE calling this."""
    return _JS_STRING.sub('""', source)


def strip_shell_comments(source: str) -> str:
    """Shell with `#` comments removed at a real boundary (line start, or after space/;&|()), while
    `$#` and `${#…}` — where the `#` is not a comment — survive. NOT quote-aware (see BOUNDS)."""
    return _SH_COMMENT.sub("", source)


def _strip_python_prose(source: str) -> str:
    """Python with comments (free — never in the AST) and docstrings (blanked) removed; code strings
    kept. On unparseable source, falls back to a `#`-comment strip so the result is never LESS
    strict than the raw text."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return _PY_LINE_COMMENT.sub("", source)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body[0] = ast.Expr(value=ast.Constant(value=Ellipsis))
    try:
        return ast.unparse(tree)
    except Exception:  # noqa: BLE001 — any unparse failure keeps a comment-stripped raw source
        return _PY_LINE_COMMENT.sub("", source)


def strip_comments_any_lang(source: str, suffix: str) -> str:
    """Comments (and Python docstrings) removed, dispatched by file suffix. An unknown suffix is
    returned unchanged — there is nothing safe to strip without knowing the language."""
    s = suffix.lower()
    if s == ".py":
        return _strip_python_prose(source)
    if s in _JS_SUFFIXES:
        return strip_js_comments(source)
    if s == ".sh":
        return strip_shell_comments(source)
    return source
