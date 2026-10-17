"""Document identity — the semantic version layer git does not provide (`BUILD_PLAN.md` D3).

Git already gives revision history, diffs, integrity and blame, and this module deliberately
rebuilds none of it. What git cannot answer is: *which generation of this document is this, has it
moved since that generation was cut, who produced it, and does anyone claim it was verified?* Those
four questions are `version`, `revision`, `produced_by` and `verified_state` on
``models.DocHeader`` (`OG-07`), and they are what this module reads, derives and refuses.

**Two halves, and only one of them can live in the document.**

A governed document carries its identity in its own front matter, which is the good case: the
document is self-describing and a reader needs nothing else. But a corpus also contains documents
the engine does not govern — this repository's own hash-locked rule files are the worked example.
Adding front matter to those would change their bytes, which forces the RULEBOOK L9 two-step
re-baseline, and would make three *rule* files into governed *content* documents, which they are
not. So identity for those is carried entirely by the archive: `tools.docgen.archive` records the
cut, and the snapshot's bytes are the evidence.

**The authority is always the bytes, never the field.** Where a document carries both — a header
claiming ``revision: 0`` and an archived snapshot — the two must agree, and disagreement is a
finding rather than a preference. That is the same two-documents-one-claim discipline `CONS-03`
applies to the locked-file set: neither side is trusted alone, and neither side moves alone.

**The stamp grammar lives here because two callers need it.** `tools/corpus_check/guards/stamps.py`
owned the only copy, and this module's ``verified_state`` check asks the same question of the same
syntax. A second regex for one grammar is the exact shape `docs/process/RULES.md` Rule 1 names —
one root, several consumers, one guarded — so the guard now imports its grammar from here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tools.docgen.models import DocHeader, Finding, Severity, VerifiedState

GATE = "identity"

# The house stamp form, in both of its live spellings:
#   <!-- artifact-hardened: <STATUS> @ <sha> on <date> via <pass> -->
#   <!-- session-state:     <STATE>  @ <sha> on <date> via <pass> -->
# The kind is captured rather than listed, so a host project's own stamp kind is covered unchanged.
STAMP_RE = re.compile(
    r"<!--\s*([a-z][a-z-]*)\s*:\s*([A-Z][A-Za-z0-9 _-]*?)\s*@\s*([0-9a-f]{7,40})\s+on\s+"
    r"(\d{4}-\d{2}-\d{2})\s+via\s+([^\s>]+)\s*-->"
)

# Stamp kinds that certify their OWN BODY, and therefore invalidate when the body changes.
#
# Not every stamp does. `docs/process/SESSION_STATE.md` says so in its own text: a session-state
# record is written AFTER the work it describes and normally lands one commit later, so drifting
# from its own stamp is its designed behaviour. Applying the content-certification rule to it asks
# the wrong question. A host project adding its own hardening stamp kind adds it here; the tuple is
# explicit rather than inferred, because guessing which contract a stamp carries is the mistake
# this comment exists to record.
DRIFT_SENSITIVE_KINDS: tuple[str, ...] = ("artifact-hardened",)

NEEDS_REHARDENING = "NEEDS RE-HARDENING"

# The identity fields, as they are spelled in front matter. Named once so the schema test, the
# parser and the archive writer cannot drift apart on a spelling.
IDENTITY_FIELDS: tuple[str, ...] = ("version", "revision", "produced_by", "verified_state")

_ID_SEPARATOR = "__"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class Stamp:
    """One parsed stamp comment, with the line it sits on."""

    kind: str
    state: str
    sha: str
    date: str
    pass_name: str
    line: int

    @property
    def certifies_body(self) -> bool:
        """True when this stamp's contract is *"this body, at this commit"*."""
        return self.kind in DRIFT_SENSITIVE_KINDS


def find_stamps(text: str) -> list[Stamp]:
    """Every stamp in a document, in source order, with 1-based line numbers."""
    return [
        Stamp(
            kind=match.group(1),
            state=match.group(2),
            sha=match.group(3),
            date=match.group(4),
            pass_name=match.group(5),
            line=text[: match.start()].count("\n") + 1,
        )
        for match in STAMP_RE.finditer(text)
    ]


def archive_prefix() -> str:
    """The archive directory as a repo-relative prefix, e.g. ``docs/archive/``."""
    from tools.docgen import engine_config

    return f"{engine_config.archive_dir_relative().strip('/')}/"


def is_archived_path(rel: str) -> bool:
    """True when a repo-relative path is a superseded snapshot rather than a live document.

    **One predicate, every consumer.** Three places independently answer *"is this a live
    document?"*: `tools/corpus_check/corpus.py` (the corpus the guards read), `tools/health`'s
    charter-count check, and this module. The first version guarded only the corpus, and within
    minutes the health check and the `counts` guard disagreed about how many documents this
    repository has — 67 against 61 — which is the *exact* defect `docs/process/RULES.md` Rule 1
    describes and the exact defect `docs/CHARTER.md` exists to prevent. Two answers to one
    question is the bug, whichever answer is right.
    """
    return rel.startswith(archive_prefix())


def body_without_stamps(text: str) -> str:
    """The document with its stamp comments removed — *the body a stamp actually certifies*.

    **Why a raw ``git diff`` is the wrong comparison, and this is not a loophole.**

    A stamp records "this body, at commit C". To write it you must put the sha into the file, which
    changes the file — so the file at C never contains the stamp that names C. A fixed point would
    require a document whose bytes at commit C include ``sha(C)``, and no such document exists.
    Compared raw, therefore, **every** content-certifying stamp reads as drifted the instant it is
    written, for the sole reason that it was written. A gate whose "accepted" state is unreachable
    is not strict; it is broken in the direction nobody notices, because it only ever fires.

    Stripping the stamps from **both** sides compares the thing the stamp is about. The certificate
    is not part of what it certifies. Everything the rule is meant to catch still fires: add a
    sentence, delete a section, change a number, and the stripped bodies differ.

    Two things this deliberately does NOT do. It does not ignore the stamp's *own* fields — a
    changed sha or status is a changed stamp and the guard reads it directly. And it does not
    normalise whitespace: a diff that is only whitespace is still a diff, because a body whose
    layout changed is a body a reader sees differently.
    """
    return "\n".join(line for line in text.splitlines() if not STAMP_RE.search(line))


def body_matches(blob_at_commit: str, current_text: str) -> bool:
    """True when a stamped document's body is unchanged since the commit its stamp names.

    Pure, so it is falsifiable without a repository: the guards do the ``git show`` and hand the
    two texts here. One comparison, one place — `tools/corpus_check/guards/stamps.py` and the
    ``identity`` guard ask the identical question and must not answer it two ways.
    """
    return body_without_stamps(blob_at_commit) == body_without_stamps(current_text)


def slug_for_path(rel_path: str) -> str:
    """The archive id for a document that carries no header id of its own.

    ``docs/design/doc-system/TAXONOMY.md`` -> ``docs__design__doc-system__TAXONOMY``.

    Path-derived rather than allocated, because the alternative is an id registry — a second
    hand-kept mapping that can disagree with the tree, which is the failure mode this engine
    exists to catch. The cost is stated rather than hidden: **renaming a document orphans its
    archived history**, because the id moves with the path. That is a deliberate trade. An
    allocated id survives a rename but requires every ungoverned document to be edited to carry
    one, and for this repository's hash-locked rule files that edit is the L9 re-baseline this
    whole design exists to avoid.
    """
    stem = rel_path.removesuffix(".md")
    return stem.strip("/").replace("/", _ID_SEPARATOR)


def archive_id(rel_path: str, header: DocHeader | None = None) -> str:
    """This document's archive id: its header id when it has a real one, else a path slug.

    A governed document's id is already its name everywhere else in the engine, so reusing it
    keeps one document from having two names. ``UNKNOWN`` — ``classification.parse_header``'s
    sentinel for "this document has no parseable header" — is explicitly NOT a name: every
    unparseable document in a corpus would collapse onto the same archive directory.
    """
    if header is not None and header.id and header.id != "UNKNOWN":
        candidate = header.id
    else:
        candidate = slug_for_path(rel_path)
    return candidate if is_safe_id(candidate) else slug_for_path(rel_path)


def is_safe_id(candidate: str) -> bool:
    """True when an id is a single, ordinary path segment.

    An archive id becomes a directory name, so anything that could climb out of the archive root
    (``/``, ``..``, a leading dot, an absolute path, an empty string) is refused here rather than
    at the point where it would already have been joined onto a real path.
    """
    return bool(candidate) and candidate not in (".", "..") and bool(_SAFE_ID_RE.match(candidate))


def header_findings(header: DocHeader, source: str | None = None) -> list[Finding]:
    """Identity invariants that need nothing but the header and (optionally) its own text.

    These are the checks that hold for a single document in isolation, so they run in the
    host-facing ``docgen check``/``build`` path where there is no corpus and no git. The checks
    that genuinely need history — does this stamp still cover this body, does the header agree
    with the archived snapshot — belong to `tools.docgen.archive` and the ``identity`` corpus
    guard, which have the tree to answer them. The split is by *what evidence the question
    needs*, not by convenience, so neither side re-asks the other's question.
    """
    findings: list[Finding] = []

    if header.version < 0 or header.revision < 0:
        findings.append(
            Finding(
                gate=GATE,
                message=(
                    f"version/revision must be non-negative; got version={header.version}, "
                    f"revision={header.revision}."
                ),
                severity=Severity.HIGH,
                blocking=True,
                evidence=f"version={header.version} revision={header.revision}",
            )
        )

    if header.revision > 0 and header.version == 0:
        findings.append(
            Finding(
                gate=GATE,
                message=(
                    f"revision={header.revision} on an unversioned document. revision counts edits "
                    "made SINCE a version was cut into the archive, and no version has been cut — "
                    "so this number counts from nothing. Cut a version, or remove the field."
                ),
                severity=Severity.HIGH,
                blocking=True,
                evidence=f"version=0 revision={header.revision}",
            )
        )

    if header.verified_state is VerifiedState.VERIFIED:
        findings.extend(_verified_claim_findings(header, source))

    return findings


def _verified_claim_findings(header: DocHeader, source: str | None) -> list[Finding]:
    """``verified_state: verified`` is an assertion, and an assertion the engine can refute.

    This is the half of the claim that is answerable without history: **is there a stamp at all?**
    A document that says it was verified and carries no content-certifying stamp is claiming a
    result no evidence exists for, and that is a blocking finding here rather than a note.

    The other half — *does that stamp still cover this body* — needs git, and is answered by the
    ``identity`` corpus guard against the same grammar this module owns. Deliberately not
    duplicated: one grammar, one drift comparison, two callers.
    """
    if source is None:
        # Refusing here would fail every caller that legitimately has no source text to offer,
        # and passing silently would be a green on an unexamined claim. Neither: the claim is
        # simply not adjudicated in this call, and the corpus guard still adjudicates it.
        return []
    if any(stamp.certifies_body for stamp in find_stamps(source)):
        return []
    kinds = ", ".join(DRIFT_SENSITIVE_KINDS)
    return [
        Finding(
            gate=GATE,
            message=(
                "verified_state: verified, but this document carries no content-certifying stamp. "
                "The field is the claim; a stamp is the evidence. Without one there is nothing to "
                "check the claim against, so it reads as verified forever and for free."
            ),
            severity=Severity.CRIT,
            blocking=True,
            evidence=f"no stamp of kind {{{kinds}}} found in {len(source)} byte(s) of source",
        )
    ]
