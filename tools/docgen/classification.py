"""Header parsing + validation for the doc-system (RULEBOOK L2/L5/L14; CLASSIFICATION.md).

Parses the required YAML metadata header from a document's Markdown source and validates it against
the locked rules: all fields present, ``export_allowed`` a real bool, tier/surface/export agreement,
id-prefix known to ``TAXONOMY.md``, and header/manifest drift (a document's header tier must match its
``DOC_MANIFEST.md`` row).

Fail-closed throughout: a missing or malformed header is reported as a **blocking** ``Finding``, never
raised as an exception that a caller could mistake for "no findings = pass". ``parse_header`` never
raises on malformed input — malformed input is instead surfaced as a header with placeholder id
``"UNKNOWN"`` plus ``validate_header`` blocking findings when validated.
"""

from __future__ import annotations

import datetime
import logging
import re
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped,unused-ignore]  # PyYAML stubs are not bundled with mypy; present in some envs

from tools.docgen import engine_config, identity
from tools.docgen.doc_manifest import _strip_markup
from tools.docgen.models import (
    DocHeader,
    Finding,
    ManifestRow,
    Severity,
    Surface,
    Tier,
    VerifiedState,
)
from tools.lib import md_table
from tools.lib.front_matter import (
    UNPARSEABLE_LEADING_BLOCK,
    leading_comment_lines,
    unparseable_leading_block,
)

# The two verdict names are RE-EXPORTED here so `tools.docgen.hooks` reaches the
# fail-closed verdict through the module it already depends on. A direct `hooks -> tools.lib` edge
# is what the blueprint's ELK placement rejected: it moved two containers to a 43 px gap against a
# 72 px floor. The gate was right — the edge was unnecessary, because every caller of
# `unparseable_leading_block` already imports this module for `parse_header`.
__all__ = [
    "UNPARSEABLE_LEADING_BLOCK",
    "DocHeader",
    "parse_header",
    "unparseable_leading_block",
    "validate_header",
]

_LOG = logging.getLogger("tools.docgen.classification")

# TAXONOMY.md table shapes — same pipe-table dialect as DOC_MANIFEST.md / CONTRADICTION.md.
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR_ROW_RE = re.compile(r"^\|[\s:|-]+\|\s*$")


def _split_table_row(line: str) -> list[str]:
    """Split a TAXONOMY.md table row. **Delegates to the one reader** (`OG-36`).

    This used to be ``line.strip().strip("|").split("|")``, which deletes a GFM-escaped ``\\|``
    mid-word and eats an intentionally empty leading or trailing cell. It agreed with
    `tools/docgen/doc_manifest.py` on ordinary rows and disagreed on exactly the cells the
    governance corpus actually contains — the manifest's own
    ``variants: [commercial\\|confidential\\|secret]`` header parsed as four cells here and two
    there.
    """
    return md_table.split_row(line)


# Column headers ``load_taxonomy_prefixes`` accepts for the id-prefix column, matched
# case-insensitively and whitespace-tolerantly against the WHOLE normalised cell value — never a
# substring test, so a column named e.g. ``prefix-notes`` or ``no-prefix-here`` does NOT match.
# ``prefix`` is this engine's original bundled spelling; ``id-prefix`` is a spelling a host
# project's own TAXONOMY.md is free to use instead (a host project renaming this column to
# ``id-prefix`` made this function return an EMPTY set and fail-closed every document).
# New spellings belong HERE, as general engine vocabulary — never special-cased to one project.
_PREFIX_COLUMN_HEADERS = frozenset({"prefix", "id-prefix"})


def _normalize_header_cell(cell: str) -> str:
    """Whitespace-trim and lowercase a table-header cell for matching against a header-alias set.

    Deliberately explicit rather than assumed: the one caller below already receives
    pre-lowercased cells (its list comprehension applies ``.lower()``), but this function does not
    rely on that — it normalises its own input, so the comparison stays correct even if that
    upstream lowering is ever changed or removed.
    """
    return cell.strip().lower()


# The YAML front-matter delimiters (CLASSIFICATION.md "Metadata header" fence: ``---`` ... ``---``).
# Anchored at the START OF FILE (\A), but tolerant of what really precedes front matter in this
# tree: an optional UTF-8 BOM (many editors emit one) and any number of leading HTML comments —
# `<!-- title: … -->` is the house style of every process document here, and
# `docs/design/doc-system/CLASSIFICATION.md` opens with `<!-- classification: public -->`.
#
# The old pattern was `^\s*---` without re.MULTILINE, so `^` anchored at offset 0 and `\s*` matched
# neither a BOM nor a comment. Any document carrying one leading comment therefore parsed as
# HEADER-LESS: `_has_doc_header` returned False and the L14 placement gate skipped it entirely.
# Worse, a leading `<!-- classification: public -->` on a document whose YAML said
# `classification: secret` fell through to the legacy branch and passed on the COMMENT's word.
# The same rule backs the push-time gate, so nothing caught it later either.
# ⚠ **LEADING BLANK LINES TOO** (`OG-160`). This tolerated a BOM, any number of leading HTML
# comments, and horizontal whitespace — but not a blank LINE. Measured: prefixing a
# `classification: secret` document with a single `\n` made it invisible to `classify_file`, and
# therefore to BOTH L14 placement gates, so it committed and pushed clean with an affirmative
# "classification placement clean" printed. One keystroke, no bypass flag — precisely the
# cooperating-developer accident `THREAT_MODEL.md` says the moat exists to stop.
#
# The detector's job is to notice a classification a human or a renderer would read as front
# matter. Being stricter than that is not security, it is a blind spot: every byte the pattern
# refuses to skip is a place to hide a header.
_FRONT_MATTER_RE = re.compile(
    rf"\A\ufeff?{leading_comment_lines()}"
    r"[ \t]*---[ \t]*\r?\n(.*?\r?\n)---[ \t]*\r?\n?",
    re.DOTALL,
)

# Required header fields (CLASSIFICATION.md). ``variants`` is optional (defaults to empty list).
_REQUIRED_FIELDS = (
    "id",
    "classification",
    "title",
    "audience",
    "owner",
    "status",
    "export_allowed",
    "surface",
    "last_reviewed",
)

# The raw YAML type each header field may legally have, BEFORE ``parse_header``'s coercion runs
# (`P8-094`). Every coercion in ``parse_header`` is deliberately fail-closed and deliberately
# SILENT: a wrong-typed value becomes ""/SECRET/NONE/False/[] and the document then fails (or
# passes) for a reason that names a value the author never wrote. ``export_allowed: "true"`` — the
# quoted string, a YAML mistake so ordinary that quoting is the usual advice — read as ``False``
# with ZERO findings, so a document that says it may be exported was silently marked
# non-exportable and nothing anywhere said the word ``export_allowed``.
#
# ``last_reviewed`` accepts ``datetime.date`` as well as ``str`` because YAML auto-parses an
# unquoted ISO date, which ``_str_field`` converts back to ISO text on purpose — flagging that
# would be flagging correct authoring. ``bool`` is checked with ``isinstance``, which is False for
# ``1``/``0`` (``bool`` is a subclass of ``int``, not the reverse), so ``export_allowed: 1`` is
# caught too.
_FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "id": (str,),
    "classification": (str,),
    "title": (str,),
    "audience": (str,),
    "owner": (str,),
    "status": (str,),
    "export_allowed": (bool,),
    "surface": (str,),
    "last_reviewed": (str, datetime.date),
    "variants": (list,),
    # --- identity (Phase 4). Optional: absent means "unversioned", which every document that
    # predates the block is. They appear here and NOT in _REQUIRED_FIELDS on purpose — this map
    # answers "if you wrote it, is it the right type?", which is the only question an optional
    # field can be asked.
    "version": (int,),
    "revision": (int,),
    "produced_by": (str,),
    "verified_state": (str,),
}

# Fields whose only legal raw type is a REAL integer.
#
# ``bool`` is a subclass of ``int``, so ``isinstance(True, int)`` is True and ``version: true``
# would pass a plain ``(int,)`` check and then coerce to ``1`` — a document silently claiming to be
# at version 1 because someone typed a word YAML reads as a boolean. This is the same trap the
# ``export_allowed`` note above describes, running in the opposite direction, and it is exactly the
# "one root, several consumers" shape `docs/process/RULES.md` Rule 1 names: the bool/int confusion
# was already guarded in one direction and unguarded in the other.
_STRICT_INT_FIELDS = frozenset({"version", "revision"})

# id must be "<PREFIX>-<NNN>" where PREFIX is uppercase letters (with an optional single hyphenated
# suffix segment, e.g. "SOC-S" style prefixes like "SOC-S-003" are NOT supported here — TAXONOMY.md's
# prefixes with an internal hyphen, e.g. "SOC-S"/"SOC-E", are matched by longest-prefix-first below).
_ID_RE = re.compile(r"^([A-Z][A-Z0-9-]*[A-Z0-9])-([0-9]+)$")

_SENTINEL_ID = "UNKNOWN"


def _sentinel_header() -> DocHeader:
    """A placeholder header returned when parsing cannot even establish structure.

    Never used to signal success — always paired with a blocking Finding from validate_header when
    the caller runs validation. Exists so parse_header's return type stays a plain DocHeader (fail
    closed via findings, not via exceptions).
    """
    return DocHeader(
        id=_SENTINEL_ID,
        classification=Tier.SECRET,
        title="",
        audience="",
        owner="",
        status="",
        export_allowed=False,
        surface=Surface.NONE,
        last_reviewed="",
        variants=[],
    )


def parse_header(md: str) -> DocHeader:
    """Parse the YAML front-matter header from a document's Markdown source.

    Returns a best-effort ``DocHeader``. Any field that is missing, of the wrong type, or not a valid
    enum member is coerced to a safe placeholder (empty string / SECRET / NONE / False) rather than
    raising — callers MUST run ``validate_header`` on the result to discover what was wrong; a parsed
    header alone is never proof of validity. This keeps the contract fail-closed: malformed input never
    silently reads as a valid public/exportable document.
    """
    match = _FRONT_MATTER_RE.search(md)
    if match is None:
        return _sentinel_header()

    try:
        raw = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return _sentinel_header()

    if not isinstance(raw, dict):
        return _sentinel_header()

    doc_id = raw.get("id")
    doc_id_str = doc_id if isinstance(doc_id, str) else _SENTINEL_ID

    classification_raw = raw.get("classification")
    classification = _coerce_tier(classification_raw)

    surface_raw = raw.get("surface")
    surface = _coerce_surface(surface_raw)

    export_allowed_raw = raw.get("export_allowed")
    export_allowed = export_allowed_raw if isinstance(export_allowed_raw, bool) else False

    variants_raw = raw.get("variants", [])
    variants = [str(v) for v in variants_raw] if isinstance(variants_raw, list) else []

    def _str_field(name: str) -> str:
        value = raw.get(name)
        if isinstance(value, str):
            return value
        # YAML auto-parses an unquoted ISO date (e.g. `last_reviewed: 2026-07-05`) into a
        # datetime.date/datetime object rather than a string; coerce it back to ISO text so a
        # correctly-formatted-but-unquoted date is never treated as a missing field.
        if isinstance(value, datetime.date):
            return value.isoformat()
        return ""

    return DocHeader(
        id=doc_id_str,
        classification=classification,
        title=_str_field("title"),
        audience=_str_field("audience"),
        owner=_str_field("owner"),
        status=_str_field("status"),
        export_allowed=export_allowed,
        surface=surface,
        last_reviewed=_str_field("last_reviewed"),
        variants=variants,
        version=_int_field(raw, "version"),
        revision=_int_field(raw, "revision"),
        produced_by=_str_field("produced_by"),
        verified_state=_coerce_verified_state(raw.get("verified_state")),
    )


def _int_field(raw: dict[str, object], name: str) -> int:
    """A non-negative identity counter, fail-closed to 0 (``unversioned``).

    ``bool`` is rejected before ``int`` because it IS an ``int`` in Python: without this,
    ``version: true`` would read as version 1. The wrong-type case is reported by
    ``_raw_field_findings``; this side only has to make sure the coerced value cannot be a lie
    that reads as a real version.
    """
    value = raw.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _coerce_verified_state(value: object) -> VerifiedState:
    """Fail-closed: anything unrecognised reads as ``unverified``.

    The safe direction is unambiguous here and worth stating, because the tier coercion above
    documents the opposite instinct. For classification, fail-closed means *most restrictive*; for
    a verification claim it means *least certified*. A typo must never read as ``verified``.
    """
    if isinstance(value, str):
        try:
            return VerifiedState(value.strip().lower())
        except ValueError:
            print(
                f"verified_state: {value.strip()!r} is not a known state "
                f"({', '.join(s.value for s in VerifiedState)}); reading it as "
                f"{VerifiedState.UNVERIFIED.value!r} (fail-closed).",
                file=sys.stderr,
            )
    return VerifiedState.UNVERIFIED


def _coerce_tier(value: object) -> Tier:
    if isinstance(value, str):
        try:
            return Tier(value.strip().lower())
        except ValueError:
            # Say which value was rejected. Fail-closed is right, but SILENT fail-closed made the
            # diagnosis nonsense: `classification: publik` became `secret`, and the author then got
            # two errors about `classification=secret` — a tier they never wrote — with nothing
            # anywhere naming the typo. The reader is left proving a negative about a value that is
            # not in their file.
            print(
                f"classification: {value.strip()!r} is not a known tier "
                f"({', '.join(t.value for t in Tier)}); reading it as "
                f"{Tier.SECRET.value!r} (fail-closed). Any error below that mentions "
                f"'classification={Tier.SECRET.value}' is about THIS coercion, not about your file.",
                file=sys.stderr,
            )
    # Fail-closed: an unrecognized/missing tier is treated as the most restrictive tier so a
    # malformed header never accidentally reads as PUBLIC/exportable.
    return Tier.SECRET


def _coerce_surface(value: object) -> Surface:
    if isinstance(value, str):
        try:
            return Surface(value.strip().lower())
        except ValueError:
            pass
    # Fail-closed: an unrecognized/missing surface is treated as NONE (nothing may render there).
    return Surface.NONE


def _raw_front_matter_fields(md: str) -> dict[str, object] | None:
    """Re-parse raw YAML without coercion, for field-presence/type checks in validate_header."""
    match = _FRONT_MATTER_RE.search(md)
    if match is None:
        return None
    try:
        raw = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return raw if isinstance(raw, dict) else None


def validate_header(h: DocHeader, *, source: str | None = None) -> list[Finding]:
    """Validate a parsed ``DocHeader`` against RULEBOOK L2/L5/L14 + CLASSIFICATION.md.

    Pass ``source`` (the document's raw Markdown) to additionally catch fields that are PRESENT in
    the front matter but of the wrong YAML type — the class ``parse_header`` coerces away silently
    (`P8-094`). Without it those checks are skipped, which is why ``source`` exists as a keyword
    rather than a second positional: every existing caller keeps working, and the callers that
    HAVE the source (the build gate) pass it. ``_raw_front_matter_fields`` was written for exactly
    this and then had no caller at all until now.

    Checks (each independent, all fail-closed, all blocking unless noted):
    - all required fields present and non-empty (id/classification/title/audience/owner/status/
      surface/last_reviewed) and ``export_allowed`` a real bool;
    - (with ``source``) no header field present with the wrong YAML type;
    - id matches ``<PREFIX>-<NNN>`` and PREFIX is a known TAXONOMY.md prefix;
    - tier/surface agreement: non-public -> surface must be NONE; public -> surface must NOT be NONE;
    - tier/export agreement: ``export_allowed: true`` only legal for PUBLIC.

    A header that failed to parse at all (sentinel id ``"UNKNOWN"``) always yields a blocking finding
    naming the missing/malformed header — this function never returns an empty list for garbage input.
    """
    findings: list[Finding] = []

    if h.id == _SENTINEL_ID and not h.title and not h.audience:
        findings.append(
            Finding(
                gate="header",
                message="Document header is missing or malformed (no valid YAML front-matter found).",
                severity=Severity.CRIT,
                blocking=True,
                evidence="parse_header returned the sentinel header",
            )
        )
        # Still fall through to per-field checks below (they will also fire, which is fine —
        # redundant blocking findings do not weaken fail-closed behavior).

    missing = [f for f in _REQUIRED_FIELDS if not _field_present(h, f)]
    if missing:
        findings.append(
            Finding(
                gate="header",
                message=f"Missing or empty required header field(s): {', '.join(missing)}.",
                severity=Severity.CRIT,
                blocking=True,
                evidence=f"fields={missing}",
            )
        )

    findings.extend(_raw_field_findings(source, already_reported=set(missing)))

    if not isinstance(h.export_allowed, bool):  # pragma: no cover - dataclass typing enforces this
        findings.append(
            Finding(
                gate="header",
                message="export_allowed is not a real boolean.",
                severity=Severity.CRIT,
                blocking=True,
            )
        )

    if h.id != _SENTINEL_ID and h.id:
        id_match = _ID_RE.match(h.id)
        if id_match is None:
            findings.append(
                Finding(
                    gate="header",
                    message=f"id '{h.id}' does not match the required <PREFIX>-<NNN> format.",
                    severity=Severity.HIGH,
                    blocking=True,
                    evidence=h.id,
                )
            )

    # Tier <-> surface agreement (CLASSIFICATION.md metadata header rules).
    if h.classification is not Tier.PUBLIC and h.surface is not Surface.NONE:
        findings.append(
            Finding(
                gate="header",
                message=(
                    f"classification={h.classification.value} must have surface=none; "
                    f"got surface={h.surface.value}."
                ),
                severity=Severity.CRIT,
                blocking=True,
            )
        )
    if h.classification is Tier.PUBLIC and h.surface is Surface.NONE:
        findings.append(
            Finding(
                gate="header",
                message="classification=public must have surface in {web, repo, both}, got none.",
                severity=Severity.HIGH,
                blocking=True,
            )
        )

    # Identity invariants (Phase 4). Delegated rather than inlined so the host-facing single-doc
    # path and the corpus guard adjudicate an identity claim through ONE implementation.
    findings.extend(identity.header_findings(h, source))

    # Tier <-> export_allowed agreement.
    if h.export_allowed and h.classification is not Tier.PUBLIC:
        findings.append(
            Finding(
                gate="header",
                message=(
                    f"export_allowed=true is only legal for classification=public; "
                    f"got classification={h.classification.value}."
                ),
                severity=Severity.CRIT,
                blocking=True,
            )
        )

    return findings


def _raw_field_findings(source: str | None, *, already_reported: set[str]) -> list[Finding]:
    """Blocking findings only the RAW front matter can produce (`P8-094`, `P8-096`).

    Two classes, both invisible to every check that reads the coerced ``DocHeader``:

    1. **Present but wrong-typed.** ``export_allowed: "true"`` (quoted) is a ``str``; it becomes
       ``False`` with no diagnostic anywhere.
    2. **Absent where the placeholder is TYPE-VALID.** ``_field_present`` asks "is this a ``Tier`` /
       ``Surface`` / ``bool``?", and the fail-closed placeholders (``SECRET`` / ``NONE`` /
       ``False``) all answer yes — so omitting ``classification``, ``surface`` or
       ``export_allowed`` entirely satisfied a "required fields present" check that named them as
       required. ``already_reported`` carries the names ``_field_present`` DID catch (the string
       fields, whose placeholder is ``""``) so the same absence is not reported twice.

    Returns ``[]`` when ``source`` is None (the caller did not offer it) or carries no parseable
    front matter — the missing/malformed-header case is already a blocking finding of its own, and
    duplicating it here would say nothing new.
    """
    if source is None:
        return []
    raw = _raw_front_matter_fields(source)
    if raw is None:
        return []
    findings: list[Finding] = []
    for name in _REQUIRED_FIELDS:
        if name in raw or name in already_reported:
            continue
        findings.append(
            Finding(
                gate="header",
                message=(
                    f"required header field '{name}' is absent from the front matter. "
                    "parse_header substituted a fail-closed placeholder whose TYPE is valid, so "
                    "no check that reads the parsed header can see that you never wrote it."
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=f"present fields={sorted(raw)}",
            )
        )
    for name, allowed in _FIELD_TYPES.items():
        if name not in raw:
            continue
        value = raw[name]
        if name in _STRICT_INT_FIELDS and isinstance(value, bool):
            findings.append(
                Finding(
                    gate="header",
                    message=(
                        f"header field '{name}' is a YAML boolean, not an integer. Python's bool "
                        f"IS an int, so an unguarded type check accepts it and it coerces to "
                        f"{int(value)} — the document would read as version/revision "
                        f"{int(value)} because a word YAML parses as true/false was written where "
                        f"a number belongs."
                    ),
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=f"{name}={value!r} (bool)",
                )
            )
            continue
        if isinstance(value, allowed):
            continue
        wanted = " or ".join(t.__name__ for t in allowed)
        findings.append(
            Finding(
                gate="header",
                message=(
                    f"header field '{name}' is present but is a {type(value).__name__}, not a "
                    f"{wanted}. It was silently coerced to a safe placeholder, so every error "
                    f"below about '{name}' describes the placeholder and not what you wrote "
                    f"(e.g. export_allowed: \"true\" — the quoted string — reads as false)."
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=f"{name}={value!r} ({type(value).__name__})",
            )
        )
    return findings


def _field_present(h: DocHeader, name: str) -> bool:
    if name == "export_allowed":
        return isinstance(h.export_allowed, bool)
    if name == "classification":
        return isinstance(h.classification, Tier)
    if name == "surface":
        return isinstance(h.surface, Surface)
    value = getattr(h, name, None)
    return isinstance(value, str) and value.strip() != "" and value != _SENTINEL_ID


def load_taxonomy_prefixes(path: Path | None = None) -> set[str]:
    """Read the known doc-type id-prefixes from ``TAXONOMY.md`` (RULEBOOK L2/L5).

    Locates the first well-formed pipe table whose header has an id-prefix column — accepted
    spellings are ``_PREFIX_COLUMN_HEADERS`` (currently ``prefix`` and ``id-prefix``), matched
    case-insensitively and whitespace-tolerantly against the WHOLE cell value, never a substring
    (a column named e.g. ``prefix-notes`` does not count) — tolerating the narrative prose before
    the table and the change-history table after it — the same tolerance
    ``doc_manifest.read_manifest`` and ``adjudication.load_contradictions`` use.

    Fail-closed by omission: a missing/unreadable/malformed file, or a matching table with zero
    data rows, returns an EMPTY set, and ``check_taxonomy_prefix`` treats an empty set as "cannot
    validate — block every document" rather than "nothing to check". The absent file therefore
    never widens what is accepted.
    """
    resolved = path if path is not None else engine_config.doc_system_dir() / "TAXONOMY.md"
    if not resolved.is_file():
        _LOG.warning("TAXONOMY.md absent at %s — id-prefix validation will fail closed", resolved)
        return set()
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError is a ValueError, NOT an OSError — catching only OSError let a
        # non-UTF-8 registry crash the caller with an uncaught traceback instead of failing
        # closed. A traceback is not a gate result.
        _LOG.warning("TAXONOMY.md unreadable at %s: %s", resolved, exc)
        return set()

    lines = text.splitlines()
    prefix_col: int | None = None
    start = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not _TABLE_ROW_RE.match(stripped):
            continue
        cells = [_strip_markup(c).lower() for c in _split_table_row(stripped)]
        found = next(
            (i for i, c in enumerate(cells) if _normalize_header_cell(c) in _PREFIX_COLUMN_HEADERS),
            None,
        )
        if found is not None:
            prefix_col = found
            start = idx + 1
            break
    if prefix_col is None:
        _LOG.warning("TAXONOMY.md has no recognizable 'prefix' table at %s", resolved)
        return set()

    if start < len(lines) and _SEPARATOR_ROW_RE.match(lines[start].strip()):
        start += 1

    prefixes: set[str] = set()
    for raw in lines[start:]:
        stripped = raw.strip()
        if not stripped or not _TABLE_ROW_RE.match(stripped):
            break
        cells = _split_table_row(stripped)
        if len(cells) <= prefix_col:
            continue
        value = _strip_markup(cells[prefix_col])
        if value:
            prefixes.add(value)
    return prefixes


def check_taxonomy_prefix(h: DocHeader, known_prefixes: set[str]) -> list[Finding]:
    """Validate the header's id-prefix is a known TAXONOMY.md prefix (RULEBOOK L2, TAXONOMY.md).

    Fail-closed: an empty ``known_prefixes`` set (e.g. TAXONOMY.md unreadable) blocks every document,
    it never silently accepts an unrecognized prefix.
    """
    findings: list[Finding] = []
    if not known_prefixes:
        findings.append(
            Finding(
                gate="header",
                message="No known TAXONOMY.md prefixes were supplied; cannot validate id-prefix (fail-closed).",
                severity=Severity.CRIT,
                blocking=True,
            )
        )
        return findings

    prefix = _extract_prefix(h.id)
    if prefix is None:
        findings.append(
            Finding(
                gate="header",
                message=f"id '{h.id}' has no extractable prefix (expected <PREFIX>-<NNN>).",
                severity=Severity.HIGH,
                blocking=True,
                evidence=h.id,
            )
        )
        return findings

    if prefix not in known_prefixes:
        findings.append(
            Finding(
                gate="header",
                message=f"id-prefix '{prefix}' is not a known TAXONOMY.md doc type.",
                severity=Severity.HIGH,
                blocking=True,
                evidence=f"id={h.id}, known={sorted(known_prefixes)}",
            )
        )
    return findings


def _extract_prefix(doc_id: str) -> str | None:
    """Extract the prefix from an id, matching the LONGEST known-shape first.

    Handles hyphenated prefixes like ``SOC-S``/``SOC-E`` (TAXONOMY.md) by splitting on the final
    ``-<digits>`` suffix rather than the first hyphen.
    """
    match = re.match(r"^(.+)-([0-9]+)$", doc_id)
    if match is None:
        return None
    return match.group(1)


def check_manifest_drift(h: DocHeader, manifest_rows: list[ManifestRow]) -> list[Finding]:
    """Cross-check a document header's tier against its DOC_MANIFEST.md row (RULEBOOK L5/L10).

    A document's header ``classification`` must appear in the ``variants`` list of the manifest row
    whose ``id`` matches the header's id-prefix (manifest rows are keyed by type prefix, e.g. ``DET``,
    not by the full instance id). Fail-closed: if no manifest row matches the header's prefix at all,
    that is itself a blocking drift finding (an unlisted doc type must not silently pass).
    """
    findings: list[Finding] = []
    prefix = _extract_prefix(h.id)
    if prefix is None:
        findings.append(
            Finding(
                gate="header",
                message=f"id '{h.id}' has no extractable prefix; cannot check manifest drift.",
                severity=Severity.HIGH,
                blocking=True,
                evidence=h.id,
            )
        )
        return findings

    matching_row = next((row for row in manifest_rows if row.id == prefix), None)
    if matching_row is None:
        findings.append(
            Finding(
                gate="header",
                message=f"No DOC_MANIFEST.md row found for doc-type prefix '{prefix}'.",
                severity=Severity.HIGH,
                blocking=True,
                evidence=f"id={h.id}",
            )
        )
        return findings

    if h.classification not in matching_row.variants:
        findings.append(
            Finding(
                gate="header",
                message=(
                    f"Header tier '{h.classification.value}' for '{h.id}' is not among the tiers "
                    f"DOC_MANIFEST.md lists for '{prefix}': "
                    f"{[t.value for t in matching_row.variants]} (manifest drift)."
                ),
                severity=Severity.CRIT,
                blocking=True,
                evidence=f"id={h.id}, prefix={prefix}",
            )
        )

    # Surface drift is only meaningful for the PUBLIC/commercial variant. A manifest row stores a
    # single surface, and by the manifest's own convention (doc_manifest._parse_surface) that is the
    # primary/commercial surface — e.g. ENG's compound cell "web (commercial) / none (confidential+
    # secret)" parses to `web`. A non-public variant's surface is independently and correctly pinned
    # to `none` by the tier<->surface agreement rule above, so comparing it against the commercial
    # surface would be a spurious conflict (it blocked every confidential/secret ENG doc). Check the
    # row surface only when the header is public.
    if h.classification is Tier.PUBLIC and matching_row.surface is not h.surface:
        findings.append(
            Finding(
                gate="header",
                message=(
                    f"Header surface '{h.surface.value}' for '{h.id}' disagrees with DOC_MANIFEST.md's "
                    f"surface '{matching_row.surface.value}' for '{prefix}' (manifest drift)."
                ),
                severity=Severity.HIGH,
                blocking=True,
                evidence=f"id={h.id}, prefix={prefix}",
            )
        )

    return findings
