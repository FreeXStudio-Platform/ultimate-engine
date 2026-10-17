"""The ONE definition of "a leading HTML comment" every front-matter regex shares.

Four modules independently decide whether a markdown file is *governed* by looking for
front matter behind a run of leading HTML comments — ``tools.docgen.classification`` (the placement
gate), ``tools.health.checks`` twice (``CONS-09``, ``BUILD-02``), ``tools.docgen.archive``
(``_FM_FENCE_RE``) and ``tools.corpus_check.corpus``. They held four *copies* of the comment
sub-pattern, under a comment in ``corpus.py`` asserting they were identical. **They were not**, and
the divergence was invisible because nothing compared them:

* base ``1.0.12`` used ``<!--.*?-->`` (lazy, and in ``corpus.py`` catastrophically backtracking:
  8.3 s on 26 leading comments);
* round 1 of the CodeQL pass (``66e71ff0``) replaced it with the tempered dot
  ``<!--(?:(?!-->).)*-->`` in **all four**;
* round 2 (``93ca4096``) discovered that the tempered dot is NOT equivalent
  — it commits to the FIRST ``-->`` with no backtracking, so HTML's degenerate "abrupt-closing"
  forms ``<!-->`` and ``<!--->``, which share dashes between their own open and close, stop parsing
  as separate comments — and fixed **only** ``classification.py``.

The measured consequence of that asymmetry, at ``07a287b2``: a run of ``<!--->`` before a real
``---`` fence made ``CONS-09`` miscount ``governed`` (fails loudly — safe), ``BUILD-02`` silently
build fewer documents, and ``archive.py._write_header_version`` silently return ``False``, skipping
the ``version:`` stamp because it read a governed document as ungoverned.

**So the copies are gone.** One constant, four importers: a future rewrite cannot reach three of
four sites again, and the ``corpus.py`` comment is now true by construction rather than by
assertion. This module is deliberately dependency-free (stdlib only, no ``tools`` imports) so every
layer above can import it without importing downward — the reason ``tools.lib`` exists at all; see
this package's ``__init__``.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Callable

#: One leading HTML comment.
#:
#: The two alternatives are NOT interchangeable and the order matters. ``-?>`` matches the
#: abrupt-closing forms ``<!-->`` and ``<!--->`` in one deterministic step; the ``(?!-?>)`` guard on
#: the general branch makes the two mutually exclusive, and that exclusion is what keeps the whole
#: pattern linear. Two "simplified" variants without the guard were measured at >6 s on 200
#: repetitions — the catastrophic backtracking this token exists to avoid.
#:
#: Lazy ``.*?`` would also be correct here, and is what the base version used; it is not used
#: because it is what CodeQL flags. This token is the linear form that keeps the lazy version's
#: language.
HTML_COMMENT = r"<!--(?:-?>|(?!-?>)(?:(?!-->).)*-->)"

#: A run of leading comment LINES — each carrying **one or more** comments, with blank or
#: whitespace-only lines allowed before, between and after them.
#:
#: The `+` is load-bearing. Every version of this run from base ``1.0.12`` through
#: ``07a287b2`` allowed exactly ONE comment per line, which was harmless while the comment token
#: backtracked (base's lazy ``<!--.*?-->`` simply expanded to the LAST ``-->`` on the line) and
#: became a **placement-gate bypass** the moment round 1 replaced it with a tempered dot that
#: commits to the FIRST ``-->``.
#:
#: The blank-line tolerance used to live only in ``classification.py``'s private
#: variant, so ``corpus.governed``, ``archive._write_header_version`` and ``CONS-09``/``BUILD-02``
#: all stopped seeing a document whose leading comments were separated by a blank line — base's
#: ``DOTALL`` lazy token spanned those blanks and matched. One grammar now, four readers.
#:
#: It stays linear because the quantified pieces cannot match the same character: ``[ \t]*``
#: matches only space/tab and ``HTML_COMMENT`` only text starting with ``<``. Asserted by a timing
#: test at the caller's own 4,000-character cap, not by this paragraph.
_BLANK_LINES = r"(?:[ \t]*\r?\n)*"
LEADING_COMMENT_LINES = rf"{_BLANK_LINES}(?:(?:[ \t]*{HTML_COMMENT})+[ \t]*\r?\n{_BLANK_LINES})*"


def leading_comment_lines() -> str:
    """The comment-run fragment every front-matter reader composes.

    Returns a FRAGMENT for f-string composition, not a compiled pattern: each reader wraps it in its
    own anchors and capture groups, and handing back a compiled object would force them all into one
    shape they do not share.

    It takes no arguments any more. It used to take ``allow_blank_lines``, with
    ``classification.py`` the only caller passing ``True`` — which is precisely how the other four
    readers ended up with a different language from the gate. A parameter whose non-default value
    is the correct one for everybody is a divergence waiting to be re-introduced.
    """
    return LEADING_COMMENT_LINES


#: The readers' own run, anchored and BOM-tolerant, compiled exactly as they compile it — with
#: ``DOTALL``, so a comment that spans lines is consumed here too. Defined once, next to the
#: fragment, so ``unparseable_leading_block`` cannot drift from what the readers actually accept.
_LEADING_RUN_RE = re.compile(rf"\A\ufeff?{LEADING_COMMENT_LINES}", re.DOTALL)

#: A front-matter fence sitting where base ``1.0.12``'s leading token could have reached it: right
#: behind some ``-->``, separated by nothing but horizontal whitespace and blank lines.
#:
#: This is the REACHABILITY test, and it is the whole of the amended fail-closed invariant (a
#: reader may lose an input only where base ``1.0.12`` would have refused it). Base's token was
#: ``<!--.*?-->`` under ``DOTALL``: lazy, so from the document's first ``<!--`` it could
#: expand across *any* intervening junk to a later ``-->`` and then take the fence. That — and only
#: that — is what base could see and the strict grammar cannot. So the question "would base have
#: found a classification here?" is answered by asking whether a fence sits behind ANY ``-->``,
#: not by guessing at the shape of the junk in between.
#:
#: Deliberately NOT implemented by running base's own pattern as an oracle. That pattern is the
#: catastrophic backtracker this module exists to remove; importing the defect to decide
#: whether the fix applies would put a >6 s worst case on the commit path. This is a literal
#: ``-->`` followed by bounded whitespace — one forward scan, no nesting, nothing to backtrack.
#:
#: The same-line alternative ``-->[ \t]*---`` is STRICTLY MORE PERMISSIVE than base, which requires
#: a ``\r?\n`` after every comment before its fence. It is included on an explicit instruction and
#: it can only ever add refusals, never remove one, so the theorem is unaffected; the availability
#: cost it carries is measured on both corpora rather than argued (0 tracked, 0 on disk).
_REACHABLE_FENCE_RE = re.compile(r"-->[ \t]*(?:\r?\n(?:[ \t]*\r?\n)*[ \t]*)?---")

#: A fence that OPENS front matter: ``---`` and then nothing but horizontal whitespace to the end
#: of its line. Matched with ``.match(text, pos)`` — no slice, no anchor, O(1) per candidate.
#:
#: This is the cheap test that keeps the expensive one rare. Every reader spells the
#: opener ``---[ \t]*\r?\n``, so a candidate whose ``---`` is followed by anything else can never
#: declare front matter and must not cost a search. In the adversarial shape ``-->---`` repeated,
#: EVERY candidate fails here, in constant time, before any lookup happens.
_FENCE_OPENS_FRONT_MATTER_RE = re.compile(r"---[ \t]*\r?\n")

#: The start of every line in the document that begins ``---``. Built ONCE, lazily, in one linear
#: pass; the closing fence for any candidate is then a ``bisect`` away.
_FENCE_LINE_START_RE = re.compile(r"\n(?=---)")

#: The message the placement gate uses when it refuses an unparseable leading block.
UNPARSEABLE_LEADING_BLOCK = (
    "leading HTML-comment block cannot be parsed — reformat it, one or more well-formed "
    "comments per line, before the classification header"
)


def unparseable_leading_block(
    text: str, *, declares_classification: Callable[[str], bool]
) -> str | None:
    """The first line of a leading block that hides a classification header, or ``None``.

    Four rounds of widening the comment grammar each certified a language the next round found
    too small, and at ``classify_file`` a language that is too small is **fail-open**: ``if not _has_doc_header(text): return None`` reads
    "I cannot parse this" and "there is nothing here to protect" as the same answer.

    Round 5 replaced the enumeration with a verdict — and then guessed once more, on the residue:
    ``if "<!--" in first_line``. That third assumption re-opened the class. ``<!-- a -->`` / ``z`` /
    ``<!-- b -->`` / fence leaves a residue whose first line is ``z``, which contains no ``<!--``,
    so the verdict returned ``None`` and a ``classification: secret`` document committed clean
    outside the vault — while base ``1.0.12`` REFUSED it, because its lazy ``DOTALL`` token spanned
    the junk line to the last ``-->``. One byte of junk was the whole exploit.

    **So the residue is not inspected at all.** The verdict now fires iff all three hold:

    (i)   the first non-blank line, BOM- and indentation-stripped, begins with ``<!--`` — this only
          speaks about blocks that are *trying* to be a comment run, so ordinary prose that merely
          contains ``<!--`` is never this gate's business;
    (ii)  the strict run does not itself land on a fence — if it does, the readers parse the
          document and nothing is lost, whether or not that fence declares a classification (base
          lands on the same first fence, so the two agree either way);
    (iii) a classification header exists behind some ``-->``, at a position base's leading token
          could have reached (``_REACHABLE_FENCE_RE``), confirmed by the CALLER's own header parser.

    Condition (iii) is what makes ``base REFUSED ⇒ HEAD REFUSED`` true *by construction* rather than
    by shape enumeration: base can only have refused a document whose classification header its
    token reached, and every such document satisfies (iii). It is also what returns the availability
    cost to zero — OpenZeppelin's ``Fixes #???? <!-- Fill in with issue number -->`` template, which
    round 5 refused ten times on this disk, carries no header anywhere and so is accepted again.

    ``declares_classification`` is INJECTED, not imported. This module is deliberately
    dependency-free so every layer above can import it without importing downward, and the caller
    already owns the one authoritative answer to "does this text declare a classification?"
    (``staged_content_scanner._has_doc_header``). Writing a second one here would be the
    four-copies defect — two implementations of one question — in the module that exists to close it.
    It is keyword-only and has no default: a default would be a second behaviour to drift.
    """
    stripped = text.lstrip("\ufeff")
    first_non_blank = next((ln for ln in stripped.split("\n") if ln.strip()), "")
    if not first_non_blank.lstrip(" \t").startswith("<!--"):
        return None
    match = _LEADING_RUN_RE.match(text)
    rest = text[match.end() :] if match else stripped
    # ``[ \t]*---`` is how every reader spells the fence, so an INDENTED fence the run landed on is
    # still a fence. Testing ``rest.startswith("---")`` instead would send a document the readers
    # parse perfectly into (iii), which would then refuse it with a message about a block that is
    # not in fact unparseable.
    if rest.lstrip(" \t").startswith("---"):
        return None
    # Round 6 removed a per-candidate O(n) SLICE and left a per-candidate O(n) lookup,
    # `text.find("\n---", fence + 3)`, in the same statement — O(1) when it hits and O(remaining)
    # when it MISSES, which it does for every candidate in a document that has no `\n---` after
    # them. Measured end-to-end at `classify_file`: 1.05 ms at 4 KB, 424 ms at 64 KB, 128.8 s at
    # 1 MB, against base 1.0.12's 39 ms — and the gate passes the whole blob, because the
    # 4,000-character cap belongs to `corpus.front_matter` and `checks.py`, never to this path.
    # Third quadratic in this sequence, after ``corpus.py``'s catastrophic backtracker and the
    # quadratic fifth comment regex in ``rendered_output.py``; the shape of the mistake
    # each time is a per-item scan that looks constant because the test's input makes it hit.
    #
    # So nothing is searched per candidate. The fence lines are found ONCE in a linear pass and
    # located by `bisect`; the O(1) opener test above rejects the dense adversarial shapes before
    # even that; and `seen_close` collapses candidates that share one closing fence, which is what
    # keeps the surviving slices disjoint and their total O(n).
    fence_line_starts: list[int] | None = None
    seen_close: set[int] = set()
    for hit in _REACHABLE_FENCE_RE.finditer(text):
        fence = hit.end() - 3
        if _FENCE_OPENS_FRONT_MATTER_RE.match(text, fence) is None:
            continue
        if fence_line_starts is None:
            fence_line_starts = [m.start() for m in _FENCE_LINE_START_RE.finditer(text)]
        index = bisect.bisect_left(fence_line_starts, fence + 3)
        if index == len(fence_line_starts):
            continue
        close = fence_line_starts[index]
        # Candidates are walked left to right, so the FIRST one to reach a given closing fence has
        # the earliest opener and therefore the largest body. `"classification" in body` is
        # monotone in the body, and the line this function returns does not depend on which
        # candidate matched, so a later candidate sharing that fence can add nothing. Asserted by
        # a differential over the whole generated grammar and all three corpora, not by this note.
        if close in seen_close:
            continue
        seen_close.add(close)
        eol = text.find("\n", close + 1)
        block = text[fence : eol + 1] if eol != -1 else text[fence:]
        if declares_classification(block):
            return rest.split("\n", 1)[0].rstrip("\r")
    return None
