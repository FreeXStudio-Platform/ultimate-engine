"""The corpus every guard reads — **this repository's own tracked documents**.

`docs/CHARTER.md` purpose 2: the engine is proven by governing documentation someone actually
depends on, changing under real edits, in a repository with real history. So the corpus is not a
fixture directory. It is whatever ``git ls-files`` reports, loaded once and shared by every guard.

**Tracked, not on disk.** Resolution is against tracked content for the same reason `CONS-06` was
changed to: an untracked, gitignored file satisfied a citation locally and vanished on a fresh
clone, so a check passed on the author's machine and failed on everyone else's. A build artifact
that happens to exist because someone ran the build is not evidence that a document is real.

**Fail-closed.** If ``git`` cannot be reached, `Corpus.available` is ``False`` and every guard
reports SKIP. A corpus checker that silently checks an empty corpus is the vacuous-pass defect this
package exists to catch, so it is refused at the source rather than in nine places.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from tools.lib.front_matter import LEADING_COMMENT_LINES

# Front matter: an optional BOM, any number of leading HTML comments (`<!-- title: … -->` is this
# repo's house style), then a `---` fence. The comment sub-pattern is now IMPORTED, not copied, so
# "three places must not disagree about what a governed document means" is true by construction
# instead of by assertion — it was measurably false at 1.0.12 through 07a287b2, and this
# comment asserted the opposite the whole time.
#
# The copy that used to live here used a lazy dot-star comment token, which backtracks
# catastrophically on leading comments with no closing `---` fence — measured 9.2 s on 26 comments
# (234 bytes), and the caller's own `text[:4000]` cap does NOT bound it (still running after 30 s
# at the cap). HTML_COMMENT is linear on the same inputs: 0.015 ms at 26, 0.084 ms at the cap.
_FRONT_MATTER_RE = re.compile(
    rf"\A﻿?{LEADING_COMMENT_LINES}[ \t]*---[ \t]*\r?\n(.*?\r?\n)---",
    re.DOTALL,
)


@dataclass
class Corpus:
    """Tracked content plus the small amount of git this package needs, read once."""

    root: Path
    _text_cache: dict[str, str] = field(default_factory=dict, repr=False)

    # ---------------------------------------------------------------- git ----

    def git(self, *argv: str, timeout: int = 60) -> str | None:
        """Run a fixed-argv git command. ``None`` on any failure — never raises, never shells out.

        Every caller here treats ``None`` as "unknown", which propagates to a SKIP rather than to a
        guess. `tools/health/run.py` makes the same choice for the run log and states why: a value
        recorded as certain on evidence we could not obtain is a lie a later reader treats as fact.
        """
        try:
            proc = subprocess.run(
                ("git", "-C", str(self.root), *argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            # ValueError covers UnicodeDecodeError from text=True on undecodable git output.
            return None
        return proc.stdout if proc.returncode == 0 else None

    @cached_property
    def available(self) -> bool:
        """True when the tracked file list could actually be obtained."""
        return self._raw_tracked is not None

    @cached_property
    def _raw_tracked(self) -> str | None:
        return self.git("ls-files")

    # ------------------------------------------------------------- content ----

    @cached_property
    def tracked_all(self) -> tuple[str, ...]:
        """Every tracked path, repo-relative, POSIX separators — git's own listing, unfiltered.

        Use this **only** to answer *"does this path exist in the repository?"*. For anything that
        reads a file's CONTENT as a live claim, use ``tracked``, which excludes the archive.
        """
        raw = self._raw_tracked
        if raw is None:
            return ()
        return tuple(line for line in raw.splitlines() if line)

    @cached_property
    def archive_prefix(self) -> str:
        """The archive directory as a repo-relative prefix, e.g. ``docs/archive/``."""
        try:
            from tools.docgen import identity

            return identity.archive_prefix()
        except Exception:  # noqa: BLE001 - a missing/broken config must not disable the checker
            return "docs/archive/"

    def is_archived(self, rel: str) -> bool:
        """True when a path is a superseded snapshot rather than a live document.

        **An archived snapshot is a historical record, and a guard must not judge it as a claim.**
        Every textual guard here asks some form of *"is this sentence true NOW?"* — does this path
        exist, does this count re-derive, does this command still work, does this stamp still cover
        its body. A snapshot's whole purpose is to preserve what was true THEN, so running those
        questions over it manufactures findings for content nobody may edit: correcting an archived
        document would corrupt the record, and the audit's sha256 would (correctly) refuse it. The
        only honest answer is not to ask.
        """
        return rel.startswith(self.archive_prefix)  # identity.is_archived_path, prefix cached

    @cached_property
    def tracked(self) -> tuple[str, ...]:
        """Tracked paths whose content is a LIVE claim — everything except archived snapshots.

        Filtered here, at the single root every content selector below derives from, rather than in
        each guard. `docs/process/RULES.md` Rule 1: the question *"who else reads tracked content?"*
        has ten answers in this package — ``markdown``, ``python_files``, and the ``.html``/``.json``
        /``.sh``/``.py`` loops in ``built_claims``, ``crossrefs``, ``test_refs``, ``counts`` and
        ``rendered_output`` — and guarding one of them would have left the rest reading history as
        if it were an assertion.

        Citation resolution deliberately does NOT use this: ``tracked_set`` and ``tracked_dirs``
        come from ``tracked_all``, so a document may still cite an archived path and have it
        resolve. Excluding the archive from *reading* and from *existing* are different questions.
        """
        return tuple(rel for rel in self.tracked_all if not self.is_archived(rel))

    @cached_property
    def archived(self) -> tuple[str, ...]:
        """The archived snapshots themselves, for the guard that audits the archive."""
        return tuple(rel for rel in self.tracked_all if self.is_archived(rel))

    @cached_property
    def tracked_set(self) -> frozenset[str]:
        """Every tracked path as a set, for citation resolution — archive included."""
        return frozenset(self.tracked_all)

    @cached_property
    def tracked_dirs(self) -> frozenset[str]:
        """Every directory implied by a tracked path.

        Git tracks files, not directories, so ``docs/process`` appears in no listing even though
        every document cites it. Deriving the parents is what lets a citation to a directory
        resolve without the check having to special-case one.
        """
        dirs: set[str] = set()
        for rel in self.tracked_all:
            parts = rel.split("/")
            for i in range(1, len(parts)):
                dirs.add("/".join(parts[:i]))
        return frozenset(dirs)

    @cached_property
    def markdown(self) -> tuple[str, ...]:
        """Tracked Markdown documents that exist on disk — the corpus proper."""
        return tuple(
            rel for rel in self.tracked if rel.endswith(".md") and (self.root / rel).is_file()
        )

    @cached_property
    def python_files(self) -> tuple[str, ...]:
        """Tracked Python sources, for the guards that resolve symbols against real code."""
        return tuple(
            rel for rel in self.tracked if rel.endswith(".py") and (self.root / rel).is_file()
        )

    def text(self, rel: str) -> str:
        """Read a tracked file once and cache it. Unreadable files read as empty, never raise.

        Guards run over 56 documents and several read the same ones; re-reading per guard turned a
        one-second run into a many-second one for no new information.
        """
        cached = self._text_cache.get(rel)
        if cached is not None:
            return cached
        try:
            content = (self.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        self._text_cache[rel] = content
        return content

    def lines(self, rel: str) -> list[str]:
        """``text`` split into lines. Index ``i`` is line ``i + 1``."""
        return self.text(rel).splitlines()

    # ------------------------------------------------------------ governed ----

    def front_matter(self, rel: str) -> str | None:
        """The raw YAML front matter of a document, or ``None`` when it has none."""
        match = _FRONT_MATTER_RE.match(self.text(rel)[:4000])
        return match.group(1) if match else None

    @cached_property
    def governed(self) -> tuple[str, ...]:
        """Documents the engine governs: tracked Markdown declaring ``classification``.

        The same derivation `BUILD-02` and `CONS-09` use. Three definitions of "governed" would be
        three chances to disagree about the number `docs/CHARTER.md`'s whole argument rests on.
        """
        return tuple(
            rel
            for rel in self.markdown
            if (fm := self.front_matter(rel)) is not None and "classification" in fm
        )

    # --------------------------------------------------------------- utils ----

    def resolves(self, cited: str) -> bool:
        """True when a cited repo-relative path names tracked content (file **or** directory)."""
        target = cited.rstrip("/")
        return target in self.tracked_set or target in self.tracked_dirs

    def is_ignored(self, cited: str) -> bool:
        """True when git deliberately ignores this path.

        The distinction this draws is the one that separates *"not built yet"* from *"real, and
        deliberately not tracked"*. `docs/confidential/` is the engine's own vault: RULEBOOK L14
        says non-public documents may live only there, `--local-preview` writes into it, and
        `.gitignore` excludes it on purpose. A guard that treats untracked as unbuilt would report
        `CLASSIFICATION.md`'s sentence *"`docs/confidential/` is gitignored"* as a false present-tense
        claim — flagging a document for correctly describing a design decision.

        Asked with the path exactly as the document spells it, trailing slash included: git answers
        differently for ``docs/confidential`` and ``docs/confidential/`` when the directory does not
        exist locally, and the document's spelling is the claim being judged.
        """
        return self.git("check-ignore", cited) is not None

    def exists_untracked(self, cited: str) -> bool:
        """True when a path exists on disk but is not tracked — the most confusing failure.

        Worth distinguishing in a finding: "you never created this" and "this exists but will not
        survive a clone" need different fixes, and a message that cannot tell them apart sends the
        reader looking for the wrong one.
        """
        return (self.root / cited).exists() and not self.resolves(cited)


def repo_root(start: Path | None = None) -> Path:
    """The repository root — ``git rev-parse`` first, the package's own location as a fallback.

    The fallback matters: a verification lab is built with ``git archive`` into a fresh directory,
    and asking git there answers about the lab, which is the correct answer. Where git is absent
    entirely, ``tools/corpus_check/corpus.py`` is three levels below the root by construction.
    """
    here = start or Path(__file__).resolve()
    try:
        proc = subprocess.run(
            ("git", "-C", str(here.parent), "rev-parse", "--show-toplevel"),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return Path(__file__).resolve().parents[2]
