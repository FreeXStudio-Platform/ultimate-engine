<!-- title: NEXT SESSION -->
# Phase 7 — harden, stamp, and make the moat non-optional

**Written:** 2026-08-29 at the close of Phase 6. **Superseded 2026-08-30: Phase 7 is COMPLETE and the
build ended at `1.0.0`.** The brief below is kept as the record of how the phase was run; the next
session's starting point is `docs/plan/AFTER_1_0.md` (the operating loop, not a phase), and its state
is in `HANDOFF.md`. Read this file for what Phase 7 did, not for what to do next.

**Phase 7 was COMPLETE at `1.0.0`.** It ran the reverification that came due, delivered the
server-side moat (`OG-31`), re-stamped the package (`OG-09`), and reached the first non-zero
`verified` count as a consequence. The register (`OPEN_GATES.md`) carries no blocking row.

**This is the last phase, and it is different in kind from the six before it.** Those built things.
This one *proves* things, and the proving is the deliverable: a full reverification, a stamp that
references a real commit, and the one gate no client-side hook can provide.

> **What comes after this phase is `docs/plan/AFTER_1_0.md`** — the build ends at Phase 7 and only
> half the charter does. Read it if you are deciding whether something belongs *in* Phase 7: most
> things that feel worth doing belong in the operating loop instead, and that file says so with
> reasons.
>
> **Scope lives in `docs/plan/PHASE7_SCOPE.md`** — every deliverable at full width, the order they
> have to happen in, and the eleven things Phase 7 must **refuse** to do. Read it before planning.
> This file is the operating brief: how to start, the standing constraints, and what green looks
> like. Neither restates the other.

## What Phase 6 and its closeout left you

- **`python3 -m tools.blueprint completeness`** — `sketched`/`documented`/`verified` per node from
  evidence, the six-step lifecycle per governed document, and the depth ratchet's verdict. Exit 1
  when a container is below its floor **or** declares a floor with slack. Read the numbers from the
  command; they are derived, and any figure repeated here would be a second copy waiting to go
  stale.
- **`verified` is 0 across every node.** That is the number Phase 7 can actually move, and it is the
  honest measure of what "hardened" means here: a node reaches `verified` only when its owning
  document is governed **and** carries a stamp that still covers its body. `OG-207` records that
  this is structurally unattainable for most nodes today, and it is Phase 7's to decide.
- **The ratchet is level**, with its memory taken from the spec's whole git history and adjudicated
  by `CONS-12` against the real repository — because the retained probes run in a lab that `git
  init`s its own tree and structurally cannot see a loosening (`L-40`).
- **`CONS-13` is new**, and it is worth understanding before you touch the plan: it reconciles the
  plan's status prose against its phase-row completion markers. It exists because that convention
  lapsed after Phase 3, which blinded `cross_doc`'s deferral guard for two phases and left two
  finished rows sitting in `## Open` (`OG-210`, `L-38`). **If you mark Phase 7 complete, mark it in
  both places** — the row and the status paragraph — or `CONS-13` will stop you, which is the point.
- **`docs/process/AUTHORING_CONTRACT.md`** and **`skills/doc-lifecycle/SKILL.md`** — the six steps a
  governed document owes, and which gate owns each. Phase 7's stamp is step 6 of that contract, so
  read it before stamping anything.

## ▶ 0. Start from the map

```bash
cat blueprint/SYSTEM.md
cat blueprint/COMPLETENESS.md
```

The first says what exists and what guards it; the second says how far each part got. Then
`blueprint/SURFACES.md` for anything at the level of a flag, a check, a guard or a schema. Open only
what they point at.

## ▶ 1. Before touching anything

```bash
cd <your clone> && \
  (python3 -c 'import yaml' 2>/dev/null || python3 -m pip install --quiet --user PyYAML) && \
  bash tools/hooks/install.sh && \
  (cd tools/visual-engine && npm install --no-audit --no-fund) && \
  (cd tools/mermaid-engine && npm install --no-audit --no-fund) && \
  python3 -m tools.health --full
```

Every link is load-bearing, and `--full` turns a SKIP into a failure by design. **Never pipe a gate
into `tail` and then test the exit code** — that reads the pipe's status, and a failing gate looks
green.

## ▶ 2. Write the acceptance set FIRST

`RULES.md` Rule 5, and it matters most here. Phase 7's work is *verification*, which is precisely the
activity that does not converge without a finish line: a completeness critic's question — *what did
you never look at?* — can never return empty by construction.

Two things Phases 5 and 6 both paid for, worth having before you write yours:

- **Make each `-k` token select its whole group.** A line saying "selects at least one test" is
  satisfied by a token matching one probe of eleven.
- **Freeze the set and check it at the close.** Phases 5 and 6 both hashed theirs before writing code
  and proved at the end that it was byte-identical. An acceptance set edited to fit what was built
  is not an acceptance set.

## ▶ 3. The work

`BUILD_PLAN.md` row 7, at full width in `PHASE7_SCOPE.md`. The exit condition is the only one in the
plan that names a hostile act:

> All suites green, browser sweep clean, stamp references a real commit, **and a push with
> `--no-verify` carrying a planted secret is rejected by something that is not a local hook.**

**Do the reverification while the tree is still quiet** (`PHASE7_SCOPE.md` §3). It is read-only, it
is the biggest item, and every later edit invalidates the sha the verifiers were handed.

**On `OG-136` and the shared runner, before you plan any CI:** registering the VPS2 runner for this
repository is an **operator** action (`~/.claude/rules/ci-cost-control.md` §9.3), and §9.1 is the one
that bites — GitHub does not fail a job whose runner label nobody serves, it queues it forever as
`pending`, so a required context pointing at an unregistered runner blocks every merge silently.
**Additive first; required only on measured evidence.**

## ▶ 4. How to write, every time

```bash
python3 -m tools.draft check <path>
python3 -m tools.corpus_check
```

`draft check` reports the *difference* a candidate introduces, including findings that land on other
documents because yours moved a fact they state. It has now caught that three times across two
sessions — each new document moved the charter's tracked-document count, and the gate named the line
every time.

## ▶ 5. Standing constraints

1. **Fix the CLASS, not the instance** — and check for the consumer you have not thought of. Phase 5
   fixed a root in three consumers, was told a fourth existed, fixed that, and a verifier then found
   the **fifth inside the module that exported the fix**.
2. **After narrowing anything, attack its NEW edge.**
3. **Severity decides the pipeline.** LOW does not stop a phase.
4. **Derived work is committed**, and rebuilt **last** — every later edit restales it.
5. **Never run a git command that writes to undo your own edit.**
6. **A hash-locked file needs the two-step**: pending sentinel, then the write-hash flag. Never
   write-hash on a live mismatch.
7. **Secret-scan before every stage**, and read the exit code directly.
8. **Do not mutate the tree while verifiers run.** Hand each an explicit commit sha.
9. **Do not bypass the hooks** — not `core.hooksPath`, not git's own verification-bypass flag.
   Phase 7 is the phase that closes that hole; using it while closing it would be absurd.
10. **Do not tune a measurement in the phase that benefits from tuning it.** `OG-198` and `OG-204`
    are both open records of that rule being obeyed rather than argued about.
11. **A fix to derived output is not landed until the OUTPUT is re-read** (`L-39`). Grep the whole
    tree for the string being corrected before believing any count of how many copies there were.

## ▶ 6. What "done" looks like

- The acceptance set from step 2 passes, command by command, and is byte-identical to what was frozen.
- A push carrying a planted secret with `--no-verify` is **rejected by something that is not a local
  hook** — falsified, not asserted.
- `PROVENANCE.md` carries a stamp referencing a real commit, and `blueprint completeness` reports a
  non-zero `verified` count **as a consequence** — not as a target that was aimed at.
- `python3 -m tools.health --full` green · `corpus_check` clean · `blueprint verify` clean ·
  `blueprint completeness` exit 0.
- `CHANGELOG.md` carries a `1.0.0` entry; `PROJECT_VERSION` updated; `OPEN_GATES.md` current.
- The deep reverification has actually run — `OG-190`, `OG-203` and `OG-209` closed by independent
  attack, not by assertion. **This is the phase where that debt comes due.**
- Every row `PHASE7_SCOPE.md` §2 names is closed or re-dispositioned with reasoning. **Nothing rolls
  forward: there is no Phase 8 to park it against.**
- Everything committed and pushed with the hooks active and the push verified against `origin`.
