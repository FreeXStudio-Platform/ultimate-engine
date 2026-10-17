"""The doc-system gate CLI + rulebook hash-gate (VERSION.json's ``gate``).

Implements the VERSION.json hash-gate spec: the locked rule files (``rulebook_files``) are
concatenated and SHA-256'd; a mismatch against the recorded ``rulebook_sha256`` — without a
version bump + CHG-700 entry + ADR — means someone edited a locked rule without following
RULEBOOK L9 ("Any change to a locked rule MUST bump VERSION.json, append a CHG-700 entry, and
record an ADR"). The gate cannot verify the CHG-700/ADR half of that (that's a human process,
checked by review); what it CAN mechanically verify is: has the file set's content changed
since the last recorded hash, and if so, was the version bumped to reflect it.

Fail-closed throughout: any missing rulebook file raises to a blocking finding (never
silently skipped) — a locked rule file that vanished from disk is itself a governance defect.

CLI:
    python -m tools.docgen.validate_doc_system [--strict] [--write-hash] [--rules-dir DIR]
        [--version-json PATH]

Exit code is non-zero whenever any BLOCKING finding exists (mirroring ``GateResult.blocked``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from tools.docgen import adjudication, engine_config
from tools.docgen.models import Finding, GateResult, Severity

# Resolved via engine_config (env var > engine.config.json > auto-detected git root > this
# engine's own directory) — see ../../CONFIGURATION.md. Both remain overridable per-call via
# the --rules-dir/--version-json CLI flags below; these are just the defaults those flags fall
# back to when not passed explicitly.
_REPO_ROOT = engine_config.host_root()
_DEFAULT_RULES_DIR = engine_config.doc_system_dir()
_DEFAULT_VERSION_JSON = engine_config.version_json_path()
_PENDING_SENTINEL_PREFIX = "PENDING"


def compute_hash(files: list[Path]) -> str:
    """SHA-256 of the concatenated contents of ``files``, in the given order.

    Fail mode: FAIL-CLOSED — raises ``FileNotFoundError`` (propagated, never swallowed) if any
    file is missing. A missing locked-rule file must never be silently treated as "no content to
    hash"; the caller (``check``) converts this into a blocking ``Finding`` rather than letting an
    uncaught traceback stand in for a gate result. Timestamps are never part of the hashed
    content — callers must pass file paths whose content excludes any timestamp/`created_at`
    fields (per ENGINE_PLAN §4b's determinism note) for the hash to be stable across runs that
    don't actually change rule meaning.
    """
    digest = hashlib.sha256()
    for file_path in files:
        if not file_path.is_file():
            raise FileNotFoundError(f"locked rulebook file missing: {file_path}")
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


# --------------------------------------------------------------------------------------
# `P8-068` — the re-baseline half of RULEBOOK L9.
#
# L9 says a locked-rule edit MUST bump VERSION.json, append a CHG-700 entry and record an ADR.
# The gate's own docstring used to wave all three off as "a human/process check", and the
# sanctioned two-step then accepted ANY rewrite of the locked set for free: drop
# ``tools/hooks/pre-push`` from ``rulebook_files``, set the sentinel, run ``--write-hash`` — three
# line-edits, ``version`` still 1.2.9, no CHANGELOG entry, and every gate green. That is the moat's
# own executable leaving the lock with nothing recording that it happened.
#
# One of the three IS mechanical, and it is the one the other two hang off: **did the version
# change when the locked content changed?** HEAD is the reference point — the previous VERSION.json
# and the previous bytes of every locked file are both in it — so no new field is needed anywhere
# (VERSION.json's schema is not this module's to extend).
#
# What this still cannot see, stated plainly instead of as a wave: whether a CHG-700 entry or an
# ADR was actually written, and a re-baseline whose PENDING state was itself committed first
# (HEAD then already contains the mutation, so there is nothing left to compare against). Those
# remain review's job. "I checked the half I can" beats "this is all human process".
# --------------------------------------------------------------------------------------
def _git_output(repo_root: Path, args: list[str]) -> bytes | None:
    """Run a read-only git command in ``repo_root``; None when git is absent or the command fails."""
    git_bin = engine_config.tool_path("git")
    if git_bin is None:
        return None
    try:
        proc = subprocess.run(
            [git_bin, "-C", str(repo_root), *args],
            capture_output=True, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _version_tuple(value: object) -> tuple[int, ...] | None:
    if not isinstance(value, str):
        return None
    parts = value.strip().split(".")
    if not all(part.isdigit() for part in parts) or not parts:
        return None
    return tuple(int(part) for part in parts)


def _is_bumped(previous: object, current: object) -> bool:
    """True when ``current`` is a real advance on ``previous``.

    Dotted-numeric versions must strictly INCREASE (so a re-baseline cannot be waved through by
    moving the version backwards, which is a change but not a bump). Anything this cannot parse
    falls back to plain inequality — a non-semver scheme is still declaring a new version — and a
    missing previous version means there is nothing to advance from, so any current value counts.
    """
    if previous is None:
        return True
    prev_tuple, cur_tuple = _version_tuple(previous), _version_tuple(current)
    if prev_tuple is not None and cur_tuple is not None:
        return cur_tuple > prev_tuple
    return current != previous


def _refuse_unbumped_rebaseline(
    version_json_path: Path,
    version_data: dict[str, object],
    computed: str,
    *,
    repo_root: Path,
) -> Finding | None:
    """Blocking ``Finding`` when ``--write-hash`` would re-baseline changed rules with no bump.

    Returns None when the write is legitimate: the locked set is byte-identical to HEAD's (a
    genuine first-run baseline, or a re-run of one), or ``version`` advanced past HEAD's.
    Fail-closed on "cannot tell": no git, no HEAD, or a VERSION.json outside ``repo_root`` all
    BLOCK, because an unverifiable re-baseline is exactly the state this check exists to refuse.
    """
    try:
        rel_version_json = version_json_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return Finding(
            gate="hash_gate",
            message=(
                f"--write-hash refused: {version_json_path} is outside the repo root {repo_root}, "
                "so the RULEBOOK L9 version bump cannot be verified against HEAD."
            ),
            severity=Severity.CRIT, blocking=True, evidence=str(version_json_path),
        )

    if _git_output(repo_root, ["rev-parse", "--verify", "HEAD"]) is None:
        return Finding(
            gate="hash_gate",
            message=(
                "--write-hash refused: no readable git HEAD in "
                f"{repo_root}, so this re-baseline cannot be compared against the previously "
                "recorded rule set and the RULEBOOK L9 version bump cannot be verified. Commit "
                "the current state first (or run the re-baseline inside the real repository)."
            ),
            severity=Severity.CRIT, blocking=True, evidence=str(repo_root),
        )

    head_blob = _git_output(repo_root, ["show", f"HEAD:{rel_version_json}"])
    if head_blob is None:
        return None  # never committed -> there is no previous baseline to bump away from

    try:
        head_data = json.loads(head_blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        head_data = None
    if not isinstance(head_data, dict):
        return Finding(
            gate="hash_gate",
            message=(
                f"--write-hash refused: HEAD:{rel_version_json} is not readable JSON, so the "
                "previously locked rule set cannot be recovered and the L9 version bump cannot "
                "be verified."
            ),
            severity=Severity.CRIT, blocking=True, evidence=rel_version_json,
        )

    head_files = head_data.get("rulebook_files")
    current_files = version_data.get("rulebook_files")
    changed = head_files != current_files
    if not changed and isinstance(head_files, list):
        digest = hashlib.sha256()
        for rel in head_files:
            blob = _git_output(repo_root, ["show", f"HEAD:{rel}"])
            if blob is None:
                changed = True
                break
            digest.update(blob)
        else:
            changed = digest.hexdigest() != computed

    if not changed:
        return None

    if _is_bumped(head_data.get("version"), version_data.get("version")):
        return None

    return Finding(
        gate="hash_gate",
        message=(
            "--write-hash refused: the locked rule set changed since HEAD but VERSION.json's "
            f"'version' is still {head_data.get('version')!r}. RULEBOOK L9 requires a locked-rule "
            "edit to bump VERSION.json (plus a CHG-700 entry and an ADR, which review checks). "
            "Bump 'version', then re-run --write-hash."
        ),
        severity=Severity.CRIT,
        blocking=True,
        evidence=f"HEAD version={head_data.get('version')!r} working version="
                 f"{version_data.get('version')!r} computed={computed}",
    )


def _resolve_rulebook_files(
    version_data: dict[str, object], *, repo_root: Path, rules_dir: Path
) -> list[Path]:
    """Resolve ``rulebook_files`` entries to absolute paths under an explicit, deterministic root.

    Unlike a "probe several candidate roots and pick whichever exists" strategy, resolution here
    is a single deterministic rule: each entry is a path relative to the real repo root (e.g.
    ``docs/design/doc-system/RULEBOOK.md``). We resolve against ``repo_root`` directly. A probing
    strategy is deliberately avoided — it is unsound whenever a test fixture's relative path
    happens to also exist under the real repo root (it does, for every real rulebook filename),
    which would silently resolve a test's file list to the REAL project's files instead of the
    fixture's. ``rules_dir`` (conventionally ``docs/design/doc-system``) is accepted and used as a
    secondary anchor ONLY when an entry's repo-root-relative resolution does not exist AND the
    entry's basename can be found directly under ``rules_dir`` (this covers a caller passing a
    non-default ``rules_dir`` while ``rulebook_files`` still lists the default relative paths) —
    but the repo-root-relative path always wins when it exists, so this can never silently swap in
    the wrong file when both roots happen to contain a same-named file.

    Fail mode: a malformed/missing ``rulebook_files`` key returns an empty list; the caller
    treats an empty list as a blocking configuration defect (fail-closed), never as "nothing to
    check."
    """
    raw_files = version_data.get("rulebook_files")
    if not isinstance(raw_files, list):
        return []
    rel_paths = [str(rel) for rel in raw_files]

    resolved: list[Path] = []
    for rel in rel_paths:
        # An ABSOLUTE entry would make `repo_root / rel` evaluate to `rel` itself — pathlib
        # discards the left operand — so a `rulebook_files` entry pointing anywhere on the
        # filesystem would silently be hashed as though it were part of this repo. Same for any
        # entry that climbs out with `..`. Neither is ever legitimate, so both resolve to a path
        # that cannot exist, and the caller's existing fail-closed "listed file missing" finding
        # fires with the offending entry named (OG-01).
        candidate = Path(rel)
        if candidate.is_absolute() or ".." in candidate.parts:
            resolved.append(repo_root / "<<REFUSED-NON-RELATIVE-rulebook_files-ENTRY>>" / rel.lstrip("/"))
            continue
        primary = repo_root / rel
        if primary.is_file():
            resolved.append(primary)
            continue
        secondary = rules_dir / Path(rel).name
        resolved.append(secondary)
    return resolved


def _load_version_json(version_json_path: Path) -> tuple[dict[str, object] | None, Finding | None]:
    """Load and parse VERSION.json.

    Fail mode: FAIL-CLOSED. A missing or malformed VERSION.json returns ``(None, Finding)`` with
    ``Finding.blocking=True`` — the hash-gate has nothing to check against and must not report a
    pass.
    """
    if not version_json_path.is_file():
        return None, Finding(
            gate="hash_gate",
            message=f"VERSION.json not found at {version_json_path}",
            severity=Severity.CRIT,
            blocking=True,
            evidence=str(version_json_path),
        )
    try:
        data = json.loads(version_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, Finding(
            gate="hash_gate",
            message=f"VERSION.json is not valid JSON: {exc}",
            severity=Severity.CRIT,
            blocking=True,
            evidence=str(version_json_path),
        )
    if not isinstance(data, dict):
        return None, Finding(
            gate="hash_gate",
            message="VERSION.json top level is not a JSON object",
            severity=Severity.CRIT,
            blocking=True,
            evidence=str(version_json_path),
        )
    return data, None


def _derive_repo_root(rules_dir: Path) -> Path:
    """Derive the repo root to resolve ``rulebook_files`` against, from ``rules_dir``.

    When ``rules_dir`` IS the real ``docs/design/doc-system`` directory (the default), the real
    ``_REPO_ROOT`` is returned directly — no path-math involved, so the production path is exact.
    Otherwise ``rules_dir`` is treated as an isolated fixture's own ``docs/design/doc-system``
    equivalent, and its 3rd-level parent (mirroring that same nesting depth) is returned as the
    fixture's repo root; if the fixture doesn't have 3 parents (e.g. a flat temp dir used directly
    as ``rules_dir``), ``rules_dir`` itself is used as the root instead.
    """
    resolved_rules_dir = rules_dir.resolve()
    if resolved_rules_dir == _DEFAULT_RULES_DIR.resolve():
        return _REPO_ROOT
    parents = resolved_rules_dir.parents
    if len(parents) >= 3:
        return parents[2]
    return resolved_rules_dir


def consult_governance(
    result: GateResult,
    *,
    change_type: str | None = None,
    contradiction_path: Path | None = None,
    impact_map_path: Path | None = None,
) -> GateResult:
    """Actively consult the L10/L11 governance matrices and fold their advice into ``result``.

    This is the active-adjudication upgrade (ENGINE_PLAN §4b's deferred item): the gate no longer
    merely relies on the matrices existing — it READS them.

    * L11 (``CONTRADICTION.md``): every blocking finding in ``result`` gets its documented
      tie-breaker resolution attached as an advisory INFO finding (via
      ``adjudication.annotate_with_contradictions``).
    * L10 (``update_impact_map.json``): when ``change_type`` is given, the map is consulted and
      its dependent-doc list + public-sanitization rule are appended as advisory findings (via
      ``adjudication.compute_change_impact``).

    Purely additive and fail-open — every appended finding is non-blocking, so ``result.blocked``
    is unchanged; a missing/unreadable matrix leaves ``result`` untouched (the consultation logs a
    WARNING rather than faking a pass). Returns a NEW ``GateResult`` (does not mutate the input).
    """
    findings = adjudication.annotate_with_contradictions(
        result.findings, contradiction_path=contradiction_path
    )
    if change_type is not None:
        impact = adjudication.compute_change_impact(
            change_type, impact_map_path=impact_map_path
        )
        findings = [*findings, *impact.findings]
    return GateResult(gate=result.gate, findings=findings)


def check(
    rules_dir: Path,
    *,
    strict: bool = False,
    version_json_path: Path | None = None,
    write_hash: bool = False,
) -> GateResult:
    """Run the hash-gate: compare the locked rulebook file set's hash to the recorded one.

    Behavior:
        - Loads ``version_json_path`` (default ``docs/design/doc-system/VERSION.json``).
        - Resolves ``rulebook_files`` to absolute paths under the repo root.
        - FAIL-CLOSED if VERSION.json is missing/malformed, if ``rulebook_files`` is empty/absent,
          or if ANY listed file is missing from disk (``compute_hash`` raises; caught here and
          turned into a blocking Finding, never a silent pass).
        - If the recorded ``rulebook_sha256`` starts with the ``PENDING`` sentinel (as documented
          in VERSION.json), this is the FIRST RUN: the computed hash is accepted and, when
          ``write_hash`` is True, written back into VERSION.json's ``rulebook_sha256`` field
          (this is the one case where the gate mutates its own input, matching ENGINE_PLAN's
          spec: "if PENDING, WRITE the computed hash back on this first run and pass").
        - ``--write-hash`` additionally REFUSES a re-baseline whose locked content changed since
          HEAD while ``VERSION.json``'s ``version`` did not advance (`P8-068`,
          ``_refuse_unbumped_rebaseline``) — the mechanical third of RULEBOOK L9. The CHG-700
          entry and the ADR remain review's job, and so does a re-baseline whose PENDING state was
          committed before ``--write-hash`` ran; those two carve-outs are named here rather than
          summarised as "L9 is a human process", which is what let a locked file leave the set in
          three line-edits with every gate green.
        - Otherwise, a hash mismatch is a BLOCKING finding — a locked rule changed without a
          recorded version bump. (This mechanical check catches the "content changed silently"
          half.)
        - ``rules_dir`` is the deterministic anchor for resolving ``rulebook_files`` (see
          ``_resolve_rulebook_files``): when ``rules_dir`` equals the default
          ``docs/design/doc-system`` under the real repo, resolution uses the real repo root;
          otherwise (an isolated test fixture) the repo root is derived from ``rules_dir`` itself
          (its 3rd-level parent, mirroring the real ``docs/design/doc-system`` nesting depth, or
          ``rules_dir`` directly if the fixture doesn't have that much nesting), so a fixture's
          files are never confused with the real project's same-named files.
        - ``strict`` currently has no additional effect for the hash-gate itself (findings here
          are already unconditionally blocking — a rulebook drift is never merely advisory), but
          is accepted uniformly with ``export_sanitizer.run_gates(..., strict=...)`` for a
          consistent CLI story (``--strict`` is one flag that tightens every gate it can).
    """
    del (
        strict
    )  # accepted for CLI/API symmetry; hash-gate findings are already unconditionally blocking.
    resolved_version_json = version_json_path or _DEFAULT_VERSION_JSON

    version_data, load_finding = _load_version_json(resolved_version_json)
    if load_finding is not None or version_data is None:
        findings = [load_finding] if load_finding is not None else []
        return GateResult(gate="hash_gate", findings=findings)

    repo_root = _derive_repo_root(rules_dir)
    rulebook_files = _resolve_rulebook_files(version_data, repo_root=repo_root, rules_dir=rules_dir)
    if not rulebook_files:
        return GateResult(
            gate="hash_gate",
            findings=[
                Finding(
                    gate="hash_gate",
                    message=(
                        "VERSION.json has no (or a malformed) 'rulebook_files' list — "
                        "failing closed (evidence root: "
                        f"{rules_dir})"
                    ),
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=str(resolved_version_json),
                )
            ],
        )

    try:
        computed = compute_hash(rulebook_files)
    except FileNotFoundError as exc:
        return GateResult(
            gate="hash_gate",
            findings=[
                Finding(
                    gate="hash_gate",
                    message=f"locked rulebook file set incomplete: {exc}",
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=str(exc),
                )
            ],
        )

    recorded = version_data.get("rulebook_sha256")
    recorded_str = recorded if isinstance(recorded, str) else ""

    if recorded_str.strip().upper().startswith(_PENDING_SENTINEL_PREFIX):
        if write_hash:
            # The SANCTIONED half of the two-step re-baseline: the operator has deliberately set the
            # sentinel and is now asking for the hash to be written. This is the only path that may
            # accept a PENDING and report success — and it is sanctioned only when the L9 version
            # bump that must accompany a locked-rule change is actually there (`P8-068`).
            refusal = _refuse_unbumped_rebaseline(
                resolved_version_json, version_data, computed, repo_root=repo_root
            )
            if refusal is not None:
                return GateResult(gate="hash_gate", findings=[refusal])
            _write_hash_back(resolved_version_json, version_data, computed)
            return GateResult(
                gate="hash_gate",
                findings=[
                    Finding(
                        gate="hash_gate",
                        message=(
                            "rulebook_sha256 was PENDING — re-baselined to computed hash "
                            f"{computed[:12]}... and written back to VERSION.json"
                        ),
                        severity=Severity.INFO,
                        blocking=False,
                        evidence=computed,
                    )
                ],
            )
        # CHECKING with PENDING recorded means the rulebook is UNLOCKED RIGHT NOW: the gate has
        # nothing to compare against and is verifying nothing. This used to return a non-blocking
        # INFO, so `cli check` reported PASSED and `tools.health` printed
        # "[PASS] RULE-01 hash-gate holds — no undeclared rulebook drift" — a summary line that is
        # literally false — over a RULEBOOK.md rewritten to carry any rule at all. The evidence
        # string that would have betrayed it was visible only under --json, because the human
        # renderer prints evidence for non-PASS results only. An adversarial pass published an
        # attacker-authored rule this way with every gate green.
        #
        # VERSION.json is deliberately not a member of its own locked set, so nothing else can catch
        # this. Blocking is the only honest answer: "I could not verify" is not "verified".
        return GateResult(
            gate="hash_gate",
            findings=[
                Finding(
                    gate="hash_gate",
                    message=(
                        "rulebook_sha256 is PENDING — the locked rule set is UNLOCKED and this gate "
                        "verified nothing. Complete the two-step re-baseline: run "
                        "`python3 -m tools.docgen.validate_doc_system --write-hash`. "
                        f"(computed {computed[:12]}...)"
                    ),
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence=computed,
                )
            ],
        )

    if computed != recorded_str:
        return GateResult(
            gate="hash_gate",
            findings=[
                Finding(
                    gate="hash_gate",
                    message=(
                        "locked rulebook file set hash mismatch: a locked rule changed without "
                        "a recorded version bump (RULEBOOK L9 requires a VERSION.json bump + "
                        "CHG-700 entry + ADR on any locked-rule edit). "
                        f"computed={computed[:12]}... recorded={recorded_str[:12]}..."
                    ),
                    severity=Severity.HIGH,
                    blocking=True,
                    evidence=f"computed={computed} recorded={recorded_str}",
                )
            ],
        )

    return GateResult(
        gate="hash_gate",
        findings=[
            Finding(
                gate="hash_gate",
                message="rulebook hash matches VERSION.json — no undeclared drift",
                severity=Severity.INFO,
                blocking=False,
                evidence=computed[:12] + "...",
            )
        ],
    )


def _write_hash_back(
    version_json_path: Path, version_data: dict[str, object], computed_hash: str
) -> None:
    """Write the freshly computed hash into VERSION.json's ``rulebook_sha256`` field.

    Only called on the documented PENDING first-run path (``check(..., write_hash=True)``) or an
    explicit ``--write-hash`` CLI invocation. Preserves all other keys and formatting via a full
    read-modify-write of the JSON object; not used to silently paper over a real drift (a non-
    PENDING mismatch never calls this function from ``check()``).
    """
    updated = dict(version_data)
    updated["rulebook_sha256"] = computed_hash
    version_json_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.docgen.validate_doc_system",
        description=" doc-system gate: rulebook hash-gate + manifest consistency check.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Tighten advisory gates to blocking (mirrors export_sanitizer.run_gates strict mode).",
    )
    parser.add_argument(
        "--write-hash",
        action="store_true",
        help="On a PENDING first-run hash, write the computed hash back into VERSION.json.",
    )
    parser.add_argument(
        "--rules-dir",
        type=Path,
        default=_DEFAULT_RULES_DIR,
        help="Root directory of the doc-system rulebook (default: engine.config.json's "
        "docSystem.docSystemDir, normally docs/design/doc-system).",
    )
    parser.add_argument(
        "--version-json",
        type=Path,
        default=None,
        help="Path to VERSION.json (default: docs/design/doc-system/VERSION.json).",
    )
    parser.add_argument(
        "--change-type",
        type=str,
        default=None,
        help=(
            "Actively consult update_impact_map.json for this L10 change type "
            "(DETECTOR_CHANGE/VISUAL_STYLE_CHANGE/USER_POLICY_CHANGE/ARCHITECTURE_CHANGE/"
            "RULE_CHANGE) and print the dependent docs + sanitization rule (advisory)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 = pass, non-zero = blocking finding)."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    result = check(
        args.rules_dir,
        strict=args.strict,
        version_json_path=args.version_json,
        write_hash=args.write_hash,
    )

    # Active L10/L11 consultation (advisory, fail-open — never flips the exit code): attach the
    # governing CONTRADICTION.md tie-breakers and, if --change-type is given, the L10 blast-radius.
    result = consult_governance(result, change_type=args.change_type)

    for finding in result.findings:
        marker = "BLOCK" if finding.blocking else "info"
        print(
            f"[{marker}] ({finding.gate}) {finding.message}",
            file=sys.stderr if finding.blocking else sys.stdout,
        )

    if result.blocked:
        print("doc-system gate: FAILED", file=sys.stderr)
        return 1

    print("doc-system gate: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
