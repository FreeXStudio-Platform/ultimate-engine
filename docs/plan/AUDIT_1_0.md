<!-- title: AUDIT 1.0 -->
# The 1.0.0 full-system audit — acceptance set, frozen before the work

**Status:** PROCESS — the acceptance set for the one commissioned post-1.0 audit pass. Written and
committed **before any audit work ran**, per `docs/process/RULES.md` Rule 5: a measure fixed after
seeing the thing measured is not a measure. The commissioning record is the operator paragraph in
`docs/process/SESSION_STATE.md` (2026-08-30); the procedure is `docs/process/DEEP_VERIFICATION_PASS.md`
run in the `docs/plan/AFTER_1_0.md` Stream-C shape; the exit hands off to Stream B
(`docs/plan/FIELD_TRIAL.md`). **This is not a phase and does not reopen the build** — there is no
Phase 8, and no row may be dispositioned `SCHEDULED` against this file.

**Freeze protocol.** This file's acceptance section is hashed the moment it is committed and proven
byte-identical at the pass's close. The recipe, identical in shape to the one that produced Phase 7's
`db24fd1fab14150b`:

```bash
git show <freeze-commit>:docs/plan/AUDIT_1_0.md \
  | awk '/^## The acceptance set/,/^## The landing record/' | sed '$d' \
  | shasum -a 256 | cut -c1-16
```

The frozen hash is recorded in the `CHANGELOG.md` entry for this pass, **outside** this file, so
writing it down does not change the bytes it measures. The `## The landing record` section below the
acceptance set is the one part of this file the close may edit; the awk range excludes it.

Findings outside this list are recorded in `docs/process/OPEN_GATES.md`, not held against the pass
(`DEEP_VERIFICATION_PASS.md` §3.1). A step that cannot complete honestly reports `CANNOT_VERIFY`
with its cause named — a TIMEOUT under external machine load is a verdict to repeat in a quiet
window, never a pass and never a corpus defect (`OG-212`).

## The acceptance set — written before the work

**AC-1 — the health floor holds on a quiet machine.**

```bash
python3 -m tools.health --full
```

`HEALTHY`, exit `0`, zero failed and zero skipped, run to a completed verdict on a machine whose
1-minute load permits `SUITE-05` to finish inside its wall-clock budget.

**AC-2 — the corpus is clean over the tree as committed.** Every registered guard green.

```bash
python3 -m tools.corpus_check
```

Exit `0`, zero findings.

**AC-3 — the derived map matches a fresh build, the ratchet is level, and `verified` remains a
consequence.**

```bash
python3 -m tools.blueprint verify
python3 -m tools.blueprint completeness --check
python3 -m unittest discover -s tools/tests -t . -k verified_reachable
```

All three exit `0`; the `-k` token selects at least one test and every selected test passes. No
depth floor moves down in this pass, whatever today's measurement says.

**AC-4 — every content-certifying stamp body-matches at a real commit.**

```bash
python3 -m tools.corpus_check --guard stamps
```

Exit `0`, a non-zero `checked` count, drift declared by none.

**AC-5 — the retained counter-examples all pass, none skipped.**

```bash
python3 -m unittest discover -s tools/tests -t .
```

Exit `0`, zero failures, zero skips, over the full defined set.

**AC-6 — every retained moat attack is still refused.**

```bash
bash tools/tests/hook_attacks.sh
```

Exit `0`.

**AC-7 — the server-side moat is live and holds, verified on use.** The ruleset is read from the
server (`enforcement` active, a pull-request rule and a required `secret-scan` context on the
default branch, an EMPTY bypass list), and then the retained hostile push is run:

```bash
gh api repos/FreeXStudio-Platform/ultimate-engine/rulesets
bash tools/tests/moat_server_side.sh
```

The script exits `0` — the hostile `--no-verify` push is refused by the server, not by a local hook.
This is the one sanctioned use of the bypass flag (`HANDOFF.md` standing rule 17).

**AC-8 — the rendered gallery is measured clean in a real browser, both themes.** Build
`examples/capability-gallery.md`, walk every `<text>`/`<tspan>` in a real browser in light AND dark
themes, compare bounding boxes pairwise and against each element's own `<svg>` box
(`INTERPRETATION.md` Part 2 method). Zero overlaps, zero out-of-box text, and the measured element
count is recorded beside the zeros — it is `0`-of-what that makes a zero worth anything
(`docs/process/LESSONS.md` L-18).

**AC-9 — the Phase-7 close survives an independent re-attack.** Read-only verifier lanes, each
pinned to the merge state the close produced (`eceb78c` and its stamped ancestry), each handed the
CLAIM and never the diff, none below the session tier, covering at least: the `OG-234` gitlink
skip; the `OG-224`–`OG-233` fix waves; the A-5 `verified_reachable` probe's own faithfulness; the
stamp dance (body-match semantics and the drift-declaration path); the acceptance-freeze mechanics
(`db24fd1fab14150b` reproduced from the recorded freeze commit); and the merge topology (every
stamped commit, `96b90d8` included, reachable from `master`). Every lane returns a written verdict.
CRITICAL and HIGH findings are fixed red-first with a retained counter-example and re-verified by
the lane that found them; MEDIUM is fixed and falsified by the fixer; LOW is recorded. Findings
that are stated bounds get a register row, not a silent fix.

**AC-10 — the three product pillars each carry a finished-product verdict with cited evidence.**
Document creation (registered artifacts resolve and render; gates carry retained red-first cases;
`cli check` clean on governed documents; export sanitizer proven; the gallery sweep green both
themes). The blueprint system (build/verify/completeness/depth/gatekeepers/surfaces clean on the
live tree AND still failing correctly on the retained hostile labs; `system.mmd` and `system.d2`
render; ELK layout stable). The graphing layer (`SUITE-01`, `SUITE-02`, `BUILD-04`, `SUITE-07`
green, plus one real-browser render of a representative artifact per engine). Each pillar ends
FINISHED with evidence, or the gap is filed — small gaps fixed in-pass, large ones registered with
an owner and a trigger.

**AC-11 — calibration is examined against earned reality, and ratchets only tighten.** Every pinned
ceiling and floor the health checks carry is re-derived against what the tree now earns — the
lint and type ceilings, the counter-example floors, the moat-attack floor, the duration budgets —
and each is either ratcheted UP with the move documented, or left with the reason stated. Nothing
loosens. No measurement is tuned by the pass in a way the pass benefits from (`OG-207` discipline).

**AC-12 — the records close and the stamp dance ends the pass, in order.** `OPEN_GATES.md` current;
a `CHANGELOG.md` entry for this pass; `PROJECT_VERSION` bumped exactly once with the changelog
agreeing (`CONS-05`); `docs/process/SESSION_STATE.md` rewritten in place; stamps re-issued at the
real body commit; the blueprint rebuilt as the final content commit; this file's frozen hash proven
byte-identical by the recipe above; `corpus_check --guard stamps` green after the dance.

**AC-13 — the repository lands clean and the verdict is written.** Every landing through a pull
request merged with a merge commit; every audit branch deleted local and origin; `git status`
clean and level with `origin/master`; zero stashes, one worktree, nothing untracked. The
`CHANGELOG.md` entry ends with a written GO / NO-GO for the Stream-B field trial: the
`FIELD_TRIAL.md` preconditions checked (§2 the three roles, §3 the subject-project rules, §7 the
blind-operator task statement), the paired design confirmed runnable, and anything blocking named
as a register row. GO means the next session is the trial itself.

### Round declaration — bounded before dispatch (`DEEP_VERIFICATION_PASS.md` §3.3)

- **Round 1:** the AC-9 verifier lanes plus the AC-10 pillar lanes, dispatched read-only against a
  pinned commit.
- **Round 2:** fixes for round-1 CRITICAL/HIGH findings return to the lane that found them; MEDIUM
  is falsified by the fixer; LOW is recorded.
- **Round 3 (contingent):** runs only if round 2 refutes a fix; it re-attacks the fix-of-the-fix
  and is the last round.
- **One completeness critic** runs after round 1, scoped to the acceptance set — what it finds
  outside the set becomes register rows, not pass work.
- **Stop rule:** convergence (a round returning no CRITICAL/HIGH) or the round bound above,
  whichever comes first — never fatigue, never "stopped finding things".

## The landing record

Completed at the close, outside the frozen range. The freeze commit, the reproduced hash, and the
close-out proof live in the `CHANGELOG.md` entry for this pass; this section exists so the awk
range above has a terminator that is present from the freeze commit onward.
