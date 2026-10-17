"""``counts`` — a number a document states about the system must re-derive from the system.

This is `docs/process/RULES.md` **Rule 2** made mechanical: *if a machine can derive it, prose must
not state it; and where a number genuinely must appear, a check must derive and compare it.*

**Why it needs to be mechanical rather than careful.** The evidence is in this repository's own
history. `BUILD_PLAN.md` carried a hand-maintained line-count column; it went stale, was re-measured
with a note reading *"do not hand-maintain these"*, and **four of six were stale again inside the
same session**, because the very fixes being recorded changed the files. Care does not keep a
restated fact true. Only derivation does.

**What already owns part of this, and is not re-asked.** `CONS-08` owns the *version* and *health
floor* claims in the four handover documents. `CONS-09` owns a different question about the
charter's sentence than this guard asks: `CONS-09` asserts the measurement **still exists in a
readable form** — that nobody quietly deleted the argument — while this guard asserts that **every
count anywhere in the corpus is right**. The overlap on one line is deliberate and the two
assertions are not the same.

**Every claim family below is derived from real data on disk.** None is a literal compared against
itself, which is doctrine §5's flat prohibition and the reason a checker can be trusted at all.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.corpus_check.text import (
    iter_prose_lines_with_headings,
    strip_inline_code,
    under_dated_heading,
)
from tools.lib import md_table

GUARD = "counts"

_FLOOR = 4


@dataclass(frozen=True)
class CountClaim:
    """One family of stated number, with the code that re-derives its truth."""

    name: str
    pattern: re.Pattern[str]
    derive: Callable[[Corpus], int | None]
    source: str
    severity: Severity = Severity.HIGH


# ---------------------------------------------------------------------------- derivations ----
# Each reads a real artifact. A derivation returning None means "could not measure", which produces
# no finding at all — a guard must never turn its own blindness into someone else's defect.


def _tracked_markdown(corpus: Corpus) -> int | None:
    return len(corpus.markdown) if corpus.available else None


def _governed(corpus: Corpus) -> int | None:
    return len(corpus.governed) if corpus.available else None


def _manifest_rows(corpus: Corpus) -> int | None:
    table = md_table.find_table(
        corpus.text("docs/design/doc-system/DOC_MANIFEST.md"),
        required_headers=("id", "variants"),
        require_separator=False,
    )
    return len(table.rows) if table else None


def _taxonomy_prefixes(corpus: Corpus) -> int | None:
    table = md_table.find_table(
        corpus.text("docs/design/doc-system/TAXONOMY.md"),
        required_headers=("prefix",),
        require_separator=False,
    )
    return len(table.rows) if table else None


def _contradiction_rows(corpus: Corpus) -> int | None:
    table = md_table.find_table(
        corpus.text("docs/design/doc-system/CONTRADICTION.md"),
        required_headers=("conflict", "resolution"),
        require_separator=False,
    )
    return len(table.rows) if table else None


def _locked_files(corpus: Corpus) -> int | None:
    try:
        data = json.loads(corpus.text("docs/design/doc-system/VERSION.json"))
    except ValueError:
        return None
    files = data.get("rulebook_files")
    return len(files) if isinstance(files, list) else None


def _highest_law(corpus: Corpus) -> int | None:
    """The highest law number the rulebook actually defines, from its own ``### L<n>`` headings."""
    numbers = [
        int(m.group(1))
        for m in re.finditer(
            r"^#{2,4}\s*L(\d{1,2})\b", corpus.text("docs/design/doc-system/RULEBOOK.md"), re.MULTILINE
        )
    ]
    return max(numbers) if numbers else None


def _health_checks(corpus: Corpus) -> int | None:
    """The number of registered health checks, counted from the ``CHECKS`` tuple's own source.

    Parsed rather than imported. Importing `tools.health.checks` from inside a guard pulls in the
    whole check module at corpus-check time — and, more to the point, a guard that has to import
    the thing it measures cannot measure a repository that is merely *being read*, which is exactly
    what a verification lab does.
    """
    text = corpus.text("tools/health/checks.py")
    match = re.search(r"^CHECKS:.*?=\s*\((.*?)^\)", text, re.DOTALL | re.MULTILINE)
    if not match:
        return None
    body = match.group(1)
    entries = [
        line.strip().rstrip(",")
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return len(entries) or None


def _corpus_guards(corpus: Corpus) -> int | None:
    r"""The number of registered corpus guards, parsed from the ``GUARDS`` tuple with ``ast``.

    **A one-line regex is not a parser** (`OG-179`). This counted lines matching
    ``^\s*\([a-z_]+\.GUARD,\s*[a-z_]+\.run\),`` — so a `ruff`-clean line wrap of any single
    registration, which changes nothing about the program, dropped the count by one and made every
    document stating it false. The ground truth for "how many guards are registered" has to come
    from the structure of the tuple, not from how it happens to be formatted.

    Same class as `OG-166` (symbol resolution by substring) and `OG-164` (a key space widened by a
    fenced heading): a fact the code owns, read by looking at the text instead of the code.
    """
    return _sequence_length(corpus.text("tools/corpus_check/guards/__init__.py"), "GUARDS")


def _sequence_length(text: str, name: str) -> int | None:
    """``len()`` of a module-level tuple/list literal called ``name``, parsed with ``ast``.

    Lifted out of `_corpus_guards`' body rather than copied for `PRECEDENCE`: both need the
    identical "annotated or plain assignment, tuple or list" tolerance, and `OG-179`'s lesson —
    **a one-line regex is not a parser** — is only learned once if there is one implementation of
    it. Two copies is how the second one quietly stops accepting `AnnAssign`.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        # `GUARDS: tuple[...] = (...)` is an AnnAssign, not an Assign — both are accepted so a
        # later change to (or from) the annotation cannot silently zero the count.
        target: ast.expr | None
        value: ast.expr | None
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign):
            target = node.targets[0] if node.targets else None
            value = node.value
        else:
            continue
        if not (isinstance(target, ast.Name) and target.id == name):
            continue
        if isinstance(value, (ast.Tuple, ast.List)):
            return len(value.elts) or None
    return None


def _gate_functions(corpus: Corpus) -> int | None:
    """The number of ``gate_*`` functions the export sanitizer defines, parsed with ``ast``.

    **This is the one number this project has watched go stale twice** (`OG-27`: a stated
    "7-gate precedence spine" against a `PRECEDENCE` that held 9 and then 17), and until now it was
    the one with no derivation at all. `OG-155`'s own closing row states *"All 8 gate functions are
    reachable today"* directly above `tools/health/checks.py`'s `CONS-04`, whose `gate_fns` set has
    **seven** members — and it had seven at `e8c32ba` too, so the sentence was false on the day it
    was written and stayed false because nothing could read it.

    **Deliberately the same expression `CONS-04` uses** — `ast.walk`, `ast.FunctionDef`,
    ``name.startswith("gate_")`` over `export_sanitizer.py` — so the guard and the health check
    cannot disagree about what a gate function is. If `CONS-04` ever widens its set (to
    `AsyncFunctionDef`, say), this must widen with it or the two will report different truths about
    the same tuple, which is the defect class this whole guard exists to close.
    """
    text = corpus.text("tools/docgen/export_sanitizer.py")
    if not text:
        return None
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    total = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("gate_")
    )
    return total or None


def _precedence_labels(corpus: Corpus) -> int | None:
    """The number of entries in ``export_sanitizer.PRECEDENCE``, parsed with ``ast``.

    A **second, different** universe from `_gate_functions` and the reason `OG-27` was wrong twice:
    `PRECEDENCE` carries every gate LABEL the engine adjudicates — including `hash_gate`, `header`,
    `staged-content-scanner`, `build`, `pdf` and `run_gates`, none of which is a ``gate_*``
    function. Anyone re-deriving "how many gates" from one and comparing against prose written from
    the other gets a false answer with a straight face, so the two are separate families with
    separate patterns, never one family with one number.

    Parsed, never imported: importing `export_sanitizer` from inside a guard pulls the whole docgen
    package in at corpus-check time and makes the count depend on whether the environment can
    execute it — see `_health_checks`' docstring for the same decision, made for the same reason.
    """
    return _sequence_length(corpus.text("tools/docgen/export_sanitizer.py"), "PRECEDENCE")


# The heading that opens the live half of a gate register, and the disposition that stops a phase.
# `register` already validates that `BLOCKS_PHASE_N` is a legal *spelling*; nothing counted the
# rows carrying it, which is the whole gap — the vocabulary was guarded and the gate was not.
_OPEN_SECTION_RE = re.compile(r"^##\s+Open\s*$(?P<body>.*?)(?=^##\s|\Z)", re.DOTALL | re.MULTILINE)
_BLOCKS_PHASE_RE = re.compile(r"^BLOCKS_PHASE_\d+$")


def _open_blocking_rows(corpus: Corpus) -> int | None:
    r"""Rows in `OPEN_GATES.md`'s ``## Open`` table whose disposition blocks a phase.

    **The sentence this derives is the single one a next-phase session reads before deciding it may
    start**, and at `cdab0ad` it was false: `BUILD_PLAN.md` asserted *"carries zero rows marked
    `BLOCKS_PHASE_*`"* while `OG-181` sat open with exactly that disposition. The document even
    told the reader *"do not trust this sentence; re-derive it from `OPEN_GATES.md`"* — an
    instruction that concedes the claim is unverified, and which no code carried out.

    Three deliberate narrowings, each of which is a way this could have been wrong:

    1. **Any phase number** (``BLOCKS_PHASE_\d+``), never the literal `BLOCKS_PHASE_4`. `OG-172` is
       exactly this defect one layer up: the accounting measured `BLOCKS_PHASE_3`, a label the
       register's own vocabulary says can never legitimately appear again once Phase 3 completes,
       so the sentence was structurally incapable of seeing the only failure it exists to report.
    2. **The ``## Open`` section only.** The ``## Closed`` table is full of rows that *were*
       `BLOCKS_PHASE_N` and are not any more; counting those would report a permanent blocker.
    3. **``id``+``sev``+``disposition`` headers**, because `OPEN_GATES.md` opens with a *vocabulary*
       table whose header is ``| disposition | meaning |`` — matching on ``disposition`` alone binds
       to that one and returns 0, which is the exact wrong answer: a silent, confident "clear".

    Returns `None` — measure nothing, report nothing — when the register, the section or the column
    is absent, so a host project without a gate register is not accused of anything.
    """
    text = corpus.text("docs/process/OPEN_GATES.md")
    if not text:
        return None
    section = _OPEN_SECTION_RE.search(text)
    if section is None:
        return None
    table = md_table.find_table(
        section.group("body"),
        required_headers=("id", "sev", "disposition"),
        require_separator=False,
    )
    if table is None:
        return None
    columns = md_table.column_index(table.headers, ("disposition",))
    index = columns.get("disposition")
    if index is None:
        return None
    return sum(
        1
        for row in table.rows
        if index < len(row) and _BLOCKS_PHASE_RE.match(md_table.strip_markup(row[index]))
    )


# ------------------------------------------------------------------------------- claims ----
# The pattern must be specific enough that only the intended sentence matches. Every one of these
# requires a noun phrase, never a bare number: "56 documents" is a claim, "56" is a token.

def _retained_counter_examples(corpus: Corpus) -> int | None:
    """Every `test*` function under `tools/tests/`, parsed from source.

    **Added 2026-08-22 because a hand-written one was wrong** (`OG-107`): `CHANGELOG.md` claimed
    `111 → 132` retained counter-examples for `0.4.1`; the release commit actually carried **136**.
    Nothing caught it, because no family derived this number — the corpus was restating a fact the
    test tree owns, which is `docs/process/RULES.md` Rule 2, and the only defence against a Rule 2
    restatement is to derive it.

    Parsed with `ast`, never imported and never run: a count of what is RETAINED is a property of
    the source tree, and importing the suite from inside a guard would make the number depend on
    whether the environment can execute it. `test-refs` learned the same lesson (`L-24`) — a
    docstring mentioning a test name is not a test.
    """
    if not corpus.available:
        return None
    total = 0
    seen = False
    for rel in corpus.tracked:
        if not rel.startswith("tools/tests/") or not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(corpus.text(rel))
        except (SyntaxError, ValueError):
            return None
        seen = True
        total += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
        )
    return total if seen else None


CLAIMS: tuple[CountClaim, ...] = (
    CountClaim(
        "tracked documents",
        re.compile(r"\b(\d{1,4})\s+tracked\s+(?:Markdown\s+)?documents?\b", re.IGNORECASE),
        _tracked_markdown,
        "git ls-files '*.md'",
    ),
    CountClaim(
        "governed documents",
        re.compile(r"\b(\d{1,4})\s+governed\b", re.IGNORECASE),
        _governed,
        "tracked Markdown whose front matter declares `classification`",
    ),
    CountClaim(
        "manifest rows",
        re.compile(r"\b(\d{1,3})\s+manifest\s+rows?\b|\bmanifest.{0,20}?\b(\d{1,3})\s+rows?\b", re.IGNORECASE),
        _manifest_rows,
        "DOC_MANIFEST.md's own table",
    ),
    CountClaim(
        "doc-type prefixes",
        re.compile(r"\b(\d{1,3})\s+doc-type\s+prefix(?:es)?\b", re.IGNORECASE),
        _taxonomy_prefixes,
        "TAXONOMY.md's own table",
    ),
    CountClaim(
        "L11 rows",
        re.compile(r"\b(\d{1,3})\s+L11\s+(?:tie-breaker\s+)?rows?\b", re.IGNORECASE),
        _contradiction_rows,
        "CONTRADICTION.md's own table",
    ),
    CountClaim(
        "locked rulebook files",
        re.compile(r"\b(\d{1,3})\s+locked\s+(?:rulebook\s+)?files?\b", re.IGNORECASE),
        _locked_files,
        "VERSION.json `rulebook_files`",
    ),
    CountClaim(
        "highest law",
        re.compile(r"\bL1\s*[–\-—]\s*L(\d{1,2})\b"),
        _highest_law,
        "RULEBOOK.md's own `### L<n>` headings",
    ),
    CountClaim(
        "registered health checks",
        re.compile(r"\b(\d{1,3})\s+(?:registered\s+)?health\s+checks?\b|\b(\d{1,3})\s+checks?\s+are\s+registered\b", re.IGNORECASE),
        _health_checks,
        "the CHECKS tuple in tools/health/checks.py",
    ),
    CountClaim(
        "registered corpus guards",
        # **`P8-042`: the bare and word-numeral spellings this corpus actually uses.** `OG-179`
        # made `_corpus_guards` (the GROUND TRUTH) ast-derived instead of hand-counted — but the
        # pattern that reads the CLAIM still only knew `"N registered guards"`, so it stayed blind
        # to `HANDOFF.md`'s and `docs/design/ARCHITECTURE.md`'s ``ten guards`` and
        # `docs/plan/NEXT_SESSION.md`'s ``**10 guards**``. Adding an unqualified `\d+\s+guards?`
        # was MEASURED and rejected: it also matches `` `doctrine §5 guard set` `` (a section
        # number, not a count) in `BUILD_PLAN.md`, and unqualified word-numerals match `"Six
        # guards"`, `"Three guards"`, `"two guards"` and `"One guard"` in `PHASE3_OVERLAP.md`,
        # `LESSONS.md` and `OPEN_GATES.md` — every one of those names a SUBSET of guards discussed
        # in one passage, not the corpus total, and firing on them is a false claim of drift. The
        # bare digit form is accepted only **bold** (`**10 guards**`), the one shape this corpus's
        # stats-summary lines actually use and the only bare-digit spelling that does not collide
        # with a subset mention anywhere in the live corpus (measured: zero other `\*\*\d+
        # guards?\*\*` occurrences). The word form is accepted only for `ten` — see
        # `_WORD_NUMBERS`'s docstring for why the rest of the word-number list stays out.
        re.compile(
            r"\b(\d{1,3})\s+registered\s+guards?\b"
            r"|\*\*(\d{1,3})\s+guards?\*\*"
            r"|\b(ten)\s+guards?\b",
            re.IGNORECASE,
        ),
        _corpus_guards,
        "the GUARDS tuple in tools/corpus_check/guards/__init__.py",
    ),
    CountClaim(
        "retained counter-examples",
        re.compile(r"\b(\d{1,4})\s+retained\s+counter-examples?\b", re.IGNORECASE),
        _retained_counter_examples,
        "test* functions under tools/tests/, parsed with ast",
    ),
    CountClaim(
        "open blocking rows",
        # **Two spellings, because the sentence being guarded is rewritten every phase.** The
        # first is the phrasing `BUILD_PLAN.md` now uses; the second is the phrasing it used at
        # `cdab0ad` — *"carries zero rows marked `BLOCKS_PHASE_*`"* — kept so that reverting to the
        # old wording cannot switch the guard back off.
        #
        # ⚠ **The old spelling had to be matched on `rows marked`, NOT on the label.** `run()`
        # blanks inline code before matching, so `` `BLOCKS_PHASE_*` `` is a run of spaces by the
        # time any pattern sees the line: a pattern anchored on the label is structurally incapable
        # of reading the very sentence it exists for. The claim's discriminating noun phrase has to
        # live in PROSE. That, plus a paragraph wrap falling between "zero" and "rows" (this guard
        # scans line by line), is the mechanical reason the false sentence survived — it was
        # unreadable twice over, not merely unread.
        #
        # **A bare `N blocking rows` was MEASURED and rejected.** It matches four live lines, and
        # `docs/process/OPEN_GATES.md:127` — `OG-172`'s own closed row, in the undated `## Closed`
        # table and therefore NOT exempt — reads *"Both now assert zero blocking rows of ANY phase
        # number"*. That is a true record of what was asserted then; firing on it would report the
        # register for describing its own history, the mistake `test-refs` made in `OG-137`.
        # Both accepted spellings were measured at **zero** other occurrences in the live corpus.
        re.compile(
            r"\b(\d{1,3}|zero|no|one)\s+open\s+blocking\s+rows?\b"
            r"|\b(\d{1,3}|zero|no)\s+rows?\s+marked\b",
            re.IGNORECASE,
        ),
        _open_blocking_rows,
        "OPEN_GATES.md's `## Open` table, rows whose disposition matches BLOCKS_PHASE_<n>",
        Severity.CRITICAL,
    ),
    CountClaim(
        "gate functions",
        re.compile(r"\b(\d{1,3})\s+gate\s+functions?\b", re.IGNORECASE),
        _gate_functions,
        "gate_* FunctionDefs in tools/docgen/export_sanitizer.py, parsed with ast",
    ),
    CountClaim(
        "gate labels",
        # Matches nothing in this corpus today — `docs/process/RULES.md:85` forbids the
        # restatement outright (*not "the 9-gate sanitizer"*), and `OG-27` deleted the enumeration
        # rather than re-counting it. That is Rule 2 being obeyed, and the family exists so the
        # NEXT person to restate it is caught the same day. `docs/design/ARCHITECTURE.md` already
        # ships the `len(PRECEDENCE)` one-liner inside a fence, which is exactly where a count
        # belongs and which this guard deliberately cannot see.
        #
        # **`(\d+)-gate` was MEASURED and rejected**: 15 live matches spanning BOTH universes at
        # once — `README.md`'s *"7-gate leak sanitizer"* means the seven `gate_*` functions and is
        # right, while `OG-27`'s closed row *"states a 7-gate precedence spine"* means the
        # seventeen `PRECEDENCE` labels and is a record of a past error. One pattern cannot serve
        # two universes; it would have to call one of those two true sentences a lie.
        re.compile(r"\b(\d{1,3})\s+gate\s+labels?\b|\b(\d{1,3})\s+entries\s+in\s+`?PRECEDENCE", re.IGNORECASE),
        _precedence_labels,
        "the PRECEDENCE tuple in tools/docgen/export_sanitizer.py, parsed with ast",
    ),
)


# Word-numerals a CountClaim pattern may capture instead of a digit string. **Deliberately just
# `ten`** (`P8-042`) rather than the usual one-through-twenty list: this corpus's own prose uses
# "Six guards", "Three guards", "two guards" and "One guard" to mean a SUBSET discussed in one
# passage (a Pass's findings, a table's row count), never the corpus total — measured live, adding
# the full word list turned four of those subset mentions into false drift findings. `ten` is safe
# because every "ten guards" in this corpus already means the total, and it is the one word this
# defect's own evidence (`HANDOFF.md`, `docs/design/ARCHITECTURE.md`) actually uses.
#
# `zero`, `no` and `one` were added with the `open blocking rows` family (`GAP-BUILD_PLAN`). They
# are safe for the same reason `ten` is: a word here is only ever consulted for a group a family's
# OWN pattern chose to capture, and only that family accepts them. **The zero-state has to be
# spellable** — the sentence this guard exists for reads *"carries no open blocking rows"* the day
# the gate is clear, and a family that can only read digits would go quietly blind at exactly the
# moment its answer starts authorising work.
_WORD_NUMBERS = {"ten": 10, "zero": 0, "no": 0, "one": 1}


def _stated(match: re.Match[str]) -> int | None:
    """The first non-empty group — patterns with alternatives have several.

    A digit group parses directly; a WORD-numeral group (`_WORD_NUMBERS`) is looked up instead.
    """
    for group in match.groups():
        if not group:
            continue
        if group.isdigit():
            return int(group)
        mapped = _WORD_NUMBERS.get(group.lower())
        if mapped is not None:
            return mapped
    return None



def _is_record(line: str, headings: tuple[str, ...]) -> bool:
    """A DECLARED append-only record, heading-scoped — see `OG-165`."""
    return under_dated_heading(headings)


def run(corpus: Corpus) -> GuardResult:
    """Re-derive every stated count in the tracked corpus and compare."""
    truth: dict[str, int | None] = {c.name: c.derive(corpus) for c in CLAIMS}
    matched: dict[str, int] = {c.name: 0 for c in CLAIMS}
    findings: list[Finding] = []
    checked = 0

    for rel in corpus.markdown:
        for line_no, line, headings in iter_prose_lines_with_headings(corpus.text(rel)):
            # Heading-scoped, like `built-claims` and `symbols` — see `_is_record` (`OG-165`).
            if not line.strip() or _is_record(line, headings):
                continue
            # Inline code is an example or a symbol, not a claim: `` `--full` → 32 passed `` is
            # discussed as a command, and `LINE 47` in a code sample is not a count.
            scannable = strip_inline_code(line)
            for claim in CLAIMS:
                real = truth[claim.name]
                if real is None:
                    continue
                for match in claim.pattern.finditer(scannable):
                    stated = _stated(match)
                    if stated is None:
                        continue
                    checked += 1
                    matched[claim.name] += 1
                    if stated != real:
                        findings.append(
                            Finding(
                                guard=GUARD,
                                path=rel,
                                line=line_no,
                                message=f"states {stated} {claim.name}; the system has {real}",
                                evidence=f"derived from {claim.source} — {match.group(0).strip()!r}",
                                severity=claim.severity,
                            )
                        )

    # **Two different numbers, and conflating them was the defect.** `measurable` is how many
    # families' GROUND TRUTH could be computed from source; `active` is how many actually matched a
    # claim in the corpus. The summary used to report only the first as "N of N measurable claim
    # families", which reads as "nine families are doing work" while six matched nothing (`OG-87`).
    #
    # A family matching nothing is **not** a failure: it means the corpus does not restate that
    # fact, which is `docs/process/RULES.md` Rule 2 being obeyed. What it *would* hide is a pattern
    # that silently stopped working — so each family's pattern is proven to still match a synthetic
    # claim by a retained counter-example (`tools/tests/test_corpus_check.py`), not at runtime,
    # because at runtime there is nothing to compare a dead pattern against.
    measurable = sum(1 for v in truth.values() if v is not None)
    active = sum(1 for n in matched.values() if n)
    detail = "; ".join(
        f"{c.name}={truth[c.name]} (matched {matched[c.name]})"
        for c in CLAIMS
        if truth[c.name] is not None
    )
    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: all {checked} stated count(s) re-derive — {active} of {measurable} derivable "
        f"claim families matched anything ({len(CLAIMS) - measurable} not derivable here)",
        checked=checked,
        floor=_FLOOR,
        evidence=detail + ". A family matching 0 means the corpus does not restate that fact "
        "(Rule 2 obeyed); that each pattern still WORKS is proven by counter-example, not here.",
    )
