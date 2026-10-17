"""The throwaway-lab helpers, in ONE place — used by every probe that needs a real repository.

WHY THIS MODULE EXISTS
======================
`RULES.md` Rule 1: *fix the CLASS, not the instance.* Two test modules independently grew the same
three helpers — copy this repository into a temporary directory, make it a git repository, and tear
it down afterwards past git's read-only object files. The second copy was written in the session
that created this file, and writing it was the finding: two implementations of one idea drift, and
the ``_force_rmtree`` pair had **already** drifted — one copy carried two ``type: ignore`` comments
the other did not, and mypy reported them as unused.

So the helpers live here and both callers import them. That is the same argument `tools/lib/
md_table.py` settled for Markdown tables, where five readers of one format were measured
disagreeing about the manifest's own header cell.

WHAT A LAB IS, AND WHY IT IS A COPY RATHER THAN A FIXTURE
=========================================================
`DOC_WRITING_DOCTRINE.md` §5: *read real source off disk; never compare a copied literal against
itself.* A guard proven against three hand-written documents has been proven against its author's
imagination. A lab is the **whole tracked tree**, copied, so probes run against the same corpus and
the same 97 modules the real commands do — and can plant a defect in it without touching the
working tree the session is editing (`LESSONS.md` L-09).

``git ls-files -c -o --exclude-standard`` is tracked **plus** untracked-but-not-ignored, so code
written in the current session is present in the lab without needing a commit first. Ignored trees
such as ``node_modules`` are excluded by construction.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def git(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    """Run git in the lab, raising on failure — a lab that cannot be set up is not a test result."""
    return subprocess.run(
        ("git", "-C", str(cwd), *argv),
        check=True, capture_output=True, text=True, timeout=120,
    )


def commit_all(cwd: Path, message: str) -> str:
    """Commit everything in the lab and return the new HEAD.

    ``--allow-empty`` because a probe that re-plants a file a previous probe removed leaves the
    index matching ``HEAD``; git then exits 1 with "nothing to commit", which is not a failure of
    anything under test. The stamp probes need a real sha more than they need a real diff.
    """
    git(cwd, "add", "-A")
    git(cwd, "-c", "user.name=lab", "-c", "user.email=lab@local",
        "commit", "-q", "--allow-empty", "-m", message)
    out = subprocess.run(
        ("git", "-C", str(cwd), "rev-parse", "HEAD"),
        check=True, capture_output=True, text=True, timeout=60,
    )
    return out.stdout.strip()


def build_lab(dest: Path) -> None:
    """Copy this repository into ``dest`` and make it a git repository of its own."""
    listing = subprocess.run(
        ("git", "-C", str(ROOT), "ls-files", "-c", "-o", "--exclude-standard"),
        check=True, capture_output=True, text=True, timeout=180,
    ).stdout.split("\n")
    for rel in listing:
        if not rel:
            continue
        src = ROOT / rel
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    git(dest, "init", "-q")
    commit_all(dest, "lab")


def force_rmtree(path: Path) -> None:
    """Remove a tree containing git's read-only object files.

    ``shutil.rmtree`` cannot unlink a mode-444 file on every platform, and every lab is a real git
    repository, so ``.git/objects/**`` is full of them.
    """
    def _chmod_and_retry(func: object, target: str, _exc: object) -> None:
        try:
            Path(target).chmod(0o700)
        except OSError:
            # Can't even make it writable (already gone, permissions we don't own, …) — nothing
            # left to retry. Deliberately silent: this whole callback is `setUpClass`'s documented
            # backstop, never allowed to turn a green suite red over leftover temp-dir bytes (N22).
            return
        if callable(func):
            try:
                func(target)
            except OSError:
                # The retried removal still failed. Same backstop contract as above — a directory
                # `shutil.rmtree` could not fully clear is a leaked temp dir, not a test failure.
                pass

    # README declares Python 3.11+; `onexc` is 3.12+. The callback ignores its third argument,
    # so it serves both hooks unchanged.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_chmod_and_retry)
    else:
        shutil.rmtree(path, onerror=_chmod_and_retry)


class LabCase(unittest.TestCase):
    """Base class owning one faithful copy of the tree, built once per class.

    Once per CLASS rather than once per test: building a lab copies ~340 files and initialises a git
    repository, which is seconds. Per-test setup would make the suite too slow to run every pass,
    and a suite nobody runs is not a gate.
    """

    lab: Path
    _tmp: tempfile.TemporaryDirectory[str]
    lab_prefix = "lab-"

    @classmethod
    def setUpClass(cls) -> None:
        # `ignore_cleanup_errors` because a lab is a real git repository and git writes its object
        # files read-only. `force_rmtree` clears them properly; this is the backstop, so a leftover
        # temp directory can never turn a green suite red for a reason unrelated to anything under
        # test.
        cls._tmp = tempfile.TemporaryDirectory(prefix=cls.lab_prefix, ignore_cleanup_errors=True)
        cls.lab = Path(cls._tmp.name) / "repo"
        cls.lab.mkdir(parents=True)
        build_lab(cls.lab)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            force_rmtree(Path(cls._tmp.name))
        except OSError:
            # Deliberately silent (N22): `cls._tmp.cleanup()` right below is the REAL safety net —
            # it was built with `ignore_cleanup_errors=True` in `setUpClass` precisely so a
            # leftover read-only git object file can never fail a test class over cleanup, only
            # leave a stray temp directory behind.
            pass
        cls._tmp.cleanup()
