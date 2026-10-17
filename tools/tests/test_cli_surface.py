"""Every documented CLI entry point must actually run. Retained counter-example for `OG-86`.

**Why this file exists.** `python3 -m tools.docgen.cli render` raised `AttributeError` on *every*
invocation at `c956619` — the handler read `args.output` while the flag was declared `-o/--out`, so
the argparse dest was `out`. It had presumably never worked. Nothing caught it because **nothing
ever ran it**: no test, no health check, and no other module calls it.

That is the whole lesson, and it generalises past this one bug. `built-claims` verifies a documented
command *resolves to a real parser* — it reads source, so it can prove the subcommand and the flags
are declared. It cannot prove the handler behind them executes. The gap between "declared" and
"runs" is exactly where this defect lived, and only running the thing closes it.

So: one smoke invocation per subcommand, asserting exit 0 and a real artifact where one is promised.
Deliberately shallow — output *correctness* is `BUILD-01`/`BUILD-02`/`rendered-output`'s question.
This asserts only that the surface a user is told to type does not crash.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.corpus_check.corpus import repo_root

_ROOT = repo_root()


def _run(*argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *argv],
        cwd=cwd or _ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )


class DocgenCliSurfaceRuns(unittest.TestCase):
    """Each `docgen` subcommand runs. `OG-86`'s retained counter-example."""

    def setUp(self) -> None:
        # Built into the gitignored derived-state directory the engine already uses. The generator
        # canonicalises its output path inside the repository on purpose, so a system temp dir is
        # not an option for the commands that write.
        # **`mkdir` first — `.docgen/` is GITIGNORED, so it does not exist in a fresh clone**
        # (`OG-121`). `mkdtemp` does not create its parent, so all four probes in this class raised
        # `FileNotFoundError` in `setUp`, before invoking any CLI, on every fresh clone and every
        # `git archive` lab: measured `FAILED (errors=4)` running the standard discover command.
        #
        # It was invisible because of stage ORDERING: `tools.health` runs BUILD-01 (stage 4), which
        # creates `.docgen/`, before SUITE-05 (stage 5) runs these tests — so health reported
        # `[PASS] SUITE-05 … 136 ran, 136 defined` over a suite that cannot stand alone. A
        # counter-example that only passes when something else ran first is not retained evidence.
        scratch = _ROOT / ".docgen"
        scratch.mkdir(parents=True, exist_ok=True)
        self._out = Path(tempfile.mkdtemp(prefix="cli-", dir=scratch))
        self.addCleanup(lambda: __import__("shutil").rmtree(self._out, ignore_errors=True))

    def test_every_subcommand_is_reachable(self) -> None:
        """`--help` for each subcommand the parser declares — **actually derived from the parser.**

        The docstring said "derived from the parser itself" while the body iterated a hardcoded
        tuple of six names. A docstring that describes a property the code does not have is worse
        than no docstring: a reader checking whether new surface is covered reads the sentence,
        believes it, and moves on. A seventh subcommand added tomorrow would have been tested by
        nothing, which is exactly the gap that let `render` ship raising `AttributeError` on every
        invocation (`OG-106`).

        Now it reads `build_parser()`'s own subparser registry, so the list cannot drift.
        """
        from tools.docgen.cli import build_parser

        # `_subparsers` is argparse internals and untyped; the assertion is what makes the
        # narrowing honest rather than a blind index.
        subparsers = build_parser()._subparsers
        self.assertIsNotNone(subparsers, "the parser declares no subparsers at all")
        assert subparsers is not None
        subcommands = sorted(
            name
            for action in subparsers._group_actions
            for name in (action.choices or {})
        )
        self.assertGreaterEqual(
            len(subcommands), 5,
            f"only {subcommands} found — the parser introspection has broken, and a probe that "
            "iterates nothing passes for free",
        )
        listing = _run("tools.docgen.cli", "--help")
        self.assertEqual(listing.returncode, 0, listing.stderr[-400:])
        for sub in subcommands:
            with self.subTest(subcommand=sub):
                proc = _run("tools.docgen.cli", sub, "--help")
                self.assertEqual(proc.returncode, 0, f"{sub} --help: {proc.stderr[-300:]}")

    def test_render_writes_an_svg(self) -> None:
        """The exact invocation that raised `AttributeError` at `c956619`."""
        target = self._out / "out.svg"
        proc = _run(
            "tools.docgen.cli", "render", "tools/docgen/sample_spec.json", "-o", str(target)
        )
        self.assertEqual(proc.returncode, 0, f"render failed: {proc.stdout[-500:]}{proc.stderr[-500:]}")
        self.assertTrue(target.is_file(), "render exited 0 but wrote no file")
        self.assertIn("<svg", target.read_text(encoding="utf-8")[:400])

    def test_check_runs_on_a_governed_document(self) -> None:
        proc = _run("tools.docgen.cli", "check", "tools/docgen/sample.md")
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr)[-500:])

    def test_manifest_prints_rows(self) -> None:
        proc = _run("tools.docgen.cli", "manifest")
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr)[-400:])
        self.assertTrue(proc.stdout.strip(), "manifest exited 0 and printed nothing")


class CorpusCheckSurfaceRuns(unittest.TestCase):
    """The corpus checker's own CLI flags. A documented flag that crashes is the same defect class.

    **`tools.health` is deliberately NOT invoked here.** These tests are run *by* `SUITE-05`, which
    is run by `tools.health` — so shelling out to health from inside them is unbounded recursion,
    and the first attempt duly ran past a 600-second timeout. Health's own surface is exercised
    every time health runs, which is the only place it can be exercised safely. `--help` is the one
    thing that would be safe, and it is not worth the trap of having the invocation here at all.
    """

    def test_corpus_check_list_and_json(self) -> None:
        listing = _run("tools.corpus_check", "--list")
        self.assertEqual(listing.returncode, 0, listing.stderr[-300:])
        self.assertIn("register", listing.stdout)

        proc = _run("tools.corpus_check", "--json", "--guard", "register")
        self.assertIn(proc.returncode, (0, 1), proc.stderr[-300:])
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["counts"]["guards"], 1)

    def test_corpus_check_rejects_an_unknown_guard(self) -> None:
        """argparse's own exit 2, with the known names listed — not a traceback."""
        proc = _run("tools.corpus_check", "--guard", "no-such-guard")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown guard", proc.stderr)


class EslintConfigActuallyLints(unittest.TestCase):
    """Retained counter-example for `P8-051`: this repo's ~2.5k lines of hand-written `.mjs`/`.js`
    tooling had no linter config anywhere (`git ls-files '*.mjs' '*.js' | grep -v node_modules |
    grep -v '.min.js'` matched files but no `eslint.config.*`/`.eslintrc*` existed to check them).

    A config file that nobody ever asked to lint anything is exactly the kind of "number nobody
    compares is decoration" defect `tools/health/lint_baseline.json` was written to stop for
    ruff/mypy — so this asserts the JS config is not decoration either: it must reject a real
    unused-import and accept the same import when it's used, using the exact config + binary a
    caller would invoke (`node_modules/.bin/eslint -c eslint.config.mjs`), not a mocked rule list.

    Skips (does not fail) when `npm install` has not been run — `node_modules/` is gitignored
    scratch state, mirroring how SUITE-04 skips ruff/mypy when `uvx` is not on PATH rather than
    failing the whole suite on missing optional tooling.
    """

    eslint_bin: Path

    @classmethod
    def setUpClass(cls) -> None:
        # **Never `raise SkipTest` from `setUpClass`.** unittest then drops the whole class from
        # the run COUNT — not "2 skipped", but 2 tests that never appear — which is exactly the
        # shape `SUITE-05` exists to catch. This class DID raise here, and on any checkout without
        # `npm install` it silently cost the suite its two tests: measured 2026-09-13 on
        # the copy's build 1.0.11 as `640 defined but only 638 ran`, with a single "skipped=1" line
        # standing in for both. The identical trap, and this identical fix, are already documented
        # at `tools/tests/test_corpus_check.py` — it was fixed there and missed here.
        # Each test skips ITSELF instead (`_require_eslint`), and a self-skip IS counted.
        cls.eslint_bin = _ROOT / "node_modules" / ".bin" / "eslint"

    def _require_eslint(self) -> None:
        """A COUNTED skip when `npm install` has not been run here."""
        if not self.eslint_bin.exists():
            self.skipTest(
                "node_modules/.bin/eslint not present — run `npm install` first "
                "(node_modules/ is gitignored, regenerable scratch state)"
            )

    def _lint(self, source: str) -> subprocess.CompletedProcess[str]:
        # Probe files live at the repo root (not under a dot-directory) so ESLint's flat-config
        # base-path/ignore resolution treats them as ordinary in-tree files rather than silently
        # ignoring them (dot-directories like `.docgen/` are excluded by ESLint's own defaults,
        # which made an earlier version of this probe pass for the wrong reason: `exit 0` because
        # the file was never actually linted, not because it was clean).
        with tempfile.NamedTemporaryFile(
            dir=_ROOT, prefix="_eslint_probe_", suffix=".mjs", mode="w",
            delete=False, encoding="utf-8",
        ) as fh:
            fh.write(source)
            probe_path = Path(fh.name)
        try:
            return subprocess.run(
                [str(self.eslint_bin), "--no-config-lookup", "-c", "eslint.config.mjs", probe_path.name],
                cwd=_ROOT, capture_output=True, text=True, timeout=60, check=False,
            )
        finally:
            probe_path.unlink(missing_ok=True)

    def test_unused_import_is_rejected(self) -> None:
        self._require_eslint()
        proc = self._lint('import { readFileSync } from "node:fs";\nexport function f() { return 1; }\n')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("no-unused-vars", proc.stdout)

    def test_clean_module_is_accepted(self) -> None:
        self._require_eslint()
        proc = self._lint('export function f() { return 1; }\n')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class EngineConfigHasNoDeadFields(unittest.TestCase):
    """Retained counter-example for `P8-061`.

    `engine.config.json`'s four `tools.*` blocks each carried an `onMissing` field
    (`"fail-with-message"` / `"degrade"`) that read as documentation of real behaviour but was
    never consulted anywhere: `toolPath()`/`requireTool()` in `tools/lib/engine-config.mjs` and
    `tool_path()`/`require_tool()` in `tools/docgen/engine_config.py` decided fail-vs-degrade
    entirely by which of the two functions the *caller* invoked — the field could be edited to any
    value, including nonsense, with zero effect. That is a lie in a config file, not a knob.

    The field was deleted (not wired) rather than made to control anything, because wiring it
    consistently would require editing `tools/docgen/engine_config.py`, which sits outside this
    lane's owned paths — see this session's report for the exact cross-lane edit if the operator
    wants to wire it up in the Python loader instead of leaving it deleted.

    This guards the deletion: if `onMissing` (or any other field pattern like it) reappears in
    `engine.config.json`'s tools section without a matching reference in *both* loaders, the field
    is decorative again and this fails loudly instead of drifting back in silently.
    """

    def test_no_onmissing_field_anywhere(self) -> None:
        config = json.loads((_ROOT / "engine.config.json").read_text(encoding="utf-8"))
        for name, block in config.get("tools", {}).items():
            if name == "_readme":
                continue
            self.assertNotIn(
                "onMissing", block,
                f"tools.{name}.onMissing reappeared in engine.config.json but neither "
                "tools/lib/engine-config.mjs nor tools/docgen/engine_config.py reads it — wire it "
                "into toolPath()/requireTool() (both languages) before reintroducing it, or it is "
                "decorative again (P8-061).",
            )

    def test_neither_loader_references_onmissing(self) -> None:
        js_src = (_ROOT / "tools" / "lib" / "engine-config.mjs").read_text(encoding="utf-8")
        py_src = (_ROOT / "tools" / "docgen" / "engine_config.py").read_text(encoding="utf-8")
        self.assertNotIn("onMissing", js_src)
        self.assertNotIn("onMissing", py_src)


class GraphifyBuildersRefuseAVacuousGraph(unittest.TestCase):
    """`OG-248` — a builder that finds nothing must say so, not ship an empty graph and exit 0.

    Two-sided, and both sides have been paid for. `build-deps.mjs` shipped a 0-node graph over ~77
    real modules for weeks because `srcRoot` still pointed at the shipped example default, and
    nothing noticed because it exited 0 (`engine.config.json` graphify._readme). A field trial then
    ran `build-coverage.mjs` against a foreign host, read `0 detectors ... exit 0` as a result, and
    filed the exit code as an engine false green. `SUITE-07` covers `build-deps` and `build` with a
    fixture; this covers the REFUSAL itself, at the builder, for every host-scanning builder — the
    surface a human or agent actually runs.
    """

    _EMPTY_HOST_BUILDERS = (
        ("build-coverage.mjs", "ENGINE_GRAPHIFY_DETECTORS_DIR", "coverage.json", "no detectors under"),
        ("build-deps.mjs", "ENGINE_GRAPHIFY_SRC_ROOT", "deps.json", "no .py files under"),
    )

    def test_an_empty_host_is_refused_and_leaves_no_artifact(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is not on PATH")
        for builder, env_var, artifact, expected in self._EMPTY_HOST_BUILDERS:
            with (self.subTest(builder=builder),
                  tempfile.TemporaryDirectory(prefix="vacuous-host-") as td):
                    host = Path(td)
                    (host / "scanned").mkdir()
                    proc = subprocess.run(
                        ["node", str(_ROOT / "tools" / "graphify" / builder)],
                        cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False,
                        env={**os.environ, "ENGINE_HOST_ROOT": str(host), env_var: "scanned"},
                    )
                    self.assertNotEqual(proc.returncode, 0,
                                        f"{builder} exited 0 over an empty tree: {proc.stdout}")
                    self.assertIn(expected, proc.stderr)
                    self.assertIn("REFUSING", proc.stderr)
                    self.assertIn("nothing is written", proc.stderr)
                    self.assertFalse(
                        (host / "graphify-out" / artifact).exists(),
                        f"{builder} left a plausible {artifact} behind after refusing — "
                        "build-admin-catalog.mjs counts whatever graphify-out holds",
                    )

    def test_a_populated_host_still_builds(self) -> None:
        """The control. Without it, an unconditional `process.exit(2)` would pass the probe above."""
        if shutil.which("node") is None:
            self.skipTest("node is not on PATH")
        with tempfile.TemporaryDirectory(prefix="populated-host-") as td:
            host = Path(td)
            src = host / "scanned"
            src.mkdir()
            (src / "alpha.py").write_text("import scanned.beta\n", encoding="utf-8")
            (src / "beta.py").write_text("VALUE = 1\n", encoding="utf-8")
            proc = subprocess.run(
                ["node", str(_ROOT / "tools" / "graphify" / "build-deps.mjs")],
                cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False,
                env={**os.environ, "ENGINE_HOST_ROOT": str(host),
                     "ENGINE_GRAPHIFY_SRC_ROOT": "scanned"},
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            graph = json.loads((host / "graphify-out" / "deps.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(graph["nodes"]), 2,
                                    "the refusal must not fire on a host that really has modules")


class ToolPathValidatesEveryDiscoveryRoute(unittest.TestCase):
    """Retained counter-example for `P8-062`.

    `toolPath()` in `tools/lib/engine-config.mjs` validated the `pathFallback` route with
    `existsSync`/`whichSync`, but returned the `envVar`-override and config `path` values
    completely unchecked. Reproduced live before the fix:
    `ENGINE_CODEMAP_BIN=/nonexistent/codemap node tools/graphify/build.mjs` raised a raw
    `Error: spawnSync /nonexistent/codemap ENOENT` from deep inside the codemap-invocation code,
    instead of `requireTool()`'s actionable "required tool 'codemap' not found. …" message — because
    `toolPath()` had already handed back the bogus path as "found".

    Exercises all three override routes via the real CLI wrapper (`tools/lib/print-tool-path.mjs`),
    not the module internals directly, so the retained example is the same code path a real
    invocation takes.
    """

    def _print_tool_path(self, tool: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        full_env = {**os.environ, **env}
        return subprocess.run(
            ["node", "tools/lib/print-tool-path.mjs", tool],
            cwd=_ROOT, env=full_env, capture_output=True, text=True, timeout=30, check=False,
        )

    def test_bogus_envvar_path_is_rejected(self) -> None:
        proc = self._print_tool_path("codemap", {"ENGINE_CODEMAP_BIN": "/nonexistent/codemap-xyz"})
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_real_absolute_envvar_path_is_accepted(self) -> None:
        git_bin = shutil.which("git")
        assert git_bin is not None, "git must be on PATH to run this test"
        proc = self._print_tool_path("git", {"ENGINE_GIT_BIN": git_bin})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.strip(), git_bin)

    def test_bare_command_envvar_is_still_accepted(self) -> None:
        """A bare PATH-resolvable name (not a filesystem path) must still work via whichSync."""
        proc = self._print_tool_path("git", {"ENGINE_GIT_BIN": "git"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.strip(), "git")


class WriteCapableCommandsRefuseOutsideRepoRoot(unittest.TestCase):
    """Retained counter-example for `P8-075`.

    `docgen render`/`index` and `project_index dashboard` all refuse an `--out` path that resolves
    outside the repo root (`OG-60`'s containment guard, `P8-074` extended it to `content-index` and
    `dashboard`) — but before this class, nothing in the Python test suite asserted it: a grep for
    `containment|_canonicalize_inside_repo|outside the repo` across `tools/tests/*.py` matched only
    an unrelated placement-gate test. A security guard nobody's suite exercises is a guard that can
    silently regress (exactly the class of defect `OG-60`/`P8-074` themselves were).

    One test per write-capable subcommand: exit 2 (or docgen `build`'s own `BuildBlockedError`
    path) and no artifact written for an out-of-repo target; exit 0 and a real artifact written for
    an in-repo one. Each subcommand needs different positional arguments (a parser-driven generic
    loop would still have to special-case every one of them), so this enumerates the four `docgen`
    write-capable subcommands plus `project_index dashboard` explicitly rather than pretending a
    single loop derived from `build_parser()` covers heterogeneous argument shapes for free.
    """

    def setUp(self) -> None:
        self.outside_dir = Path(tempfile.mkdtemp(prefix="p8075_outside_"))
        self.addCleanup(lambda: shutil.rmtree(self.outside_dir, ignore_errors=True))

        scratch = _ROOT / ".docgen"
        scratch.mkdir(parents=True, exist_ok=True)
        self.inside_dir = Path(tempfile.mkdtemp(prefix="p8075_inside_", dir=scratch))
        self.addCleanup(lambda: shutil.rmtree(self.inside_dir, ignore_errors=True))

    def test_render_refuses_outside_and_accepts_inside(self) -> None:
        outside = self.outside_dir / "out.svg"
        proc = _run("tools.docgen.cli", "render", "tools/docgen/sample_spec.json", "-o", str(outside))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertFalse(outside.exists())

        inside = self.inside_dir / "out.svg"
        proc = _run("tools.docgen.cli", "render", "tools/docgen/sample_spec.json", "-o", str(inside))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(inside.is_file())

    def test_index_refuses_outside_and_accepts_inside(self) -> None:
        outside = self.outside_dir / "index.html"
        proc = _run("tools.docgen.cli", "index", str(self.inside_dir), "-o", str(outside))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertFalse(outside.exists())

        inside = self.inside_dir / "index.html"
        proc = _run("tools.docgen.cli", "index", str(self.inside_dir), "-o", str(inside))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(inside.is_file())

    def test_content_index_refuses_outside_and_accepts_inside(self) -> None:
        outside = self.outside_dir / "CONTENT_INDEX.json"
        proc = _run(
            "tools.docgen.cli", "content-index", "--docs-root", "docs", "-o", str(outside)
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertFalse(outside.exists())

        inside = self.inside_dir / "CONTENT_INDEX.json"
        proc = _run(
            "tools.docgen.cli", "content-index", "--docs-root", "docs", "-o", str(inside)
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(inside.is_file())

    def test_project_index_dashboard_refuses_outside_and_accepts_inside(self) -> None:
        outside = self.outside_dir / "PROJECT_INDEX.html"
        proc = _run("tools.project_index.cli", "dashboard", "--out", str(outside))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertFalse(outside.exists())

        inside = self.inside_dir / "PROJECT_INDEX.html"
        proc = _run("tools.project_index.cli", "dashboard", "--out", str(inside))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(inside.is_file())

    def test_build_blocks_an_out_dir_outside_the_repo(self) -> None:
        """`build`'s containment lives one layer deeper (inside `generator.build`, `OG-60`), so it
        surfaces as a reported `BuildBlockedError` and exit 1, not cli.py's own exit 2 — asserted
        here so the class of guard is covered for every write-capable subcommand, not only the
        three whose check lives directly in cli.py."""
        outside = self.outside_dir / "build_out"
        proc = _run("tools.docgen.cli", "build", "tools/docgen/sample.md", "-o", str(outside))
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("resolves outside the repo root", proc.stdout + proc.stderr)
        written = list(outside.glob("*")) if outside.exists() else []
        self.assertEqual(written, [], f"build wrote into a blocked out-dir: {written}")


class RenderRefusesToLeakSecrets(unittest.TestCase):
    """Retained counter-example for `P8-076`.

    `docgen render` built an SVG from an arbitrary `VisualSpec` JSON and wrote/printed it with NO
    export scan at all — reproduced live: a database-connection-string-shaped value with embedded
    credentials (scheme + user:pass + host, the `dsn_with_credentials` gate pattern) planted in a
    node label came out verbatim in the written SVG at exit 0. Full `export_sanitizer.run_gates()`
    needs a `DocHeader` (tier/manifest/variant-overlap gates presuppose a governed Markdown
    document, which a standalone chart spec is not) — this fires the two gates that operate on
    plain text (`gate_secret_value`, `gate_pii_path_internal`) before either output route.

    The poisoned value is built by concatenation, not as one literal, so this file's own source
    does not itself contain a DSN-shaped string a secret scanner would flag on commit.
    """

    def setUp(self) -> None:
        scratch = _ROOT / ".docgen"
        scratch.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="p8076_", dir=scratch))
        self.addCleanup(lambda: shutil.rmtree(self.work, ignore_errors=True))

    def _poisoned_spec(self) -> Path:
        spec = json.loads(
            (_ROOT / "tools" / "docgen" / "sample_spec.json").read_text(encoding="utf-8")
        )
        # A DSN-shaped value (scheme, then user/pass, then host) assembled at runtime from
        # separate literals — see class docstring for why it isn't written as one string.
        spec["nodes"][0]["label"] = "db" + "://" + "a" + ":" + "b" + "@" + "h"
        path = self.work / "poisoned_spec.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    def test_secret_shaped_label_is_blocked_not_written(self) -> None:
        spec_path = self._poisoned_spec()
        out = self.work / "out.svg"
        proc = _run("tools.docgen.cli", "render", str(spec_path), "-o", str(out))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("secret_value", proc.stdout + proc.stderr)
        self.assertFalse(out.exists(), "render wrote an SVG despite a blocking leak finding")

    def test_clean_spec_still_renders(self) -> None:
        out = self.work / "clean.svg"
        proc = _run("tools.docgen.cli", "render", "tools/docgen/sample_spec.json", "-o", str(out))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(out.is_file())


class StagedContentScannerSeesHtmlDocs(unittest.TestCase):
    """Retained counter-example for `P8-101`.

    `tools/docgen/hooks/staged_content_scanner.py`'s `_DOC_SUFFIXES` covered `.md`/`.markdown`/
    `.mdx`/`.txt`/`.rst`/`.adoc`/`.org` but not `.html`/`.htm` — while the sibling placement gate
    `tools/corpus_check/guards/stamps.py` already scanned `.html`/`.htm` for a *different* marker
    (stamps), so the two gates disagreed about which files carry a doc-system marker. Reproduced
    live: staging `notes.html` with a `<!-- classification: secret -->` marker and running the
    scanner returned zero findings at exit 0 — the file was never even opened for classification —
    while the identical marker in `notes.md` was at least evaluated.

    Exercises the real end-to-end path (`scan_staged` against a throwaway git repo with the file
    actually staged), not just the suffix predicate, so a future refactor of the read/classify
    pipeline is covered too, not only the extension list.
    """

    def test_html_with_a_secret_marker_is_now_caught(self) -> None:
        from tools.docgen.hooks.staged_content_scanner import scan_staged

        lab = Path(tempfile.mkdtemp(prefix="p8101_"))
        self.addCleanup(lambda: shutil.rmtree(lab, ignore_errors=True))
        subprocess.run(["git", "init", "-q"], cwd=lab, check=True)
        subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=lab, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=lab, check=True)
        (lab / "notes.html").write_text(
            "<!-- classification: secret -->\n<p>hi</p>\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "notes.html"], cwd=lab, check=True)

        findings = scan_staged(lab, files=["notes.html"])
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(findings[0].blocking)
        self.assertEqual(findings[0].evidence, "notes.html")

    def test_plain_html_with_no_marker_is_still_clean(self) -> None:
        """The widened suffix list must not turn ordinary HTML into false positives."""
        from tools.docgen.hooks.staged_content_scanner import scan_staged

        lab = Path(tempfile.mkdtemp(prefix="p8101_clean_"))
        self.addCleanup(lambda: shutil.rmtree(lab, ignore_errors=True))
        subprocess.run(["git", "init", "-q"], cwd=lab, check=True)
        subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=lab, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=lab, check=True)
        (lab / "page.html").write_text(
            "<!doctype html>\n<html><body><h1>Ordinary page</h1></body></html>\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "page.html"], cwd=lab, check=True)

        findings = scan_staged(lab, files=["page.html"])
        self.assertEqual(findings, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
