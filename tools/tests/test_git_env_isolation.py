"""A scratch repository must never be the real one (OG-291).

A hook run from a linked worktree exports ``GIT_DIR``; a child that runs ``git init`` / ``git commit`` in a scratch directory then
commits to the REAL repository. Measured on the explorer release's pre-push hook: three ``draft-gate baseline`` commits and one
``base`` commit on the branch being pushed. These tests run the real code with the hostile environment.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import gitenv

_REPO = Path(__file__).resolve().parents[2]
_HOSTILE = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX")


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    base = gitenv.clean_env() if env is None else env
    return subprocess.run(
        ("git", "-c", "user.email=t@x", "-c", "user.name=t", *args), cwd=cwd, env=base, capture_output=True, text=True, check=True
    ).stdout.strip()


def _real_repo(root: Path) -> Path:
    repo = root / "real"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "the real history")
    return repo


class ScrubDropsExactlyTheRepositoryLocalVariables(unittest.TestCase):
    def test_the_variables_that_pick_a_repository_go_and_the_rest_stay(self) -> None:
        env = {"GIT_DIR": "/x", "GIT_WORK_TREE": "/y", "GIT_INDEX_FILE": "/z", "GIT_AUTHOR_NAME": "keep", "PATH": "/usr/bin", "HOME": "/h"}
        removed = gitenv.scrub(env)
        self.assertEqual(sorted(removed), ["GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"])
        self.assertEqual(env, {"GIT_AUTHOR_NAME": "keep", "PATH": "/usr/bin", "HOME": "/h"})

    def test_clean_env_is_a_copy_and_leaves_the_process_alone(self) -> None:
        before = dict(os.environ)
        out = gitenv.clean_env({"GIT_DIR": "/x", "PATH": "/p"})
        self.assertEqual(out, {"PATH": "/p"})
        self.assertEqual(dict(os.environ), before)

    def test_git_s_own_list_is_covered(self) -> None:
        self.assertLessEqual({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}, set(gitenv.local_vars()))


class EachPackageThatRunsGitInAScratchDirectoryScrubsOnImport(unittest.TestCase):
    def _imported_env(self, module: str) -> str:
        env = dict(os.environ, GIT_DIR="/nonexistent/.git", GIT_INDEX_FILE="/nonexistent/index", GIT_WORK_TREE="/nonexistent")
        code = f"import os, {module}; print(sorted(k for k in os.environ if k in {_HOSTILE + ('GIT_INDEX_FILE',)!r}))"
        return subprocess.run([sys.executable, "-c", code], cwd=_REPO, env=env, capture_output=True, text=True, check=True).stdout.strip()

    def test_health(self) -> None:
        self.assertEqual(self._imported_env("tools.health"), "[]")

    def test_the_test_package(self) -> None:
        self.assertEqual(self._imported_env("tools.tests"), "[]")

    def test_the_draft_gate(self) -> None:
        self.assertEqual(self._imported_env("tools.draft"), "[]")


class TheDraftGateNeverCommitsToTheRealRepository(unittest.TestCase):
    def test_a_baseline_built_under_a_hostile_environment_stays_in_its_scratch_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gitenv-") as td:
            root = Path(td)
            real = _real_repo(root)
            scratch = root / "scratch"
            scratch.mkdir()
            (scratch / "doc.md").write_text("# doc\n", encoding="utf-8")
            hostile = dict(os.environ, GIT_DIR=str(real / ".git"), GIT_WORK_TREE=str(real))
            code = f"from pathlib import Path; from tools.draft import gate; gate._init_repo(Path({str(scratch)!r}))"
            subprocess.run([sys.executable, "-c", code], cwd=_REPO, env=hostile, capture_output=True, text=True, check=True)
            self.assertEqual(_git(real, "rev-list", "--count", "HEAD"), "1", "the baseline commit landed in the REAL repository")
            self.assertEqual(_git(real, "log", "-1", "--format=%s"), "the real history")
            self.assertTrue((scratch / ".git").exists(), "the scratch directory did not get its own repository")
            self.assertEqual(_git(scratch, "rev-list", "--count", "HEAD"), "1")


if __name__ == "__main__":
    unittest.main()
