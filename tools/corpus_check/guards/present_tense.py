"""``present-tense`` — a thing marked planned may never be described in the present tense.

This is a standing rule in `HANDOFF.md` that, before this phase, had **zero** mechanical
enforcement, and `docs/plan/NEXT_SESSION.md` records three separate stale-state defects in one
phase that were instances of it. `DOC_WRITING_DOCTRINE.md` §5's taxonomy names the class precisely:
*"Feature never existed, stated in present tense under an approved stamp"* — and marks it
**mechanically catchable**.

**What this guard checks, stated narrowly on purpose.**

> A backticked repo path that the corpus does **not** contain, described on the same line by a
> present-tense existence verb, with no future, conditional or historical marker on that line.

Both halves are derived, so it cannot produce a confident false finding: existence is
``git ls-files``, and the verb list is closed and short.

**Why that narrowing is the honest one, rather than a weakening.** The general form — "is this
sentence about an unbuilt thing written in the present tense?" — needs to know which noun the verb
belongs to, and a regex that guesses would flag `OPEN_GATES.md`'s own *"this **is** Phase 3's
declared main work"*, which is a correct present-tense statement about a *deferral*, not a false
claim about an *artifact*. A guard that cries wolf on a register's justification column is a guard
somebody switches off. So this one answers only the question it can answer exactly, and the
doctrine's §7 already says which half no grep will ever reach: *direction-and-soundness errors — no
grep finds that; a careful reader does.*

**Relationship to `CONS-06`.** `CONS-06` requires a cited path to resolve to tracked content *or* be
declared in `docs/process/ABSENT_PATHS.md`. That registry is what makes deliberate absence legal —
and this guard is what stops it becoming a licence to describe an absent thing as though it were
here. The two are complementary: `CONS-06` asks *may this path be missing?*; this asks *then why is
the sentence in the present tense?*
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.corpus_check.text import (
    is_append_only_record,
    is_historical,
    iter_prose_lines_with_headings,
    under_dated_heading,
)
from tools.lib import md_table

GUARD = "present-tense"

_ABSENT_REGISTRY = "docs/process/ABSENT_PATHS.md"

# A backticked repo-relative path. The top-level segment is checked against the real tracked tree
# by the caller, so this pattern stays deliberately loose.
_PATH_RE = re.compile(r"`((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_./-]*)`")

# **A bare-filename tense check was BUILT, MEASURED, AND REJECTED here** (`OG-116`).
#
# The hole is real: `symbols` honours a name declared in `ABSENT_PATHS.md` so a document may
# legitimately NAME an absent file, and it excuses that name in ANY sentence — so a verifier wrote
# *"Today `build.py` renders every document in this repository"* about a declared-absent file and
# it passed both guards, this one because `_PATH_RE` requires a `/` and could not see it at all.
#
# The fix was implemented and run against the corpus. It produced **12 findings, 11 of them on
# correct prose**: `RULEBOOK.md` saying no `BRAND_MANIFEST.md` ships, `SKILL.md` describing
# `graph.json` as the output you get when you run the skill, `BUILD_PLAN.md` citing three
# `~/.claude/` files as measurement evidence, `THREAT_MODEL.md` naming the portfolio's own
# `secret-scan.sh`. Every one of those is a true sentence about something deliberately not in this
# repository — which is the entire reason `ABSENT_PATHS.md` exists.
#
# Widening `_ABSENCE_MARKERS` to cover them would be the fourth over-broad exemption list in this
# package, and the words needed (`no`, `output`, `supplies`) are exactly the ordinary English that
# made the first three holes. **A guard that reports eleven correct sentences to catch one wrong
# one is a guard people switch off**, and `docs/process/OPEN_GATES.md` records what that costs.
#
# This is the class the module docstring already names as out of reach: *direction-and-soundness
# errors — no grep finds that; a careful reader does.* Recorded rather than half-built, with the
# measurement, so the next session does not rediscover it as a gap.

# Present-tense existence/capability verbs. Closed and short: every entry asserts that the subject
# is here and working NOW. Padded with spaces so `is` cannot match inside "this".
_PRESENT_VERBS = (
    " is ", " are ", " has ", " have ", " ships ", " ships with ", " exists ", " exist ",
    " contains ", " provides ", " enforces ", " renders ", " runs ", " holds ", " lives ",
    " implements ", " exposes ", " returns ", " carries ", " covers ",
)

# Any one of these makes the sentence future, conditional, or hypothetical — in which case
# describing the artifact is not a claim that it exists.
# ⚠ SAME WARNING AS `_ABSENCE_MARKERS` BELOW, AND IT WAS EARNED TWICE.
#
# `LESSONS.md` L-23 was written in this session about a bare `" deliberately"` in the absence list.
# Only that list was narrowed. **This one was left broad, and an independent verifier walked a false
# present-tense claim straight past the guard using ordinary English** — seven of the entries here
# (`" if "`, `" when "`, `" after "`, `" until "`, `" may "`, `" should "`, `" could "`, `" to be "`)
# appear in normal prose with no futurity about the artifact at all, and each disabled the guard for
# the WHOLE PARAGRAPH.
#
# That is Rule 1's sibling clause exactly: the fix moved the hole instead of closing it. Every entry
# below now asserts futurity ABOUT THE THING'S EXISTENCE, and the counter-example plants a claim in a
# paragraph containing the innocent words to prove they no longer excuse it.
# **Audited against the corpus 2026-08-22, not against intent** (`L-23`), and cut on the result.
# Measurement: of the fifteen entries this list carried, exactly ONE — `" not yet"` — exempted a
# would-be finding anywhere in the corpus. The other fourteen were dead weight, and dead weight in
# a list of disarm switches is not free: each is a latent hole waiting for the sentence that trips
# it. `" will "` and `" shall "` are ordinary English modals that attach to ANY clause, so
# *"`docs/current/` is the archive root, and Phase 5 will extend it"* would have gone unflagged —
# the whole-line-exemption defect `CONS-08` was corrected for, and `L-26`'s moved hole a third time.
#
# What remains is only constructions that cannot describe a thing as present: an explicit
# not-yet/planned marker, or a conditional whose subject IS the artifact's existence. A future
# sentence with no present-tense verb was never flagged in the first place — the verb list gates
# this one — so removing the modals costs no legitimate exemption.
_FUTURE_MARKERS = (
    " going to ", " plans to ", " intends to ", " is to be ",
    " to be built", " to be written", " not yet", " planned",
    " once it exists", " when it exists", " if it existed",
)

# Markers that say the sentence is ABOUT the absence rather than asserting presence. Without these
# the guard would flag `ABSENT_PATHS.md`'s own rows, which exist precisely to say a path is missing.
# ⚠ EVERY ENTRY MUST BE ABOUT ABSENCE. An exemption marker is a switch that turns this guard OFF
# for a whole paragraph, so a broad word here is not a small inaccuracy — it is a silent hole.
#
# Measured, in this file, on the way to shipping it: the first draft carried a bare `" deliberately"`
# (intended for "deliberately absent"). `docs/plan/BUILD_PLAN.md`'s Phase 3 row says *"every guard
# **deliberately** falsified first"* — nothing to do with absence — and that one word exempted the
# single row that described `tools/corpus_check/` in the present tense while it did not exist. The
# guard went green on the exact finding it had been built to catch. `CONS-08` learned the identical
# lesson twice (its "bump" and arrow exemptions), which is why the counter-example for this guard
# asserts that shaped line is still caught.
_ABSENCE_MARKERS = (
    " absent", " missing", " does not exist", " do not exist", " not present", " never existed",
    " deliberately absent", " deliberately not", " deliberately excluded", " deliberately does not",
    " no longer", " not in this", " not in the repo", " not contain", " would be at ",
    " if it existed", " declared absent", " not shipped", " ships no",
    # The contracted forms are as common as the spelled-out ones in this corpus and were missed by
    # the first draft: `PROVENANCE.md` says a manifest listed "paths … that don't exist in this
    # package", which is a sentence ABOUT the absence being flagged as an assertion of presence.
    " don't exist", " doesn't exist", " didn't exist", " isn't ", " aren't ", " never shipped",
    # "not bundled here" is how this corpus says a path belongs to the engine's SOURCE project
    # rather than to this repository — `tools/docgen/AUTHORING_PROMPT.md`'s correction note is a
    # paragraph whose entire purpose is to say three documents are absent, and it was flagged for
    # saying so. A guard that reports a document for correctly declaring an absence is a guard
    # that punishes the fix it exists to ask for.
    " not bundled", " not included", " belong to the engine", " belongs to the engine",
)

_FLOOR = 3


# Punctuation, blanked before marker matching. Markers are WORD sequences; the corpus wraps those
# words in emphasis, backticks, parentheses and dashes, and each wrapper hid a marker in turn:
# `**not bundled here**` defeated `" not bundled"` on the first pass, and `(not bundled here)`
# defeated the same marker again after only emphasis was handled. Normalising all punctuation at
# once closes the class instead of the two instances. Apostrophes survive because markers contain
# them (`" don't exist"`).
_EMPHASIS_RE = re.compile(r"[^0-9a-z']+", re.IGNORECASE)


# A sentence boundary inside a paragraph. Terminal punctuation followed by whitespace and the
# start of a new sentence — a capital, a backtick, emphasis or an opening bracket.
#
# **Why sentences and not paragraphs, and why not lines either.** The exemption lists are switches
# that turn this guard OFF, so their SCOPE is the whole safety question. Paragraph scope let a
# marker in one sentence excuse a false claim in the next — Pass 7 walked a claim past the guard
# that way, and `_FUTURE_MARKERS`' ordinary-English modals made it easy. Line scope is the opposite
# error and was already measured: this corpus wraps at ~100 columns, so `AUTHORING_PROMPT.md` puts
# *"are **not bundled here**"* on one line and the paths it excuses on the next, and a line-scoped
# guard reported a paragraph for correctly declaring an absence.
#
# A sentence is the unit that owns a claim. It spans wrapped lines, so the real declaration still
# works, and it stops at the full stop, so the next claim is judged on its own. Measured on the
# live corpus at the time of the change: **zero** new findings — a pure narrowing.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z`*(\[])")


def _sentence_spans(joined: str) -> list[tuple[int, int]]:
    """``(start, end)`` character spans of each sentence in a joined paragraph."""
    bounds = [0]
    for match in _SENTENCE_SPLIT_RE.finditer(joined):
        bounds.append(match.end())
    bounds.append(len(joined))
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


@dataclass(frozen=True)
class _Paragraph:
    """Consecutive non-blank prose lines, with the heading stack they sit under."""

    lines: list[tuple[int, str]]
    headings: tuple[str, ...]


def _paragraphs(text: str) -> list[_Paragraph]:
    """Split a document's prose into paragraphs, keeping every line's original number.

    A blank line, a heading, or a table row ends a paragraph. Table rows are their own units
    because a register row is a self-contained statement — joining two rows would let one row's
    absence marker excuse the next row's claim.
    """
    out: list[_Paragraph] = []
    current: list[tuple[int, str]] = []
    headings: tuple[str, ...] = ()

    def flush() -> None:
        if current:
            out.append(_Paragraph(lines=list(current), headings=headings))
            current.clear()

    for line_no, line, stack in iter_prose_lines_with_headings(text):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            flush()
            headings = stack
            continue
        if stripped.startswith("|"):
            flush()
            headings = stack
            out.append(_Paragraph(lines=[(line_no, line)], headings=stack))
            continue
        if not current:
            headings = stack
        current.append((line_no, line))
    flush()
    return out


def run(corpus: Corpus) -> GuardResult:
    """Flag present-tense description of a path this repository does not contain.

    **Judged per SENTENCE, and the scope is the whole safety question.** Paragraphs are still the
    unit that gets assembled — this corpus wraps at about 100 columns, so one sentence routinely
    spans three lines, and `tools/docgen/AUTHORING_PROMPT.md` puts *"are **not bundled here**"* on
    one line with the paths it excuses on the next. A LINE-scoped guard reported that paragraph for
    correctly declaring an absence. But a PARAGRAPH-scoped one let a marker in one sentence excuse
    a false claim in the next, which is how Pass 7 walked a claim past this guard.

    So the paragraph is assembled and then split into sentences, and each sentence is judged alone:
    a present-tense verb in it, no future or absence marker in it. `is_historical` stays
    paragraph-wide, because a dated heading dates everything beneath it. Findings still cite the
    line the path is on.
    """
    roots = {rel.split("/", 1)[0] for rel in corpus.tracked if "/" in rel}
    # Paths `ABSENT_PATHS.md` declares absent ON PURPOSE, read from its own table — the same set
    # `symbols` and `CONS-06` consult, so the three cannot disagree about what is declared.
    # **Exact values only**, never prefixes: `docs/confidential/` is declared, and that must not
    # silently excuse `docs/confidential/POLICY.md`, which nobody has written.
    declared_absent = {
        md_table.strip_markup(row[0]).strip("`")
        for table in md_table.find_tables(corpus.text(_ABSENT_REGISTRY))
        if table.headers and md_table.strip_markup(table.headers[0]).lower() == "path"
        for row in table.rows
        if row
    }
    findings: list[Finding] = []
    checked = 0

    for rel in corpus.markdown:
        doc_is_record = is_append_only_record(corpus.text(rel))  # OG-140
        for para in _paragraphs(corpus.text(rel)):
            # The registry of deliberate absences declares absence **in its table**; every row
            # there names a path that is missing on purpose, so judging a row would flag the
            # document for doing its job.
            #
            # ⚠ It used to skip the WHOLE FILE, and a verifier planted a false present-tense claim
            # in that document's prose and walked it straight through (`OG-115`). "This document
            # is allowed to say a path is absent" never meant "nothing in this document is a
            # claim". `_paragraphs` isolates each table row as its own unit, which is exactly the
            # granularity this needs.
            if rel == _ABSENT_REGISTRY and len(para.lines) == 1 and (
                para.lines[0][1].lstrip().startswith("|")
            ):
                continue
            # Offsets into the joined paragraph, so a citation found on a line can be mapped back
            # to the SENTENCE that owns it. The join is a single space between lines, matching how
            # `_sentence_spans` reads it.
            joined_parts: list[str] = []
            line_offsets: list[tuple[int, int, str]] = []
            cursor = 0
            for line_no, line in para.lines:
                line_offsets.append((line_no, cursor, line))
                joined_parts.append(line)
                cursor += len(line) + 1
            joined = " ".join(joined_parts)

            # A record of what WAS is not a claim about what IS — but "how much text does one
            # record cover?" has two different right answers, and collapsing them was a hole.
            #
            # **A dated heading dates every sentence beneath it**, so that half is paragraph-wide
            # and short-circuits here. The other three exemptions `is_historical` carries — a date
            # on the text, a numeric transition, a past-tense marker — describe ONE sentence, and
            # applying them paragraph-wide let `" no longer"` in a first sentence excuse a false
            # present-tense claim in a second. The probe below found exactly that, after the
            # marker lists had already been scoped: `LESSONS.md` L-26, the hole moving again into
            # the one exemption that had not been narrowed with the others.
            if doc_is_record and under_dated_heading(para.headings):
                continue

            # Emphasis must not defeat a word marker. "are **not bundled here**" carries the
            # marker; " not bundled" with a leading space does not match "**not bundled" — which
            # is how the first draft still flagged the paragraph after the marker was added.
            judged: list[tuple[int, int, bool]] = []
            for start, end in _sentence_spans(joined):
                padded = " " + _EMPHASIS_RE.sub(" ", joined[start:end]).lower() + " "
                sentence = joined[start:end]
                live = (
                    any(v in padded for v in _PRESENT_VERBS)
                    and not any(m in padded for m in _FUTURE_MARKERS)
                    and not any(m in padded for m in _ABSENCE_MARKERS)
                    # Sentence-scoped, headings deliberately empty — the dated-heading half was
                    # already answered above, and passing them again would restore the paragraph
                    # scope this decomposition exists to remove.
                    and not is_historical(sentence, ())
                )
                judged.append((start, end, live))
            if not any(live for _s, _e, live in judged):
                continue

            for line_no, offset, line in line_offsets:
                for match in _PATH_RE.finditer(line):
                    at = offset + match.start()
                    if not any(start <= at < end and live for start, end, live in judged):
                        continue
                    cited = match.group(1)
                    if cited.split("/", 1)[0] not in roots:
                        continue
                    if "*" in cited or "<" in cited:
                        continue
                    checked += 1
                    if corpus.resolves(cited):
                        continue
                    if corpus.exists_untracked(cited) or (
                        corpus.is_ignored(cited) and cited in declared_absent
                    ):
                        # Real and deliberately untracked, **or declared absent by name**.
                        #
                        # `exists_untracked` alone was too strict: `docs/confidential/` is created
                        # on demand by `engine_config.confidential_dir()`, so it is legitimately
                        # missing from a clean checkout while three documents describe it in the
                        # present tense, correctly.
                        #
                        # But a declaration ALONE is too loose, and measuring it proved so
                        # immediately: `ABSENT_PATHS.md` also declares `tools/not_built_yet/` —
                        # the path this guard's own counter-examples plant — so excusing every
                        # declared name disarmed 49 of the guard's retained probes in one edit.
                        # The conjunction is the actual concept: **gitignored AND declared** means
                        # "a runtime path the engine creates", which is the only case where
                        # describing an absent thing in the present tense is true. Matched
                        # EXACTLY, so `docs/confidential/POLICY.md` — which nobody has written —
                        # is still refused, and a declared-but-tracked-shaped probe path is still
                        # refused.
                        #
                        # **`exists_untracked`, not
                        # `is_ignored`** (`OG-115`). Being gitignored says a path WOULD be
                        # untracked if it existed; it says nothing about whether it exists. So
                        # `docs/confidential/POLICY.md is the live security policy` passed while
                        # naming a file nobody has written, inside a gitignored tree. "Untracked
                        # is not unbuilt" is true only when the thing is actually there.
                        #
                        # `docs/confidential/` is the engine's own
                        # vault: RULEBOOK L14 confines non-public documents to it and
                        # `--local-preview` writes into it. `CLASSIFICATION.md`'s sentence
                        # "`docs/confidential/` is gitignored" is present tense AND true, and
                        # flagging it would report a document for correctly describing a design
                        # decision. Untracked is not unbuilt.
                        continue
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"describes `{cited}` in the present tense, but the corpus does "
                            "not contain it",
                            evidence=(
                                "A planned thing is never written in the present tense (HANDOFF.md "
                                "standing rule 5). Date the sentence, mark it planned, or build it."
                            ),
                            severity=Severity.HIGH,
                        )
                    )

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: {checked} present-tense path claim(s) checked; every one names something the "
        "corpus actually contains",
        checked=checked,
        floor=_FLOOR,
        evidence=f"{_ABSENT_REGISTRY} is excluded — declaring absence is that document's purpose",
    )
