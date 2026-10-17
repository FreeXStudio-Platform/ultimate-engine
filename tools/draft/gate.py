"""Answer one question: *would this document be accepted if it landed right now?*

WHY THIS EXISTS, measured
=========================
Across three verification passes the largest single category of finding was not broken code. It was
**prose written without reading its neighbours** — counts already stale when typed, paths naming
nothing, claims contradicting the module they described, deferrals no plan accepted. Every one was
detectable by a guard that already existed. The guards simply ran at the END of a session, over the
whole corpus, after everything was written. So the cost of each error was *repair* rather than
*avoidance*, and one session was spent deleting defects from documents written earlier in the same
session.

Writing prose without running it is the same mistake as writing code without running it, and this
project would never ship the second.

HOW IT WORKS
============
Two runs of the same guards over two roots, and a set difference:

* **baseline** — the corpus as it exists at ``HEAD``, with the candidate absent.
* **candidate** — the same corpus with the candidate's WORKING-TREE bytes spliced in at its path.

Findings present in the candidate run and not in the baseline are what this document would
introduce. That difference is the answer, and it is the reason this is not simply
``corpus_check | grep <path>``: **adding a document changes facts elsewhere.** A new file moves a
tracked-document count that some other document states; a new register row can orphan a citation in
a third file. Those land on OTHER paths and a grep would miss every one of them.

Both roots are throwaway copies. The live tree is never modified, and no git command that writes is
ever run against it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.guards import GUARDS
from tools.corpus_check.model import Finding, Severity


def _repo_root() -> Path:
    """The HOST project being mapped — never this engine's own install directory.

    `Path(__file__).parents[2]` is the ENGINE's root, and it is the wrong question. This engine is
    vendored INTO other projects: a blueprint that maps the engine instead of the project consuming
    it is useless to the agent that asked for it, and silently so, because it still produces a
    plausible map. `engine_config.host_root()` is the one answer to "which project am I governing",
    already honoured by the CLI, the generator, the doc-system validator and the health run — this
    module invented a second answer, which is exactly the defect `RULES.md` Rule 1 names.
    """
    from tools.docgen import engine_config
    return engine_config.host_root()


def _export_tree(root: Path, dest: Path) -> None:
    """Unpack the tracked tree into ``dest``. A worktree, NOT yet a git repository.

    ``git archive`` rather than a filesystem copy: it yields exactly the committed state, with no
    build residue, no ignored directories and no half-saved editor files — which is what "the corpus
    as it exists" has to mean for the difference below to be meaningful.

    Split from ``_init_repo`` so the candidate lab can be copied from this worktree BEFORE either
    root owns an object database — see ``check``, and `OG-244` for the crash that bought the split.
    """
    dest.mkdir(parents=True, exist_ok=True)
    # THE WORKING TREE, not `HEAD`. The baseline has to be *what the corpus will look like when
    # this lands*, and code almost always lands with the document that describes it: checking a
    # draft against `HEAD` reported every command it documented as naming no module, because the
    # module was staged and not yet committed. `stash create` snapshots the working tree into a
    # dangling object WITHOUT touching the index, the worktree or the stash ref — it is the only
    # git command here that writes anything, and it writes nothing anyone can observe. It returns
    # empty when there is nothing to snapshot, hence the fallback.
    snapshot = subprocess.run(
        ["git", "-C", str(root), "stash", "create"],
        capture_output=True, text=True, check=False, timeout=180,
    ).stdout.strip()
    tar = subprocess.run(
        ["git", "-C", str(root), "archive", snapshot or "HEAD"],
        capture_output=True, check=True, timeout=180,
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=tar, check=True, timeout=180)


def _init_repo(dest: Path) -> None:
    """Turn an exported worktree into a git repository the guards can enumerate.

    ⚠ THE COPY MUST BE A GIT REPOSITORY, and this is the whole reason the first version of this
    gate was worthless. `Corpus` enumerates documents with `git ls-files`. An unpacked archive has
    no `.git`, so it enumerated NOTHING: every guard reported `checked=0`, found nothing, and the
    gate answered CLEAN for any input at all — including a probe naming a nonexistent module and an
    impossible guard count. A check the measured thing can satisfy by being invisible is not a
    check. `_assert_sees_the_corpus` below is what stops that returning.

    ``gc.auto=0`` is the second half of `OG-244`'s repair and it is not belt-and-braces. `git
    commit` ends by launching a DETACHED `gc --auto`; on a tree this size that background process
    packs the loose objects and prunes them within ~3 s, while this function's caller is still
    reading the lab. Measured on a 1,046-file host: 255 loose object directories immediately after
    the commit, zero of them three seconds later. Every git command run against a lab after this
    point — the guards' own `git ls-files`, `git cat-file` — is therefore racing a process that is
    deleting the files it reads. A lab lives for one run and is deleted; it never needs packing.
    """
    for cmd in (["git", "init", "-q", "."],
                # Set BEFORE the commit that would otherwise launch the collector.
                ["git", "config", "gc.auto", "0"],
                ["git", "add", "-A"],
                ["git", "-c", "user.email=draft@local", "-c", "user.name=draft",
                 "commit", "-q", "-m", "draft-gate baseline", "--no-verify"]):
        subprocess.run(cmd, cwd=dest, check=True, capture_output=True, timeout=300)


def _materialise(root: Path, dest: Path) -> None:
    """Export the tracked tree at ``root`` into ``dest`` and make it a repository."""
    _export_tree(root, dest)
    _init_repo(dest)


class EmptyCorpusError(RuntimeError):
    """The gate could not see the corpus, so its verdict would be meaningless."""


# The corpus examines thousands of claims. A copy the guards cannot read still reports a HANDFUL,
# because two guards fall back to a filesystem walk — so `total == 0` was not a floor at all: it
# was the number nine dressed as success. Measured: a non-repository copy of this tree checks 9.
# This floor is a RATCHET — raise it as the corpus grows, never lower it to make a run pass.
_VISIBILITY_FLOOR = 200


def _assert_sees_the_corpus(results: list[tuple[str, int]], root: Path | None = None) -> None:
    """Refuse to answer when the guards could not read the corpus.

    ANTI-VACUITY, checked TWO ways, because the first way was not enough:

    1. **The precondition, structurally.** ``Corpus`` enumerates documents with ``git ls-files``, so
       a copy that is not a git repository is invisible to it. That is a binary fact and it is
       asserted directly rather than inferred from an output number.
    2. **The floor, as a backstop.** A run examining fewer than ``_VISIBILITY_FLOOR`` claims has not
       seen this corpus, whatever the reason.

    A zero — or a nine — does not mean "no problems", it means "no visibility", and the two are
    indistinguishable in a verdict line. That is what let the first version of this gate report
    CLEAN for every input it was ever given.
    """
    if root is not None and not (root / ".git").is_dir():
        raise EmptyCorpusError(
            f"{root} is not a git repository, so `git ls-files` enumerates nothing and the corpus "
            "is invisible to every guard. The verdict would be CLEAN for any input."
        )
    total = sum(n for _, n in results)
    if total < _VISIBILITY_FLOOR:
        raise EmptyCorpusError(
            f"the guards examined {total} claims, below the visibility floor of "
            f"{_VISIBILITY_FLOOR} — the corpus was invisible, not clean. `Corpus` enumerates "
            "documents with `git ls-files`, so the usual cause is a copy that is not a git "
            "repository; it still reports a handful, because two guards fall back to a "
            "filesystem walk."
        )


def _findings(root: Path) -> list[Finding]:
    corpus = Corpus(root=root)
    out: list[Finding] = []
    seen: list[tuple[str, int]] = []
    for _name, run in GUARDS:
        try:
            result = run(corpus)
            out.extend(result.findings)
            seen.append((_name, getattr(result, "checked", 0) or 0))
        except Exception as exc:  # noqa: BLE001
            # A guard that CRASHES on the candidate is the strongest possible finding, and
            # swallowing it would let a document that breaks the checker sail through the check.
            # `guard=` is required, and omitting it made THIS handler — the one that exists so a
            # crashing guard is reported rather than lost — itself raise. The type checker caught
            # it; nothing else would have, because the path only runs when a guard is already
            # broken (`LESSONS.md` L-30: the type checker is a gate).
            out.append(Finding(guard=_name, path=str(root), line=0,
                               message=f"guard raised {type(exc).__name__}: {exc}",
                               severity=Severity.CRITICAL))
    _assert_sees_the_corpus(seen, root)
    return out


def _key(f: Finding) -> tuple[str, int, str]:
    return (f.path, f.line, f.message)


@dataclass
class DraftReport:
    """What this candidate would introduce, and where."""

    target: str
    introduced: list[Finding]
    on_the_draft: list[Finding]
    elsewhere: list[Finding]
    baseline_count: int
    candidate_count: int

    @property
    def clean(self) -> bool:
        return not self.introduced


def check(target: str, *, root: Path | None = None, source: Path | None = None) -> DraftReport:
    """Run the corpus guards on ``target`` as it stands in the working tree.

    ``target`` is repo-relative — the path the document will occupy. It does not need to exist at
    ``HEAD``: a brand-new document is simply absent from the baseline, which is exactly right.
    """
    root = root or _repo_root()
    src = source or (root / target)
    if not src.is_file():
        raise FileNotFoundError(f"no such candidate: {src}")
    body = src.read_bytes()

    with tempfile.TemporaryDirectory(prefix="draft-base-") as b, \
         tempfile.TemporaryDirectory(prefix="draft-cand-") as c:
        base_root, cand_root = Path(b) / "repo", Path(c) / "repo"
        # ORDER IS LOAD-BEARING: export, copy, place, and only THEN initialise. Exporting twice
        # would cost the same again for a tree that is byte-identical by construction, so the
        # candidate is still a copy — but a copy of a WORKTREE, taken while neither root owns a
        # `.git`.
        #
        # `OG-244`: the previous order materialised the baseline as a full repository and copied
        # THAT, object database included. `git commit` leaves a detached `gc --auto` running behind
        # it, which packs the loose objects and unlinks them; `shutil.copytree` walking
        # `.git/objects/` then read paths that had just been deleted and raised `shutil.Error`
        # before any guard ran. Reproduced 3/3 on a 1,046-file host and 0/3 on this repository's
        # own 362 files, which is exactly why self-checks never saw it: the gate crashed on every
        # project large enough to need it. Not copying a live object database removes the race
        # rather than narrowing it — the same treatment `test_blueprint_phase6` already gives every
        # lab copy it makes.
        _export_tree(root, base_root)
        shutil.copytree(base_root, cand_root)

        # The baseline must NOT contain the candidate. For a modified document `git archive` already
        # gives the committed version, which is the right baseline; for a new one there is nothing
        # to remove. Placed BEFORE `_init_repo`, so the `git add -A` inside it stages the candidate
        # as part of the initial commit.
        placed = cand_root / target
        placed.parent.mkdir(parents=True, exist_ok=True)
        placed.write_bytes(body)
        # IT MUST BE STAGED, or `git ls-files` cannot see it and the candidate run is identical to
        # the baseline — the second way this gate managed to answer CLEAN for every input. A file
        # written into a git repository is not IN it, and `Corpus` asks git, not the filesystem.
        # `_init_repo`'s `git add -A` is what stages it now; `_assert_sees_the_corpus` is what
        # proves the staging happened rather than assuming it.
        _init_repo(base_root)
        _init_repo(cand_root)

        before = _findings(base_root)
        after = _findings(cand_root)

    seen = {_key(f) for f in before}
    introduced = [f for f in after if _key(f) not in seen]
    return DraftReport(
        target=target,
        introduced=introduced,
        on_the_draft=[f for f in introduced if f.path == target],
        elsewhere=[f for f in introduced if f.path != target],
        baseline_count=len(before),
        candidate_count=len(after),
    )
