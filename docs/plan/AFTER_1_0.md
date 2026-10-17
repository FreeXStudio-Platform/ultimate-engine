<!-- title: AFTER 1.0 -->
# After 1.0 — what the work becomes when the build ends

**Status:** PLAN — **written 2026-08-29, before Phase 7 ran.** It describes the mode the project
enters *after* Phase 7 closes and does not change anything Phase 7 does.

`docs/plan/BUILD_PLAN.md` has seven phases and then stops. That is correct — the build genuinely
ends — but it left the obvious next question unanswered, and this file is the answer.

---

## 1. Yes, it ends. Half of it.

`docs/CHARTER.md` states two purposes, and Phase 7 finishes exactly one of them.

**Purpose 1 — build the engine.** *"Phases 1–7 in `docs/plan/BUILD_PLAN.md` are that build."* Phase 7
ships `1.0.0`, and the version scheme reserves MAJOR *"thereafter for a breaking engine change"*.
There is no Phase 8 and none is planned. **This is done, and you may call it done.**

**Purpose 2 — be the engine's own test corpus.** This one is a *measurement*, not a phase. `CONS-09`
reports how many of this repository's documents the engine actually governs, and
`blueprint completeness` reports how many nodes reach `verified`. Both numbers are small, both are
honest, and Phase 7 moves them without finishing them. **A measurement does not have a last day.**

So the honest summary: **at `1.0.0` you stop building and start operating.** Everything below is
operating. None of it is a phase, none of it blocks anything, and the engine is a finished product
whether or not you do any of it.

---

## 2. Why operating it is not busywork

The charter's last line is the whole argument:

> Every defect the engine can catch in this repository's documents is a defect it can catch in a
> customer's. **Every defect it cannot catch here is a gap in the product, discovered for free.**

That makes the operating mode a **gap-finding machine**, not maintenance. You are not tidying
documents. You are running real material through the engine to find out what it cannot see — and
what it cannot see is the product backlog.

The catch, and it is the reason this file exists: **the gap announces itself as silence.** A gate
that should have fired and did not produces a clean run. It looks exactly like success. Both
findings in this session's own closeout were that shape — a deferral guard blind for two phases
(`OG-210`) and a crash-recovery record five phases stale (`OG-211`) — and both ran green the entire
time.

---

## 3. The loop, and what counts as a finding

Take one ungoverned document. Put it through the six steps in
`docs/process/AUTHORING_CONTRACT.md` — tag, wire, date, version, changelog, stamp. Watch what the
gates do. Then classify what happened, because **only two of the four outcomes are findings**:

| what happened | finding? | what you add |
|---|---|---|
| A gate fired and it was **right** | **No** | Nothing to the engine. Fix the document and move on. This is the engine working, and it should be most outcomes |
| A gate fired and it was **wrong** — a false positive | **Yes** | An `OPEN_GATES.md` row, the narrowing fix, and a retained counter-example pinning the *correct* case so the narrowing cannot drift back |
| A gate stayed **silent** on something a careful reader calls wrong | **Yes — and this is the valuable one** | An `OPEN_GATES.md` row, the gate or widening that catches it, shown **red first**, and a counter-example in both directions |
| **No gate exists** for that class at all | **Yes** | An `OPEN_GATES.md` row naming the class and its bound — then a decision: build it, or record why not with reasoning a future verifier can attack |

**Rows 2 and 3 are the product backlog.** Row 3 is the charter's "discovered for free", and it is
the one that requires deliberate effort to notice, because nothing tells you. The habit that finds
it: after every clean run, ask *what would a careful reader object to that this run did not
mention?* — and treat a confident silence as a claim needing evidence, not as a result.

**Nothing new is needed to record any of this.** `OPEN_GATES.md` is already the register, `LESSONS.md`
is already where a repeated shape goes, and `CHANGELOG.md` is already where a closure is recorded.
Do not build a second register; two registers of one thing is the drift this engine exists to catch.

---

## 4. The three streams of work, in priority order

**Stream A — govern this repository's own documents, one at a time.** The direct execution of
purpose 2, and the cheapest source of findings because the corpus is here and you already know it.
Each document either goes through clean (the engine works) or produces a row 2/3/4 finding (the
engine has a gap). Pick documents that are *actually depended on* rather than the easy ones; a
document nobody reads exercises nothing.

**Stream B — run the engine on a project that is not this one.** The product test. A defect class
that only shows up in somebody else's corpus is a gap you could never have found here, and this is
the only stream that can find it. It is also the only one that tests the *portability* claims — the
config chain, the host-root resolution, the zero-configuration defaults.

> **Stream B has its own programme: `docs/plan/FIELD_TRIAL.md`.** A **blind** operator — a model
> with no history here — runs the engine on a real external project while this project's own agent
> runs the same task independently, and the two are compared against the gates, against the task,
> and **against each other**. That pairing is the point: one tests whether the hard thing comes out
> *correct*, the other whether it can be *found at all*, and a divergence names which half is
> broken. It is also the only thing that can test `HANDOFF.md`'s standing claim that nothing
> important lives only in a previous chat — a claim nothing gates, and that no agent who was present
> for the build could ever falsify. The programme has a declared stop rule, because unbounded
> verification does not converge here; it gets interrupted.

**Stream C — keep what is already true, true.** Facts rot: stamps drift, counts move, citations
point at lines that have shifted. The gates catch most of it; `OG-211` is the measured proof that
"most" is not "all", and that the document nobody checks is the one that goes furthest wrong.

Streams A and B produce findings. Stream C prevents the specific decay that has already happened
here more than once. **None of them is urgent.** That is the point of finishing a build.

---

## 5. One thing to settle at the first post-1.0 finding

**The disposition vocabulary loses a word when the last phase ends.**

`OPEN_GATES.md`'s phase gate permits exactly one kind of deferral: `SCHEDULED (Phase N)`, valid only
when phase N's `BUILD_PLAN.md` row declares that work. Its whole force is that a deferral must name
a **forcing event**. After Phase 7 there are no more phases, so that word becomes unusable — and the
failure mode is obvious and already documented: dispositions with no forcing event become indefinite
parking, which is exactly what retired `SHOULD_FIX`, `NEXT_SESSION`, `NICE_TO_HAVE` and open-ended
`ACCEPTED` when the register was carrying 26 open rows with 19 of them parked.

**Recommended, and needing ratification rather than assumed:** replace the phase with a **release**
— `SCHEDULED (1.1.0)` — keeping the same two-sided rule, where the named release must declare the
work somewhere a check can read it. That preserves the property that makes the gate work: a deferral
points at an event, the event points back, and neither side moves alone.

Settle it **when the first post-1.0 finding is recorded**, not before. Deciding it now would be
designing against an imagined register, and `cross_doc`'s existing check must be taught the new
spelling in the same change — otherwise the check silently stops adjudicating deferrals, which is
`L-38` happening for the second time in the same file.

---

## 6. What this file is not

- **Not a phase.** Nothing here blocks anything, and no row should ever be dispositioned against it.
- **Not a licence to reopen the build.** `1.0.0` is a real boundary. Work that would change the
  engine's shape rather than close a measured gap is a new MAJOR, decided deliberately, not drift.
- **Not a promise the work happens.** The engine is finished at `1.0.0`. This describes what is
  *available* to do next and why it pays, so a future session is choosing rather than guessing.
