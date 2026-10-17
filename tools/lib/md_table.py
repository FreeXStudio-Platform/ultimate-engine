"""The one Markdown pipe-table reader (``OPEN_GATES.md`` OG-36).

**Why this module exists.** Five readers in this repository parsed the same governance corpus, in
two mutually incompatible dialects, and the disagreement was measured rather than guessed:

    input:  | variants: [commercial\\|confidential\\|secret] | x |
    tools/docgen/classification.py   -> 4 cells, the escaped pipes deleted mid-word
    tools/docgen/adjudication.py     -> 4 cells, identically corrupted
    tools/docgen/doc_manifest.py     -> 2 cells, correct
    tools/docgen/generator.py        -> 2 cells, correct
    tools/health/checks.py           -> ad hoc, per call site

    input:  || a | b |
    the three ``.strip("|")`` readers  -> 2 cells (the empty leading cell is deleted)
    tools/docgen/doc_manifest.py       -> 3 cells, correct

That first input is not hypothetical: it is `DOC_MANIFEST.md`'s own header cell. A corpus checker
that cannot read its own corpus consistently is not a checker, so Phase 3 owns this reader and
every previous reader delegates to it.

**The dialect is GFM, stated so it can be attacked.**

1. A row is stripped of surrounding whitespace, then **exactly one** leading ``|`` and **exactly
   one** trailing ``|`` are removed. Not ``str.strip("|")``, which eats an unbounded run and
   silently deletes an intentionally empty first or last cell.
2. Cells are split on a ``|`` **not preceded by a backslash**. GFM's only in-cell escape is
   ``\\|``; a cell holding a shell pipeline, a regex alternation or a union type depends on it.
3. Each cell is then unescaped (``\\|`` -> ``|``) and stripped.

**Stdlib only** (RULEBOOK L23), and no import from ``tools.docgen`` / ``tools.health`` /
``tools.corpus_check`` — see `tools/lib/__init__.py` for why the dependency direction matters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "Table",
    "column_index",
    "find_table",
    "find_tables",
    "is_row",
    "is_separator",
    "parse_block",
    "split_row",
    "strip_markup",
    "vocabulary_terms",
]

# A table row is a line that starts and ends with `|` and has something between them. Anchored on
# the STRIPPED line: Markdown permits leading indentation, and a row indented by two spaces is
# still a row to every renderer.
_ROW_RE = re.compile(r"^\|(.+)\|\s*$")

# The delimiter row: pipes, dashes, colons and whitespace only. `|---|:--:|` and `| --- | --- |`
# both qualify; `| a | b |` does not.
_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|\s*$")

# Split on a `|` that is NOT preceded by a backslash. `(?<!\\)` is a fixed-width lookbehind, which
# is all that is needed because GFM has no `\\\\|` ambiguity inside table cells.
_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")

# Markup that carries no meaning for header/word matching: backticks around a cell, and bold.
# **Underscores are deliberately NOT stripped.** They are part of identifiers, not emphasis, in
# every cell that matters here: `NOT_A_DEFECT`, `BLOCKS_PHASE_3`, `content_role`,
# `_GATE_TO_CONTRADICTION_TOKENS`. Stripping them was measured mangling a disposition into
# `NOTADEFECT` inside a finding's own evidence line the first time this ran over the real corpus.
# `tools/docgen/doc_manifest.py` has always stripped exactly these two, and now there is one copy.
_MARKUP_RE = re.compile(r"[`*]")


def is_row(line: str) -> bool:
    """True if ``line`` is a Markdown table row (data **or** header **or** separator)."""
    return _ROW_RE.match(line.strip()) is not None


def is_separator(line: str) -> bool:
    """True if ``line`` is the delimiter row that turns a pipe row into a table header."""
    return _SEPARATOR_RE.match(line.strip()) is not None


def split_row(line: str) -> list[str]:
    """Split one Markdown table row into its cells. **This is the canonical dialect.**

    Removes exactly one leading and one trailing pipe, splits on unescaped pipes, unescapes ``\\|``
    and strips each cell. See the module docstring for what each of those three choices prevents.
    """
    stripped = line.strip()
    stripped = stripped.removeprefix("|")
    stripped = stripped.removesuffix("|")
    return [cell.strip().replace("\\|", "|") for cell in _UNESCAPED_PIPE_RE.split(stripped)]


def strip_markup(cell: str) -> str:
    """Drop backticks and emphasis so header matching survives the corpus's real formatting.

    `DOC_MANIFEST.md` writes ``` `id` ``` and `OPEN_GATES.md` writes ``**sev**``; a header match
    that only accepts bare words cannot find either.
    """
    return _MARKUP_RE.sub("", cell).strip()


@dataclass(frozen=True)
class Table:
    """One Markdown pipe table, with the line numbers needed to cite a defect precisely.

    ``header_line`` and ``first_row_line`` are **1-based**, matching every editor, every
    ``file:line`` citation in this repository's registers, and ``git blame``. A finding that cannot
    name a line is a finding a reader has to go hunting for.
    """

    headers: list[str]
    rows: list[list[str]]
    header_line: int
    first_row_line: int

    @property
    def width(self) -> int:
        """The header's column count — the width every data row is expected to match."""
        return len(self.headers)

    def ragged_rows(self) -> list[tuple[int, int]]:
        """``(line number, cell count)`` for every row whose width differs from the header's.

        A ragged row is how a register silently loses a column: the cells after the missing pipe
        shift left by one, so a ``disposition`` reads as a ``title`` and every consumer indexing by
        position gets a plausible-looking wrong answer rather than an error.
        """
        return [
            (self.first_row_line + i, len(row))
            for i, row in enumerate(self.rows)
            if len(row) != self.width
        ]


def parse_block(block: list[str], *, first_line: int = 1) -> Table | None:
    """Parse a contiguous run of table lines that the caller has already isolated.

    Expects ``block[0]`` to be the header row. A separator row at ``block[1]`` is consumed if
    present and simply skipped if not — the leniency the manifest, taxonomy and contradiction
    readers have always had, preserved deliberately rather than tightened, because these files gate
    the build and a stricter parse would turn a formatting nit into a blocked engine.
    """
    if not block or not is_row(block[0]):
        return None
    headers = split_row(block[0])
    start = 2 if len(block) > 1 and is_separator(block[1]) else 1
    rows = [split_row(line) for line in block[start:] if is_row(line)]
    return Table(
        headers=headers,
        rows=rows,
        header_line=first_line,
        first_row_line=first_line + start,
    )


# A fenced code block. Owned here rather than imported from `tools.corpus_check.text` because
# `tools/lib` is the lower layer — a reader that depended on a guard package would invert the
# dependency the whole `OG-36` consolidation exists to establish. The two implementations agree
# by construction: `test_md_table.py` asserts it against `text.iter_prose_lines`.
_FENCE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>.*)$")


def without_fenced_blocks(text: str) -> str:
    """``text`` with every fenced code block blanked, line numbering preserved.

    **A table drawn inside a fence is a DEMONSTRATION, not a declaration.** `docs/CHARTER.md` and
    the doctrine both say a fenced block is not a claim, and `vocabulary_terms` reading one is not
    a cosmetic bug: a document that *shows* a governance table in an example — as several here do —
    silently widens the real vocabulary that `register` validates rows against. Pass 7 added a
    three-row fenced table declaring `disposition | TOTALLY_FINE` and watched `register` accept a
    live row carrying it (`OG-100`).
    """
    out: list[str] = []
    open_fence: str | None = None
    for line in text.splitlines():
        match = _FENCE_RE.match(line)
        if open_fence is None:
            if match is not None:
                open_fence = match.group("fence")
                out.append("")
                continue
            out.append(line)
        else:
            if (
                match is not None
                and match.group("fence")[0] == open_fence[0]
                and len(match.group("fence")) >= len(open_fence)
                and not match.group("info").strip()
            ):
                open_fence = None
            out.append("")
    return "\n".join(out)


def find_tables(
    text: str, *, require_separator: bool = True, include_fenced: bool = False
) -> list[Table]:
    """Every pipe table in ``text``, in document order.

    A blank line ENDS a table — that is Markdown, not a choice made here, and `CONS-10` exists
    because a blank line between two rows once split this project's own gate register into five
    tables that looked like one. Two tables separated by a blank line are therefore returned as
    two ``Table`` objects, which is what any conforming renderer also does.

    ``require_separator=True`` is GFM: a pipe row followed by a delimiter row is a table, a pipe
    row on its own is a paragraph that happens to contain pipes. The three governance readers pass
    ``False`` to keep the tolerance they were written with.
    """
    # **FENCE-AWARE BY DEFAULT** (`OG-163`). `OG-100` fixed exactly one caller —
    # `vocabulary_terms` — after a fenced example table was shown to widen a live governance
    # vocabulary. The root was left fence-blind, so every OTHER consumer kept the hole: health's
    # `CONS-06` and `symbols` both build their suppression set from `ABSENT_PATHS.md` through this
    # function, so a fenced example row there declares a path absent for real. A fenced table is a
    # DEMONSTRATION; this corpus shows governance tables inside fences on purpose.
    #
    # `include_fenced=True` remains for a caller that genuinely wants them, but no caller in this
    # engine does — fixing one call site and leaving the root is `LESSONS.md` L-26, and this is the
    # root.
    if not include_fenced:
        text = without_fenced_blocks(text)
    lines = text.splitlines()
    tables: list[Table] = []
    i = 0
    while i < len(lines):
        if not is_row(lines[i]) or is_separator(lines[i]):
            i += 1
            continue
        has_sep = i + 1 < len(lines) and is_separator(lines[i + 1])
        if require_separator and not has_sep:
            i += 1
            continue
        header_line = i + 1
        start = i + (2 if has_sep else 1)
        j = start
        while j < len(lines) and is_row(lines[j]) and not is_separator(lines[j]):
            j += 1
        tables.append(
            Table(
                headers=split_row(lines[i]),
                rows=[split_row(lines[k]) for k in range(start, j)],
                header_line=header_line,
                first_row_line=start + 1,
            )
        )
        i = max(j, i + 1)
    return tables


def find_table(
    text: str,
    *,
    required_headers: tuple[str, ...],
    require_separator: bool = True,
) -> Table | None:
    """The first table whose header row contains every name in ``required_headers``.

    Matching is case-insensitive, markup-stripped and **substring**: ``"variants"`` matches the
    manifest's ``variants: [commercial\\|confidential\\|secret]`` header cell, which is the shape
    the corpus actually uses. Returns ``None`` rather than raising — every caller here is a parser
    with a documented fail-closed contract of its own, and raising through them was `LESSONS.md`
    L-17.
    """
    wanted = [w.lower() for w in required_headers]
    for table in find_tables(text, require_separator=require_separator):
        cells = [strip_markup(c).lower() for c in table.headers]
        if all(any(w in cell for cell in cells) for w in wanted):
            return table
    return None


def vocabulary_terms(text: str) -> dict[str, set[str]]:
    """``column name -> declared terms`` for every vocabulary table in a document.

    A **vocabulary table** is one whose *first* header cell names a column that other tables use:
    ``| disposition | meaning |`` declares the ``disposition`` vocabulary, and its terms are the
    first cells of its rows.

    First-column-only, for the reason `CONS-06` learned the hard way about `ABSENT_PATHS.md`: a
    table that would exempt every term it merely *mentions* is a suppression list, not a registry.

    Lives here rather than in a guard because two guards need it and disagreeing about what a
    vocabulary is would be `OG-36` again, one abstraction up.
    """
    # **Prose only.** A vocabulary declared inside a fenced example is a demonstration; letting
    # one widen the live vocabulary is a governance injection, not a parsing nicety.
    vocab: dict[str, set[str]] = {}
    for table in find_tables(without_fenced_blocks(text)):
        if not table.headers:
            continue
        name = strip_markup(table.headers[0]).lower()
        if not name:
            continue
        terms = {strip_markup(row[0]) for row in table.rows if row and row[0].strip()}
        if terms:
            vocab.setdefault(name, set()).update(terms)
    return vocab


def column_index(headers: list[str], names: tuple[str, ...]) -> dict[str, int]:
    """Map each name in ``names`` to the index of the first header cell that equals it.

    Equality is on the markup-stripped, lower-cased, whitespace-stripped cell — not substring, so
    ``"id"`` cannot accidentally bind to a ``"valid"`` column. Names with no matching header are
    simply absent from the result; the caller decides which are required, because "which columns
    must exist" is the caller's contract and not this reader's.
    """
    normalized = [strip_markup(c).strip().lower() for c in headers]
    out: dict[str, int] = {}
    for name in names:
        key = name.lower()
        for i, cell in enumerate(normalized):
            if cell == key:
                out[name] = i
                break
    return out
