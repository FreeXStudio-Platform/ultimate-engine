"""The leak-gate library — doc-system export sanitizer.

Implements CLASSIFICATION.md's "leak-gate" spec (RULEBOOK L4/L6/L14/L18, precedence L1) as a
set of defense-in-depth gates over a document's rendered text. Every gate **fails closed**: a
missing input (sibling text, manifest row, taxonomy entry) is treated as a BLOCKING finding,
never silently skipped. See ENGINE_PLAN.md §1 + §4b for the exact contract this module
implements.

**How many gates there are is not written down here** (`P8-116`). This docstring said "9
defense-in-depth gates" while the one at ``run_gates`` said "across all 7 gates", in the same
file, and neither number was derived from anything — ``run_gates`` calls exactly the gate
functions in its own ``results`` list, and ``PRECEDENCE`` below carries every gate label the
package can emit, including the ones emitted outside this module. Read those two, never a
sentence. A count restated in prose is stale the day a gate is added (docs/process/RULES.md
Rule 2: a document never restates a fact that code owns).

Public entry point: ``run_gates()``. It runs all gates and returns one merged ``GateResult``.
Findings are then orderable by security precedence via ``adjudicate()``.

Fail-mode summary (repeated per-gate in each function's docstring):
    - Gate 1 (tier)              -> missing/non-public tier BLOCKS.
    - Gate 3 (secret value)       -> any match BLOCKS.
    - Gate 3b (PII/path/internal) -> any match BLOCKS.
    - Gate 4 (detector-internal)  -> ADVISORY (non-blocking) unless ``strict=True``.
    - Gate 5 (header<->registry)  -> mismatch or missing manifest row BLOCKS.
    - Gate 10 (WCAG-AA contrast)  -> a below-AA (or unparseable) colour pair BLOCKS (fail-closed).
    - Gate 9 (variant overlap)    -> overlap BLOCKS; a missing/None sibling ALSO BLOCKS (fail-closed).

Stdlib only. mypy --strict clean.
"""

from __future__ import annotations

import base64
import binascii
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from tools.docgen.components import contrast_ratio, wcag_aa_ok
from tools.docgen.models import (
    DocHeader,
    Finding,
    GateResult,
    ManifestRow,
    Severity,
    Tier,
)

# --------------------------------------------------------------------------------------
# L1 — Precedence spine: security > source-of-truth > registries > execution-state >
#      visual rules > automation contracts > exports > changelog (RULEBOOK L1).
# Gate names below are ordered to match that spine so ``adjudicate()`` can sort on it.
# --------------------------------------------------------------------------------------
PRECEDENCE: tuple[str, ...] = (
    # Added 2026-08-20: both were absent, so their BLOCKING findings sorted BELOW advisory ones
    # (an unlisted gate ranks last). An undeclared locked-rule edit outranks any single document's
    # problem — it means the rules themselves are untrustworthy — so hash_gate leads the spine.
    "hash_gate",  # RULEBOOK L9 — source-of-truth integrity: the rules themselves
    "header",     # RULEBOOK L5/L2 — the document's own identity must parse before anything else
    # Emitted since Phase 4 and unranked until 2026-08-24 (`OG-195`), because it is written as
    # `gate=GATE` against a module constant and every scan here looked for a string literal or a
    # constant spelled `_GATE`. It sits beside `header` because it asks the same kind of question:
    # what does this document claim about itself, and does the claim hold.
    "identity",
    "tier",  # Gate 1 — security: classification boundary
    # Added 2026-08-20: emitted by tools/docgen/hooks/staged_content_scanner.py, the commit-time
    # L14 placement gate, and absent from this tuple since it was written — so its findings, which
    # are the last line before a classified document enters history, ranked below every advisory.
    "staged-content-scanner",  # RULEBOOK L14 — commit-time classification placement
    "secret_value",  # Gate 3 — security: literal secret material
    "pii_path_internal",  # Gate 3b — security: PII / internal paths / hostnames
    "variant_overlap",  # Gate 9 — security: the moat (cross-tier leakage)
    # Added with the audience/level view generator. It sits directly below gate 9 because it is
    # the pipeline built ON gate 9: its blocking finding means a generated audience view
    # could not be produced safely (e.g. it could not be registered as derived), so the
    # view was not written. Absent from this tuple, its blocking findings would have
    # sorted BELOW advisory ones, since an unlisted gate ranks last.
    "audience_views",  # derived audience/level views
    "manifest_drift",  # Gate 5 — registries: header<->DOC_MANIFEST agreement
    "wcag_contrast",  # Gate 10 — visual rules: WCAG-AA text legibility (DESIGN_SYSTEM §7)
    "figure_provenance",  # L16 — visual rules: every rendered number names its source (`OG-63`)
    # --- the figure gates, made visible 2026-08-24 (`OG-191`) -------------------------------
    #
    # These sixteen were emitted by real code paths from the day each renderer landed and were
    # absent from this tuple the whole time, because CONS-04's label scan could not match a name
    # containing a dot. They rank HERE, in visual-rules, because that is what they are: rules
    # about what a figure may render. Before this they ranked nowhere, which `_precedence_rank`
    # scores below every advisory — so a blocking "this figure has no data source" finding sorted
    # under a LOW note about a paraphrase.
    #
    # Ordered `.source`, then `.rule`, then `.collision`: provenance outranks well-formedness,
    # which outranks legibility, because that is the order in which a reader can act on them —
    # an unsourced number is a truth problem, a malformed spec is a correctness problem, and a
    # label collision is a presentation problem.
    "geomap.source",
    "choropleth.source",
    "chart.rule",
    "geomap.rule",
    "choropleth.rule",
    "iso3d.rule",
    "iso3d.bounds",
    "layered.rule",
    "sankey.rule",
    "sequence.rule",
    "chart.collision",
    "geomap.collision",
    "iso3d.collision",
    "layered.collision",
    "sankey.collision",
    "sequence.collision",
    "visual.collision",
    "detector_internal",  # Gate 4 — advisory net (paraphrase-fragile, not sole moat)
    # Added 2026-08-20. These labels are emitted by real code paths and were absent from this
    # tuple, so `_precedence_rank` returned `len(PRECEDENCE)` for each — ranking them BELOW every
    # advisory. `gate="build"` in particular is emitted blocking with severity HIGH ("unknown
    # format requested"), and because rank is the PRIMARY sort key and `blocking` only the
    # tie-break WITHIN a gate, a blocking build failure sorted underneath a non-blocking LOW
    # advisory. They sit here, below the content gates, because a content finding tells you what
    # to FIX whereas these tell you the run did not complete — but any position is better than
    # "unlisted", which is what they had.
    "l10_impact",  # RULEBOOK L10 — blast-radius advisory
    "l11_contradiction",  # RULEBOOK L11 — tie-breaker advisory
    "ci_cost_control",  # portfolio CI policy advisory
    "build",  # the build itself could not complete
    "build-cache",  # a cached build path could not produce a trustworthy artifact
    "pdf",  # the PDF export path failed
    "run_gates",  # the gate RUNNER's own container result
)

# Gates that legitimately have no L11 contradiction mapping. An L11 row breaks a tie between two
# RULES; these report that machinery FAILED (or are themselves the L10/L11 advisories), so demanding
# a tie-breaker row for them would mean inventing rows that can never fire — which is the defect
# LESSONS.md L-03 warns about, not a fix for it.
NO_CONTRADICTION_MAPPING: frozenset[str] = frozenset({
    "l10_impact", "l11_contradiction", "ci_cost_control",
    "build", "build-cache", "pdf", "run_gates",
    # --- the well-formedness gates (`OG-191`, classified 2026-08-24 from their own messages) ---
    #
    # An L11 row breaks a tie between two RULES. Read what these actually emit — *"bar chart has
    # no items"*, *"point 'x' lon=999 outside [-180, 180]"*, *"matrix shape must be 3x4 to match
    # row/col labels"*, *"connector references unknown src"* — and there is no tie to break: the
    # spec is malformed or out of range, and no second law wants it accepted. Inventing a
    # contradiction row for them would mean writing rows that can never fire, which is the defect
    # `LESSONS.md` L-03 warns about rather than a fix for it.
    #
    # Their siblings are NOT here and that distinction is the point: `.source` maps to `l16` (row
    # 8 — an unsourced number IS a real tie between completeness and provenance) and `.collision`
    # maps to `l21` (row 9 — expressiveness against legibility). Three suffixes, three different
    # answers, each from the messages the gate emits.
    # **Three gates moved OUT of this set on 2026-08-24** (`OG-195`): an independent verifier of
    # `OG-191`'s closure read their messages and found the suffix-based classification too coarse.
    # `chart.rule`, `iso3d.rule` and `layered.rule` each ALSO emit a legibility cap — *"pie has N
    # slices, exceeds the 6-slice VISUAL_LIBRARY cap"*, `_MAX_BOXES = 24  # legibility cap`,
    # `_MAX_LAYERS = 4`. That is exactly the expressiveness-versus-legibility tie used to justify
    # mapping the `.collision` gates to row 9, so exempting these contradicted the reasoning
    # written beside them. They are mapped now. **Stated bound:** a gate maps as a whole, so a
    # malformed-spec message from one of them also receives row 9's advisory — the same
    # over-attachment this file already acknowledges for rows 2 and 6 both citing `L4`.
    "geomap.rule", "choropleth.rule", "iso3d.bounds", "sankey.rule", "sequence.rule",
})


# --------------------------------------------------------------------------------------
# L1 — the spine ITSELF, as data, so the ORDER above is checkable rather than merely commented.
#
# `P8-088`: the comment above ``PRECEDENCE`` says the gate names "are ordered to match that
# spine", and nothing anywhere checked that they were. CONS-04 (``tools/health`` gate-token
# coverage) checks MEMBERSHIP and MAPPING only — every emitted label has *a* position, every rule
# gate is mapped — so moving ``"tier"`` (Gate 1, the classification boundary that decides what may
# leave the vault) from position 3 to the END of the tuple, below ``build``/``pdf``/``run_gates``,
# left CONS-04 reporting PASS. A blocking tier violation would then have sorted underneath every
# advisory in the triage list that humans actually read top-down.
#
# So the spine is declared as ordered CLASSES here, each gate belongs to exactly one, and
# ``check_precedence_spine`` asserts the classes appear in this order along ``PRECEDENCE``.
# Membership is asserted in BOTH directions: a gate missing from ``PRECEDENCE`` is a violation
# too, because ``_precedence_rank`` returns ``len(PRECEDENCE)`` for an unlisted gate — deleting
# ``"tier"`` demotes it exactly as far as moving it to the end does, and is the wider input.
# --------------------------------------------------------------------------------------
SPINE_CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    ("source-of-truth", frozenset({"hash_gate", "header", "identity"})),
    ("security", frozenset({
        "tier", "staged-content-scanner", "secret_value", "pii_path_internal", "variant_overlap",
        # The generated audience/level views. A SECURITY class, not a run-state
        # one: a generated view IS a tier boundary, and this gate's blocking finding means one
        # could not be produced safely — the same concern as variant_overlap, which it sits
        # directly below in PRECEDENCE.
        "audience_views",
    })),
    ("registries", frozenset({"manifest_drift"})),
    ("visual-rules", frozenset({
        "wcag_contrast", "figure_provenance",
        # The seventeen figure gates (`OG-191`, plus `identity` found by `OG-195`). Derive, do not
# count by eye: `len([g for g in PRECEDENCE if '.' in g])`. All one class: each is a rule about what a figure
        # may render, and none of them is a security or registry concern.
        "geomap.source", "choropleth.source",
        "chart.rule", "geomap.rule", "choropleth.rule", "iso3d.rule", "iso3d.bounds",
        "layered.rule", "sankey.rule", "sequence.rule",
        "chart.collision", "geomap.collision", "iso3d.collision", "layered.collision",
        "sankey.collision", "sequence.collision", "visual.collision",
    })),
    ("advisory", frozenset({
        "detector_internal", "l10_impact", "l11_contradiction", "ci_cost_control",
    })),
    ("run-state", frozenset({"build", "build-cache", "pdf", "run_gates"})),
)


def _spine_class_index(gate: str) -> int | None:
    for idx, (_name, members) in enumerate(SPINE_CLASSES):
        if gate in members:
            return idx
    return None


def check_precedence_spine(precedence: tuple[str, ...] = ()) -> list[str]:
    """Return the L1 spine violations in ``precedence`` (empty list == the spine holds).

    Pass nothing to check the live ``PRECEDENCE``. Three violation classes, all of which
    demote a security gate below an advisory one in ``adjudicate()``:

    * a gate that ``SPINE_CLASSES`` declares but ``precedence`` omits (an unlisted gate ranks
      ``len(precedence)`` — i.e. last, below every advisory);
    * a gate listed in ``precedence`` that no class claims (its position is unreviewable);
    * a pair out of class order — e.g. ``"tier"`` appearing after ``"build"``.
    """
    listed = precedence or PRECEDENCE
    problems: list[str] = []

    for name, members in SPINE_CLASSES:
        for gate in sorted(members - set(listed)):
            problems.append(
                f"{gate!r} ({name}) is absent from PRECEDENCE, so it ranks LAST — below every "
                "advisory gate"
            )
    for gate in listed:
        if _spine_class_index(gate) is None:
            problems.append(
                f"{gate!r} is in PRECEDENCE but belongs to no SPINE_CLASSES class, so its "
                "position against the L1 spine cannot be checked"
            )

    ranked = [(g, _spine_class_index(g)) for g in listed]
    highest_seen = -1
    highest_gate = ""
    for gate, cls in ranked:
        if cls is None:
            continue
        if cls < highest_seen:
            problems.append(
                f"{gate!r} ({SPINE_CLASSES[cls][0]}) is listed AFTER {highest_gate!r} "
                f"({SPINE_CLASSES[highest_seen][0]}), inverting the RULEBOOK L1 spine"
            )
        else:
            highest_seen, highest_gate = cls, gate
    return problems


_SPINE_VIOLATIONS = check_precedence_spine()
if _SPINE_VIOLATIONS:  # pragma: no cover - the module refuses to load on a broken spine
    raise RuntimeError(
        "export_sanitizer.PRECEDENCE violates the RULEBOOK L1 security spine and would sort "
        "blocking security findings below advisories: " + "; ".join(_SPINE_VIOLATIONS)
    )


def _precedence_rank(gate: str) -> int:
    """Unknown gate names sort last (never crash on an unexpected gate label)."""
    try:
        return PRECEDENCE.index(gate)
    except ValueError:
        return len(PRECEDENCE)


def adjudicate(findings: list[Finding]) -> list[Finding]:
    """Order findings by the L1 precedence spine (security-relevant gates first).

    Stable sort: within the same gate, original order is preserved. Never drops or
    mutates a finding — purely a presentation/triage ordering.
    """
    return sorted(findings, key=lambda f: (_precedence_rank(f.gate), not f.blocking))


# --------------------------------------------------------------------------------------
# Normalization (run before every scan) — CLASSIFICATION.md leak-gate step 3 note + §4b.1
# --------------------------------------------------------------------------------------

# NOTE: every codepoint below is written as a \uXXXX escape (never a literal
# invisible/bidi character in this source file) so the file itself can never be
# accused of hiding bidi/zero-width tricks — the very thing this pattern set
# scans for (formerly jury KB-004, retired 2026-07-25).
_ZERO_WIDTH_AND_CONTROL_RE = re.compile(
    "["
    "\u200b-\u200f"  # zero-width space/joiners/marks
    "\u202a-\u202e"  # bidi embedding/override
    "\u2060-\u2064"  # word joiner, invisible operators
    "\ufeff"  # BOM / zero-width no-break space
    "\x00-\x08\x0b\x0c\x0e-\x1f\x7f"  # C0 controls except \t\n\r
    "]"
)

# Long base64/hex runs worth decoding-and-rescanning. Conservative minimum lengths keep
# noise down while still catching an encoded secret (e.g. a base64'd API key or PEM).
_BASE64_RUN_RE = re.compile(r"(?:[A-Za-z0-9+/]{4}){5,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?")
_HEX_RUN_RE = re.compile(r"(?:[0-9a-fA-F]{2}){16,}")


def normalize(text: str) -> str:
    """Unicode NFKC-normalize and strip zero-width/control characters.

    Fail mode: this is a pure text transform with no external input — it cannot fail
    closed/open in the gate sense, but it MUST run before every scan below so a
    homoglyph or zero-width-space-split secret cannot dodge the patterns.
    """
    nfkc = unicodedata.normalize("NFKC", text)
    return _ZERO_WIDTH_AND_CONTROL_RE.sub("", nfkc)


def _decode_candidates(text: str) -> list[str]:
    """Best-effort base64/hex decode of long runs found in ``text``.

    Returns extra text blobs to re-scan (never raises). A run that fails to decode as
    valid base64/hex, or that doesn't decode to printable-ish text, is silently
    dropped — decoding is a widening of the scan surface, not a source of findings by
    itself, so failures here are not fail-closed (nothing security-relevant is lost:
    the ORIGINAL encoded text is still scanned by the entropy fallback in Gate 3).
    """
    decoded: list[str] = []
    for run in _BASE64_RUN_RE.findall(text):
        if len(run) < 20:
            continue
        try:
            raw = base64.b64decode(run + "=" * (-len(run) % 4), validate=False)
            candidate = raw.decode("utf-8", errors="ignore")
        except (binascii.Error, ValueError):
            continue
        if candidate and sum(c.isprintable() for c in candidate) / max(len(candidate), 1) > 0.85:
            decoded.append(candidate)
    for run in _HEX_RUN_RE.findall(text):
        if len(run) < 32:
            continue
        try:
            raw = bytes.fromhex(run)
            candidate = raw.decode("utf-8", errors="ignore")
        except (ValueError, binascii.Error):
            continue
        if candidate and sum(c.isprintable() for c in candidate) / max(len(candidate), 1) > 0.85:
            decoded.append(candidate)
    return decoded


# --------------------------------------------------------------------------------------
# Gate 3 — secret-value scan: known credential/token formats (AWS keys, API tokens,
# private-key headers, etc.) plus decoded base64/hex candidates from above
# (formerly jury KB-004 dialect, retired 2026-07-25; CLASSIFICATION.md §leak-gate.3)
# --------------------------------------------------------------------------------------

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "anthropic_key": re.compile(r"sk-(ant|proj)-[A-Za-z0-9_-]{20,}"),
    "generic_sk_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),
    "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    "dsn_with_credentials": re.compile(r"[a-z][a-z0-9+.-]*://[^:@/\s]+:[^@/\s]+@[^\s\"'<>]+"),
    "private_key_block": re.compile(
        r"-----BEGIN (RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "aws_secret_access_key": re.compile(r"aws_secret_access_key\s*=\s*\S+", re.IGNORECASE),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}

# Labeled-context allowance: known-benign hex blobs that would otherwise trip the entropy
# fallback (SHAs, Ethereum addresses) when explicitly labeled as such nearby.
_LABELED_SAFE_CONTEXT_RE = re.compile(
    r"\b(sha-?256|sha-?1|commit|hash|checksum|address|contract|txid|tx hash)\b", re.IGNORECASE
)
_HEX_BLOB_RE = re.compile(r"\b(0x)?[0-9a-fA-F]{32,64}\b")


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _entropy_fallback_findings(text: str, *, source: str) -> list[Finding]:
    """High-entropy unlabeled string fallback, with a labeled-context allowance.

    Fail mode: conservative — only flags long hex/base64-ish tokens whose local
    context does NOT carry a recognized benign label (sha/commit/address/etc). This
    keeps the entropy fallback from drowning real findings in noise while still
    catching an unlabeled high-entropy credential-shaped token.
    """
    findings: list[Finding] = []
    for match in _HEX_BLOB_RE.finditer(text):
        token = match.group(0)
        window_start = max(0, match.start() - 40)
        window_end = min(len(text), match.end() + 40)
        context = text[window_start:window_end]
        if _LABELED_SAFE_CONTEXT_RE.search(context):
            continue
        entropy = _shannon_entropy(token)
        if entropy >= 3.5 and len(token) >= 32:
            findings.append(
                Finding(
                    gate="secret_value",
                    message=(
                        f"[{source}] unlabeled high-entropy token "
                        f"(entropy={entropy:.2f}, len={len(token)}) resembles a secret"
                    ),
                    severity=Severity.HIGH,
                    blocking=True,
                    # **NEVER THE MATERIAL ITSELF** — see the note on the pattern gate below
                    # (`OG-168`). A length and an entropy score identify the token for a
                    # human without carrying any of it into an artifact.
                    evidence=f"<redacted high-entropy token, len={len(token)}, "
                             f"entropy={entropy:.2f}>",
                )
            )
    return findings


def gate_secret_value(text: str) -> GateResult:
    """Gate 3 — literal secret-value scan across normalized + decoded views.

    Fail mode: BLOCKING on any pattern hit or entropy-fallback hit, in either the raw
    normalized text OR any base64/hex-decoded sub-blob (so an encoded secret embedded
    in a data-URI/base64 string still trips the gate).
    """
    findings: list[Finding] = []
    views: list[tuple[str, str]] = [("raw", text)]
    for i, decoded in enumerate(_decode_candidates(text)):
        views.append((f"decoded#{i}", decoded))

    for source, view in views:
        for name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(view):
                findings.append(
                    Finding(
                        gate="secret_value",
                        message=f"[{source}] matched secret pattern '{name}'",
                        severity=Severity.CRIT,
                        blocking=True,
                        # ⚠ **THIS USED TO CARRY 16 CHARACTERS OF THE SECRET** (`OG-168`).
                        # `evidence=match.group(0)[:16] + "..."` put real key material into a
                        # `Finding`, and a `Finding` is not a transient: it is serialised into the
                        # JSON build artifact, printed to logs, and written into evidence files.
                        # Measured: a `ghp_` token produced `evidence='ghp_AAAAAAAAAAAA...'`, and
                        # a 16-character prefix is below every pattern's own threshold — so the
                        # leak gate's own output is a place the leak gate cannot see.
                        #
                        # The portfolio scanner already gets this right and prints
                        # `<redacted — the matched text is not printed>`. A finding needs to say
                        # WHICH pattern fired and WHERE, never WHAT matched.
                        evidence=(
                            f"<redacted — pattern '{name}' matched {len(match.group(0))} "
                            f"char(s) at offset {match.start()}; the matched text is not printed>"
                        ),
                    )
                )
        findings.extend(_entropy_fallback_findings(view, source=source))

    return GateResult(gate="secret_value", findings=findings)


# --------------------------------------------------------------------------------------
# Gate 3b — PII / internal path / hostname net (CLASSIFICATION.md L4, ENGINE_PLAN §4b.3)
# --------------------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RFC1918_RE = re.compile(
    r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|169\.254\.\d{1,3}\.\d{1,3})\b"
)
_LOOPBACK_HOST_RE = re.compile(r"\blocalhost\b", re.IGNORECASE)
_USERS_PATH_RE = re.compile(r"/Users/[^\s\"'<>)]+")
_OPT_PATH_RE = re.compile(r"/opt/[^\s\"'<>)]+")
_HOME_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/home/[A-Za-z0-9._-]+/[^\s\"'<>)]+")
_INTERNAL_HOSTNAME_RE = re.compile(
    r"\b[a-zA-Z0-9-]+\.(?:internal|corp|local|lan|intranet)\b", re.IGNORECASE
)
_STACK_TRACE_RE = re.compile(
    r"(Traceback \(most recent call last\)|^\s+File \"[^\"]+\", line \d+"
    r"|at [\w.$]+\([\w./]+:\d+\))",
    re.MULTILINE,
)


def gate_pii_path_internal(text: str) -> GateResult:
    """Gate 3b — PII / private-path / internal-hostname / stack-trace net.

    Fail mode: BLOCKING on any match. Every sub-check is its own labeled finding so a
    human reviewer sees exactly which class fired.
    """
    findings: list[Finding] = []
    checks: list[tuple[str, re.Pattern[str], Severity]] = [
        ("email", _EMAIL_RE, Severity.HIGH),
        ("rfc1918_or_loopback_ip", _RFC1918_RE, Severity.HIGH),
        ("localhost_hostname", _LOOPBACK_HOST_RE, Severity.MED),
        ("users_path", _USERS_PATH_RE, Severity.HIGH),
        ("opt_path", _OPT_PATH_RE, Severity.HIGH),
        ("home_path", _HOME_PATH_RE, Severity.HIGH),
        ("internal_hostname", _INTERNAL_HOSTNAME_RE, Severity.MED),
        ("stack_trace_or_log_dump", _STACK_TRACE_RE, Severity.HIGH),
    ]
    for name, pattern, severity in checks:
        for match in pattern.finditer(text):
            findings.append(
                Finding(
                    gate="pii_path_internal",
                    message=f"matched PII/internal net '{name}'",
                    severity=severity,
                    blocking=True,
                    evidence=match.group(0)[:60],
                )
            )
    return GateResult(gate="pii_path_internal", findings=findings)


# --------------------------------------------------------------------------------------
# Gate 4 — detector-internal semantic net (ADVISORY — CLASSIFICATION.md §leak-gate.4,
# ENGINE_PLAN §4b.4). This is paraphrase-fragile and is explicitly NOT the sole moat:
# Gate 9 (variant non-overlap) is the structural backstop. This gate is a tripwire for
# human review, not a hard block, unless --strict is requested.
# --------------------------------------------------------------------------------------

_ANALYZER_NAMES = r"(?:slither|mythril|semgrep|mythx|securify|manticore|echidna|foundry|oyente)"
DETECTOR_INTERNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "threshold_weight_confidence_near_number": re.compile(
        r"\b(threshold|weight|confidence|cutoff|signal)\b(?:\W+\w+){0,6}?\W+\d+(\.\d+)?%?"
        r"|\d+(\.\d+)?%?(?:\W+\w+){0,6}?\W+\b(threshold|weight|confidence|cutoff|signal)\b",
        re.IGNORECASE,
    ),
    "bypass_evade_near_analyzer": re.compile(
        rf"\b(bypass|evade|defeat|circumvent)\b(?:\W+\w+){{0,8}}?\W+{_ANALYZER_NAMES}"
        rf"|{_ANALYZER_NAMES}(?:\W+\w+){{0,8}}?\W+\b(bypass|evade|defeat|circumvent)\b",
        re.IGNORECASE,
    ),
    "feature_name_near_detector_term": re.compile(
        r"\bfeature[_ ]?(name|vector|set)\b(?:\W+\w+){0,6}?\W+\b(detector|classifier|model)\b",
        re.IGNORECASE,
    ),
}


_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
# `font-weight` (CSS property in the embedded ``@font-face``/type-scale stylesheet, or an
# inline SVG/HTML attribute emitted by every figure renderer — visual.py, charts.py,
# sequence_diagram.py, layered_workflow.py) is rendering boilerplate, never document
# content. Neutralize both forms before the scan below.
_FONT_WEIGHT_RE = re.compile(r"font-weight\s*[:=]\s*[\"']?\d+(\.\d+)?[\"']?", re.IGNORECASE)


def gate_detector_internal(text: str, *, strict: bool = False) -> GateResult:
    """Gate 4 — detector-internal net. ADVISORY unless ``strict`` is set.

    Fail mode: non-blocking by default (a `Finding` is still emitted and flagged for
    human review, per ENGINE_PLAN §4b.4: "paraphrase-fragile... not the sole moat").
    When ``strict=True`` (the pre-push / CI posture, CLASSIFICATION gate 7) every hit
    becomes blocking.

    ``run_gates`` calls this against the FINAL RENDERED HTML, which embeds the same
    boilerplate ``<style>`` block (vendored ``@font-face`` rules, e.g. ``font-weight:
    300``) and inline SVG ``font-weight="700"`` attributes on every single document.
    ``threshold_weight_confidence_near_number`` reads "weight" near a number regardless
    of source, so that CSS/SVG boilerplate trips it on every build — in ``strict`` mode
    that would make every document unconditionally fail, permanently, independent of its
    actual content. Neither form is ever document content, so both are excluded from the
    scan here (not from the other gates, which don't share this false-positive class).
    """
    scan_text = _FONT_WEIGHT_RE.sub("", _STYLE_BLOCK_RE.sub("", text))
    findings: list[Finding] = []
    for name, pattern in DETECTOR_INTERNAL_PATTERNS.items():
        for match in pattern.finditer(scan_text):
            findings.append(
                Finding(
                    gate="detector_internal",
                    message=(
                        f"possible detector-internal disclosure: '{name}' "
                        "(advisory — paraphrase-fragile, review manually)"
                    ),
                    severity=Severity.MED,
                    blocking=strict,
                    evidence=match.group(0)[:80],
                )
            )
    return GateResult(gate="detector_internal", findings=findings)


# --------------------------------------------------------------------------------------
# Gate 1 — tier gate (hard). Only Tier.PUBLIC is export-eligible.
# --------------------------------------------------------------------------------------


def gate_tier(header: DocHeader, *, local_preview: bool = False) -> GateResult:
    """Gate 1 — only `classification: public` is eligible for any EXPORT path.

    Fail mode: BLOCKING whenever ``header.classification`` is not ``Tier.PUBLIC``, or
    when the ``export_allowed``/``surface`` fields disagree with a public tier (a
    prose/typo value is never trusted — the enum-typed ``Tier`` already guarantees a
    real boolean/enum, so a disagreement here is a genuine header defect, not a parse
    failure elsewhere).

    ``local_preview=True`` downgrades a non-public classification to a non-blocking INFO
    finding — CONFIDENTIAL/SECRET docs still need a *local, git-ignored* rendered preview
    for internal/NDA'd-partner review (RULEBOOK L3/DETECTOR_DOC_SPEC §4 — "never leaves
    local", not "never rendered"). This is NOT a general export bypass: the caller
    (``generator.build``) must independently confine the write path to ``docs/confidential/``
    before honoring this flag — this gate has no path awareness and cannot enforce that
    itself. Every other gate (secret-value, PII/path, variant-overlap) still runs and still
    blocks normally; only the tier-mismatch itself stops being fatal.
    """
    findings: list[Finding] = []
    if header.classification is not Tier.PUBLIC:
        if local_preview:
            findings.append(
                Finding(
                    gate="tier",
                    message=(
                        f"document classification is '{header.classification.value}' — "
                        "local-preview mode, never exported, caller must confine to a "
                        "git-ignored confidential path"
                    ),
                    severity=Severity.INFO,
                    blocking=False,
                    evidence=header.id,
                )
            )
            return GateResult(gate="tier", findings=findings)
        findings.append(
            Finding(
                gate="tier",
                message=(
                    f"document classification is '{header.classification.value}', "
                    "not 'public' — not export-eligible"
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=header.id,
            )
        )
        return GateResult(gate="tier", findings=findings)

    if not header.export_allowed:
        findings.append(
            Finding(
                gate="tier",
                message="classification is public but export_allowed is False",
                severity=Severity.HIGH,
                blocking=True,
                evidence=header.id,
            )
        )
    if header.surface.value not in ("web", "repo", "both"):
        findings.append(
            Finding(
                gate="tier",
                message=f"public document has invalid surface '{header.surface.value}'",
                severity=Severity.HIGH,
                blocking=True,
                evidence=header.id,
            )
        )
    return GateResult(gate="tier", findings=findings)


# --------------------------------------------------------------------------------------
# Gate 5 — header <-> DOC_MANIFEST registry drift (RULEBOOK L5, CLASSIFICATION header rules)
# --------------------------------------------------------------------------------------


def _try_import_check_manifest_drift() -> (
    Callable[[DocHeader, list[ManifestRow]], list[Finding]] | None
):
    """Return ``classification.check_manifest_drift`` if that module (B1's output) is
    importable and exposes the function; otherwise None so the caller falls back to a
    local re-implementation.

    Never raises — an ImportError/AttributeError simply means B1 hasn't landed yet or
    doesn't expose that name, which is tolerated during parallel builds. The real
    signature (as landed) is ``check_manifest_drift(h: DocHeader, manifest_rows:
    list[ManifestRow]) -> list[Finding]`` — note it returns a list of Finding, not a
    GateResult, and requires a real (non-None) list, so the None/empty fail-closed
    check below MUST run before delegating.
    """
    try:
        from tools.docgen import classification as classification_module
    except ImportError:
        return None
    fn = getattr(classification_module, "check_manifest_drift", None)
    if fn is None:
        return None
    return cast("Callable[[DocHeader, list[ManifestRow]], list[Finding]]", fn)


def gate_manifest_drift(header: DocHeader, manifest_rows: list[ManifestRow] | None) -> GateResult:
    """Gate 5 — header tier must agree with its DOC_MANIFEST row (no drift).

    Fail mode: BLOCKING when ``manifest_rows`` is None/empty (fail-closed: we cannot
    prove agreement with a registry we cannot see), when no row matches ``header.id``
    (by exact id or by type-prefix), or when a matched row's ``variants`` does not
    include ``header.classification``. Delegates the "matched row" check to
    ``classification.check_manifest_drift`` when importable (B1's canonical
    prefix-matching implementation); otherwise re-implements an exact-id-match
    fallback locally so this module works standalone even before B1 lands.
    """
    if not manifest_rows:
        return GateResult(
            gate="manifest_drift",
            findings=[
                Finding(
                    gate="manifest_drift",
                    message=(
                        "no DOC_MANIFEST rows provided — cannot verify header<->registry "
                        "agreement (failing closed)"
                    ),
                    severity=Severity.HIGH,
                    blocking=True,
                    evidence=header.id,
                )
            ],
        )

    delegate = _try_import_check_manifest_drift()
    if delegate is not None:
        delegate_findings = delegate(header, manifest_rows)
        if isinstance(delegate_findings, list):
            return GateResult(gate="manifest_drift", findings=list(delegate_findings))

    findings: list[Finding] = []
    matches = [row for row in manifest_rows if row.id == header.id]
    if not matches:
        findings.append(
            Finding(
                gate="manifest_drift",
                message=f"document id '{header.id}' has no DOC_MANIFEST row",
                severity=Severity.HIGH,
                blocking=True,
                evidence=header.id,
            )
        )
        return GateResult(gate="manifest_drift", findings=findings)

    row = matches[0]
    if header.classification not in row.variants:
        findings.append(
            Finding(
                gate="manifest_drift",
                message=(
                    f"header classification '{header.classification.value}' not listed in "
                    f"DOC_MANIFEST row variants {[v.value for v in row.variants]} for '{header.id}'"
                ),
                severity=Severity.HIGH,
                blocking=True,
                evidence=header.id,
            )
        )
    if header.surface != row.surface:
        findings.append(
            Finding(
                gate="manifest_drift",
                message=(
                    f"header surface '{header.surface.value}' disagrees with DOC_MANIFEST "
                    f"row surface '{row.surface.value}' for '{header.id}'"
                ),
                severity=Severity.MED,
                blocking=True,
                evidence=header.id,
            )
        )
    return GateResult(gate="manifest_drift", findings=findings)


# --------------------------------------------------------------------------------------
# Gate 9 — variant non-overlap (the moat). Shingled n-gram overlap between a PUBLIC
# document and its declared CONFIDENTIAL/SECRET siblings (CLASSIFICATION §leak-gate.9).
# --------------------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "it",
        "as",
        "with",
        "at",
        "by",
        "from",
        "into",
        "over",
        "under",
        "if",
        "then",
        "else",
        "we",
        "our",
        "its",
        "their",
        "these",
        "those",
        "will",
        "can",
        "may",
    }
)

_WORD_RE = re.compile(r"[a-z0-9]+")

# Very light stemmer: strip a small set of common suffixes. Deliberately conservative
# (no external NLP dependency — stdlib only) so behavior is deterministic and testable.
_SUFFIXES = ("ational", "tional", "ing", "edly", "ed", "es", "s", "ly")


def _light_stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _normalize_for_shingle(text: str) -> list[str]:
    """Lowercase, collapse whitespace, strip stopwords, light-stem -> token list."""
    lowered = text.lower()
    tokens = _WORD_RE.findall(lowered)
    return [_light_stem(t) for t in tokens if t not in _STOPWORDS]


def _shingles(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def shingle_overlap(a: str, b: str, n: int = 8) -> list[str]:
    """Return the overlapping n-gram shingles (as space-joined strings) between ``a``
    and ``b`` after normalization (lowercase/collapse-ws/strip-stopwords/light-stem).

    Pure function, no fail-closed semantics of its own (the caller, ``gate_variant_
    overlap``, applies fail-closed policy for missing siblings).
    """
    tokens_a = _normalize_for_shingle(a)
    tokens_b = _normalize_for_shingle(b)
    shingles_a = _shingles(tokens_a, n)
    shingles_b = _shingles(tokens_b, n)
    overlap = shingles_a & shingles_b
    return [" ".join(s) for s in overlap]


def _similarity_ratio(a: str, b: str, n: int) -> float:
    """Jaccard-style similarity ratio over n-gram shingle sets. 0.0 when either side
    has fewer than ``n`` tokens (nothing to compare -> no evidence of overlap)."""
    tokens_a = _normalize_for_shingle(a)
    tokens_b = _normalize_for_shingle(b)
    shingles_a = _shingles(tokens_a, n)
    shingles_b = _shingles(tokens_b, n)
    if not shingles_a or not shingles_b:
        return 0.0
    union = shingles_a | shingles_b
    if not union:
        return 0.0
    return len(shingles_a & shingles_b) / len(union)


_SIMILARITY_RATIO_THRESHOLD = 0.15

# The smallest shingle size `_variant_overlap_against` checks (see its `for n in (8, 4)`
# loop below) -- i.e. the actual shingle FLOOR, not the `n=8` an at-a-glance read of
# `shingle_overlap`'s default would suggest (an earlier host finding). A sibling whose CONTENT token
# count (after `_normalize_for_shingle` strips stopwords) is below this floor produces
# ZERO shingles at every n this gate checks and is therefore invisible to shingle-based
# detection BY CONSTRUCTION, regardless of whether it appears verbatim in the doc under
# test -- measured: a 6-raw-word excluded block (3 content tokens) leaked with
# `gate.ok = True` and zero findings. `_exact_substring_overlap` below closes that blind
# spot for anything under this floor; lowering `n` itself was rejected (the brief: "a
# lower shingle floor... would raise false positives across the whole corpus").
_MIN_SHINGLE_N = 4

#: The floor, public, so a caller outside this module can NAME it in a message to an author
#: without re-spelling it. `views.py` needs the number in its authoring refusal.
MIN_SHINGLE_N = _MIN_SHINGLE_N

_EXACT_MATCH_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_for_exact_match(text: str) -> str:
    """Lowercase + collapse-whitespace, deliberately NOT stopword-stripped/stemmed --
    that normalization is exactly what lets a short excluded block fall below
    `_MIN_SHINGLE_N` with zero shingles in the first place. Trivial
    reformatting (extra spaces, blank lines, capitalization) still matches under this
    normalization; an independently-written phrase that merely shares a few words does
    NOT, because the caller uses this for an EXACT substring test, not a similarity
    score -- so it does not raise false positives across the corpus the way lowering the
    shingle floor globally would.
    """
    return _EXACT_MATCH_WHITESPACE_RE.sub(" ", text.strip().lower())


def below_shingle_floor(text: str) -> bool:
    """True iff *text* has too few content tokens for gate 9 to shingle it — the ONE definition.

    Two callers need this question answered: this module, to decide whether
    to fall back to the exact-substring check, and `views.build_and_gate_views`, to refuse such a
    block at authoring time. They must never disagree about where the floor is, which is exactly
    the failure an earlier host round measured (four copies of one predicate, three of them left unfixed), so the
    floor is exported rather than re-spelled — `views.py` importing `_MIN_SHINGLE_N` and
    `_normalize_for_shingle` across the module boundary would be that same second copy wearing an
    underscore.
    """
    return len(_normalize_for_shingle(text)) < _MIN_SHINGLE_N


def _exact_substring_overlap(doc_text: str, sibling_text: str) -> str | None:
    """For a sibling TOO SHORT for shingle detection (see `_MIN_SHINGLE_N`): the
    normalized sibling text if it appears verbatim (post-normalization) inside the
    normalized doc text, else None. An empty normalized sibling never matches (nothing
    to find is not evidence of a leak).
    """
    normalized_sibling = _normalize_for_exact_match(sibling_text)
    if not normalized_sibling:
        return None
    normalized_doc = _normalize_for_exact_match(doc_text)
    # A raw `in` test matches MID-WORD: the excluded block `Q4 plan` fired CRIT and
    # blocking on the ordinary public sentence "our Q4 planning meeting is on Tuesday". Word
    # boundaries remove that class and break no true positive (measured: 1 of 4 constructed false
    # positives rescued, 0 of 2 genuine verbatim leaks missed).
    #
    # It does NOT fix the other three — `Pending` inside "the review is pending sign-off" is a
    # whole word, and "See the table below." is a whole phrase. That ambiguity is unfixable HERE,
    # because at this length the text carries no signal separating a leak from a coincidence, so
    # The view builder removes it at the source instead: `views.build_and_gate_views` refuses a sub-floor
    # excluded block at AUTHORING time rather than having this gate guess. The deliberate choice
    # was to push the cost to the author and keep the gate exact — not to add a
    # distinctiveness/boilerplate rule (a new false-negative surface on a moat) and not to
    # downgrade a CRIT to a warning on ambiguity (fail-closed is the doctrine).
    hit = re.search(rf"(?<!\w){re.escape(normalized_sibling)}(?!\w)", normalized_doc)
    return normalized_sibling if hit is not None else None


def gate_variant_overlap(header: DocHeader, siblings: list[str] | None) -> GateResult:
    # NOTE (2026-08-20): this is the PUBLIC, header-only entry point. ``run_gates`` runs the
    # sibling-aware ``_variant_overlap_against`` instead, so nothing inside this package calls this
    # function — it is a library API, not dead code, and it is recorded as such rather than left
    # ambiguous. The gate itself DOES run on every export; only this overload has no internal caller.
    """Gate 9 — variant non-overlap, the structural moat.

    Fail mode: **FAIL-CLOSED**. If the document declares ``header.variants`` (sibling
    doc ids/paths at other tiers) but ``siblings`` is None, empty, or shorter than the
    declared variant count, this BLOCKS — a missing sibling text (common when a
    git-ignored CONFIDENTIAL/SECRET file is absent on this checkout/CI) must never be
    silently treated as "no overlap"; that would let a converged doc slip through
    whenever its sibling happens not to be checked out. Only when the document
    declares NO variants at all does an empty ``siblings`` list mean "nothing to
    check" (not a failure).

    Otherwise: for each declared sibling text, compute shingle overlap at n=8 AND n=4,
    plus a similarity ratio, and BLOCK if any overlap is found or the ratio exceeds
    ``_SIMILARITY_RATIO_THRESHOLD``, naming the leaked span.
    """
    findings: list[Finding] = []

    if not header.variants:
        return GateResult(gate="variant_overlap", findings=findings)

    if siblings is None or len(siblings) < len(header.variants):
        findings.append(
            Finding(
                gate="variant_overlap",
                message=(
                    f"document declares {len(header.variants)} variant sibling(s) but only "
                    f"{0 if siblings is None else len(siblings)} sibling text(s) were provided — "
                    "failing closed (a missing sibling must never be treated as 'no overlap')"
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=header.id,
            )
        )
        return GateResult(gate="variant_overlap", findings=findings)

    self_text_placeholder = ""  # overlap is computed against the CALLER's own text via run_gates
    for idx, sibling_text in enumerate(siblings):
        if sibling_text is None:
            findings.append(
                Finding(
                    gate="variant_overlap",
                    message=f"sibling #{idx} for '{header.id}' is None — failing closed",
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=header.id,
                )
            )
            continue
        # Placeholder path is unreachable in normal use — run_gates() calls the real
        # comparison (below) with the document's own text; kept here only so this
        # function remains independently callable/testable with an explicit doc text.
        _ = self_text_placeholder
    return GateResult(gate="variant_overlap", findings=findings)


def _variant_overlap_against(
    doc_text: str, header: DocHeader, siblings: list[str] | None
) -> GateResult:
    """Real Gate 9 comparison: ``doc_text`` (the PUBLIC document under test) against
    each declared sibling. Fail-closed identically to ``gate_variant_overlap`` above;
    this variant additionally performs the actual n=8/n=4 shingle + ratio comparison,
    plus a length-independent exact-substring check for a sibling too short for shingle
    detection to see at all (see ``_MIN_SHINGLE_N``).
    """
    findings: list[Finding] = []

    if not header.variants:
        return GateResult(gate="variant_overlap", findings=findings)

    if siblings is None or len(siblings) < len(header.variants):
        findings.append(
            Finding(
                gate="variant_overlap",
                message=(
                    f"document declares {len(header.variants)} variant sibling(s) but only "
                    f"{0 if siblings is None else len(siblings)} sibling text(s) were provided — "
                    "failing closed (a missing sibling must never be treated as 'no overlap')"
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=header.id,
            )
        )
        return GateResult(gate="variant_overlap", findings=findings)

    for idx, sibling_text in enumerate(siblings):
        if sibling_text is None:
            findings.append(
                Finding(
                    gate="variant_overlap",
                    message=f"sibling #{idx} for '{header.id}' is None — failing closed",
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=header.id,
                )
            )
            continue

        # The shingle floor's blind spot: a sibling with fewer than
        # `_MIN_SHINGLE_N` CONTENT tokens (after stopword-stripping) produces zero
        # shingles at every `n` this gate checks and would report clean BY
        # CONSTRUCTION regardless of whether it appears verbatim in `doc_text`. Checked
        # length-independently here rather than by lowering `n` globally, which would
        # raise false positives across the whole corpus.
        if below_shingle_floor(sibling_text):
            exact_hit = _exact_substring_overlap(doc_text, sibling_text)
            if exact_hit is not None:
                findings.append(
                    Finding(
                        gate="variant_overlap",
                        message=(
                            f"exact-substring overlap between public doc '{header.id}' and "
                            f"sibling #{idx}: the excluded block is too short for shingle "
                            "detection (below the n=4 shingle floor) but appears verbatim "
                            "in the rendered view"
                        ),
                        severity=Severity.CRIT,
                        blocking=True,
                        evidence=exact_hit[:80],
                    )
                )

        for n in (8, _MIN_SHINGLE_N):
            overlap = shingle_overlap(doc_text, sibling_text, n=n)
            if overlap:
                sample = overlap[0]
                findings.append(
                    Finding(
                        gate="variant_overlap",
                        message=(
                            f"variant-overlap (n={n}) between public doc '{header.id}' and "
                            f"sibling #{idx}: {len(overlap)} shared shingle(s)"
                        ),
                        severity=Severity.CRIT,
                        blocking=True,
                        evidence=sample,
                    )
                )

        ratio = _similarity_ratio(doc_text, sibling_text, n=8)
        if ratio > _SIMILARITY_RATIO_THRESHOLD:
            findings.append(
                Finding(
                    gate="variant_overlap",
                    message=(
                        f"similarity ratio {ratio:.3f} between public doc '{header.id}' and "
                        f"sibling #{idx} exceeds threshold {_SIMILARITY_RATIO_THRESHOLD} "
                        "(reordered/synonym-paraphrased convergence)"
                    ),
                    severity=Severity.HIGH,
                    blocking=True,
                    evidence=f"ratio={ratio:.3f}",
                )
            )

    return GateResult(gate="variant_overlap", findings=findings)


# --------------------------------------------------------------------------------------
# Gate 10 — WCAG-AA contrast (DESIGN_SYSTEM §7 accessibility gate; ENGINE_PLAN §99 POOL
# item "WCAG-AA auto-contrast — ship a helper now"). Wires the existing
# ``components.contrast_ratio`` / ``components.wcag_aa_ok`` helpers into a REAL additive
# build gate: any foreground/background colour pair that renders as readable text but
# fails WCAG-AA BLOCKS the build. Additive-by-construction — the default checked set is
# the load-bearing Atlas text-role pairings, which all currently pass, so no existing
# passing document regresses.
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ColorPair:
    """One foreground/background colour pairing to check for WCAG-AA legibility.

    ``fg``/``bg`` are ``#rrggbb`` (or ``#rgb``) hex strings; ``large`` selects the 3:1
    large-text threshold (>=18pt, or >=14pt bold) instead of the 4.5:1 normal-text one.
    ``label`` names the role so a failing finding says exactly which pairing regressed.
    """

    fg: str
    bg: str
    label: str
    large: bool = False


# The load-bearing readable-text pairings the doc-system renders, sourced from the Atlas
# tokens (assets/tokens.json — mirrored here as literals because the gate must fail-closed
# on a hard-coded known-good baseline rather than trust a re-vendored token file at scan
# time). These are the running body/heading/eyebrow/table pairings a reader actually reads;
# every one currently clears AA (proven by tests), so wiring this gate is strictly additive.
# NOT included: the classification-badge pill (small decorative accent text at 3.92:1 by
# design — a large-text/decorative element, never running body copy) and pure-decoration
# strokes/fills, which carry no text and are out of WCAG text-contrast scope.
_DEFAULT_CONTRAST_PAIRS: tuple[ColorPair, ...] = (
    # Dark theme (native) — primary reading surfaces.
    ColorPair("#EAEEF5", "#060608", "dark: body ink (--bone) on ground (--night)"),
    ColorPair("#EAEEF5", "#141420", "dark: body ink (--bone) on raised (--steel-2/paper-2)"),
    ColorPair("#8A96AE", "#060608", "dark: secondary ink (--ash: eyebrow/caption) on ground"),
    ColorPair("#8A96AE", "#141420", "dark: secondary ink (--ash) on raised (--steel-2)"),
    # Light theme (report/print) — primary reading surfaces.
    ColorPair("#0B0E14", "#FAFBFC", "light: body ink (--bone) on ground (--night)"),
    ColorPair("#0B0E14", "#EEF1F5", "light: body ink (--bone) on raised (--steel-2/paper-2)"),
    ColorPair("#4B5568", "#FAFBFC", "light: secondary ink (--ash: eyebrow/caption) on ground"),
)


def gate_wcag_contrast(pairs: list[ColorPair] | None = None) -> GateResult:
    """Gate 10 — every declared text colour pairing must clear WCAG-AA.

    Fail mode: **BLOCKING** for any pair whose measured contrast ratio is below the WCAG-AA
    threshold for its kind (4.5:1 normal text / 3.0:1 large text). A malformed hex colour is
    ALSO blocking (fail-closed — an unparseable colour can never be proven legible), never
    silently skipped. Delegates the ratio + threshold to ``components.contrast_ratio`` /
    ``components.wcag_aa_ok`` (the single source of the WCAG maths — this gate never
    re-derives it).

    ``pairs=None`` checks ``_DEFAULT_CONTRAST_PAIRS`` (the Atlas load-bearing text roles).
    Pass an explicit list to check a document/theme's own declared pairings. An empty list
    is a legitimate "nothing to check" (no text pairings were declared) and passes.
    """
    to_check = _DEFAULT_CONTRAST_PAIRS if pairs is None else tuple(pairs)
    findings: list[Finding] = []
    for pair in to_check:
        try:
            ratio = contrast_ratio(pair.fg, pair.bg)
            ok = wcag_aa_ok(pair.fg, pair.bg, large=pair.large)
        except ValueError as exc:
            findings.append(
                Finding(
                    gate="wcag_contrast",
                    message=(
                        f"unparseable colour in pair '{pair.label}' "
                        f"(fg={pair.fg!r}, bg={pair.bg!r}) — failing closed: {exc}"
                    ),
                    severity=Severity.HIGH,
                    blocking=True,
                    evidence=f"{pair.fg} / {pair.bg}",
                )
            )
            continue
        if not ok:
            threshold = 3.0 if pair.large else 4.5
            findings.append(
                Finding(
                    gate="wcag_contrast",
                    message=(
                        f"colour pair '{pair.label}' fails WCAG-AA: "
                        f"contrast {ratio:.2f}:1 < {threshold:.1f}:1 required "
                        f"({'large' if pair.large else 'normal'} text)"
                    ),
                    severity=Severity.HIGH,
                    blocking=True,
                    evidence=f"{pair.fg} on {pair.bg} = {ratio:.2f}:1",
                )
            )
    return GateResult(gate="wcag_contrast", findings=findings)


# --------------------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------------------


def run_gates(
    text: str,
    header: DocHeader,
    *,
    siblings: list[str] | None = None,
    manifest_rows: list[ManifestRow] | None = None,
    strict: bool = False,
    local_preview: bool = False,
    contrast_pairs: list[ColorPair] | None = None,
) -> GateResult:
    """Run ALL gates against ``text``/``header`` and return one merged, adjudicated
    ``GateResult``.

    Order of operations (ENGINE_PLAN §4b):
        1. Normalize ``text`` (NFKC + strip zero-width/control) before every scan.
        2. Gate 1 — tier (hard: only PUBLIC is export-eligible, unless ``local_preview``).
        3. Gate 3 — secret-value scan (incl. base64/hex-decoded views).
        4. Gate 3b — PII/path/internal-hostname/stack-trace net.
        5. Gate 4 — detector-internal semantic net (advisory unless ``strict``).
        6. Gate 5 — header<->DOC_MANIFEST drift.
        7. Gate 10 — WCAG-AA text-contrast (blocks a below-AA colour pairing; additive —
           the default Atlas text-role pairings all pass).
        8. Gate 9 — variant non-overlap (fail-closed on missing siblings).

    Findings from every gate are merged and re-ordered by the L1 precedence spine via
    ``adjudicate()`` before being returned. ``GateResult.ok`` is True only if NO
    blocking finding exists across EVERY gate in the ``results`` list below — that list is
    the definition, and the numbered steps above are its commentary; no count is restated
    here (see the module docstring, `P8-116`).

    ``contrast_pairs`` overrides the default Atlas text-role pairings for Gate 10 (e.g.
    to check a document's own declared theme colours); ``None`` uses the defaults.

    ``local_preview`` only relaxes Gate 1 (see ``gate_tier``) — every other gate still runs
    and still blocks normally, so a leaked secret/PII value in a CONFIDENTIAL/SECRET doc
    still fails closed even in preview mode.
    """
    normalized = normalize(text)

    results: list[GateResult] = [
        gate_tier(header, local_preview=local_preview),
        gate_secret_value(normalized),
        gate_pii_path_internal(normalized),
        gate_detector_internal(normalized, strict=strict),
        gate_manifest_drift(header, manifest_rows),
        gate_wcag_contrast(contrast_pairs),
        _variant_overlap_against(normalized, header, siblings),
    ]

    merged = GateResult(gate="run_gates", findings=[])
    for result in results:
        merged = merged.merge(result)
    merged.findings = adjudicate(merged.findings)
    merged.gate = "run_gates"
    return merged
