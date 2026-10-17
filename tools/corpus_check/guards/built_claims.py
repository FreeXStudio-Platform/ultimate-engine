"""``built-claims`` — a documented command must actually be runnable.

The doctrine's rule is *"anything marked **built** whose only definition is under a test guard, or
whose branch ends in an unconditional error, fails"*. In this corpus the shape that class actually
takes is the **documented invocation**, and it has already cost a real defect: `OG-58` records two
documents — one of which authoring agents are told to copy *verbatim* — teaching a build command
whose first line fails, with every gate green.

Three things are resolved, all against real source read off disk:

1. ``python3 -m tools.<pkg>`` — the module or package must be tracked content.
2. the **subcommand** after it — must appear as an ``add_parser("<name>")`` in that package.
3. every ``--flag`` on the same command — must appear as an ``add_argument`` option in that package.

Plus ``npm run <script>`` against the ``scripts`` of a tracked ``package.json``.

**This guard reads fenced code blocks, unlike every other prose guard, and that is the point.**
`docs/plan/START_NEXT_SESSION.md`'s launch command is inside a ```` ```bash ```` fence and is *the
single most-executed line in the repository* — `CONS-08` says so in its own source, having been
corrected once for being unable to see it. A guard over documented commands that skipped fences
would be blind to every command anybody actually runs.

The cost of that choice is stated rather than hidden: a fence deliberately showing a *broken*
command as an example would be flagged. Nothing in this corpus does, and if something ever needs to,
the honest fix is to mark it — not to make the guard stop looking where the commands are.
"""

from __future__ import annotations

import json
import re

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import Finding, GuardResult, Severity, failed, passed
from tools.corpus_check.text import (
    is_append_only_record,
    iter_all_lines_with_headings,
    under_dated_heading,
)

GUARD = "built-claims"

# `python3 -m tools.health --full`, `python -m tools.docgen.cli build x.md`. The tail is captured up
# to a shell metacharacter so a pipeline or a `&&` chain does not drag the next command's flags in.
_PY_MODULE_RE = re.compile(
    r"python3?\s+-m\s+([a-z_][a-z0-9_.]*)((?:\s+[^\s|&;<>`\"']+)*)"
)

# `python3 <path>/<script>.py FILE.md` — the SCRIPT-PATH invocation form, as opposed to the
# `-m module` form above. Added after deleting a legacy renderer left three documented invocations
# of it standing: the guard covered `python3 -m X` and was blind to `python3 X.py`, which is the
# same claim in the other spelling. A guard that covers one spelling of a class covers the class
# only by luck (`docs/process/RULES.md` Rule 1: the counter-example must cover the CLASS).
_PY_SCRIPT_RE = re.compile(r"python3?\s+((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.py)\b")

# `npm run simulate`, `npm test`.
_NPM_RE = re.compile(r"npm\s+(?:run\s+([a-z0-9:_-]+)|(test))\b")

# `node <script>.mjs` — **the third spelling of "run this program", and the one nobody added**
# (`OG-143`). This guard had `python3 -m <module>`, `python3 <script>.py` and `npm run <script>`,
# and its PASS line asserts *every* documented command resolves. It could not see `node` at all,
# while the corpus documents **9 distinct** node invocations and `CAPABILITIES.json` gives a
# `node`-form entry point for most of the engines. A deleted `.mjs` left every one of them
# standing and silent — the exact defect `_PY_SCRIPT_RE`'s own evidence string describes.
_NODE_RE = re.compile(r"\bnode\s+((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:mjs|js|cjs))\b")

_FLAG_RE = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")

# HTML tags, stripped so a command inside `<code>` reads as the instruction it is.
#
# ⚠ **`[^>]` MATCHES NEWLINES, AND EVERY FINDING IN AN HTML FILE PAID FOR IT** (`OG-108`).
# Written `<[^>]+>` and replaced by a single space, a tag could swallow arbitrarily many lines —
# a `<![CDATA[ … ]]>` block in `examples/capability-gallery.html` spanned **33** — so the line
# numbers the scanner produced were the STRIPPED text's, not the file's. Measured: that file went
# 1095 lines to 993, and a command planted at real line 1001 was reported at line 908, which holds
# an unrelated SVG element. A finding that cites the wrong line is worse than none — the reader
# goes there, sees nothing wrong, and stops trusting the guard.
#
# Second half of the same defect: a bare `<` in text content (`a < b`, `List<T>`) began a match
# that ran to the next `>` anywhere in the file, DELETING everything between. A probe lost an
# `npm run …` line that way entirely.
#
# `[^>\n]` confines a tag to one line, and the replacement is now an equal-length run of spaces,
# so line numbers AND columns survive the strip exactly.
_TAG_RE = re.compile(r"<[^>\n]*>")

# **Exact files, not path segments** (`P8-077`). A command quoted in a third-party catalogue is a
# record of what SOMEONE ELSE runs — `_EXTERNAL_REF_RE` catches the prose form (a URL, a
# `host.tld/owner/repo`), but `SOURCE_REGISTRY.json` attributes with a BARE `owner/repo:` on the
# same line as the command, with no domain for that pattern to match, so it needs a scope
# declared some other way. A whole DIRECTORY was that scope (`/knowledge/`, `/evidence/`) —
# but `tools/visual-engine/evidence/release/acceptance-simulations.json` lives in that same
# directory and documents OUR OWN `npm run simulate`, not a third party's. Measured: rewriting its
# `"run"` field to name a script no `package.json` defines still passed clean — 22 other tracked
# files under the same two directories were blinded for the one file that actually needed the
# exemption. The exact file, not the directory, is the scope: only `SOURCE_REGISTRY.json` mixes a
# third-party attribution and a command on one line with no URL to mark it.
_THIRD_PARTY_RECORDS = ("tools/visual-engine/knowledge/SOURCE_REGISTRY.json",)

# A line naming an external project: a URL, or a bare `host.tld/owner/repo`. (This comment was
# separated from its constant when `_TAG_RE` was inserted between them, so it read as
# documentation for the tag pattern and `_EXTERNAL_REF_RE` was left with none.)
_EXTERNAL_REF_RE = re.compile(
    r"https?://"
    r"|\b[a-z0-9-]+\.(?:com|org|dev|io|net)/[A-Za-z0-9_.-]+/"
    # An explicit attribution: the line says the command belongs to something else. Structured
    # records carry this instead of a URL — `"run method is npm run dev (not a published package)"`.
    r"|not a published package|third-party|upstream project|owning a fork"
)

# Flags argparse defines for every parser without being told to.
_ARGPARSE_BUILTINS = frozenset({"--help"})

# **Raised 3 -> 40, `P8-054`.** 3 was 0.7% of this guard's own measured live coverage (~420+
# documented commands) — the same order of magnitude `symbols` and `cross-doc` were pinned at,
# and none of the three had ever been revisited since. 40 leaves comfortable room below the live
# count for legitimate corpus edits while being materially above the level the finding measured.
_FLOOR = 40


def _package_dir(corpus: Corpus, module: str) -> str | None:
    """The tracked directory (or file) a dotted module path names, or ``None``."""
    base = module.replace(".", "/")
    for candidate in (base, f"{base}.py", f"{base}/__init__.py"):
        if corpus.resolves(candidate):
            return base if candidate == base else candidate
    return None


def _package_source(corpus: Corpus, module: str) -> str:
    """The source that defines this module's own parser.

    **A MODULE gets its own file; a PACKAGE gets its whole tree.** The distinction is not
    cosmetic. `tools.docgen.i18n` is a single module with its own tiny argument handling, and
    reading its *parent package* pulled in `cli.py`'s six ``add_parser`` calls — so the documented
    ``python3 -m tools.docgen.i18n en`` was reported, at HIGH, as "no such subcommand", listing
    `cli.py`'s subcommands as the evidence. A module is not answerable for its siblings' parsers.

    A package still gets its whole tree, because `tools.health` genuinely defines its arguments in
    `run.py` rather than in `__main__.py`.
    """
    base = module.replace(".", "/")
    if corpus.resolves(f"{base}.py"):
        return corpus.text(f"{base}.py")
    return "\n".join(
        corpus.text(rel) for rel in corpus.python_files if rel.startswith(f"{base}/")
    )


def run(corpus: Corpus) -> GuardResult:
    """Resolve every documented command, subcommand and flag against its own parser source."""
    roots = {rel.split("/", 1)[0] for rel in corpus.tracked if "/" in rel}
    npm_scripts: set[str] = set()
    for rel in corpus.tracked:
        if not rel.endswith("package.json") or "node_modules" in rel:
            continue
        try:
            data = json.loads(corpus.text(rel))
        except ValueError:
            continue
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            npm_scripts.update(scripts)

    findings: list[Finding] = []
    checked = 0

    # **Markdown AND tracked built output.** `OG-91`: seven instructions for the deleted `build.py`
    # survived in `tools/docgen/demo/*.html` — tracked, rendered, and invisible to a guard that read
    # `.md` only. That is `DOC_WRITING_DOCTRINE.md` §8.4 ("grep the outputs, not just the source")
    # applied to commands rather than to markup, and it is the same asymmetry `L-21` names: the
    # source was clean and the artifact was not.
    #
    # HTML is stripped to text first, so a command inside `<code>` is read exactly as one in a
    # fence: it is still an instruction a reader will type.
    # **Every tracked text surface a human reads a command from**, not just Markdown.
    # `OG-91` widened `.md` to `.md`+`.html`; Pass 7 then planted the identical broken command in
    # `CAPABILITIES.json`, `tools/hooks/install.sh` and `tools/health/run.py` and watched all three
    # escape — and `CAPABILITIES.json` carries live commands today (`OG-97`). The hole had moved
    # one extension over, which is `LESSONS.md` L-26 exactly.
    scanned: list[tuple[str, str, bool]] = [
        (rel, corpus.text(rel), True) for rel in corpus.markdown
    ]
    scanned += [
        # HTML is tag-stripped so a command inside `<code>` reads as the instruction it is — but its
        # heading stack is NOT derived, because a Markdown ATX scanner over stripped HTML lets a
        # `# comment` inside a rendered `<pre>` forge a heading and exempt the rest of the file.
        (rel, _TAG_RE.sub(lambda m: " " * len(m.group(0)), corpus.text(rel)), False)
        for rel in corpus.tracked
        if rel.endswith((".html", ".htm")) and "node_modules" not in rel
    ]
    scanned += [
        (rel, corpus.text(rel), False)
        for rel in corpus.tracked
        if rel.endswith((".json", ".sh", ".py", ".mjs", ".yml", ".yaml", ".txt", ".cfg", ".toml"))
        and "node_modules" not in rel
        and "/tests/" not in f"/{rel}"
        and rel not in _THIRD_PARTY_RECORDS
    ]

    # `text`, not `source`: the inner loop rebinds a name for a PACKAGE's source when resolving
    # a subcommand, and it used to reuse this one — so the document's own text became
    # unreachable for the rest of that file's iteration. Benign today only because the line
    # generator captured the original binding before the rebind; a reader adding one more
    # read of it would get a package's source where they asked for a document's.
    for rel, text, use_headings in scanned:
        # `OG-140` — record-ness is DECLARED, not inferred from a date in a heading.
        doc_is_record = is_append_only_record(text)
        # Fences included, deliberately — see the module docstring — but a dated record is not an
        # instruction. `VERIFICATION_LOG.md` quotes the very commands a pass found broken, and
        # `CHANGELOG.md` names the module a release deleted; flagging those reports the append-only
        # histories for accurately recording what went wrong.
        for line_no, line, headings in iter_all_lines_with_headings(text):
            if use_headings and doc_is_record and under_dated_heading(headings):
                continue
            # A command attributed to ANOTHER project is not a claim about this one. The research
            # notes under `tools/visual-engine/evidence/` catalogue third-party packages and quote
            # their invocations — "github.com/apache/echarts-mcp → … `npm run dev` runner" — and
            # judging those against our own package.json is confidently answering the wrong
            # question. A URL or a `owner/repo` on the line is the marker.
            #
            # **Applied before ALL FOUR command families, not just the last three** (`P8-052`).
            # This `continue` used to sit between the `python3 -m` loop and the other three, so a
            # line naming all four families plus one URL had its `python3 -m` finding fire while
            # the identical bogus `python3 <script>.py` and `npm run …` commands on the SAME line,
            # under the SAME external attribution, were silently suppressed. A URL on the line
            # means the whole line is someone else's command, not three-quarters of it.
            if _EXTERNAL_REF_RE.search(line):
                continue
            for match in _PY_MODULE_RE.finditer(line):
                module, tail = match.group(1), match.group(2) or ""
                if module.split(".", 1)[0] not in roots:
                    continue
                checked += 1
                if _package_dir(corpus, module) is None:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"documents `python3 -m {module}`, which names no tracked module",
                            evidence="a documented command whose module does not exist fails on its "
                            "first line — OG-58's class",
                            severity=Severity.HIGH,
                        )
                    )
                    continue

                package_source = _package_source(corpus, module)
                subcommands = set(
                    re.findall(r"add_parser\(\s*[\"']([a-z0-9_-]+)[\"']", package_source)
                )
                words = [w for w in tail.split() if not w.startswith("-")]
                if words and subcommands:
                    sub = words[0]
                    # Only judge a token that LOOKS like a subcommand: a bare word, no path
                    # separator, no extension. `build tools/docgen/sample.md` has one of each.
                    if re.fullmatch(r"[a-z][a-z0-9_-]*", sub):
                        checked += 1
                        if sub not in subcommands:
                            findings.append(
                                Finding(
                                    guard=GUARD,
                                    path=rel,
                                    line=line_no,
                                    message=f"documents `{module} {sub}`, but that package defines "
                                    "no such subcommand",
                                    evidence=f"defined: {', '.join(sorted(subcommands))}",
                                    severity=Severity.HIGH,
                                )
                            )

                known_flags = set(re.findall(r"[\"'](--[a-z][a-z0-9-]*)[\"']", package_source))
                if not known_flags:
                    continue  # no parser found in this package — nothing certain to say about flags
                for flag in _FLAG_RE.findall(tail):
                    if flag in _ARGPARSE_BUILTINS:
                        continue
                    checked += 1
                    if flag not in known_flags:
                        findings.append(
                            Finding(
                                guard=GUARD,
                                path=rel,
                                line=line_no,
                                message=f"documents `{module} … {flag}`, which that package's "
                                "parser does not define",
                                evidence=f"a documented flag argparse will reject with exit 2. "
                                f"Defined: {', '.join(sorted(known_flags)[:12])}",
                                severity=Severity.HIGH,
                            )
                        )

            for match in _PY_SCRIPT_RE.finditer(line):
                script = match.group(1)
                if script.split("/", 1)[0] not in roots:
                    continue
                checked += 1
                if not corpus.resolves(script):
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"documents `python3 {script}`, which names no tracked script",
                            evidence="the script-path spelling of the same claim `python3 -m …` "
                            "makes; a deleted module leaves these standing and silent",
                            severity=Severity.HIGH,
                        )
                    )

            for match in _NODE_RE.finditer(line):
                script = match.group(1)
                checked += 1
                # A node invocation is written either repo-relative (`node tools/graphify/build.mjs`)
                # or relative to the package it lives in (`node render.mjs`, from inside
                # `tools/mermaid-engine/`). Both are legitimate documentation, so both resolve:
                # exact tracked path, the citing document's own directory, or any tracked file whose
                # path ends with it. The last is deliberately generous — this guard's job is to
                # catch a script that exists NOWHERE, not to police which directory you are in.
                doc_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
                candidates = {script, f"{doc_dir}/{script}" if doc_dir else script}
                resolved = any(corpus.resolves(c) for c in candidates) or any(
                    t.endswith("/" + script) for t in corpus.tracked
                )
                if not resolved:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"documents `node {script}`, which names no tracked script",
                            evidence="the third spelling of a documented command; this guard read "
                            "`python3 -m`, `python3 <script>.py` and `npm run` and was blind to "
                            "`node` while asserting every documented command resolves (OG-143)",
                            severity=Severity.HIGH,
                        )
                    )

            for match in _NPM_RE.finditer(line):
                script = match.group(1) or match.group(2)
                if not script or not npm_scripts:
                    continue
                checked += 1
                if script not in npm_scripts:
                    findings.append(
                        Finding(
                            guard=GUARD,
                            path=rel,
                            line=line_no,
                            message=f"documents `npm run {script}`, which no tracked package.json "
                            "defines",
                            evidence=f"defined across the tracked packages: "
                            f"{', '.join(sorted(npm_scripts))}",
                            severity=Severity.MEDIUM,
                        )
                    )

    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    return passed(
        GUARD,
        f"{GUARD}: all {checked} documented command(s), subcommand(s) and flag(s) resolve to a "
        "real parser",
        checked=checked,
        floor=_FLOOR,
        evidence=f"npm scripts available: {', '.join(sorted(npm_scripts)) or 'none'}",
    )
