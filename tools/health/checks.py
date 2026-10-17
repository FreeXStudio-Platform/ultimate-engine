"""The health checks themselves, in execution order.

**Adding a check is one entry in ``CHECKS``** at the bottom of this file. Each check is a plain
function taking a ``Ctx`` and returning a ``CheckResult`` — no registration elsewhere, no base class
to subclass. That is deliberate: the cost of adding a guard should be near zero, or guards do not
get added.

Every check must return real evidence. A ``PASS`` whose evidence is empty is indistinguishable from
a check that did nothing.
"""

from __future__ import annotations

import ast
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tools.corpus_check.text import (
    is_append_only_record,
    iter_prose_lines_with_headings,
    under_dated_heading,
)
from tools.health.model import CheckResult, Stage, Status
from tools.lib import md_table
from tools.lib.front_matter import LEADING_COMMENT_LINES


@dataclass(frozen=True)
class Ctx:
    """Everything a check needs to locate the engine. Resolved once, in ``run.py``."""

    root: Path
    doc_system: Path
    full: bool


CheckFn = Callable[[Ctx], CheckResult]

# The five change types documented in adjudication.py's docstring and validate_doc_system's --help.
# These are a FLOOR, not the universe: RULE-03 derives what to validate from the map's own keys
# (see check_impact_map) and uses this tuple only to assert the documented five have not vanished.
# It used to be the universe, which meant a sixth change type added to update_impact_map.json got
# zero validation — the check's answer came from the same place as its question (LESSONS.md L-13).
_BASELINE_CHANGE_TYPES = (
    "DETECTOR_CHANGE",
    "VISUAL_STYLE_CHANGE",
    "USER_POLICY_CHANGE",
    "ARCHITECTURE_CHANGE",
    "RULE_CHANGE",
)

# Core documents the project's own process depends on. Absence is a structural defect, not taste.
_CORE_DOCS = (
    "HANDOFF.md",
    "CHANGELOG.md",
    "PROJECT_VERSION",
    "docs/plan/BUILD_PLAN.md",
    "docs/framework/DOC_WRITING_DOCTRINE.md",
    "docs/process/DEEP_VERIFICATION_PASS.md",
    "docs/process/LESSONS.md",
    "docs/process/OPEN_GATES.md",
    # Added 2026-08-20. These were UNPROTECTED: the two files that hand work to the next session
    # could vanish with health still green, and ABSENT_PATHS.md is machine-read by CONS-06, so
    # deleting it would silently widen that check instead of failing it.
    "docs/process/ABSENT_PATHS.md",
    "docs/plan/NEXT_SESSION.md",
    "docs/plan/START_NEXT_SESSION.md",
)


def _ok(cid: str, stage: Stage, summary: str, evidence: str = "") -> CheckResult:
    return CheckResult(check_id=cid, stage=stage, status=Status.PASS, summary=summary, evidence=evidence)


def _fail(cid: str, stage: Stage, summary: str, evidence: str = "", detail: list[str] | None = None) -> CheckResult:
    return CheckResult(
        check_id=cid, stage=stage, status=Status.FAIL, summary=summary, evidence=evidence, detail=detail or []
    )


def _skip(cid: str, stage: Stage, summary: str, evidence: str = "") -> CheckResult:
    return CheckResult(check_id=cid, stage=stage, status=Status.SKIP, summary=summary, evidence=evidence)


# ======================================================================================
# 1 — STRUCTURE
# ======================================================================================


def check_core_docs(ctx: Ctx) -> CheckResult:
    """The process documents this project runs on must exist."""
    missing = [p for p in _CORE_DOCS if not (ctx.root / p).is_file()]
    if missing:
        return _fail(
            "STRUCT-01", Stage.STRUCTURE, f"{len(missing)} core document(s) missing", ", ".join(missing), missing
        )
    # Existence is not content. Truncating all seven of these to zero bytes left this check green
    # (they still "exist") and `CONS-08` green too (it validates only claims it can FIND, and zero
    # bytes contain none) — so the entire handover could be destroyed with a fully healthy engine.
    #
    # The floor is per-KIND, not flat. The first draft used one byte count for everything and
    # immediately failed on `PROJECT_VERSION`, which legitimately holds five bytes — a blanket
    # threshold across heterogeneous artifacts is a false-positive generator, and a check that cries
    # wolf gets bypassed, which is worse than the gap it closes.
    _MIN_DOC_BYTES = 200
    empty: list[str] = []
    for rel in _CORE_DOCS:
        path = ctx.root / rel
        size = path.stat().st_size
        if rel.endswith(".md"):
            if size < _MIN_DOC_BYTES:
                empty.append(f"{rel} ({size} bytes, floor {_MIN_DOC_BYTES})")
        else:
            # Not a document: require content that still parses as what it is meant to be.
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                empty.append(f"{rel} (empty)")
            elif rel == "PROJECT_VERSION" and not re.fullmatch(r"\d+\.\d+\.\d+", text):
                empty.append(f"{rel} ({text[:30]!r} is not a semver)")
    if empty:
        return _fail("STRUCT-01", Stage.STRUCTURE,
                     f"{len(empty)} core document(s) exist but carry no usable content",
                     "; ".join(empty), empty)
    return _ok("STRUCT-01", Stage.STRUCTURE,
               f"all {len(_CORE_DOCS)} core documents present and non-empty")


def check_locked_files_exist(ctx: Ctx) -> CheckResult:
    """Every file VERSION.json locks must be on disk — the hash-gate fails closed without them."""
    vj = ctx.doc_system / "VERSION.json"
    if not vj.is_file():
        return _fail("STRUCT-02", Stage.STRUCTURE, "VERSION.json absent", str(vj))
    try:
        data = json.loads(vj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail("STRUCT-02", Stage.STRUCTURE, f"VERSION.json is not valid JSON: {exc}", str(vj))
    files = data.get("rulebook_files")
    if not isinstance(files, list) or not files:
        return _fail("STRUCT-02", Stage.STRUCTURE, "rulebook_files missing or empty", str(vj))
    missing = [f for f in files if not (ctx.root / str(f)).is_file()]
    if missing:
        return _fail("STRUCT-02", Stage.STRUCTURE, f"{len(missing)} locked file(s) missing", ", ".join(map(str, missing)))
    return _ok("STRUCT-02", Stage.STRUCTURE, f"all {len(files)} locked rulebook files present")


# Each installed hook must be present, executable, byte-identical to its tracked source, AND still
# contain the invocations that make it a gate. Byte-identity alone proves FIDELITY, not
# EFFECTIVENESS: `tools/hooks/pre-push` is an ordinary tracked file that nothing hashes, so
# replacing it with `exit 0` and reinstalling would leave the check green while the moat did
# nothing. An inert moat is loud; a NEUTERED moat would have been silent.
# Markers are matched against the hook's EXECUTABLE lines only — see ``_executable_text``. They
# name the invocation, not the topic: "tools.health" appears in this file's own prose, whereas
# "-m tools.health" is how the hook actually runs the gate.
_HOOK_MARKERS: dict[str, tuple[str, ...]] = {
    # gate 3 (`staged_content_scanner`) and the gate-count assertion are named too: without a
    # marker each could be deleted outright without failing this test.
    "pre-push": ("-m tools.health", '"$SCANNER"', "staged_content_scanner", "GATES_EXPECTED"),
    "pre-commit": ("staged_content_scanner", '"$SCANNER"', "GATES_EXPECTED"),
}

# AWS's own published documentation key, split so this literal is not itself a scannable secret in
# a tracked file. It is the standard non-credential fixture for exactly this purpose.
_PROBE_PLANTED_VALUE = "AKIA" + "IOSFODNN7EXAMPLE"


def _executable_text(source_bytes: bytes) -> str:
    """The hook's text with whole-line comments removed.

    A marker search over the RAW text is satisfied by a COMMENT. An independent pass reduced both
    moat hooks to six-line ``exit 0`` bodies that merely *mentioned* the marker strings in comments,
    installed them, and health reported ``installed, current, and still gating`` while a secret
    sailed to a remote. Stripping comment lines is what makes this test describe what the hook
    DOES rather than what it says about itself.
    """
    out: list[str] = []
    for line in source_bytes.decode("utf-8", errors="replace").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue                       # whole-line comment
        # A TRAILING comment defeated the whole-line rule: `exit 0  # -m tools.health "$SCANNER"`
        # satisfied every marker while the hook did nothing. Cut at the first `#` that follows
        # whitespace and is outside quotes. This is an approximation of shell lexing and is stated
        # as one — its job is to stop a marker hiding in a comment, not to parse bash.
        cut, in_s, in_d, prev = None, False, False, ""
        for i, ch in enumerate(line):
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif ch == "#" and not in_s and not in_d and (i == 0 or prev in " \t"):
                cut = i
                break
            prev = ch
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


# The nesting marker. **A token backed by a marker file, not the literal string "1"** — and the
# difference is the difference between a recursion guard and a bypass switch.
#
# It was `ENGINE_IN_HOOK_PROBE=1`, tested with `== "1"`, and it gated `STRUCT-04`'s behavioural
# probe AND the whole of `SUITE-05`. Anyone with that variable exported in their shell — an
# operator who set it once while debugging, a CI job that inherited it — got a health run in which
# the hook is never actually exercised and the counter-example suite never runs, reported as SKIP
# and passed straight through the pre-push moat, which does not use `--full`. One `export` silently
# removing a moat is precisely the fail-open shape this engine exists to refuse (`OG-103`).
#
# A REAL nesting is now proved, not asserted: the outer run mints a random token, writes a marker
# file named by it into a directory only that process owns, and exports both. An inner run honours
# the skip only when the file it names exists. A variable left over in a shell names no live file,
# so the checks run normally — which is the safe direction. `tempfile` gives the file 0600 in a
# private directory, so this is not a lock another user can forge.
_PROBE_VAR = "ENGINE_IN_HOOK_PROBE"
_PROBE_MARKER_VAR = "ENGINE_HOOK_PROBE_MARKER"


def _mint_probe_marker(env: dict[str, str]) -> tempfile.TemporaryDirectory[str]:
    """Mark ``env`` as nested and return the marker's lifetime holder.

    The returned object must be kept alive for as long as the nested runs may occur; when it is
    cleaned up the marker vanishes and the guard stops applying, which is the correct default.
    """
    holder = tempfile.TemporaryDirectory(prefix="engine-probe-token-")
    token = secrets.token_hex(16)
    marker = Path(holder.name) / f"{token}.marker"
    marker.write_text(token, encoding="utf-8")
    env[_PROBE_VAR] = token
    env[_PROBE_MARKER_VAR] = str(marker)
    return holder


def _inside_hook_probe() -> bool:
    """True only for a run genuinely nested inside a live outer probe."""
    token = os.environ.get(_PROBE_VAR)
    marker = os.environ.get(_PROBE_MARKER_VAR)
    if not token or not marker:
        return False
    try:
        return Path(marker).read_text(encoding="utf-8").strip() == token
    except OSError:
        return False


def _hook_behaviour_probe(ctx: Ctx, installed: Path) -> tuple[bool, str]:
    """Run the installed hook twice in a throwaway repo: clean must pass, a planted secret must fail.

    Two-sided on purpose. A one-sided probe ("does it refuse a secret?") passes vacuously whenever
    the hook refuses *everything* — a missing scanner, a broken interpreter, a stub that exits 1.
    Only "accepts clean AND refuses dirty" distinguishes a gate from both a stub and a brick.

    Returns ``(ok, detail)``. ``ok`` False with a detail beginning ``inconclusive:`` means the probe
    could not be run and the caller should SKIP rather than fail — a skip is unknown, never green.
    """
    git = shutil.which("git")
    if git is None:
        return False, "inconclusive: git not on PATH"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ctx.root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.update(GIT_AUTHOR_NAME="probe", GIT_AUTHOR_EMAIL="probe@invalid",
               GIT_COMMITTER_NAME="probe", GIT_COMMITTER_EMAIL="probe@invalid")
    # The bypass must not leak in from the caller's environment, or the probe proves nothing.
    for var in ("ENGINE_SKIP_PRECOMMIT", "ENGINE_SKIP_PREPUSH"):
        env.pop(var, None)
    # Mark the environment as "already inside a hook probe". A hook invoked here may itself run
    # `tools.health` (pre-push does), and that inner run would start its OWN probe — the same real
    # work, one level down, for no additional evidence. Unmarked, the cost compounds: this probe is
    # ~72 s, `hook_attacks.sh` performs ~20 lab pushes, and SUITE-06 consequently blew through its
    # 1800 s ceiling and reported a TIMEOUT rather than a result. A gate that cannot finish is a
    # gate that fails for environmental reasons, which is exactly the failure mode this engine
    # refuses elsewhere. The OUTER probe still runs every attack and asserts every refusal, so
    # nothing is weakened — only the redundant inner repetition is skipped.
    probe_marker = _mint_probe_marker(env)
    try:
      with probe_marker, tempfile.TemporaryDirectory(prefix="engine-hookprobe-") as td:
              repo = Path(td)
              def run(args: list[str]) -> subprocess.CompletedProcess[str]:
                  return subprocess.run(args, cwd=repo, env=env, capture_output=True,
                                        text=True, timeout=60, check=False)
              if run([git, "init", "-q", "."]).returncode != 0:
                  return False, "inconclusive: git init failed in the probe repo"
              # A MATRIX, not one fixture. The first version planted exactly one file, at the repo
              # root, carrying exactly one secret — so it could distinguish a hook that refuses
              # NOTHING from one that refuses SOMETHING, and nothing finer. Any narrowing of scope (a
              # path exclusion, a suffix filter, a size cap) was invisible to it, and it never planted
              # a classified document at all, so the placement gate had no behavioural coverage.
              (repo / "clean.txt").write_text("nothing to see here\n", encoding="utf-8")
              (repo / "docs").mkdir(exist_ok=True)
              (repo / "docs" / "clean.md").write_text("# ordinary document\n", encoding="utf-8")
              run([git, "add", "clean.txt", "docs/clean.md"])
              clean = subprocess.run([str(installed)], cwd=repo, env=env, capture_output=True,
                                     text=True, timeout=120, check=False)
              if clean.returncode != 0:
                  return False, ("inconclusive: the hook refused a CLEAN index (exit "
                                 f"{clean.returncode}) — probe cannot distinguish a gate from a brick: "
                                 + (clean.stderr or clean.stdout).strip().replace("\n", " ")[:160])
              # Each probe is planted and tested ALONE, so a refusal names the dimension that caught
              # it. Nested and odd-extension placements exist because scope narrowing is the failure
              # this cannot otherwise see.
              probes: list[tuple[str, str, str]] = [
                  ("secret at the repo root", "planted.txt",
                   f"AWS_ACCESS_KEY_ID={_PROBE_PLANTED_VALUE}\n"),
                  ("secret nested deep", "docs/deep/nested/planted.txt",
                   f"AWS_ACCESS_KEY_ID={_PROBE_PLANTED_VALUE}\n"),
                  ("secret in an odd extension", "notes.rst",
                   f"AWS_ACCESS_KEY_ID={_PROBE_PLANTED_VALUE}\n"),
                  ("classified document outside the vault", "docs/secret-plan.md",
                   (
                       "---\nid: PRB-001\ntitle: t\nclassification: secret\nsurface: none\n"
                       "audience: a\nowner: o\nstatus: draft\nlast_reviewed: 2026-01-01\n---\n\n# x\n"
                   )),
              ]
              accepted: list[str] = []
              for label, rel, body in probes:
                  target = repo / rel
                  target.parent.mkdir(parents=True, exist_ok=True)
                  target.write_text(body, encoding="utf-8")
                  run([git, "add", rel])
                  dirty = subprocess.run([str(installed)], cwd=repo, env=env, capture_output=True,
                                         text=True, timeout=120, check=False)
                  if dirty.returncode == 0:
                      accepted.append(label)
                  run([git, "rm", "-q", "-f", "--cached", rel])
                  target.unlink(missing_ok=True)
              if accepted:
                  return False, ("the installed hook exited 0 over: " + "; ".join(accepted)
                                 + " — it does not gate those dimensions")
              return True, (f"probed live across {len(probes)} dimensions: clean index accepted, "
                            "and every planted probe refused")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return False, f"inconclusive: probe could not run: {exc}"


# pre-push runs `python3 -m tools.health` as its first gate, so probing it from inside a health
# check would recurse. pre-commit has no such dependency and IS probed live.
_BEHAVIOURALLY_PROBED = frozenset({"pre-commit"})


def _hook_check(ctx: Ctx, name: str, check_id: str) -> CheckResult:
    """Shared body for the installed-hook checks. See ``_HOOK_MARKERS`` for why content matters.

    ``.git/hooks/`` is not version-controlled, so a hook cannot arrive with a clone; it has to be
    copied in once per checkout. That is exactly how the git moat stayed inert through all of
    Phase 1 — the hook existed as a file in the tree that nobody had run, and nothing said so.

    Outside a git repository the question cannot be answered at all, so it SKIPs with the cause: a
    skip is unknown, never green.
    """
    source = ctx.root / "tools" / "hooks" / name
    fix = "run: bash tools/hooks/install.sh"
    if not source.is_file():
        return _fail(check_id, Stage.STRUCTURE, f"hook source missing: tools/hooks/{name}", str(source))

    try:
        proc = subprocess.run(
            ("git", "-C", str(ctx.root), "rev-parse", "--git-path", "hooks"),
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return _skip(check_id, Stage.STRUCTURE, "cannot locate .git/hooks", str(exc))
    if proc.returncode != 0:
        return _skip(check_id, Stage.STRUCTURE, "not a git repository — no hooks to check",
                     proc.stderr.strip()[:200])

    hooks_dir = Path(proc.stdout.strip())
    if not hooks_dir.is_absolute():
        hooks_dir = ctx.root / hooks_dir
    installed = hooks_dir / name

    if not installed.is_file():
        return _fail(check_id, Stage.STRUCTURE,
                     f"{name} hook NOT installed — that gate is opt-in", f"{installed} absent; {fix}")
    source_bytes = source.read_bytes()
    if source_bytes != installed.read_bytes():
        return _fail(check_id, Stage.STRUCTURE,
                     f"installed {name} hook has drifted from tools/hooks/{name}",
                     f"{installed} differs from {source}; {fix}")
    if not os.access(installed, os.X_OK):
        return _fail(check_id, Stage.STRUCTURE, f"{name} hook is not executable",
                     f"{installed} lacks +x; {fix}")
    text = _executable_text(source_bytes)
    missing = [marker for marker in _HOOK_MARKERS[name] if marker not in text]
    if missing:
        return _fail(check_id, Stage.STRUCTURE,
                     f"{name} hook no longer invokes its gate(s)",
                     f"tools/hooks/{name} has no executable line containing: {', '.join(missing)}",
                     missing)
    if name in _BEHAVIOURALLY_PROBED and _inside_hook_probe():
        # Set only by _hook_behaviour_probe itself. See the comment there: re-probing inside a probe
        # buys no evidence and costs ~72 s per nested invocation.
        return _skip(check_id, Stage.STRUCTURE,
                     f"{name} hook installed and current; behavioural probe skipped inside a probe",
                     "a live outer probe marker is present — that probe is already exercising this hook")
    if name in _BEHAVIOURALLY_PROBED:
        ok, detail = _hook_behaviour_probe(ctx, installed)
        if not ok:
            if detail.startswith("inconclusive:"):
                return _skip(check_id, Stage.STRUCTURE,
                             f"{name} hook is installed and current, but could not be probed", detail)
            return _fail(check_id, Stage.STRUCTURE,
                         f"{name} hook is installed but DOES NOT GATE", detail)
        return _ok(check_id, Stage.STRUCTURE, f"{name} hook installed, current, and proven to gate",
                   f"{installed} matches tools/hooks/{name}; {detail}")
    return _ok(check_id, Stage.STRUCTURE, f"{name} hook installed, current, and still gating",
               f"{installed} matches tools/hooks/{name} and invokes {', '.join(_HOOK_MARKERS[name])}"
               " (structural: see OPEN_GATES for why pre-push is not behaviourally probed)")


def check_prepush_hook_installed(ctx: Ctx) -> CheckResult:
    """The push-time moat (engine health + a secret scan of the pushed content) must be live."""
    return _hook_check(ctx, "pre-push", "STRUCT-03")


def check_precommit_hook_installed(ctx: Ctx) -> CheckResult:
    """The commit-time moat (classification placement + a secret scan of the index) must be live."""
    return _hook_check(ctx, "pre-commit", "STRUCT-04")


def engine_config_confidential_relative(ctx: Ctx) -> str:
    """The configured vault path, host-root-relative. Honours `ENGINE_CONFIDENTIAL_DIR`."""
    try:
        from tools.docgen import engine_config

        return engine_config.confidential_dir_relative()
    except Exception:  # noqa: BLE001 - config problems are reported by their own checks
        return "docs/confidential"


_SESSION_STAMP_RE = re.compile(
    r"<!--\s*session-state:\s*([A-Z][A-Z-]*)\s*@\s*([0-9a-f]{7,40})\s+on\s+"
    r"(\d{4}-\d{2}-\d{2})\s+via\s+([^\s>]+)\s*-->"
)
# The state VOCABULARY is derived from the document's own table, not hardcoded here. Hardcoding it
# would put the answer and the question in two places that drift (LESSONS.md L-13): adding a state
# to the document would then fail a check that claims to validate the document.
_SESSION_STATE_ROW_RE = re.compile(r"^\|\s*`([A-Z][A-Z-]*)`\s*\|", re.MULTILINE)

#: "Is this tracked document GOVERNED?" — the front-matter reader `CONS-09` and `BUILD-02` share.
#:
#: Both checks spelled this pattern inline, byte-identically, inside their own file
#: loops. Two copies of one question is the shape that started this sequence of fixes, and it had
#: a second cost here: the differential that proves nothing base 1.0.12 accepted was lost could not
#: pin either site, because an f-string argument is a `JoinedStr` and not a `Constant` the `ast`
#: walk can read. One module-level constant is both the deduplication and the handle the test needs.
_GOVERNED_FRONT_MATTER_RE = re.compile(
    rf"\A\ufeff?{LEADING_COMMENT_LINES}[ \t]*---[ \t]*\r?\n(.*?\r?\n)---", re.DOTALL
)


def check_session_state_stamp(ctx: Ctx) -> CheckResult:
    """The crash-recovery record must carry a stamp that parses and points at real history.

    ``docs/process/SESSION_STATE.md`` is the first thing a session reads after a crash, and its whole
    value is that a fresh session can trust it instead of redoing finished work. A stamp that is
    missing, malformed, invents a state word, or names a commit that no longer exists would send that
    session to re-derive everything by hand — or worse, to believe a checklist it should not.

    This checks the MECHANICAL half only, and says so: that a stamp exists, parses, uses a state the
    document itself defines, names a commit that is real, and is an ancestor of `HEAD`. Whether the
    checklist is *honest* is not machine-decidable and is not claimed here.
    """
    path = ctx.root / "docs" / "process" / "SESSION_STATE.md"
    if not path.is_file():
        return _fail("STRUCT-06", Stage.STRUCTURE, "session-state record missing",
                     f"{path} absent — a crash would leave no record of what was finished")
    text = path.read_text(encoding="utf-8", errors="replace")
    states = set(_SESSION_STATE_ROW_RE.findall(text))
    if not states:
        return _fail("STRUCT-06", Stage.STRUCTURE,
                     "session-state document defines no state vocabulary",
                     "no `| `STATE` |` table rows found; the stamp cannot be validated against "
                     "anything, so this check would pass vacuously (LESSONS.md L-19)")
    stamp = _SESSION_STAMP_RE.search(text[:4000])
    if stamp is None:
        return _fail("STRUCT-06", Stage.STRUCTURE, "session-state stamp missing or malformed",
                     "expected `<!-- session-state: <STATE> @ <commit> on <YYYY-MM-DD> via <pass> -->` "
                     "near the top of docs/process/SESSION_STATE.md")
    state, sha, date, pass_name = stamp.groups()
    if state not in states:
        return _fail("STRUCT-06", Stage.STRUCTURE,
                     f"session-state stamp uses an undefined state: {state}",
                     f"the document defines {', '.join(sorted(states))}")
    code, out = _run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], ctx.root, timeout=30)
    if code != 0:
        # SKIP, not FAIL — and the distinction is the honest one. "The stamped commit is not in this
        # repository" has two causes that look identical from here: history was rewritten, or this is
        # a detached export with a fresh history (`git archive` + `git init`), which is exactly how
        # every verification lab in this project is built. Failing would paint every lab red for a
        # reason that has nothing to do with what the lab is testing, and a gate that is red for
        # irrelevant reasons is a gate people learn to ignore.
        #
        # A SKIP is not a soft pass here: it is unknown, `--full` and `--strict` both fail on one,
        # and the cause names both possibilities so a reader can tell which applies.
        return _skip("STRUCT-06", Stage.STRUCTURE,
                     f"session-state stamp names a commit not present here: {sha}",
                     "either history was rewritten (re-derive the checklist from git log and "
                     "CHANGELOG.md before trusting it) or this is a detached export/verification "
                     f"lab with its own fresh history, where the record cannot be validated. {out.strip()[:120]}")
    code, _ = _run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], ctx.root, timeout=30)
    if code != 0:
        return _fail("STRUCT-06", Stage.STRUCTURE,
                     f"HEAD is BEHIND the stamped commit {sha} — someone reset",
                     "the record describes work that is not in this history. Stop and reconcile "
                     "before doing anything; re-running finished work is the failure this file exists "
                     "to prevent.")
    return _ok("STRUCT-06", Stage.STRUCTURE,
               f"session-state record stamped {state} @ {sha}",
               f"dated {date}, via {pass_name}; commit exists and is an ancestor of HEAD; state is "
               f"one of the {len(states)} the document defines")


def check_confidential_vault_is_ignored(ctx: Ctx) -> CheckResult:
    """The confidential vault must be git-ignored — six places in this tree assume it is.

    It was not, for the whole life of the project. RULEBOOK **L14** says non-public documents may
    live only under ``docs/confidential/``; both placement gates therefore *skip* anything inside it;
    and ``--local-preview`` actively writes confidential renders there. With the directory tracked,
    the single location the engine instructs you to use was the one guaranteed publication route —
    a classified document placed there committed clean, pushed clean, and landed on the remote with
    every gate printing an affirmative line.

    Asked of **git**, not of the file's text, because what matters is the effective ignore status:
    a `.gitignore` line can be overridden by a later negation, by `.git/info/exclude`, or by a
    global excludes file, and only ``git check-ignore`` accounts for all of them.
    """
    rel = engine_config_confidential_relative(ctx)
    probe = f"{rel.rstrip('/')}/__vault_probe__.md"
    code, out = _run(["git", "check-ignore", "-q", probe], ctx.root, timeout=30)
    if code != 0:
        return _fail("STRUCT-07", Stage.STRUCTURE,
                     f"the confidential vault '{rel}' is NOT git-ignored",
                     "RULEBOOK L14 confines non-public documents to this directory and both "
                     "placement gates skip it, so a tracked vault is a guaranteed publication "
                     f"route for exactly the documents it exists to contain. Add '{rel}' to "
                     f".gitignore. (git check-ignore exit {code}) {out.strip()[:120]}")
    tracked_code, tracked_out = _run(["git", "ls-files", "--", rel], ctx.root, timeout=30)
    if tracked_code == 0 and tracked_out.strip():
        listed = tracked_out.strip().splitlines()
        return _fail("STRUCT-07", Stage.STRUCTURE,
                     f"{len(listed)} file(s) inside the confidential vault are already TRACKED",
                     "ignoring the directory does not untrack what is already in it: "
                     + ", ".join(listed[:5]), listed)
    return _ok("STRUCT-07", Stage.STRUCTURE,
               f"the confidential vault '{rel}' is git-ignored and holds no tracked files")


def check_ci_cost_control(ctx: Ctx) -> CheckResult:
    """The portfolio CI cost-control gate must actually run, and pass.

    It shipped in this engine and NOTHING invoked it, so it had never passed here — it fabricated a
    phantom `.github/workflows/docgen-gate.yml` when the directory was empty and reported
    `workflow unreadable (fail-closed)`, permanently BLOCKED in a repository that is compliant by
    construction (`OG-25`). A gate with no caller is not a gate (LESSONS.md L-01), and a gate that
    has never passed teaches nothing when it finally runs.
    """
    from tools.docgen import ci_cost_control

    result = ci_cost_control.audit(repo_root=ctx.root)
    blocking = [f for f in result.findings if f.blocking]
    if blocking:
        return _fail("STRUCT-05", Stage.STRUCTURE,
                     f"{len(blocking)} CI cost-control violation(s)",
                     "; ".join(f.message for f in blocking[:5]), [f.message for f in blocking])
    scope = next((f.message for f in result.findings), "")
    return _ok("STRUCT-05", Stage.STRUCTURE, "CI cost-control policy holds",
               scope[:200] or f"{len(result.findings)} advisory finding(s), none blocking")


# ======================================================================================
# 2 — RULE LAYER
# ======================================================================================


def check_hash_gate(ctx: Ctx) -> CheckResult:
    """The L9 rulebook hash-gate must hold: no undeclared drift in a locked rule."""
    try:
        from tools.docgen import validate_doc_system
    except ImportError as exc:  # pragma: no cover - engine always ships this
        return _fail("RULE-01", Stage.RULE_LAYER, f"cannot import validate_doc_system: {exc}")
    result = validate_doc_system.check(rules_dir=ctx.doc_system)
    if result.blocked:
        msgs = [f.message for f in result.findings if f.blocking]
        return _fail("RULE-01", Stage.RULE_LAYER, "hash-gate BLOCKED", "; ".join(msgs), msgs)
    return _ok("RULE-01", Stage.RULE_LAYER, "hash-gate holds — no undeclared rulebook drift",
               "; ".join(f.message for f in result.findings) or "no findings")


def check_contradictions_parse(ctx: Ctx) -> CheckResult:
    """CONTRADICTION.md must parse into rows — presence is not consultation."""
    from tools.docgen import adjudication

    rows = adjudication.load_contradictions(ctx.doc_system / "CONTRADICTION.md")
    if not rows:
        return _fail("RULE-02", Stage.RULE_LAYER, "CONTRADICTION.md parsed to ZERO rows (L11 inert)")
    return _ok("RULE-02", Stage.RULE_LAYER, f"{len(rows)} L11 tie-breaker row(s) parsed",
               f"row tags: {[sorted(r.rule_tags) for r in rows]}")


def check_impact_map(ctx: Ctx) -> CheckResult:
    """Every documented L10 change type must resolve to a real, populated map entry."""
    from tools.docgen import adjudication

    path = ctx.doc_system / "update_impact_map.json"

    # Derive the universe from the MAP, not from the tuple above: a change type added to the map
    # must be validated the moment it is added, without a matching Python edit (OPEN_GATES OG-15).
    try:
        declared = json.loads(path.read_text(encoding="utf-8")).get("change_types")
    except (OSError, ValueError) as exc:
        return _fail("RULE-03", Stage.RULE_LAYER, "impact map unreadable (fail-closed)", f"{path}: {exc}")
    if not isinstance(declared, dict) or not declared:
        return _fail("RULE-03", Stage.RULE_LAYER, "impact map has no change_types", str(path))

    bad: list[str] = []
    # The documented five must still be there. Deriving the universe from the map alone would let
    # a deletion pass silently — the map would simply have fewer keys, and every one of them fine.
    for ct in _BASELINE_CHANGE_TYPES:
        if ct not in declared:
            bad.append(f"{ct}: documented baseline type missing from the map")

    # Type-check the RAW entry before trusting the coerced view. compute_change_impact runs values
    # through str(), so a JSON `null` arrives as the literal string "None" — which is truthy, and
    # therefore passed the emptiness tests below. A change type whose L10 blast-radius answer is
    # null would have been reported as resolving fine.
    for ct, entry in declared.items():
        if not isinstance(entry, dict):
            bad.append(f"{ct}: entry is {type(entry).__name__}, not an object")
            continue
        deps = entry.get("dependent_doc_ids")
        rule = entry.get("public_sanitization_rule")
        # `description` was never type-checked here (`P8-120`) — only `dependent_doc_ids` and
        # `public_sanitization_rule` were. Measured in a disposable lab: nulling the `description`
        # of a real entry still reported `[PASS] all 5 L10 change types in the map resolve`, because
        # `compute_change_impact` never reads that field either — nothing anywhere validated it.
        # Required, not merely type-checked: every baseline entry HAS a real one (verified against
        # the live map), so requiring it costs nothing on the real corpus and catches exactly the
        # class of defect `dependent_doc_ids`/`public_sanitization_rule` already catch for their
        # own fields — a blank or null value passing as though it were documentation.
        description = entry.get("description")
        if not isinstance(deps, list) or not deps or not all(
            isinstance(d, str) and d.strip() for d in deps
        ):
            bad.append(f"{ct}: dependent_doc_ids must be a non-empty list of non-empty strings")
        if not isinstance(rule, str) or not rule.strip():
            bad.append(f"{ct}: public_sanitization_rule must be a non-empty string")
        if not isinstance(description, str) or not description.strip():
            bad.append(f"{ct}: description must be a non-empty string")

    for ct in declared:
        impact = adjudication.compute_change_impact(ct, impact_map_path=path)
        if not impact.known:
            bad.append(f"{ct}: not in map")
        elif not impact.dependent_doc_ids:
            bad.append(f"{ct}: empty dependent_doc_ids")
        elif not impact.public_sanitization_rule:
            bad.append(f"{ct}: empty public_sanitization_rule")
    if bad:
        return _fail("RULE-03", Stage.RULE_LAYER, f"{len(bad)} change type(s) unusable", "; ".join(bad), bad)
    return _ok("RULE-03", Stage.RULE_LAYER,
               f"all {len(declared)} L10 change types in the map resolve "
               f"(incl. the {len(_BASELINE_CHANGE_TYPES)} documented baseline types)")


def check_taxonomy_parses(ctx: Ctx) -> CheckResult:
    """TAXONOMY.md must yield a non-empty prefix set — an empty set blocks every document."""
    from tools.docgen.classification import load_taxonomy_prefixes

    prefixes = load_taxonomy_prefixes(ctx.doc_system / "TAXONOMY.md")
    if not prefixes:
        return _fail("RULE-04", Stage.RULE_LAYER, "TAXONOMY.md yielded ZERO prefixes (blocks every doc)")
    return _ok("RULE-04", Stage.RULE_LAYER, f"{len(prefixes)} doc-type prefix(es)", ", ".join(sorted(prefixes)))


def check_manifest_parses(ctx: Ctx) -> CheckResult:
    """DOC_MANIFEST.md must yield at least one registry row."""
    from tools.docgen import doc_manifest

    rows = doc_manifest.read_manifest(ctx.doc_system / "DOC_MANIFEST.md")
    if not rows:
        return _fail("RULE-05", Stage.RULE_LAYER, "DOC_MANIFEST.md parsed to ZERO rows")
    return _ok("RULE-05", Stage.RULE_LAYER, f"{len(rows)} manifest row(s)",
               ", ".join(f"{r.id}({'/'.join(t.value for t in r.variants)})" for r in rows))


# ======================================================================================
# 3 — CONSISTENCY — "no part lies to another part"
# ======================================================================================


def check_impact_prefixes_known(ctx: Ctx) -> CheckResult:
    """Every prefix the L10 map tells you to review must be a real doc type.

    A map naming a prefix that TAXONOMY.md does not register sends an operator to review a document
    class that cannot exist — one file lying to another.
    """
    from tools.docgen import adjudication
    from tools.docgen.classification import load_taxonomy_prefixes

    known = load_taxonomy_prefixes(ctx.doc_system / "TAXONOMY.md")
    the_map = adjudication.load_impact_map(ctx.doc_system / "update_impact_map.json")
    # A set difference over an EMPTY source is vacuously empty, so both halves must be non-empty
    # for a PASS to mean anything. Without this the check reported "every dependent prefix is a
    # registered doc type" over zero prefixes and zero doc types (LESSONS.md L-19).
    if not known or not the_map:
        return _fail("CONS-01", Stage.CONSISTENCY,
                     "cannot check prefixes: the rule layer produced nothing to compare",
                     f"TAXONOMY prefixes={len(known)}, impact-map change types={len(the_map)}")
    unknown: list[str] = []
    for ct, entry in sorted(the_map.items()):
        ids = entry.get("dependent_doc_ids")
        if isinstance(ids, list):
            unknown.extend(f"{ct}->{i}" for i in ids if str(i) not in known)
    if unknown:
        return _fail("CONS-01", Stage.CONSISTENCY,
                     f"{len(unknown)} impact-map prefix(es) absent from TAXONOMY.md",
                     "; ".join(unknown), unknown)
    return _ok("CONS-01", Stage.CONSISTENCY, "every impact-map dependent prefix is a registered doc type")


def check_manifest_ids_known(ctx: Ctx) -> CheckResult:
    """Every DOC_MANIFEST row id must be a registered TAXONOMY prefix.

    Otherwise a document can satisfy the registry gate while failing the taxonomy gate (or the
    reverse) — two gates disagreeing about the same document.
    """
    from tools.docgen import doc_manifest
    from tools.docgen.classification import load_taxonomy_prefixes

    known = load_taxonomy_prefixes(ctx.doc_system / "TAXONOMY.md")
    rows = doc_manifest.read_manifest(ctx.doc_system / "DOC_MANIFEST.md")
    # Same vacuity guard as CONS-01: "all 0 manifest id(s) are registered" is not a pass.
    if not known or not rows:
        return _fail("CONS-02", Stage.CONSISTENCY,
                     "cannot check manifest ids: the rule layer produced nothing to compare",
                     f"TAXONOMY prefixes={len(known)}, manifest rows={len(rows)}")
    # **BIDIRECTIONAL** (`OG-156`). This checked manifest → taxonomy only, while
    # `DOC_MANIFEST.md` states "every registered prefix has a row — the two files are kept in
    # agreement mechanically by this check". Measured: a `ZZZ` prefix added to `TAXONOMY.md` with
    # no manifest row, through the documented L9 two-step so the hash gate is satisfied, left
    # **both CONS-01 and CONS-02 PASSING**. The claim of mechanical agreement was true in one
    # direction and asserted in both — the same shape `CONS-03` was corrected for, where a
    # one-way comparison made the L9 lock self-certifying.
    problems = [f"manifest id not in TAXONOMY.md: {r.id}" for r in rows if r.id not in known]
    manifest_ids = {r.id for r in rows}
    problems += [
        f"TAXONOMY prefix with no DOC_MANIFEST row: {prefix}"
        for prefix in sorted(known)
        if prefix not in manifest_ids
    ]
    if problems:
        return _fail("CONS-02", Stage.CONSISTENCY,
                     f"{len(problems)} TAXONOMY/DOC_MANIFEST disagreement(s)",
                     "; ".join(problems), problems)
    return _ok("CONS-02", Stage.CONSISTENCY,
               f"TAXONOMY.md and DOC_MANIFEST.md agree exactly, both ways "
               f"({len(rows)} manifest row(s), {len(known)} registered prefix(es))")


def _normalise_locked_path(raw: str) -> str:
    """A host-root-relative path, POSIX-separated, with a leading ``./`` stripped.

    Used for both `VERSION.json`'s JSON strings (always full host-root-relative paths) and
    RULEBOOK.md's backticked table cells (a MIX of full paths and bare basenames — see
    `_locked_cell_matches`) before either is compared.
    """
    posix = PurePosixPath(raw.strip().replace("\\", "/"))
    parts = [p for p in posix.parts if p not in ("", ".")]
    return "/".join(parts)


def _locked_cell_matches(cell: str, declared_full_path: str) -> bool:
    """Does one RULEBOOK.md table cell name one `VERSION.json` `rulebook_files` entry?

    **The table is not written in one convention** (verified against the live document, not
    assumed): `RULEBOOK.md`, `TAXONOMY.md`, `update_impact_map.json` and even the two law files
    that live outside `docs/design/doc-system/` (`DOC_WRITING_DOCTRINE.md`,
    `DEEP_VERIFICATION_PASS.md`) are all listed as bare basenames with no directory at all, while
    the three hook entries (`tools/hooks/pre-push`, `tools/hooks/pre-commit`,
    `tools/hooks/install.sh`) spell a full path. Forcing every cell onto a derived full path (by
    assuming a bare cell lives under the rule-layer directory) is WRONG here — it would turn the
    two out-of-doc-system law files into false mismatches, since a bare cell carries no signal
    about which of several possible directories it means.

    So a cell is trusted for exactly what it commits to:

    * a cell that spells a directory (contains ``/``) must equal the declared FULL path exactly —
      this is what closes `P8-119`: retargeting `tools/hooks/pre-push` to
      `attacker/elsewhere/pre-push` no longer matches merely because the trailing basename still
      reads `pre-push`. Measured in a disposable lab before this fix: that exact retarget left
      `[PASS] RULEBOOK locked-file table matches VERSION.json exactly (10 file(s))` unchanged.
    * a bare cell (no ``/``) matches by basename only, which is all it claims to say.
    """
    normalised = _normalise_locked_path(cell)
    if "/" in normalised:
        return normalised == declared_full_path
    return normalised == PurePosixPath(declared_full_path).name


def check_rulebook_locked_table(ctx: Ctx) -> CheckResult:
    """RULEBOOK.md's locked-file table must name exactly VERSION.json's rulebook_files.

    The rulebook tells a human which files are locked; VERSION.json tells the gate. If they
    disagree, the document is lying about what the machine enforces.

    **A cell that spells a directory must match FULL PATH, not merely basename** (`P8-119`).
    Comparing every cell's `Path(...).name` let ANY table entry impersonate ANY declared file of
    the same basename regardless of directory — the widest form of the hole is a hook entry
    retargeted outside `tools/hooks/` while its trailing filename stays the same. See
    `_locked_cell_matches` for why this cannot simply become "always compare full paths": most of
    the table's rows are legitimately bare basenames with no directory implied.

    This is still an UNORDERED comparison — the two sides' relative *order* can diverge undetected
    (`P8-067`, tracked separately: its fix needs a hash-locked document edit outside this check's
    own file, so it is not bundled here — doing so would flip this gate red on a corpus this check
    cannot itself repair).
    """
    vj = ctx.doc_system / "VERSION.json"
    rb = ctx.doc_system / "RULEBOOK.md"
    if not (vj.is_file() and rb.is_file()):
        # FAIL, not SKIP. BOTH files are members of the locked set — their absence is the condition
        # this check exists to detect, never an environment fact. See the note below: Pass 6 fixed
        # two of this function's four exits and left these two, and Pass 7 walked through them.
        return _fail("CONS-03", Stage.CONSISTENCY,
                     "VERSION.json or RULEBOOK.md is absent",
                     "both are members of the hash-locked set; neither can go missing by accident "
                     "(OG-94)")
    declared_order = [
        _normalise_locked_path(str(f))
        for f in json.loads(vj.read_text(encoding="utf-8")).get("rulebook_files", [])
    ]
    declared = set(declared_order)
    text = rb.read_text(encoding="utf-8")
    # ⚠ **NO HEADING TEXT IS LOAD-BEARING HERE, AND THAT IS THE FIX.**
    #
    # This used to `text.split("## Locked-file set", 1)` and SKIP when the heading was absent —
    # a Python literal restating a fact RULEBOOK.md owns (`docs/process/RULES.md` Rule 2), guarding
    # a check whose whole job is to notice that document changing. Pass 7 drove the full chain in a
    # lab: rename the heading to `## The locked-file set`, and CONS-03 SKIPs; drop
    # `tools/hooks/pre-push` from `rulebook_files`; complete the documented L9 two-step; and the
    # engine reports HEALTHY at exit 0 with the moat's own executable silently out of the lock —
    # which RULEBOOK.md L9 says is the ONLY structural defence pre-push has, because it cannot be
    # behaviourally probed.
    #
    # Pass 6 converted the two TABLE exits of this function from SKIP to FAIL and left the two
    # DOCUMENT exits alone. That is `LESSONS.md` L-26 failing one generation after it was written:
    # the fix was attacked at the edge the previous verifier had found, not at its new edge.
    #
    # The table is now located by its own `File` header across the WHOLE document (verified unique:
    # RULEBOOK.md has three tables and only one carries that column), so retitling, moving or
    # reordering the section changes nothing, and there is no literal left to drift.
    body = text
    # Only the locked-set TABLE rows, so prose mentioning a filename cannot pad the set; and only
    # the FIRST backticked token per row, which is the File column.
    #
    # The character class deliberately allows a path and no extension. It used to require
    # `\.(?:md|json)`, which made the check structurally unable to see the two entries that matter
    # most: `tools/hooks/pre-push` and `tools/hooks/pre-commit` are the moat's own executables and
    # carry no extension, so locking them left CONS-03 reporting them "locked but undocumented"
    # forever, no matter what the table said. Compared by FULL PATH (`_normalise_locked_path`,
    # `P8-119`) — the extensionless-hook problem was in this regex's character class, not in the
    # comparison, so widening the class already covers those two entries with no basename needed.
    # Cells come from the one Markdown reader (`OG-36`), and the File column is located BY ITS
    # HEADER, never by position. Two weaker forms were tried and rejected while this was rewired:
    # regexing the whole line for its first backticked token (what this did before — it happened to
    # land on the File column, and would have silently started reading the `#` column the moment a
    # column was inserted to its left), and hardcoding index 0 (which IS the `#` column here, and
    # failed immediately). A named column is the only form that survives the table being edited.
    table = md_table.find_table(body, required_headers=("file",))
    if table is None:
        # FAIL, not SKIP. A verifier applied the exact mutation this check exists to catch —
        # rename the table header, drop `tools/hooks/pre-commit` from `rulebook_files`, complete
        # the documented L9 re-baseline — and measured the difference: at `66e39cc` CONS-03
        # FAILED; after Phase 3 rewired it to locate the column by name, it SKIPPED and the whole
        # engine reported HEALTHY with a file silently removed from the lock (`OG-85`).
        #
        # An unreadable locked-file table is not "cannot check" — it IS the condition. The table is
        # in a hash-locked file, so it cannot go missing by accident; if it is unreadable, either
        # the lock was edited or the declaration was destroyed, and both are exactly what L9 is for.
        return _fail("CONS-03", Stage.CONSISTENCY,
                     "RULEBOOK.md's locked-file section has no readable `File` table",
                     "the locked set cannot be compared against VERSION.json — and this table lives "
                     "in a hash-locked file, so its absence is a declaration being destroyed, not "
                     "an environment fact (OG-85, widened to every exit by OG-94)")
    col = md_table.column_index(table.headers, ("File",))
    file_col = col.get("File")
    if file_col is None:
        return _fail("CONS-03", Stage.CONSISTENCY, "locked-file table has no `File` column",
                     "same reasoning as above: the column's absence is the defect, not a reason "
                     "to stop looking")
    cells = [
        m.group(1)
        for row in table.rows
        if len(row) > file_col
        for m in [re.search(r"`([A-Za-z0-9_./-]+)`", row[file_col])]
        if m
    ]

    # BIDIRECTIONAL. Checking only one direction made the L9 lock SELF-CERTIFYING: VERSION.json
    # declares both what is locked and the digest, and is not a member of its own locked set, so
    # deleting an entry from `rulebook_files` and re-baselining removed a file from the lock with
    # every gate still green. RULEBOOK.md's table is the human-declared truth; the two must match
    # EXACTLY, both ways. Proven by falsification 2026-08-20.
    #
    # Per-cell, via `_locked_cell_matches` (`P8-119`), not a plain set difference on basenames or
    # on full paths alone — see that function's docstring for why the table cannot be reduced to
    # either form uniformly.
    covered = {d for d in declared if any(_locked_cell_matches(c, d) for c in cells)}
    unmatched_cells = [c for c in cells if not any(_locked_cell_matches(c, d) for d in declared)]
    missing_from_doc = declared - covered
    problems = [f"locked but undocumented: {f}" for f in sorted(missing_from_doc)]
    problems += [f"documented as locked but NOT in rulebook_files: {c}" for c in sorted(unmatched_cells)]
    if problems:
        return _fail("CONS-03", Stage.CONSISTENCY,
                     f"RULEBOOK locked-file table and VERSION.json disagree ({len(problems)})",
                     "; ".join(problems), problems)

    # ORDER, not only membership (`P8-067`). The section above the table states that the files are
    # listed "in `VERSION.json`'s `rulebook_files`, **in that order**" — and that order is
    # load-bearing, because the L9 digest is computed over the files IN THAT SEQUENCE, so anyone
    # re-deriving the hash by hand needs it. Membership was checked bidirectionally and order was
    # not examined at all, so the claim could be false with every gate green: measured 2026-08-23,
    # `VERSION.json` positions 8-10 read install.sh / pre-push / pre-commit while the table read
    # pre-push / pre-commit / install.sh. A locked rule file asserting an order it does not have is
    # exactly the drift L9 exists to catch, and it was invisible to the check named as its guard.
    #
    # Deliberately runs only AFTER the membership comparison: with an unmatched cell present, an
    # index mismatch is a consequence of the missing row, and reporting position noise would bury
    # the specific message above (the `OG-171` ordering lesson).
    table_order = [
        next(d for d in declared_order if _locked_cell_matches(c, d))
        for c in cells
        if any(_locked_cell_matches(c, d) for d in declared_order)
    ]
    if table_order != declared_order:
        first = next(
            (i for i, (a, b) in enumerate(zip(table_order, declared_order)) if a != b),
            min(len(table_order), len(declared_order)),
        )
        return _fail(
            "CONS-03", Stage.CONSISTENCY,
            "RULEBOOK locked-file table lists the same files in a DIFFERENT ORDER to VERSION.json",
            f"first divergence at position {first + 1}: the table says "
            f"{table_order[first] if first < len(table_order) else '<end of table>'!r}, "
            f"rulebook_files says "
            f"{declared_order[first] if first < len(declared_order) else '<end of list>'!r}. "
            "The section states the table follows rulebook_files order, and the L9 digest is "
            "computed in that sequence — so the two must agree or the document is asserting an "
            "order the hash does not use.",
            [f"position {i + 1}: table={t!r} rulebook_files={d!r}"
             for i, (t, d) in enumerate(zip(table_order, declared_order)) if t != d],
        )

    return _ok("CONS-03", Stage.CONSISTENCY,
               f"RULEBOOK locked-file table matches VERSION.json exactly, in order "
               f"({len(declared_order)} file(s))")


def _gate_labels_via_ast(source: str) -> set[str]:
    """Every ``gate=`` label in a module, resolving module-level string constants (`OG-195`).

    Two shapes reach a `Finding`: ``gate="literal"`` and ``gate=SOME_NAME`` where ``SOME_NAME`` is
    a module-level string. Only the first is visible to a regex, and the second is what hid the
    `identity` gate — its constant is named ``GATE``, and the pattern looking for a constant
    required the name ``_GATE``.

    Unparseable source yields nothing rather than raising: this check's job is coverage, and a
    module that does not parse is a problem every other check will report more usefully.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()

    constants: dict[str, str] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value

    found: set[str] = set()
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        for kw in call.keywords:
            if kw.arg != "gate":
                continue
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                found.add(kw.value.value)
            elif isinstance(kw.value, ast.Name) and kw.value.id in constants:
                found.add(constants[kw.value.id])
    return found


def check_gate_token_coverage(ctx: Ctx) -> CheckResult:
    """Every gate the ENGINE EMITS must have a precedence position, and every rule gate a firing row.

    The universe is derived from the source's own ``gate="..."`` literals, not from ``PRECEDENCE``
    and not from the token mapping. Deriving it from either made the check unable to report the
    thing it exists to report: a gate missing from that structure was also missing from the set
    being checked. Measured 2026-08-20 — six emitted labels (``build``, ``build-cache``, ``pdf``,
    ``run_gates``, ``l10_impact``, ``l11_contradiction``) were absent from ``PRECEDENCE`` while
    CONS-04 reported full coverage, and an unlisted gate ranks BELOW every advisory.

    Known limit, stated rather than hidden: a gate label built dynamically (an f-string) would not
    be seen by this scan. Every label in the tree today is a plain literal, and the reverse
    assertion below catches the opposite drift — a PRECEDENCE entry nothing emits any more.
    """
    from tools.docgen import adjudication
    from tools.docgen.export_sanitizer import NO_CONTRADICTION_MAPPING, PRECEDENCE

    rows = adjudication.load_contradictions(ctx.doc_system / "CONTRADICTION.md")
    if not rows:
        return _fail("CONS-04", Stage.CONSISTENCY, "no contradiction rows to check coverage against")
    mapping = adjudication.gate_contradiction_tokens()

    # **Resolved with `ast`, not with a regex, because a regex cannot see a NAME** (`OG-195`).
    #
    # `OG-191` widened these patterns to accept a dot, which exposed 16 hidden gates. An
    # independent verifier of that closure then found a 17th the widened regex still could not
    # see: `tools/docgen/identity.py` writes `Finding(gate=GATE, ...)` where `GATE = "identity"` is
    # a module-level constant. `label_re` needs a literal after `gate=`; `const_re` required the
    # constant to be spelled `_GATE`. So a real, blocking, CRITICAL-emitting gate was absent from
    # `PRECEDENCE` while this check reported full coverage over 34 of 35 — the identical defect
    # `OG-191` claims to have eliminated, one spelling further on.
    #
    # A regex cannot fix this class, only postpone it: the next site will assign the constant a
    # third name, or build the label some other way. `LESSONS.md` L-24 already records the rule —
    # *parse structured source with ast, do not scan it* — from a guard whose own docstring taught
    # it a false vocabulary. So the scan below resolves module-level string constants and then
    # reads every `gate=` keyword argument, whether it is a literal or a name.
    #
    # The regexes are KEPT as a widening net, not replaced: they still catch a label in a
    # non-Python surface and cost nothing. The union is what is checked.
    #
    # **The dot is in the character class because leaving it out hid 16 gates** (`OG-191`).
    # This pattern was `[a-z0-9_-]+`, so every emitted label containing a `.` —
    # `geomap.source`, `chart.rule`, `visual.collision` and thirteen more — was invisible to the
    # scan. CONS-04 then reported full coverage while none of them had a `PRECEDENCE` position,
    # and `_precedence_rank` returns `len(PRECEDENCE)` for an unlisted gate, so a BLOCKING
    # `geomap.source` finding sorted below every advisory in the list humans read top-down. That
    # is the identical defect this function's own docstring records for the six labels it caught
    # on 2026-08-20, surviving in the one spelling it could not read.
    label_re = re.compile(r'gate\s*=\s*"([a-z0-9_.-]+)"')
    const_re = re.compile(r'^_GATE\s*=\s*"([a-z0-9_.-]+)"', re.MULTILINE)
    emitted: set[str] = set()
    scanned = 0
    for py in sorted((ctx.root / "tools" / "docgen").rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        scanned += 1
        text = py.read_text(encoding="utf-8", errors="replace")
        emitted.update(label_re.findall(text))
        emitted.update(const_re.findall(text))
        emitted.update(_gate_labels_via_ast(text))
    if not emitted:
        return _fail("CONS-04", Stage.CONSISTENCY,
                     "no gate labels found in tools/docgen — the scan cannot be right",
                     f"scanned {scanned} module(s)")

    problems: list[str] = []

    # **A registered gate that nothing CALLS is inert** (`OG-155`). Everything below asks whether a
    # gate's *label* is wired — precedence position, contradiction mapping, a firing row. None of
    # it asks whether the gate's *function* is ever invoked, and `run_gates` builds its list by
    # hand: a new `gate_*` could be defined, given a precedence position, mapped, and pass this
    # check in full while never running on a single document. Measured at the time of writing:
    # all 8 gate functions are reachable, so this closes the class before an instance exists —
    # which is the cheapest moment to close one.
    try:
        gate_src = (ctx.root / "tools" / "docgen" / "export_sanitizer.py").read_text(encoding="utf-8")
        tree = ast.parse(gate_src)
        gate_fns = {
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name.startswith("gate_")
        }
        run_fn = next(
            (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_gates"),
            None,
        )
        if run_fn is None:
            problems.append("export_sanitizer.run_gates is absent — no gate runs at build time")
        else:
            # ⚠ **CALL SITES, VIA `ast` — NOT `f"{fn}(" in source`.** The substring form was
            # written first and falsified immediately: `def gate_x(` contains `gate_x(`, so every
            # gate satisfied "is called somewhere" by its own DEFINITION and the check passed on a
            # planted inert gate. A ground truth that the thing being measured can satisfy is not
            # a ground truth — `test_refs._defined_ids` carries the same lesson in its docstring,
            # and this check reproduced the defect while being written to close a sibling of it.
            # Across the WHOLE tree, not just this module: `gate_variant_overlap` is the
            # test-facing overload documented as having no internal caller, and `generator.py` and
            # the hooks invoke gates too. Restricting the search to `export_sanitizer.py` produced
            # a false red on the clean corpus the moment the AST rewrite made the check work.
            called_anywhere: set[str] = set()
            for py in (ctx.root / "tools").rglob("*.py"):
                if "node_modules" in str(py):
                    continue
                try:
                    other = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
                except (OSError, SyntaxError, ValueError):
                    continue
                for node in ast.walk(other):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            called_anywhere.add(node.func.id)
                        elif isinstance(node.func, ast.Attribute):
                            called_anywhere.add(node.func.attr)
            called_in_run = {
                node.func.id
                for node in ast.walk(run_fn)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            for fn in sorted(gate_fns):
                # A gate may legitimately be invoked from elsewhere (a hook, a test-facing
                # overload). Being called SOMEWHERE is the bar; being called NOWHERE is the defect.
                if fn in called_in_run or fn in called_anywhere:
                    continue
                problems.append(f"gate function defined but never called: {fn}")
    except (OSError, SyntaxError, ValueError) as exc:
        problems.append(f"could not verify gate invocation: {type(exc).__name__}: {exc}")

    problems += [f"emitted but absent from PRECEDENCE: {g}" for g in sorted(emitted - set(PRECEDENCE))]
    problems += [f"in PRECEDENCE but emitted nowhere: {g}" for g in sorted(set(PRECEDENCE) - emitted)]
    rule_gates = emitted - NO_CONTRADICTION_MAPPING
    problems += [f"unmapped rule gate: {g}" for g in sorted(rule_gates - set(mapping))]
    problems += [
        f"no firing row: {g}"
        for g, tokens in sorted(mapping.items())
        if g in rule_gates and not any(r.rule_tags & tokens for r in rows)
    ]
    if problems:
        return _fail("CONS-04", Stage.CONSISTENCY,
                     f"{len(problems)} gate coverage problem(s) across {len(emitted)} emitted gate(s)",
                     "; ".join(problems), problems)
    return _ok("CONS-04", Stage.CONSISTENCY,
               f"all {len(emitted)} gate(s) emitted by tools/docgen have a precedence position; "
               f"all {len(rule_gates)} rule gate(s) are mapped and have a firing row "
               f"({len(NO_CONTRADICTION_MAPPING & emitted)} exempt by declaration)")

def check_project_version_matches_changelog(ctx: Ctx) -> CheckResult:
    """PROJECT_VERSION must equal the newest version heading in CHANGELOG.md.

    A version file that disagrees with its own changelog is the smallest possible instance of the
    failure this system exists to prevent.
    """
    vf = ctx.root / "PROJECT_VERSION"
    cl = ctx.root / "CHANGELOG.md"
    if not (vf.is_file() and cl.is_file()):
        return _skip("CONS-05", Stage.CONSISTENCY, "PROJECT_VERSION or CHANGELOG.md absent")
    version = vf.read_text(encoding="utf-8").strip()
    headings = re.findall(r"^##\s*\[([0-9]+\.[0-9]+\.[0-9]+)\]", cl.read_text(encoding="utf-8"), re.MULTILINE)
    if not headings:
        return _fail("CONS-05", Stage.CONSISTENCY, "CHANGELOG.md has no '## [x.y.z]' version heading")
    if headings[0] != version:
        return _fail("CONS-05", Stage.CONSISTENCY,
                     "PROJECT_VERSION does not match newest CHANGELOG entry",
                     f"PROJECT_VERSION={version} newest CHANGELOG=[{headings[0]}]")
    return _ok("CONS-05", Stage.CONSISTENCY, f"version {version} agrees with CHANGELOG")


def check_rulebook_citations_resolve(ctx: Ctx) -> CheckResult:
    """Every symbol a RULEBOOK Status line cites must exist in the file it names.

    The rulebook's authority rests entirely on its enforcement citations being real. The Phase 1
    deep pass found three that were not — ``_append_generated_guard`` existed nowhere, and both L8
    and L16 pointed at ``visual.py``, which contains zero ``DataSource`` machinery. A rulebook that
    cites a symbol that does not exist is a document lying about what the machine enforces, which is
    the exact defect class this engine exists to prevent.

    Method: for each ``**Status:**`` line, take the ``path/to/file.py`` citations and the
    backticked ``identifier()`` tokens on that line, and require each identifier to appear in at
    least one cited file. Deliberately lenient about WHICH cited file contains it (a status line may
    legitimately name several), and skips prose-shaped tokens.
    """
    rb = ctx.doc_system / "RULEBOOK.md"
    if not rb.is_file():
        return _skip("CONS-07", Stage.CONSISTENCY, "RULEBOOK.md absent")

    ident_re = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)\(\)`|`([A-Z][A-Za-z0-9_]{2,})`")
    # `.py` ONLY was a blind spot: this engine's enforcement lives in `.mjs` renderers and in the
    # two shell hooks as well, and a Status line citing either was invisible — the citation guard
    # could not see the files that do the enforcing.
    path_re = re.compile(r"`?((?:tools|docs)/[A-Za-z0-9_./-]+\.(?:py|mjs|sh))`?|`(tools/hooks/[a-z-]+)`")
    broken: list[str] = []

    # A Status entry is a BLOCK, not a line: it wraps across lines, and a citation on a
    # continuation line is exactly as load-bearing as one on the first. Scanning only the first
    # line let a fabricated `check_choropleth_rules()` slip into L16 — inside the very commit that
    # fixed the previous fabricated citation. Corrected 2026-08-20.
    lines = rb.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    for idx, line in enumerate(lines):
        if "**Status:**" not in line:
            continue
        block = [line]
        for nxt in lines[idx + 1 :]:
            # A blockquote does NOT end a Status block. Rulebook entries routinely explain a
            # correction in a `>` note directly beneath the status line, and a citation inside one
            # is exactly as load-bearing as one above it — but was invisible, which is the second
            # construction that could hide a fabricated citation.
            if not nxt.strip() or nxt.lstrip().startswith(("#", "|", "```")):
                break
            block.append(nxt)
        blocks.append(" ".join(block))

    for raw in blocks:
        paths = [ctx.root / (a or b) for a, b in path_re.findall(raw) if (a or b)]
        existing = [p for p in paths if p.is_file()]
        for p in paths:
            if not p.is_file():
                broken.append(f"cited file missing: {p.relative_to(ctx.root)}")
        if not existing:
            continue
        # RESOLVE AGAINST WHAT THE FILE DEFINES, NOT AGAINST ITS TEXT.
        #
        # This check used `re.search(rf"\b{name}\b", blob)` over raw file text, so a symbol that
        # appears ONLY IN A COMMENT resolved. An adversarial verifier falsified it live: it put
        # `# NOTE: there is no longer a helper called GHOST_RANKER_XYZ here.` into a module, cited
        # `GHOST_RANKER_XYZ` from a RULEBOOK Status line, and CONS-07 passed.
        #
        # `symbols._defined_names` records this exact lesson (`OG-166`) and its docstring counts
        # itself "the third consumer of a ground truth that prose can widen". CONS-07 was a FOURTH,
        # and the one that matters most: `symbols` deliberately excludes RULEBOOK.md because "that
        # question has an owner" — so the hash-locked rulebook, whose authority rests entirely on
        # its citations being real, was held to the WEAKEST standard in the tree.
        #
        # Imported rather than reimplemented, for the reason `OG-195`'s closure gives: a fifth copy
        # of one idea is how the four already drifted. `_names_or_text` is AST-first and falls back
        # to a text search only when a file cannot be parsed, which is what keeps the cited `.mjs`
        # and `.sh` enforcement files working.
        from tools.corpus_check.guards.symbols import _names_or_text

        texts = [p.read_text(encoding="utf-8", errors="replace") for p in existing]
        for fn, const in ident_re.findall(raw):
            name = fn or const
            if name and not any(_names_or_text(text, name) for text in texts):
                cited = ", ".join(str(p.relative_to(ctx.root)) for p in existing)
                broken.append(f"`{name}` not found in {cited}")

    if broken:
        return _fail("CONS-07", Stage.CONSISTENCY,
                     f"{len(broken)} RULEBOOK citation(s) do not resolve",
                     "; ".join(broken[:8]), broken)
    return _ok("CONS-07", Stage.CONSISTENCY, "every RULEBOOK enforcement citation resolves to real source")


def check_doc_paths_resolve(ctx: Ctx) -> CheckResult:
    """Repo-relative paths cited in the core process documents must exist.

    Catches the stale-pointer defect: a document confidently naming a file that was moved or never
    created.
    """
    # THE PATTERN IS PART OF THE UNIVERSE (LESSONS L-14), so both halves are derived, not guessed:
    #   * the top-level prefixes come from the repository itself. The hardcoded four
    #     (docs|tools|examples|skills) made this check structurally blind to `vault-graph-engine/`,
    #     one of the repo's five tracked top-level directories.
    #   * the extension is OPTIONAL. Requiring a dot meant the check could not see
    #     `tools/hooks/pre-push` — this engine's own git moat, cited by name in six documents.
    # An earlier fix widened the extension from {1,5} to `+` and stopped there, which is how a
    # completeness check keeps passing while its blind spots merely move.
    code, listing = _run(["git", "ls-files"], ctx.root, timeout=60)
    if code != 0:
        return _skip("CONS-06", Stage.CONSISTENCY, "git ls-files unavailable", listing[:200])
    tracked = listing.split()
    # Resolution is against TRACKED content, never the filesystem. `(ctx.root / cited).exists()`
    # let an untracked, gitignored path satisfy a citation: `PROVENANCE.md` cites
    # `tools/visual-engine/node_modules/`, which exists here only because npm install has been run,
    # so this check passed locally and FAILED on every fresh clone — and because the pre-push moat
    # runs health, no fresh clone could push until it had run npm install. Worse, an empty
    # zero-byte directory satisfied it, so the check never tested that anything was installed.
    # A consistency check over tracked documents whose answer flips on untracked local state is
    # the same right-gate-wrong-artifact class as LESSONS.md L-15.
    tracked_set = set(tracked)
    tracked_dirs: set[str] = set()
    for rel in tracked:
        parts = rel.split("/")
        for i in range(1, len(parts)):
            tracked_dirs.add("/".join(parts[:i]))
    tops = sorted({rel.split("/", 1)[0] for rel in tracked if "/" in rel})
    if not tops:
        return _skip("CONS-06", Stage.CONSISTENCY, "no tracked subdirectories found", "")
    pattern = re.compile(rf"`((?:{'|'.join(re.escape(t) for t in tops)})/[A-Za-z0-9_./-]+)`")
    # Scope: every tracked Markdown file, not just the core set. A narrower scope reported
    # "every repo path resolves" while being blind to the tools/ tree — where a document cited by
    # three files (DOC_DESIGN_SYSTEM.md) had never existed. Widened 2026-08-20.
    listing = "\n".join(rel for rel in tracked if rel.endswith(".md"))

    # Paths this repo deliberately does not contain, declared with a reason in a reviewable
    # registry. NOT a suppression list: anything absent and undeclared still fails.
    declared_absent: set[str] = set()
    broken_rows: list[str] = []
    registry = ctx.root / "docs" / "process" / "ABSENT_PATHS.md"
    if registry.is_file():
        # FIRST COLUMN ONLY. Scanning the whole file swept the "what serves its role here" column
        # into the suppression set: measured 2026-08-20, that silently exempted 7 REAL files —
        # RULEBOOK.md, DOC_WRITING_DOCTRINE.md and OPEN_GATES.md among them — from this check
        # everywhere in the repo, so deleting any of them would have broken every citation
        # unnoticed. A registry of deliberate absences must not be able to excuse a path merely by
        # mentioning it; only the path a row is ABOUT is declared absent.
        in_table = False
        for line in registry.read_text(encoding="utf-8").splitlines():
            if line.startswith("##"):
                # Only the "Declared absent" table declares anything. Without this, a path named
                # in prose or in the change history silently became an exemption too.
                in_table = line.strip().lower().startswith("## declared absent")
                continue
            if not in_table or not md_table.is_row(line) or md_table.is_separator(line):
                continue
            cells = md_table.split_row(line)
            if not cells:
                continue
            cell = pattern.findall(cells[0])
            if len(cell) > 1:
                # One row declares ONE path. A cell naming two would exempt both — the same
                # "a row excuses everything it mentions" defect, one column narrower.
                broken_rows.append(f"ABSENT_PATHS.md row declares {len(cell)} paths: {cell}")
                continue
            declared_absent.update(cell)

    broken: list[str] = list(broken_rows)
    scanned = 0
    for rel in listing.splitlines():
        doc = ctx.root / rel.strip()
        if not doc.is_file():
            continue
        scanned += 1
        # **A dated record cites what a pass FOUND, not what exists now** (`OG-139`).
        # `VERIFICATION_LOG.md` quotes the lab probe paths each verifier planted —
        # `docs/notes/LEAK.md`, `docs/PROBE_LINKS.md`, a deliberately nonexistent guard module —
        # and those must never resolve: several exist precisely to demonstrate a path that is NOT
        # there. Declaring them in `ABSENT_PATHS.md` looked like the fix and was worse: the
        # declaration then EXEMPTED the same paths in `present-tense`, disarming the very
        # counter-example that guards `OG-115`. One registry cannot both silence a record and
        # arm a guard.
        #
        # `symbols`, `built-claims`, `crossrefs` and `test-refs` all already skip content under a
        # dated heading. This is that same rule, so "record" means one thing across the engine.
        text = doc.read_text(encoding="utf-8", errors="replace")
        doc_is_record = is_append_only_record(text)  # OG-140: declared, not inferred
        live_lines = [
            line
            for _n, line, headings in iter_prose_lines_with_headings(text)
            if not (doc_is_record and under_dated_heading(headings))
        ]
        for cited in set(pattern.findall("\n".join(live_lines))):
            if "*" in cited or "<" in cited or cited in declared_absent:
                continue
            target = cited.rstrip("/")
            if target not in tracked_set and target not in tracked_dirs:
                hint = " (exists locally but is not tracked — declare it in ABSENT_PATHS.md)" \
                    if (ctx.root / cited).exists() else ""
                broken.append(f"{rel} -> {cited}{hint}")
    if broken:
        return _fail("CONS-06", Stage.CONSISTENCY,
                     f"{len(broken)} cited path(s) do not resolve across {scanned} tracked doc(s)",
                     "; ".join(sorted(broken)[:10]), sorted(broken))
    return _ok("CONS-06", Stage.CONSISTENCY,
               f"every cited repo path resolves to TRACKED content across {scanned} tracked doc(s) "
               f"({len(declared_absent)} declared absent by design)")


_CHARTER_TRACKED_RE = re.compile(r"\*\*(\d+)\s+tracked Markdown documents?\.?\s*(\d+)\s+governed", re.IGNORECASE)


def check_charter_counts(ctx: Ctx) -> CheckResult:
    """The charter's two measured counts must be re-derived, not trusted.

    ``docs/CHARTER.md``'s whole argument rests on one measurement — how many documents this
    repository tracks versus how many the engine actually governs — and the gap being stark is the
    point. It was **wrong the day it was written** (53 stated, 55 real) and wronger by the time a
    verifier checked (56). `docs/process/RULES.md` Rule 2 says a document must not restate a fact
    code owns, *and* that where a number genuinely must appear, a check must derive and compare it.
    This is that check: the charter may keep its numbers precisely because this recomputes them.

    "Governed" is derived exactly as ``BUILD-02`` derives it — a tracked Markdown file whose YAML
    front matter declares ``classification`` — so the two can never disagree about what the word
    means.
    """
    charter = ctx.root / "docs" / "CHARTER.md"
    if not charter.is_file():
        return _fail("CONS-09", Stage.CONSISTENCY, "docs/CHARTER.md is absent",
                     "the anti-drift anchor is a core document; STRUCT-01 should have caught this")
    code, listing = _run(["git", "ls-files", "*.md"], ctx.root, timeout=60)
    if code != 0:
        return _skip("CONS-09", Stage.CONSISTENCY, "git ls-files unavailable", listing[:200])
    # **Archived snapshots are not documents this corpus has; they are documents it HAD.**
    # Counting them would make the charter's measurement grow every time a version is cut, and it
    # would put this check into direct contradiction with the `counts` corpus guard, which reads
    # `Corpus.markdown` and excludes them. Measured the moment the archive first had contents: this
    # check said 67 and the guard said 61. Both use `identity.is_archived_path` now, so the two
    # cannot answer differently again (`RULES.md` Rule 1).
    from tools.docgen import identity as _identity

    tracked = [
        rel for rel in listing.split()
        if (ctx.root / rel).is_file() and not _identity.is_archived_path(rel)
    ]
    if not tracked:
        return _fail("CONS-09", Stage.CONSISTENCY, "no tracked Markdown files found",
                     "an empty universe would make every comparison below vacuous")
    governed = 0
    for rel in tracked:
        head = (ctx.root / rel).read_text(encoding="utf-8", errors="replace")[:4000]
        fm = _GOVERNED_FRONT_MATTER_RE.match(head)
        if fm and "classification" in fm.group(1):
            governed += 1
    stated = _CHARTER_TRACKED_RE.search(charter.read_text(encoding="utf-8", errors="replace"))
    if stated is None:
        return _fail("CONS-09", Stage.CONSISTENCY,
                     "the charter no longer states its measurement in a form this check can read",
                     "expected `**N tracked Markdown documents. M governed ...**` — if the sentence "
                     "changed, update this check; do not delete the measurement, it is the argument")
    said_tracked, said_governed = int(stated.group(1)), int(stated.group(2))
    problems = []
    if said_tracked != len(tracked):
        problems.append(f"charter says {said_tracked} tracked documents, git lists {len(tracked)}")
    if said_governed != governed:
        problems.append(f"charter says {said_governed} governed, the engine derives {governed}")
    if problems:
        return _fail("CONS-09", Stage.CONSISTENCY,
                     f"{len(problems)} stale measurement(s) in docs/CHARTER.md",
                     "; ".join(problems), problems)
    return _ok("CONS-09", Stage.CONSISTENCY,
               f"the charter's measurement re-derives: {len(tracked)} tracked, {governed} governed "
               f"({100 * governed // len(tracked)}% of the corpus is under the engine)")


# Clause boundaries inside one line: sentence punctuation, semicolons, and em/en dashes used as
# clause separators. Used by `CONS-08` to stop a "bump" instruction in one clause exempting a
# present-tense version claim in another (`OG-123`).
_CLAUSE_SPLIT_RE = re.compile(r"[.;:!?]\s+|\s+[—–]\s+")


# The documents `CONS-08` holds to the truth. **Module-level so the probe cannot keep a second,
# private copy of the list** — `tools/tests/test_health_guards.py` builds its lab from this tuple,
# and while it hardcoded its own the two silently disagreed the moment a document was added here
# (`RULES.md` Rule 1, `LESSONS.md` L-37).
#
# OPEN_GATES.md is in scope because it states the health floor too, and a register that misreports
# the floor is exactly the stale-state defect this check exists to catch.
#
# **SESSION_STATE.md was added 2026-08-29, and its absence had cost exactly what this check exists
# to prevent** (`OG-211`). It is the crash-recovery record — the FIRST thing a fresh session reads
# after a crash, and the one document whose entire value is that it can be trusted instead of
# re-derived. It had gone five phases stale in all three fact families, and told a recovering
# session to start a phase that had shipped three phases earlier. Its own stamp check `STRUCT-06`
# passed throughout and was right to: it validates the stamp mechanically and explicitly disclaims
# judging the checklist. Nothing was watching the numbers, because the most load-bearing state
# document was the one not on this list.
STATE_DOCS: tuple[str, ...] = (
    "HANDOFF.md",
    "docs/plan/NEXT_SESSION.md",
    "docs/plan/START_NEXT_SESSION.md",
    "docs/process/OPEN_GATES.md",
    "docs/process/SESSION_STATE.md",
)


def check_state_docs_facts(ctx: Ctx) -> CheckResult:
    """The three "starting state" documents must not misstate the facts they exist to hand over.

    `HANDOFF.md`, `docs/plan/NEXT_SESSION.md` and `docs/plan/START_NEXT_SESSION.md` are read FIRST
    by the next session and reasoned from. A wrong number in them is the most expensive kind of
    wrong, and it has now happened twice in two phases:

    * the rulebook version stood at `1.1.0` in two of them for a whole phase after `VERSION.json`
      said `1.2.0`;
    * the version of this check that caught that guarded **only** the rulebook — and an independent
      pass immediately found the identical defect in the adjacent table column, where all three
      documents still claimed project `0.2.1` while `PROJECT_VERSION` said `0.3.0`, plus a health
      floor of "20 passed" against 22 registered checks. A false red aimed at a healthy engine is
      worse than a false green: the predictable response is an agent "fixing" a correct baseline.

    So this checks all three fact families against their machine-readable sources:

    ============================  ==========================================
    claim in a state document     ground truth
    ============================  ==========================================
    ``rulebook <semver>``         ``VERSION.json`` ``version``
    ``project <semver>``          ``PROJECT_VERSION``
    ``N passed, M failed, K       ``len(CHECKS)`` — the live registry
    skipped``
    ============================  ==========================================

    Two line-level exemptions, both narrow and both about *tense*: a line containing an arrow is a
    transition record (``1.1.0`` → ``1.2.0``), and a line containing "bump" is an instruction about
    a future change (the launch prompt tells the next session to bump the version). Neither is a
    claim about the present, and failing on an accurate history entry or a correct instruction is
    how a check teaches people to bypass it.
    """
    truth: dict[str, str] = {}

    version_json = ctx.doc_system / "VERSION.json"
    try:
        declared = json.loads(version_json.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError) as exc:
        return _fail("CONS-08", Stage.CONSISTENCY, "VERSION.json unreadable (fail-closed)",
                     f"{version_json}: {exc}")
    if not isinstance(declared, str) or not declared:
        return _fail("CONS-08", Stage.CONSISTENCY, "VERSION.json declares no version", str(version_json))
    truth["rulebook"] = declared

    try:
        truth["project"] = (ctx.root / "PROJECT_VERSION").read_text(encoding="utf-8").strip()
    except (OSError, ValueError) as exc:
        return _fail("CONS-08", Stage.CONSISTENCY, "PROJECT_VERSION unreadable (fail-closed)", str(exc))
    if not truth["project"]:
        return _fail("CONS-08", Stage.CONSISTENCY, "PROJECT_VERSION is empty", str(ctx.root / "PROJECT_VERSION"))

    total_checks = len(CHECKS)
    # Keyword-then-nearest-semver, rather than "any semver on a line mentioning X". The first
    # draft of this check used the looser form and immediately mis-flagged
    # "**Starting state:** project `0.2.1`, rulebook `1.1.0`" — reading the PROJECT version as a
    # stale rulebook claim. Walking the line in order and binding each version to the keyword that
    # most recently preceded it reads that sentence exactly as a human does.
    keyword_re = re.compile(r"\b(rulebook|project)\b", re.IGNORECASE)
    semver_re = re.compile(r"\d+\.\d+\.\d+")
    # Accept BOTH separators. The comma-only form could not see the one line in
    # START_NEXT_SESSION.md a human actually executes — the copy-paste launch command, which
    # writes "confirm 23 passed / 0 failed / 0 skipped". The floor claim most likely to go stale
    # was the one claim this check could not read.
    counts_re = re.compile(r"(\d+)\s+passed\s*[,/]\s*(\d+)\s+failed\s*[,/]\s*(\d+)\s+skipped")

    wrong: list[str] = []
    checked = 0
    for rel in STATE_DOCS:
        doc = ctx.root / rel
        if not doc.is_file():
            wrong.append(f"{rel}: state document missing")
            continue
        for n, line in enumerate(doc.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            # "bump" = an instruction about a future change, never a claim about the PRESENT
            # VERSION — so it exempts the semver loop only. It used to `continue` past the whole
            # line, and the launch command in START_NEXT_SESSION.md says "bump PROJECT_VERSION to
            # 0.4.0" in the same 2,684-character line that states the health floor: one word
            # switched the check off for the single most-executed line in the repo.
            # ⚠ **PER CLAUSE, NOT PER LINE — the whole-line form was still open** (`OG-123`).
            #
            # `bump` exempts an INSTRUCTION about a future change. Evaluated over the whole line it
            # exempts everything else on that line too, and Pass 7 measured the consequence by
            # appending one sentence to `HANDOFF.md`:
            #
            #     "The rulebook is at version 9.9.9 today."                  -> FAIL   (correct)
            #     "The rulebook is at version 9.9.9 today; bump it later."   -> PASS   (silenced)
            #
            # A present-tense claim and an instruction sat on one line and the CLAIM was the half
            # that got silenced. This exemption was already narrowed once — it used to `continue`
            # past the entire line including the health-floor claim — and the hole moved one step
            # over rather than closing, which is `LESSONS.md` L-26 for the third time in this file.
            # `_MIN_CLAIMS = 6` against 10 live claims leaves four claims of headroom, so several
            # could be hidden this way before the floor bites.
            #
            # Clauses are split on sentence and clause punctuation, so "bump it later" no longer
            # reaches across a semicolon to excuse a claim it has nothing to do with.
            clause_bounds = [0] + [m.end() for m in _CLAUSE_SPLIT_RE.finditer(line)] + [len(line)]
            bump_spans = [
                (clause_bounds[i], clause_bounds[i + 1])
                for i in range(len(clause_bounds) - 1)
                if re.search(r"\bbump", line[clause_bounds[i] : clause_bounds[i + 1]], re.IGNORECASE)
            ]

            def _in_bump_clause(pos: int, spans: list[tuple[int, int]] = bump_spans) -> bool:
                return any(start <= pos < end for start, end in spans)
            # A transition record is an arrow BETWEEN TWO VERSIONS ("1.1.0 → 1.2.0"), and only
            # version claims on such a line are exempt. Skipping every line containing an arrow was
            # the first draft, and it silently exempted
            # "`python3 -m tools.health --full` → **20 passed, 0 failed, 0 skipped**" — where the
            # arrow means "produces", not "became". That is the very floor claim this check exists
            # to guard, so the exemption was cancelling the check on its most important line.
            is_version_transition = bool(
                re.search(r"\d+\.\d+\.\d+[^\n]*(?:→|->)[^\n]*\d+\.\d+\.\d+", line)
            )
            marks = [(m.start(), "kw", m.group(1).lower()) for m in keyword_re.finditer(line)]
            marks += [(m.start(), "ver", m.group(0)) for m in semver_re.finditer(line)]
            pending: str | None = None
            for _pos, kind, val in [] if is_version_transition else sorted(marks):
                if kind == "kw":
                    pending = val
                elif pending is not None:
                    if _in_bump_clause(_pos):
                        # An instruction to bump, in the clause that contains this version.
                        pending = None
                        continue
                    checked += 1
                    if val != truth[pending]:
                        wrong.append(f"{rel}:{n} says {pending} {val}, truth is {truth[pending]}")
                    pending = None
            for m in counts_re.finditer(line):
                checked += 1
                stated = sum(int(g) for g in m.groups())
                if stated != total_checks:
                    wrong.append(
                        f"{rel}:{n} states a health floor of {stated} check(s) "
                        f"({m.group(0)}), but {total_checks} are registered"
                    )
    if wrong:
        return _fail("CONS-08", Stage.CONSISTENCY,
                     f"{len(wrong)} stale claim(s) in the state documents",
                     "; ".join(wrong), wrong)
    # A check that validates only the claims it can FIND passes over a document containing none.
    # Emptying the state documents removed every claim and this check went green — the handover can
    # be destroyed without the engine noticing (LESSONS.md L-19, applied where it was first missed).
    _MIN_CLAIMS = 6
    if checked < _MIN_CLAIMS:
        return _fail("CONS-08", Stage.CONSISTENCY,
                     f"only {checked} state claim(s) found across {len(STATE_DOCS)} document(s)",
                     f"expected at least {_MIN_CLAIMS}. Either the handover documents have lost "
                     "their version/floor claims, or this check has stopped being able to see them "
                     "— both are defects, and passing over zero claims is not a pass.")
    return _ok("CONS-08", Stage.CONSISTENCY,
               f"all {checked} state claim(s) across {len(STATE_DOCS)} handover document(s) agree "
               f"with ground truth (rulebook {truth['rulebook']}, project {truth['project']}, "
               f"{total_checks} checks)")


# ======================================================================================
# 4 — BUILD
# ======================================================================================


# Two failures that are not the same failure, and used to be reported as one.
#
# `_run` collapsed `TimeoutExpired` and `OSError` into a single `127`, so no caller could tell
# "the command ran out of wall-clock time" from "the command could not be launched" — and neither
# from "the command failed". Measured 2026-08-29 (`OG-212`): the machine was carrying a load average
# of 36 from an unrelated project, the counter-example suite used its usual ~407 s of CPU but took
# 783 s of wall-clock, and `SUITE-05` reported **"python counter-examples FAILED"**. The suite was
# green. Because the pre-push hook runs health, that false red blocks every push, and its wording
# sends the reader looking for a broken test.
#
# `LESSONS.md` L-25: an environment fact is not a finding about the artifact, and must be NAMED
# rather than folded into a verdict. The verdict here stays FAIL — a timeout can also be a genuine
# hang, and a gate that passes on "it did not finish" would be worse than useless — but the two
# causes are now distinguishable, and the numbers 124/127 are the shell's own conventions.
_EXIT_TIMEOUT = 124
_EXIT_UNLAUNCHABLE = 127

# THE INTERPRETER RUNNING THIS RUN, never whatever `python3` PATH happens to resolve to. These
# checks shell out to the engine's own modules — docgen, project_index, the unittest suite — and
# every one of them needs the dependencies declared in `tools/docgen/requirements.txt`. Resolving
# the child by name lets health measure a DIFFERENT interpreter than the one it is running on: this
# machine carries `/opt/homebrew/bin/python3` (PyYAML present) and `/usr/local/bin/python3` (PyYAML
# absent) simultaneously, so `python3 -m tools.docgen.cli` fails on an ImportError that says nothing
# about the interpreter split, and the check reports the engine broken. A field trial hit exactly
# that and spent the diagnosis on the engine instead of the environment (`OG-247`). `sys.executable`
# is the one answer that cannot disagree with the process asking the question.
_PY = sys.executable or "python3"


def _child_env(env: dict[str, str] | None) -> dict[str, str]:
    """The caller's environment with any RELATIVE ``PYTHONPATH`` entry pinned to an absolute path.

    `OG-247`, second half. Every check here launches its child with ``cwd`` set to the host root,
    which is usually not the directory health itself was started in — and a relative ``PYTHONPATH``
    silently changes meaning when the working directory moves under it. The documented way to point
    this engine at a foreign project is exactly the shape that breaks:

        PYTHONPATH=engine ENGINE_HOST_ROOT=subject python3 -m tools.health --root subject

    The parent imports `tools.docgen` fine; the child, running in ``subject/``, looks for
    ``subject/engine`` and reports `ModuleNotFoundError: No module named 'tools.docgen'`. Measured:
    the child DOES inherit ``PYTHONPATH=engine`` — the variable is not lost, and a field trial that
    diagnosed it as a lost variable proposed a repair that would have changed nothing. Resolving
    each entry against the directory the CALLER wrote it in preserves what the caller meant, which
    is the only reading that survives a ``cwd`` change.

    Empty entries are left alone: an empty ``PYTHONPATH`` element is a request for *the child's*
    working directory, not a path the caller wrote, and rewriting it would be inventing intent.
    """
    resolved = dict(os.environ if env is None else env)
    raw = resolved.get("PYTHONPATH")
    if raw:
        resolved["PYTHONPATH"] = os.pathsep.join(
            entry if not entry or os.path.isabs(entry) else str(Path(entry).resolve())
            for entry in raw.split(os.pathsep)
        )
    return resolved


def _run(cmd: list[str], cwd: Path, timeout: int = 600,
         env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              check=False, env=_child_env(env))
    except subprocess.TimeoutExpired as exc:
        return _EXIT_TIMEOUT, f"{type(exc).__name__}: {exc}"
    except OSError as exc:
        return _EXIT_UNLAUNCHABLE, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _suite_failure(cid: str, label: str, code: int, tail: str, timeout: int) -> CheckResult:
    """The FAIL a suite reports, worded by CAUSE rather than by exit code.

    A pure function of its arguments so the timeout wording can be falsified without waiting for a
    real timeout — a probe that had to spend ``timeout`` seconds to test this would not be run.
    """
    if code == _EXIT_TIMEOUT:
        return _fail(cid, Stage.SUITES,
                     f"{label} did not finish within {timeout}s — TIMEOUT, not a test failure",
                     f"{tail}\nA timeout is an environment fact until proven otherwise (L-25): "
                     f"check the machine's load before the suite. It still fails, because a "
                     f"timeout can also be a genuine hang and 'it did not finish' is not a pass.")
    if code == _EXIT_UNLAUNCHABLE:
        return _fail(cid, Stage.SUITES, f"{label} could not be launched at all", tail)
    return _fail(cid, Stage.SUITES, f"{label} FAILED (exit {code})", tail)


def _doc_system_documents(ctx: Ctx) -> list[str]:
    """Tracked Markdown whose front matter declares ``classification``. One derivation, two checks."""
    code, listing = _run(["git", "ls-files", "*.md"], ctx.root, timeout=60)
    if code != 0:
        return []
    found: list[str] = []
    for rel in listing.split():
        path = ctx.root / rel
        if not path.is_file():
            continue
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        fm = _GOVERNED_FRONT_MATTER_RE.match(head)
        if fm and "classification" in fm.group(1):
            found.append(rel)
    return found


def check_sample_builds(ctx: Ctx) -> CheckResult:
    """A real document must still build end to end."""
    docs = _doc_system_documents(ctx)
    if not docs:
        return _fail("BUILD-01", Stage.BUILD, "no doc-system documents to build",
                     "an empty set would make this check vacuous")
    # Build into a scratch directory, never in place. Building in place overwrote
    # `examples/capability-gallery.html`, a TRACKED deliverable, so every health run left the tree
    # dirty and a real regression would hide in that noise — the same defect as the `render_ms`
    # churn (`OG-19`). A check must not write into the tree it is checking.
    scratch = ctx.root / ".docgen" / "health-build"
    code, out = _run([_PY, "-m", "tools.docgen.cli", "build", *docs, "-o", str(scratch)],
                     ctx.root)
    # `.docgen/` is gitignored, so there is nothing to clean up and nothing to damage. The first
    # version built in place and then deleted every produced `.html` — which destroyed
    # `examples/capability-gallery.html`, a tracked deliverable this engine ships and
    # `PROJECT_INDEX.json` registers. `SUITE-03` caught it within one run.
    if code != 0:
        # "engine deps not installed" is an ABSENT TOOLCHAIN, not a broken engine — the flagship
        # gallery renders through the mermaid and ECharts bridges, which need `npm install`. Widening
        # this check from one pure-Python sample to every doc-system document quietly made a fresh
        # clone fail it, which would have contradicted the bootstrap this repository documents and
        # verifies. SKIP with the cause, exactly as SUITE-01/02 do for the same missing toolchain —
        # and a skip is not a soft pass: `--full` and `--strict` both fail on one, so a milestone
        # run still demands the real thing.
        if "engine deps not installed" in out or "npm install" in out:
            return _skip("BUILD-01", Stage.BUILD,
                         f"{len(docs)} doc-system document(s): renderer deps absent",
                         "run `npm install` in tools/mermaid-engine and tools/visual-engine. "
                         + out[-200:])
        return _fail("BUILD-01", Stage.BUILD,
                     f"{len(docs)} doc-system document(s) — build failed (exit {code})", out[-400:])
    return _ok("BUILD-01", Stage.BUILD,
               f"all {len(docs)} tracked doc-system document(s) build", out[-200:])


def check_cli_check_passes(ctx: Ctx) -> CheckResult:
    """``cli check`` must pass on EVERY tracked doc-system document, not one hardcoded sample.

    This check used to run only ``tools/docgen/sample.md``, so ``export_sanitizer``'s gate spine
    never executed against any other document at commit or push time — a document the engine's own
    gates rate BLOCKING passed both hooks and reached the remote with everything green.

    The document set is DERIVED, never listed: a doc-system document is a tracked Markdown file
    whose YAML front-matter declares ``classification`` (the same test the commit-time placement
    gate uses). Files with other front-matter schemas — the ``skills/*/SKILL.md`` manifests carry
    ``name``/``description`` for Claude Code, not a doc header — are correctly not in scope, and a
    new doc-system document joins the set with no edit here.
    """
    code, listing = _run(["git", "ls-files", "*.md"], ctx.root, timeout=60)
    if code != 0:
        return _skip("BUILD-02", Stage.BUILD, "git ls-files unavailable", listing[:200])
    docs: list[str] = []
    for rel in listing.split():
        path = ctx.root / rel
        if not path.is_file():
            continue
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        fm = re.match(r"\A\s*---\s*\n(.*?\n)---\s*\n", head, re.DOTALL)
        if fm and "classification" in fm.group(1):
            docs.append(rel)
    if not docs:
        return _fail("BUILD-02", Stage.BUILD,
                     "no doc-system documents found — the gate suite would run on nothing",
                     "no tracked .md declares `classification` in its front-matter")
    failures: list[str] = []
    for rel in docs:
        code, out = _run([_PY, "-m", "tools.docgen.cli", "check", rel], ctx.root)
        if code != 0:
            first = next((ln for ln in out.splitlines() if "crit:" in ln or "high:" in ln), out[-160:])
            failures.append(f"{rel} (exit {code}): {first.strip()[:140]}")
    if failures:
        return _fail("BUILD-02", Stage.BUILD,
                     f"cli check fails on {len(failures)} of {len(docs)} doc-system document(s)",
                     "; ".join(failures), failures)
    return _ok("BUILD-02", Stage.BUILD,
               f"cli check passes on all {len(docs)} tracked doc-system document(s)",
               ", ".join(docs))

def check_no_degraded_mode(ctx: Ctx) -> CheckResult:
    """No entry point may report degraded governance consultation.

    The engine spent its whole life printing "matrix absent — skipping active consultation". This
    check makes that regression impossible to reintroduce silently.
    """
    needles = ("skipping active consultation", "— skipping", "absent at")
    hits: list[str] = []
    for args in (["build", "tools/docgen/sample.md"], ["check", "tools/docgen/sample.md"], ["manifest"]):
        # The exit code used to be discarded (`_, out = ...`), so this check greped the stdout of
        # commands that may not have run at all — an ImportError or a usage error produces no
        # degraded-mode line and was read as evidence of health.
        code, out = _run([_PY, "-m", "tools.docgen.cli", *args], ctx.root)
        if code != 0:
            hits.append(f"cli {args[0]}: exited {code} — its output is not evidence of anything")
        hits.extend(f"cli {args[0]}: {ln.strip()}" for ln in out.splitlines()
                    if any(n in ln for n in needles))
    produced = ctx.root / "tools" / "docgen" / "sample.html"
    if produced.is_file():
        produced.unlink()
    if hits:
        return _fail("BUILD-03", Stage.BUILD, f"{len(hits)} degraded-mode line(s) still printed",
                     "; ".join(hits[:5]), hits)
    return _ok("BUILD-03", Stage.BUILD, "no degraded-mode consultation on any entry point")


# Runs `buildAllThemes()`/`loadTokens()` from the real adapter module and prints every file it
# would write, as JSON, WITHOUT ever writing to the tracked `themes/` directory — `--build`'s own
# `writeFileSync` calls are never reached because this never sets `process.argv`'s `--build` flag.
# Import path is relative to the invoking process's cwd (`ctx.root`), exactly as verified live.
_THEME_BUILD_NODE_SCRIPT = """
import { buildThemeFiles } from './tools/visual-engine/adapters/echarts/theme-adapter.mjs';
process.stdout.write(JSON.stringify(buildThemeFiles()));
"""


def check_theme_build_matches_source(ctx: Ctx) -> CheckResult:
    """BUILD-04 — the committed `themes/*.json` must equal a fresh rebuild, byte for byte.

    `RESKINNING_AND_THEME_POLICY.md` states the authority chain terminates at `themes/*.json`
    (marked GENERATED) via `theme-adapter.mjs`'s `buildAllThemes()` / `npm run build:themes`. Until
    this check, nothing ever re-ran that build and compared it against what is committed — no
    health check, no corpus guard, nothing under `tools/corpus_check/guards/*.py` referenced
    `THEMES_DIR`, `buildAllThemes()` or `theme-adapter.mjs` at all (`P8-044`). The six tracked
    theme files were write-only build residue: `tokens.json` could be re-vendored, the adapter
    edited, or a file hand-patched, and every gate still reported green, because nothing was
    reading the generator's own output back.

    This runs the SAME functions the `--build` CLI path calls, in a throwaway node subprocess, and
    diffs the result against the tracked files — never writing to `themes/` itself (the `--build`
    flag that triggers `writeFileSync` is never set), so this check cannot itself cause the drift
    it looks for.
    """
    adapter = ctx.root / "tools" / "visual-engine" / "adapters" / "echarts" / "theme-adapter.mjs"
    themes_dir = ctx.root / "tools" / "visual-engine" / "themes"
    if not adapter.is_file():
        return _fail("BUILD-04", Stage.BUILD, "theme-adapter.mjs is missing",
                     f"{adapter} absent — the themes it is meant to generate cannot be verified")
    node = shutil.which("node")
    if node is None:
        return _skip("BUILD-04", Stage.BUILD,
                     "node not on PATH — cannot rebuild themes.json to compare against source")
    code, out = _run([node, "--input-type=module", "-e", _THEME_BUILD_NODE_SCRIPT], ctx.root,
                     timeout=60)
    if code != 0:
        return _fail("BUILD-04", Stage.BUILD, f"theme rebuild failed (exit {code})", out[-800:])
    try:
        rebuilt = json.loads(out)
    except ValueError as exc:
        return _fail("BUILD-04", Stage.BUILD, "theme rebuild printed non-JSON output",
                     f"{type(exc).__name__}: {exc}. " + out[-400:])
    if not isinstance(rebuilt, dict) or not rebuilt:
        return _fail("BUILD-04", Stage.BUILD, "theme rebuild produced nothing to compare",
                     "buildAllThemes()/loadTokens() returned no files")
    problems: list[str] = []
    for name, content in sorted(rebuilt.items()):
        committed = themes_dir / name
        if not committed.is_file():
            problems.append(f"{name}: a fresh rebuild produces this file but it is not committed")
            continue
        on_disk = committed.read_text(encoding="utf-8")
        if on_disk != content:
            problems.append(f"{name}: committed file does not match a fresh rebuild (drift)")
    if themes_dir.is_dir():
        extra = sorted(p.name for p in themes_dir.glob("*.json") if p.name not in rebuilt)
        problems += [f"{name}: committed but the current build no longer produces it"
                    for name in extra]
    if problems:
        return _fail("BUILD-04", Stage.BUILD,
                     f"{len(problems)} theme file(s) diverge from a fresh rebuild",
                     "; ".join(problems), problems)
    return _ok("BUILD-04", Stage.BUILD,
               f"all {len(rebuilt)} theme file(s) match a fresh rebuild exactly", str(themes_dir))


# ======================================================================================
# 5 — SUITES (slow; --full only)
# ======================================================================================


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# node --test's own summary block, e.g. "ℹ pass 30". Matched after ANSI stripping.
# The leading "\u2139 " glyph node prints is NOT matched by \\W — Python's re treats it as a word
# character — so an anchored \\W* prefix silently never matched and every count went unchecked.
# `\\S*` consumes whatever marker glyph node uses; both ends stay anchored so prose cannot match.
_NODE_COUNT_RE = re.compile(
    r"^[ \t]*\S*[ \t]*(tests|suites|pass|fail|skipped|todo|cancelled)\s+(\d+)[ \t]*$", re.MULTILINE)
# mermaid-engine's own summary, e.g. "6/6 diagram types render clean".
_RATIO_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s+(.+?)\s+clean\s*$", re.MULTILINE)


def _npm_suite(ctx: Ctx, cid: str, pkg: str, floor: int) -> CheckResult:
    """Run a package's ``npm test`` and ASSERT ITS OWN REPORTED COUNTS, not just its exit code.

    ``floor`` is the minimum number of passing tests the suite must report. It used to be a display
    string ("expected 30/30") that was interpolated into the summary and never compared against
    anything, so health printed the number 30 as though it had checked it while being structurally
    blind to tests that had been DELETED or marked skipped/todo — only outright failures moved the
    exit code. A count nobody compares is decoration (LESSONS.md L-18).
    """
    if not ctx.full:
        return _skip(cid, Stage.SUITES, f"{pkg} suite not run (pass --full)")
    pkg_dir = ctx.root / "tools" / pkg
    if not (pkg_dir / "node_modules").is_dir():
        return _skip(cid, Stage.SUITES, f"{pkg}: node_modules absent — run npm install")
    code, out = _run(["npm", "test"], pkg_dir, timeout=900)
    plain = _ANSI_RE.sub("", out)
    tail = "\n".join(plain.splitlines()[-6:])
    if code != 0:
        return _fail(cid, Stage.SUITES, f"{pkg} suite FAILED (exit {code})", tail)

    counts = {k: int(v) for k, v in _NODE_COUNT_RE.findall(plain)}
    problems: list[str] = []
    if counts:
        for zero_key in ("fail", "skipped", "todo", "cancelled"):
            if counts.get(zero_key, 0):
                problems.append(f"{zero_key}={counts[zero_key]} (must be 0)")
        if counts.get("pass", 0) < floor:
            problems.append(f"pass={counts.get('pass', 0)} is below the floor of {floor}")
        summary = (f"{pkg} suite green — {counts.get('pass', 0)}/{counts.get('tests', 0)} pass, "
                   f"0 fail/skipped/todo (floor {floor})")
    else:
        ratio = _RATIO_RE.search(plain)
        if not ratio:
            return _fail(cid, Stage.SUITES,
                         f"{pkg} suite exited 0 but printed no summary this check can verify",
                         "neither a `node --test` count block nor an `N/M … clean` line was found; "
                         "an exit code alone cannot distinguish 30 passing tests from 0. " + tail)
        done, total = int(ratio.group(1)), int(ratio.group(2))
        if done != total:
            problems.append(f"{done}/{total} — not all cases reported clean")
        if total < floor:
            problems.append(f"{total} case(s) is below the floor of {floor}")
        summary = f"{pkg} suite green — {done}/{total} {ratio.group(3)} clean (floor {floor})"
    if problems:
        return _fail(cid, Stage.SUITES, f"{pkg} suite counts do not hold", "; ".join(problems) + "\n" + tail,
                     problems)
    return _ok(cid, Stage.SUITES, summary, tail)


def check_visual_engine(ctx: Ctx) -> CheckResult:
    """SUITE-01 — the visual-engine npm suite must pass AND report at least 30 passing tests."""
    return _npm_suite(ctx, "SUITE-01", "visual-engine", 30)


def check_mermaid_engine(ctx: Ctx) -> CheckResult:
    """SUITE-02 — the mermaid-engine npm suite must pass AND report at least 6 diagram types."""
    return _npm_suite(ctx, "SUITE-02", "mermaid-engine", 6)


_LINT_ERROR_RE = re.compile(r"^Found (\d+) error", re.MULTILINE)


# Hard upper bounds on what `lint_baseline.json` may declare. In CODE, so a "baseline update" to
# the JSON alone cannot loosen the gate — see `OG-174`. These may only ever be LOWERED.
_LINT_HARD_CEILING = {"ruff": 0, "mypy_strict": 0}


def check_lint_baseline(ctx: Ctx) -> CheckResult:
    """Lint and type-check counts must not exceed the pinned baseline.

    Exists because ``OG-02``'s error count was quoted at three different values in three documents
    across two phases while nothing measured it — and because this session's own edits took ruff
    from 22 to 26 silently, caught only by a manual measurement. The ceiling may only go DOWN.

    Mode-gated like the npm suites: it needs an external toolchain and takes ~30s, so it runs under
    ``--full``. If the toolchain is absent it SKIPs with the cause rather than passing — and under
    ``--full`` a skip fails the run, which is the honest answer to "we could not verify".
    """
    if not ctx.full:
        return _skip("SUITE-04", Stage.SUITES, "lint/type baseline not run (pass --full)")
    baseline_path = ctx.root / "tools" / "health" / "lint_baseline.json"
    if not baseline_path.is_file():
        return _fail("SUITE-04", Stage.SUITES, "lint baseline file missing", str(baseline_path))
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        ceilings = baseline["max_errors"]
        invocations = baseline["invocations"]
    except (OSError, ValueError, KeyError) as exc:
        return _fail("SUITE-04", Stage.SUITES, f"lint baseline unreadable: {exc}", str(baseline_path))

    # **The ceiling's rules need no tool, so they are judged BEFORE the tool is looked for** (`OG-311`). The skip used
    # to come first: on a machine without `uvx` (a CI runner, a contributor's laptop) a baseline whose ceiling had
    # been RAISED, or whose invocation had been narrowed to one directory, reported SKIP — unknown, not red — and the
    # two `OG-174` / `OG-175` guards were switched off exactly where nobody was measuring. Only the measurement needs `uvx`.
    runner = shutil.which("uvx")

    problems: list[str] = []
    measured: dict[str, int] = {}

    # **THE CEILING HAS A CEILING, AND IT LIVES IN CODE** (`OG-174`).
    #
    # `lint_baseline.json`'s own `_readme` says "A number nobody compares is decoration", and the
    # engine compared the measured errors against the ceiling — while the ceiling itself was an
    # uncompared, unlocked number in an ordinary JSON file. Raising `max_errors` turned a real ruff
    # error green in one edit, invisible in review as a "baseline update". The file's stated
    # contract is "may only go DOWN"; nothing enforced it. These bounds do.
    for key, hard in _LINT_HARD_CEILING.items():
        declared = int(ceilings.get(key, hard))
        if declared > hard:
            problems.append(
                f"{key}: the baseline declares a ceiling of {declared}, above the hard bound of "
                f"{hard} pinned in tools/health/checks.py — the ceiling may only go DOWN"
            )

    for tool, key in (("ruff", "ruff"), ("mypy", "mypy_strict")):
        argv = str(invocations[tool]).split()
        # **The invocation is DATA the guard executes verbatim** (`OG-175`). Narrowing its scope —
        # one path segment inside a JSON string — keeps the headline 0/22 intact while deleting
        # most of the analysed surface, and the check then invites re-pinning the now-lower count.
        # The target is asserted rather than trusted.
        if not any(a.rstrip("/") == "tools" for a in argv):
            problems.append(
                f"{tool}: the baseline's invocation {str(invocations[tool])!r} does not analyse "
                "tools/ — narrowing the scope is how a ceiling is met without fixing anything"
            )
            continue
        if runner is None:
            continue  # the scope rule above has been applied; only the measurement needs the tool
        code, out = _run([runner, *argv[1:]] if argv[0] == "uvx" else [runner, *argv],
                         ctx.root, timeout=900)
        # Strip ANSI first: mypy colours its summary line, so an anchored `^Found` never matched
        # and the check reported "could not parse" while the number was right there.
        plain = _ANSI_RE.sub("", out)
        # **Both arms need the clean-output case** (`OG-176`). Only ruff had one, so driving
        # mypy --strict to ZERO — the exact destination `lint_baseline.json`'s "may only go DOWN"
        # contract points at — printed "Success: no issues found", matched no error-count pattern,
        # and turned SUITE-04 RED with the message "lint/type baseline exceeded". Reaching the goal
        # was reported as breaking the rule.
        if code == 0 and ("All checks passed" in plain or "Success: no issues found" in plain):
            count = 0
        else:
            found = _LINT_ERROR_RE.search(plain)
            if not found:
                problems.append(f"{tool}: could not parse an error count from its output (exit {code})")
                continue
            count = int(found.group(1))
        measured[key] = count
        if count > int(ceilings[key]):
            problems.append(f"{tool}: {count} error(s) exceeds the pinned ceiling of {ceilings[key]}")
    if problems:
        return _fail("SUITE-04", Stage.SUITES,
                     f"lint/type baseline exceeded ({len(problems)} problem(s))",
                     "; ".join(problems) + f" — baseline: {baseline_path.name}", problems)
    if runner is None:
        return _skip("SUITE-04", Stage.SUITES, "uvx not on PATH — cannot measure lint/types",
                     f"pinned ceilings: {ceilings}; install uv, or measure with: "
                     f"{invocations.get('ruff')} / {invocations.get('mypy')}")
    improved = [k for k, v in measured.items() if v < int(ceilings[k])]
    note = f" — {', '.join(improved)} improved; re-pin the baseline" if improved else ""
    return _ok("SUITE-04", Stage.SUITES,
               f"lint/type baseline holds ({', '.join(f'{k}={v}' for k, v in sorted(measured.items()))})",
               f"ceilings {ceilings}{note}")


_UNITTEST_COUNT_RE = re.compile(r"^Ran (\d+) tests? in", re.MULTILINE)
# A floor, not the exact count — the suite is expected to GROW, and a check that fails on growth
# trains people to delete tests. It fails on SHRINKAGE, which is the direction that matters.
#
# The floor is DERIVED, not written down. A literal floor is a stale fact by construction: this one
# sat at 30 while the suite grew to 71, so 41 counter-examples could have been deleted with the
# engine still reporting green — the check certified a suite two-thirds smaller than the one it was
# guarding. Counting the `def test_*` methods actually present in the files makes the expectation
# track the suite, and turns the check into the one it should always have been: every test that
# EXISTS must also RUN. That is what catches the silent case — a broken import makes unittest skip
# a whole module, and the run stays green with the tests simply absent.
# **A RATCHET, and it may only go UP** (`OG-153`). It sat at 30 against a suite of 196, so **150
# retained counter-examples could be deleted and this check still reported green** — while its own
# docstring claims it "fails on SHRINKAGE". The `defined` cross-check below does not save it: that
# compares what RAN against what is DEFINED, and deleting a test drops both.
#
# This is the mirror of `lint_baseline.json`'s ceiling, whose `_readme` says "A number nobody
# compares is decoration" — and whose contract is "may only go DOWN". A floor may only go UP, and
# the closeout raises it when the suite legitimately grows. Set to the measured count at the time
# of writing, less a small margin so an environment that skips a module is not a false red.
#
# **Ratcheted 190 → 500 by the 1.0.0 audit.** The comment above says the closeout raises it "when
# the suite legitimately grows" — and nothing forced that, so it sat at 190 while the suite grew to
# 575: a gutting-backstop that had drifted to a THIRD of the suite it guards, the same "written-down
# floor is stale the moment the suite grows" failure it had already suffered once at 30-vs-71. 500
# keeps a ~13% margin below the 575 defined. The drift itself is now a gate, not a hope:
# `test_the_pytest_and_harness_floors_track_their_suites` refuses a floor below 80% of the defined
# count (RULES.md Rule 1 — fix the class, so the ratchet can never again be forgotten).
# **Ratcheted 500 -> 550 by an earlier round.** The suite grew 575 -> 632 defined (the taxonomy
# alias, ci_cost_control's first-ever tests, the html-template security cases, the audience/level
# view generator, the CSS-injection and recursion guards, and the mark hook). At 632 defined, the
# 80%-of-defined rule this floor is checked against needs >= 506, so 500 was about to make
# `test_the_pytest_and_harness_floors_track_their_suites` red -- the ratchet the comment above
# says the closeout performs "when the suite legitimately grows". 550 keeps the same ~13% margin
# below the defined count that 500 kept below 575.
# Wall-clock budget for the Python counter-example suite. Raised 600 -> 1200 by that same round:
# the suite measured 522 s at 592 defined tests and then grew to 637, so 600 s began TIMING OUT —
# and SUITE-05 reports a timeout as a failure, correctly ("a timeout is an environment fact until
# proven otherwise", L-25), which made a green suite unreachable for a reason that had nothing to
# do with any test. A timeout is a budget, not a floor: it exists to catch a HANG, so it must stay
# comfortably above the honest runtime rather than tracking it closely.
_PYTHON_SUITE_TIMEOUT_S = 1200

# Three separate patches all raised this from 550, on the same tag — the number is chosen for the
# FULL union of everything outstanding, not for whichever patch happened to touch this line last:
#
#   patch A alone                  697 defined, lower bound 557
#   patch B alone                  697 defined, lower bound 557
#   patch C alone                  691 defined, lower bound 552
#   patches A + B                  707 defined, lower bound 565
#   all three (this tree)          711 defined, lower bound 568
#
# 569 was minimum-plus-one at THAT full union and inside [lower bound, defined] for every subset.
#
# **Ratcheted 569 -> 573 by a later patch (2026-09-24).** `tools/tests/test_views.py` gained
# `ViewsRegisterDespiteAnUnrelatedHostProjectIndexPackage` (2 tests, the falsifying counter-example
# for the artifact-registry-move fix) and `tools/tests/test_config_resolution.py` gained
# `ProjectIndexPathIsHostRootRelativeNotCwdRelative` (3 tests, for the `project_index_path()`
# CWD-vs-host-root fix in the same patch) — taking the defined count 711 -> 716, lower bound
# 568 -> 572. 573 is minimum-plus-one at this new full union. Picking any single patch's own
# minimum is green on that side and RED on the union — the failure an earlier pull request hit, and this constant's
# fourth time producing it (see the paragraph above) — so the number is chosen for the union this
# tree actually carries, verified against this tree's own `Ran N tests` count before landing, not
# assumed from a patch.
_PYTEST_HARD_FLOOR = 728  # 2026-10-10, 1.0.14 (OG-300..OG-303 tests): 909 defined tests, lower bound 727, minimum-plus-one as above.
# (645 was minimum-plus-one at 807; the 808th test landed after it was set and `test_the_pytest_and_harness_floors_track_their_suites`
# refused the tree, which the full health run reported as SUITE-05. A floor is chosen against the tree it ships with: re-count `Ran N
# tests` on the final tree, not on the tree the work started from.)

# `unittest`'s trailing `OK (skipped=N)` / `FAILED (… skipped=N)` count.
_UNITTEST_SKIP_RE = re.compile(r"skipped=(\d+)")


def _defined_python_tests(tests_dir: Path) -> int:
    """Count `def test_*` methods across tools/tests/ by parsing, not importing."""
    total = 0
    for path in sorted(tests_dir.rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                total += 1
    return total


def check_python_tests(ctx: Ctx) -> CheckResult:
    """The retained counter-examples must pass, and there must not be fewer of them than before.

    This is `OG-32`'s closure and the structural fix for the defect class that produced most of this
    project's findings. Every guard here was falsified BY HAND when it was written — shown red, then
    restored — and the falsification was thrown away. Nothing re-ran it, so each guard decayed from
    *proven* to *assumed*, and four verification passes found 203 defects, most of them guards that
    no longer did what their name said.

    Deliberately NOT mode-gated. It runs in about a second, and a suite that only runs under
    ``--full`` is a suite that does not run at commit or push time — which is the opt-in problem
    this engine already fixed once for its gates (`OG-10`).
    """
    if _inside_hook_probe():
        # A health run nested inside a hook probe or the attack harness. The suite is already being
        # run by the outer invocation; re-running it here is the same evidence at ~100 s a copy,
        # multiplied by every lab push the harness performs.
        return _skip("SUITE-05", Stage.SUITES,
                     "python counter-examples skipped inside a hook probe",
                     "a live outer probe marker is present — the outer run owns this suite")
    tests_dir = ctx.root / "tools" / "tests"
    if not tests_dir.is_dir():
        return _fail("SUITE-05", Stage.SUITES, "tools/tests/ is absent",
                     "the retained counter-examples are the difference between a guard that is "
                     "proven and one that is assumed (OG-32)")
    code, out = _run([_PY, "-m", "unittest", "discover", "-s", "tools/tests", "-t", "."],
                     ctx.root, timeout=_PYTHON_SUITE_TIMEOUT_S)
    plain = _ANSI_RE.sub("", out)
    tail = "\n".join(plain.splitlines()[-4:])
    if code != 0:
        return _suite_failure("SUITE-05", "python counter-examples", code, tail, _PYTHON_SUITE_TIMEOUT_S)
    found = _UNITTEST_COUNT_RE.search(plain)
    if not found:
        return _fail("SUITE-05", Stage.SUITES,
                     "python test suite exited 0 but printed no count this check can verify",
                     "an exit code alone cannot distinguish 38 passing tests from 0 collected. " + tail)
    ran = int(found.group(1))
    defined = _defined_python_tests(tests_dir)
    if ran < _PYTEST_HARD_FLOOR:
        return _fail("SUITE-05", Stage.SUITES,
                     f"python counter-examples shrank: {ran} ran, hard floor is "
                     f"{_PYTEST_HARD_FLOOR}",
                     "tests were deleted or stopped being collected. " + tail, [str(ran)])
    if defined and ran < defined:
        return _fail("SUITE-05", Stage.SUITES,
                     f"{defined} python test(s) are defined but only {ran} ran",
                     "a test that exists but is not collected is a guard that silently stopped "
                     "guarding — usually an import error in one module. " + tail,
                     [str(ran), str(defined)])
    # **A SKIPPED counter-example did not run** (`OG-154`). `unittest` prints `OK (skipped=10)` and
    # exits 0, and this check read only the `Ran N` line — so in a fresh clone, in CI, and in every
    # `git archive` lab, ten probes silently did not execute and health said "green". A skip is an
    # environment fact worth NAMING (`L-25`), not a pass to fold into one.
    skipped = 0
    found_skips = _UNITTEST_SKIP_RE.search(plain)
    if found_skips:
        skipped = int(found_skips.group(1))
    note = f", {skipped} SKIPPED (did not execute)" if skipped else ""
    return _ok("SUITE-05", Stage.SUITES,
               f"python counter-examples green — {ran} ran{note}, {defined} defined "
               f"(hard floor {_PYTEST_HARD_FLOOR})", tail)


#: The trailing per-class breakdown is OPTIONAL in the pattern on purpose: a
#: harness older than this check still parses, and the absence is then REPORTED rather than
#: guessed at. Reading two numbers and calling every failure a moat breach is the defect.
_HARNESS_RESULT_RE = re.compile(
    r"^RESULT: (\d+) passed, (\d+) failed(?:\s*\((\d+) attack, (\d+) control\))?",
    re.MULTILINE,
)
# Same reasoning as `_PYTEST_HARD_FLOOR`: a written-down floor is stale the moment the suite grows,
# so the real expectation is derived from the `verdict` calls present in the script. The literal
# survives only as a hard floor — a backstop against the script being gutted entirely.
# Same ratchet as `_PYTEST_HARD_FLOOR` (`OG-153`). It sat at 15 against 21 defined attacks, so six
# could be deleted while the summary read "all 15 retained moat attacks still refused" — a sentence
# that sounds like completeness and measures the opposite.
_HARNESS_HARD_FLOOR = 20


def _defined_harness_attacks(script: Path) -> int:
    """Count the attack cases in hook_attacks.sh by counting its `verdict` assertions."""
    try:
        text = script.read_text(encoding="utf-8")
    except OSError:
        return 0
    # Anchored at a STATEMENT boundary, not a line start. Most cases are written
    # `git push … ; verdict 1 $? "…"`, so an `^\s*verdict` anchor counted 6 of 20 — and an
    # UNDER-count is the dangerous direction here: `passed < defined` could then never fire, which
    # would have made this guard vacuous. It was caught by reading the number the check printed
    # ("6 defined") rather than by trusting that the check passed, which is the same discipline
    # that found every other stale count in this repository.
    return len(re.findall(r"(?:^|;|&&|\|\|)\s*verdict\s", text, re.MULTILINE))


def check_moat_attacks(ctx: Ctx) -> CheckResult:
    """The retained moat attacks must still be refused.

    Attacks that once defeated the git moat, kept runnable. `CHANGELOG [0.3.2]` cited a
    "12-case harness" as the evidence for every moat CRITICAL and `THREAT_MODEL.md` said the cases
    "are re-run by the harness" — while no harness existed in the tree. That is
    `docs/process/RULES.md` Rule 1 violated on this project's most load-bearing claim.

    **The attack count is never written here as a literal** (`P8-059`). This docstring and this
    function's own error strings twice named a hardcoded "seventeen"/"17" after the harness had
    already grown past that count (live count, derived, never copied: `_defined_harness_attacks`,
    which counts `tools/tests/hook_attacks.sh`'s own `verdict` calls — the same technique
    `tools/hooks/pre-push` uses for the identical number, in the identical comment, for the
    identical reason). A count that is not derived goes stale the moment the harness grows and
    nothing that reads it notices.

    **Mode-gated, and the deviation is stated rather than hidden.** Rule 1 says a counter-example
    runs on every health run; this one takes about six minutes because every case drives real git,
    real hooks and a real bare remote, so it runs under ``--full`` only. That is a genuine departure
    from the rule, made deliberately: the alternative is a six-minute pre-push, which people would
    route around, and a gate people route around is worth less than one that runs at milestones.

    It earned its keep immediately — on its first complete run it caught the interpreter guard being
    satisfied by a stub that merely exits 0, a fix that would otherwise have shipped broken and
    looked green.
    """
    if not ctx.full:
        return _skip("SUITE-06", Stage.SUITES,
                    "moat attack harness not run (pass --full; ~2 min measured 2026-08-21)")
    script = ctx.root / "tools" / "tests" / "hook_attacks.sh"
    if not script.is_file():
        return _fail("SUITE-06", Stage.SUITES, "the retained moat attacks are missing",
                     f"{script} absent — the evidence for every moat CRITICAL would be unretained "
                     "again (RULES.md Rule 1)")
    # Computed here, once, so both the "no result line" exit below AND the "fewer ran than are
    # defined" exit further down report the SAME live count — never a literal (`P8-059`).
    defined = _defined_harness_attacks(script)
    # The harness IS an exhaustive behavioural probe of both hooks — it performs ~20 real
    # commits and pushes through them. Each of those pushes runs the pre-push hook, which runs
    # `tools.health`, which would start `STRUCT-04`'s own ~72 s probe: the same evidence, ~20 times,
    # nested inside the test that already proves it. That nesting is what pushed this check past its
    # 1800 s ceiling, so it reported a TIMEOUT rather than a result — and a gate that cannot finish
    # is a gate that fails for environmental reasons. Marking the environment lets those inner runs
    # skip the redundant probe (with the reason printed) while every attack here still executes.
    harness_env = dict(os.environ)
    harness_marker = _mint_probe_marker(harness_env)
    with harness_marker:
        code, out = _run(["bash", str(script)], ctx.root, timeout=1800, env=harness_env)
    plain = _ANSI_RE.sub("", out)
    tail = "\n".join(plain.splitlines()[-6:])
    found = _HARNESS_RESULT_RE.search(plain)
    if not found:
        return _fail("SUITE-06", Stage.SUITES,
                     f"the attack harness printed no result line (exit {code})",
                     f"an exit code alone cannot distinguish {defined} refused attacks from 0 "
                     "run. " + tail)
    passed, failed = int(found.group(1)), int(found.group(2))
    # A failed ATTACK and a failed POSITIVE CONTROL mean opposite things, and this
    # branch used to report both as "N moat attack(s) are no longer refused" — pointing at the moat
    # while the cause was the lab or an unrelated red health. Measured twice (once in an earlier
    # host finding, and once when two controls failed because new modules were untracked and so
    # absent from a `git ls-files` lab); each cost a full misdiagnosis. The harness now reports the
    # split and this names whichever actually happened.
    fail_attack = int(found.group(3)) if found.group(3) is not None else None
    fail_control = int(found.group(4)) if found.group(4) is not None else None
    if failed and fail_attack is None:
        return _fail("SUITE-06", Stage.SUITES,
                     f"{failed} verdict(s) failed, and the harness did not report their class",
                     "this check and hook_attacks.sh have drifted apart: without the "
                     "`(N attack, M control)` breakdown a failed positive control is "
                     "indistinguishable from a breached moat, which is the misdiagnosis this "
                     "check exists to prevent. " + tail,
                     [f"{failed} failed"])
    if fail_attack and fail_control:
        return _fail("SUITE-06", Stage.SUITES,
                     f"{fail_attack} moat attack(s) are no longer refused, and "
                     f"{fail_control} positive control(s) failed",
                     "BOTH classes failed — fix the control first: a broken lab can also make an "
                     "attack look un-refused. " + tail,
                     [f"{fail_attack} attack", f"{fail_control} control"])
    if fail_attack:
        return _fail("SUITE-06", Stage.SUITES,
                     f"{fail_attack} moat attack(s) are no longer refused",
                     tail, [f"{fail_attack} attack"])
    if fail_control:
        return _fail("SUITE-06", Stage.SUITES,
                     f"{fail_control} positive control(s) failed — the moat is NOT implicated",
                     "a control asserts a LEGITIMATE operation still succeeds, so this is the lab "
                     "or an unrelated red health, not a hole. The pre-push hook runs health, so a "
                     "red check of any kind fails the clean-push control; untracked new modules "
                     "are absent from the `git ls-files` lab and break it the same way. " + tail,
                     [f"{fail_control} control"])
    if code != 0:
        return _fail("SUITE-06", Stage.SUITES,
                     f"the attack harness exited {code} with every verdict passing",
                     "no attack and no control failed, so this is the harness or the lab itself — "
                     "an import error, a missing tool, or a trap firing after the last verdict. "
                     "Not a moat result. " + tail)
    if passed < _HARNESS_HARD_FLOOR:
        return _fail("SUITE-06", Stage.SUITES,
                     f"the attack set shrank: {passed} ran, hard floor is {_HARNESS_HARD_FLOOR}",
                     "attacks were deleted or stopped being reached. " + tail)
    if defined and passed < defined:
        return _fail("SUITE-06", Stage.SUITES,
                     f"{defined} moat attack(s) are defined but only {passed} ran",
                     "an attack that exists but is never reached is not a test — usually an early "
                     "`exit`, or a lab that failed to build. " + tail, [str(passed), str(defined)])
    return _ok("SUITE-06", Stage.SUITES,
               f"all {passed} retained moat attacks still refused ({defined} defined, hard floor "
               f"{_HARNESS_HARD_FLOOR})", tail)


_INDEX_COUNT_RE = re.compile(r"(\d+)\s+artifact\(s\) registered")


def check_project_index(ctx: Ctx) -> CheckResult:
    """SUITE-03 — the artifact index must resolve, over a NON-EMPTY set, and the dashboard must
    render every row it holds.

    **It used to print "project index resolves" and nothing else.** `PROJECT_INDEX.json` holds one
    artifact for a 295-file repository, so the green line was true of exactly one row — and would
    have been just as green over zero. That is the vacuity `test_no_guard_passes_vacuously` exists
    to refuse, in the package that owns that test. A reader seeing "project index resolves" cannot
    tell a working index from an empty one, so the count is now IN the line and an empty index is a
    hard failure.

    **What this check does and does not measure, said out loud.** It is a RESOLUTION probe: every
    registered row points at a real file, no duplicates, and the dashboard renders all of them. It
    is NOT a COVERAGE measure — it cannot tell you that the artifacts this engine ships (the
    gallery, the themes, the goldens) are registered, because the index is the only statement of
    what "should" be there. Registering the shipped artifacts is a separate, deliberate act; until
    then this line means "the rows that exist are sound", and now says so.

    The `dashboard` subcommand had no test and no health check of any kind — it was executable
    surface nothing ran. It is exercised here against the live index, into the gitignored
    `.health/` directory, and its output must name every registered artifact: a dashboard that
    silently drops a row is a reporting failure the `verify` subcommand cannot see.

    **The rows come from the CLI, never from a path spelled here.** The first version of this
    check read `ctx.root / "PROJECT_INDEX.json"` directly while `verify` and `dashboard` resolved
    the index through `engine_config.project_index_path()` — so with `ENGINE_PROJECT_INDEX_PATH`
    set, the count and the titles came from two different files and the comparison was between
    unrelated documents. That is the identical defect `STRUCT-08` was just fixed for (`P8-100`):
    a check that hardcodes a path the thing it certifies resolves. `list --json` asks the engine
    where its own index is.

    **Titles are compared HTML-ESCAPED**, because `dashboard.py` writes every cell through
    `html.escape`. Comparing the raw title would report `Themes & Tokens` as "silently omitted"
    from a page that renders it perfectly as `Themes &amp; Tokens` — a false red on the first
    artifact anyone registers with an ampersand in its name.
    """
    code, out = _run([_PY, "-m", "tools.project_index.cli", "verify"], ctx.root)
    if code != 0:
        return _fail("SUITE-03", Stage.SUITES, f"project_index verify failed (exit {code})",
                     out[-400:])
    found = _INDEX_COUNT_RE.search(out)
    if not found:
        return _fail("SUITE-03", Stage.SUITES,
                     "project_index verify printed no artifact count",
                     "an exit code alone cannot distinguish a resolving index from an empty one. "
                     + out[-300:])
    registered = int(found.group(1))
    if registered == 0:
        return _fail("SUITE-03", Stage.SUITES,
                     "the project index registers no artifacts",
                     "`verify` exits 0 over an empty index — every row resolves because there are "
                     "no rows. A green line over nothing is the failure mode this package exists "
                     "to refuse.")
    code, rows_out = _run([_PY, "-m", "tools.project_index.cli", "list", "--json"], ctx.root)
    if code != 0:
        return _fail("SUITE-03", Stage.SUITES, f"project_index list --json failed (exit {code})",
                     rows_out[-400:])
    try:
        rows = json.loads(rows_out)
    except ValueError as exc:
        return _fail("SUITE-03", Stage.SUITES, "project_index list --json emitted unparseable JSON",
                     f"{type(exc).__name__}: {exc} — `verify` reported {registered} row(s)")
    titles = [str(a.get("title") or a.get("id") or "") for a in rows]
    probe_rel = ".health/project-index-probe.html"
    probe = ctx.root / probe_rel
    probe.parent.mkdir(parents=True, exist_ok=True)
    code, dash_out = _run([_PY, "-m", "tools.project_index.cli", "dashboard",
                           "--out", probe_rel], ctx.root)
    if code != 0:
        return _fail("SUITE-03", Stage.SUITES, f"project_index dashboard failed (exit {code})",
                     dash_out[-400:])
    try:
        page = probe.read_text(encoding="utf-8")
    except OSError as exc:
        return _fail("SUITE-03", Stage.SUITES,
                     "project_index dashboard exited 0 but wrote no readable page",
                     f"{type(exc).__name__}: {exc}")
    finally:
        probe.unlink(missing_ok=True)
    missing = [t for t in titles if t and html.escape(t) not in page]
    if missing:
        return _fail("SUITE-03", Stage.SUITES,
                     f"the dashboard silently omits {len(missing)} registered artifact(s)",
                     "; ".join(missing[:5]), missing)
    return _ok("SUITE-03", Stage.SUITES,
               f"all {registered} registered artifact(s) resolve and render "
               f"(a resolution probe over {registered} row(s), not a coverage measure)",
               f"{len(page)}-byte dashboard names every row; " +
               (out.splitlines()[-1] if out else "exit 0"))


# ======================================================================================
# The registry — ADD A CHECK BY ADDING ONE LINE HERE
# ======================================================================================

_GOVERNANCE_TABLE_DOCS = (
    "docs/process/OPEN_GATES.md",
    "docs/process/VERIFICATION_LOG.md",
    "docs/plan/BUILD_PLAN.md",
    "docs/design/doc-system/RULEBOOK.md",
    "docs/design/doc-system/DOC_MANIFEST.md",
)


def check_governance_tables_are_whole(ctx: Ctx) -> CheckResult:
    """CONS-10 — no governance table is split in two by a blank line.

    A blank line between two table rows ENDS the Markdown table and starts a new one. Nothing about
    the rendered page or the raw source makes that visible: the rows keep their pipes and keep
    lining up, so the file reads as one table to a human and parses as several to a program.

    Measured on 2026-08-21: `OPEN_GATES.md`'s `## Open` section was **five tables**, and the first
    held 10 of its 22 rows. That file is the ledger the phase gate itself consults — *"a phase does
    not begin while a known defect is open"* is answered by reading it — so a reader taking the
    first table would have certified the gate satisfied while twelve rows sat unread below a break
    it could not see. `OG-36` records that five different table readers in this repository disagree
    about this corpus; this check removes one of the reasons they can.
    """
    broken: list[str] = []
    for rel in _GOVERNANCE_TABLE_DOCS:
        path = ctx.root / rel
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if line.strip():
                continue
            prev = lines[i - 1].strip() if i else ""
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if md_table.is_row(prev) and md_table.is_row(nxt):
                broken.append(f"{rel}:{i + 1}")
    if broken:
        return _fail("CONS-10", Stage.CONSISTENCY,
                     f"{len(broken)} blank line(s) split a governance table in two",
                     "a blank line between two table rows ends the table; every row after it is a "
                     "SEPARATE table to any parser, while looking continuous to a reader: "
                     + ", ".join(broken[:6]), broken[:6])
    return _ok("CONS-10", Stage.CONSISTENCY,
               f"all governance tables across {len(_GOVERNANCE_TABLE_DOCS)} document(s) are whole",
               "no blank line sits between two table rows")


def check_corpus_claims(ctx: Ctx) -> CheckResult:
    """CONS-11 — the corpus checker's guard set must be clean over this repository's own documents.

    `docs/CHARTER.md` purpose 2: this repository is the engine's first corpus, so the guards run
    over the tracked Markdown `git ls-files` reports — not over fixtures. Health owns the single
    command a session has to remember, so `tools/corpus_check/` reports through here rather than
    being a second thing to run and therefore a thing nobody runs (`OG-10`'s lesson about opt-in
    gates, applied one layer up).

    **This does not duplicate `CONS-01…CONS-10`; it extends them.** Which guard defers to which
    check is recorded guard-by-guard in `docs/plan/PHASE3_OVERLAP.md` and restated in each guard's
    own module docstring — `crossrefs` leaves backticked paths to `CONS-06`, `symbols` leaves
    `RULEBOOK.md`'s Status blocks to `CONS-07`, `cross-doc` leaves its five pairs to
    `CONS-01…CONS-05`.

    Run in-process rather than as a subprocess: `run_all` already turns a guard that raises into a
    FAILURE with its traceback, so the fail-closed contract is preserved, and a subprocess would
    only add interpreter startup to a check that already builds documents.

    **A guard SKIP propagates as a health SKIP — which is not a pass, and is fatal under `--full`
    or `--strict`, but IS accepted by a default run and therefore by the pre-push hook.** That is
    stated plainly because the first version of this docstring claimed the opposite ("a SKIP from any
    guard is a FAILURE here") while the code did the propagating, and `CHANGELOG.md` repeated the
    claim. A verifier proved the gap end to end: on a fresh clone, in CI, and in every `git archive`
    lab, `rendered-output` cannot build, so the guard Phase 3 added specifically to catch what only
    built output shows checked nothing and the push was accepted.

    The exposure is narrowed rather than merely documented: `rendered-output` now falls back to
    inspecting the **tracked** docgen-built artifacts when the engines are absent, so it checks
    something real instead of nothing, and still reports SKIP because a committed snapshot cannot
    show a defect introduced since. Run `--full`, or install the engines, to check the corpus as it
    actually stands.
    """
    try:
        from tools.corpus_check.corpus import Corpus
        from tools.corpus_check.guards import GUARDS
        from tools.corpus_check.model import Status as GuardStatus
        from tools.corpus_check.run import run_all
    except ImportError as exc:
        return _fail("CONS-11", Stage.CONSISTENCY, f"cannot import tools.corpus_check: {exc}",
                     "the corpus checker is Phase 3's deliverable; its absence is a failure, "
                     "never a skip")

    results = run_all(Corpus(root=ctx.root))
    if not results:
        return _fail("CONS-11", Stage.CONSISTENCY, "the guard registry is empty",
                     "a checker with no guards passes over everything, which is the vacuous pass "
                     "this package exists to catch (LESSONS.md L-19)")
    checked = sum(r.checked for r in results)
    # A guard that SKIPPED could not run; a guard that FAILED found something. Collapsing the two
    # is what made a fresh clone report a broken engine: `rendered-output` cannot build without
    # `node_modules`, and calling that a corpus defect took the whole moat down with it. SKIP
    # propagates as SKIP — still not a pass, and `--full`/`--strict` still fail on it, exactly as
    # `SUITE-01`/`SUITE-02` behave for the same missing dependency.
    skipped_guards = [r for r in results if r.status is GuardStatus.SKIP]
    bad = [r for r in results if r.status is GuardStatus.FAIL]
    if not bad and skipped_guards:
        return _skip("CONS-11", Stage.CONSISTENCY,
                     f"{len(skipped_guards)} of {len(results)} corpus guard(s) could not run",
                     "; ".join(f"{r.guard}: {r.summary}" for r in skipped_guards))
    if bad:
        detail = [f"{r.guard}: {r.summary}" for r in bad]
        first = [f.render().splitlines()[0] for r in bad for f in r.sorted_findings()[:2]]
        return _fail("CONS-11", Stage.CONSISTENCY,
                     f"{len(bad)} of {len(results)} corpus guard(s) not green",
                     "; ".join(detail[:4]) + ("\n" + "\n".join(first[:6]) if first else ""),
                     detail)
    return _ok("CONS-11", Stage.CONSISTENCY,
               f"all {len(GUARDS)} corpus guard(s) clean across {checked} claim(s)",
               ", ".join(r.guard for r in results))


def check_engine_config_parses(ctx: Ctx) -> CheckResult:
    """STRUCT-08 — if the config file actually in force exists, it must parse.

    `engine_config._raw_config()` returns `{}` on any read or parse error, and that behaviour is
    deliberate: it is called at import time by the CLI, the generator, the adjudicator and by
    `run.py`'s own `main()` — BEFORE `run_all()`'s fail-closed wrapper exists — so raising there
    takes down every entry point including the one that would report the problem (`LESSONS.md`
    L-17). The consequence is that a single stray byte silently demotes the engine to built-in
    defaults: every path override, every tool location, every host-root setting in that file stops
    applying while the operator believes it is in force.

    Fail-closed belongs HERE, where failing loudly costs nothing. Absent is fine — the engine is
    designed to run with no config at all; present-but-unparseable never is.

    **Must resolve the path the same way `_raw_config()` does** (`P8-100`). This used to hardcode
    `ctx.root / "engine.config.json"` unconditionally — so with `ENGINE_CONFIG_PATH` set to a
    broken or entirely absent file, `_raw_config()` silently fell back to built-in defaults (or
    printed a warning STRUCT-08 never read) while this check kept certifying the file NOT actually
    in force. Measured live: `ENGINE_CONFIG_PATH=/…/broken.json` (invalid JSON) still reported
    `[PASS] engine.config.json parses (9 top-level key(s))` — the count of the untouched default
    file, not of the broken one the engine was actually running on.
    """
    override = os.environ.get("ENGINE_CONFIG_PATH", "")
    if override:
        path = Path(override)
        label = f"{path} (ENGINE_CONFIG_PATH)"
    else:
        path = ctx.root / "engine.config.json"
        label = str(path)
    if not path.is_file():
        if override:
            # An explicit override naming a file that is not there is never "no config wanted" —
            # that reading is reserved for the unset-env-var default case below. `_raw_config()`
            # discards this silently (it warns only when the path EXISTS but fails to parse), so
            # the engine runs on built-in defaults while the operator believes ENGINE_CONFIG_PATH
            # is in force. Failing here is the only place that says so.
            return _fail("STRUCT-08", Stage.STRUCTURE,
                         "ENGINE_CONFIG_PATH names a file that does not exist",
                         f"{path} absent — the engine silently discards this override and every "
                         "entry point falls back to built-in defaults with no warning that the "
                         "file actually in force is not this one", [str(path)])
        return _ok("STRUCT-08", Stage.STRUCTURE, "no engine.config.json — built-in defaults apply",
                   "absent is a supported configuration, not a failure")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _fail("STRUCT-08", Stage.STRUCTURE,
                     f"{label} exists but does not parse",
                     f"{type(exc).__name__}: {exc} — the engine is silently running on built-in "
                     "defaults and every setting in that file is being ignored", [str(path)])
    if not isinstance(data, dict):
        return _fail("STRUCT-08", Stage.STRUCTURE,
                     f"{label} is a {type(data).__name__}, not an object",
                     "every reader indexes it as a mapping; a list or a string is ignored wholesale")
    return _ok("STRUCT-08", Stage.STRUCTURE,
               f"{label} parses ({len(data)} top-level key(s))", str(path))



def _tracked_npm_lockfiles(ctx: Ctx) -> tuple[list[str], str]:
    """Every ``package-lock.json`` this repository TRACKS, derived — never a hardcoded list.

    Returns ``(repo-relative paths, how they were derived)``. ``git ls-files`` is authoritative
    because tracked-ness is exactly the property that matters: a lockfile a fresh clone receives is
    a lockfile a fresh ``npm ci`` installs from. The filesystem fallback exists only so that a tree
    without git still gets a fail-CLOSED answer rather than a silently empty subject set;
    ``node_modules/`` is excluded on both routes (a dependency's own lockfile is not ours to attest).
    """
    code, listing = _run(["git", "ls-files", "*package-lock.json"], ctx.root, timeout=60)
    if code == 0:
        rels = sorted(r for r in listing.split() if "node_modules/" not in r)
        return rels, "git ls-files"
    found = sorted(
        str(p.relative_to(ctx.root)).replace("\\", "/")
        for p in ctx.root.rglob("package-lock.json")
        if "node_modules" not in p.parts
    )
    return found, "filesystem walk (git unavailable)"


def check_npm_lockfile_attestation(ctx: Ctx) -> CheckResult:
    """EVERY tracked npm lockfile must carry a sibling ``VERSION_LOCK.json`` that attests its hash.

    **A supply-chain attestation nobody verifies is decoration, and this one was also false.**
    `tools/visual-engine/SECURITY_POLICY.md` cites `npm_lockfile_sha256` as the control for its
    dependency-tampering threat row. Measured at `ba0294a`: the recorded value was
    `c49a31bee180…` and the lockfile hashed to `ff66cda9685f…` — it had never been true, in either
    direction, and no code compared them. Anyone re-deriving the pin concluded the lockfile was
    tampered with; anyone trusting the row concluded it was pinned. Both wrong.

    **The subject set is DERIVED, never named** (`P8-STRUCT09-DERIVE`). `OG-158` fixed the
    attestation for `tools/visual-engine/` by hardcoding that one path — while
    `git ls-files '*package-lock.json'` returned TWO tracked lockfiles. The unguarded sibling,
    `tools/mermaid-engine/package-lock.json`, feeds `tools/mermaid-engine/render.mjs`, which
    EXECUTES at build time (`BUILD-01` renders every doc-system document through it), and it had no
    attestation anywhere in the tree. The one plausible compensating control does not compensate:
    `tools/docgen/build_cache.py` hashes that lockfile as a CACHE-INVALIDATION fingerprint — it
    answers "did the renderer change since this build was cached?" and rebuilds on change. It never
    refuses. A gate that hardcodes one member of a set it does not enumerate rots the moment a
    second member appears, and this one already had.

    So the check enumerates the tracked lockfiles and requires each to be attested by a
    `VERSION_LOCK.json` NEXT TO IT. A new package directory therefore arrives already covered: add
    a lockfile and this check goes red until an attestation lands beside it — which is the point,
    and is what `tools/tests/test_health_guards.py` pins with a two-lockfile counter-example.

    Fails CLOSED on every unknown: no lockfiles found at all, a lockfile with no attestation file,
    an attestation with no `npm_lockfile_sha256`, or a hash that does not match. This is a security
    control, and "I could not check" is not "it is fine".
    """
    locks, how = _tracked_npm_lockfiles(ctx)
    if not locks:
        return _fail("STRUCT-09", Stage.STRUCTURE,
                     "no npm lockfile found — the pinned dependency set cannot be verified",
                     f"derived via {how}; this engine ships npm-installed renderers "
                     "(tools/visual-engine, tools/mermaid-engine) and a run that finds no lockfile "
                     "at all is a check measuring nothing, not a clean bill of health")
    problems: list[str] = []
    verified: list[str] = []
    for rel in locks:
        lock_path = ctx.root / rel
        attest_path = lock_path.parent / "VERSION_LOCK.json"
        if not lock_path.is_file():
            problems.append(f"{rel}: tracked but absent from the working tree")
            continue
        if not attest_path.is_file():
            # The REPO-RELATIVE path of the attestation, not `attest_path.parent.name` — for a
            # lockfile at the repository root that read out as the checkout directory's own name
            # ("repo/VERSION_LOCK.json" in a lab), which names no file anyone can create.
            want = PurePosixPath(rel).parent / "VERSION_LOCK.json"
            problems.append(
                f"{rel}: NO ATTESTATION — {want} does not exist, so this dependency set is "
                "pinned by nothing a gate reads. Create it with an `npm_lockfile_sha256` of "
                f"`shasum -a 256 {rel}`, read the lockfile diff first.")
            continue
        try:
            attested = json.loads(attest_path.read_text(encoding="utf-8")).get("npm_lockfile_sha256")
        except (OSError, ValueError) as exc:
            problems.append(f"{rel}: attestation unreadable ({type(exc).__name__}: {exc})")
            continue
        if not isinstance(attested, str) or not attested.strip():
            problems.append(f"{rel}: attestation declares no npm_lockfile_sha256")
            continue
        actual = hashlib.sha256(lock_path.read_bytes()).hexdigest()
        if actual != attested:
            problems.append(
                f"{rel}: attested {attested[:16]}…, actual {actual[:16]}… — either the lockfile "
                "changed without the attestation being re-derived, or the dependency set was "
                "tampered with. Re-derive deliberately; do not copy the actual value in without "
                "reading the lockfile diff.")
            continue
        verified.append(f"{rel}={actual[:12]}…")
    if problems:
        return _fail("STRUCT-09", Stage.STRUCTURE,
                     f"{len(problems)} of {len(locks)} tracked npm lockfile(s) are not attested",
                     "; ".join(problems), problems)
    return _ok("STRUCT-09", Stage.STRUCTURE,
               f"all {len(verified)} tracked npm lockfile(s) match their attestation",
               f"derived via {how}: " + ", ".join(verified))


# The fixture `build-deps.mjs` is measured against. A graph builder's failure mode is not a crash —
# it is a clean exit over an empty result, so the probe needs a tree whose correct answer is
# non-empty and KNOWN: two importing modules, one edge, both spellings of an internal import
# (absolute `src.core` and relative `..core`) so a regression in either resolver shows up.
_GRAPHIFY_FIXTURE: tuple[tuple[str, str], ...] = (
    ("src/__init__.py", ""),
    ("src/core.py", "VALUE = 1\n"),
    ("src/pkg/__init__.py", ""),
    ("src/pkg/leaf.py", "from src.core import VALUE\nfrom ..core import VALUE as V2\n"),
)


def _graph_size(path: Path) -> tuple[int, int] | None:
    """``(nodes, links)`` from a node-link JSON graph, or ``None`` if it is unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    nodes, links = data.get("nodes"), data.get("links")
    if not isinstance(nodes, list) or not isinstance(links, list):
        return None
    return len(nodes), len(links)


def check_graphify_builders(ctx: Ctx) -> CheckResult:
    """SUITE-07 — the graphify builders must emit a NON-EMPTY graph, not merely exit 0.

    `tools/graphify/` is ten executable files with, before this check, no test, no health check and
    no lane in any verification pass: `build-coverage.mjs`, `build-deps.mjs`, `build-pipeline.mjs`,
    `build.mjs` and `open.sh` were named nowhere in `OPEN_GATES.md`, `VERIFICATION_LOG.md` or
    `LESSONS.md`, and `grep -n graphify tools/health/checks.py` returned nothing.

    **Exit 0 is not the answer here.** Measured at HEAD, `build-deps.mjs` printed
    `"[/deps] 0 .py files · 0 modules · 0 internal import edges"` and exited 0 on a repository with
    ~70 tracked `.py` files, writing `graphify-out/deps.json` with `nodes: 0, links: 0`;
    `build-coverage.mjs` printed `"0 detectors · 0 SWC classes · 0 tags"`. A builder that succeeds
    vacuously is the same defect class as a check that passes vacuously — the whole reason this
    package exists — and no exit code distinguishes it from a working run.

    So the probe asserts SIZE, and it asserts it against a fixture whose correct answer is known:
    a throwaway host root containing four `.py` files, two of which import each other. Two nodes,
    one edge. A regression in the module mapper or either import resolver takes it to zero and this
    check goes red; `tools/tests/test_health_guards.py` holds that counter-example.

    **Why a fixture rather than this repository.** `graphify.srcRoot` defaults to `src`, which this
    engine does not have — `engine.config.json` says so itself: these four builders are *"WORKED
    EXAMPLES tuned to one Python project's layout"*. Re-pointing `ENGINE_GRAPHIFY_SRC_ROOT` at
    `tools/` would make this check's answer depend on how well the builder's import resolver
    happens to handle a namespace it was not written for — a moving target that belongs to the
    builder's own tests, not to a gate. The fixture instead measures what the builder claims to do
    on the layout it claims to support, and its correct answer (two nodes, one edge) is fixed, so
    the only thing that can move it is a regression.

    `build.mjs` — the generic structure mapper, which needs none of that configuration — is run
    against the real tree under ``--full``: it is the one builder whose correct answer for THIS
    repository is non-empty (195 nodes / 194 links, 0.65 s measured). It needs the external
    `codemap` binary, so its absence is a SKIP with the cause, never a silent pass.
    """
    node = shutil.which("node")
    if node is None:
        return _skip("SUITE-07", Stage.SUITES, "graphify builders not run — node is not on PATH",
                     "the builders are ES modules run by node")
    deps_builder = ctx.root / "tools" / "graphify" / "build-deps.mjs"
    if not deps_builder.is_file():
        return _fail("SUITE-07", Stage.SUITES, "tools/graphify/build-deps.mjs is missing",
                     f"{deps_builder} absent — the connection-graph builder this check certifies "
                     "is not in the tree")
    findings: list[str] = []
    evidence: list[str] = []
    with tempfile.TemporaryDirectory(prefix="engine-graphify-probe-") as td:
        host = Path(td)
        for rel, body in _GRAPHIFY_FIXTURE:
            target = host / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        env = dict(os.environ)
        # Pin BOTH: the host root the builder analyses and the source subtree inside it. Leaving
        # either to discovery would let the probe silently measure this repository instead of the
        # fixture — a probe that reads the wrong artifact is the failure this engine keeps finding.
        env["ENGINE_HOST_ROOT"] = str(host)
        env["ENGINE_GRAPHIFY_SRC_ROOT"] = "src"
        code, out = _run([node, str(deps_builder)], ctx.root, timeout=120, env=env)
        if code != 0:
            return _fail("SUITE-07", Stage.SUITES,
                         f"build-deps.mjs failed on a known-good fixture (exit {code})", out[-400:])
        size = _graph_size(host / "graphify-out" / "deps.json")
        if size is None:
            findings.append("build-deps.mjs exited 0 but wrote no readable deps.json")
        else:
            nodes, links = size
            evidence.append(f"build-deps fixture: {nodes} node(s), {links} link(s)")
            if nodes < 2 or links < 1:
                findings.append(
                    f"build-deps.mjs exited 0 on a fixture with two importing modules and emitted "
                    f"{nodes} node(s)/{links} link(s) — a vacuous graph reported as success")
    if ctx.full:
        structure_builder = ctx.root / "tools" / "graphify" / "build.mjs"
        code, out = _run([node, str(structure_builder)], ctx.root, timeout=300)
        if code != 0:
            if "codemap" in out:
                evidence.append("build.mjs skipped: codemap not installed (" + out[-120:] + ")")
            else:
                findings.append(f"build.mjs failed on the real tree (exit {code}): {out[-200:]}")
        else:
            size = _graph_size(ctx.root / "graphify-out" / "graph.json")
            if size is None:
                findings.append("build.mjs exited 0 but wrote no readable graph.json")
            else:
                nodes, links = size
                evidence.append(f"build.mjs on this tree: {nodes} node(s), {links} link(s)")
                if nodes < 2 or links < 1:
                    findings.append(
                        f"build.mjs exited 0 over this repository and emitted {nodes} node(s)/"
                        f"{links} link(s)")
    if findings:
        return _fail("SUITE-07", Stage.SUITES,
                     f"{len(findings)} graphify builder(s) succeeded vacuously",
                     "; ".join(findings + evidence), findings)
    return _ok("SUITE-07", Stage.SUITES,
               f"graphify builders emit non-empty graphs ({len(evidence)} builder(s) measured)",
               "; ".join(evidence))


def check_depth_ratchet(ctx: Ctx) -> CheckResult:
    """CONS-12 — the depth ratchet must be level, measured against the REAL repository.

    **This check exists because the fix and the enforcement path were disjoint sets.** The ratchet's
    memory is the highest floor each container has ever been committed with, read from the spec's
    git history — and no gate ran the command that computes it. The only path from a git operation to
    the ratchet was pre-push → this module → `SUITE-05` → the retained probes, and those probes run
    inside a throwaway lab that `git init`s its own tree. Inside a lab there IS no prior history, so
    the probes structurally cannot see a loosening, and one of them is documented as "the positive
    control". A verifier lowered a floor, committed it, and watched every probe pass.

    So the ratchet is adjudicated here, against `ctx.root`, where the history is real.
    """
    from tools.blueprint.completeness import build as completeness_build
    from tools.blueprint.model import build_model

    try:
        model = build_model(ctx.root)
        report = completeness_build(ctx.root, model)
    except Exception as exc:  # noqa: BLE001 — a model that cannot build IS the finding
        return _fail("CONS-12", Stage.CONSISTENCY, "the system model could not be built",
                     f"{type(exc).__name__}: {exc}", [str(exc)])

    memory = str(report.get("ratchet_memory", ""))
    findings = list(report.get("floor_findings", []))
    if memory.startswith("UNAVAILABLE"):
        # An environment fact, not a fact about the artifact (`LESSONS.md` L-25) — but never a
        # silent pass: without memory the loosening direction cannot be adjudicated at all.
        return _skip("CONS-12", Stage.CONSISTENCY,
                     f"ratchet memory unavailable, so loosening cannot be detected: {memory}")
    if findings:
        return _fail("CONS-12", Stage.CONSISTENCY,
                     f"{len(findings)} depth-ratchet finding(s)", "; ".join(findings[:4]), findings)
    containers = len(model.get("containers", []))
    return _ok("CONS-12", Stage.CONSISTENCY,
               f"the depth ratchet is level across {containers} container(s) ({memory})")


_PLAN_COMPLETE_PROSE_RE = re.compile(
    r"\bPhases?\s+(\d+)\s*(?:[–—-]\s*(\d+))?\s+(?:is|are|was|were)\s+complete\b",
    re.IGNORECASE,
)


def check_phase_completion_markers(ctx: Ctx) -> CheckResult:
    """CONS-13 — the plan's prose and its phase rows must agree about which phases are finished.

    **This exists because the deferral guard went blind and nothing noticed for two phases.**
    ``cross_doc``'s rule-2 machinery refuses a `SCHEDULED (Phase N)` row whose phase the plan marks
    COMPLETE — *"a deferral to finished work is parked forever: the phase that was going to close it
    has already ended"* — and it decides "is N complete?" by looking for a marker **inside phase N's
    own table row**. Phases 1-3 carry one (``✅``, ``— DONE <sha>``). Phases 4, 5 and 6 shipped
    without one, because completion had migrated into the status paragraph at the top of the file.

    So the branch could not fire, and the guard reported clean while `OG-07` and `OG-63` — both
    deferred to Phase 4, both finished inside Phase 4 — sat in the `## Open` table for two further
    phases. That is a **false green**: the register over-reported open defects, and the one check
    written to catch exactly this said nothing. A convention that a gate depends on, and that
    nothing enforces, is a gate with an expiry date.

    The two statements are checked against each other, both ways, and the check **fails rather than
    passes when it cannot derive either side** — a vacuous pass here would rebuild the same
    blindness one layer up (`LESSONS.md` L-37).

    Bound, stated so a verifier can attack it: the prose side reads a fixed, small set of spellings
    (``Phase 4 is complete``, ``Phases 1-6 are complete``, en/em dash or hyphen). Rewording the
    status sentence past that vocabulary makes this check **fail loudly** with "no phase-completion
    claim found", never pass quietly. Failing closed is the whole point.
    """
    from tools.corpus_check.guards.cross_doc import marks_complete, phase_rows

    plan = ctx.root / "docs" / "plan" / "BUILD_PLAN.md"
    if not plan.is_file():
        return _fail("CONS-13", Stage.CONSISTENCY, "docs/plan/BUILD_PLAN.md is absent",
                     "the plan is what every SCHEDULED deferral is adjudicated against")
    text = plan.read_text(encoding="utf-8", errors="replace")

    # Table rows are the OTHER side of this comparison. Reading a completion word out of one would
    # make the two sources one source, and the check would agree with itself forever.
    prose: set[int] = set()
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            continue
        for lo, hi in _PLAN_COMPLETE_PROSE_RE.findall(line):
            start, end = int(lo), int(hi or lo)
            if start <= end and end - start < 100:
                prose.update(range(start, end + 1))

    rows = phase_rows(text)
    if not rows:
        return _fail("CONS-13", Stage.CONSISTENCY, "the plan carries no phase table",
                     "with no rows there is nothing to reconcile, and cross-doc's COMPLETE branch "
                     "has nothing to read either")
    if not prose:
        return _fail("CONS-13", Stage.CONSISTENCY, "no phase-completion claim found in the plan",
                     "the status prose is one of the two sources this reconciles; deriving nothing "
                     "from it would make every comparison below vacuous")

    marked = {int(n) for n, row in rows.items() if marks_complete(row)}
    numbered = {int(n) for n in rows}
    problems: list[str] = []

    for n in sorted(prose - marked):
        problems.append(
            f"the plan's prose says Phase {n} is complete, but its row carries no completion "
            f"marker — cross_doc cannot see it, so a SCHEDULED (Phase {n}) deferral would pass"
        )
    for n in sorted(marked - prose):
        problems.append(
            f"Phase {n}'s row is marked complete, but the plan's status prose does not say so"
        )
    for n in sorted(prose - numbered):
        problems.append(f"the prose claims Phase {n} is complete, but the plan has no row for it")
    if marked and marked != set(range(1, max(marked) + 1)):
        gaps = sorted(set(range(1, max(marked) + 1)) - marked)
        problems.append(
            f"the completed set {sorted(marked)} is not a contiguous prefix (missing "
            f"{gaps}) — a phased plan cannot finish a phase before the one it depends on"
        )

    if problems:
        return _fail("CONS-13", Stage.CONSISTENCY,
                     f"{len(problems)} phase-completion disagreement(s) between the plan's prose "
                     f"and its rows", problems[0], problems)
    return _ok("CONS-13", Stage.CONSISTENCY,
               f"the plan's prose and its rows agree that phase(s) {sorted(marked)} are complete "
               f"of {len(rows)} planned")


CHECKS: tuple[CheckFn, ...] = (
    # 1 — structure
    check_core_docs,
    check_locked_files_exist,
    check_prepush_hook_installed,
    check_precommit_hook_installed,
    check_confidential_vault_is_ignored,
    check_npm_lockfile_attestation,
    check_ci_cost_control,
    check_session_state_stamp,
    check_engine_config_parses,
    # 2 — rule layer
    check_hash_gate,
    check_contradictions_parse,
    check_impact_map,
    check_taxonomy_parses,
    check_manifest_parses,
    # 3 — consistency ("no part lies to another part")
    check_impact_prefixes_known,
    check_manifest_ids_known,
    check_rulebook_locked_table,
    check_governance_tables_are_whole,
    check_gate_token_coverage,
    check_project_version_matches_changelog,
    check_rulebook_citations_resolve,
    check_doc_paths_resolve,
    check_state_docs_facts,
    check_charter_counts,
    check_corpus_claims,
    # 4 — build
    check_sample_builds,
    check_cli_check_passes,
    check_no_degraded_mode,
    check_theme_build_matches_source,
    # 5 — suites
    check_project_index,
    check_visual_engine,
    check_mermaid_engine,
    check_lint_baseline,
    check_python_tests,
    check_moat_attacks,
    check_graphify_builders,
    check_depth_ratchet,
    check_phase_completion_markers,
)
