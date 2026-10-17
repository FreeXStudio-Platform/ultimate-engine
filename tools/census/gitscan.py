"""What the census reads from git: the tracked files, and each file's history in one pass.

Every git call runs with the repository-local environment scrubbed (``tools.gitenv``): a census run from a hook of a linked
worktree must read the repository it was pointed at, not the one the hook exported.

History is read ONCE (``git log --name-status -M``), newest first, and a rename is followed so a moved document keeps its
first-added date and its commit count instead of reading as "removed" plus "added". A path that was deleted and is not
in the tree is a removal; a path renamed away is not.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from tools import gitenv

_TIMEOUT = 600


class GitError(RuntimeError):
    """A git command the census needs failed."""


def git(root: Path, *args: str, check: bool = True) -> str:
    """Run ``git -C root ...`` with a clean environment and return stdout."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, env=gitenv.clean_env(), timeout=_TIMEOUT, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {' '.join(args[:3])}: {exc}") from exc
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args[:3])} failed ({proc.returncode}): {proc.stderr.strip()[:300]}")
    return proc.stdout


def head(root: Path) -> tuple[str, str]:
    """``(sha, committer date as YYYY-MM-DD)`` of ``HEAD``."""
    out = git(root, "log", "-1", "--format=%H%x09%cs").strip().split("\t")
    return out[0], out[1]


def is_dirty(root: Path) -> bool:
    return bool(git(root, "status", "--porcelain", "--untracked-files=no").strip())


def tracked(root: Path) -> list[str]:
    """Every tracked path, sorted, as git writes it."""
    return sorted(p for p in git(root, "ls-files", "-z").split("\0") if p)


@dataclass
class History:
    """Per current path: newest and oldest touch, commit count; plus the paths removed from the tree and when."""

    last_touch: dict[str, str] = field(default_factory=dict)
    first_seen: dict[str, str] = field(default_factory=dict)
    commits: dict[str, int] = field(default_factory=dict)
    removed: dict[str, str] = field(default_factory=dict)
    renamed: int = 0
    commit_count: int = 0
    recent: list[tuple[str, list[str]]] = field(default_factory=list)


def history(root: Path, current: set[str], since: str | None = None) -> History:
    """One pass over the whole history. ``current`` is the set of paths in the tree now.

    ``since`` (YYYY-MM-DD) additionally keeps, for every commit on or after that day, the paths it touched (``recent``).
    """
    raw = git(root, "log", "--name-status", "-M", "--no-color", "--format=%x01%cs")
    h = History()
    alias: dict[str, str] = {}
    date = ""
    cur: list[str] = []

    def flush() -> None:
        if since and date and date >= since and cur:
            h.recent.append((date, list(cur)))

    for line in raw.split("\n"):
        if line.startswith("\x01"):
            flush()
            cur = []
            date = line[1:].strip()
            h.commit_count += 1
            continue
        if not line or not date:
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) == 3:
            old, new = parts[1], parts[2]
            target = alias.get(new, new)
            alias[old] = target
            h.renamed += 1
            _touch(h, target, date)
            cur.append(target)
            continue
        if status.startswith("C") and len(parts) == 3:
            _touch(h, alias.get(parts[2], parts[2]), date)
            cur.append(alias.get(parts[2], parts[2]))
            continue
        if len(parts) < 2:
            continue
        path = alias.get(parts[1], parts[1])
        if status == "D":
            # Newest-first: a deletion seen first for a path means it was the last thing that happened to it.
            if path not in current and path not in h.removed and path not in h.last_touch:
                h.removed[path] = date
            cur.append(path)
            continue
        _touch(h, path, date)
        cur.append(path)
    flush()
    return h


def _touch(h: History, path: str, date: str) -> None:
    h.last_touch.setdefault(path, date)
    h.first_seen[path] = date  # newest-first, so the last assignment is the oldest
    h.commits[path] = h.commits.get(path, 0) + 1


def read(root: Path, path: str, limit: int = 2_000_000) -> str:
    """The working-tree text of a tracked file; undecodable bytes are replaced, an unreadable file reads as empty."""
    try:
        data = (root / path).read_bytes()[:limit]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def commit_exists(root: Path, sha: str) -> bool:
    """Whether ``sha`` (any unambiguous prefix) names a commit in this repository."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True, env=gitenv.clean_env(),
            timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def commits_since(root: Path, sha: str, path: str) -> int:
    """How many commits touched ``path`` after ``sha`` (0 when none, or when ``sha`` is not an ancestor-reachable commit)."""
    out = git(root, "rev-list", "--count", f"{sha}..HEAD", "--", path, check=False).strip()
    return int(out) if out.isdigit() else 0


def show(root: Path, sha: str, path: str) -> str | None:
    """The text of ``path`` as it was at ``sha``; ``None`` when the commit or the path does not exist there."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show", f"{sha}:./{path}"], capture_output=True, env=gitenv.clean_env(), timeout=120, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.decode("utf-8", errors="replace") if proc.returncode == 0 else None
