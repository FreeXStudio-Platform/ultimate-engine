"""Counter-examples for engine configuration resolution.

Both defects here were live and both were reachable by a one-character edit to a config file.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path, PurePosixPath

from tools.docgen import engine_config


class PathFieldNeverReturnsNone(unittest.TestCase):
    """``_field`` is typed ``str | None`` and genuinely returns ``None``.

    Every caller joined the result onto a ``Path``, so a config that blanked a key produced
    ``host_root() / None`` — a ``TypeError`` at IMPORT time, taking down every entry point in the
    package including ``tools.health`` itself, on a file that is valid JSON.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._prev = os.environ.get("ENGINE_CONFIG_PATH")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self._prev is None:
            os.environ.pop("ENGINE_CONFIG_PATH", None)
        else:
            os.environ["ENGINE_CONFIG_PATH"] = self._prev
        engine_config._raw_config.cache_clear()

    def _with_config(self, payload: object) -> None:
        path = Path(self._tmp.name) / "engine.config.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        os.environ["ENGINE_CONFIG_PATH"] = str(path)
        engine_config._raw_config.cache_clear()

    def test_blank_value_falls_back_to_the_documented_default(self) -> None:
        self._with_config({"docSystem": {"confidentialDir": {"value": ""}}})
        self.assertEqual(engine_config._path_field("docSystem", "confidentialDir", "docs/confidential"),
                         "docs/confidential")

    def test_null_value_falls_back_to_the_documented_default(self) -> None:
        self._with_config({"docSystem": {"confidentialDir": {"value": None}}})
        self.assertEqual(engine_config._path_field("docSystem", "confidentialDir", "docs/confidential"),
                         "docs/confidential")

    def test_confidential_dir_relative_is_never_empty(self) -> None:
        """An empty string here made ``PurePosixPath('')`` == ``PurePosixPath('.')``, so the L14
        containment test was true for EVERY path in the repository — one blank character silently
        disabled the placement gate while the hook printed its ordinary affirmative line."""
        self._with_config({"docSystem": {"confidentialDir": {"value": ""}}})
        self.assertNotEqual(engine_config.confidential_dir_relative().strip(), "")


class RuleLayerRelocatesAsAUnit(unittest.TestCase):
    """``ENGINE_DOC_SYSTEM_DIR`` used to move the taxonomy and leave the manifest and VERSION.json
    behind — a silently SPLIT rule layer, in which the hash gate and the manifest gate consult
    different directories."""

    def setUp(self) -> None:
        self._prev = os.environ.get("ENGINE_DOC_SYSTEM_DIR")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self._prev is None:
            os.environ.pop("ENGINE_DOC_SYSTEM_DIR", None)
        else:
            os.environ["ENGINE_DOC_SYSTEM_DIR"] = self._prev

    def test_children_follow_the_doc_system_dir(self) -> None:
        os.environ["ENGINE_DOC_SYSTEM_DIR"] = "custom/rules"
        base = engine_config.doc_system_dir()
        for resolved in (engine_config.doc_manifest_path(), engine_config.version_json_path()):
            self.assertEqual(resolved.parent, base, f"{resolved} did not follow {base}")

    def test_a_path_with_a_separator_stays_host_root_relative(self) -> None:
        """Back-compatibility: a config spelling out the full path must keep working."""
        os.environ["ENGINE_DOC_SYSTEM_DIR"] = "custom/rules"
        os.environ["ENGINE_DOC_MANIFEST_PATH"] = "some/where/DOC_MANIFEST.md"
        self.addCleanup(os.environ.pop, "ENGINE_DOC_MANIFEST_PATH", None)
        resolved = engine_config.doc_manifest_path()
        self.assertEqual(resolved, engine_config.host_root() / "some/where/DOC_MANIFEST.md")
        self.assertNotEqual(resolved.parent, engine_config.doc_system_dir())

    def test_an_absolute_override_is_used_as_is(self) -> None:
        os.environ["ENGINE_DOC_SYSTEM_DIR"] = "custom/rules"
        os.environ["ENGINE_VERSION_JSON_PATH"] = "/tmp/elsewhere/VERSION.json"
        self.addCleanup(os.environ.pop, "ENGINE_VERSION_JSON_PATH", None)
        self.assertEqual(engine_config.version_json_path(), Path("/tmp/elsewhere/VERSION.json"))


class ProjectIndexPathIsHostRootRelativeNotCwdRelative(unittest.TestCase):
    """dh36 (2026-09-24). ``project_index_path()`` is the one path field in this module that did
    NOT follow ``RuleLayerRelocatesAsAUnit``'s discipline above: a relative ``projectIndex.path``
    override was returned bare, so it resolved against the process's CURRENT WORKING DIRECTORY at
    the point of use, not ``host_root()`` — correct only by accident, whenever a caller's CWD
    happened to already equal the host root. Every sibling accessor in this module
    (``doc_manifest_path``, ``confidential_dir``, ``version_json_path``, ...) is host-root-anchored;
    this one now is too. Measured before the fix, from a CWD one level below ``host_root()`` with
    ``ENGINE_HOST_ROOT`` correctly pointing at the real root: the relative override still resolved
    against the wrong directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        (self.root / "elsewhere").mkdir()
        self._prev_root = os.environ.get("ENGINE_HOST_ROOT")
        self._prev_path = os.environ.get("ENGINE_PROJECT_INDEX_PATH")
        os.environ["ENGINE_HOST_ROOT"] = str(self.root)
        # `host_root()` is `@lru_cache(maxsize=1)` — every OTHER test in this file relies on
        # setting `ENGINE_HOST_ROOT` only for a SUBPROCESS invocation, which always gets a fresh
        # cache. This test sets it for THIS process, so the cache must be cleared on both sides or
        # it silently keeps returning whatever the first caller in the run resolved.
        engine_config.host_root.cache_clear()
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        for name, prev in (
            ("ENGINE_HOST_ROOT", self._prev_root),
            ("ENGINE_PROJECT_INDEX_PATH", self._prev_path),
        ):
            if prev is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = prev
        engine_config.host_root.cache_clear()

    def test_a_relative_override_resolves_against_host_root_regardless_of_cwd(self) -> None:
        os.environ["ENGINE_PROJECT_INDEX_PATH"] = "elsewhere/PROJECT_INDEX.json"
        cwd = Path.cwd()
        os.chdir(self.root / "elsewhere")
        try:
            resolved = engine_config.project_index_path()
        finally:
            os.chdir(cwd)
        self.assertEqual(resolved, self.root / "elsewhere" / "PROJECT_INDEX.json")

    def test_the_default_is_still_host_root_slash_project_index_json(self) -> None:
        os.environ.pop("ENGINE_PROJECT_INDEX_PATH", None)
        self.assertEqual(engine_config.project_index_path(), self.root / "PROJECT_INDEX.json")

    def test_an_absolute_override_is_still_used_as_is(self) -> None:
        os.environ["ENGINE_PROJECT_INDEX_PATH"] = str(self.root / "elsewhere" / "PROJECT_INDEX.json")
        self.assertEqual(
            engine_config.project_index_path(), self.root / "elsewhere" / "PROJECT_INDEX.json"
        )


class ConfidentialDirCannotBecomeTheRepositoryRoot(unittest.TestCase):
    """`OG-92` — a vault that contains everything is not a vault.

    `PurePosixPath('')` equals `PurePosixPath('.')`, so an empty `confidentialDir` made the L14
    placement gate's containment test true for EVERY path in the repository — one character
    disabling a security gate while the hook printed its ordinary affirmative line.

    **That was fixed for `""` alone, and a verifier walked past it with `.`** — same effect,
    different spelling. `docs/process/RULES.md` Rule 1: the counter-example must cover the CLASS.
    So this is parametrised over every spelling of the root and of an escape upward, plus the
    two-sided half: a legitimate value must still be honoured.
    """

    _ROOTISH = ("", " ", ".", "./", "././.", "..", "../..", "/", "//")

    def test_every_root_spelling_is_refused(self) -> None:
        import importlib

        for value in self._ROOTISH:
            with self.subTest(value=value):
                with unittest.mock.patch.dict(os.environ, {"ENGINE_CONFIDENTIAL_DIR": value}):
                    module = importlib.reload(
                        importlib.import_module("tools.docgen.engine_config")
                    )
                    resolved = module.confidential_dir_relative()
                self.assertEqual(
                    resolved, "docs/confidential",
                    f"{value!r} was accepted — the L14 vault would contain the whole repository",
                )
                self.assertNotIn(resolved, ("", ".", "/"))

    def test_no_ancestor_of_the_rule_layer_is_accepted(self) -> None:
        """`OG-102` — the third spelling, and the one no root-blacklist could ever have caught.

        `ENGINE_CONFIDENTIAL_DIR=docs` is an ordinary relative directory: no dots, no escape, no
        empty string. It sails past every check above — and because `docs/` holds this project's
        entire governed corpus, it produces exactly the `OG-92` outcome: every document counts as
        already inside the vault, the L14 placement gate passes everything, and the hook prints its
        ordinary affirmative line. A verifier walked a `classification: secret` document out of the
        vault with it.

        Blacklisting `docs` would be the fourth instance of the same mistake, so the guard asserts
        an INVARIANT instead: the vault may not be an ancestor of the rule layer. This probe is
        derived from the live `docSystemDir` — every proper prefix of it — so it cannot go stale if
        a host relocates the rule layer, and it is not a restatement of the implementation's
        constant.
        """
        import importlib

        module = importlib.reload(importlib.import_module("tools.docgen.engine_config"))
        rule_layer = PurePosixPath(
            module._path_field("docSystem", "docSystemDir", "docs/design/doc-system")
        )
        prefixes = [
            str(PurePosixPath(*rule_layer.parts[: i + 1])) for i in range(len(rule_layer.parts))
        ]
        self.assertTrue(prefixes, "rule layer has no path parts; this probe would be vacuous")
        for value in prefixes:
            with self.subTest(value=value):
                with unittest.mock.patch.dict(os.environ, {"ENGINE_CONFIDENTIAL_DIR": value}):
                    resolved = importlib.reload(
                        importlib.import_module("tools.docgen.engine_config")
                    ).confidential_dir_relative()
                self.assertEqual(
                    resolved, "docs/confidential",
                    f"{value!r} was accepted as the vault — it contains the rule layer "
                    f"{rule_layer}, so the L14 placement gate would pass every governed document",
                )
        importlib.reload(importlib.import_module("tools.docgen.engine_config"))

    def test_a_legitimate_relocation_is_still_honoured(self) -> None:
        """The other side: refusing everything would be its own defect."""
        import importlib

        with unittest.mock.patch.dict(os.environ, {"ENGINE_CONFIDENTIAL_DIR": "private/vault"}):
            module = importlib.reload(importlib.import_module("tools.docgen.engine_config"))
            self.assertEqual(module.confidential_dir_relative(), "private/vault")
        importlib.reload(importlib.import_module("tools.docgen.engine_config"))

class EveryPathFieldRefusesTheRootLoudly(unittest.TestCase):
    """`OG-127` / `OG-128` / `OG-129` — the LOW band of the same family `OG-92` opened.

    Three defects that each made a refusal wrong in a different way:

    * `""` was the FIRST value both `OG-92`'s register row and the resolver's docstring list among
      those "refused loudly", and it was the one spelling refused **silently** — `_path_field`
      returned the default before the refusal could see it.
    * an absolute path was refused with `OG-92`'s message, which says the value "names the
      repository root or escapes it". That is untrue of `/abs/vault`, and a refusal that
      misdescribes what it refused sends the operator after the wrong mistake.
    * `confidentialDir`'s SIBLINGS were unguarded although they are joined onto `host_root()` the
      same way: `ENGINE_TRASH_DIR=.` resolved the trash directory to the repository root.
    """

    def _resolve(self, env: dict[str, str], call: str) -> str:
        import importlib

        with unittest.mock.patch.dict(os.environ, env):
            module = importlib.reload(importlib.import_module("tools.docgen.engine_config"))
            value = str(getattr(module, call)())
        importlib.reload(importlib.import_module("tools.docgen.engine_config"))
        return value

    def test_an_explicitly_blank_value_is_refused_and_announced(self) -> None:
        with self.assertLogs("tools.docgen.engine_config", level="ERROR") as captured:
            resolved = self._resolve(
                {"ENGINE_CONFIDENTIAL_DIR": ""}, "confidential_dir_relative"
            )
        self.assertEqual(resolved, "docs/confidential")
        self.assertTrue(
            any("empty value" in line for line in captured.output),
            f"blank value fell back silently: {captured.output}",
        )

    def test_an_absolute_vault_is_refused_with_its_OWN_reason(self) -> None:
        with self.assertLogs("tools.docgen.engine_config", level="ERROR") as captured:
            resolved = self._resolve(
                {"ENGINE_CONFIDENTIAL_DIR": "/abs/vault"}, "confidential_dir_relative"
            )
        self.assertEqual(resolved, "docs/confidential")
        joined = " ".join(captured.output)
        self.assertIn("absolute path", joined)
        self.assertNotIn(
            "names the repository root", joined,
            "an absolute path was refused with the root-escape message, which misdescribes it",
        )

    def test_the_sibling_path_fields_refuse_the_root_too(self) -> None:
        for var, call, default_tail in (
            ("ENGINE_TRASH_DIR", "trash_dir", "docs/archives/_trash"),
            ("ENGINE_DOC_SYSTEM_DIR", "doc_system_dir", "docs/design/doc-system"),
        ):
            for value in (".", "..", "./."):
                with self.subTest(var=var, value=value):
                    with self.assertLogs("tools.docgen.engine_config", level="ERROR"):
                        resolved = self._resolve({var: value}, call)
                    self.assertTrue(
                        resolved.endswith(default_tail),
                        f"{var}={value!r} resolved to {resolved}, not the default",
                    )

    def test_a_legitimate_sibling_relocation_is_still_honoured(self) -> None:
        """Two-sided: refusing everything would be its own defect."""
        resolved = self._resolve({"ENGINE_TRASH_DIR": "attic/bin"}, "trash_dir")
        self.assertTrue(resolved.endswith("attic/bin"), resolved)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class MarkPathIsHostConfigurableAndFailsClosed(unittest.TestCase):
    """``branding.markPath`` — the profile-aware identity hook.

    Before it existed, ``components._MARK_PATH`` was a module-level ``Final`` pinned to the
    engine's neutral placeholder, so a host project that vendored its real brand mark right next
    to it still shipped the generic one in EVERY rendered document — silently, with the mark
    present on disk and named in the host's own profile, read by nothing.
    """

    def setUp(self) -> None:
        self._prev = os.environ.get("ENGINE_MARK_PATH")

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("ENGINE_MARK_PATH", None)
        else:
            os.environ["ENGINE_MARK_PATH"] = self._prev

    def test_the_default_is_the_engines_neutral_placeholder(self) -> None:
        os.environ.pop("ENGINE_MARK_PATH", None)
        self.assertEqual(engine_config.mark_path().name, "engine-mark-placeholder.svg")
        self.assertTrue(engine_config.mark_path().is_file())

    def test_a_bare_filename_resolves_under_the_engines_own_assets_dir(self) -> None:
        """Where a vendored host mark sits, beside the placeholder it replaces."""
        os.environ["ENGINE_MARK_PATH"] = "engine-mark-placeholder.svg"
        resolved = engine_config.mark_path()
        self.assertEqual(resolved.parent.name, "assets")
        self.assertTrue(resolved.is_file())

    def test_an_absolute_path_is_used_as_is_and_reaches_logo_svg(self) -> None:
        from tools.docgen import components

        with tempfile.TemporaryDirectory() as td:
            mark = Path(td) / "host-mark.svg"
            mark.write_text('<svg aria-label="HostBrand" viewBox="0 0 10 10"></svg>')
            os.environ["ENGINE_MARK_PATH"] = str(mark)
            self.assertEqual(engine_config.mark_path(), mark)
            # The hook is only worth anything if the RENDERER actually uses it.
            self.assertIn('aria-label="HostBrand"', components.logo_svg())

    def test_a_configured_mark_that_is_missing_RAISES_rather_than_degrading(self) -> None:
        """Fail-closed. Falling back to the placeholder would BE the original defect."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["ENGINE_MARK_PATH"] = str(Path(td) / "absent.svg")
            with self.assertRaises(FileNotFoundError):
                engine_config.mark_path()


class ProjectNameNamespacesRenderedOutput(unittest.TestCase):
    """``branding.projectName`` — the other half of the identity hook.

    The engine had a project-name SLOT in two rendered outputs and no way to fill it, so the
    emptiness shipped: a trust footer reading ``Verified by `` with nothing after it, and a
    content-index schema id beginning with a bare ``.`` where the namespace belongs.
    """

    def setUp(self) -> None:
        self._prev = os.environ.get("ENGINE_PROJECT_NAME")

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("ENGINE_PROJECT_NAME", None)
        else:
            os.environ["ENGINE_PROJECT_NAME"] = self._prev

    def test_the_default_is_empty_so_existing_output_is_unchanged(self) -> None:
        os.environ.pop("ENGINE_PROJECT_NAME", None)
        self.assertEqual(engine_config.project_name(), "")

    def test_whitespace_only_is_treated_as_unset_not_as_a_name(self) -> None:
        os.environ["ENGINE_PROJECT_NAME"] = "   "
        self.assertEqual(engine_config.project_name(), "")

    def test_a_configured_name_reaches_the_trust_footer(self) -> None:
        import importlib

        from tools.docgen import components

        os.environ["ENGINE_PROJECT_NAME"] = "ExampleCorp"
        importlib.reload(engine_config)
        importlib.reload(components)
        try:
            self.assertIn("Verified by ExampleCorp", components.verified_stamp("AUDIT-1"))
        finally:
            os.environ.pop("ENGINE_PROJECT_NAME", None)
            importlib.reload(engine_config)
            importlib.reload(components)

