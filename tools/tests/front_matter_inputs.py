"""The input grammar every front-matter reader is tested against — ONE generator, importable.

Three separate differentials were run over this code in one week and each missed a defect the
next one found, for the same reason every time: **the generated inputs did not contain the shape
that broke.** Round 1's differential had no abrupt-closing comments, so it certified a tempered dot
that could not parse them. Round 2's had them, and no multi-comment LINES, so it certified a run
pattern that let a `classification: secret` document commit clean outside the vault (the
placement-gate bypass).

A differential is only as strong as its input grammar, so the grammar lives here, in one place a
verifier can import and EXTEND, rather than as literals inside whichever test happened to be
written first. **Adding a shape here strengthens every reader's tests at once** — which is the
same argument as `tools.lib.front_matter` itself, applied to the inputs instead of the pattern.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

#: One comment, in every spelling that has ever mattered here.
COMMENT_FORMS: tuple[tuple[str, str], ...] = (
    ("well-formed", "<!-- c -->"),
    ("no spaces", "<!--c-->"),
    ("empty", "<!---->"),
    ("whitespace only", "<!-- -->"),
    # HTML's "abrupt-closing" forms: they share dashes between their own open and close, which is
    # why a pattern that commits to the first `-->` cannot see them.
    ("abrupt 5-char", "<!--->"),
    ("abrupt 4-char", "<!-->"),
    # Multiple comments on ONE line — the shape that was missing when the run pattern was certified
    # (the placement-gate bypass). Base 1.0.12 accepted these because its lazy token backtracked to
    # the last `-->`.
    ("two adjacent", "<!-- a --><!-- b -->"),
    ("two spaced", "<!-- a --> <!-- b -->"),
    ("two tab-separated", "<!-- a -->\t<!-- b -->"),
    ("three adjacent", "<!-- a --><!-- b --><!-- c -->"),
    # The residual round 4 left — a separator outside space/tab between two comments.
    # `X` is any single character the strict grammar cannot consume; these are `x` and a form feed.
    # Base accepted both (its lazy token spanned them); HEAD REFUSES them at the gate rather than
    # reading them as "no front matter", which is what made them fail-open for four rounds.
    ("V07 arrow-ish inside", "<!-- a --> b -->"),
    ("V26 form feed separator", "<!-- a -->\x0c<!-- b -->"),
)

#: Runs whose comment LINES are separated by a blank or whitespace-only line. Base's
#: DOTALL token spanned these; every reader but `classification` stopped seeing them at round 4.
#:
#: These were DEFINED in round 5 and consumed by nothing — `generate()` never read the
#: tuple, so not one generated input carried a blank-line-separated run and the differential still
#: could not see the shape these entries exist for. A grammar entry that no generator reads is
#: indistinguishable from an absent one, which is why `TheGeneratorConsumesEveryDeclaredShape`
#: below now asserts consumption rather than leaving it to review.
MULTILINE_RUNS: tuple[tuple[str, str], ...] = (
    ("V11 blank line between", "<!-- a -->\n\n<!-- b -->\n"),
    ("V12 ws-only line between", "<!-- a -->\n   \n<!-- b -->\n"),
    ("V13 comment spanning lines", "<!-- a\nb -->\n"),
)

#: The class that survived round 5: a run INTERRUPTED by a line the strict grammar
#: cannot consume, with more comments after it. Base's lazy `DOTALL` token spanned the interruption
#: from the first `<!--` to the last `-->` and took the fence behind it, so base saw a governed
#: document; the strict run stops at the interruption, and round 5's verdict then asked whether the
#: residue's first line re-contained `<!--` — which for a junk line it does not. One byte of junk
#: was a placement-gate bypass for a `classification: secret` document.
#:
#: The interruption is varied deliberately: prose, a heading (Markdown's own syntax), two lines,
#: and blank lines on either side. Round 5's residual was described as "any single character
#: outside space/tab"; it is really "any LINE the run cannot consume", and these shapes say so.
INTERRUPTED_RUNS: tuple[tuple[str, str], ...] = (
    ("W01 junk line between comments", "<!-- a -->\nz\n<!-- b -->\n"),
    ("W02 junk line, CRLF", "<!-- a -->\r\nz\r\n<!-- b -->\r\n"),
    ("W16 junk then two comment lines", "<!-- a -->\nz\n<!-- b -->\n<!-- c -->\n"),
    ("W17 blank, junk, comment", "<!-- a -->\n\nz\n<!-- b -->\n"),
    ("N01 heading between comments", "<!-- a -->\n# Heading\n<!-- b -->\n"),
    ("N02 two junk lines", "<!-- a -->\nz\ny\n<!-- b -->\n"),
    ("N03 junk, blank, comment", "<!-- a -->\nz\n\n<!-- b -->\n"),
)

#: Shapes that fuse the run and the fence, so they cannot be expressed as (prefix, tail). One `%s`
#: takes the front-matter body.
#:
#: The same-line fence `-->---` is the one place round 6 is deliberately STRICTER than base: base
#: requires a `\r?\n` after every comment before its fence, so it never reached this fence and
#: failed open on it. The reachability test accepts `-->[ \t]*---` on an explicit instruction,
#: which can only add refusals — measured at 0 newly-refused files across 80 engine tracked files
#: and, in a large host project, 1,384 tracked and 27,171 on-disk `.md` files.
FUSED_SHAPES: tuple[tuple[str, str], ...] = (
    ("V30 same-line fence after -->", "<!-- a -->---\n%s---\nbody\n"),
    ("N04 junk then same-line fence", "<!-- a -->\nz\n<!-- b -->---\n%s---\nbody\n"),
    (
        "N06 fence carrying no classification",
        "<!-- a -->\n---\nfoo: bar\n---\n%sbody\n",
    ),
)

#: Leading indentation the readers tolerate.
INDENTS: tuple[str, ...] = ("", "  ", "\t")

#: Front-matter bodies. The `classification` one is what makes a document *governed*.
BODIES: tuple[tuple[str, str], ...] = (
    ("governed", "classification: secret\nid: GEN-001\n"),
    ("ungoverned", "title: t\n"),
    ("empty", ""),
)

#: What follows the comment run. The empty tail is the adversarial one: comments and NO fence at
#: all, which is the shape the catastrophic backtracking in ``corpus.py`` needed.
TAILS: tuple[tuple[str, str], ...] = (
    ("fence + body", "---\n%s---\nbody\n"),
    ("fence only", "---\n%s---\n"),
    ("blank line then fence", "\n---\n%s---\n"),
    ("no fence at all", ""),
)


def generate(max_reps: int = 4) -> Iterator[tuple[str, str]]:
    """Yield ``(label, text)`` over the full product of every declared shape.

    THREE families, because they have three different shapes and flattening them would lose one:
    single comments repeated per line (``COMMENT_FORMS``), whole multi-line runs that carry their
    own newlines (``MULTILINE_RUNS`` + ``INTERRUPTED_RUNS``), and documents whose run and fence are
    fused on one line (``FUSED_SHAPES``). Every tuple this module declares is consumed
    here, and ``TheGeneratorConsumesEveryDeclaredShape`` fails if a new one is not.
    """
    for (cn, comment), indent, (bn, body), (tn, tail), reps in itertools.product(
        COMMENT_FORMS, INDENTS, BODIES, TAILS, range(max_reps)
    ):
        text = (indent + comment + "\n") * reps + (tail % body if tail else "")
        yield f"{cn} x{reps} indent={indent!r} body={bn} tail={tn}", text
    for (rn, run), indent, (bn, body), (tn, tail), reps in itertools.product(
        MULTILINE_RUNS + INTERRUPTED_RUNS, INDENTS, BODIES, TAILS, range(1, max_reps)
    ):
        text = (indent + run) * reps + (tail % body if tail else "")
        yield f"{rn} x{reps} indent={indent!r} body={bn} tail={tn}", text
    for (fn_, shape), (bn, body) in itertools.product(FUSED_SHAPES, BODIES):
        yield f"{fn_} body={bn}", shape % body


def adversarial_prefixes() -> tuple[tuple[str, str], ...]:
    """Just the prefixes, each known to have broken at least one reader, for per-site gate tests."""
    out: list[tuple[str, str]] = []
    for name, comment in COMMENT_FORMS:
        for reps in (1, 3):
            out.append((f"{name} x{reps}", (comment + "\n") * reps))
    out.append(("mixed abrupt + multi-line", "<!--->\n<!-- a --><!-- b -->\n<!-->\n"))
    out.append(("indented three-per-line", "  <!-- a --> <!-- b --><!-- c -->\n"))
    return tuple(out)


#: Shapes whose COST is the question, not whose parse is. Each is grown to the caller's own
#: 4,000-character cap, which was measured not to bound a backtracking pattern.
TIMING_UNITS: tuple[tuple[str, str], ...] = (
    ("one per line", "<!-- c -->\n"),
    ("two per line", "<!-- a --><!-- b -->\n"),
    ("whitespace heavy", "  <!-- a -->  <!-- b -->  \n"),
    ("trailing unterminated", "<!-- a --><!-- b -->"),
    ("abrupt forms", "<!--->\n"),
)
