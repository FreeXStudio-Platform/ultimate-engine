"""``test-refs`` — every cited test name and every cited **check id** must exist.

The doctrine's rule is *"every cited test name must exist in the test tree"*, and the defect behind
it is stark: one project's index document claimed for **months** that a test prevented drift, and
that test had never existed (doctrine §4).

**This corpus's version of the same defect is the check id.** `HANDOFF.md`, `OPEN_GATES.md`,
`RULES.md` and `LESSONS.md` cite `SUITE-05`, `CONS-08`, `STRUCT-03`, `BUILD-02` constantly, in the
documents a session reads *first* and reasons from. A citation to a check that does not exist is a
session being told a question is answered when nothing asks it — the exact shape of the defect
above, one layer up.

**Ground truth is read off disk, never listed here** (doctrine §5: *read real source; never compare
a copied literal against itself*):

* the **prefix vocabulary** is derived — whatever prefixes actually appear as ``"PREFIX-NN"``
  literals in the tracked source tree. So a host project whose checks are called ``LINT-01`` is
  covered without editing this file, and a prefix nobody uses stops being enforced by itself.
* an id is **valid** if that exact literal appears in tracked source.

That derivation is also what keeps the guard quiet about ids it has no business judging: `OG-47` is
a register key, `L-15` a lesson, `R2` a risk, and none of their prefixes appears in source as a
check literal, so none is treated as one. Register keys are `cross_doc`'s question.
"""

from __future__ import annotations

import ast
import re

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.corpus_check.text import (
    is_append_only_record,
    iter_prose_lines_with_headings,
    under_dated_heading,
)

GUARD = "test-refs"

# `PREFIX-NN`, backticked. Backticks are required: this corpus writes prose like "Phase 3" and
# "2026-08-21" that an unanchored pattern would shred.
_ID_RE = re.compile(r"`([A-Z][A-Z0-9]{1,9})-(\d{1,3})`")

# A cited test: `test_something` or `test_something.py`, backticked.
_TEST_RE = re.compile(r"`(test_[a-z0-9_]+)(\.py)?`")

# Sources that may define a check id or a test. `.sh` is included because this repo's moat attacks
# live in `tools/tests/hook_attacks.sh` and are cited by id from four documents.
_SOURCE_SUFFIXES = (".py", ".mjs", ".sh", ".js", ".ts")

_FLOOR = 10


def _strip_shell_comments(text: str) -> str:
    """Drop a `#` comment to end of line, outside single- and double-quoted strings.

    `P8-053`: `.sh` sources were harvested with raw full-text regex, no comment stripping — only
    `.py` dropped anything, via `ast` docstring removal. Reproduced live: appending
    ``# coverage note: see "SUITE-99" in the register`` to `tools/hooks/install.sh` widened this
    guard's id vocabulary and turned a real, correctly-refused citation clean.

    A `#` is a comment start when it is unquoted and word-initial (line start, or preceded by
    whitespace) — the shape every real comment in this corpus's `.sh` sources takes. A `#` that is
    quoted, or sits mid-word, is left alone; this is a lexer for comments, not a shell parser, so
    it does not need to resolve command substitution or here-docs to do its one job.
    """
    out: list[str] = []
    for line in text.split("\n"):
        chars: list[str] = []
        in_single = in_double = False
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            if in_single:
                chars.append(ch)
                in_single = ch != "'"
                i += 1
                continue
            if in_double:
                chars.append(ch)
                if ch == "\\" and i + 1 < n:
                    chars.append(line[i + 1])
                    i += 2
                    continue
                in_double = ch != '"'
                i += 1
                continue
            if ch == "'":
                in_single = True
                chars.append(ch)
                i += 1
                continue
            if ch == '"':
                in_double = True
                chars.append(ch)
                i += 1
                continue
            if ch == "#" and (i == 0 or line[i - 1] in " \t"):
                break  # unquoted, word-initial — the rest of the line is commentary
            chars.append(ch)
            i += 1
        out.append("".join(chars))
    return "\n".join(out)


def _strip_js_comments(text: str) -> str:
    """Drop `//` line comments and `/* … */` block comments, outside string/template literals.

    `P8-053`'s other half: `.mjs`, `.js` and `.ts` are the other non-`.py` sources this guard
    scans textually, and a `//` or `/* */` comment naming a bogus id would widen the vocabulary
    the same way a `.sh` comment did.

    Tracks single/double/backtick string state with backslash escaping, but does not disambiguate
    a `/` division operator from a regex-literal opener — a real tokenizer's job, not a comment
    lexer's. That gap can only cause UNDER-stripping (a comment survives uncut), never
    over-stripping code into a comment, so it cannot hide a real id definition.
    """
    chars: list[str] = []
    i, n = 0, len(text)
    quote: str | None = None
    while i < n:
        ch = text[i]
        if quote is not None:
            chars.append(ch)
            if ch == "\\" and i + 1 < n:
                chars.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"`":
            quote = ch
            chars.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        chars.append(ch)
        i += 1
    return "".join(chars)


def _defined_ids(corpus: Corpus) -> set[str]:
    """Every ``PREFIX-NN`` this repository actually **defines**, read off disk.

    Two exclusions, and both were earned by this guard failing on the real corpus rather than
    reasoned about in advance:

    1. **The test tree.** A fixture quoting a deliberately-bad probe id would enter the vocabulary
       and make every citation of that prefix a finding. Measured: 155 findings from one fixture.

    2. **Docstrings.** A *docstring is prose about the code, not code* — and this guard's own
       module docstring, explaining exclusion 1, quoted the probe id it was explaining. The
       explanation recreated the defect: 158 findings, from the sentence describing why there had
       been 155. Python sources are therefore parsed with `ast` and every module, class and
       function docstring is dropped before literals are collected; only `.mjs` and `.sh`, which
       have no docstring concept, are scanned textually.

    A ground truth that documentation can widen is not a ground truth.
    """
    ids: set[str] = set()

    def harvest(text: str) -> None:
        ids.update(f"{m.group(1)}-{m.group(2)}"
                   for m in re.finditer(r"\"([A-Z][A-Z0-9]{1,9})-(\d{1,3})\"", text))
        ids.update(f"{m.group(1)}-{m.group(2)}"
                   for m in re.finditer(r"'([A-Z][A-Z0-9]{1,9})-(\d{1,3})'", text))

    for rel in corpus.tracked:
        if not rel.endswith(_SOURCE_SUFFIXES) or "/tests/" in f"/{rel}":
            continue
        text = corpus.text(rel)
        if not rel.endswith(".py"):
            # `.py` drops docstrings via `ast`; these have no docstring concept but do have
            # COMMENTS, which are prose about the code exactly as a docstring is (`P8-053`) —
            # scanning the raw text let a `#`/`//` comment widen the id vocabulary the same way
            # an unstripped docstring once did.
            harvest(_strip_shell_comments(text) if rel.endswith(".sh") else _strip_js_comments(text))
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            # An unparseable source is not evidence about ids either way; scanning it textually
            # would reintroduce the docstring hole for exactly the files least worth trusting.
            continue
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                harvest(f'"{node.value}"')
    return ids


def run(corpus: Corpus) -> GuardResult:
    """Resolve cited check ids and test names against the tracked source tree."""
    # The prefix vocabulary and the id universe, both derived from real source.
    defined_ids = _defined_ids(corpus)
    known_prefixes = {i.split("-", 1)[0] for i in defined_ids}

    # Test names: a file basename under the test tree, or a `def test_*` anywhere in source.
    test_names = {
        rel.rsplit("/", 1)[-1].removesuffix(".py")
        for rel in corpus.tracked
        if "/tests/" in f"/{rel}" and rel.endswith(".py")
    }
    # Test FUNCTION names come from every source file — a `def test_*` is a definition wherever
    # it lives, and the test tree is exactly where most of them are.
    all_source = "\n".join(
        corpus.text(rel) for rel in corpus.tracked if rel.endswith(_SOURCE_SUFFIXES)
    )
    test_names |= set(re.findall(r"def\s+(test_[A-Za-z0-9_]+)", all_source))

    findings: list[Finding] = []
    checked = 0

    for rel in corpus.markdown:
        doc_text = corpus.text(rel)
        doc_is_record = is_append_only_record(doc_text)  # OG-140: declared, not inferred
        for line_no, line, headings in iter_prose_lines_with_headings(doc_text):
            # **A dated record names what was true THEN** (`OG-137`). `VERIFICATION_LOG.md` records
            # each pass against the commit it ran on, and a pass's whole job is to name the tests
            # it found — including ones a later fix renamed or replaced. Reporting those is
            # reporting the append-only history for accurately recording what it saw, which is the
            # failure mode that gets a gate switched off. Same `under_dated_heading` test the rest
            # of the package uses, so "record" means one thing across every guard.
            if doc_is_record and under_dated_heading(headings):
                continue
            for match in _ID_RE.finditer(line):
                prefix, number = match.group(1), match.group(2)
                if prefix not in known_prefixes:
                    # Not a check id at all — a register key, a lesson, a risk. Someone else's
                    # question, and answering it here would produce confident nonsense.
                    continue
                cited = f"{prefix}-{number}"
                checked += 1
                if cited not in defined_ids:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"cites check `{cited}`, which no tracked source defines",
                            evidence=(
                                f"{prefix}-* ids exist in source, so this is a check citation, not "
                                f"a register key. Defined {prefix}-* ids: "
                                + ", ".join(sorted(i for i in defined_ids if i.startswith(prefix + "-")))
                            ),
                            severity=Severity.HIGH,
                        )
                    )
            for match in _TEST_RE.finditer(line):
                name = match.group(1)
                checked += 1
                if name not in test_names:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"cites test `{name}`, which exists in no tracked test file",
                            evidence=(
                                "A document claiming a test guards something, where no such test "
                                "exists, is the defect DOC_WRITING_DOCTRINE.md §4 opens with."
                            ),
                            severity=Severity.HIGH,
                        )
                    )

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: all {checked} cited check id(s) and test name(s) resolve to real source "
        f"({len(defined_ids)} ids and {len(test_names)} tests defined)",
        checked=checked,
        floor=_FLOOR,
        evidence=f"prefix vocabulary derived from source: {', '.join(sorted(known_prefixes))}",
    )
