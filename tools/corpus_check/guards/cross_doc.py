"""``cross-doc`` — when two documents enumerate the same set, the sets must match.

**What already owns five instances of this, and is not re-asked.** `tools/health` `CONS-01` through
`CONS-05` each guard one specific pair: impact-map prefixes against the taxonomy, manifest ids
against the taxonomy, the rulebook's locked-file table against `VERSION.json`, the emitted gate
labels against `PRECEDENCE` and the contradiction matrix, and `PROJECT_VERSION` against
`CHANGELOG.md`. Those five pairs have an owner and are not touched here.

**What was missing.** Two pairs that this repository's own rules state in prose and leave to human
care — which is the arrangement `docs/process/RULES.md` Rule 2 exists to end:

1. **Every cited register key must exist in its register.** `OG-47`, `L-15`, `R2` are cited across
   the handover documents as though they were addresses. A citation to a key the register does not
   contain sends a reader to look something up that is not there — and, worse, reads as evidence
   that a decision was recorded when it was not.

2. **A `SCHEDULED (Phase N)` row must be honoured by the plan.** `OPEN_GATES.md`'s own "Rules for
   this file" #6 says it outright: *"A SCHEDULED row must name the phase AND that phase must name
   the work. Two documents, one claim, checked against each other."* Written as a rule, enforced by
   nobody. It is the load-bearing rule of the operator's phase gate: the **only** permitted deferral
   is one a later phase's own row declares, so an unhonoured `SCHEDULED` row is a defect that has
   been parked while looking scheduled.

3. **The doctrine's mandatory guard set must all be registered.** `DOC_WRITING_DOCTRINE.md` §5 is a
   law file; its guard table is a *minimum*, so the comparison is one-directional by design —
   every mandated guard must exist, and a registry carrying more than the minimum is compliant, not
   in breach. `register` is exactly such an extra and `docs/plan/PHASE3_OVERLAP.md` records why.
"""

from __future__ import annotations

import re

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.corpus_check.text import (
    is_append_only_record,
    iter_prose_lines_with_headings,
    under_dated_heading,
)
from tools.lib import md_table

GUARD = "cross-doc"

_DOCTRINE = "docs/framework/DOC_WRITING_DOCTRINE.md"
_GUARD_REGISTRY = "tools/corpus_check/guards/__init__.py"

# A citation to a register key: `OG-47`, `L-15`. Backticked, so prose dates and versions cannot
# match. The PREFIX VOCABULARY IS DERIVED from the registers themselves — nothing is listed here.
_KEY_RE = re.compile(r"`([A-Z][A-Z0-9]{0,9})-?(\d{1,3})`")

# A phase reference inside a disposition cell: `SCHEDULED (Phase 4)`.
_PHASE_RE = re.compile(r"Phase\s+(\d+)", re.IGNORECASE)

# A backticked document path cited as the evidence for a deferral.
_DOC_PATH_RE = re.compile(r"`((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.md)`")

# **A deferral can hide in a table that never had a `disposition` column at all** (`P8-028`). Check
# 2 above can only see a `SCHEDULED (Phase N)` deferral when it sits in a `disposition` cell — but
# `OPEN_GATES.md`'s own `## Closed` table (`| id | closed | title | how |`) has no such column, so
# a row that reads as closed can still carry a live deferral in its `how` prose and never be
# examined by rule 6's honoured-deferral machinery. Three markers, ALL required in the SAME row,
# keep this from firing on ordinary history: this corpus's `## Closed` table alone mentions "Phase
# N" in 9 rows and "scheduled" in 5, almost all of them narrating what a guard or rule now does —
# only a row that also says the work itself was left undone (`_UNBUILT_RE`) is a defect wearing a
# closed label rather than a closed defect that happens to discuss phases.
_SCHEDULED_RE = re.compile(r"\bschedul(?:ed|ing)?\b", re.IGNORECASE)
_UNBUILT_RE = re.compile(r"\bnot\s+(?:yet\s+)?built\b", re.IGNORECASE)

# **Raised 5 -> 40, `P8-054`.** 5 was ~1.5% of this guard's own measured live coverage (~325+
# cross-document claims) — the same order of magnitude `symbols` and `built-claims` were pinned
# at. 40 leaves comfortable room below the live count for legitimate corpus edits while being
# materially above the level the finding measured.
_FLOOR = 40


# A plan phase row marked finished. Both spellings this corpus uses.
# A plan phase row marked finished. **Every spelling this corpus and its neighbours use** — the
# first version knew only `✅` and `— DONE <sha>`, and Pass 7 marked a phase `**COMPLETE**
# … finished 2026-08-22, shipped` and got no findings at all (`OG-99`).
_COMPLETE_RE = re.compile(
    r"✅|✔|\bDONE\b|\bCOMPLETE[D]?\b|\bSHIPPED\b|\bFINISHED\b|\bCLOSED\b", re.IGNORECASE
)


def phase_rows(text: str) -> dict[str, str]:
    """Every phase row in ``text``, keyed by phase number. **The** definition of a phase row.

    A *phase table* is one whose first header cell is ``#`` and which carries a ``phase`` column —
    derived from the table's shape, so a host project's plan works unchanged. Rows are matched on
    the first cell's leading number, so a completion marker (``3 ✅``) does not defeat it. The
    first table to claim a number wins, which is what the single-row reader below always did.

    Exported because ``tools.health`` ``CONS-13`` audits the same rows from the other side, and two
    readers with two notions of "a phase row" is the drift `RULES.md` Rule 1 forbids.
    """
    found: dict[str, str] = {}
    for table in md_table.find_tables(text):
        headers = [md_table.strip_markup(h).lower() for h in table.headers]
        if not headers or headers[0] != "#" or "phase" not in headers:
            continue
        for row in table.rows:
            if not row:
                continue
            number = re.match(r"\**\s*(\d+)", md_table.strip_markup(row[0]))
            if number and number.group(1) not in found:
                found[number.group(1)] = " | ".join(row)
    return found


def marks_complete(row: str) -> bool:
    """Does this phase row declare itself finished? **The** definition, for every reader.

    Kept as a function over :data:`_COMPLETE_RE` rather than exporting the pattern, so the
    vocabulary can grow (it has, from two spellings to seven — `OG-99`) without every caller
    learning about it.
    """
    return bool(_COMPLETE_RE.search(row))


def _phase_row(text: str, phase: str) -> str | None:
    """The plan's own table row for ``phase``, as one string, or ``None`` if it has none."""
    return phase_rows(text).get(phase)


def _resolve_doc(corpus: Corpus, cited: str) -> str | None:
    """Resolve a cited document, **by basename when it carries no directory**.

    This corpus cites its own plans by bare filename — ``BUILD_PLAN.md``, ``HANDOFF.md`` — and only
    spells a full path when disambiguating. A resolver that required a directory separator found no
    plan document for six scheduled rows and reported every one of them as an unhonoured deferral.
    An ambiguous basename (two tracked files with the same name) resolves to nothing rather than to
    a guess.
    """
    if corpus.resolves(cited):
        return cited
    if "/" in cited:
        return None
    matches = [rel for rel in corpus.markdown if rel.rsplit("/", 1)[-1] == cited]
    return matches[0] if len(matches) == 1 else None


def _register_keys(corpus: Corpus) -> dict[str, set[str]]:
    """``prefix -> {keys}`` for every id-column table in the tracked corpus.

    Structural, exactly as the `register` guard finds registers, so the two agree by construction
    about what a register is.
    """
    keys: dict[str, set[str]] = {}
    for rel in corpus.markdown:
        for table in md_table.find_tables(corpus.text(rel)):
            if not table.headers or md_table.strip_markup(table.headers[0]).lower() != "id":
                continue
            for row in table.rows:
                if not row or not row[0].strip():
                    continue
                value = md_table.strip_markup(row[0])
                match = re.fullmatch(r"([A-Z][A-Z0-9]{0,9})-?(\d{1,3})", value)
                if match:
                    keys.setdefault(match.group(1), set()).add(value)
    return keys


def _heading_keys(corpus: Corpus) -> dict[str, set[str]]:
    """Keys a register declares as HEADINGS rather than table rows.

    **Prose only** (`OG-164`). This scanned raw text, so a `## OG-999` heading shown inside a
    fenced code block ANYWHERE in the corpus defined that key, and every citation of it then
    resolved. `test_refs._defined_ids` records this exact lesson in its own docstring — *"A ground
    truth that documentation can widen is not a ground truth"* — and strips Python docstrings with
    `ast` for it. A register's key space is defined by its real headings, not by an example of one.

    **The hyphen is optional, and that is the whole point.** This corpus runs two key spaces under
    the letter ``L``: `LESSONS.md` writes ``## L-15 — …`` and `RULEBOOK.md` writes ``## L1 — …``.
    A pattern requiring the hyphen sees only the first, so every citation of a *law* — `L4`, `L6`,
    `L7` — read as a citation to a lesson that does not exist. Both spellings are registered under
    the prefix so a citation in either form resolves.
    """
    keys: dict[str, set[str]] = {}
    for rel in corpus.markdown:
        for match in re.finditer(
            r"^#{2,4}\s*\**\s*([A-Z][A-Z0-9]{0,9})-?(\d{1,3})\b", md_table.without_fenced_blocks(corpus.text(rel)), re.MULTILINE
        ):
            prefix, number = match.group(1), match.group(2)
            bucket = keys.setdefault(prefix, set())
            bucket.add(f"{prefix}-{number}")
            bucket.add(f"{prefix}{number}")
    return keys


def run(corpus: Corpus) -> GuardResult:
    """Check cited register keys, honoured deferrals, and the doctrine's mandatory guard set."""
    findings: list[Finding] = []
    checked = 0

    # ---- shared derivation --------------------------------------------------------------
    universe = _register_keys(corpus)
    for prefix, found in _heading_keys(corpus).items():
        universe.setdefault(prefix, set()).update(found)
    # A prefix is only enforceable if the corpus actually registers keys under it. This is what
    # keeps the guard silent about `SUITE-05` (a check id — `test-refs` owns those) and about
    # `WCAG-2` or `UTF-16`, which are not keys at all.
    enforceable = {p for p, keys in universe.items() if len(keys) >= 3}

    # ---- 1. every cited register key exists ----------------------------------------------
    for rel in corpus.markdown:
        doc_text = corpus.text(rel)
        # **A declared append-only record quotes what a pass FOUND** (`OG-180`), including the probe
        # keys a verifier invented to attack a guard — `VERIFICATION_LOG.md` Pass 8 quotes `OG-999`
        # verbatim because a verifier used it to show a fenced heading could define a register key.
        # Reporting that is reporting the log for recording what it saw, which is the failure mode
        # that gets a gate switched off. Same `is_append_only_record` + `under_dated_heading` pair
        # the four other path guards already use, so "record" means one thing across the engine.
        doc_is_record = is_append_only_record(doc_text)
        for line_no, line, headings in iter_prose_lines_with_headings(doc_text):
            if doc_is_record and under_dated_heading(headings):
                continue
            for match in _KEY_RE.finditer(line):
                prefix = match.group(1)
                if prefix not in enforceable:
                    continue
                cited = match.group(0).strip("`")
                checked += 1
                if cited in universe[prefix]:
                    continue
                # Tolerate the two spellings the corpus uses interchangeably (`L-15` / `L15`).
                alt = cited.replace("-", "") if "-" in cited else f"{prefix}-{match.group(2)}"
                if alt in universe[prefix]:
                    continue
                findings.append(
                    Finding(
                        guard=GUARD,
                        path=rel,
                        line=line_no,
                        message=f"cites `{cited}`, which no register defines",
                        evidence=f"{prefix}-* keys are registered in this corpus, so this is a "
                        f"register citation; the register has "
                        f"{len(universe[prefix])} key(s) under that prefix",
                        severity=Severity.HIGH,
                    )
                )

    # ---- 2. a SCHEDULED deferral must be honoured by the plan it names ---------------------
    for rel in corpus.markdown:
        text = corpus.text(rel)
        for table in md_table.find_tables(text):
            if not table.headers or md_table.strip_markup(table.headers[0]).lower() != "id":
                continue
            cols = md_table.column_index(table.headers, ("disposition",))
            disposition_col = cols.get("disposition")
            if disposition_col is None:
                continue
            for offset, row in enumerate(table.rows):
                if len(row) <= disposition_col:
                    continue
                disposition = md_table.strip_markup(row[disposition_col])
                phase = _PHASE_RE.search(disposition)
                if not phase or "schedul" not in disposition.lower():
                    continue
                checked += 1
                line_no = table.first_row_line + offset
                rest = " ".join(row[disposition_col + 1 :])
                cited_docs = [d for d in (_resolve_doc(corpus, p) for p in _DOC_PATH_RE.findall(rest)) if d]
                if not cited_docs:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"row {md_table.strip_markup(row[0])!r} is "
                            f"{disposition!r} but cites no plan document that resolves",
                            evidence="a deferral the plan does not name is a defect parked while "
                            "looking scheduled — this register's own rule 6",
                            severity=Severity.HIGH,
                        )
                    )
                    continue
                # **Resolve against the plan's actual phase ROW, not a substring.** The first
                # version searched every cited document for the literal "Phase N" — so a row could
                # defer to a phase the plan does not have (`BUILD_PLAN.md` contains zero
                # occurrences of "Phase 7"; the two Phase-7 rows passed only because the phrase
                # appeared in the *citing* cell), and a verifier re-pointed a row at an unrelated
                # phase with the guard staying green (`OG-88`).
                wanted_phase = phase.group(1)
                # **EVERY cited document, not the first one that answers.** Breaking on the first
                # match let a decoy `.md` carrying any `| # | Phase |` table remove a row from the
                # COMPLETE check entirely — Pass 7 added one and watched `OG-07` drop out of the
                # findings (`OG-99`). If ANY cited plan marks the phase complete, the deferral is
                # to finished work whatever another cited document says.
                plan_rows = [
                    row for row in (_phase_row(corpus.text(doc), wanted_phase) for doc in cited_docs)
                    if row is not None
                ]
                plan_row = next((r for r in plan_rows if _COMPLETE_RE.search(r)), None) or (
                    plan_rows[0] if plan_rows else None
                )
                row_id = md_table.strip_markup(row[0])

                if plan_row is None:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"row {row_id!r} defers to Phase {wanted_phase}, but "
                            f"{', '.join(cited_docs)} has no phase table row for it",
                            evidence="a deferral is only legal if a later phase DECLARES the work; "
                            "a phase with no row in the plan declares nothing",
                            severity=Severity.HIGH,
                        )
                    )
                elif _COMPLETE_RE.search(plan_row):
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"row {row_id!r} defers to Phase {wanted_phase}, which the "
                            "plan marks COMPLETE",
                            evidence=f"the phase row reads {plan_row[:110]!r} — a deferral to "
                            "finished work is parked forever: the phase that was going to close "
                            "it has already ended",
                            severity=Severity.HIGH,
                        )
                    )
                # **THE PLAN MUST NAME THE ROW IT ACCEPTS** (`OG-171`).
                #
                # Everything above proves the cited phase EXISTS and is not already complete.
                # Nothing proved the phase declares THIS work — the rule this guard's own docstring
                # quotes from `OPEN_GATES.md` rule 6: *"A SCHEDULED row must name the phase AND that
                # phase must name the work."* Measured at `ba0294a`: all four deferrals passed while
                # `BUILD_PLAN.md`'s phase rows named **zero** of them, and `OG-63` deferred figure
                # `data_sources` work to a phase whose row is about document identity and archiving.
                #
                # "Does this phase declare that work?" is a semantic question no grep answers. The
                # mechanical form of the same question is exact: **the phase row must name the key.**
                # A deferral is then a two-sided agreement — the register points at the phase, the
                # phase points back — and neither side can be moved alone.
                elif row_id and row_id not in plan_row:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"row {row_id!r} defers to Phase {wanted_phase}, but that "
                            f"phase's plan row does not name it",
                            evidence="a deferral is only honoured when the phase declares the work "
                            "(OPEN_GATES rule 6). Name the key in the phase row, or re-disposition "
                            "the finding — otherwise it is a defect parked while looking scheduled",
                            severity=Severity.HIGH,
                        )
                    )

    # ---- 2b. a deferral hiding in a table with NO disposition column must still be caught -----
    #
    # Same record exemption as check 1: a document must DECLARE itself an append-only record
    # (`is_append_only_record`) AND the specific row must sit under a dated heading
    # (`under_dated_heading`) before it is exempt — otherwise `VERIFICATION_LOG.md` quoting this
    # very defect's evidence (which itself carries "Phase 7" + "scheduled" + "not built") would be
    # reported for accurately recording what a verifier found, the exact failure mode `OG-137`
    # and `OG-159` were closed for.
    for rel in corpus.markdown:
        text = corpus.text(rel)
        doc_is_record = is_append_only_record(text)
        heads_by_line = {n: heads for n, _line, heads in iter_prose_lines_with_headings(text)}
        for table in md_table.find_tables(text):
            if not table.headers or md_table.strip_markup(table.headers[0]).lower() != "id":
                continue
            cols = md_table.column_index(table.headers, ("disposition",))
            if cols.get("disposition") is not None:
                continue  # check 2 above already examines this table
            for offset, row in enumerate(table.rows):
                line_no = table.first_row_line + offset
                if doc_is_record and under_dated_heading(heads_by_line.get(line_no, ())):
                    continue
                row_text = " ".join(md_table.strip_markup(cell) for cell in row)
                if not (
                    _PHASE_RE.search(row_text)
                    and _SCHEDULED_RE.search(row_text)
                    and _UNBUILT_RE.search(row_text)
                ):
                    continue
                checked += 1
                row_id = md_table.strip_markup(row[0]) if row else "?"
                findings.append(
                    Finding(
                        guard=GUARD,
                        path=rel,
                        line=line_no,
                        message=f"row {row_id!r} reads as a SCHEDULED deferral (names a phase, "
                        "calls itself scheduled, and says the work is not built) but sits in a "
                        f"table with no `disposition` column, so it never reaches check 2 above",
                        evidence="a deferral parked in a table this guard cannot see is a defect "
                        "wearing a closed label; give the table a `disposition` column, or move "
                        "the row to a table that has one, so rule 6 can actually check it",
                        severity=Severity.HIGH,
                    )
                )

    # ---- 3. every guard the doctrine mandates is registered --------------------------------
    doctrine = corpus.text(_DOCTRINE)
    doctrine_table = md_table.find_table(doctrine, required_headers=("guard", "rule"))
    registry = corpus.text(_GUARD_REGISTRY)
    if doctrine_table and registry:
        registered = set(re.findall(r"^\s*\(([a-z_]+)\.GUARD,", registry, re.MULTILINE))
        # The registry keys on module names (`test_refs`); the doctrine writes guard names
        # (`test-refs`). Normalise once, here, rather than letting two spellings diverge.
        registered_names = {name.replace("_", "-") for name in registered}
        for offset, row in enumerate(doctrine_table.rows):
            if not row:
                continue
            # The cell is `` `rendered-output` **[UE-S4]** `` — a backticked NAME plus an
            # evidence marker. Taking the whole cell read the marker as part of the guard's name
            # and reported a registered guard as missing, at CRITICAL, on the first real run.
            backticked = re.match(r"\s*`([^`]+)`", row[0])
            mandated = (backticked.group(1) if backticked else md_table.strip_markup(row[0]))
            mandated = mandated.replace("_", "-").strip()
            if not mandated:
                continue
            checked += 1
            if mandated not in registered_names:
                findings.append(
                    Finding(
                        guard=GUARD,
                        path=_DOCTRINE,
                        line=doctrine_table.first_row_line + offset,
                        message=f"§5 mandates the `{mandated}` guard; the registry does not have it",
                        evidence=f"registered: {', '.join(sorted(registered_names))} — the "
                        f"comparison is one-directional, so extra guards are compliant",
                        severity=Severity.CRITICAL,
                    )
                )

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: {checked} cross-document claim(s) agree — register keys resolve, every "
        f"deferral is honoured by the plan it names, every mandated guard is registered",
        checked=checked,
        floor=_FLOOR,
        evidence=f"enforceable key prefixes derived from the corpus: "
        f"{', '.join(sorted(enforceable)) or 'none'}",
    )
