"""Git's repository-local environment, scrubbed — so a scratch repository is never the real one.

A hook run from a LINKED worktree (``git worktree add``) exports ``GIT_DIR`` (and, for ``pre-commit``, ``GIT_INDEX_FILE``).
A child that then runs ``git init -q .`` / ``git commit`` in a scratch directory inherits it, and git obeys the variable
over the working directory: the "scratch" repository IS the real one. Measured 2026-10-10 on the pre-push hook of the
explorer release: three ``draft-gate baseline`` commits and one ``base`` commit landed on the branch being pushed, the index
turned into 406 staged additions, and the health run read 55 errors and a skipped ``STRUCT-04``. A main clone exports neither,
so the engine's own release process (run from the main clone) never saw it.

The variables to drop are the ones git itself names: ``git rev-parse --local-env-vars``. The list is read from git when git is
available and falls back to the list below (git 2.4x), so a newer git that adds one is still covered.

Stdlib only; no side effect at import.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, MutableMapping
from typing import Final

_FALLBACK: Final = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY",
    "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE", "GIT_PREFIX", "GIT_SHALLOW_FILE", "GIT_COMMON_DIR",
)


def local_vars() -> tuple[str, ...]:
    """The variables that make a git command act on a specific repository: git's own list, else the fallback."""
    try:
        out = subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return _FALLBACK
    names = tuple(n for n in out.stdout.split() if n.startswith("GIT_"))
    return tuple(dict.fromkeys(names + _FALLBACK)) if out.returncode == 0 and names else _FALLBACK


def clean_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of ``base`` (default: the process environment) without the repository-local variables."""
    drop = set(local_vars())
    return {k: v for k, v in (os.environ if base is None else base).items() if k not in drop}


def scrub(environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Remove the repository-local variables from ``environ`` (default ``os.environ``) in place; return what was removed."""
    target = os.environ if environ is None else environ
    removed = [k for k in local_vars() if k in target]
    for k in removed:
        del target[k]
    return removed
