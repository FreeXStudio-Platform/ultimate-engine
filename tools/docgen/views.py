"""Audience-view GENERATOR for the views registry.

The views-registry rule (operator, 2026-09-08): one AUTHORED source per subject stays the law; audience/level
VIEWS are GENERATED sibling files produced by this module from that one source. Generated
views are BUILD OUTPUTS: never hand-edited, regenerated on every build, registered in
``tools.docgen.artifact_index`` as ``derived`` -- and leak-gate 9 (``export_sanitizer``'s variant-
overlap gate) stays STRICT and runs on every one of them. Relaxing a leak gate for
"derived" files would be a green that cannot see the failure, so this module never does
that; it arms the gate correctly instead (see "Gate-9 wiring" below).

## Marker syntax

Block-level audience gating uses paired HTML comments in the document BODY -- never the
YAML front matter, which ``classification.py`` owns and this module never touches. Parsing
starts only AFTER the front-matter fence, so a marker can never collide with the existing
``<!-- classification: ... -->`` convention:

    <!-- audience: internal -->
    ... content visible only to the `internal` tier ...
    <!-- /audience -->

**Fence-aware:** a marker comment written INSIDE a fenced code block (```` ``` ````
or ``~~~``, e.g. a document illustrating this very syntax) is TEXT, never a real marker --
``_real_marker_matches`` is the single shared primitive ``has_audience_markers`` and
``parse_body_segments`` both scan through, so the two can never disagree about whether a document
has markers. Without this, a document that documents the marker syntax gets its illustrated
example silently treated as a real block, splitting content out from under it and leaving a
mangled empty fence in every view that does not permit the (fake) audience -- fails SAFE for
leaks, but corrupts the document.

Recognized audiences, most-open to most-restricted (``AUDIENCE_LEVELS``)::

    public  <  github  <  commercial  <  internal

## Permission rule

A generated view for audience A includes every block whose marker audience level is
<= A's level in the ordering above ("the marker permits A"). Concretely: a block marked
``public`` appears in all four views; a block marked ``internal`` appears ONLY in the
``internal`` view, because ``internal`` is the single most-restricted (highest-trust)
level and nothing outranks it. The ``internal`` view is therefore always a superset of
the other three -- it excludes nothing, ever.

Body content that carries NO marker inherits the document's front-matter
``default_audience`` field (a plain string field this module reads directly out of the raw
YAML -- it is deliberately NOT added to ``DocHeader``/``classification.py``, which this
module must not touch). **Fail-closed, not "best effort":** a document with >=1 marked
block but no valid ``default_audience`` FAILS the build (``AudienceMarkerError``), as does
an unclosed marker, a stray ``<!-- /audience -->``, an unknown audience name, or nested
markers. A document with ZERO markers is completely untouched by this module --
``has_audience_markers()`` is False and ``generator.build()`` never calls anything else
here for it, which is what keeps this a purely additive path.

## Output naming, stamping and non-reprocessing

Generated views are written as ``<stem>.<audience>.md`` siblings of the source
(``generated_view_filename``). Every generated file opens with a ``docgen:generated-view``
HTML-comment stamp naming its source id and audience, so a reader (or this module itself)
can never mistake it for an authored source; ``is_generated_view_text`` lets a caller check
this, and ``build_and_gate_views`` refuses outright (raises ``AudienceMarkerError``) if
asked to treat an already-stamped text as a NEW source -- a generated view can never be
re-processed as one, so there is no chain.

Generation is a pure function of (source text, source header) with no wall-clock
timestamps or other non-determinism anywhere in the output bytes, so two builds from a
clean tree produce byte-identical files (see ``tools/tests/test_views.py``'s determinism
case).

## Gate-9 wiring -- the views-registry resolution (read this before changing anything below)

Two naive readings of "run gate 9 on a generated view" both fail:

  * Declaring the SIBLING VIEWS in ``header.variants`` and passing THOSE as ``siblings``
    blocks ALWAYS, because a more-restricted view is by construction a subset of a
    less-restricted one -- a gate that always fires gets disabled, which is worse than
    none.
  * Leaving ``header.variants`` empty makes the gate silently no-op (``export_sanitizer.
    gate_variant_overlap``/``_variant_overlap_against`` both return clean the instant
    ``not header.variants``) -- exactly the "green that cannot see the failure" this design
    forbids.

The resolution implemented here: for a generated view, gate 9's ``siblings`` are the
EXCLUDED higher-tier BLOCK TEXTS -- the content filtered OUT of that specific view, one
entry per excluded block -- never the sibling views. Overlap between a view and content
that was excluded FROM it is a genuine leak (the generator itself would have to be
broken to produce it); the expected, healthy result is ZERO overlap every time, and any
non-zero overlap means ``render_view``/``build_view_header`` let something through that
should not be there. ``build_view_header`` arms ``header.variants`` with exactly one label
per excluded block (never padded, never fewer than the excluded-block count), so the
fail-closed missing-sibling branch in ``export_sanitizer`` is satisfied honestly. The
``internal`` view excludes nothing (it is the superset), so its ``variants`` list is empty
and gate 9 correctly no-ops FOR IT SPECIFICALLY -- there is nothing that could have leaked
into a view that omits nothing, which is a sound, load-bearing edge case, not a workaround.

## Retention on a blocked rebuild

Gate 9 (and every other gate ``run_gates`` folds in) guards the WRITE path only. Without more,
a document that once published a clean view and later grows a leak would keep SERVING the old,
now-wrong view forever -- the blocked rebuild correctly refuses to overwrite it with the new
(bad) text, but nothing ever removes the stale one either. ``build_and_gate_views`` therefore
retires a stale view -- deregisters it via ``project_index.remove_artifact`` and deletes the
file -- the moment that SAME (stem, audience)'s rebuild is gate-blocked (``_retire_stale_view``).
This never happens merely because ``may_write=False`` (a dry-run/preview build must not mutate
anything, including an existing view); it triggers only on an actual blocking gate result.
Deliberately not wrapped in a blanket ``try/except``: a failed deregister or delete must be LOUD,
never silently swallowed, because a half-retired view (removed from the index but still
on disk, or the reverse) is exactly the half-done state this exists to prevent.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType

from tools.docgen import export_sanitizer
from tools.docgen.classification import _FRONT_MATTER_RE, _raw_front_matter_fields
from tools.docgen.models import DocHeader, Finding, GateResult, ManifestRow, Severity

# --------------------------------------------------------------------------------------
# Audiences
# --------------------------------------------------------------------------------------

#: Most-open to most-restricted. Index in this tuple IS the trust level used by the
#: permission rule (`audience_permits`) -- never re-derive this ordering elsewhere.
AUDIENCE_LEVELS: tuple[str, ...] = ("public", "github", "commercial", "internal")
_LEVEL_INDEX: dict[str, int] = {name: i for i, name in enumerate(AUDIENCE_LEVELS)}

#: The stamp token every generated view opens with (see module docstring). Kept as one
#: named constant so the writer and the `is_generated_view_text` reader can never drift.
_GENERATED_VIEW_TOKEN = "docgen:generated-view"
_GENERATED_VIEW_STAMP_RE = re.compile(r"\A<!--\s*" + re.escape(_GENERATED_VIEW_TOKEN) + r"\b")

# Marker tokens, matched only in the BODY (callers always strip front matter first via
# `_strip_body` below). One combined pattern so tokens are found in true document order --
# scanning open/close separately and merge-sorting the two lists is the same information at
# more risk of a subtle ordering bug.
_TOKEN_RE = re.compile(
    r"<!--\s*(?:audience:\s*(?P<name>[A-Za-z0-9_-]+)|(?P<close>/audience))\s*-->"
)

# A fence-open line: up to 3 leading spaces (CommonMark tolerance), then 3+ backticks or
# 3+ tildes, optionally followed by an info string. Matched line-by-line, never with DOTALL
# across the whole body, because a fence's extent is a LINE-ORIENTED property. The info
# string is CAPTURED, not skipped, because a backtick fence's info string may not contain
# a backtick -- see `_fenced_ranges`.
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(?P<info>[^\n]*)")


def _fenced_ranges(body_md: str) -> list[tuple[int, int]]:
    """Character-offset ``[start, end)`` ranges of ``body_md`` covered by fenced code
    blocks -- the primitive that keeps a marker comment WRITTEN INSIDE a
    fence (documenting the marker syntax) from being scanned as a real marker.

    Recognizes fences the way CommonMark does: a fence OPENS on a line that is (up to 3
    leading spaces) 3-or-more backticks or 3-or-more tildes, optionally followed by an
    info string, and CLOSES at the first following line that is (up to 3 leading spaces)
    the SAME fence character repeated AT LEAST as many times, with nothing but trailing
    whitespace after (a shorter or differently-charactered run does not close it -- e.g.
    a ``~~~`` fence is not closed by a bare ```` ``` ````, and a 3-backtick fence is not
    closed by a 2-backtick line). A BACKTICK fence-open's info string may not itself
    contain a backtick (CommonMark), so ```` ```x``` ```` is a code SPAN in a paragraph
    and opens nothing; a tilde fence has no such restriction.

    An unterminated fence (no matching close before EOF) runs to the END of the text.

    **Neither failure direction here is safe, and an earlier version of this docstring
    claimed otherwise**. Recognising too LITTLE lets a marker that is only being
    *illustrated* act as a real one: the document is mis-split and the example is
    stripped from every non-internal view (leak-safe but corrupting).
    Recognising too MUCH hides a REAL marker: its block is never separated, so internal
    content is published into open views -- and if the over-long range swallows the whole
    body, ``build_and_gate_views`` returns ``ok`` having produced no views at all, a green
    that did nothing. Both are defects; accuracy is the only safe direction.

    **Scoped out, deliberately -- three container shapes where a marker inside a code
    block IS still scanned as real** (the corrupting, not leaking, direction):
    a fence indented into a list item's content column, a 4-space-indented code block, and
    a fence inside a blockquote. Each needs CommonMark CONTAINER-block tracking, which is a
    markdown parser, not a helper. A partial implementation would be worse than none: mis-
    reading list content as an indented code block hides real markers in list items, i.e.
    it converts a corrupting bug into a LEAKING one. No document in this repository uses
    the marker syntax today, so these are unexercised; they must be closed by a real block
    parser before view publication depends on any of the three shapes.
    """
    ranges: list[tuple[int, int]] = []
    n = len(body_md)
    pos = 0
    while pos < n:
        newline = body_md.find("\n", pos)
        line_end = newline + 1 if newline != -1 else n
        # Matched against the SLICED line, never `_FENCE_OPEN_RE.match(body_md, pos,
        # line_end)`: `^` anchors only to the true start of the searched string unless
        # `re.MULTILINE` is set -- passing `pos` as a start offset does NOT make `^`
        # match there, so matching the full `body_md` with a `pos` offset would silently
        # find nothing for every line but the first.
        open_match = _FENCE_OPEN_RE.match(body_md[pos:line_end])
        if open_match is None:
            pos = line_end
            continue
        fence_char = open_match.group(1)[0]
        if fence_char == "`" and "`" in open_match.group("info"):
            # CommonMark forbids a backtick in a BACKTICK fence's info string, so a
            # line like ```` ```x``` ```` is a paragraph containing a code SPAN, not a
            # fence-open. Reading it as one opened a fence that never closed, swallowing
            # the rest of the document -- every real marker after it went unseen and the
            # build returned ok with zero views. (A TILDE fence's info string MAY contain
            # backticks, so this test is deliberately backtick-only.)
            pos = line_end
            continue
        fence_len = len(open_match.group(1))
        close_re = re.compile(rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$")
        fence_start = pos
        scan_pos = line_end
        while True:
            if scan_pos >= n:
                ranges.append((fence_start, n))
                pos = n
                break
            next_newline = body_md.find("\n", scan_pos)
            next_line_end = next_newline + 1 if next_newline != -1 else n
            candidate = body_md[scan_pos:next_line_end].rstrip("\n")
            if close_re.match(candidate):
                ranges.append((fence_start, next_line_end))
                pos = next_line_end
                break
            scan_pos = next_line_end
    return ranges


def _offset_is_fenced(offset: int, fenced_ranges: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in fenced_ranges)


# A GFM table's delimiter row: optional leading pipe, cells of `-` with optional `:` alignment
# marks, separated by pipes, at least one pipe or a leading/trailing one (`|---|`, `:--|--:`).
_TABLE_DELIMITER_RE = re.compile(r"^ {0,3}\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$|^ {0,3}\|\s*:?-+:?\s*\|\s*$")


def _code_span_ranges(body_md: str, fenced_ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Character-offset ``[start, end)`` ranges covered by inline CODE SPANS.

    The fence handling taught the marker scanner about fenced BLOCKS; a marker written
    in backticks on a prose line — ``` `<!-- audience: internal -->` ``` — is the same thing one
    construct further down and was still read as a real directive. Measured on the copy's
    build 1.0.13: four tracked host documents register as marker-using purely
    through backticked mentions in register rows and reports.

    This states the trade rather than assuming it: a marker inside a code span is DOCUMENTATION
    of the syntax, not a directive — an author who wants a real marker writes it outside backticks.
    That is the fence trade extended one construct, and ``parse_body_segments`` stays fail-closed
    on an unbalanced pair, so a backticked open with a real close REFUSES rather than mis-parses.

    CommonMark, not a backtick count (the naive "does this line have two backticks" test is the
    same input-grammar mistake that cost four earlier host findings a round each):

    * a backtick STRING is a run of one or more backticks, and a span is opened by one run and
      closed by a run of EXACTLY equal length — so ``` `` a ` b `` ``` is one span containing a
      shorter run, not two spans;
    * an opening run with no equal-length closer is LITERAL text and opens nothing;
    * a span may cross a line break, but NOT a blank line. That bound is load-bearing rather than
      pedantic: without it a single stray backtick could swallow the rest of the document and hide
      every real marker after it, which would turn a typo into a silent leak.

    Backticks inside a fenced block are skipped — fences are block-level and already resolved.
    """
    def _run_is_alone_on_its_line(start: int, end: int) -> bool:
        """True iff nothing but whitespace (or a list/blockquote prefix) surrounds the run.

        Such a run is a FENCE-OPEN shape, not an inline span, and it must not be paired here.
        Without this the scanner closes two gaps that `_fenced_ranges` deliberately leaves open
        and pins (`test_known_gap_container_shapes_are_still_fence_blind`) — a fence indented into
        a list item, and a blockquoted fence — by accidentally pairing their two fence lines as one
        enormous "code span". It would close them INCONSISTENTLY, too: a blank line anywhere inside
        the block re-opens the gap, because a code span cannot cross a paragraph boundary. A gap
        that closes only when the block happens to contain no blank line is worse than one that is
        honestly pinned, so this fix stays inside its own construct and those gaps stay pinned.
        """
        line_start = body_md.rfind("\n", 0, start) + 1
        line_end = body_md.find("\n", end)
        line_end = len(body_md) if line_end == -1 else line_end
        before = body_md[line_start:start].strip(" \t>-*+0123456789.")
        return not before and not body_md[end:line_end].strip()

    # Line-start offsets of every row of a real GFM table: a line holding a pipe, followed by a
    # delimiter row (`|---|:--:|`), and every line after it up to the next blank line. A pipe at
    # the start of a line is NOT enough — pipe-prefixed prose is an ordinary paragraph, where a
    # span may cross a soft break (found in a code review of the copy).
    table_row_starts: set[int] = set()
    line_starts = [0] + [i + 1 for i, ch in enumerate(body_md) if ch == "\n"]
    lines = body_md.split("\n")
    row = 0
    while row < len(lines) - 1:
        if (
            "|" in lines[row]
            and _TABLE_DELIMITER_RE.match(lines[row + 1])
            and not _offset_is_fenced(line_starts[row], fenced_ranges)
        ):
            end = row
            while end < len(lines) and lines[end].strip():
                table_row_starts.add(line_starts[end])
                end += 1
            row = end
            continue
        row += 1

    def _line_is_table_row(offset: int) -> bool:
        """True iff the line holding ``offset`` belongs to a real GFM table."""
        return body_md.rfind("\n", 0, offset) + 1 in table_row_starts

    ranges: list[tuple[int, int]] = []
    text_len = len(body_md)
    cursor = 0
    while cursor < text_len:
        if body_md[cursor] != "`" or _offset_is_fenced(cursor, fenced_ranges):
            cursor += 1
            continue
        open_end = cursor
        while open_end < text_len and body_md[open_end] == "`":
            open_end += 1
        run = open_end - cursor
        if _run_is_alone_on_its_line(cursor, open_end):
            cursor = open_end
            continue
        # A code span is inline content, so it cannot cross a paragraph boundary.
        limit = body_md.find("\n\n", open_end)
        limit = text_len if limit == -1 else limit
        # A GFM table is one paragraph, but each row's cells are parsed as inline content on
        # their own, so a span in a table row cannot reach past that row. Without this bound, one
        # stray backtick anywhere in a long table (a row truncated mid-span, measured on 28 rows
        # of a host's findings register) flips the pairing of every row after it, and a
        # backticked `<!-- audience: … -->` mention further down reads as a real directive.
        if _line_is_table_row(cursor):
            row_end = body_md.find("\n", open_end)
            limit = min(limit, text_len if row_end == -1 else row_end)
        probe = open_end
        closed = False
        while probe < limit:
            if body_md[probe] != "`":
                probe += 1
                continue
            close_end = probe
            while close_end < limit and body_md[close_end] == "`":
                close_end += 1
            if close_end - probe == run and not _offset_is_fenced(probe, fenced_ranges):
                ranges.append((cursor, close_end))
                cursor = close_end
                closed = True
                break
            probe = close_end
        if not closed:
            # Unterminated: the run is literal text and opens nothing (CommonMark).
            cursor = open_end
    return ranges


def _real_marker_matches(body_md: str) -> list[re.Match[str]]:
    """Every ``_TOKEN_RE`` match in ``body_md`` that is not inside a fenced block OR a code span.

    The single shared primitive: ``has_audience_markers`` and ``parse_body_segments``
    both scan through this (never ``_TOKEN_RE`` directly), so the two can never
    disagree about whether a document carries a real marker.

    That "can never disagree" property is exactly why the code-span fix belongs HERE
    and not in the detector. The two callers already agreed — they were agreeing on the wrong
    answer. Teaching only ``has_audience_markers`` about code spans would have bought a correct
    detector at the price of the one invariant this function exists to hold.
    """
    fenced_ranges = _fenced_ranges(body_md)
    span_ranges = _code_span_ranges(body_md, fenced_ranges)
    return [
        m
        for m in _TOKEN_RE.finditer(body_md)
        if not _offset_is_fenced(m.start(), fenced_ranges)
        and not _offset_is_fenced(m.start(), span_ranges)
    ]


class AudienceMarkerError(ValueError):
    """Raised -- never swallowed -- when a document's audience markers, or its
    ``default_audience`` front-matter field, cannot be resolved unambiguously.

    Every raise site names the document id and the exact problem (unknown audience,
    unclosed/stray marker, nesting, missing default). Callers (``generator.build()``)
    must let this propagate as a hard build failure; there is no valid fallback here
    (silent success is a defect class, and picking a default audience for
    content nobody tagged is exactly the silent-success shape this module exists to
    refuse)."""


@dataclass(frozen=True)
class AudienceBlock:
    """One ordered segment of a document body: either an explicitly marked block, or a
    run of unmarked content that inherited the document's ``default_audience``."""

    audience: str
    text: str
    index: int
    marked: bool


@dataclass(frozen=True)
class ViewsBuildResult:
    """What ``build_and_gate_views`` did for one source document: the merged gate result
    across every generated view (so a caller can fold it into its own ``final_gate`` the
    same way ``generator.build()`` already folds its html/json/pdf gates), plus the paths
    actually written -- keyed ``"view:<audience>"`` -- for the ones that passed."""

    gate: GateResult
    outputs: dict[str, Path]


def audience_permits(block_audience: str, view_audience: str) -> bool:
    """True iff a block marked ``block_audience`` belongs in the ``view_audience`` view."""
    return _LEVEL_INDEX[block_audience] <= _LEVEL_INDEX[view_audience]


def _strip_body(md_text: str) -> str:
    """The document body, i.e. everything after the YAML front-matter fence.

    Deliberately re-implemented against ``classification._FRONT_MATTER_RE`` (imported,
    never copied) rather than reusing ``generator._strip_front_matter`` -- importing FROM
    ``generator.py`` here would create the exact import cycle ``generator.build()`` calling
    into this module is about to introduce in the other direction. Using the classification
    module's own front-matter authority (rather than a second, simpler regex) is also the
    more correct choice: it is BOM/leading-comment tolerant, which is the pattern that
    actually governs where a header ends in this corpus.
    """
    match = _FRONT_MATTER_RE.search(md_text)
    if match is None:
        return md_text
    return md_text[match.end() :]


def _front_matter_default_audience(md_text: str) -> str | None:
    """The raw ``default_audience:`` front-matter value, or None if absent/not a string.

    Reuses ``classification._raw_front_matter_fields`` (the same uncoerced-YAML-dict
    primitive ``validate_header`` uses for its own present-but-wrong-typed checks) rather
    than re-parsing the fence -- one parse, one home for "what does the raw header say",
    same discipline as `_strip_body` above.
    """
    raw = _raw_front_matter_fields(md_text)
    if raw is None:
        return None
    value = raw.get("default_audience")
    return value if isinstance(value, str) and value else None


def has_audience_markers(body_md: str) -> bool:
    """True iff ``body_md`` (BODY text, already stripped of front matter) contains at
    least one REAL audience-marker TOKEN -- open OR close/stray, but NOT one written
    inside a fenced code block (a marker illustrated in a ``` or ~~~ fence
    is documentation text, never a real marker -- see ``_real_marker_matches``). This is
    the switch ``generator.build()`` uses to decide whether the whole audience-view path
    engages for a document; a document with none is untouched, which is what keeps this
    additive. Returning True on a stray close (not just a valid open) is deliberate: a
    stray token is still a marker the author meant to use, and it must reach
    `parse_body_segments`'s fail-closed handling rather than being silently invisible to
    `has_audience_markers`. Uses the exact same primitive `parse_body_segments` does
    (`_real_marker_matches`), so the two can never disagree about whether a document has
    markers.
    """
    return len(_real_marker_matches(body_md)) > 0


def parse_body_segments(
    body_md: str, *, default_audience: str | None, doc_id: str
) -> tuple[AudienceBlock, ...]:
    """Decompose ``body_md`` into ordered ``AudienceBlock`` segments.

    Fail-closed on every malformed shape (never "best effort"): an unknown audience name,
    a nested marker, a stray ``<!-- /audience -->``, an unclosed marker, or (whenever any
    marker is present at all) a missing/invalid ``default_audience`` all raise
    ``AudienceMarkerError`` naming ``doc_id`` and the exact problem. Returns an empty tuple
    when ``body_md`` carries no markers at all (callers should check
    ``has_audience_markers`` first; this function still handles the empty case safely on
    its own).

    Scans only REAL markers (``_real_marker_matches``): a marker written
    inside a fenced code block is body TEXT belonging to whatever segment surrounds the
    fence, never a segment boundary of its own, so a document illustrating this very
    syntax is never corrupted by its own example.
    """
    tokens = _real_marker_matches(body_md)
    if not tokens:
        return ()

    if default_audience is not None and default_audience not in AUDIENCE_LEVELS:
        raise AudienceMarkerError(
            f"document '{doc_id}' declares default_audience='{default_audience}' in its "
            f"front matter, which is not one of {', '.join(AUDIENCE_LEVELS)}."
        )

    segments: list[AudienceBlock] = []
    # Depth is asserted <=1 below (nesting refused), so one slot is always enough --
    # kept as a list (not a bare tuple) only so "is something open" reads as `if stack`.
    stack: list[tuple[str, int, int]] = []  # (audience, content_start_offset, open_marker_offset)
    cursor = 0
    counter = 0

    def emit_unmarked(raw_text: str) -> None:
        nonlocal counter
        # Whitespace-only spans (almost always the blank line authors leave between two
        # adjacent markers) carry no content to assign an audience to -- `.strip() == ""`,
        # not `== ""`, so these are skipped without becoming their own segment. This does
        # NOT "silently drop unmarked content" (the fail-closed rule this module must
        # honor): there is no content in a blank span to drop, only formatting whitespace,
        # and every segment that carries actual text is still required to resolve an
        # audience (marked, or via a declared default) below.
        if raw_text.strip() == "":
            return
        if default_audience is None:
            raise AudienceMarkerError(
                f"document '{doc_id}' has audience-marked blocks but declares no "
                "'default_audience' in its front matter, so unmarked body content cannot "
                "be assigned an audience. Add 'default_audience: <one of "
                f"{', '.join(AUDIENCE_LEVELS)}>' to the header, or mark every block "
                "explicitly -- unmarked content is never silently dropped or defaulted."
            )
        segments.append(AudienceBlock(default_audience, raw_text, counter, marked=False))
        counter += 1

    for m in tokens:
        name = m.group("name")
        if name is not None:
            if name not in AUDIENCE_LEVELS:
                raise AudienceMarkerError(
                    f"document '{doc_id}' has an unknown audience marker '{name}' at body "
                    f"offset {m.start()} -- expected one of {', '.join(AUDIENCE_LEVELS)}."
                )
            if stack:
                open_name, _content_start, open_at = stack[-1]
                raise AudienceMarkerError(
                    f"document '{doc_id}' opens <!-- audience: {name} --> at body offset "
                    f"{m.start()} while <!-- audience: {open_name} --> (opened at offset "
                    f"{open_at}) is still open -- nested audience markers are not "
                    "supported; close the outer block first."
                )
            emit_unmarked(body_md[cursor : m.start()])
            stack.append((name, m.end(), m.start()))
            cursor = m.end()
        else:
            if not stack:
                raise AudienceMarkerError(
                    f"document '{doc_id}' has a <!-- /audience --> at body offset "
                    f"{m.start()} with no matching open <!-- audience: ... --> marker."
                )
            open_name, content_start, _open_at = stack.pop()
            segments.append(
                AudienceBlock(open_name, body_md[content_start : m.start()], counter, marked=True)
            )
            counter += 1
            cursor = m.end()

    if stack:
        open_name, _content_start, open_at = stack[-1]
        raise AudienceMarkerError(
            f"document '{doc_id}' has an unclosed <!-- audience: {open_name} --> opened "
            f"at body offset {open_at} -- every audience marker must be closed with "
            "<!-- /audience -->."
        )

    emit_unmarked(body_md[cursor:])
    return tuple(segments)


def render_view(
    segments: tuple[AudienceBlock, ...], audience: str
) -> tuple[str, list[str]]:
    """The (view_text, excluded_block_texts) pair for one audience (the views registry's required
    generator signature, plus the segment-carrying step ahead of it).

    ``view_text`` is every segment whose marker permits ``audience``, concatenated in
    original document order. ``excluded_block_texts`` is every OTHER segment's text, one
    entry per excluded block -- this list is what gate 9 gets as ``siblings`` (see the
    module docstring's "Gate-9 wiring" section); it is never merged into one string,
    because per-block granularity is what lets the gate name which block leaked.
    """
    if audience not in AUDIENCE_LEVELS:
        raise AudienceMarkerError(
            f"cannot render a view for unknown audience '{audience}' -- expected one of "
            f"{', '.join(AUDIENCE_LEVELS)}."
        )
    included: list[str] = []
    excluded: list[str] = []
    for block in segments:
        (included if audience_permits(block.audience, audience) else excluded).append(block.text)
    return "".join(included), excluded


def build_view_header(source_header: DocHeader, excluded_block_texts: list[str]) -> DocHeader:
    """The ``DocHeader`` used to gate ONE generated view.

    Deliberately identical to the source header -- same ``id``, same ``classification``,
    same ``export_allowed``/``surface`` -- except ``variants``, which carries exactly one
    label per excluded block (never fewer, never padded) so gate 9 is armed and the
    fail-closed missing-sibling branch in ``export_sanitizer`` is satisfied honestly.

    The ``id`` is UNCHANGED on purpose: it is what lets gate 5 (manifest drift) resolve
    the view against the SAME ``DOC_MANIFEST.md`` row the source document already
    satisfies, rather than requiring a synthetic per-view manifest entry that does not
    exist. Reusing one header across several ``run_gates`` calls for the same source is
    not a new pattern -- ``generator.build()`` already does exactly this across its own
    html/json/pdf format loop.
    """
    labels = [f"{source_header.id}#excluded-block-{i}" for i in range(len(excluded_block_texts))]
    return replace(source_header, variants=labels)


def generated_view_filename(stem: str, audience: str, suffix: str = ".md") -> str:
    """``<stem>.<audience><suffix>`` -- e.g. ``("FOO-002", "public")`` -> ``"FOO-002.public.md"``."""
    if audience not in AUDIENCE_LEVELS:
        raise AudienceMarkerError(f"cannot name a view file for unknown audience '{audience}'.")
    return f"{stem}.{audience}{suffix}"


def _stamp(source_id: str, audience: str) -> str:
    return (
        f'<!-- {_GENERATED_VIEW_TOKEN} source="{source_id}" audience="{audience}" '
        "DO NOT EDIT -- produced by tools/docgen/views.py from the authored source; "
        "hand edits are overwritten on the next build. -->\n"
    )


def is_generated_view_text(text: str) -> bool:
    """True iff ``text`` opens with this module's generated-view stamp.

    The guard against a generated view being fed back in as if it were an authored
    source: ``build_and_gate_views`` calls this on its OWN input and refuses to run if it
    is already a generated view (see that function)."""
    return _GENERATED_VIEW_STAMP_RE.match(text) is not None


def is_generated_view_path(path: Path) -> bool:
    """Filename-only heuristic companion to ``is_generated_view_text``: True iff ``path``
    matches the ``<stem>.<audience>.md`` naming scheme this module writes. Cheap enough to
    use as a pre-filter (e.g. "don't even try to build_and_gate_views this path") before
    paying for a file read; the content stamp remains the authority."""
    if path.suffix != ".md":
        return False
    stem_parts = path.stem.rsplit(".", 1)
    return len(stem_parts) == 2 and stem_parts[1] in AUDIENCE_LEVELS


class ViewRegistrationUnavailable(RuntimeError):
    """The engine's artifact registry (``tools.docgen.artifact_index``) is not importable in this
    host.

    **History, kept because it explains why this guard exists at all (2026-09-24).**
    ``tools/project_index`` is a name a HOST PROJECT may already own — one host does: its
    ``tools/project_index`` is a docs-index/supersession gate (``docs_index.py``,
    ``banner_check.py``), a different tool from the engine's flat artifact registry, and it is
    deliberately NOT vendored (see the host's engine-profile file ▸ ``not_vendored``).
    The registry used to live at ``tools/project_index/index.py``, so in that host
    ``from tools.project_index import index`` failed unconditionally — every build in that host hit
    this guard, views were permanently inert, and no amount of the host being otherwise
    correctly set up could change that. The registry now lives at
    ``tools.docgen.artifact_index`` — inside the package every host that wants views at all
    already vendors whole (``views.py`` is itself part of it) — so a host owning an unrelated
    ``tools/project_index`` of its own no longer collides with anything. That host's own vendored
    copy proves this: see ``tools/tests/test_views.py``'s
    ``ViewsRegisterDespiteAnUnrelatedHostProjectIndexPackage``.

    This class, and the fail-closed probe below, stay: an import can still genuinely fail — a
    host that vendors ``tools/docgen`` partially and drops ``artifact_index.py``, a syntax error
    introduced by a hand edit, a broken ``tools.docgen.engine_config`` or
    ``tools.docgen.hooks.staged_content_scanner`` (the two modules ``artifact_index`` itself
    depends on) — and the views registry requires every generated view to be registered as
    derived, so a view that cannot be registered must not be written, and the reason must be
    named. This was a
    module-level ``import`` once, so any such collision raised ``ImportError`` at import time and
    took down EVERY consumer of ``tools.docgen.views``, including hosts that never generate a
    view. It is probed lazily, at the one place that needs it, and reported as a BLOCKING gate
    finding rather than a crash. Never silently skipped.
    """


def _load_project_index() -> ModuleType:
    """Import the engine's artifact registry, or raise :class:`ViewRegistrationUnavailable`."""
    try:
        from tools.docgen import artifact_index as project_index
    except ImportError as exc:  # genuinely broken/partial vendoring — see the class docstring
        raise ViewRegistrationUnavailable(
            "the engine's `tools.docgen.artifact_index` is not importable in this host "
            f"({exc}). The views registry requires every generated view to be registered as a derived "
            "artifact, so the view was NOT written."
        ) from exc
    return project_index


def _register_view(out_path: Path, source_header: DocHeader, audience: str) -> None:
    """Register one written view in ``PROJECT_INDEX.json`` as a ``derived`` artifact
    (the views registry's registration requirement). Deliberately NOT wrapped in a try/except:
    ``project_index.RegistrationRefused`` (e.g. a view written into the confidential
    vault under ``local_preview``) must propagate as a hard build failure, the same way
    ``generator.BuildBlockedError`` already does for its own hard stops (no
    ``except: return a plausible default`` anywhere).

    **Registers the path relative to the INDEX's own directory, not the host root
    (2026-09-24).** This used to relativize against ``engine_config.host_root()``
    unconditionally, which silently disagreed with ``artifact_index._artifact_root()`` --
    the frame every READER (``verify``, ``list_artifacts``, the dashboard) resolves a
    registered path against, and which is documented there as "moving the index moves its
    frame of reference with it": a host that relocates ``PROJECT_INDEX.json`` away from its
    repo root (exactly what a host wanting to avoid a root-level collision would do -- see
    ``engine_config.project_index_path()``) got every view registered with a path that
    ``verify()`` then reported ``MISSING``, because the two sides of one registration were
    measured against two different roots. Measured live in a host with the index relocated
    to a doc-system subdirectory: a real ``cli build`` wrote and registered a view, and
    ``verify()`` reported ``file not found`` for all four -- correct data, WRONG frame.

    ``os.path.relpath``, not ``Path.relative_to``: the index's directory and the output
    directory are typically SIBLINGS under the host root (a doc-system state directory and a
    docs output tree), never one inside the other, so a real relocation is exactly the case
    ``relative_to`` cannot express (it has no ``..`` -- ``walk_up=True`` needs Python 3.12,
    this package targets 3.11+) and ``relpath`` exists precisely for. Falling back to storing
    an ABSOLUTE path (the previous behaviour whenever ``relative_to`` failed) is avoided
    deliberately: ``PROJECT_INDEX.json`` is a TRACKED, committed file, and an absolute path
    bakes one contributor's local filesystem layout into it for every other checkout to read.
    """
    project_index = _load_project_index()
    try:
        rel_path = os.path.relpath(out_path.resolve(), project_index._artifact_root().resolve())
    except ValueError:
        # Only raised on Windows when the two paths are on different drives -- genuinely
        # inexpressible as a relative path. An absolute string is the honest fallback then.
        rel_path = str(out_path)
    project_index.register_artifact(
        project_index.Artifact(
            id=f"{source_header.id}.{audience}",
            path=rel_path,
            type="document",
            title=f"{source_header.title} ({audience} view)".strip(),
            section=source_header.id,
            summary=(
                f"Generated {audience}-audience view of '{source_header.id}', derived by "
                "tools/docgen/views.py -- never hand-edited, regenerated every build."
            ),
            tags=["derived", "view", audience],
            status="generated",
            engine="docgen.views",
        )
    )


def _retire_stale_view(out_path: Path, source_header: DocHeader, audience: str) -> None:
    """Remove a STALE view + its registration when THIS rebuild is gate-blocked.

    Gate 9 (and every other gate ``run_gates`` folds in) guards the WRITE path only --
    nothing previously guarded RETENTION, so a document that once published a clean view
    and later grows a leak kept serving the OLD view forever while the gate correctly
    reported the new one blocked. Called ONLY on an actual blocking gate result (never
    merely because ``may_write=False`` -- a dry-run/preview build must not mutate an
    existing view either).

    Deliberately NOT wrapped in a try/except: a failed deregister or delete must be LOUD
    (no ``except: return a plausible default`` anywhere), never silently
    swallowed -- a half-retired view (removed from the index but still on disk, or the
    reverse) is exactly the half-done state this function exists to prevent. Deregisters
    BEFORE deleting the file: if the delete then raises, the worst residue is an
    unregistered stray file on disk (inert -- nothing indexes it), never a registered
    artifact whose path no longer exists.
    """
    if not out_path.exists():
        return
    project_index = _load_project_index()
    project_index.remove_artifact(f"{source_header.id}.{audience}")
    out_path.unlink()


def _retire_all(
    pending: list[tuple[Path, str]], header: DocHeader, *, may_write: bool
) -> None:
    """Retire every stale view in *pending*, then raise if any failed. ONE definition.

    Two guarantees live here. `may_write` is checked HERE so no caller can forget it — a
    dry-run/preview build must not mutate an existing view, which both docstrings promised and
    the code did not do. And every audience is attempted before anything is raised: retirement
    is deliberately loud, and while the raise lived inside the audience loop the first
    failure aborted it and left the remaining audiences' stale views published and registered.
    A retention fix whose failure mode is "retire one, keep three" is not a retention fix.

    Called from BOTH exits of `build_and_gate_views` — the gate-blocked path and the sub-floor
    authoring refusal. An authoring refusal IS a blocked rebuild, so it must retire too;
    returning early without retiring would reopen exactly the retention hole
    (a document that can no longer build keeps serving its old view forever).
    """
    if not may_write:
        return
    failures: list[tuple[str, Exception]] = []
    for out_path, audience in pending:
        try:
            _retire_stale_view(out_path, header, audience)
        except Exception as exc:  # noqa: BLE001 - always re-raised below; nothing is swallowed
            failures.append((audience, exc))
    if len(failures) == 1:
        # One failure re-raises UNCHANGED — same type, same traceback, same behaviour as before
        # this fix. Only the multi-failure case, which could not arise while the first raise
        # aborted the loop, is new.
        raise failures[0][1]
    if failures:
        raise RuntimeError(
            f"'{header.id}': {len(failures)} audience view(s) could not be retired "
            f"({'; '.join(f'{a}: {exc!r}' for a, exc in failures)}). Every audience was "
            "attempted; the first failure is chained as the cause."
        ) from failures[0][1]


def build_and_gate_views(
    *,
    source_stem: str,
    md_text: str,
    header: DocHeader,
    out_directory: Path,
    manifest_rows: list[ManifestRow] | None,
    local_preview: bool = False,
    may_write: bool = True,
) -> ViewsBuildResult:
    """The single seam ``generator.build()`` calls. Does nothing (returns a clean, empty
    result) unless ``md_text``'s body carries at least one audience marker -- see the
    module docstring's "purely additive" guarantee.

    For a document that DOES carry markers: parses the body into segments (fail-closed --
    see ``parse_body_segments``), then for each of the four audiences renders its view,
    arms gate 9 against the blocks excluded FROM that view (see "Gate-9 wiring" in the
    module docstring), and runs the FULL gate pipeline (``export_sanitizer.run_gates`` --
    not gate 9 alone) against the rendered markdown. A view is written to disk, and
    registered in ``PROJECT_INDEX.json``, only when its own gate result is clean AND
    ``may_write`` is True -- exactly the ``if gate.ok and may_write`` pattern
    ``generator.build()`` already uses for its html/json/pdf outputs. Every gate result
    (passing or not) is folded into the returned ``ViewsBuildResult.gate``, so a caller
    that merges it into its own running gate result gets an honest signal even for a
    view that was blocked and therefore never written. Conversely, when a rebuild for a
    given audience IS gate-blocked, any PREVIOUSLY written view + registration for that
    same (stem, audience) is retired -- see "Retention on a blocked rebuild" in the
    module docstring and ``_retire_stale_view``.
    """
    if is_generated_view_text(md_text):
        raise AudienceMarkerError(
            f"'{source_stem}' is itself a GENERATED audience view (carries the "
            f"{_GENERATED_VIEW_TOKEN!r} stamp) and may not be re-processed as an "
            "authored source -- point the build at the original document instead."
        )

    body_md = _strip_body(md_text)
    if not has_audience_markers(body_md):
        return ViewsBuildResult(gate=GateResult(gate="audience_views", findings=[]), outputs={})

    default_audience = _front_matter_default_audience(md_text)
    segments = parse_body_segments(body_md, default_audience=default_audience, doc_id=header.id)

    merged = GateResult(gate="audience_views", findings=[])
    outputs: dict[str, Path] = {}
    pending_retirement: list[tuple[Path, str]] = []

    # The views registry requires every generated view to be REGISTERED as derived. Probe that once, before
    # writing anything: a view written and then left unregistered would be a half-done build
    # output, and discovering the problem per-view would write some and block others. A host
    # that shadows the engine's `project_index` (see ViewRegistrationUnavailable) gets ONE
    # blocking finding naming the cause, and no view is written at all.
    try:
        _load_project_index()
    except ViewRegistrationUnavailable as exc:
        merged = merged.merge(
            GateResult(
                gate="audience_views",
                findings=[
                    Finding(
                        gate="audience_views",
                        message=f"generated views cannot be registered as derived: {exc}",
                        severity=Severity.HIGH,
                        blocking=True,
                        evidence=(
                            "views registry: views are registered build outputs; one that cannot be "
                            "registered must not be written"
                        ),
                    )
                ],
            )
        )
        merged.gate = "audience_views"
        return ViewsBuildResult(gate=merged, outputs={})

    # Sub-floor refusal. Render every audience FIRST, then refuse sub-floor excluded blocks
    # before a single view is written — the same "probe once, before writing anything" discipline
    # the registration check above uses, and for the same reason: a per-audience refusal would
    # write some views and block others.
    rendered = [(audience, *render_view(segments, audience)) for audience in AUDIENCE_LEVELS]

    # Gate 9's exact-substring check exists for blocks too short to shingle, and at that length it
    # cannot tell a leak from a coincidence: `Pending` matched "the review is pending sign-off",
    # and "See the table below." matched its own legitimate reuse — CRIT and blocking, both times
    # (4 of 4 constructed cases). The ambiguity is real and no reading of the text
    # removes it, so this rule removes the INPUT instead: an excluded block must carry enough
    # distinctive content to be checkable, and the author is told so at build time rather than the
    # gate guessing. The alternatives were rejected deliberately — a distinctiveness or boilerplate
    # allowlist is a new false-negative surface on a moat, and downgrading the CRIT to a warning
    # trades a certain availability loss for an uncertain security one.
    sub_floor: dict[str, list[str]] = {}
    for audience, _view_text, excluded_block_texts in rendered:
        for block in excluded_block_texts:
            if export_sanitizer.below_shingle_floor(block):
                sub_floor.setdefault(" ".join(block.split()), []).append(audience)
    if sub_floor:
        for block, audiences in sub_floor.items():
            merged = merged.merge(
                GateResult(
                    gate="audience_views",
                    findings=[
                        Finding(
                            gate="audience_views",
                            message=(
                                f"'{header.id}': the block excluded from the "
                                f"{', '.join(audiences)} view(s) carries fewer than "
                                f"{export_sanitizer.MIN_SHINGLE_N} distinctive content words, so gate 9 "
                                "cannot "
                                "tell a real leak from an ordinary sentence that happens to use "
                                "the same words. Widen it to a distinctive span of at least "
                                f"{export_sanitizer.MIN_SHINGLE_N} content words, or move the sentence out of the "
                                f"audience block — do not weaken the gate. Offending block: "
                                f"{block!r}"
                            ),
                            severity=Severity.HIGH,
                            blocking=True,
                            evidence=(
                                "sub-floor refusal: an excluded block below the n="
                                f"{export_sanitizer.MIN_SHINGLE_N} shingle floor is not checkable"
                            ),
                        )
                    ],
                )
            )
        # An authoring refusal is a BLOCKED REBUILD, so the same retention rule applies: a
        # document that can no longer build must not keep serving the view it published before
        # the offending block was added. Returning here without retiring would reopen
        # the retention hole. Caught by this module's own test, not by review.
        _retire_all(
            [
                (out_directory / generated_view_filename(source_stem, audience), audience)
                for audience in AUDIENCE_LEVELS
                if (out_directory / generated_view_filename(source_stem, audience)).exists()
            ],
            header,
            may_write=may_write,
        )
        merged.gate = "audience_views"
        return ViewsBuildResult(gate=merged, outputs={})

    for audience, view_text, excluded_block_texts in rendered:
        view_header = build_view_header(header, excluded_block_texts)
        gate = export_sanitizer.run_gates(
            view_text,
            view_header,
            siblings=excluded_block_texts,
            manifest_rows=manifest_rows,
            local_preview=local_preview,
        )
        merged = merged.merge(gate)
        out_path = out_directory / generated_view_filename(source_stem, audience)
        if gate.ok and may_write:
            out_path.write_text(_stamp(header.id, audience) + view_text, encoding="utf-8")
            outputs[f"view:{audience}"] = out_path
            _register_view(out_path, header, audience)
        elif not gate.ok:
            # COLLECT unconditionally; `_retire_all` is the ONE place that decides whether to act
            # on `may_write`. Guarding here as well would be a second copy of that decision, and
            # a second copy is a duplicated guard — it also made the red proof for this
            # very property come back GREEN, because removing either guard left the other
            # standing. One decision, one site, one test that can fail.
            pending_retirement.append((out_path, audience))

    # Second half of the retention fix. `_retire_stale_view` is deliberately loud, and it used to be
    # called INSIDE the audience loop — so the first raise aborted the loop and left the remaining
    # audiences' stale views published and registered. A retention fix whose failure mode is
    # "retire one, keep three" is not a retention fix. Every audience is retired, then the first
    # error is re-raised with the rest chained to it, so nothing is swallowed either.
    _retire_all(pending_retirement, header, may_write=may_write)

    merged.gate = "audience_views"
    return ViewsBuildResult(gate=merged, outputs=outputs)
