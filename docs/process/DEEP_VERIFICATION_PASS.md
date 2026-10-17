<!-- title: DEEP VERIFICATION PASS -->
# The Deep Verification Pass — standing end-of-phase ritual

**Status:** PROCESS — normative. This is a law file for *how work ends*, not a suggestion file.
**Established:** 2026-08-20 by operator directive, at the close of Phase 1.
**Cached deliberately:** the operator asked that this never need re-explaining. **Every phase ends
with this pass. It is not optional and it is not requested — it is assumed.**

Read with `docs/framework/DOC_WRITING_DOCTRINE.md` (the *method*) and `docs/plan/BUILD_PLAN.md`
(the *work*). This file is the *gate between phases*.

---

## 0. The shape of a phase

```
   implement  →  FIRST REPORT  →  DEEP VERIFICATION PASS  →  fix what it finds  →  close & stamp
                                  ▲                                                      │
                                  └──── never skipped, never self-run ───────────────────┘
```

A phase is **not** complete at the first report. The first report is a *claim*. The deep pass is
what converts a claim into a fact.

---

## 1. The separation-of-duties law (the one that must never bend)

> **Whoever created, fixed, or found the work MUST NOT be the one who verifies it.**

- The implementer may **orchestrate** the pass and **synthesise** its results. That is not a conflict.
- The implementer may **never** issue the green light on their own work.
- A verifier must be a **fresh agent** that did not participate in the implementation and does not
  inherit the implementer's reasoning. It re-derives from the artifacts.
- **Verify the thing, not the report.** A verifier that reads the report and agrees has done nothing.
  It must run the command, read the file, recompute the hash.
- **Absence of a verifier is a red light, not a green one.** Unverified never silently becomes verified.

Why this is absolute: a model checking its own output converges on its own blind spots. It goes
quiet long before it goes correct (doctrine §4).

---

## 2. The pass, in order

Each step produces written findings. Nothing is held in memory.

### Step 1 — Recover the prior state
Read the previous session's `HANDOFF.md`, the phase's section of `BUILD_PLAN.md`, `CHANGELOG.md`,
and `docs/process/OPEN_GATES.md`. **Never work from memory or from chat context** — a new session
has none of it.

### Step 2 — Re-prove the baseline
Run every suite the engine ships, in the documented order, and record real numbers. A phase that
broke the baseline is not done, whatever else it achieved.

**Load-bearing ordering:** `npm test` **before** `npm run simulate` — `simulate` rewrites the
goldens `npm test` compares against. Reversing them silently re-baselines drift.

### Step 3 — Independent verification (fan out)
Dispatch fresh verifier agents, one per dimension, each with the ground rules from §1. Minimum set:

| Verifier | Proves |
|---|---|
| Claim/symbol truth | Every symbol, path, count and enforcement site cited in prose resolves against real source |
| Gates actually fire | Each gate **falsified on purpose**, shown red, then restored to green |
| Baseline regression | Every suite still green; no golden drift beyond documented noise |
| Lint + types | Zero **new** errors vs. the pre-phase commit (measure the baseline, don't assume it) |
| Data-file contracts | Declarative files are *parsed and consulted*, not merely present |
| Cross-document truth | No file contradicts another; every cross-reference resolves |

### Step 4 — Design analysis (fan out)
| Analyzer | Answers |
|---|---|
| Modularity | What must change to add a law / doc type / gate / renderer / change type? Is anything data-in-code? |
| Rules preserved | Are all prior decisions, standing rules, phases and risks still present, locked, and scheduled? |
| Hygiene | Junk, orphans, stale path references, dead branches, uncommitted work |
| Gatekeeper + health | What guards exist, in what order, fail-open or fail-closed, and what is missing |

### Step 5 — Completeness critic
One final agent whose only job is *what did everyone miss, and what did they get wrong*. It
resolves contradictions between reports by checking the artifact itself, and spot-refutes the most
load-bearing confirmations. **What it finds becomes work, not commentary.**

### Step 6 — Triage into a written list
Every finding lands in `docs/process/OPEN_GATES.md` with a severity and one of **three**
dispositions, defined normatively in that file under **THE PHASE GATE**:

| Disposition | Meaning |
|---|---|
| `BLOCKS_PHASE_N` | A real, open defect. **The next phase may not start until it is closed.** N is the literal next phase number. |
| `SCHEDULED (Phase N)` | Valid **only** if closing it is Phase N's declared main work, and Phase N's `BUILD_PLAN.md` row says so. |
| `NOT_A_DEFECT` | Examined and found not to be one, carrying reasoning a future verifier can attack. |

> **Corrected 2026-08-21.** This table previously mandated `MUST_FIX_NOW` / `SHOULD_FIX` /
> `NICE_TO_HAVE` / `NEXT_SESSION` — a vocabulary `OPEN_GATES.md` had already retired, because 19 of
> 26 rows were parked under those four labels with no forcing event. This file is **hash-locked**,
> so the L9 gate saw nothing wrong: the bytes agreed with themselves. **A hash gate proves a file
> has not changed; it cannot prove the file is right.** Cross-file agreement is `CONS-03`'s job and
> the deep pass's job, not L9's.

**The bar for adding anything: must-have gets built; nice-to-have gets built only when it earns its
weight.** We do not add everything we can think of.

### Step 7 — Fix, re-verify, record
Fix every `BLOCKS_PHASE_N` finding. **Re-run the verifier that found it** — a fix is not done because the
fixer says so. Record each in `CHANGELOG.md` with date, time, version, file and section.

### Step 8 — Close out
Everything green · everything committed · pushed · changelog and version updated · open gates list
current · next-session brief written · tree clean, no dead branches or worktrees.

---

## 3. Termination condition

> **Terminate on the checker's exit code, never on "I stopped finding things."**

A script cannot get bored, cannot agree with itself, and cannot be persuaded. If a step cannot be
mechanically checked, say `CANNOT_VERIFY` and name the cause — never infer a pass.

### 3.1 The pass checks the phase's ACCEPTANCE SET, and stops

**A phase declares its exit conditions in `BUILD_PLAN.md` before it is built** (`RULES.md` Rule 5).
The pass verifies exactly that list. It does not go looking for whatever else it can find.

**Why this clause exists, measured.** A phase whose exit condition was prose could not terminate.
Each pass found more; each fix created surface for the next pass to examine; and a completeness
critic — whose question is *"what did you never look at?"* — can never return empty by construction.
One phase consumed three passes and two follow-up waves, and the last of those spent most of its
budget on findings that would never have stopped anything. **Verification without a finite
acceptance set does not converge; it is interrupted.**

### 3.2 Severity decides how much machinery a finding earns

`RULES.md` Rule 4 is binding on this pass and is not restated here beyond its consequence:

- **CRITICAL and HIGH** get an independent verifier, handed the CLAIM and never the diff, and a
  retained counter-example falsified in both directions. These block the phase.
- **MEDIUM** is fixed and falsified by whoever fixes it. It does not get its own agent.
- **LOW** is recorded and batched. **A LOW finding does not stop a phase.**

**Measured:** one fix wave closed 68 findings of which 60 were MEDIUM or LOW, and an unused
dependency line received the same lane, the same counter-example discipline and the same register
row as a classification leak. Applying the full machinery to every finding is how a verification
pass comes to cost more than the work it verifies.

### 3.3 Rounds are bounded before the pass starts

Declare the number of refutation rounds and whether a completeness critic will run **before**
dispatching, and record it. An unbounded critic is a generator of work, not a gate.

---

## 4. What the pass must never do

1. **Never green-light unverified work.** `CANNOT_VERIFY` is an honest outcome; a false green is not.
2. **Never let the fixer verify the fix.**
3. **Never trust a summary over the artifact** — the summary is the most-read and least-re-derived
   line in any document (doctrine §8.3).
4. **Never grep only the source.** Check built output too; defects invisible in source have been
   found in rendered artifacts repeatedly.
5. **Never leave a finding unwritten.** An open gate held only in context is an open gate that will
   be forgotten under load. That is the entire reason this file exists.
6. **Never rewrite history or force-push** to reach a green state.

---

## 5. Cost

A full pass runs ~10 agents and is deliberately expensive. It is cheaper than one false "verified"
claim reaching a later phase, where every document downstream reasons from it.

*Change history*

| date | change |
|------|--------|
| 2026-08-20 | Ritual established and cached after Phase 1, on operator directive. Separation-of-duties made the load-bearing law. |
| 2026-08-23 | §3.1-3.3 added: acceptance sets, the severity gate, bounded rounds. Written after a phase took three passes and two waves to close, with most of the last wave's budget going to findings that could never have stopped it. The pass was thorough and did not converge; these clauses are what make it finish. |
