"""``crossrefs`` — every internal link and document reference must resolve.

**What already owns half of this question, and is not re-asked here.** `tools/health` `CONS-06`
resolves every **backtick-delimited** repo-relative path across all tracked Markdown against
*tracked* content, with `docs/process/ABSENT_PATHS.md` as a reviewable registry of deliberate
absences. That check stays the owner of backticked paths; this guard never re-scans them.

**What was missing.** `CONS-06`'s pattern is anchored on backticks, so a **Markdown link** —
``[text](target)`` — is invisible to it. Two whole classes of dead reference could therefore exist
in this corpus with every check green:

* a link to a file that was moved or never written;
* a link to a ``#section`` that was renamed.

The second is the one worth having. An anchor is the reference most likely to rot, because renaming
a heading is a normal edit that no reader connects to a link three documents away — and it is
invisible in source *and* in the rendered page, which is doctrine §8.4's "grep the outputs" class
seen from the other side.

**Deliberately out of scope: external URLs.** `http(s)` targets are not checked. The engine's
offline law (RULEBOOK L23) means a guard that reaches the network cannot run in a fresh clone or a
verification lab, and a guard that is *sometimes* skipped is one whose green means nothing.
"""

from __future__ import annotations

import re

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.corpus_check.text import (
    heading_slugs,
    is_append_only_record,
    iter_prose_lines,
    iter_prose_lines_with_headings,
    strip_inline_code,
    under_dated_heading,
)

GUARD = "crossrefs"

# `[text](target)` — target taken up to the first whitespace so a titled link `[t](p "Title")`
# yields the path alone. Images (`![alt](src)`) are included: a dead image is a dead reference.
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")

# **Reference-style links and raw HTML, both invisible to `_LINK_RE`** (`OG-111`). Pass 6 recorded
# this as `P6-67` and it was not fixed, so Pass 7 found it again — a guard advertising "every
# internal link resolves" while seeing exactly ONE link across 58 documents is a green that means
# almost nothing, and its coverage number said so plainly.
#
# `[text][label]` resolves through a `[label]: target` definition, which must start a line (up to
# three spaces of indent, per CommonMark). A use with no definition renders LITERALLY — the reader
# sees `[text][label]` on the page — so an undefined label is a dead reference of its own kind and
# is reported as one.
_REF_USE_RE = re.compile(r"!?\[[^\]]*\]\[([^\]]+)\]")
_REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*<?([^\s>]+)>?", re.MULTILINE)

# **In an HTML file, `[a][b]` is almost never Markdown** (`OG-264`). A tracked, built page carries CSS attribute selectors
# (`[data-k="node"][data-id="n0"]`), JavaScript indexing (`rows[i][j]`) and inline SVG, and every one of them matches
# `_REF_USE_RE`; the flagship gallery reported 221 "dead reference-style links" the day its figures gained scoped hover
# CSS. What the check is FOR — an unrendered `[text][label]` that a reader would see on the page — lives in text
# nodes, so for HTML the use-check reads only what is outside these regions (newlines kept so line numbers hold).
_OPAQUE_HTML_RE = re.compile(r"<(script|style|svg|pre|code|template)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)


def _mask_opaque_html(text: str) -> str:
    return _OPAQUE_HTML_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


# `<a href>`, `<img src>`, `<link href>`, `<script src>` in tracked HTML and in Markdown's inline
# HTML. A dead `href` in a built page is the same defect as a dead Markdown link and is the more
# likely of the two to survive, because nothing renders it differently.
_HTML_REF_RE = re.compile(
    r"""<(?:a|img|link|script)\b[^>]*?\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE
)

# Schemes a guard that must work offline has no business resolving.
_EXTERNAL = ("http://", "https://", "mailto:", "ftp://", "tel:", "data:", "//")

# Floor: 1, and the number is small for a MEASURED reason rather than a convenient one. This
# corpus contains exactly **one** Markdown link across all 56 tracked documents — it cites in
# backticks almost exclusively, which is `CONS-06`'s territory by design. A floor set to what the
# guard "ought" to find would fail permanently on a corpus that is simply written that way, and a
# gate that is red for a reason nobody can fix is a gate people route around.
#
# So the floor guards the degenerate case only: the scanner breaking entirely. The guard's value
# here is real but thin, and it grows with any host project that links rather than backticks —
# which is the shape most documentation corpora actually have.
# **Raised from 1 to 2** (`OG-111`). At 1 the floor was satisfied by the single inline Markdown
# link this corpus contains — `checked == floor == 1` across 58 documents, which is vacuity by
# construction: the guard could stop working entirely and still clear its own bar. Widening the
# guard to reference-style and HTML references took real coverage to 3, so 2 requires the guard to
# still be seeing more than one thing while tolerating one reference being legitimately deleted.
_FLOOR = 2


def _resolve_target(corpus: Corpus, rel: str, target: str) -> str | None:
    """Resolve a link target to a tracked path, or ``None`` if it does not resolve.

    Tried document-relative first, then repo-root-relative, because both spellings are live in this
    corpus and picking one would report the other as dead.
    """
    doc_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
    candidates = []
    if doc_dir:
        # Normalise `../` without touching the filesystem — a link is a repo reference, not a path
        # on this machine, and `Path.resolve()` would follow symlinks out of the repository.
        parts: list[str] = []
        for piece in f"{doc_dir}/{target}".split("/"):
            if piece in ("", "."):
                continue
            if piece == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(piece)
        candidates.append("/".join(parts))
    candidates.append(target.lstrip("./"))
    for candidate in candidates:
        if corpus.resolves(candidate):
            return candidate
    return None


def run(corpus: Corpus) -> GuardResult:
    """Resolve every Markdown link target and every in-document anchor."""
    findings: list[Finding] = []
    checked = 0
    slug_cache: dict[str, set[str]] = {}

    def slugs(path: str) -> set[str]:
        if path not in slug_cache:
            slug_cache[path] = heading_slugs(corpus.text(path))
        return slug_cache[path]

    scanned: list[tuple[str, bool]] = [(rel, True) for rel in corpus.markdown]
    scanned += [
        (rel, False)
        for rel in corpus.tracked
        if rel.endswith((".html", ".htm")) and "node_modules" not in rel
    ]

    for rel, is_markdown in scanned:
        text = corpus.text(rel)
        # A reference DEFINITION must begin a line; one quoted inside a table cell is not a
        # definition, which is why this is derived from the whole document rather than per line.
        definitions = {m.group(1).strip().lower() for m in _REF_DEF_RE.finditer(text)}
        doc_is_record = is_append_only_record(text)  # OG-140: declared, not inferred
        lines = (
            list(iter_prose_lines_with_headings(text))
            if is_markdown
            else [(n, ln, ()) for n, ln in enumerate(text.splitlines(), 1)]
        )
        # The reference-style USE check reads text nodes only in HTML (see `_OPAQUE_HTML_RE`); hrefs below read raw.
        use_lines = dict(enumerate(_mask_opaque_html(text).splitlines(), 1)) if not is_markdown else {}
        for line_no, raw_line, headings in lines:
            # `VERIFICATION_LOG.md` quotes the probes a pass ran, dead links and all — reporting
            # those is reporting the log for recording what it found. Same dated-heading test the
            # rest of the package uses, so "record" means one thing here.
            if doc_is_record and under_dated_heading(headings):
                continue
            use_line = raw_line if is_markdown else use_lines.get(line_no, "")
            for match in _REF_USE_RE.finditer(strip_inline_code(use_line)):
                label = match.group(1).strip().lower()
                checked += 1
                if label in definitions:
                    continue
                findings.append(
                    Finding(
                        guard=GUARD,
                        path=rel,
                        line=line_no,
                        message=f"reference-style link [{match.group(1)}] has no definition",
                        evidence=(
                            "a `[text][label]` with no `[label]: target` renders literally — the "
                            "reader sees the brackets on the page"
                        ),
                        severity=Severity.MEDIUM,
                    )
                )
            for match in _HTML_REF_RE.finditer(raw_line):
                raw = match.group(1).strip()
                if not raw or raw.startswith(_EXTERNAL) or raw.startswith("#"):
                    continue
                if "<" in raw or "{" in raw or "*" in raw:
                    continue
                target = raw.partition("#")[0]
                if not target:
                    continue
                checked += 1
                resolved = _resolve_target(corpus, rel, target)
                if resolved is None:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"`{target}` referenced by an HTML href/src does not resolve",
                            evidence=(
                                "a dead href in a built page is invisible in source and in the "
                                "rendered output — doctrine §8.4's class seen from the other side"
                            ),
                            severity=Severity.MEDIUM,
                        )
                    )
        if not is_markdown:
            continue
        for line_no, raw_line in iter_prose_lines(text):
            # A link inside an inline code span is being SHOWN, not followed. `PHASE3_OVERLAP.md`
            # explains this guard by quoting `` `[text](path)` `` and `` `[text](#anchor)` `` — and
            # the first version of this guard reported the document that documents it as carrying
            # two dead references. Fenced blocks were already excluded; inline spans were not.
            line = strip_inline_code(raw_line)
            for match in _LINK_RE.finditer(line):
                raw = match.group(1).strip()
                if not raw or raw.startswith(_EXTERNAL):
                    continue
                # A link written as a template placeholder is documentation of a shape.
                if "<" in raw or "{" in raw or "*" in raw:
                    continue
                path_part, _, anchor = raw.partition("#")
                checked += 1

                if not path_part:
                    # Same-document anchor.
                    if anchor and anchor.lower() not in slugs(rel):
                        findings.append(
                            Finding(
                                guard=GUARD,
                                path=rel,
                                line=line_no,
                                message=f"link to #{anchor} — no heading in this document has "
                                "that anchor",
                                evidence=(
                                    "A renamed heading breaks every link to it, and the break is "
                                    "invisible in the source AND in the rendered page."
                                ),
                                severity=Severity.MEDIUM,
                            )
                        )
                    continue

                resolved = _resolve_target(corpus, rel, path_part)
                if resolved is None:
                    hint = (
                        " (exists on disk but is not tracked — it will not survive a clone)"
                        if corpus.exists_untracked(path_part)
                        else ""
                    )
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"link target does not resolve to tracked content: {path_part}"
                            + hint,
                            evidence="[…](…) targets are invisible to CONS-06's backtick pattern.",
                            severity=Severity.MEDIUM,
                        )
                    )
                    continue

                if anchor and resolved.endswith(".md") and anchor.lower() not in slugs(resolved):
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"link to {resolved}#{anchor} — that document has no heading "
                            "with that anchor",
                            evidence="the file resolves; the section inside it does not",
                            severity=Severity.MEDIUM,
                        )
                    )

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: all {checked} internal link target(s) and anchor(s) resolve across "
        f"{len(corpus.markdown)} tracked document(s)",
        checked=checked,
        floor=_FLOOR,
        evidence="backticked repo paths remain CONS-06's question, deliberately not re-asked here",
    )
