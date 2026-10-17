"""Counter-examples for the project index's classification gate.

``PROJECT_INDEX.json`` is a TRACKED file. Until ``index.RegistrationRefused`` existed there was no
classification check anywhere under ``tools/project_index/``, so ``register`` wrote a confidential
document's **path, title and summary** straight into it, and both commit-time gates passed the
result: the placement gate judges the *document's* blob (gitignored, never staged), and the leak is
an English paraphrase inside a ``.json``, which carries no secret pattern.

Every test here fails if the gate in ``register_artifact`` is removed, and the ALLOW-side tests fail
if it is made too wide — a gate that refuses ordinary public artifacts would be reverted within a
day, which is its own kind of hole.

**Imports the implementation directly, not through the ``tools.project_index.index`` shim
(2026-09-24).** The real registry now lives at ``tools.docgen.artifact_index`` — see that
module's and ``tools/project_index/index.py``'s docstrings. This suite patches the private
``_index_path`` and calls ``register_artifact``/``_load`` in the same breath, which only works
when the patch target and the called function are defined in the SAME module (Python resolves a
function's globals against its own ``__globals__``, not the caller's import alias) — so this file
imports ``tools.docgen.artifact_index`` under the local name ``index`` rather than going through
the shim, which would silently patch a name nothing reads.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tools.docgen import artifact_index as index
from tools.docgen import engine_config
from tools.docgen.hooks.staged_content_scanner import classify_file
from tools.project_index import cli

_SECRET_TITLE = "Acquisition target shortlist Q4"
_SECRET_SUMMARY = "Board-only shortlist: Acme, Zenith, Northwind"

_VAULT_TIER_DOC = """---
id: SEC-01
title: Acquisition target shortlist Q4
classification: secret
surface: none
status: final
export_allowed: false
---
Board-only shortlist.
"""

_PUBLIC_DOC = """---
id: PUB-01
title: Public overview
classification: public
surface: github
status: final
export_allowed: true
---
Nothing sensitive.
"""


class ProjectIndexGateCase(unittest.TestCase):
    """A throwaway host root with a vault in it, and the index pointed inside it."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.index_file = self.root / "PROJECT_INDEX.json"
        (self.root / "docs" / "confidential").mkdir(parents=True)
        (self.root / "docs" / "public-notes").mkdir(parents=True)
        (self.root / "examples").mkdir()
        (self.root / "docs" / "confidential" / "SECRET-NOTES.md").write_text(
            _VAULT_TIER_DOC, encoding="utf-8"
        )
        # A HEADER-LESS artifact inside the vault, and the single most important fixture here.
        # Pointing the containment probes at SECRET-NOTES.md instead was a silent hole in THIS
        # SUITE: the header route's own message ends "...may only live in the confidential vault",
        # so `assertIn("confidential vault", ...)` passed for a *classified-document* refusal even
        # when containment was disabled. Measured — with `_is_vault_path`'s `resolve()` route
        # deleted, all five vault spellings still "passed". A rendered chart of board data carries
        # no doc-system header at all, so `classify_file` returns None on it and **containment is
        # the only thing that can refuse it**.
        (self.root / "docs" / "confidential" / "board-chart.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><text>Q4 shortlist</text></svg>',
            encoding="utf-8",
        )
        (self.root / "examples" / "gallery.html").write_text(
            "<!doctype html><title>Gallery</title>", encoding="utf-8"
        )
        patcher = unittest.mock.patch.object(
            index, "_index_path", lambda: self.index_file
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _register(self, **kwargs: object) -> None:
        defaults: dict[str, object] = {
            "id": "probe",
            "path": "",
            "type": "document",
            "title": _SECRET_TITLE,
            "summary": _SECRET_SUMMARY,
        }
        defaults.update(kwargs)
        index.register_artifact(index.Artifact(**defaults))  # type: ignore[arg-type]

    def _index_text(self) -> str:
        return self.index_file.read_text(encoding="utf-8") if self.index_file.is_file() else ""

    def assert_refused_by_containment(self, exc: BaseException) -> None:
        """Assert the refusal came from `_is_vault_path`, not from the header check.

        Both messages contain the substring "confidential vault", so a bare `assertIn` cannot tell
        the two routes apart — the reason every containment probe in this file once passed against
        a build with containment removed. Discriminate on the verb, and forbid the other route's.
        """
        message = str(exc)
        self.assertIn("resolves inside the confidential vault", message)
        self.assertNotIn("is not a public document", message)


class VaultContainmentFollowsARelocatedIndex(unittest.TestCase):
    """Found in a code review of the copy (P1). An earlier fix made a registered path relative to the
    INDEX's own directory, but ``_is_vault_path`` still compared it against the vault as if the
    index sat at the host root: the textual route saw ``../../confidential/...`` (no ``docs/``
    prefix) and the filesystem route resolved the vault as ``<index-dir>/docs/confidential``.
    With the index relocated below the host root, a headerless artifact inside the REAL vault
    registered into the tracked public index. Both routes now anchor the vault at
    ``engine_config.host_root()``.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.host = Path(tmp.name).resolve()
        (self.host / "docs" / "confidential").mkdir(parents=True)
        (self.host / "docs" / "design" / "doc-system").mkdir(parents=True)
        (self.host / "examples").mkdir()
        (self.host / "docs" / "confidential" / "board-chart.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><text>Q4 shortlist</text></svg>',
            encoding="utf-8",
        )
        (self.host / "examples" / "gallery.html").write_text(
            "<!doctype html><title>Gallery</title>", encoding="utf-8"
        )
        self.index_file = self.host / "docs" / "design" / "doc-system" / "PROJECT_INDEX.json"

        prev = os.environ.get("ENGINE_HOST_ROOT")
        os.environ["ENGINE_HOST_ROOT"] = str(self.host)
        engine_config.host_root.cache_clear()

        def _restore() -> None:
            if prev is None:
                os.environ.pop("ENGINE_HOST_ROOT", None)
            else:
                os.environ["ENGINE_HOST_ROOT"] = prev
            engine_config.host_root.cache_clear()

        self.addCleanup(_restore)
        patcher = unittest.mock.patch.object(index, "_index_path", lambda: self.index_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _register(self, path: str) -> None:
        index.register_artifact(
            index.Artifact(
                id="probe", path=path, type="document", title=_SECRET_TITLE, summary=_SECRET_SUMMARY
            )
        )

    def _assert_refused_and_unwritten(self, path: str) -> None:
        with self.assertRaises(index.RegistrationRefused) as caught:
            self._register(path)
        self.assertIn("resolves inside the confidential vault", str(caught.exception))
        written = self.index_file.read_text(encoding="utf-8") if self.index_file.is_file() else ""
        self.assertNotIn(_SECRET_TITLE, written)

    def test_a_not_yet_built_vault_path_climbing_out_of_the_index_dir_is_refused(self) -> None:
        # Lexical route: the file does not exist, so only the host-relative spelling can catch it.
        self._assert_refused_and_unwritten("../../confidential/board-future.svg")

    def test_an_existing_headerless_vault_artifact_is_refused(self) -> None:
        self._assert_refused_and_unwritten("../../confidential/board-chart.svg")

    def test_an_absolute_path_into_the_host_vault_is_refused(self) -> None:
        # Filesystem route: the old code resolved the vault under the index directory.
        self._assert_refused_and_unwritten(
            str(self.host / "docs" / "confidential" / "board-chart.svg")
        )

    def test_a_public_artifact_still_registers_through_a_relocated_index(self) -> None:
        # Positive control: the fix must not refuse everything outside the index directory.
        self._register("../../../examples/gallery.html")
        entries = index.list_artifacts()
        self.assertEqual([e["path"] for e in entries], ["../../../examples/gallery.html"])


class VaultPathsAreRefused(ProjectIndexGateCase):
    def test_the_measured_leak_is_refused_and_writes_nothing(self) -> None:
        """The exact reproduction from the finding, end to end."""
        with self.assertRaises(index.RegistrationRefused) as caught:
            self._register(id="leak-1", path="docs/confidential/SECRET-NOTES.md", status="final")
        self.assert_refused_by_containment(caught.exception)
        # Not "the entry was overwritten later" — the file was never created at all.
        self.assertFalse(self.index_file.exists())

    def test_no_field_of_a_vault_document_reaches_the_index(self) -> None:
        """Path was only ONE of four leaking fields; title and summary are the real disclosure."""
        with self.assertRaises(index.RegistrationRefused):
            self._register(path="docs/confidential/SECRET-NOTES.md")
        text = self._index_text()
        for leaked in (_SECRET_TITLE, _SECRET_SUMMARY, "SECRET-NOTES", "confidential"):
            self.assertNotIn(leaked, text)

    def test_every_spelling_of_the_vault_is_refused(self) -> None:
        """The CLASS, not the instance (``docs/process/RULES.md`` Rule 1).

        Every case names ``board-chart.svg`` — the header-less fixture — so ``classify_file``
        returns ``None`` for all of them and **only containment can produce a refusal**. Each was
        run against deliberately weakened builds rather than imagined: dropping ``_is_vault_path``'s
        ``resolve()`` route lets *symlinked file*, *symlinked directory* and *absolute* through, and
        making ``_starts_with`` case-sensitive lets *case-varied* through — both measured as real
        test failures, not assumed.

        ⚠ *dotdot re-entry* is the honest exception, and it is recorded rather than dressed up: no
        probe here kills a build that stops normalising ``..`` textually, because ``resolve()``
        normalises it too, so the two routes catch that spelling **independently**. Measured — for
        ``docs/../docs/confidential/board-chart.svg`` the textual route answers ``True`` and the
        filesystem route answers ``True``. The case is kept because the redundancy is the point (a
        path this gate cannot ``resolve()`` fails closed and the textual route is what remains), but
        nobody should read a green run here as evidence that the ``..`` handling is load-bearing.
        """
        (self.root / "docs" / "public-notes" / "via-symlink").symlink_to(
            self.root / "docs" / "confidential", target_is_directory=True
        )
        (self.root / "docs" / "public-notes" / "innocuous.svg").symlink_to(
            self.root / "docs" / "confidential" / "board-chart.svg"
        )
        vault = self.root / "docs" / "confidential"
        cases = {
            "dotdot re-entry": "docs/../docs/confidential/board-chart.svg",
            "absolute": str(vault / "board-chart.svg"),
            "symlinked directory": "docs/public-notes/via-symlink/board-chart.svg",
            "symlinked file": "docs/public-notes/innocuous.svg",
            "case-varied": "DOCS/Confidential/board-chart.svg",
            "windows separators": "docs\\confidential\\board-chart.svg",
            "redundant separators": "docs//confidential//./board-chart.svg",
            "leading whitespace": "  docs/confidential/board-chart.svg",
            "trailing slash": "docs/confidential/",
            "the vault directory itself": "docs/confidential",
            # An artifact may legitimately be registered before it is built (``verify`` reports the
            # gap), so a not-yet-existing file must be judged on its LOCATION or the gate is a
            # "touch the file first" speed bump.
            "not built yet": "docs/confidential/NOT-BUILT-YET.svg",
        }
        for label, path in cases.items():
            with self.subTest(label), self.assertRaises(index.RegistrationRefused) as caught:
                self._register(path=path)
            self.assert_refused_by_containment(caught.exception)
        self.assertFalse(self.index_file.exists())

    def test_an_unreadable_named_file_is_refused_not_assumed_public(self) -> None:
        target = self.root / "docs" / "public-notes" / "unreadable.md"
        target.write_text(_VAULT_TIER_DOC, encoding="utf-8")
        with (
            unittest.mock.patch.object(Path, "open", side_effect=OSError("denied")),
            self.assertRaises(index.RegistrationRefused) as caught,
        ):
            self._register(path="docs/public-notes/unreadable.md")
        self.assertIn("could not be read", str(caught.exception))


class TheGatesOwnEdgeAfterNarrowing(ProjectIndexGateCase):
    """Probes written against the FINISHED gate, not against the original leak.

    Once "no vault path, no classified header" is enforced, the widest remaining input is a
    document the shared classification authority cannot *read* — and the honest boundary of this
    gate is that containment survives that while header-parsing does not.
    """

    def test_containment_still_refuses_a_document_the_header_parser_cannot_read(self) -> None:
        r"""Location beats encoding — the half of the residual this gate actually owns.

        ``normalise_for_scanning`` is ADDITIVE (raw bytes, then readable views appended) while both
        header patterns are ``\A``-anchored, so a UTF-16 ``classification: secret`` document reads
        as header-less to ``classify_file``. Measured in the working tree 2026-08-23: the byte
        sequence below, placed OUTSIDE the vault, yields ``classify_file(...) -> None``. That blind
        spot lives in the shared authority, not here, and fixing it here would mean growing a
        second private notion of "classified" — the drift this gate was built to avoid.

        What this gate owes regardless: ``_is_vault_path`` is containment, and containment never
        parses a byte. The same undecodable document inside the vault is refused, and refused *for
        the containment reason* — asserted below so a future rewrite cannot quietly downgrade this
        path to header-parsing and inherit the blind spot.
        """
        undecodable = _VAULT_TIER_DOC.encode("utf-16")
        (self.root / "docs" / "confidential" / "u16.md").write_bytes(undecodable)
        with self.assertRaises(index.RegistrationRefused) as caught:
            self._register(path="docs/confidential/u16.md")
        self.assert_refused_by_containment(caught.exception)
        self.assertFalse(self.index_file.exists())

    def test_climbing_out_of_the_project_does_not_escape_the_header_check(self) -> None:
        """``..`` past the artifact root leaves the vault behind, so containment cannot help and
        the header check is the only thing left standing."""
        outside = self.root.parent / (self.root.name + "-outside")
        outside.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, outside, True)
        (outside / "s.md").write_text(_VAULT_TIER_DOC, encoding="utf-8")
        with self.assertRaises(index.RegistrationRefused) as caught:
            self._register(path=f"../{outside.name}/s.md")
        self.assertIn("not a public document", str(caught.exception))

    def test_a_header_one_byte_off_the_start_is_not_a_header(self) -> None:
        r"""Bounds the ``_HEADER_READ_LIMIT`` question so nobody re-opens it as a hole.

        Both header patterns are ``\A``-anchored: a ``classification: secret`` block at byte 1 is
        already invisible to the shared authority, so the read cap cannot be hiding one at byte
        300000. Raising the cap would buy nothing; this records why.
        """
        for offset in (1, 4096):
            with self.subTest(offset=offset):
                self.assertIsNone(
                    classify_file("d/x.md", "x" * offset + _VAULT_TIER_DOC, self.root)
                )


class ClassifiedDocumentsOutsideTheVaultAreRefused(ProjectIndexGateCase):
    def test_front_matter_header_decides(self) -> None:
        (self.root / "docs" / "public-notes" / "misplaced.md").write_text(
            _VAULT_TIER_DOC, encoding="utf-8"
        )
        with self.assertRaises(index.RegistrationRefused) as caught:
            self._register(path="docs/public-notes/misplaced.md")
        self.assertIn("not a public document", str(caught.exception))

    def test_legacy_html_comment_syntax_decides_too(self) -> None:
        """The foreign ``<!-- classification: X -->`` vocabulary this tree still contains."""
        (self.root / "docs" / "public-notes" / "legacy.md").write_text(
            "<!-- classification: INTERNAL -->\nInternal only.\n", encoding="utf-8"
        )
        with self.assertRaises(index.RegistrationRefused):
            self._register(path="docs/public-notes/legacy.md")


class PublicArtifactsStillRegister(ProjectIndexGateCase):
    """The other half of the gate. A refusal that also refuses real work is not a fix."""

    def test_an_ordinary_rendered_artifact_registers(self) -> None:
        self._register(
            id="gallery", path="examples/gallery.html", title="Capability Gallery", summary="ok"
        )
        payload = json.loads(self._index_text())
        self.assertEqual([a["id"] for a in payload["artifacts"]], ["gallery"])
        self.assertEqual(payload["artifacts"][0]["path"], "examples/gallery.html")

    def test_a_public_document_registers(self) -> None:
        (self.root / "docs" / "public-notes" / "overview.md").write_text(
            _PUBLIC_DOC, encoding="utf-8"
        )
        self._register(path="docs/public-notes/overview.md", title="Public overview", summary="ok")
        self.assertIn("overview.md", self._index_text())

    def test_a_header_less_file_registers(self) -> None:
        """``parse_header`` returns the SECRET sentinel for header-less text; treating that as a
        classified document would refuse every README and every rendered artifact in the tree."""
        (self.root / "docs" / "public-notes" / "plain.md").write_text(
            "# Just notes\nNo header.\n", encoding="utf-8"
        )
        self._register(path="docs/public-notes/plain.md", title="Notes", summary="ok")
        self.assertIn("plain.md", self._index_text())

    def test_an_artifact_that_does_not_exist_yet_registers(self) -> None:
        self._register(path="examples/not-built-yet.svg", title="Planned", summary="ok")
        self.assertIn("not-built-yet.svg", self._index_text())

    def test_a_vault_lookalike_sibling_is_not_the_vault(self) -> None:
        """``docs/confidential-notes/`` shares a prefix with the vault and is NOT inside it —
        containment, not string prefix matching."""
        self._register(path="docs/confidential-notes/x.md", title="Sibling", summary="ok")
        self.assertIn("confidential-notes", self._index_text())

    def test_updating_an_existing_public_entry_still_works(self) -> None:
        self._register(id="gallery", path="examples/gallery.html", title="One", summary="ok")
        self._register(id="gallery", path="examples/gallery.html", title="Two", summary="ok")
        payload = json.loads(self._index_text())
        self.assertEqual(len(payload["artifacts"]), 1)
        self.assertEqual(payload["artifacts"][0]["title"], "Two")


class CliReportsTheRefusalRatherThanCrashing(ProjectIndexGateCase):
    def test_register_of_a_vault_path_exits_2_and_writes_nothing(self) -> None:
        rc = cli.main(
            [
                "register",
                "--id", "leak-1",
                "--path", "docs/confidential/SECRET-NOTES.md",
                "--type", "document",
                "--title", _SECRET_TITLE,
                "--summary", _SECRET_SUMMARY,
            ]
        )
        # 2, not 1: `verify` already uses 1 for "the index and the filesystem disagree".
        self.assertEqual(rc, 2)
        self.assertFalse(self.index_file.exists())

    def test_register_of_a_public_artifact_exits_0(self) -> None:
        rc = cli.main(
            [
                "register",
                "--id", "gallery",
                "--path", "examples/gallery.html",
                "--type", "document",
                "--title", "Capability Gallery",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertIn("gallery.html", self._index_text())


if __name__ == "__main__":
    unittest.main()
