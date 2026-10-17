"""Markdown text helpers shared by the guards. Stdlib only.

Everything here exists because more than one guard needs it, and a second copy of "which lines are
prose?" is exactly the kind of quiet divergence `OG-36` was: five readers, two answers, nobody
aware.

**The one idea that matters: a fenced code block is not a claim.** A document showing
``python3 -m <a.module.that.does.not.exist>`` inside a fence is *demonstrating*, not *asserting*,
and a guard
that cannot tell the difference produces false findings in the documents most worth checking —
which is how a gate teaches people to bypass it. Every guard that reads prose iterates
`iter_prose_lines`, never `str.splitlines`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

__all__ = [
    "DATE_RE",
    "heading_slugs",
    "is_append_only_record",
    "is_dated_record",
    "is_historical",
    "iter_all_lines_with_headings",
    "iter_prose_lines",
    "iter_prose_lines_with_headings",
    "prose_text",
    "slugify",
    "strip_inline_code",
    "under_dated_heading",
]

# An ISO date. This corpus dates everything it records, which is what makes the history/present
# distinction mechanical rather than a judgement call.
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# A clock time — `CHANGELOG.md`'s rows are `| 03:05 | …`, dated only by their section heading.
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")

# A numeric transition: "20 -> 22", "1.1.0 → 1.2.0". The arrow means *became*, so the first number
# is deliberately the old one. `CONS-08` carries the same exemption and the same warning with it:
# an arrow can also mean *produces* ("`--full` → 32 passed"), so the exemption requires a number on
# BOTH sides, which "produces" never has.
_TRANSITION_RE = re.compile(r"\d[\d.]*\s*(?:→|->|—>)\s*\d[\d.]*")

# Past-tense markers: every entry is a word that turns a sentence into a record of what WAS.
#
# ⚠ THIRD LIST OF THIS SHAPE, AND THE THIRD TO BE FOUND TOO BROAD. Every entry is a switch that
# turns `counts`, `symbols` AND `present_tense` off for a whole line or paragraph, so this is the
# widest-blast-radius list in the package.
#
# `" until "` and `" before "` were removed 2026-08-22: neither indicates past tense. "until you run
# it" and "before you push" are present-tense instructions, and this corpus is full of them — a
# retained counter-example proved `until` smuggling a false present-tense claim past the guard after
# `_FUTURE_MARKERS` had already been narrowed for the identical reason (`LESSONS.md` L-23).
#
# What remains are words that can only be about what WAS.
_PAST_MARKERS = (
    " was ", " were ", " used to ", " previously", " had been", " no longer",
    " stood at ", " has since ", " originally",
)

# A fence is three or more backticks or tildes at the start of a (possibly indented) line. The
# closing fence must be at least as long as the opening one and use the same character — that is
# CommonMark, and it matters here because this corpus nests ``` inside ~~~~ when showing Markdown.
_FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")

# Inline code spans. Non-greedy, and it deliberately does not try to honour CommonMark's
# equal-run-length rule: over-matching here only ever REMOVES text from a guard's view, which
# produces a missed finding rather than a false one. Given the choice, a guard should be quiet
# rather than wrong — `docs/process/OPEN_GATES.md` records what a noisy gate costs.
_INLINE_CODE_RE = re.compile(r"`[^`]*`")

_SLUG_STRIP_RE = re.compile(r"[^\w\- ]+", re.UNICODE)


def iter_prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(1-based line number, line)`` for every line **outside** a fenced code block.

    The fence lines themselves are not yielded either: an info string like ```` ```bash ```` is
    markup, not prose.
    """
    open_fence: str | None = None
    for n, line in enumerate(text.splitlines(), 1):
        match = _FENCE_RE.match(line)
        if open_fence is None:
            if match is not None:
                open_fence = match.group("fence")
                continue
            yield n, line
        else:
            if (
                match is not None
                and match.group("fence")[0] == open_fence[0]
                and len(match.group("fence")) >= len(open_fence)
                and not match.group("info").strip()
            ):
                open_fence = None
            continue


def iter_prose_lines_with_headings(text: str) -> Iterator[tuple[int, str, tuple[str, ...]]]:
    """Like `iter_prose_lines`, plus the **heading stack** each line sits under.

    The stack is what makes "is this a record or a claim?" mechanical. `CHANGELOG.md` writes
    ``## [0.3.4] — 2026-08-21`` and then an undated ``### Phase 3`` beneath it; a rule looking only
    at the nearest heading would read that subsection as a claim about *now*, and flag every count
    in a release note that was accurate the day it was written.
    """
    stack: list[tuple[int, str]] = []
    for n, line in iter_prose_lines(text):
        stripped = line.strip()
        # **At most three spaces of indent, which is CommonMark and not a stylistic preference.**
        # Four or more makes the line an INDENTED CODE BLOCK, and `iter_prose_lines` models fenced
        # blocks only — so `    # 2026-01-01 forged heading` was entering the heading stack as a
        # dated heading, and every following line inherited it. A dated heading is the widest
        # exemption in this package (`under_dated_heading` switches `built-claims` off wholesale),
        # so forging one from four spaces and a `#` disabled command checking for the rest of the
        # document (`OG-110`). Latent in this corpus — zero indented lines parse as headings today
        # — and one paste away from not being.
        if stripped.startswith("#") and len(line) - len(line.lstrip(" ")) < 4:
            level = len(stripped) - len(stripped.lstrip("#"))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, stripped))
        yield n, line, tuple(h for _lvl, h in stack)


def iter_all_lines_with_headings(text: str) -> Iterator[tuple[int, str, tuple[str, ...]]]:
    """Every line — **fenced code included** — with the heading stack it sits under.

    `iter_prose_lines_with_headings` drops fenced blocks, which is right for prose guards and wrong
    for `built-claims`: the launch command a human actually executes lives inside a ```` ```bash ````
    fence, and `CONS-08` was corrected once for being unable to see it.

    But a guard that reads fences still needs to know a RECORD from an INSTRUCTION.
    `docs/process/VERIFICATION_LOG.md` quotes the commands a pass found broken, under a dated
    heading; judging those as live instructions reports the log for doing its job. Headings are
    taken from prose only, so a `#` inside a fence cannot forge one.
    """
    stack = {n: heads for n, _line, heads in iter_prose_lines_with_headings(text)}
    current: tuple[str, ...] = ()
    for n, line in enumerate(text.splitlines(), 1):
        if n in stack:
            current = stack[n]
        yield n, line, current


# A document's own declaration that it is an APPEND-ONLY RECORD. An HTML comment, so it is
# invisible in rendered output, greppable, and reviewable in a diff.
#
# ⚠ **RECORD-NESS IS DECLARED, NEVER INFERRED FROM A DATE** (`OG-140`).
#
# `under_dated_heading` alone was the test, and it is a whole-SUBTREE switch keyed on a date
# appearing in ANY enclosing heading. Measured on the live corpus: it exempted **2458 of 8307
# prose lines — 29.6%** — from five corpus guards AND from health's `CONS-06`, which
# `tools/hooks/pre-push` runs. `CHANGELOG.md` (96.9%) and `VERIFICATION_LOG.md` (97.2%) are
# genuine append-only records and SHOULD be exempt. But three **live normative policies** were
# 78–88% exempt for one reason: each carries a strapline as an `###` heading —
# `### question first, engine last · 2026-08-08 · v1.0.0` — and every line beneath a document's
# subtitle is, structurally, beneath a dated heading.
#
# A subtitle is not a record. A version strapline is not a record. Inferring "this document is
# history" from "a date appears above this line" is the same shape as every over-broad exemption
# this package has already been corrected for (`OG-97`, `OG-115`, `OG-123`) — and this one reached
# further than any of them, because it disarms whole documents rather than whole lines.
#
# So a document must SAY it is a record, the way `ABSENT_PATHS.md` makes deliberate absence
# declared and reviewable rather than guessed. `under_dated_heading` then decides WHICH PART of
# that record is exempt, so a record's undated preamble is still checked.
_RECORD_DECLARATION_RE = re.compile(r"<!--\s*record:\s*append-only\s*-->", re.IGNORECASE)


def is_append_only_record(text: str) -> bool:
    """True when a document DECLARES itself an append-only record.

    Both halves are required before content is exempt: the document declares itself a record, and
    the specific line sits under a dated heading within it. Either alone is too wide — the first
    would exempt a record's live preamble, the second exempts any document with a dated subtitle.
    """
    return bool(_RECORD_DECLARATION_RE.search(text))


def under_dated_heading(headings: tuple[str, ...]) -> bool:
    """True when any enclosing heading carries a date — the narrowest record test there is.

    **Narrower than `is_dated_record`, and the difference was a 34% coverage loss.**
    `is_dated_record` also exempts a line carrying a date or a clock time *anywhere on it*, which
    for a guard reading whole command lines is a whole-line switch fired by an incidental token:
    Pass 7 measured `built-claims` checking 304 claims with the old rule and 231 with it, and
    re-exempted the 5,757-character launch line by injecting one ISO date into it (`OG-97`).

    A command is not made historical by mentioning a date. Only living under a dated record heading
    does that — which is what `CHANGELOG.md` and `VERIFICATION_LOG.md` actually are.
    """
    return any(DATE_RE.search(h) for h in headings)


def is_dated_record(line: str, headings: tuple[str, ...]) -> bool:
    """True when a line is part of a DATED RECORD — and nothing weaker.

    The narrow half of `is_historical`: a dated heading above the line, or a date/clock time on the
    line itself. **Deliberately excludes the past-tense marker list**, and that exclusion is the
    whole point of this function existing separately.

    `built-claims` reads whole lines including fenced ones, and the launch command in
    `docs/plan/START_NEXT_SESSION.md` is a single **5,600-character** line whose prompt narrates
    project history — *"Phase 2 was reported complete…"*. One `" was "` in a narrative clause
    exempted the entire most-executed line in the repository from command checking. That is
    `CONS-08`'s lesson verbatim: a whole-line exemption triggered by one incidental word.

    A command either names a real module or it does not; a past-tense verb elsewhere on the line
    says nothing about that. Only living under a dated record heading does.
    """
    if any(DATE_RE.search(h) for h in headings):
        return True
    return bool(DATE_RE.search(line) or _TIME_RE.search(line))


def is_historical(line: str, headings: tuple[str, ...]) -> bool:
    """True when a line records what *was*, rather than asserting what *is*.

    Four exemptions, each narrow, each about tense, and each stated so it can be attacked:

    1. **A dated heading anywhere above it.** A release note or a verification pass is a record.
    2. **A date or a clock time on the line itself.** A dated row is a dated claim.
    3. **A numeric transition** — ``20 → 22``. Both sides must be numbers; "produces" arrows have
       a number on one side only, and that is the distinction `CONS-08` was corrected to make after
       its first draft exempted the single most important floor claim in the repository.
    4. **A past-tense marker** from a short closed list.

    A guard that flags history is a guard people switch off, and a guard that treats everything as
    history checks nothing. These four are the line between the two.
    """
    if any(DATE_RE.search(h) for h in headings):
        return True
    if DATE_RE.search(line) or _TIME_RE.search(line):
        return True
    if _TRANSITION_RE.search(line):
        return True
    padded = f" {line.lower()} "
    return any(marker in padded for marker in _PAST_MARKERS)


def prose_text(text: str) -> str:
    """``text`` with every fenced code block removed, line numbering preserved by blank lines.

    Line numbers survive because a finding that cites the wrong line is worse than one that cites
    none — the reader goes to the cited line, sees nothing wrong, and stops trusting the guard.
    """
    keep = dict(iter_prose_lines(text))
    return "\n".join(keep.get(n, "") for n in range(1, len(text.splitlines()) + 1))


def strip_inline_code(line: str) -> str:
    """Blank out inline code spans, keeping the line's length so columns still line up."""
    return _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)


def slugify(heading: str) -> str:
    """GitHub's heading-anchor slug: lower-cased, punctuation dropped, spaces to hyphens.

    Deliberately an approximation of a format GitHub has never specified. It is used only to decide
    whether an in-document ``#anchor`` resolves, and the guard treats a near-miss as unresolved —
    so the failure mode is a reader being asked to check a link that was probably fine, never a
    dead link passing silently.
    """
    text = heading.strip()
    text = re.sub(r"^#+\s*", "", text)
    # Link syntax inside a heading contributes its TEXT to the slug, not its target.
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").replace("*", "").replace("_", " ")
    text = _SLUG_STRIP_RE.sub("", text)
    return text.strip().lower().replace(" ", "-")


def heading_slugs(text: str) -> set[str]:
    """Every anchor a reader could link to in this document.

    ATX headings (``## Title``) plus explicit HTML anchors (``<a id="x">`` / ``name="x"``), because
    both are live in this corpus and a guard that knows only one reports the other as dead.
    """
    slugs: set[str] = set()
    for _n, line in iter_prose_lines(text):
        stripped = line.strip()
        if stripped.startswith("#"):
            slug = slugify(stripped)
            if slug:
                slugs.add(slug)
        for match in re.finditer(r"<a\s[^>]*\b(?:id|name)=[\"']([^\"']+)[\"']", stripped):
            slugs.add(match.group(1).strip().lower())
    return slugs
