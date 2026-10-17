<!-- title: RULES -->
# Six rules — every one measured, none chosen from opinion

These are the preventive rules. `LESSONS.md` is the after-the-fact record of what went wrong;
this file is what stops it going wrong again. Each rule below names the measurement that produced
it, because a rule whose cost nobody measured is a rule nobody obeys under pressure.

**Read this with `blueprint/SYSTEM.md`.** That map tells you what exists and what depends on what;
this file tells you how to change it. Neither works alone.

---

## Rule 1 — Fix the CLASS, not the instance

**Before fixing anything, enumerate every consumer of the defect's root. Fix all of them, or record
by name the ones you are leaving and why.** A fix that closes one door and leaves its siblings open
is not a fix; it is a scar, and the next pass will find the sibling and call it a new defect.

**Measured.** On one day, a single verification lane found the shape *"one root, several consumers,
one guarded"* **five separate times**: an attestation check bound to one of several tracked
lockfiles; a placement gate that read blob content but never the paths beside it; anti-vacuity
floors raised in one module and left constant in the ten that shared the name; a config override
honoured by the loader and ignored by the check named as its compensating control; a registry
asserted bidirectionally next to an identical registry asserted not at all. Every one of those was
created by an earlier fix that stopped at the instance in front of it.

**How to obey it.** Ask three questions and write the answers into the change:
1. What is the ROOT — the single sentence the defect violates? (*"an index must not name a
   non-public document"*, not *"this function is missing a check"*.)
2. Who else answers that question? `git grep` the root's vocabulary, not the buggy symbol.
3. For each, is it guarded? If not, guard it now or name it in the register.

> **The corollary that costs the most when ignored:** after you narrow anything, attack its NEW
> edge. Ask *what is the widest input that still gets through the narrowed version?* and write the
> probe for **that**. A fix that has never been attacked at its new boundary is a hypothesis.

---

## Rule 2 — A document never restates a fact that code owns

**If code can derive it, the document must not state it.** Point at the derivation instead. When a
number genuinely must appear in prose — because a reader needs it to make a decision — a guard must
re-derive it on every run, and the document says where from.

**Measured.** A gate count went stale twice. A locked-file table asserted an order the hash did not
use. A handover file claimed a lesson range that had moved. The one sentence authorising the start
of a phase asserted zero blockers while a blocker sat open — and closed by telling the reader
*"do not trust this sentence."*

> **A document that has to ask its reader not to trust a sentence is describing a missing check,
> not a caveat.**

**The correct repair is usually DELETION, not correction.** Updating the number restores it to
true for exactly as long as nothing changes. Deleting the restatement removes the failure mode.
Correct it only when a guard derives it.

---

## Rule 3 — Draft, verify against what exists, then integrate

**No document is committed as a first draft.** Write it, run the corpus gates against it *before it
is committed*, fix what they find, and only then let it land.

**Measured, and this is the rule that pays for itself fastest.** Across three verification passes,
the largest single category of finding was not broken code — it was **prose written without reading
its neighbours**: counts that were already stale, paths that named nothing, claims that contradicted
the module they described, deferrals that no plan accepted. Every one of those was detectable by a
gate that already existed. The gate simply ran at the END of the session, after everything was
written, so the cost of the error was *repair* rather than *avoidance*. A session was spent removing
defects from documents written earlier in the same session.

**The mechanism, not the intention:**

```bash
python3 -m tools.draft check <path>     # would this document be accepted if it landed right now?
```

Write the document at the path it will occupy, then run the gate before committing. It splices the
candidate into a throwaway copy of the working tree and runs the same guards the corpus runs, then
reports the difference — so it answers *"what would this introduce?"* rather than *"is this file
tidy?"*.

**That difference is the point, and it is why this is not `corpus_check | grep <path>`.** Adding a
document moves facts other documents state. Those findings land on paths the candidate never
mentions, and a filter over one run misses every one of them — which is precisely the class that
made earlier sessions expensive: a document written in isolation, correct on its own terms, quietly
falsifying a sentence somewhere else.

Writing prose without running it is the same mistake as writing code without running it, and this
project would never ship the second.

---

## Rule 4 — Severity decides the pipeline

**Not every finding earns the same machinery.** Applying the full treatment to every finding is how
a verification pass costs more than the work it verifies.

| severity | verification | counter-example | fixed when |
|---|---|---|---|
| CRITICAL, HIGH | independent agent, handed the CLAIM and never the diff | required, falsified both ways | immediately; blocks the phase |
| MEDIUM | the implementer's own falsification is sufficient | required for behaviour, not for prose | batched at phase end |
| LOW | none | none | batched at phase end, or recorded and left |

**Measured.** One wave fixed 68 findings; **60 of them were MEDIUM or LOW**, and an unused
dependency line received the same lane slot, counter-example discipline and register row as a
classification leak. That is where the time went.

**A LOW finding is not a defect that stops a phase.** Record it and move.

---

## Rule 5 — A phase declares its acceptance set before it starts

**Write the exit conditions — a short, finite, checkable list — into the plan BEFORE building.**
Verification then checks exactly that list and stops.

**Measured.** A phase whose exit condition was prose (*"the checker works"*) could not terminate:
each pass found more, every fix created surface for the next pass to examine, and a completeness
critic asked *"what did you never look at?"* — a question that can never return empty. Verification
without a finite acceptance set does not converge; it is interrupted.

**An acceptance set is 5–10 invariants, each one a command with an expected result.** If you cannot
write it before building, you do not yet know what you are building.

---

## Rule 6 — Derived work is committed, never regenerated

**If an agent derived it, keep it.** Maps, graphs, indexes, models — commit them, and add a check
that the committed copy matches a fresh derivation. A derived artifact that is not committed is not
a source of truth; it is a cache, and the next session pays to rebuild it.

**Measured.** This engine's own navigation layer was empty in every part at once — an index holding
one row for a repository of hundreds of files, a content index never generated, a dependency graph
reporting zero nodes across the whole codebase, in a directory that was ignored by version control
so nothing survived the session that built it. Roughly thirty agents each re-derived the tree by
hand, at hundreds of thousands of tokens apiece, to rebuild a map that costs a fraction of one
percent of the tree to derive and keep.

**Two mechanical corollaries, both paid for:**
- **A builder that produces an empty result must exit non-zero.** An empty map is not a result. It
  is a confident lie, and every downstream reader believes it.
- **A derived artifact needs a staleness ratchet**, run by the retained suite, so a stale copy fails
  the push. The ratchet — not the artifact — is what makes it trustworthy.

---

## How these are enforced

None of these rules is enforced by being written here. Each has machinery, and where a rule has no
machinery this file says so rather than implying one.

| rule | enforced by |
|---|---|
| 1 — fix the class | **Not mechanically enforceable.** Enforced at review, and by the register: a fix that names no siblings invites the question. |
| 2 — no restated facts | the `counts` guard re-derives every stated count; `symbols`, `test-refs`, `crossrefs` and `built-claims` refuse a citation that resolves to nothing |
| 3 — draft first | `tools/draft`, and it refuses to promote a candidate the guards reject |
| 4 — severity gates the pipeline | `DEEP_VERIFICATION_PASS.md`, which the pass procedure follows |
| 5 — acceptance set first | `BUILD_PLAN.md` carries one row per phase; the phase gate refuses a deferral no plan names |
| 6 — derived work is kept | `blueprint check` inside the retained suite; the graph builders exit non-zero on an empty result |

---

## What these rules deliberately do NOT try to do

They do not make the work correct. They make a **specific, measured, repeated** failure mode
expensive enough to notice: asserting something nobody checked, restating something that rots,
writing prose without reading its neighbours, spending a security budget on a typo, verifying
without a finish line, and throwing away work that was already paid for.

They say nothing about architecture, naming, or performance. That is deliberate. A rule that covers
everything is obeyed nowhere, and this file is short so that it can be held in one head while
working.
