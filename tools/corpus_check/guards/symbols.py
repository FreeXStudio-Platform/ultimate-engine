"""``symbols`` — a backticked identifier must exist in the source tree, or be marked planned.

**What already owns part of this, and is not re-asked.** `tools/health` `CONS-07` resolves every
identifier cited in a `RULEBOOK.md` ``**Status:**`` block against the files that block cites, and it
does so block-aware — continuation lines and blockquotes included, because two fabricated citations
hid in exactly those two constructions. `RULEBOOK.md` is therefore **excluded** here by name; that
question has an owner.

**What was missing: everywhere else.** The rulebook is one document of fifty-six. `HANDOFF.md`,
`LESSONS.md`, `OPEN_GATES.md` and the plans cite symbols constantly — and a citation to a symbol
that does not exist is a document lying about what the machine does, which is the same defect
whichever document it lives in.

**Two questions, and the split between them is about certainty.**

1. **Dotted paths** (``tools.docgen.export_sanitizer``, ``export_sanitizer.PRECEDENCE``) resolve
   exactly. A module path either names a real file or it does not; a ``module.SYMBOL`` either
   appears in that module's source or it does not. No judgement, no false positives.
2. **Same-line identifiers** use `CONS-07`'s rule — an identifier cited beside a source file must
   appear in it — but **only on lines citing exactly one file**. `CONS-07` can be lenient about
   which of several cited files contains a symbol because a rulebook Status line names a small,
   curated set. Corpus-wide, a line naming three files beside four identifiers carries no reliable
   association at all, and guessing one would manufacture findings. Where the association is
   ambiguous, this guard says nothing — a quiet guard beats a wrong one.
"""

from __future__ import annotations

import ast
import re

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.corpus_check.text import (
    iter_prose_lines_with_headings,
    under_dated_heading,
)
from tools.lib import md_table, strip_comments_any_lang

GUARD = "symbols"

# `CONS-07` owns every citation in this file. Excluded by path, and the exclusion is the whole
# reason the two checks are not duplicates.
_OWNED_BY_CONS_07 = "docs/design/doc-system/RULEBOOK.md"

# A dotted module path rooted at a real top-level package in this repository. The root is derived
# from the tracked tree, never listed, so a host project's own package name works unchanged.
_DOTTED_RE = re.compile(r"`([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+)(?:\(\))?`")

# `module.SYMBOL` / `module.function()` — a lower-case module, then a symbol.
_MODULE_SYMBOL_RE = re.compile(r"`([a-z_][a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)(\(\))?`")

# A FILENAME is not a `module.SYMBOL`. Without this, every `` `validate_doc_system.py` `` in the
# corpus parsed as module `validate_doc_system`, symbol `py` — and the guard reported, at HIGH,
# that the module "defines no `py`". Measured on the first real run: 61 of 67 findings were this
# one mistake, which is also the clearest demonstration of why a guard is falsified against the
# real corpus before it is trusted rather than against three fixtures.
_FILE_SUFFIXES = frozenset(
    {"py", "mjs", "js", "ts", "json", "md", "sh", "html", "css", "toml", "txt", "yml", "yaml",
     "svg", "png", "lock", "cfg", "ini", "jsonl", "woff2"}
)

# A GATE LABEL is not a `module.SYMBOL` either, and it is shaped exactly like one.
#
# SEVENTEEN of this engine's gates are named with a dot — `visual.collision`, `chart.rule`,
# `geomap.source`, `iso3d.bounds` — so every one of them matches `_MODULE_SYMBOL_RE`, and **two**
# of them have a left half that IS a module basename in this tree (`sankey.py`, `visual.py`),
# producing **three** citations that would otherwise be reported: `sankey.rule`,
# `sankey.collision` and `visual.collision`. (Enumerated because the first correction said "two"
# and named only two of the three — counting the modules, not the citations.)
# (Both numbers were wrong when first written: "sixteen" predated the `identity` gate `OG-195`
# added, and the basename count said eight while naming `charts.py` and `geo_map.py`, neither of
# which collides — `chart` is not `charts`, `geomap` is not `geo_map`. Derive it, do not count by
# eye: `python3 -c "from tools.docgen.export_sanitizer import PRECEDENCE;
# print(len([g for g in PRECEDENCE if '.' in g]))"`.) The guard only checks a citation when the document already discusses that module,
# which held this false positive down until a document happened to cite both. `OPEN_GATES.md` then
# did exactly that: a row added on 2026-08-29 named `tools/docgen/visual.py`, which switched on
# checking for a `visual.collision` written four months earlier as a GATE TOKEN, and the guard
# reported — correctly by its own rule, and wrongly in fact — that `visual.py` defines no
# `collision`.
#
# The universe is read from `PRECEDENCE`, the same spine `CONS-04` ranks findings by, so this can
# never drift from the gates that actually exist: a gate renamed stops being exempt here the moment
# it stops being a gate. A hardcoded list of dotted names would have been the second copy of a
# registry, which is the defect this engine exists to catch.
def _gate_labels() -> frozenset[str]:
    """Every gate token the engine ranks. Imported, never listed."""
    try:
        from tools.docgen.export_sanitizer import PRECEDENCE
    except Exception:  # noqa: BLE001 — an unimportable spine means "exempt nothing", which is safe
        return frozenset()
    return frozenset(g for g in PRECEDENCE if "." in g)


# A cited source file.
_SOURCE_PATH_RE = re.compile(r"`((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:py|mjs|sh))`")

# A cited source file named WITHOUT a directory — `leak_gate.py`, `components.py`. This is the class
# that fell between the two existing checks: `CONS-06`'s pattern requires a tracked top-level
# directory prefix, so a bare filename never matches it, and the same-line rule below drops
# unresolvable paths *before* checking, so the wrong-citation case was the one it ignored.
#
# Measured across the corpus: 17 distinct bare filenames citing nothing. Two of them were in
# `tools/docgen/ENGINE_PLAN.md`'s own module table — `leak_gate.py` and `hash_gate.py`, neither of
# which has ever existed (the real modules are `export_sanitizer.py` and `validate_doc_system.py`).
# The engine's architecture document named modules the engine does not have, and no gate could see
# it (`OG-89`).
# Widened 2026-08-22 (`OG-98`). It covered only `py|mjs|sh`, so a Pass-7 probe walked bare
# `ghost_module.js`, `ghost_module.ts`, `GHOST_DOC.md` and `ghost_config.json` straight past it —
# and 18 live bare citations in other extensions resolve to nothing today, one of them
# `DESIGN_SYSTEM.md` in the engine's own README. The hole had moved one extension over, which
# is `LESSONS.md` L-26 again.
_BARE_SOURCE_RE = re.compile(
    r"`([A-Za-z0-9_.-]+\.(?:py|mjs|js|ts|sh|json|md|html|css|toml|yml|yaml))`"
)

# An identifier worth resolving: a call, or a SHOUTY constant. Deliberately excludes bare
# CamelCase words, which in this corpus are as often prose ("Markdown", "PyYAML") as code.
_IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)\(\)`|`([A-Z][A-Z0-9_]{2,})`")

# **Raised 10 -> 80, `P8-054`.** 10 was 1.5% of this guard's own measured live coverage (~678
# symbols) — low enough that a suppression list quietly widening (`OG-165`'s exact class, one
# guard over) could erase 85% of real coverage and still clear the floor. 80 leaves comfortable
# room below the live count for legitimate corpus edits while being "materially above" the old
# ~1-2% level the finding measured across this guard, `built-claims` and `cross-doc` alike. The
# absolute floor is deliberately still coarse — `runlog.py`'s watermark WARNS on a smaller
# relative drop than this floor alone would ever catch.
_FLOOR = 80


def _module_candidates(dotted: str) -> tuple[str, ...]:
    """Repo paths a dotted module path could name: a module file or a package directory."""
    base = dotted.replace(".", "/")
    return (f"{base}.py", base, f"{base}/__init__.py")



def _is_record(line: str, headings: tuple[str, ...]) -> bool:
    """A DECLARED append-only record, heading-scoped — see `OG-165`."""
    return under_dated_heading(headings)



def _defined_names(module_text: str) -> set[str]:
    """Every name a module actually DEFINES, from its AST — never from a substring search.

    **A comment is prose about the code, not code** (`OG-166`). Resolution was
    ``re.search(rf"\b{symbol}\b", module_text)``, so a module containing the line
    ``# NOTE: there is no longer a function called foo here`` made every citation of ``foo``
    resolve. Measured directly: the substring test returns True for exactly that input. All of this
    guard's symbol checks were resolved that way, so any of them could have been satisfied by
    documentation rather than by code.

    `test_refs._defined_ids` records this identical lesson in its own docstring and strips Python
    docstrings with `ast` for it; `cross_doc` was corrected for the same class in this pass
    (`OG-164`). This is the third consumer of "a ground truth that prose can widen".

    Falls back to the substring behaviour ONLY when the module cannot be parsed — a syntax error in
    a file this guard merely cites should not turn into a wave of false findings about symbols.
    """
    try:
        tree = ast.parse(module_text)
    except (SyntaxError, ValueError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
    return names


def _suffix_of(path: str) -> str:
    """The lower-cased file extension of a cited source path (`.py`/`.mjs`/`.sh`). `_SOURCE_PATH_RE`
    guarantees one of those extensions, so a plain rfind is enough and avoids a `pathlib` import."""
    dot = path.rfind(".")
    return path[dot:].lower() if dot != -1 else ""


def _names_or_text(module_text: str, symbol: str, *, suffix: str = ".py") -> bool:
    """True when ``symbol`` is defined in ``module_text`` — AST first, text only if unparseable.

    The text fallback fires for a NON-Python module (a `.mjs`/`.sh` whose `ast.parse` fails) and for
    a definition-free Python module (a docstring-only `__init__.py`, whose `_defined_names` is
    empty). In both, a raw `\\b{symbol}\\b` search over the source would let a name that appears ONLY
    in a comment satisfy a citation — a verifier cited `DETERMINISM` from a `.mjs` where it lives in
    a `//` comment and it passed. So prose (comments, and Python docstrings) is stripped, dispatched
    by ``suffix``, before the fallback search (`OG-219`, the symbols consumer of the JS/shell prose
    class). ``suffix`` defaults to `.py` because both dotted-module callers resolve Python modules;
    the same-line-citation caller passes the cited file's real suffix.
    """
    names = _defined_names(module_text)
    if names:
        return symbol in names
    return bool(re.search(rf"\b{re.escape(symbol)}\b", strip_comments_any_lang(module_text, suffix)))


def run(corpus: Corpus) -> GuardResult:
    """Resolve dotted module paths and unambiguous same-line identifier citations."""
    gate_labels = _gate_labels()
    roots = {rel.split("/", 1)[0] for rel in corpus.tracked if "/" in rel}
    basenames = {rel.rsplit("/", 1)[-1] for rel in corpus.tracked}
    # `ABSENT_PATHS.md` is the reviewable registry of deliberate absences, exactly as `CONS-06`
    # uses it — first column only, so a row cannot excuse a path it merely mentions.
    declared_absent = {
        md_table.strip_markup(row[0]).strip("`")
        for table in md_table.find_tables(corpus.text("docs/process/ABSENT_PATHS.md"))
        if table.headers and md_table.strip_markup(table.headers[0]).lower() == "path"
        for row in table.rows
        if row
    }
    # A module basename -> its source text, for `module.SYMBOL` resolution.
    by_basename: dict[str, str] = {}
    for rel in corpus.python_files:
        by_basename.setdefault(rel.rsplit("/", 1)[-1].removesuffix(".py"), "")
        by_basename[rel.rsplit("/", 1)[-1].removesuffix(".py")] += corpus.text(rel)

    findings: list[Finding] = []
    checked = 0

    for rel in corpus.markdown:
        if rel == _OWNED_BY_CONS_07:
            continue
        text = corpus.text(rel)
        # Which modules is THIS document actually discussing? Derived from the `.py` paths it
        # cites, so a `module.SYMBOL` reference is only judged where the association is real.
        modules_this_doc_discusses = {
            path.rsplit("/", 1)[-1].removesuffix(".py")
            for path in _SOURCE_PATH_RE.findall(text)
            if path.endswith(".py")
        }
        document_vocabulary = {
            term for terms in md_table.vocabulary_terms(text).values() for term in terms
        }
        for line_no, line, headings in iter_prose_lines_with_headings(text):
            # A record of a defect QUOTES the defect. `CHANGELOG.md` and
            # `docs/process/VERIFICATION_LOG.md` are append-only histories under dated headings,
            # and their entries name the fabricated symbol that was removed — `check_choropleth_
            # collisions`, `generator.foo`. Judging those as live citations reports a document for
            # accurately recording that something did not exist.
            # **HEADING-SCOPED, like `built-claims`** (`OG-165`). `is_historical` carries three
            # WHOLE-LINE clauses beyond the heading test — a date or clock time on the line, a
            # numeric transition, a past-tense marker — and `CONS-08` was corrected for exactly
            # that shape (`OG-123`: a claim and an instruction shared a line, and the CLAIM was
            # silenced). Measured here before changing anything: dropping the three clauses left
            # `symbols` with ZERO new findings and took its coverage 462 -> 664, and `counts`
            # 8 -> 13. They were suppressing nothing and hiding a third of the corpus.
            if _is_record(line, headings):
                continue
            # ---- 1a. dotted module paths -------------------------------------------------
            for match in _DOTTED_RE.finditer(line):
                dotted = match.group(1)
                if dotted.split(".", 1)[0] not in roots:
                    continue  # not a module path in this repository — a filename, a domain, prose
                parts = dotted.split(".")
                trailing_pair = ".".join(parts[-2:]) if len(parts) >= 2 else ""
                if dotted in gate_labels or trailing_pair in gate_labels:
                    # A GATE TOKEN, in either spelling. The exemption was added to the
                    # `module.symbol` branch only, so a document naming a gate by its emitter's
                    # FULL dotted path — `tools.docgen.visual.collision`, which is accurate prose —
                    # was still reported HIGH. A fix scoped to one branch of a two-branch rule is
                    # the instance, not the class.
                    continue
                checked += 1
                if any(corpus.resolves(c) for c in _module_candidates(dotted)):
                    continue
                # `tools.docgen.cli.build` — a symbol inside a module, not a module itself.
                head, _, tail = dotted.rpartition(".")
                if head and any(corpus.resolves(c) for c in _module_candidates(head)):
                    module_text = by_basename.get(head.rsplit(".", 1)[-1], "")
                    if _names_or_text(module_text, tail):
                        continue
                findings.append(
                    Finding(
                        guard=GUARD,
                        path=rel,
                        line=line_no,
                        message=f"cites `{dotted}`, which names no module or symbol in the tree",
                        evidence=(
                            f"looked for {', '.join(_module_candidates(dotted))}; also tried "
                            f"`{dotted.rpartition('.')[0]}` + symbol "
                            f"`{dotted.rpartition('.')[2]}`, which is what decided this"
                        ),
                        severity=Severity.HIGH,
                    )
                )

            # ---- 1b. module.SYMBOL --------------------------------------------------------
            for match in _MODULE_SYMBOL_RE.finditer(line):
                module, symbol = match.group(1), match.group(2)
                if symbol.lower() in _FILE_SUFFIXES:
                    continue  # a filename, not a symbol reference — CONS-06 owns paths
                if f"{module}.{symbol}" in gate_labels and not match.group(3):
                    # A gate token, not a module attribute — see `_gate_labels` above.
                    # `match.group(3)` is a trailing `()`. A gate token is NEVER callable, so
                    # `visual.collision()` is a claim that a FUNCTION exists and must still be
                    # checked; only the bare `visual.collision` is exempt. An adversarial verifier
                    # found the parenthesised form slipping through the first version.
                    continue
                if module not in modules_this_doc_discusses:
                    # A bare `foo.bar` is only a module reference if this document is actually
                    # about `foo`. `vault-graph-engine/VAULT_GRAPH_SPEC.md` describes a data field
                    # `counts.totp`, and `counts` became a module basename the day this package
                    # was written — so the guard confidently reported a JSON key as a missing
                    # Python symbol. A basename collision is not a citation.
                    continue
                cited_module_text = by_basename.get(module)
                if cited_module_text is None:
                    continue  # not a module in this tree; nothing certain to say
                checked += 1
                if not _names_or_text(cited_module_text, symbol):
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"cites `{module}.{symbol}`, but {module}.py defines no "
                            f"`{symbol}`",
                            evidence="a document naming a symbol the module does not have is the "
                            "defect CONS-07 was written for, one document over",
                            severity=Severity.HIGH,
                        )
                    )

            # ---- 1c. a cited source file that names nothing --------------------------------
            for match in _BARE_SOURCE_RE.finditer(line):
                cited = match.group(1)
                if "/" in cited:
                    continue  # a real path — CONS-06 owns those
                checked += 1
                if cited in basenames or cited in declared_absent:
                    continue
                findings.append(
                    Finding(
                        guard=GUARD,
                        path=rel,
                        line=line_no,
                        message=f"cites `{cited}`, which matches no tracked source file",
                        evidence="a bare filename is invisible to CONS-06 (its pattern needs a "
                        "directory prefix); declare it in ABSENT_PATHS.md if it belongs to another "
                        "project",
                        severity=Severity.HIGH,
                    )
                )

            # ---- 2. unambiguous same-line identifier citation ------------------------------
            paths = [p for p in _SOURCE_PATH_RE.findall(line) if corpus.resolves(p)]
            if len(paths) != 1:
                continue  # ambiguous or unresolvable — say nothing, deliberately
            blob = corpus.text(paths[0])
            for match in _IDENT_RE.finditer(line):
                name = match.group(1) or match.group(2)
                if not name:
                    continue
                if name in document_vocabulary:
                    # A term this document DECLARES in its own vocabulary table is not a code
                    # symbol. `OPEN_GATES.md` writes `NOT_A_DEFECT` in a disposition cell beside a
                    # row citing `tools/health/checks.py`, and the SHOUTY-constant heuristic read it
                    # as a missing Python name. The document says what it means; read that.
                    continue
                checked += 1
                # `_names_or_text`, NOT a raw regex over the file's text. This branch was the FIFTH
                # consumer of the root `_defined_names` records (`OG-166`) — and it lived in this
                # module, below the resolver this module exports to `CONS-07`. An adversarial
                # verifier planted one fabricated symbol inside a comment that says it does not
                # exist, cited it from two places in the same shape, and got opposite verdicts:
                # CONS-07 (fixed) refused it, this branch (unfixed) passed it. The cited file's
                # suffix is passed so the fallback strips the RIGHT language's comments — a `.mjs`
                # or `.sh` cited here never parses as Python (`OG-219`).
                if not _names_or_text(blob, name, suffix=_suffix_of(paths[0])):
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"cites `{name}` beside `{paths[0]}`, which does not contain it",
                            evidence="only lines citing exactly ONE source file are checked, so "
                            "the association is unambiguous",
                            severity=Severity.MEDIUM,
                        )
                    )

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: all {checked} cited symbol(s) resolve to real source across "
        f"{len(corpus.markdown) - 1} document(s)",
        checked=checked,
        floor=_FLOOR,
        evidence=f"{_OWNED_BY_CONS_07} is excluded — CONS-07 owns its Status-block citations",
    )
