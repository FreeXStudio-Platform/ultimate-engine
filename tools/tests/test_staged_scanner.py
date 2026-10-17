"""Counter-examples for the staged-content scanner's ANCHORING and its FAIL-CLOSED enumeration.

Two defects, both found by adversarial verification at the current HEAD, both in
``tools/docgen/hooks/staged_content_scanner.py``:

* **F5** — ``is_inside_confidential_dir`` ignored the ``repo_root`` it was handed and derived one
  from the current working directory, so the `OG-167` vault anchor could be evaluated against a
  *different repository* than the one whose blobs were being read. Measured: the same manifest, the
  same target repository and the same blob exited **1 (BLOCKED)** from one CWD and **0 (silent)**
  from another. And when the CWD is not a git repository at all, ``_repo_root_default`` falls back
  to the engine's own checkout — whose vault *is* git-ignored — so a vendored engine run from any
  non-git directory inherited the wrong answer by default. That is the ordinary invocation shape of
  a shipped engine, not an attacker-only path.

* **F7** — ``iter_staged_files`` swallowed a git failure into an empty list, which every caller
  reads as "clean", while its own docstring claimed ``main`` surfaced the error. It did not.

Honest bound on both, worth keeping next to the tests: neither is reachable through the *installed*
hooks, which ``cd`` to the repository root before invoking the scanner (and git prepends its
exec-path to a hook's ``PATH``, so a ``git`` shim never reaches one). The reachable surface is the
documented ``--repo-root`` / ``--manifest`` CLI and any git failure specific to one invocation.
These probes therefore drive that CLI and the importable API, which is exactly where the defects
live.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.docgen.hooks import staged_content_scanner as scanner

_ENGINE_ROOT = Path(__file__).resolve().parents[2]
_MODULE_SOURCE = Path(scanner.__file__).read_text(encoding="utf-8")

_VAULT_TIER_DOC = (
    "---\n"
    "id: LEAK-1\n"
    "title: t\n"
    "classification: secret\n"
    "surface: none\n"
    "audience: a\n"
    "owner: o\n"
    "status: draft\n"
    "last_reviewed: 2026-08-21\n"
    "---\n\n# body\n"
)


def _run_cli(*args: str, cwd: Path, path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the scanner exactly as its documented CLI, from ``cwd``."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_ENGINE_ROOT)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        ("python3", "-m", "tools.docgen.hooks.staged_content_scanner", *args),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


class _RepoLab(unittest.TestCase):
    """Throwaway git repositories. Nothing here touches the engine's own checkout."""

    def repo(self, *, vault_ignored: bool) -> Path:
        root = Path(tempfile.mkdtemp(prefix="scanner_lab_"))
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(("git", "init", "-q", "."), cwd=root, check=True)
        subprocess.run(("git", "config", "user.email", "t@t"), cwd=root, check=True)
        subprocess.run(("git", "config", "user.name", "t"), cwd=root, check=True)
        if vault_ignored:
            (root / ".gitignore").write_text("docs/confidential/\n", encoding="utf-8")
            subprocess.run(("git", "add", ".gitignore"), cwd=root, check=True)
        return root

    def stage(self, repo: Path, rel: str, text: str) -> str:
        """Write and stage ``rel``; return its blob sha."""
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        subprocess.run(("git", "add", "-f", "--", rel), cwd=repo, check=True)
        sha = subprocess.run(
            ("git", "rev-parse", f":{rel}"), cwd=repo, check=True, capture_output=True, text=True
        )
        return sha.stdout.strip()

    def blob(self, repo: Path, rel: str, text: str) -> str:
        """Write ``rel`` and record its blob WITHOUT adding it to the index; return the sha.

        Deliberately not ``git add``: ``git check-ignore`` does not report a **tracked** path as
        ignored (only ``--no-index`` does), so staging a file into the vault would make the very
        repository that keeps its vault out of git look as though it does not — which would make
        the "genuinely ignored vault" control below assert the wrong thing for the wrong reason.
        ``scan_manifest`` reads blobs with ``git cat-file``, so an index entry is not needed.
        """
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        sha = subprocess.run(
            ("git", "hash-object", "-w", "--", str(target)),
            cwd=repo, check=True, capture_output=True, text=True,
        )
        return sha.stdout.strip()

    def blob_bytes(self, repo: Path, rel: str, data: bytes) -> str:
        """Record a blob from RAW BYTES (for wide-encoded content the `str` helpers cannot express),
        WITHOUT adding it to the index; return the sha."""
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        sha = subprocess.run(
            ("git", "hash-object", "-w", "--", str(target)),
            cwd=repo, check=True, capture_output=True, text=True,
        )
        return sha.stdout.strip()

    def manifest(self, records: list[tuple[str, str]]) -> Path:
        path = Path(tempfile.mkdtemp(prefix="scanner_man_")) / "manifest.tsv"
        self.addCleanup(shutil.rmtree, path.parent, True)
        path.write_text("".join(f"{sha}\t{rel}\n" for sha, rel in records), encoding="utf-8")
        return path


class Breach1PlacementDecidedByContentNotSuffix(_RepoLab):
    """`OG-213` — the Phase-7 moat red-team walked a `classification: secret` document past BOTH
    placement gates by saving it as `notes.mkd` (a standard Markdown alias) or with no extension.

    The gate read a file's header only for nine allowlisted suffixes and skipped everything else, so
    the *filename* decided whether the *header* was even consulted — the exact inversion the module's
    own docstring forbids ("Header is authority ... NOT the filename"). The fix inverts the filter to
    a structured-data denylist: content now decides for every file except a `.yaml`/`.json`/`.csv`
    that `OG-41` already ruled out. Driven end-to-end through the push-time gate (`scan_manifest`),
    both directions.
    """

    def _refused(self, rel: str, text: str) -> None:
        repo = self.repo(vault_ignored=True)
        sha = self.blob(repo, rel, text)
        findings = scanner.scan_manifest(repo, self.manifest([(sha, rel)]))
        self.assertTrue(findings, f"a classified doc at {rel!r} must be refused, not skipped by suffix")
        self.assertIn(rel, findings[0].evidence)

    def _clean(self, rel: str, text: str) -> None:
        repo = self.repo(vault_ignored=True)
        sha = self.blob(repo, rel, text)
        self.assertEqual(
            scanner.scan_manifest(repo, self.manifest([(sha, rel)])), [],
            f"{rel!r} must pass — the denylist and the content check must not over-fire",
        )

    def test_markdown_alias_extensions_are_refused(self) -> None:
        for rel in ("notes.mkd", "notes.mdown", "notes.mkdn", "notes.mdwn", "notes.litcoffee"):
            with self.subTest(rel=rel):
                self._refused(rel, _VAULT_TIER_DOC)

    def test_a_no_extension_classified_doc_is_refused(self) -> None:
        self._refused("architecture-notes", _VAULT_TIER_DOC)

    def test_a_binary_blob_is_skipped_by_content_not_by_suffix(self) -> None:
        # A PNG-shaped blob (NUL early) is rejected by `_decode_for_scanning`, so it produces no
        # finding even though its suffix is no longer allowlisted. "Read every file" does not mean
        # "scan every JPEG for YAML".
        repo = self.repo(vault_ignored=True)
        rel = "asset.bin"
        (repo / rel).write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 64)
        sha = subprocess.run(
            ("git", "hash-object", "-w", "--", str(repo / rel)),
            cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(scanner.scan_manifest(repo, self.manifest([(sha, rel)])), [])

    def test_a_structured_data_file_is_still_spared(self) -> None:
        # `OG-41` preserved: a `.yaml` opening with a `classification` key is data, not a document,
        # and reading it would false-refuse ordinary config. The denylist spares exactly these.
        self._clean("config.yaml", "---\nclassification: secret\nfoo: bar\n")

    def test_a_public_alias_document_still_commits(self) -> None:
        self._clean("notes.mkd", _VAULT_TIER_DOC.replace("classification: secret", "classification: public"))

    def test_a_headerless_no_extension_file_is_clean(self) -> None:
        self._clean("README", "# just a readme\nno front matter here at all\n")


class Breach2WideEncodedPlacementIsDecodedCleanly(_RepoLab):
    """`OG-213` round 2 — inverting the suffix filter to a content denylist made content-classification
    the SOLE placement gate, and that gate could not read a wide-encoded header. `materialise.
    normalise_for_scanning` is ADDITIVE (raw wide bytes first, a UTF-8 view appended), which is right
    for the secret scan (it greps the union, position-blind) but wrong for placement, whose front-matter
    regex is `\\A`-anchored: on the additive buffer a UTF-16 `classification: secret` document's header
    sat AFTER the mojibake prefix, so it read as a header-less README and passed. The fix decodes a
    wide blob CLEANLY for the header check, putting a real header back at position 0. `OG-84` had
    claimed this class closed; it was closed for one of the scanner's two consumers only.
    """

    _VAULT_TIER_BODY = "---\nclassification: secret\n---\n# body of a classified document\n"
    _PUBLIC = "---\nclassification: public\n---\n# an ordinary public page\n"

    def _refused_bytes(self, rel: str, data: bytes, label: str) -> None:
        repo = self.repo(vault_ignored=True)
        sha = self.blob_bytes(repo, rel, data)
        findings = scanner.scan_manifest(repo, self.manifest([(sha, rel)]))
        self.assertTrue(findings, f"a {label} classified doc must be REFUSED, not read as header-less")
        self.assertIn(rel, findings[0].evidence)

    def test_utf16_le_secret_is_refused(self) -> None:
        self._refused_bytes("notes.md", self._VAULT_TIER_BODY.encode("utf-16-le"), "UTF-16-LE")

    def test_utf16_le_with_bom_secret_is_refused(self) -> None:
        import codecs
        self._refused_bytes("notes.md", codecs.BOM_UTF16_LE + self._VAULT_TIER_BODY.encode("utf-16-le"),
                            "BOM'd UTF-16-LE")

    def test_utf16_be_secret_is_refused(self) -> None:
        self._refused_bytes("notes.md", self._VAULT_TIER_BODY.encode("utf-16-be"), "UTF-16-BE")

    def test_utf32_le_secret_is_refused(self) -> None:
        self._refused_bytes("notes.md", self._VAULT_TIER_BODY.encode("utf-32-le"), "UTF-32-LE")

    def test_utf8_secret_is_refused_control(self) -> None:
        # The positive control the wide cases mirror: the narrow encoding was already refused.
        self._refused_bytes("notes.md", self._VAULT_TIER_BODY.encode("utf-8"), "UTF-8")

    def test_a_clean_utf16_public_doc_still_passes(self) -> None:
        # The other direction: decoding cleanly must not over-fire on a legitimate wide-encoded public.
        repo = self.repo(vault_ignored=True)
        sha = self.blob_bytes(repo, "readme.md", self._PUBLIC.encode("utf-16-le"))
        self.assertEqual(
            scanner.scan_manifest(repo, self.manifest([(sha, "readme.md")])), [],
            "a clean UTF-16 public document must pass the placement gate",
        )

    def test_a_cjk_heavy_wide_secret_is_refused(self) -> None:
        """`OG-227` — a CJK-heavy `classification: secret` document lowers NUL density below the
        UTF-16 detector's threshold (so it reads as None) or fails the UTF-32 quad test (so it reads
        AS UTF-16 with the wrong stride), and either way the additive-buffer decode left the header
        off position 0, past the `\\A`-anchored placement gate — the `OG-101` CJK-padding class in the
        placement path, found by a verifier. The candidate-codec retry must place a header back at
        pos 0 in every wide encoding."""
        secret = "---\nclassification: secret\n---\n# 标题\n" + ("你好世界这是很长的中文文档。" * 200) + "\n"
        for enc in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
            with self.subTest(encoding=enc):
                repo = self.repo(vault_ignored=True)
                sha = self.blob_bytes(repo, "notes.md", secret.encode(enc))
                findings = scanner.scan_manifest(repo, self.manifest([(sha, "notes.md")]))
                self.assertTrue(findings, f"a CJK-heavy {enc} classified doc must be REFUSED")
                self.assertIn("notes.md", findings[0].evidence)

    def test_a_narrow_legacy_cjk_secret_is_refused(self) -> None:
        """`OG-232` — the `OG-227` CJK class one encoding-family over. A `classification: secret` doc
        in a NARROW legacy encoding (Shift-JIS, EUC-JP, GB18030 — a Japanese/Chinese editor default),
        with a large CJK body, decodes to >30% U+FFFD as UTF-8 and was DISCARDED by the
        replacement-ratio binary cap, walking its ASCII header past the placement gate. A verifier
        found it. The ASCII header survives at pos 0 regardless of the body, so a blob whose
        front-matter header is present there is kept and classified rather than discarded as binary."""
        body = "これは日本語の長い文書です。" * 40  # encodable by all three legacy codecs
        secret = f"---\nclassification: secret\n---\n# h\n{body}\n"
        for enc in ("shift_jis", "euc_jp", "gb18030"):
            with self.subTest(encoding=enc):
                repo = self.repo(vault_ignored=True)
                sha = self.blob_bytes(repo, "notes.md", secret.encode(enc))
                findings = scanner.scan_manifest(repo, self.manifest([(sha, "notes.md")]))
                self.assertTrue(findings, f"a {enc} classified doc must be REFUSED, not discarded")
                # …and the public counterpart passes (the fix reads the header, it does not just refuse).
                repo2 = self.repo(vault_ignored=True)
                pub_sha = self.blob_bytes(repo2, "readme.md", secret.replace("secret", "public").encode(enc))
                self.assertEqual(
                    scanner.scan_manifest(repo2, self.manifest([(pub_sha, "readme.md")])), [],
                    f"a {enc} PUBLIC doc must pass — the fix classifies on the header, not refuses blindly",
                )


class ScanManifestSkipsPathlessObjects(_RepoLab):
    """`OG-213` collateral — the `pre-push` manifest lists path-LESS objects (the commit and tree
    objects themselves) as `<sha>\\t` with no name. Inverting the suffix ALLOWLIST to a denylist made
    `_might_carry_classification("")` true (an empty suffix is not a data suffix), so those objects
    were READ — `git cat-file blob <commit-sha>` exits 128 and raised a BLOCKING `unreadable` finding
    on EVERY push. The fix returns False for an empty/whitespace path: a name is required before a
    suffix can be judged. Without it the whole moat refuses every push, so this is a positive control
    on the gate being USABLE, not only correct.
    """

    def test_a_pathless_commit_object_entry_is_skipped_not_flagged(self) -> None:
        repo = self.repo(vault_ignored=True)
        # A real commit sha in this repo — reading it AS A BLOB fails (128), the exact 500-error shape.
        self.stage(repo, "seed.md", "# seed\nplain content\n")
        subprocess.run(("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed"),
                       cwd=repo, check=True)
        commit_sha = subprocess.run(("git", "rev-parse", "HEAD"), cwd=repo, check=True,
                                    capture_output=True, text=True).stdout.strip()
        # Manifest entry with an EMPTY path, exactly as `git ... --raw` emits for the commit/tree object.
        findings = scanner.scan_manifest(repo, self.manifest([(commit_sha, "")]))
        self.assertEqual(findings, [], "a path-less commit/tree object must be skipped, not flagged unreadable")

    def test_might_carry_classification_is_false_for_an_empty_path(self) -> None:
        self.assertFalse(scanner._might_carry_classification(""))
        self.assertFalse(scanner._might_carry_classification("   "))
        # …but still true for a real no-extension document name (the OG-213 fix must survive).
        self.assertTrue(scanner._might_carry_classification("NOTES"))

    def test_a_subtree_object_is_skipped_not_flagged(self) -> None:
        """`OG-226` — the empty-path fix reached only the COMMIT and the ROOT TREE; `git rev-list
        --objects` also emits a TREE for every DIRECTORY, WITH its path (`docs`, `tools/blueprint`),
        which `_might_carry_classification` (no extension → not a data suffix) waves through to
        `git cat-file blob <tree-sha>` → exit 128 → a false blocking finding. A verifier measured 11
        of them on the real push manifest, refusing every push. The blob-type check must skip a tree,
        while still reading a real blob at the same directory-shaped no-extension path."""
        repo = self.repo(vault_ignored=True)
        # A real subtree object (a directory), listed WITH its path exactly as rev-list --objects does.
        self.stage(repo, "docs/x.md", "# doc\nplain public content\n")
        subprocess.run(("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed"),
                       cwd=repo, check=True)
        subtree_sha = subprocess.run(("git", "rev-parse", "HEAD:docs"), cwd=repo, check=True,
                                     capture_output=True, text=True).stdout.strip()
        self.assertEqual(
            subprocess.run(("git", "cat-file", "-t", subtree_sha), cwd=repo, check=True,
                           capture_output=True, text=True).stdout.strip(), "tree",
            "the fixture must be a real tree object for this probe to mean anything",
        )
        findings = scanner.scan_manifest(repo, self.manifest([(subtree_sha, "docs")]))
        self.assertEqual(findings, [], "a tree object listed with a directory path must be skipped")


class VaultAnchorFollowsTheRepositoryBeingScanned(_RepoLab):
    """F5. The blobs and the ignore rules must come from ONE repository — the one named."""

    def test_a_committed_vault_is_refused_no_matter_where_the_process_stands(self) -> None:
        """The direct reproduction: identical inputs, three working directories, one verdict.

        Before the fix, only the first of these blocked. From a CWD whose own vault *is* ignored the
        scan exited **0 with no output** over a repository that genuinely commits its vault; from a
        CWD that is not a git repository at all, ``_repo_root_default`` fell back to the engine
        checkout and did the same thing.
        """
        host = self.repo(vault_ignored=False)
        sha = self.blob(host, "docs/confidential/S.md", _VAULT_TIER_DOC)
        manifest = self.manifest([(sha, "docs/confidential/S.md")])
        elsewhere = self.repo(vault_ignored=True)
        non_git = Path(tempfile.mkdtemp(prefix="scanner_nongit_"))
        self.addCleanup(shutil.rmtree, non_git, True)

        for label, cwd in (
            ("inside the target repo", host),
            ("inside a DIFFERENT repo whose vault IS ignored", elsewhere),
            ("in a directory that is not a git repo at all", non_git),
        ):
            with self.subTest(cwd=label):
                proc = _run_cli(
                    "--repo-root", str(host), "--manifest", str(manifest), cwd=cwd
                )
                self.assertEqual(
                    proc.returncode,
                    1,
                    f"scanning {host} from {label} must refuse a secret doc in a vault git would "
                    f"commit (OG-167).\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}",
                )
                self.assertIn("classification='secret'", proc.stderr)

    def test_a_genuinely_ignored_vault_still_passes_from_a_foreign_cwd(self) -> None:
        """The control that stops the fix from being "refuse everything".

        A fix that simply hard-failed the vault anchor would pass the test above and be useless.
        Same foreign-CWD shape, but the target repository really does keep its vault out of git, so
        the document is where it belongs and the scan must be clean.
        """
        target = self.repo(vault_ignored=True)
        sha = self.blob(target, "docs/confidential/S.md", _VAULT_TIER_DOC)
        manifest = self.manifest([(sha, "docs/confidential/S.md")])
        foreign = self.repo(vault_ignored=False)

        proc = _run_cli("--repo-root", str(target), "--manifest", str(manifest), cwd=foreign)
        self.assertEqual(
            proc.returncode, 0, f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        )
        self.assertEqual(proc.stderr, "")

    def test_scan_staged_anchors_on_its_repo_root_argument_too(self) -> None:
        """The index path, not just the manifest path — both callers had the same bug.

        Driven through the importable API from this process, whose CWD is the engine checkout (a
        repository whose vault IS git-ignored). Before the fix that CWD decided the answer.
        """
        host = self.repo(vault_ignored=False)
        self.stage(host, "docs/confidential/S.md", _VAULT_TIER_DOC)
        findings = scanner.scan_staged(host, files=["docs/confidential/S.md"])
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(findings[0].blocking)

        # The control: same path, same explicit file list, a repository that really does keep its
        # vault out of git. Containment short-circuits before any blob is read, so the anchor is the
        # only thing under test here — which is the point.
        ok = self.repo(vault_ignored=True)
        self.assertEqual(scanner.scan_staged(ok, files=["docs/confidential/S.md"]), [])

    def test_no_placement_call_site_may_invent_its_own_repository_root(self) -> None:
        """The NEW edge, attacked structurally rather than one call site at a time.

        Narrowing the two known call sites leaves the widest remaining input: a *third* scan path,
        added later, that calls the placement helpers with a root of its own choosing — which is how
        this defect survived ``_repo_root_default``'s own rewrite. So the invariant is derived from
        the module's AST: every call to ``is_inside_confidential_dir``/``classify_file`` passes the
        bare name ``repo_root``, that name is a parameter of the enclosing function, and
        ``_repo_root_default`` is called from ``main`` alone — the one place a root is legitimately
        *chosen* rather than *received*.
        """
        tree = ast.parse(_MODULE_SOURCE)
        checked = 0
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = {a.arg for a in func.args.args} | {a.arg for a in func.args.kwonlyargs}
            for node in ast.walk(func):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if node.func.id == "_repo_root_default":
                    self.assertEqual(
                        func.name,
                        "main",
                        f"{func.name}() derives a repository root of its own; only main() may — "
                        f"every other path must use the root it was handed (F5)",
                    )
                    continue
                if node.func.id not in ("is_inside_confidential_dir", "classify_file"):
                    continue
                checked += 1
                self.assertTrue(
                    node.args and isinstance(node.args[-1], ast.Name)
                    and node.args[-1].id == "repo_root",
                    f"{func.name}() calls {node.func.id}() without passing `repo_root` "
                    f"positionally as its last argument",
                )
                self.assertIn(
                    "repo_root",
                    params,
                    f"{func.name}() must RECEIVE repo_root rather than construct one",
                )
        self.assertGreaterEqual(checked, 4, "the placement call sites disappeared from the module")

    def test_the_repo_root_parameter_has_no_default(self) -> None:
        """A default would let a caller omit it — which is the defect, spelled differently.

        ``is_inside_confidential_dir(rel_path)`` was a complete, type-correct call that silently
        anchored on the wrong repository. It must not be one again.
        """
        import inspect

        for func in (scanner.is_inside_confidential_dir, scanner.classify_file):
            with self.subTest(func=func.__name__):
                param = inspect.signature(func).parameters["repo_root"]
                self.assertIs(param.default, inspect.Parameter.empty)


class StagedEnumerationFailsClosed(_RepoLab):
    """F7. "git would not tell us what is staged" is not "nothing is staged"."""

    def test_iter_staged_files_returns_none_when_git_cannot_answer(self) -> None:
        """``None``, never ``[]``. The empty list is the answer "git said: nothing", and conflating
        the two is what made a git failure read as a clean index."""
        not_a_repo = Path(tempfile.mkdtemp(prefix="scanner_norepo_"))
        self.addCleanup(shutil.rmtree, not_a_repo, True)
        self.assertIsNone(scanner.iter_staged_files(not_a_repo))

    def test_scan_staged_blocks_when_the_enumeration_failed(self) -> None:
        not_a_repo = Path(tempfile.mkdtemp(prefix="scanner_norepo_"))
        self.addCleanup(shutil.rmtree, not_a_repo, True)
        findings = scanner.scan_staged(not_a_repo)
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(findings[0].blocking)
        self.assertIn("could not be read from git", findings[0].message)

    def test_a_real_empty_index_is_still_clean(self) -> None:
        """The control against over-blocking: git answering "nothing staged" must stay exit 0."""
        empty = self.repo(vault_ignored=True)
        subprocess.run(("git", "rm", "--cached", "-q", ".gitignore"), cwd=empty, check=True)
        self.assertEqual(scanner.iter_staged_files(empty), [])
        self.assertEqual(scanner.scan_staged(empty), [])

    def test_an_explicit_empty_file_list_is_still_clean(self) -> None:
        """``files=[]`` bypasses enumeration entirely and must not be mistaken for a git failure."""
        self.assertEqual(scanner.scan_staged(self.repo(vault_ignored=True), files=[]), [])

    def test_cli_refuses_when_git_diff_cached_fails(self) -> None:
        """End-to-end through the documented CLI with a ``git`` that fails only the enumeration.

        Measured at HEAD before the fix: this exact setup exited **0 with no output at all**, over an
        index holding a ``classification: secret`` document outside the vault. The A-case below is
        the same index under real git, so the probe also proves the shim is not simply breaking
        everything.
        """
        repo = self.repo(vault_ignored=True)
        self.stage(repo, "notes/BOARD.md", _VAULT_TIER_DOC)

        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "git is required for this counter-example")

        clean = _run_cli("--repo-root", str(repo), cwd=repo)
        self.assertEqual(clean.returncode, 1, clean.stderr)
        self.assertIn("classification='secret'", clean.stderr)

        shim_dir = Path(tempfile.mkdtemp(prefix="scanner_shim_"))
        self.addCleanup(shutil.rmtree, shim_dir, True)
        shim = shim_dir / "git"
        shim.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "diff" ]; then\n'
            '  for a in "$@"; do\n'
            '    if [ "$a" = "--name-only" ]; then\n'
            '      echo "fatal: simulated git failure" >&2\n'
            "      exit 128\n"
            "    fi\n"
            "  done\n"
            "fi\n"
            f'exec {real_git} "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)

        broken = _run_cli("--repo-root", str(repo), cwd=repo, path_prefix=shim_dir)
        self.assertEqual(
            broken.returncode,
            1,
            f"a git failure must refuse, not pass silently.\nstdout={broken.stdout!r}\n"
            f"stderr={broken.stderr!r}",
        )
        self.assertIn("could not be read from git", broken.stderr)


class Breach234SubmoduleGitlinkIsSkippedNotRefused(_RepoLab):
    """`OG-234` — the commit-time gate refused a legitimate submodule COMMIT.

    A gitlink (index mode ``160000``) points at a commit sha in ANOTHER repository, so
    ``git show :<path>`` fails here and ``read_staged_bytes`` returns ``None`` — which ``scan_staged``
    fail-closes into a BLOCKING finding (``OG-118``'s posture, correct for a genuinely unreadable
    blob). But a gitlink is a pointer, not a document: it cannot carry a classification header, so it
    must be SKIPPED, exactly as ``scan_manifest`` skips non-blob objects at push time (`OG-226`). The
    defect was latent since before the acceptance freeze and surfaced only when SUITE-06 was run to a
    verdict on a quiet machine. Falsified both ways below.
    """

    def _repo_with_gitlink(self) -> Path:
        repo = self.repo(vault_ignored=True)
        # A REAL submodule, so the gitlink points at a commit that lives in the SUBMODULE's object
        # store, NOT the superproject's. That is what makes `git show :vendor/sub` return None and so
        # genuinely drives the `blob is None` -> skip branch under test. An earlier version pointed the
        # gitlink at a LOCAL commit sha via `update-index --cacheinfo`; `git show` then returned that
        # commit's body and the entry passed as `classify_file(body)=clean` — the skip branch was never
        # reached. The OG-234 adversarial verifier caught exactly that; the `assertIsNone` below pins
        # the None so the branch cannot silently stop being the reason the gitlink is spared.
        sub = Path(tempfile.mkdtemp(prefix="scanner_sub_"))
        self.addCleanup(shutil.rmtree, sub, True)
        subprocess.run(("git", "init", "-q", str(sub)), check=True)
        subprocess.run(("git", "-C", str(sub), "config", "user.email", "s@s"), check=True)
        subprocess.run(("git", "-C", str(sub), "config", "user.name", "s"), check=True)
        (sub / "a.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(sub), "add", "a.txt"), check=True)
        subprocess.run(("git", "-C", str(sub), "commit", "-q", "-m", "s"), check=True)
        subprocess.run(
            ("git", "-C", str(repo), "-c", "protocol.file.allow=always",
             "submodule", "add", "-q", str(sub), "vendor/sub"),
            check=True,
        )
        return repo

    def test_a_staged_submodule_gitlink_is_skipped_not_refused(self) -> None:
        repo = self._repo_with_gitlink()
        # Pin that the branch UNDER TEST is the one exercised: a gitlink's target commit lives in the
        # submodule's repo, so the superproject cannot show it as a blob and the staged read IS None.
        self.assertIsNone(
            scanner.read_staged_bytes(repo, "vendor/sub"),
            "the gitlink must read as None here, or the `blob is None` skip is not what spares it",
        )
        self.assertTrue(scanner._is_staged_gitlink(repo, "vendor/sub"))
        self.assertEqual(
            scanner.scan_staged(repo), [],
            "a submodule gitlink must not be refused — it is a commit pointer, not a document",
        )

    def test_the_gitlink_skip_does_not_spare_a_real_classified_doc(self) -> None:
        repo = self._repo_with_gitlink()
        self.stage(repo, "leak.md", _VAULT_TIER_DOC)
        findings = scanner.scan_staged(repo)
        self.assertTrue(
            any("leak.md" in f.evidence for f in findings),
            "a classified doc staged beside a gitlink must still be refused — the skip must not widen",
        )
        self.assertFalse(
            any("vendor/sub" in f.evidence for f in findings),
            "the gitlink itself must never be flagged",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
