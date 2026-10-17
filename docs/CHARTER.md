<!-- title: CHARTER -->
# Charter — what this project is, and the two things it is at once

**Status:** PROCESS — the anti-drift anchor. **Read before planning any phase.**
Written 2026-08-21, after a session spent almost entirely on infrastructure noticed it had drifted.

---

## The two purposes

This repository is **one project with two purposes**, and they are not independent — the second is
how the first is validated.

### 1. Build and optimise the engine

A **documentation engine with a governance layer**: it turns authored Markdown into design-system
HTML with deterministic, sourced figures, and it enforces a rule layer over the corpus — tiers,
surfaces, a manifest, a taxonomy, a precedence spine, a contradiction matrix, a hash-locked set of
laws. Phases 1–7 in `docs/plan/BUILD_PLAN.md` are that build.

### 2. Be the engine's own test corpus

**This repository is the first real project the engine governs.** Its own documents — the handover,
the registers, the plans, the laws — are the corpus. That is not a convenience; it is the design.
An engine that governs documentation is only proven by governing documentation that someone
actually depends on, changing under real edits, in a repository with real history.

**The two purposes are the same work seen from two sides.** Every defect the engine can catch in
this repository's documents is a defect it can catch in a customer's. Every defect it *cannot*
catch here is a gap in the product, discovered for free.

---

## Why this is written down

Because it was measured, and the measurement was bad.

> **80 tracked Markdown documents. 5 governed by the engine.**

These two numbers are re-derived on every health run by `CONS-09`, and again by the corpus
checker's `counts` guard, either of which fails if either drifts. They had to be: the first version
of this sentence said *53 tracked and four governed* and was **wrong the day it was written** — a
document restating a fact the code owns, in the file that argues for letting the engine own the
facts (`docs/process/RULES.md` Rule 2). It was wrong a second time on 2026-08-22, by one document,
within minutes of this phase adding one — and that time nobody had to notice, because a guard
refused the run and named the line.

**Two numbers, two different jobs, and the distinction is the phase's whole result.** *Governed*
still counts documents carrying a doc-system header — that moved 3 → 4 on 2026-08-22 when
`tools/docgen/gallery.md` was converted to the canonical convention, and 4 → 5 at the Phase-7 close
when `docs/process/THREAT_MODEL.md` was brought under governance and stamped `verified` — the first
document that OWNS a container to do so, which is what made a non-zero `verified` count reachable at
all. It is the number purpose 2 is ultimately measured by. But the **corpus checker runs over every
tracked Markdown document**
(`git ls-files '*.md' | wc -l`), not over the governed
subset: a stale count, a dead citation, a present-tense plan or a duplicated register key now fails
a check in any tracked document, header or no header. The governance header remains the deeper
goal; mechanical claim-checking no longer waits for it.

Purpose 2 was, at the time of writing, almost entirely unrealised. The consequence is visible in
this project's own history: three deep verification passes, dozens of agents, and the defects they
found were overwhelmingly **stale counts, plans written in the present tense, citations to files
that do not exist, registers contradicting themselves, a manifest described as shipping one row
when it ships eight** — precisely the defect classes the engine exists to catch **mechanically**.

They were found by hand, repeatedly, because nothing mechanical read the corpus. As of
2026-08-22 something does: `tools/corpus_check/` runs its guard set over every tracked
document, and each was shown red on a planted defect before being trusted.

**That is the whole argument.** The answer to "how do we stop re-finding stale documentation claims"
is not more verification agents. It is to point the engine at its own corpus, which is purpose 2,
which was the plan all along.

---

## What is NOT the goal

Stated explicitly, because this is where a session drifts. None of the following is the product;
each is scaffolding that must stay proportionate to the product it protects:

- **The git moat is not the product.** It is portfolio hygiene around a private repository.
  It earns effort in proportion to the accidents it prevents — see `docs/process/THREAT_MODEL.md`
  for what it does and does not claim. A session that spends itself hardening the moat has drifted,
  however real the defects it fixed were.
- **`tools/health` is not the product.** It is the gate that makes the product's claims checkable.
- **The registers are not the product.** They are the memory that makes a multi-session build
  possible. When a register grows faster than the engine, that is a signal, not an achievement.

Scaffolding is worth building well. It is not worth building endlessly.

---

## The anti-drift rule

**Every session must be able to name which purpose its work served, in one sentence, before it
commits.** If the honest answer is "neither", the session drifted, and the closeout says so.

The three legitimate answers:

1. **Engine** — a phase deliverable in `BUILD_PLAN.md`, or an optimisation of one.
2. **Corpus** — bringing this repository's own documents further under the engine's governance, so
   the engine is proven on something real.
3. **Scaffolding, bounded** — a gate, register or fix that was *blocking* 1 or 2, with the blocking
   relationship stated.

A session that reports (3) twice in a row is a project that has stopped building its product. Say it
out loud in the closeout rather than discovering it a phase later.

---

## What "done" looks like

**Purpose 1 — the engine:** the seven phases in `BUILD_PLAN.md`, each ending in something that
runs, each gate falsified red before it is trusted, and a final hardening stamp that references a
real commit.

**Purpose 2 — the corpus:** this repository's own documents carry doc-system headers, are
registered in the manifest, and are gated by the engine on every run — so that a stale count, a dead
citation, a present-tense plan or a contradicting register row **fails a check** instead of waiting
for a verification pass to find it by hand.

Purpose 2 is not a phase of its own. It is the acceptance test for Phases 3–6, and it should be
carried forward inside each of them: whatever guard a phase builds, this repository's own corpus is
the first thing it is pointed at.

---

## Decisions this charter locks

- The engine stays **domain-neutral**. This repository is its first corpus, never a special case in
  its code. A rule that only works here is a bug.
- **`docs/plan/BUILD_PLAN.md` §2 decisions D1–D7 stand** and are not re-litigated without new
  evidence.
- **The phase gate stands** (`docs/process/OPEN_GATES.md`): a phase does not begin while a known
  defect is open, and the only permitted deferral is a defect whose fix *is* a named later phase's
  declared work.
- **The deep verification pass stands** and is assumed at the end of every phase, with verifiers
  that are given the *claim* to attack and never the diff.
