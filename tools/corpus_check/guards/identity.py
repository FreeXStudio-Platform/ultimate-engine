"""``identity`` — a document's version claim, checked against the bytes that would prove it.

Phase 4 gives a document four identity fields (`OG-07`) and an archive to keep its superseded
versions in. Every one of those is a **claim**, and a claim nobody checks is a convention. This
guard is what makes them gates:

* a document whose header claims ``revision: 0`` is claiming its live bytes still equal its
  archived snapshot — so the bytes are compared, and a mismatch is a finding;
* a document whose header states a ``version`` the archive does not hold is claiming a generation
  that was never cut;
* a document claiming ``verified_state: verified`` must carry a content-certifying stamp, and that
  stamp must still cover the body — the same drift rule `stamps` applies, asked of the field that
  asserts the result rather than of the comment that records it;
* the archive's own record must match the archive's own directories, sha256 included.

**Why the freeze check cannot be replaced by "did the file change in git".** Git answers *did this
file change since some commit*; the freeze question is *do these bytes equal the bytes we kept*.
They come apart where it matters: a document reverted to its archived content is "changed" in git
and correctly frozen here.

⚠ **What this guard does NOT do, corrected 2026-08-24 after an adversarial verifier walked through
it (`OG-193`).** The sentence that used to close this paragraph claimed a document *"whose archive
was quietly edited to match is correctly refused here, because the sha256 recorded at the cut no
longer matches"*. **That is false**, and it was the only tamper-resistance claim in this module.
The snapshot and the history sit in the same working tree as the live document, so three
coordinated edits — body, snapshot, recorded sha256 — satisfy every check below. Reproduced on both
a governed and an ungoverned document. This is **self-certification**, the same bar RULEBOOK L9's
hash gate already accepts for the locked rule files (`OG-46`), and its defence is that the forgery
is visible in one reviewable diff, not that the engine detects it. What the hash genuinely catches
is the snapshot edited while the record is not.

**The anti-vacuity floor is a derived subject set, not a constant** (`LESSONS.md` L-37). This guard
counts one check per archived document plus one per identity-bearing header, and refuses to report
a pass when the corpus declares identity somewhere and this guard examined none of it. Three probes
in an earlier phase broke at the moment the thing they measured improved, because they pinned a
number that was true on the day they were written; this one derives its subject set from the corpus
every run and asserts only that it is non-empty when the corpus says it should be.
"""

from __future__ import annotations

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.model import (
    Finding,
    GuardResult,
    Severity,
    failed,
    passed,
    skipped,
)
from tools.docgen import archive, identity
from tools.docgen.classification import parse_header
from tools.docgen.models import VerifiedState

GUARD = "identity"


def _identity_bearing(corpus: Corpus) -> list[tuple[str, object]]:
    """Live documents whose front matter declares any identity field, with their parsed headers.

    Derived from the corpus on every run. A document that declares none of the four fields is not
    examined and is not counted — it has made no claim, and counting it would inflate ``checked``
    with documents this guard never judged (`OG-96`).
    """
    found: list[tuple[str, object]] = []
    for rel in corpus.markdown:
        front = corpus.front_matter(rel)
        if front is None:
            continue
        if not any(f"{name}:" in front for name in identity.IDENTITY_FIELDS):
            continue
        found.append((rel, parse_header(corpus.text(rel))))
    return found


def run(corpus: Corpus) -> GuardResult:
    """Check every identity claim in the corpus against the archive and the stamps."""
    if not corpus.available:
        return skipped(GUARD, "git is unavailable, so the tracked corpus cannot be listed")

    findings: list[Finding] = []
    checked = 0

    archived_ids = archive.archived_ids(corpus.root)
    bearers = _identity_bearing(corpus)

    # --- 1. the archive's record against the archive's directories -----------------------------
    for doc_id in archived_ids:
        checked += 1
        for defect in archive.audit_id(corpus.root, doc_id):
            findings.append(
                Finding(
                    guard=GUARD,
                    path=f"{corpus.archive_prefix}{doc_id}/{archive.HISTORY_NAME}",
                    line=0,
                    message=defect.message,
                    evidence=defect.evidence,
                    severity=Severity.CRITICAL,
                )
            )

    # --- 2. every archived document's freeze state ---------------------------------------------
    #
    # Read from the history rather than re-derived from the id: a header-id archive (``WF-201``)
    # carries no path information, so only the record knows which live document it belongs to.
    for doc_id in archived_ids:
        source_rel = archive.live_path(corpus.root, doc_id)
        if not source_rel:
            findings.append(
                Finding(
                    guard=GUARD,
                    path=f"{corpus.archive_prefix}{doc_id}/{archive.HISTORY_NAME}",
                    line=0,
                    message="archive history names no live document, so nothing can be compared "
                            "against its snapshots",
                    evidence="expected a `Live document: `<path>`` line",
                    severity=Severity.HIGH,
                )
            )
            continue
        if not corpus.resolves(source_rel):
            findings.append(
                Finding(
                    guard=GUARD,
                    path=f"{corpus.archive_prefix}{doc_id}/{archive.HISTORY_NAME}",
                    line=0,
                    message=f"archive history names `{source_rel}`, which the corpus does not "
                            "track — the live document was moved or deleted and its history was "
                            "orphaned",
                    evidence="an archive id is derived from a path; renaming the document "
                             "orphans it (tools/docgen/identity.slug_for_path)",
                    severity=Severity.HIGH,
                )
            )
            continue

        checked += 1
        state = archive.freeze_state(corpus.root, source_rel, doc_id)
        header = dict(bearers).get(source_rel)
        claims_frozen = getattr(header, "claims_frozen", False)

        # **An archived document that has moved must SAY so, and there are only two ways to say
        # it.** A governed document declares the move by bumping `revision`; an ungoverned one has
        # no field to bump, so the only declaration available to it is cutting the next version.
        #
        # Without this branch the ungoverned case was silent: the three rule files this phase
        # froze carry no front matter, so nothing claimed `revision: 0`, so editing one produced
        # no finding at all — `archive list` said "NOT frozen" and the gate said CLEAN. A freeze
        # nothing enforces is a copy of a file. Measured on this corpus the moment
        # `CONTRADICTION.md` legitimately changed under RULEBOOK L9.
        if header is None and not state.frozen:
            findings.append(
                Finding(
                    guard=GUARD,
                    path=source_rel,
                    line=0,
                    message=(
                        f"archived at v{state.version} but {state.reason}. This document carries "
                        "no front matter, so it has no revision field to declare an edit in — the "
                        "only way to record that it moved is to cut the next version "
                        "(`docgen archive cut`)."
                    ),
                    evidence=f"archive id {state.doc_id}",
                    severity=Severity.CRITICAL,
                )
            )

        # A header that claims `revision: 0` is claiming the freeze. The archive decides.
        if claims_frozen and not state.frozen:
            findings.append(
                Finding(
                    guard=GUARD,
                    path=source_rel,
                    line=0,
                    message=(
                        f"header claims revision: 0 at version {getattr(header, 'version', '?')}, "
                        f"but {state.reason}. revision: 0 asserts the live bytes ARE the archived "
                        "bytes; bump revision, or cut a new version."
                    ),
                    evidence=f"archive id {state.doc_id}, newest snapshot v{state.version}",
                    severity=Severity.CRITICAL,
                )
            )

        # The header's version must be a generation the archive actually holds.
        declared = getattr(header, "version", 0)
        if declared and declared != state.version:
            findings.append(
                Finding(
                    guard=GUARD,
                    path=source_rel,
                    line=0,
                    message=(
                        f"header declares version {declared}, but the newest version in the "
                        f"archive is v{state.version}."
                    ),
                    evidence=f"archive id {state.doc_id}, on disk: "
                             f"{archive.versions_on_disk(corpus.root, state.doc_id)}",
                    severity=Severity.HIGH,
                )
            )

    # --- 3. every `verified_state: verified` claim, against a stamp that still covers the body ---
    for rel, header in bearers:
        if getattr(header, "verified_state", None) is not VerifiedState.VERIFIED:
            continue
        checked += 1
        text = corpus.text(rel)
        stamps = [s for s in identity.find_stamps(text) if s.certifies_body]
        if not stamps:
            findings.append(
                Finding(
                    guard=GUARD,
                    path=rel,
                    line=0,
                    message="verified_state: verified with no content-certifying stamp in the body",
                    evidence=f"kinds that certify a body: {identity.DRIFT_SENSITIVE_KINDS}",
                    severity=Severity.CRITICAL,
                )
            )
            continue
        for stamp in stamps:
            if corpus.git("cat-file", "-e", f"{stamp.sha}^{{commit}}") is None:
                # A verification lab built with `git archive` has its own history, so a stamped sha
                # genuinely is not present. `stamps` makes the same call for the same reason: a
                # gate that is red for reasons unrelated to what it tests is a gate people learn
                # to ignore.
                continue
            blob = corpus.git("show", f"{stamp.sha}:./{rel}")  # `./`: resolve from the corpus root, not the git top-level (see blueprint/completeness.py)
            if blob is None or identity.body_matches(blob, text):
                continue
            findings.append(
                Finding(
                    guard=GUARD,
                    path=rel,
                    line=stamp.line,
                    message=(
                        f"verified_state: verified, but the {stamp.kind} stamp @ {stamp.sha} no "
                        "longer covers this body. The claim asserts a result its own evidence "
                        "has stopped supporting."
                    ),
                    evidence=f"the body at {stamp.sha} differs from the body now",
                    severity=Severity.CRITICAL,
                )
            )

    # --- 4. header-only identity invariants, for documents with no archive at all ---------------
    for rel, header in bearers:
        for finding in identity.header_findings(header, corpus.text(rel)):  # type: ignore[arg-type]
            if finding.gate != identity.GATE:
                continue
            checked += 1
            findings.append(
                Finding(
                    guard=GUARD,
                    path=rel,
                    line=0,
                    message=finding.message,
                    evidence=finding.evidence,
                    severity=(
                        Severity.CRITICAL if finding.severity.value == "crit" else Severity.HIGH
                    ),
                )
            )

    floor = _floor(archived_ids, bearers)
    evidence = (
        f"{len(archived_ids)} archived document(s) under {corpus.archive_prefix}; "
        f"{len(bearers)} live document(s) declare an identity field; "
        f"floor derived from the corpus, not pinned"
    )
    if findings:
        return failed(GUARD, findings, checked=checked, floor=floor)
    return passed(
        GUARD,
        f"{GUARD}: {checked} identity claim(s) checked — every archived record matches its "
        "snapshots, every freeze claim matches the bytes, every verified claim has a live stamp",
        checked=checked,
        floor=floor,
        evidence=evidence,
    )


def _floor(archived_ids: list[str], bearers: list[tuple[str, object]]) -> int:
    """The anti-vacuity floor, DERIVED from what the corpus contains rather than pinned.

    One check per archived document is guaranteed by construction (step 1 counts every id), so the
    floor is the number of archived documents — it rises when the corpus adopts identity and falls
    to zero on a corpus that has adopted none. A pinned constant would have exactly the failure
    `L-37` records: it goes red on the day the corpus legitimately changes, at which point someone
    edits the number and the guard stops measuring anything.
    """
    return len(archived_ids) if (archived_ids or bearers) else 0
