"""``rendered-output`` — guards run against **built artifacts too**, not only source.

Doctrine §5 marks this guard `[UE-S4]`, meaning this engine's own reverification earned it, and §8.4
states the rule it enforces: *"Grep the outputs, not just the source."* The evidence is not
theoretical and it is not old:

* a brand font survived a "zero residue" sweep because it appeared **only** in rendered HTML;
* this engine's documented dark/light theme toggle did nothing at all while `npm test` was green;
* the flagship document shipped through **four** green verification passes carrying **118 literal
  backticks** in its rendered body — inline code that never became code — because every guard in
  the project read Markdown and nothing read HTML.

`BUILD-01` builds three documents and discards the bytes; `BUILD-02` runs the gate spine over the
sources. Neither has ever looked at what came out. This guard is the missing half, and it is the
capability `OG-49` and `OG-50` were both scheduled to Phase 3 to wait for.

**Two families of check.**

1. **Unrendered markup in visible text.** Backticks, ``**bold**``, pipe-table rows and figure
   placeholders surviving into a text node mean the renderer silently declined to render something.
   Text nodes only: a backtick inside ``<code>``, ``<pre>``, ``<script>`` or ``<style>`` is content,
   not residue, and a guard that cannot tell the difference reports the flagship's own code samples
   as defects.

2. **Contrast measured on the document that was built** (`OG-49`). Gate 10 blocks correctly when it
   is given illegible pairs — that was falsified both ways — but **every caller passes
   ``pairs=None``**, so it has only ever checked the Atlas design tokens. It is a token-regression
   gate documented as a per-document accessibility gate. Here the pairs come out of the built
   stylesheet: each theme block's declared ink values against that same block's ground values, fed
   to the real `export_sanitizer.gate_wcag_contrast`. The maths is never re-derived here — that
   would be a second source of truth about WCAG.

**Which roles carry text is a design fact, not a derivable one.** ``--faint`` lives among the ink
tokens and is a hairline; pairing it with a ground would fail a contrast check for a line that
carries no text. So the ink/ground role names below are declared, and the guard asserts each one is
actually **present** in the built output — if a role disappears, that is a finding rather than a
silently smaller check.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import (
    Finding,
    GuardResult,
    Severity,
    failed,
    passed,
    skipped,
)
from tools.docgen.generator import GENERATED_MARKER as _GENERATED_MARKER

GUARD = "rendered-output"

# Built into the repo, under the gitignored derived-state directory the engine already uses for
# `build --cached`. Outside the repo is not an option: the generator canonicalises its output path
# inside the repository on purpose, so a build cannot be redirected somewhere unreviewable.
_OUT_DIR = Path(".docgen") / "corpus_check"

# Regions whose contents are content, never residue.
_OPAQUE_RE = re.compile(
    r"<(script|style|pre|code|svg|template)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html_comments(text: str, repl: str = " ") -> str:
    """Replace every `<!-- ... -->` with *repl*, in one forward pass. See the note below."""
    out: list[str] = []
    index = 0
    while True:
        start = text.find("<!--", index)
        if start == -1:
            break
        end = text.find("-->", start + 4)
        if end == -1:
            break  # an unterminated opener is not a comment; leave the tail as content
        out.append(text[index:start])
        out.append(repl)
        index = end + 3
    out.append(text[index:])
    return "".join(out)

#: This WAS `re.compile(r"<!--.*?-->", re.DOTALL)` used as `.sub(" ", text)`, and it
#: was quadratic: 13.8 ms at 4 KB, 908 ms at 32 KB of repeated unterminated `<!--` (8x the input,
#: 66x the time). The cause is NOT the inner pattern's backtracking — an unrolled-loop regex
#: measured 3.4x WORSE — it is `re.sub` itself retrying at every position after a failed match.
#: A regex cannot fix that, so the strip is a single forward scan: `str.find` never re-reads
#: consumed text. 931 ms -> 0.043 ms on the same shape, growth x5 instead of x65.
#:
#: Equivalence with the old pattern was proven, not assumed: identical output over 4,012 inputs
#: (12 crafted plus 4,000 random assemblies of `<!--`/`-->`/text/newline). `str.find("-->", i + 4)`
#: is exactly the lazy `.*?`'s first-close semantics.
_ENTITY_RE = re.compile(r"&[a-zA-Z#0-9]{2,8};")

# Declared text roles. See the module docstring for why these are declared rather than derived.
_INK_ROLES = ("fg", "bone", "ash")
_GROUND_ROLES = ("bg", "paper", "paper-2", "night", "steel-2")

# A CSS block that establishes a theme: `:root{…}`, a `prefers-color-scheme` media block, or an
# explicit `[data-theme=…]` selector.
_CSS_BLOCK_RE = re.compile(r"([^{}]*)\{([^{}]*)\}")
_CUSTOM_PROP_RE = re.compile(r"--([a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,8})")

# Checked against the RAW html, before comments are stripped. `_visible_text` removes comments (they
# are not visible text), so a pattern matching a comment could never fire from there — the guard's
# only CRITICAL was unreachable for its whole life, proven by two verifiers with a control.
_RAW_PATTERNS: tuple[tuple[re.Pattern[str], str, Severity], ...] = (
    (re.compile(r"<!--\s*figure:"), "an unresolved figure placeholder", Severity.CRITICAL),
)

_RESIDUE_PATTERNS: tuple[tuple[re.Pattern[str], str, Severity], ...] = (
    (re.compile(r"`"), "a literal backtick — inline code that never became code", Severity.HIGH),
    (re.compile(r"\*\*[^*\n]{1,80}\*\*"), "unrendered **bold**", Severity.HIGH),
    # **Not line-anchored, because the anchor was the bug** (`OG-112`). `^\s*\|.+\|\s*$` fired on
    # `<p>| a | b |</p>` and missed `<p>Intro | a | b | trailing</p>` — the same unrendered row,
    # invisible purely because of where the renderer put a newline. Three pipes on one line is the
    # signal instead: a real table row always has them, and ordinary prose does not. Measured
    # across all four tracked built documents: **zero** matches, so this adds no noise; a
    # single-pipe example like ``--a | --b`` is correctly ignored.
    (re.compile(r"\|[^|\n]*\|[^|\n]*\|"), "an unrendered pipe-table row", Severity.HIGH),
    # ⚠ `\b` BINDS TO WORD CHARACTERS, AND `]` IS NOT ONE. Written as
    # `\b(?:undefined|NaN|\[object Object\])\b` the trailing boundary sat between `]` and
    # whatever followed — two non-word characters, which is never a boundary — so the
    # `[object Object]` arm **could not match anything at all**, in any input. The guard listed
    # the most recognisable JavaScript sentinel of the three and had never once been able to see
    # it. A pattern is only as real as its counter-example; this one had none (`OG-104`).
    #
    # The boundaries now apply only to the bare words that need them, and the bracketed literal
    # carries its own delimiters.
    (re.compile(r"\b(?:undefined|NaN)\b|\[object Object\]"),
     "a JavaScript sentinel leaked into visible text", Severity.HIGH),
)

_FLOOR = 1

# The two vendored render engines. Their `node_modules` is gitignored by design, so it is absent in
# a fresh clone, in CI, and in every `git archive` verification lab.
_ENGINES = ("tools/visual-engine", "tools/mermaid-engine")

# What a build says when it is the ENVIRONMENT that is missing, not the corpus that is wrong.
_ENV_SIGNATURES = ("engine deps not installed", "run `npm install`", "Cannot find module")

# What `generator._stamp_generated` appends to every document this engine produces.
# **Imported, never restated** (`OG-114`, `docs/process/RULES.md` Rule 2). This was a hand-copied
# duplicate of the literal in `tools/docgen/generator.py`, with no test coupling the two: changing
# the stamp there left this guard recognising nothing, and the resulting SKIP reads as green in a
# default health run — which is what the pre-push hook runs. The import makes the two impossible
# to disagree, and fails loudly at collection time rather than quietly at judgement time.
_DOCGEN_STAMP = _GENERATED_MARKER


# Tags that begin or end a BLOCK. Their boundaries are line boundaries for a reader, so they must
# be line boundaries for a line-anchored residue pattern too. Inline tags (`<code>`, `<em>`, `<a>`)
# deliberately are not here: turning those into newlines would split a single visible sentence —
# and a command inside `<code>` — across lines, manufacturing the opposite defect.
_BLOCK_TAGS = (
    "p", "div", "section", "article", "header", "footer", "main", "aside", "nav",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "pre", "blockquote",
    "figure", "figcaption", "hr", "br", "form", "fieldset", "details", "summary",
)
_BLOCK_TAG_RE = re.compile(
    r"</?(?:" + "|".join(_BLOCK_TAGS) + r")\b[^>\n]*>", re.IGNORECASE
)


def _visible_text(html: str) -> str:
    """Everything a reader sees, with code, markup and entities removed.

    Order matters and is the reason this is one function rather than a chain at the call site:
    opaque regions go first (so their contents never reach the residue patterns), then comments,
    then tags. Removing tags first would expose the inside of a ``<pre>`` as ordinary text.
    """
    text = _OPAQUE_RE.sub(" ", html)
    text = _strip_html_comments(text)
    # **A block-level tag becomes a NEWLINE; an inline tag becomes a space** (`OG-112`).
    #
    # Every tag used to become a space, so the visible text's line structure was inherited from
    # wherever the renderer happened to emit whitespace rather than from the document's own blocks.
    # The pipe-table residue pattern is line-anchored (`^\s*\|.+\|\s*$`), so it fired on
    # `<p>| a | b |</p>` alone on a line and **missed** `<p>Intro | a | b | trailing</p>` — the same
    # unrendered row, invisible because of where a newline landed. Measured on the real artifact:
    # 557 source lines collapsed to 66 visible lines, the longest 288 characters, so most of the
    # document was one line as far as a line-anchored pattern was concerned.
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    return _ENTITY_RE.sub(" ", text)


def _theme_blocks(html: str) -> dict[str, dict[str, str]]:
    """``selector -> {role: hex}`` for every CSS block declaring colour custom properties."""
    blocks: dict[str, dict[str, str]] = {}
    for style in re.findall(r"<style\b[^>]*>(.*?)</style\s*>", html, re.DOTALL | re.IGNORECASE):
        for selector, body in _CSS_BLOCK_RE.findall(style):
            props = dict(_CUSTOM_PROP_RE.findall(body))
            if props:
                blocks.setdefault(selector.strip()[:80] or ":root", {}).update(props)
    return blocks


def _build(root: Path, docs: tuple[str, ...], out: Path) -> tuple[int, str]:
    """Build the governed corpus into ``out``. Returns ``(exit code, combined output)``."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "tools.docgen.cli", "build", *docs, "-o", str(out)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def inspect_residue(rel_out: str, html: str) -> tuple[list[Finding], int]:
    """Findings for unrendered Markdown surviving into ``html``'s visible text, and the count checked.

    Module-level and taking bytes rather than a path **so it can be falsified against a real built
    artifact**. `LESSONS.md` L-15: the probe goes only into the artifact the gate certifies. A test
    that hand-wrote its own HTML would be comparing a literal against itself, which
    `DOC_WRITING_DOCTRINE.md` §5 forbids outright — so the retained counter-example builds this
    repository's own corpus, plants one backtick in the OUTPUT, and requires the red.
    """
    text = _visible_text(html)
    findings: list[Finding] = []
    # **Which corpus a pattern searches is carried EXPLICITLY, not re-derived by membership**
    # (`OG-125`). It used to ask `(pattern, what, severity) in _RAW_PATTERNS` — and `re.Pattern`
    # defines no `__eq__`, so that comparison is IDENTITY. It happened to work only because
    # `re.compile` interns identical (source, flags) pairs; the same source with different flags is
    # a different object, and a triple duplicated across the two tuples would dispatch both copies
    # to the raw corpus. A dispatch that is correct by coincidence is one edit from being wrong,
    # and the failure would be silent: a residue pattern quietly searching the wrong text.
    scans = [(p_, w, sev, html) for p_, w, sev in _RAW_PATTERNS]
    scans += [(p_, w, sev, text) for p_, w, sev in _RESIDUE_PATTERNS]
    for pattern, what, severity, corpus_text in scans:
        hits = pattern.findall(corpus_text)
        if not hits:
            continue
        sample = ", ".join(repr(h if isinstance(h, str) else h[0])[:60] for h in hits[:3])
        findings.append(
            Finding(
                guard=GUARD,
                path=rel_out,
                line=0,
                message=f"{len(hits)} occurrence(s) of {what} in the rendered body",
                evidence=f"first: {sample} — invisible in the Markdown source; only a guard "
                "that reads the OUTPUT can see it (doctrine §8.4)",
                severity=severity,
            )
        )
    return findings, len(_RAW_PATTERNS) + len(_RESIDUE_PATTERNS)


def inspect_contrast(rel_out: str, html: str) -> tuple[list[Finding], int, int]:
    """Findings for text pairings in ``html``'s own stylesheet that fail WCAG-AA (`OG-49`).

    The WCAG maths is never re-derived here — `export_sanitizer.gate_wcag_contrast` owns it, and a
    second implementation would be the two-sources-of-truth defect this engine exists to catch. What
    is new is the *input*: pairs read out of the document that was actually built, where every
    caller before this passed ``pairs=None`` and got the design tokens.
    """
    from tools.docgen.export_sanitizer import ColorPair, gate_wcag_contrast

    blocks = _theme_blocks(html)
    if not blocks:
        return [
            Finding(
                guard=GUARD,
                path=rel_out,
                line=0,
                message="the built document declares no colour custom properties",
                evidence="Gate 10 would then have nothing document-specific to check, which is "
                "the vacuous pass OG-49 is about",
                severity=Severity.HIGH,
            )
        ], 1, 0

    findings: list[Finding] = []
    checked = 0

    # **The declared roles must be PRESENT somewhere in this document**, which the docstring
    # promised and the code did not do: a verifier deleted `--fg` and watched the assertion count
    # fall 19 -> 14 with findings still 0, then deleted every ink role and watched it reach 0
    # assertions, still green. A check that silently shrinks to nothing and reports success is the
    # vacuous pass this package exists to catch (`LESSONS.md` L-19).
    #
    # Asserted per DOCUMENT, not per block: a single theme block legitimately carries a partial
    # palette — `:root, [data-theme="dark"]` sets the inks while the grounds are set elsewhere — so
    # a per-block rule would report the real stylesheet as defective.
    declared = {role for props in blocks.values() for role in props}
    for family, roles in (("ink", _INK_ROLES), ("ground", _GROUND_ROLES)):
        absent = [r for r in roles if r not in declared]
        if absent:
            findings.append(
                Finding(
                    guard=GUARD,
                    path=rel_out,
                    line=0,
                    message=f"the built document declares no `--{'`, `--'.join(absent)}` "
                    f"{family} role(s) anywhere",
                    evidence=f"the contrast check covers {family} roles "
                    f"{', '.join('--' + r for r in roles)}; a role that disappears shrinks the "
                    "check instead of failing it",
                    severity=Severity.MEDIUM,
                )
            )
        checked += len(roles)

    # Which roles actually reached a CONTRAST COMPARISON, as opposed to merely existing somewhere.
    paired_inks: set[str] = set()
    paired_grounds: set[str] = set()
    # **Pairs, counted separately from `checked`** (`OG-113`). `checked` also carries one assertion
    # per declared role, so it is >= 8 before a single pair is built — and the counter-example
    # whose message reads "no pairs were derived from the built document" was asserting
    # `checked > 0`, which is true with ZERO pairs. Measured: deleting every ink role from the real
    # built bytes gives `checked = 8, pairs = 0` and the assertion still passed. A test that cannot
    # fail for the reason it names is not a test.
    pairs_built = 0

    for selector, props in blocks.items():
        inks = [(r, props[r]) for r in _INK_ROLES if r in props]
        grounds = [(r, props[r]) for r in _GROUND_ROLES if r in props]
        if not inks or not grounds:
            # A theme block declaring only one side is a partial palette, not a defect — many
            # blocks set grounds alone. Whether a role vanished from the DOCUMENT is asserted above.
            continue
        pairs = [
            ColorPair(ink_hex, ground_hex, f"{rel_out} {selector}: --{ink} on --{ground}")
            for ink, ink_hex in inks
            for ground, ground_hex in grounds
        ]
        checked += len(pairs)
        pairs_built += len(pairs)
        paired_inks.update(ink for ink, _hex in inks)
        paired_grounds.update(ground for ground, _hex in grounds)
        for finding in gate_wcag_contrast(pairs).findings:
            if not finding.blocking:
                continue
            findings.append(
                Finding(
                    guard=GUARD,
                    path=rel_out,
                    line=0,
                    message=finding.message,
                    evidence="pairs derived from the BUILT stylesheet, not from "
                    "_DEFAULT_CONTRAST_PAIRS — OG-64's gap",
                    severity=Severity.HIGH,
                )
            )

    # **Present is not the same as CHECKED, and only the weaker of the two was asserted** — the
    # presence test above scans every theme block in the document, while contrast is only ever
    # computed inside blocks that declare BOTH an ink and a ground. A role declared exclusively in
    # ground-only blocks therefore satisfied "the role is present" while never once being compared
    # against anything, and the guard reported a clean contrast pass over it. That is the same
    # shape as `OG-64`, which this guard was written to close: coverage shrinking silently while
    # the summary keeps saying the check ran (`OG-105`).
    for family, roles, reached in (
        ("ink", _INK_ROLES, paired_inks),
        ("ground", _GROUND_ROLES, paired_grounds),
    ):
        unpaired = [r for r in roles if r in declared and r not in reached]
        if unpaired:
            findings.append(
                Finding(
                    guard=GUARD,
                    path=rel_out,
                    line=0,
                    message=f"{family} role(s) {', '.join('--' + r for r in unpaired)} are "
                    "declared in the built stylesheet but never reach a contrast comparison",
                    evidence=(
                        "contrast is computed only within a theme block that declares both an ink "
                        "and a ground; a role appearing only in single-sided blocks is never "
                        "compared, so its readability is unasserted while the summary still counts "
                        "the document as checked"
                    ),
                    severity=Severity.HIGH,
                )
            )
    return findings, checked, pairs_built


def run(corpus: Corpus) -> GuardResult:
    """Build the governed documents and inspect what came out."""
    docs = corpus.governed
    if not docs:
        return skipped(
            GUARD,
            "no governed documents to build",
            evidence="a tracked .md declaring `classification` in its front matter is the corpus "
            "this guard renders; with none, it would pass over nothing",
        )

    # **A missing engine is not a corpus defect, and treating it as one broke the moat.**
    # Measured: with `node_modules` absent, the build fails on every mermaid figure, this guard
    # reported CRITICAL, `CONS-11` went red, `tools.health` went red — and because the pre-push
    # hook RUNS health, the moat refused a *clean* push. The harness caught it as its positive
    # control, "a clean commit and push are accepted", which is exactly what a two-sided test is
    # for: the negative half was still perfect.
    #
    # SKIP, not pass. `tools/health/model.py`'s contract holds — SKIP means the question is open,
    # `--full` and `--strict` both fail on one, and this mirrors `SUITE-01`/`SUITE-02`, which skip
    # for the same reason and say so.
    missing = [e for e in _ENGINES if not (corpus.root / e / "node_modules").is_dir()]
    if missing:
        # **Degrade, do not disappear.** Skipping outright meant that on a fresh clone, in CI, and
        # in every `git archive` lab — exactly where a push is most likely to be the first one — the
        # guard added to catch what only built output shows checked NOTHING, and the moat accepted
        # it. The repository tracks a built deliverable precisely so output can be inspected without
        # building; inspecting it is strictly better than inspecting nothing.
        # **Only documents this engine actually built.** The repository also tracks a graph viewer,
        # a template and two legacy demo pages; none is a docgen document and none carries the
        # design system's colour roles, so judging them by this guard's rules manufactures
        # findings. The generator stamps what it produces (`generator._stamp_generated`), so the
        # set is derived from the artifact itself rather than from a path convention.
        tracked_built = [
            rel
            for rel in corpus.tracked
            if rel.endswith(".html")
            and "node_modules" not in rel
            and (corpus.root / rel).is_file()
            and _DOCGEN_STAMP in corpus.text(rel)
        ]
        if not tracked_built:
            return skipped(
                GUARD,
                f"render engine deps absent and no tracked built artifact to fall back on "
                f"({', '.join(missing)})",
                evidence="node_modules is gitignored by design, so it is absent in a fresh clone "
                "and in every `git archive` lab. Run `npm install` in each engine.",
            )
        degraded: list[Finding] = []
        seen = 0
        for rel in tracked_built:
            html = (corpus.root / rel).read_text(encoding="utf-8", errors="replace")
            residue, n = inspect_residue(rel, html)
            contrast, m, _pairs = inspect_contrast(rel, html)
            degraded.extend(residue + contrast)
            seen += n + m
        if degraded:
            return failed(GUARD, degraded, checked=seen, floor=_FLOOR)
        return skipped(
            GUARD,
            f"render engines absent — inspected {len(tracked_built)} TRACKED built artifact(s) "
            f"instead and found nothing ({seen} assertion(s))",
            evidence="SKIP, not PASS: the tracked artifact is a snapshot, so a defect introduced "
            "since it was committed would not appear. `--full`/`--strict` still fail on this. "
            f"Run `npm install` in {', '.join(missing)} to check the corpus as it stands.",
        )

    out = corpus.root / _OUT_DIR
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    code, log = _build(corpus.root, docs, out)
    if code != 0 and any(sig in log for sig in _ENV_SIGNATURES):
        # The pre-flight check above catches the common case; this catches a partially-installed
        # engine, where `node_modules` exists but a needed package inside it does not.
        return skipped(
            GUARD,
            "the governed corpus could not build for an environment reason, not a corpus one",
            evidence=log[-400:],
        )
    if code != 0:
        return failed(
            GUARD,
            [
                Finding(
                    guard=GUARD,
                    path=str(_OUT_DIR),
                    line=0,
                    message=f"the governed corpus does not build (exit {code})",
                    evidence=log[-600:],
                    severity=Severity.CRITICAL,
                )
            ],
            checked=0,
            floor=_FLOOR,
        )

    built = sorted(out.glob("*.html"))
    if not built:
        return failed(
            GUARD,
            [
                Finding(
                    guard=GUARD,
                    path=str(_OUT_DIR),
                    line=0,
                    message="the build exited 0 but wrote no HTML",
                    evidence="an exit code alone cannot distinguish a rendered corpus from an "
                    "empty directory",
                    severity=Severity.CRITICAL,
                )
            ],
            checked=0,
            floor=_FLOOR,
        )

    findings: list[Finding] = []
    checked = 0
    for path in built:
        rel_out = f"{_OUT_DIR}/{path.name}"
        html = path.read_text(encoding="utf-8", errors="replace")
        residue, n = inspect_residue(rel_out, html)
        findings.extend(residue)
        checked += n
        contrast, m, _pairs = inspect_contrast(rel_out, html)
        findings.extend(contrast)
        checked += m

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: {len(built)} built document(s) carry no unrendered markup and every declared "
        f"text pairing clears WCAG-AA ({checked} assertion(s))",
        checked=checked,
        floor=_FLOOR,
        evidence=f"built from {len(docs)} governed document(s) into {_OUT_DIR}",
    )
