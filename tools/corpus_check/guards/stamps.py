"""``stamps`` — a stamp whose recorded commit no longer matches the file body is invalid.

`DOC_WRITING_DOCTRINE.md` §8.2, stated as an unbreakable rule: *"A stamp on an edited body is
invalid. Re-harden, or mark `NEEDS RE-HARDENING`. Never leave an approval on a body you changed."*

**What already owns part of this, and is not re-asked.** `tools/health` `STRUCT-06` validates the
`SESSION_STATE.md` stamp's *form*: that it parses, that its state word is one the document itself
defines, that its commit exists and is an ancestor of `HEAD`. It says so explicitly — *"this checks
the MECHANICAL half only"*.

**What was missing is the half the rule is actually about: drift.** Nothing compared a stamped
document's **body** against the commit its stamp names, and no stamped document other than
`SESSION_STATE.md` was checked at all. A stamp can therefore be perfectly well-formed, name a real
ancestor commit, and certify content that has since changed — which is precisely the state
`PROVENANCE.md` has been in for many commits (`OG-09`).

**The escape hatch is the rule's own, not an exemption invented here.** Doctrine §8.2 offers two
compliant states: re-harden, **or** mark `NEEDS RE-HARDENING`. So a drifted stamp whose document —
or a state document that hands it over — carries that marker is *compliant*, and is reported as
such rather than as a defect. That is what keeps `OG-09` an honest scheduled deferral instead of a
new blocker: the project already declares the drift, in writing, where a reader will meet it.

**An unknown commit is a SKIP-shaped fact, not a defect.** A verification lab is built with
``git archive`` into a fresh history, so a stamped sha genuinely does not exist there. `STRUCT-06`
makes the same call for the same reason: failing would paint every lab red for a reason that has
nothing to do with what the lab tests, and a gate that is red for irrelevant reasons is a gate
people learn to ignore.
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
from tools.docgen import identity

GUARD = "stamps"

# **The stamp grammar is imported, not restated.** It used to be declared here, and Phase 4's
# `verified_state` check needs to ask the same question of the same syntax — a second regex for one
# grammar is `docs/process/RULES.md` Rule 1's exact shape, and the two copies would diverge the
# first time a host added a stamp kind. `tools/docgen/identity.py` owns it; this guard owns the
# drift comparison, which is the part that needs git.
_STAMP_RE = identity.STAMP_RE
_NEEDS_REHARDENING = identity.NEEDS_REHARDENING

# **Not every stamp certifies its own body, and treating them alike produced a false green.**
#
# This corpus declares TWO stamp contracts, and says so in the document that owns the weaker one.
# `docs/process/SESSION_STATE.md`, section *The stamp — what it is and how to read it* — *"This is
# deliberately weaker than the hardening stamp in `PROVENANCE.md`, which invalidates on any edit to
# its own body. That rule is right for an artifact whose CONTENT is the thing being certified; it
# would be wrong here, where the file's job is to describe a commit from outside it."*
#
# Cited by SECTION rather than by line number since 2026-08-29: the citation read `:50-52` while the
# quoted text sat at line 63, because that file's own rule is *rewritten in place, never appended*.
# A line citation into a document that rewrites itself is guaranteed to rot.
#
# A `session-state` record is WRITTEN AFTER the work it describes and normally lands one commit
# later — drifting from its own stamp is its designed behaviour, not a defect. `STRUCT-06` owns its
# mechanical half (stamp parses, state is in the document's own vocabulary, commit is real and an
# ancestor). Applying doctrine §8.2's content-certification rule to it asks the wrong question.
#
# So drift-invalidation applies to content-certifying kinds only. A host project adding its own
# hardening stamp kind adds it here; the list is short and explicit rather than inferred, because
# guessing which contract a stamp carries is exactly the mistake this comment exists to record.
_DRIFT_SENSITIVE_KINDS = identity.DRIFT_SENSITIVE_KINDS

# Documents that hand over project state. A drift declared in any of them is declared where the
# next session will meet it, which is what doctrine §8.2's marker is for.
_HANDOVER = ("HANDOFF.md", "docs/plan/NEXT_SESSION.md", "docs/process/SESSION_STATE.md")

_FLOOR = 1


# Extensions a stamp can legitimately live in. A stamp is an HTML comment, so any text surface
# that renders or records one is in scope; `node_modules` never is.
_STAMPABLE_SUFFIXES = (".md", ".html", ".htm", ".markdown", ".txt")


def _stamped_candidates(corpus: Corpus) -> tuple[str, ...]:
    """Tracked files a stamp could appear in, in stable order.

    ``corpus.tracked`` already excludes archived snapshots (``Corpus.is_archived``), and that
    exclusion matters most HERE: a stamp inside a snapshot certifies the body it had when it was
    cut, so `git diff <sha> -- <snapshot>` compares a frozen file against a moving document.
    Judged against HEAD, every archived stamp would go red the moment the document it came from
    moved on — which is always.
    """
    return tuple(
        rel
        for rel in corpus.tracked
        if rel.endswith(_STAMPABLE_SUFFIXES) and "node_modules" not in rel
    )


def run(corpus: Corpus) -> GuardResult:
    """Compare every stamped document's body against the commit its stamp certifies."""
    findings: list[Finding] = []
    checked = 0
    unverifiable: list[str] = []
    other_kinds: list[str] = []

    # Doctrine §8.2's marker is satisfied by declaring the drift where the next session will meet
    # it — which is a handover document, not necessarily the drifted file itself. `PROVENANCE.md`
    # carries the stamp; `HANDOFF.md` carries the `NEEDS RE-HARDENING` verdict, in the state table
    # a session reads first. Requiring the marker inside the stamped file would report that
    # arrangement as a defect while the project is doing exactly what the rule asks.
    #
    # ⚠ **The declaration is PER DOCUMENT, and that is load-bearing.** The first version of this
    # guard treated any handover containing the marker as excusing every drifted stamp in the
    # corpus — so `HANDOFF.md`'s honest note about `PROVENANCE.md` would have silently exempted a
    # second, undeclared drift somewhere else. One declared drift must not be a blanket amnesty:
    # a handover excuses a document only if it names that document alongside the marker.
    declarations = {h: corpus.lines(h) for h in _HANDOVER}

    # A basename is only a safe way to name a document when it is UNIQUE. `HANDOFF.md` legitimately
    # declares the root `PROVENANCE.md`'s drift; a Pass-7 probe added
    # `tools/graphify/vendor/PROVENANCE.md` and that honest declaration excused the unrelated file
    # (`OG-96`). Where a basename is ambiguous, only the full path counts.
    basename_counts: dict[str, int] = {}
    for tracked_rel in corpus.markdown:
        base = tracked_rel.rsplit("/", 1)[-1]
        basename_counts[base] = basename_counts.get(base, 0) + 1

    def declared_for(rel: str) -> list[str]:
        """Handover documents that declare THIS document's drift, **on one line**.

        ⚠ **Co-location is the whole guarantee.** The first version accepted the marker and the
        document name appearing anywhere in the same file, and three independent verifiers broke it
        the same way: `HANDOFF.md` carries `NEEDS RE-HARDENING` on line 21 *about a different file*
        and quotes the rule verbatim on line 172, while its document-index names sixteen other
        documents elsewhere. Measured blast radius: **51 of 57 documents were auto-excused** (re-derived 2026-08-22; long recorded as `14 of 57`, which counted one carrier file and even for that file measures 17 — see `OG-107`), and a
        genuinely drifted stamp on `docs/process/SESSION_STATE.md` was reported compliant.
        Line-scoped, the legitimate declaration still works — HANDOFF.md:21 puts the marker and
        `PROVENANCE.md` in one table row — and the rule-quotation on line 172, which names no file,
        correctly stops being a declaration for anything.
        """
        name = rel.rsplit("/", 1)[-1]
        unique = basename_counts.get(name, 0) <= 1
        return [
            h
            for h, lines in declarations.items()
            if any(
                _NEEDS_REHARDENING in ln and (rel in ln or (unique and name in ln))
                for ln in lines
            )
        ]

    # **Every tracked TEXT file, not only Markdown** (`OG-126`). A stamp is an HTML comment, so it
    # is equally valid in a built `.html` page — and `corpus.markdown` filters on `.endswith(".md")`,
    # so a stamp planted in `examples/capability-gallery.html` with an edited body was not merely
    # unjudged, it was never parsed: the guard reported `2 stamp(s) checked` and passed. No live
    # instance today (only `PROVENANCE.md` and `SESSION_STATE.md` carry stamps), which is exactly
    # when a scope gap is cheapest to close.
    for rel in _stamped_candidates(corpus):
        text = corpus.text(rel)
        for match in _STAMP_RE.finditer(text):
            kind, state, sha, date, pass_name = match.groups()
            line_no = text[: match.start()].count("\n") + 1

            if kind not in _DRIFT_SENSITIVE_KINDS:
                # NOT counted as checked. It used to be — `checked += 1` ran before this branch —
                # so a corpus of nothing but non-drift-sensitive stamps would clear the anti-vacuity
                # floor while drift-checking nothing at all (`OG-96`). A stamp this guard declines
                # to judge is not a claim it examined.
                other_kinds.append(f"{rel}:{line_no} ({kind})")
                continue

            if corpus.git("cat-file", "-e", f"{sha}^{{commit}}") is None:
                # Either history was rewritten or this is a detached export with its own history.
                # Both are outside this guard's competence to distinguish, and guessing would make
                # every verification lab red.
                unverifiable.append(f"{rel}:{line_no} -> {sha}")
                continue

            checked += 1
            # **The BODY is compared, not the file** (`identity.body_matches`). A raw
            # `git diff <sha> -- <rel>` also sees the stamp line itself, and the stamp cannot
            # possibly have been present at the commit it names — writing the sha in is what
            # changed the file. Compared that way the guard's "accepted" state is unreachable and
            # it can only ever fire, which is why nobody noticed: a gate that always reports drift
            # looks strict and measures nothing.
            blob = corpus.git("show", f"{sha}:./{rel}")  # `./`: resolve from the corpus root, not the git top-level (see blueprint/completeness.py)
            if blob is None:
                unverifiable.append(f"{rel}:{line_no} -> {rel} not present at {sha}")
                continue
            if identity.body_matches(blob, text):
                continue  # the body still matches the commit the stamp certifies

            # Drifted. Compliant only if the drift is declared FOR THIS DOCUMENT, per doctrine §8.2.
            #
            # ⚠ **THERE IS NO SELF-DECLARATION HATCH, AND REMOVING IT IS THE FIX.**
            #
            # The escape used to include `_NEEDS_REHARDENING in text` — a whole-document substring
            # left beside the line-scoped handover check. So a drifted stamp on any document that
            # merely QUOTES doctrine §8.2 excused itself, and
            # `docs/framework/DOC_WRITING_DOCTRINE.md` quotes that rule verbatim. Three Pass-7
            # agents walked through it. Line-scoping it was tried first and does not work: a quote
            # of the rule and a declaration of drift are the same string on the same line, and only
            # a reader can tell them apart.
            #
            # So the declaration lives where the reader who must decide whether to trust the
            # document actually looks — a handover, on a line that names the document. That is
            # already how this project does it in practice: `PROVENANCE.md`'s drift is declared in
            # `HANDOFF.md`, not in `PROVENANCE.md`. One rule, one place, no ambiguity (`OG-96`).
            if declared_for(rel):
                continue
            findings.append(
                Finding(
                    guard=GUARD,
                    path=rel,
                    line=line_no,
                    message=f"{kind} stamp {state!r} @ {sha} no longer covers this file's body",
                    evidence=(
                        f"stamped {date} via {pass_name}; the body at {sha} differs from the body "
                        f"now (both compared with stamp lines removed). "
                        f"Doctrine §8.2 allows exactly two compliant states: re-harden, or mark "
                        f"{_NEEDS_REHARDENING}. Neither is present."
                    ),
                    severity=Severity.HIGH,
                )
            )

    declared = ", ".join(sorted({h for rel in _stamped_candidates(corpus) for h in declared_for(rel)})) or "none"
    kinds_note = (f"; {len(other_kinds)} stamp(s) of a non-drift-sensitive kind were classified and "
                  f"NOT counted: {', '.join(other_kinds[:3])}" if other_kinds else "")
    evidence = (
        f"drift declared by: {declared}; "
        f"{len(unverifiable)} stamp(s) unverifiable here (detached history or rewritten history): "
        + ("; ".join(unverifiable[:4]) if unverifiable else "none")
        + kinds_note
    )
    if findings:
        return failed(GUARD, findings, checked=checked, floor=_FLOOR)
    if checked == 0 and unverifiable:
        # **Nothing was verified, so nothing may be certified.** Every drift-sensitive stamp in
        # this corpus names a commit that is not in THIS history — a `git archive` verification
        # lab, or a rewritten history. The guard is not broken and the corpus is not dirty; the
        # environment simply cannot answer the question (`LESSONS.md` L-25).
        #
        # Reporting PASS here would be a green with `checked=0`, which is precisely the
        # clean-but-empty vacuity `model.passed()`'s floor exists to demote — and it went
        # unnoticed until the floor started counting honestly (`OG-96`: `checked += 1` used to run
        # before the kind filter, so a lab scored 1 without verifying anything). SKIP is never a
        # pass, and `--full` treats it as a failure by design, which is the correct loud outcome.
        return skipped(
            GUARD,
            f"no stamp could be verified in this history: {len(unverifiable)} stamp(s) name a "
            "commit this repository does not contain (detached or rewritten history)",
            evidence=evidence,
        )
    return passed(
        GUARD,
        f"{GUARD}: {checked} stamp(s) checked; every drifted content-certifying stamp is declared "
        f"{_NEEDS_REHARDENING} on the line that names it",
        checked=checked,
        floor=_FLOOR,
        evidence=evidence,
    )
