"""Counter-examples for document identity and the archive (Phase 4, `OG-07`).

**Every probe here creates or derives its own condition** (`LESSONS.md` L-37). Three probes in an
earlier phase broke at the exact moment the thing they measured got *better*, because they had
pinned a number or borrowed a document that happened to be in a particular state on the day they
were written. So: the lab probes synthesise their own documents and their own archive, and the two
probes that must run against the live corpus **derive** their subject set from it and assert that
set is non-empty before asserting anything about its members.

Each defect is falsified in **both** directions — planted and shown red, then removed and shown
green. A probe that only ever sees red cannot distinguish a working guard from a broken one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.guards import identity as identity_guard
from tools.corpus_check.model import Status
from tools.docgen import archive, identity
from tools.docgen.classification import parse_header, validate_header
from tools.docgen.models import DocHeader, VerifiedState

_ROOT = Path(__file__).resolve().parents[2]

_GOVERNED = """---
id: WF-900
classification: public
title: Governed Sample
audience: technical
owner: doc-system
status: draft
export_allowed: true
surface: web
last_reviewed: 2026-08-24
---

# Governed Sample

Body text that a version can be cut from.
"""

_UNGOVERNED = "# Rule File\n\nA document with no front matter at all.\n"


def _git(cwd: Path, *argv: str) -> str:
    out = subprocess.run(
        ("git", "-C", str(cwd), *argv), check=False, capture_output=True, text=True, timeout=60
    )
    return out.stdout.strip()


def _force_rmtree(path: Path) -> None:
    """Remove a tree containing git's read-only object files."""

    def _chmod_and_retry(func: object, target: str, _exc: object) -> None:
        try:
            Path(target).chmod(0o700)
        except OSError:
            return
        if callable(func):
            try:
                func(target)
            except OSError:
                pass

    # README declares Python 3.11+; `onexc` is 3.12+. The callback ignores its third argument,
    # so it serves both hooks unchanged.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_chmod_and_retry)
    else:
        shutil.rmtree(path, onerror=_chmod_and_retry)


class _ArchiveLab(unittest.TestCase):
    """A tiny real git repository, rebuilt per test so no probe inherits another's archive."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="identity-lab-", ignore_cleanup_errors=True)
        self.lab = Path(self._tmp.name) / "repo"
        (self.lab / "docs" / "process").mkdir(parents=True)
        (self.lab / "docs" / "process" / "GOV.md").write_text(_GOVERNED, encoding="utf-8")
        (self.lab / "docs" / "process" / "RULE.md").write_text(_UNGOVERNED, encoding="utf-8")
        _git(self.lab, "init", "-q")
        self.commit()

    def tearDown(self) -> None:
        _force_rmtree(Path(self._tmp.name))
        self._tmp.cleanup()

    def commit(self, message: str = "lab") -> str:
        _git(self.lab, "add", "-A")
        _git(
            self.lab, "-c", "user.name=lab", "-c", "user.email=lab@local",
            "commit", "-q", "--allow-empty", "-m", message,
        )
        return _git(self.lab, "rev-parse", "HEAD")

    def corpus(self) -> Corpus:
        """A FRESH corpus each call — ``Corpus`` caches file text and the tracked listing."""
        return Corpus(root=self.lab)

    def cut(self, rel: str, date: str = "2026-08-24") -> archive.Entry:
        text = (self.lab / rel).read_text(encoding="utf-8")
        header = parse_header(text)
        entry = archive.cut(self.lab, rel, header=header, cut_on=date)
        self.commit(f"cut {rel}")
        return entry

    def run_guard(self) -> object:
        return identity_guard.run(self.corpus())

    def assert_refused(self, result: object, needle: str) -> None:
        findings = getattr(result, "findings", [])
        blob = " ".join(f"{f.path} {f.message} {f.evidence}" for f in findings)
        self.assertEqual(
            getattr(result, "status", None),
            Status.FAIL,
            f"guard passed on a planted defect (checked={getattr(result, 'checked', '?')})",
        )
        self.assertIn(needle, blob)

    def assert_clean(self, result: object) -> None:
        findings = getattr(result, "findings", [])
        blob = " ".join(f"{f.path} {f.message}" for f in findings)
        self.assertEqual(getattr(result, "status", None), Status.PASS, f"unexpected: {blob}")


# =================================================================================================
# A-2 — a frozen document that is edited is refused, and un-editing it is accepted again.
# =================================================================================================


class FrozenDocumentDrift(_ArchiveLab):
    def test_frozen_ungoverned_document_edited_is_refused(self) -> None:
        """The archive, not a field, decides whether a document is still frozen."""
        self.cut("docs/process/RULE.md")
        doc_id = identity.slug_for_path("docs/process/RULE.md")
        self.assertTrue(archive.freeze_state(self.lab, "docs/process/RULE.md", doc_id).frozen)
        self.assert_clean(self.run_guard())

        target = self.lab / "docs" / "process" / "RULE.md"
        original = target.read_bytes()
        target.write_bytes(original + b"an edit nobody cut a version for\n")
        self.commit("edit a frozen document")
        state = archive.freeze_state(self.lab, "docs/process/RULE.md", doc_id)
        self.assertFalse(state.frozen, "an edited frozen document still reported frozen")
        self.assertIn("differ", state.reason)

        # ...and green again once the bytes are put back. Both directions, one probe.
        target.write_bytes(original)
        self.commit("restore")
        self.assertTrue(archive.freeze_state(self.lab, "docs/process/RULE.md", doc_id).frozen)
        self.assert_clean(self.run_guard())

    def test_frozen_governed_document_edited_is_refused_by_the_guard(self) -> None:
        """A header claiming ``revision: 0`` is a claim the guard refutes from the bytes."""
        self.cut("docs/process/GOV.md")
        self.assert_clean(self.run_guard())

        target = self.lab / "docs" / "process" / "GOV.md"
        target.write_text(
            target.read_text(encoding="utf-8") + "\nAn edit with no revision bump.\n",
            encoding="utf-8",
        )
        self.commit("edit body, leave revision: 0")
        self.assert_refused(self.run_guard(), "revision: 0")

        # Declaring the edit — bumping revision — is the compliant way out, and is accepted.
        text = target.read_text(encoding="utf-8").replace("revision: 0", "revision: 1")
        target.write_text(text, encoding="utf-8")
        self.commit("bump revision")
        self.assert_clean(self.run_guard())

    def test_frozen_archive_tampering_is_refused(self) -> None:
        """A snapshot edited after the cut no longer matches the sha256 the history recorded."""
        entry = self.cut("docs/process/RULE.md")
        doc_id = identity.slug_for_path("docs/process/RULE.md")
        snapshot = archive.snapshot_in(self.lab, doc_id, entry.version)
        assert snapshot is not None
        self.assert_clean(self.run_guard())

        snapshot.write_bytes(snapshot.read_bytes() + b"tampered\n")
        self.commit("tamper with the archive")
        self.assert_refused(self.run_guard(), "no longer match the sha256")


# =================================================================================================
# A-6 — supersession is derived, and cutting a new version never rewrites an old one.
# =================================================================================================


class Supersession(_ArchiveLab):
    def test_supersede_leaves_the_previous_snapshot_byte_identical(self) -> None:
        first = self.cut("docs/process/RULE.md", date="2026-08-24")
        doc_id = identity.slug_for_path("docs/process/RULE.md")
        v1 = archive.snapshot_in(self.lab, doc_id, 1)
        assert v1 is not None
        before = v1.read_bytes()

        target = self.lab / "docs" / "process" / "RULE.md"
        target.write_text(target.read_text(encoding="utf-8") + "\nsecond generation\n", encoding="utf-8")
        second = self.cut("docs/process/RULE.md", date="2026-08-25")

        self.assertEqual(second.version, first.version + 1)
        self.assertEqual(v1.read_bytes(), before, "cutting v2 rewrote the v1 snapshot")
        self.assertNotEqual(first.sha256, second.sha256)
        self.assertEqual(archive.versions_on_disk(self.lab, doc_id), [1, 2])
        self.assert_clean(self.run_guard())

    def test_supersede_refuses_a_cut_that_would_change_nothing(self) -> None:
        """`OG-197` — a cut of an unchanged document is not a version, it is a duplicate.

        Found by making the mistake: a rule-layer edit touched a different file, the archived
        document was cut anyway, and v5 landed byte-identical to v4 — same sha256, two
        directories, one document state. The supersession derivation would then report v4
        superseded by a copy of itself.
        """
        first = self.cut("docs/process/RULE.md")
        doc_id = identity.slug_for_path("docs/process/RULE.md")
        with self.assertRaises(archive.ArchiveError) as caught:
            archive.cut(self.lab, "docs/process/RULE.md", header=None, cut_on="2026-08-25")
        self.assertIn("already frozen", str(caught.exception))
        self.assertEqual(archive.versions_on_disk(self.lab, doc_id), [first.version])

        # ...and the moment the bytes actually differ, the cut is allowed again. Both directions,
        # so this proves a condition rather than a refusal.
        target = self.lab / "docs" / "process" / "RULE.md"
        target.write_text(target.read_text(encoding="utf-8") + "\nreal change\n", encoding="utf-8")
        second = self.cut("docs/process/RULE.md", date="2026-08-25")
        self.assertEqual(second.version, first.version + 1)
        self.assertNotEqual(second.sha256, first.sha256)

    def test_supersede_is_derived_and_not_stored_anywhere(self) -> None:
        """Rule 2: nothing writes 'superseded' down, so nothing can go stale about it."""
        self.cut("docs/process/RULE.md")
        target = self.lab / "docs" / "process" / "RULE.md"
        target.write_text(target.read_text(encoding="utf-8") + "\nmore\n", encoding="utf-8")
        self.cut("docs/process/RULE.md", date="2026-08-25")

        doc_id = identity.slug_for_path("docs/process/RULE.md")
        history = archive.history_path(self.lab, doc_id).read_text(encoding="utf-8")
        self.assertNotIn("superseded: ", history)
        versions = archive.versions_on_disk(self.lab, doc_id)
        latest = archive.latest_version(self.lab, doc_id)
        self.assertEqual([v for v in versions if v < latest], [1])

    def test_supersede_history_and_disk_cannot_disagree(self) -> None:
        """A-7: a version directory with no history row is refused."""
        self.cut("docs/process/RULE.md")
        doc_id = identity.slug_for_path("docs/process/RULE.md")
        orphan = archive.version_dir(self.lab, doc_id, 2)
        orphan.mkdir(parents=True)
        (orphan / "RULE.md").write_text("a snapshot nobody recorded\n", encoding="utf-8")
        self.commit("plant an unrecorded version")
        self.assert_refused(self.run_guard(), "records no row for it")


# =================================================================================================
# A-4 / A-5 — a verified claim, and the stamp that is supposed to back it.
# =================================================================================================


class VerifiedStateClaim(_ArchiveLab):
    def test_verified_state_without_a_stamp_is_refused(self) -> None:
        target = self.lab / "docs" / "process" / "GOV.md"
        text = target.read_text(encoding="utf-8")
        clean = validate_header(parse_header(text), source=text)
        self.assertEqual([f.message for f in clean if f.gate == identity.GATE], [])

        claimed = text.replace("last_reviewed: 2026-08-24", "last_reviewed: 2026-08-24\nverified_state: verified")
        findings = [f for f in validate_header(parse_header(claimed), source=claimed) if f.blocking]
        self.assertTrue(
            any("no content-certifying stamp" in f.message for f in findings),
            f"a bare verified claim was accepted: {[f.message for f in findings]}",
        )

    def test_verified_state_with_a_live_stamp_is_accepted(self) -> None:
        """The accepted direction must be REACHABLE, or the gate only ever fires.

        The stamp names the commit whose body it certifies. Writing the stamp changes the file, so
        the file at that commit cannot contain the stamp — which is exactly why the comparison
        strips stamp lines from both sides (`identity.body_matches`).
        """
        target = self.lab / "docs" / "process" / "GOV.md"
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "last_reviewed: 2026-08-24", "last_reviewed: 2026-08-24\nverified_state: verified"
            ),
            encoding="utf-8",
        )
        certified = self.commit("the body being certified")

        target.write_text(
            f"<!-- artifact-hardened: Approved @ {certified[:7]} on 2026-08-24 via three-pass-v1 -->\n"
            + target.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.commit("stamp it")
        self.assert_clean(self.run_guard())

    def test_stamp_drift_on_a_verified_document_is_refused(self) -> None:
        """A-5, end to end: the stamp gate rejects a stamp on an edited body."""
        target = self.lab / "docs" / "process" / "GOV.md"
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "last_reviewed: 2026-08-24", "last_reviewed: 2026-08-24\nverified_state: verified"
            ),
            encoding="utf-8",
        )
        certified = self.commit("the body being certified")
        target.write_text(
            f"<!-- artifact-hardened: Approved @ {certified[:7]} on 2026-08-24 via three-pass-v1 -->\n"
            + target.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.commit("stamp it")
        self.assert_clean(self.run_guard())

        # Now edit the body the stamp certifies. The stamp itself is untouched.
        target.write_text(
            target.read_text(encoding="utf-8") + "\nA sentence added after the stamp.\n",
            encoding="utf-8",
        )
        self.commit("edit a stamped body")
        self.assert_refused(self.run_guard(), "no longer covers this body")

    def test_stamp_drift_is_not_triggered_by_the_stamp_itself(self) -> None:
        """The narrowed comparison's NEW edge: what is the widest change that still passes?

        Answer: only the stamp lines. Anything in the body — one added character — must fail. This
        probe pins that boundary so a future widening of the strip rule cannot quietly let real
        edits through (`RULES.md` Rule 1's corollary).
        """
        body = "# Doc\n\nOne sentence.\n"
        stamped = (
            "<!-- artifact-hardened: Approved @ abc1234 on 2026-08-24 via three-pass-v1 -->\n" + body
        )
        self.assertTrue(identity.body_matches(body, stamped))
        self.assertTrue(
            identity.body_matches(
                stamped,
                stamped.replace("abc1234", "def5678").replace("Approved", "Approved With Known Risks"),
            ),
            "changing the stamp's own fields is judged by reading the stamp, not by body drift",
        )
        self.assertFalse(identity.body_matches(stamped, stamped.replace("One sentence.", "One sentence!")))
        self.assertFalse(identity.body_matches(stamped, stamped + "\n"))


# =================================================================================================
# A-3 — the header contract: dataclass, parser and schema all agree.
# =================================================================================================


class IdentityHeaderContract(unittest.TestCase):
    def test_identity_schema_matches_the_dataclass(self) -> None:
        """A field added to one and not the other is exactly the drift this asserts against.

        Derived from ``identity.IDENTITY_FIELDS`` rather than from a literal list here, so adding a
        fifth identity field puts it under this assertion without anyone remembering to.
        """
        schema = json.loads(
            (_ROOT / "tools" / "docgen" / "schemas" / "doc_header.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(identity.IDENTITY_FIELDS, "the identity field set is empty")
        declared = set(DocHeader.__dataclass_fields__)
        for name in identity.IDENTITY_FIELDS:
            self.assertIn(name, declared, f"{name} is in IDENTITY_FIELDS but not on DocHeader")
            self.assertIn(name, schema["properties"], f"{name} is on DocHeader but not in the schema")

    def test_identity_defaults_keep_every_pre_existing_document_valid(self) -> None:
        """Identity is opt-in: a document that declares none of the four fields stays clean."""
        header = parse_header(_GOVERNED)
        self.assertEqual(header.version, 0)
        self.assertEqual(header.revision, 0)
        self.assertEqual(header.produced_by, "")
        self.assertIs(header.verified_state, VerifiedState.UNVERIFIED)
        self.assertFalse(header.is_versioned)
        self.assertFalse(header.claims_frozen)
        self.assertEqual(identity.header_findings(header, _GOVERNED), [])

    def test_identity_version_as_yaml_boolean_is_refused(self) -> None:
        """``bool`` is an ``int`` in Python, so ``version: true`` must be refused explicitly."""
        doc = _GOVERNED.replace("last_reviewed: 2026-08-24", "last_reviewed: 2026-08-24\nversion: true")
        findings = validate_header(parse_header(doc), source=doc)
        self.assertTrue(
            any("YAML boolean" in f.message for f in findings),
            f"version: true was accepted: {[f.message for f in findings]}",
        )
        self.assertEqual(parse_header(doc).version, 0, "a boolean coerced to a real version")

    def test_identity_revision_without_a_version_is_refused(self) -> None:
        doc = _GOVERNED.replace("last_reviewed: 2026-08-24", "last_reviewed: 2026-08-24\nrevision: 4")
        findings = identity.header_findings(parse_header(doc), doc)
        self.assertTrue(any("unversioned document" in f.message for f in findings))

    def test_identity_archive_id_refuses_a_path_escape(self) -> None:
        """An archive id becomes a directory name, so it may never climb out of the archive."""
        for hostile in ("../escape", "/abs", "..", "", "a/b"):
            self.assertFalse(identity.is_safe_id(hostile), f"{hostile!r} accepted as an id")
        evil = DocHeader(
            id="../../etc", classification=parse_header(_GOVERNED).classification,
            title="t", audience="technical", owner="o", status="draft",
            export_allowed=True, surface=parse_header(_GOVERNED).surface,
            last_reviewed="2026-08-24",
        )
        self.assertEqual(identity.archive_id("docs/process/GOV.md", evil), "docs__process__GOV")


# =================================================================================================
# A-1 — the live corpus: the documents this phase froze are frozen, measured not asserted.
# =================================================================================================


class LiveCorpusFreeze(unittest.TestCase):
    def test_frozen_documents_in_this_corpus_match_their_snapshots(self) -> None:
        """The subject set is DERIVED from the archive and asserted non-empty (`L-37`).

        Naming the three documents here would be borrowing a condition: the day a fourth is frozen
        the probe would silently stop covering it, and the day one is legitimately superseded the
        probe would go red for a reason that is not a defect.
        """
        root = _ROOT
        ids = archive.archived_ids(root)
        self.assertTrue(ids, "nothing is archived, so this probe measured nothing")
        for doc_id in ids:
            source_rel = archive.live_path(root, doc_id)
            self.assertTrue(source_rel, f"{doc_id} records no live document")
            self.assertEqual(archive.audit_id(root, doc_id), [], f"{doc_id} archive is inconsistent")
            state = archive.freeze_state(root, source_rel, doc_id)
            self.assertTrue(state.versioned, f"{doc_id} has no version on disk")
            self.assertTrue(state.frozen, f"{doc_id}: {state.reason}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
