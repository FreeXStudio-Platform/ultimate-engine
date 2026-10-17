"""``register`` — a register must be able to name its own rows.

**Not one of the doctrine's nine.** It is here because it was earned: while orienting for Phase 3,
before a line of this package was written, `docs/process/OPEN_GATES.md` was found carrying **eleven
duplicate primary keys** — `OG-48` through `OG-58`, each naming two entirely different findings, one
in `## Open` and one in `## Closed`. Two numbering runs had both started at `OG-48`. Every citation
of `OG-49`, `OG-50` or `OG-58` in the handover documents, the build plan and the changelog was
therefore ambiguous, and the register the phase gate itself is answered from could not identify its
own contents.

It belongs to the `cross-doc` family one level lower than `CONS-01…CONS-05` reach: those five guard
*two documents agreeing with each other*; this guards *one document being self-consistent enough to
be worth comparing to anything*.

**Domain-neutral by construction** (`docs/CHARTER.md`: "a rule that only works here is a bug").
Nothing here names `OPEN_GATES.md`. A register is found **structurally** — any tracked Markdown
table with an ``id`` column — so a host project's own registers are covered on the day it adopts the
engine, and this repository is simply the first corpus it happens to run over.

Three questions, each with a stated failure it prevents:

1. **Are the ids unique?** A duplicate key silently redirects every citation of it.
2. **Is any row ragged?** A row with fewer cells than its header does not error — the cells after
   the missing pipe shift left, so a ``disposition`` reads as a ``title`` and every consumer
   indexing by position gets a plausible wrong answer.
3. **Is every value in a governed column declared?** When a document defines a vocabulary table for
   a column (``| disposition | meaning |``) and another table uses that column, a value outside the
   vocabulary is a row that no reader — and no rule — can classify.
"""

from __future__ import annotations

import re

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.lib import md_table

GUARD = "register"

# A register's primary key column. Compared on the markup-stripped, lower-cased header cell.
_ID_HEADERS = ("id",)

# Below this, the guard has not seen enough of a corpus to have decided anything (LESSONS.md L-19).
# Derived floors are impossible here — the number of registers is a property of the host project —
# so the floor guards the DEGENERATE case only: zero ids means either the registers lost their id
# columns or this guard stopped finding tables, and both are defects.
_FLOOR = 1

# A vocabulary term may carry the placeholder **N**, standing for a number: `SCHEDULED (Phase N)` is
# declared once and used as `(Phase 3)`, `(Phase 4)`, `(Phase 7)`, and `BLOCKS_PHASE_N` as
# `BLOCKS_PHASE_4`. Substituting `\d+` for it is the ONLY normalisation applied, and it is applied to
# the DECLARED term, never to the used value — so a typo in a row can never widen the vocabulary.
#
# **`N` specifically, and only where no letter touches it.** The first version expanded any lone
# capital via `\b([A-Z])\b`, which could not see the `N` in `BLOCKS_PHASE_N` at all (an underscore is
# a word character, so there is no boundary) — and a naive widening to "any capital not adjacent to
# a letter" would have eaten the `A` in `NOT_A_DEFECT` and silently invalidated that term instead.
# **`N` after a separator, and the LITERAL term is always accepted too** (`OG-109`).
#
# The rule was "a lone capital N not touching a letter", which mangles ordinary register terms:
# a declared `N/A` compiled to `^\d+/A$`, so the literal `N/A` was reported as undeclared while
# the genuinely undeclared `7/A` passed. Measured damage to plausible host vocabularies — `N/A`,
# `Y/N`, `SEV-N`, `N-TIER`, `TBD (N)` and a bare `N` — was wrong in BOTH directions at once: a
# false finding on the real value and a silent pass on a fake one, the worst pair a guard can
# produce.
#
# Two changes, and the first alone removes every false FINDING: the matcher accepts the term
# **verbatim** as well as expanded, so a declared value can never be reported undeclared for a
# reason invented here. The second narrows expansion to an `N` following `_` or a space —
# `BLOCKS_PHASE_N` and `SCHEDULED (Phase N)`, the two forms this corpus actually declares — which
# leaves `N/A`, `Y/N`, `SEV-N` and `N-TIER` alone. A placeholder spelled some third way is simply
# not expanded, producing a finding to fix rather than a silent pass: wrong in the loud direction,
# by choice.
_PLACEHOLDER_RE = re.compile(r"(?<=[_ ])N(?![A-Za-z])")

# Substituted for the placeholder before escaping, then swapped for `\d+` after. Escaping first
# and pattern-matching the escaped text is what made the old version fragile: `re.escape` has
# changed which characters it escapes across Python versions, so a rule written against escaped
# output silently means something different on a different interpreter.
_PLACEHOLDER_SENTINEL = "\x00"


def _declared_matcher(term: str) -> re.Pattern[str]:
    """Compile a declared vocabulary term into a matcher, expanding a separator-led `N`."""
    alternatives = [re.escape(term)]
    marked = _PLACEHOLDER_RE.sub(_PLACEHOLDER_SENTINEL, term)
    if _PLACEHOLDER_SENTINEL in marked:
        alternatives.append(
            re.escape(marked).replace(re.escape(_PLACEHOLDER_SENTINEL), r"\d+")
        )
    return re.compile("^(?:" + "|".join(alternatives) + ")$")


def run(corpus: Corpus) -> GuardResult:
    """Check every id-bearing table in the tracked Markdown corpus."""
    findings: list[Finding] = []
    checked = 0

    for rel in corpus.markdown:
        text = corpus.text(rel)
        tables = md_table.find_tables(text)
        id_tables = [
            t
            for t in tables
            if t.headers and md_table.strip_markup(t.headers[0]).lower() in _ID_HEADERS
        ]
        if not id_tables:
            continue

        # One implementation, in `tools/lib/md_table.py` — `symbols` reads the same
        # vocabularies to tell a disposition term from a code symbol.
        vocab = {k: v for k, v in md_table.vocabulary_terms(text).items()
                 if k not in _ID_HEADERS}

        # ---- 1. unique ids, ACROSS every id-table in the document -------------------------
        # Across, not within: the eleven collisions that motivated this guard were each a pair
        # spanning two tables in one file, so a per-table check would have passed on all of them.
        seen: dict[str, int] = {}
        for table in id_tables:
            for offset, row in enumerate(table.rows):
                if not row or not row[0].strip():
                    continue
                key = md_table.strip_markup(row[0])
                line = table.first_row_line + offset
                checked += 1
                first = seen.get(key)
                if first is not None:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line,
                            message=f"duplicate register id {key!r} — first seen at line {first}",
                            evidence=(
                                "One id names two rows, so every citation of it is ambiguous and "
                                "the register cannot answer which finding is meant."
                            ),
                            severity=Severity.HIGH,
                        )
                    )
                else:
                    seen[key] = line

        # ---- 2. ragged rows ---------------------------------------------------------------
        for table in id_tables:
            for line, count in table.ragged_rows():
                findings.append(
                    Finding(
                        guard=GUARD,
                        path=rel,
                        line=line,
                        message=f"row has {count} cell(s), the header declares {table.width}",
                        evidence=(
                            "A ragged row does not error — the cells after a missing pipe shift "
                            "left, so every consumer indexing by position reads the wrong column."
                        ),
                        severity=Severity.MEDIUM,
                    )
                )

        # ---- 3. undeclared vocabulary terms ------------------------------------------------
        for table in id_tables:
            for col, header in enumerate(table.headers):
                name = md_table.strip_markup(header).lower()
                terms = vocab.get(name)
                if not terms:
                    continue
                matchers = [(t, _declared_matcher(t)) for t in terms]
                for offset, row in enumerate(table.rows):
                    if len(row) <= col:
                        continue
                    value = md_table.strip_markup(row[col])
                    if not value:
                        continue
                    checked += 1
                    if any(m.match(value) for _, m in matchers):
                        continue
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=table.first_row_line + offset,
                            message=f"{name} {value!r} is not declared in this document's own "
                            f"{name} vocabulary",
                            evidence=(
                                f"declared: {', '.join(sorted(terms))} — a row carrying a term the "
                                "document never defines cannot be classified by any rule that "
                                "reads the vocabulary"
                            ),
                            severity=Severity.MEDIUM,
                        )
                    )

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: every register id is unique, every row is whole, every governed value declared "
        f"({checked} value(s) across the tracked corpus)",
        checked=checked,
        floor=_FLOOR,
    )
