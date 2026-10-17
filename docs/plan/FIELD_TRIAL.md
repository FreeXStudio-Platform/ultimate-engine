<!-- title: FIELD TRIAL -->
# The field trial — a blind operator, a real project, and calibration rounds that terminate

**Status:** PLAN — **written 2026-08-29, before Phase 7 ran, deliberately.** It describes work that
begins only after `1.0.0` ships and changes nothing Phase 7 does.

`docs/plan/AFTER_1_0.md` §4 names Stream B — *run the engine on a project that is not this one* — in
three sentences. This is that stream at full width: who runs it, what they are and are not given,
what counts as a finding, how a round calibrates, and **how the programme stops**.

> **Why this is written before Phase 7 rather than after.** A trial protocol authored *after* seeing
> what Phase 7 produced would, without anyone intending it, avoid testing what Phase 7 got wrong.
> Writing it blind is the same discipline `RULES.md` Rule 5 applies to an acceptance set: the
> measure is fixed before the thing being measured exists. It deliberately pins **no number** that
> Phase 7 will move — every quantity below is a command to run, not a value to trust.

---

## 1. Why a blind operator is the strongest test this project can run

Phase 7 verifies the engine against its own corpus, using agents that read this project's lessons,
inherit its vocabulary, and share its assumptions about what the engine is for. That is the right
way to find *correctness* defects and it is why Phase 7 exists.

It cannot find the other kind. **`HANDOFF.md` asserts, in its opening lines, that these files are
self-contained and that nothing important lives only in a previous chat. Nothing gates that claim,
and nothing here ever could** — every agent this project has used was present for the build. The
claim has been asserted for six phases and never once tested.

A blind operator tests it, and tests the actual product claim underneath it: **can someone who was
not here use this engine?** That question is the whole reason the project exists, and it is the one
question this repository has never been able to ask itself.

### The fifth finding class — the one only a blind operator produces

`AFTER_1_0.md` §3 lists four outcomes, of which two are findings. A blind operator adds a fifth:

> **The engine could do it, and the operator could not find out how.**

That is a discoverability defect, and it is **invisible to anyone who already knows the answer** —
which is every agent that has ever touched this repository. It is also, for a tool of this kind, the
most likely real-world failure: not that the capability is missing, but that the path to it is not
findable from the documents that claim to be the way in. Treat this class as the trial's primary
yield, not an afterthought.

---

## 2. The three roles

**The blind operator.** A model with no history here — ChatGPT in the first instance.

*It is given:* the repository, and a task statement written in the **subject project's** terms
rather than the engine's. *It is not given:* any session transcript, any hint, any mid-run
correction, or the answer. It reads whatever the repository tells it to read — the documents **are**
the product, so consulting them is not cheating, it is the test.

*One instruction it must carry:* if it cannot work out how to do something, it must **stop and say
so** rather than improvise. An operator that thrashes and eventually guesses destroys the
discoverability signal, which is the most valuable thing the run produces.

**The paired operator.** This project's own agent, given the same task in the same round, working
independently and without seeing the blind run.

**The adjudicator.** The human operator. Decides which divergences are findings. **Neither model
adjudicates its own run**, which is `DEEP_VERIFICATION_PASS.md` §1's separation of duties applied at
the level of the product rather than the patch.

### Why both operators, and not just the blind one

They fail in different directions, and the difference is the measurement:

| | tests | fails when |
|---|---|---|
| Paired operator (knows the engine) | **depth** — does the hard thing come out correct? | the engine is wrong |
| Blind operator (knows nothing) | **reachability** — can it be found and used at all? | the engine is unusable |

**Where they agree, the engine is both correct and documented. Where they diverge, something is
wrong and the divergence names which half** — either the documents are ambiguous enough to admit two
readings, or the engine is not deterministic. Both are findings, and neither is visible from a
single run.

---

## 3. The subject project

A real project on the operator's own machine, with real history and documents someone depends on. A
toy exercises nothing, and this project has already measured that a probe anchored to a convenient
fixture proves only what its author imagined (`LESSONS.md` L-37).

Four rules, and the first two are not negotiable:

1. **Operate on a copy or a dedicated branch. Never on live project material.** The engine writes
   documents, a blueprint and derived JSON; a calibration round is not the place to discover what
   that does to work in progress.
2. **A cross-project write needs an explicit operator grant** — named, dated and scoped to the
   subject — per the portfolio isolation rule. The Ultimate Engine's agent writing into another
   project is exactly the boundary that rule exists to hold, and a trial is not an exemption from it.
3. **The same subject across calibration rounds.** Changing it mid-programme makes round-over-round
   improvement unmeasurable, because you can no longer tell a better engine from an easier project.
4. **A fresh, never-seen subject for the final round.** A protocol run five times against one
   project has been calibrated to that project. The last round is the only one that measures
   generalisation, and it is the reason the programme has an ending worth trusting.

---

## 4. What a round is

The surface under test is the reason the project was started: **project document creation, document
interconnections, blueprint creation and connecting, graph creation, and the derived JSON.**

1. **Issue the task.** One statement, identical for both operators, in the subject's terms. Neither
   sees the other's copy of anything.
2. **Run, independently.** Each produces the documents, the blueprint, the interconnections, the
   graphs and the JSON for the subject project.
3. **Compare, three ways.** Each output against *the engine's own gates* — does `corpus_check`,
   `health` and `blueprint verify` pass on the corpus it just produced? Each output against *the
   task* — did it do what was asked? And **output against output** — where did the two diverge?
4. **Classify** every result into the five classes (§1 plus `AFTER_1_0.md` §3). Most results should
   be *the engine worked*, and that is not a finding.
5. **Record before fixing.** Every finding is written into `docs/process/OPEN_GATES.md` **when it is
   found**, before any repair is attempted. A record written after the fixing has been trimmed to
   what got fixed.
6. **Calibrate.** See §5, which is the rule that keeps this honest.
7. **Log the round** — subject, task, both outputs' verdicts, findings by class, what was changed.

---

## 5. The trap this programme must not fall into

**The engine is being tuned by the thing testing it.** That is the shape `OG-198` and `OG-204` are
open records of refusing: *do not tune a measurement in the exercise that benefits from tuning it.*
Here it would look entirely reasonable — the blind run failed, so make it pass.

Two guards, and they are the price of the programme being worth anything:

- **Every calibration is a CLASS fix carrying a retained counter-example, falsified in both
  directions.** If a repair cannot be expressed as a counter-example, it is not a fix, it is an
  accommodation, and it will make exactly one run green.
- **A finding is never closed by making the operator smarter.** Adding a hint to the task statement,
  or telling the next run what the last one got wrong, converts a product defect into a coaching
  problem and destroys the measurement. If the answer was not findable from the repository, **the
  repository is what changes.**

---

## 6. How the programme ends

*"Several backtests"* is unbounded, and unbounded verification does not converge in this project —
it gets interrupted, which is a worse ending than a declared one. So the stop rule is explicit:

- **Stop after two consecutive rounds that produce no NEW CLASS.** Not *no findings* — a round can
  keep producing instances of a known class indefinitely, and that is the engine being used, not the
  engine being unexplored. A new **class** is the signal that failure modes remain unmapped.
- **A hard ceiling of six rounds**, whatever the streak. If classes are still appearing at six, that
  is itself the finding, and it gets written down rather than chased.
- **Then the final round, on the never-seen subject** (§3 rule 4). It does not count toward the
  streak; it is the generalisation check, and its findings are recorded whether or not anyone acts
  on them.

**Done means:** the streak was met or the ceiling reached with the residue named; the fresh-subject
round has run; every finding is closed or dispositioned with reasoning a future verifier can attack;
the engine's own floor is still green; and **`HANDOFF.md`'s self-containment claim has either held
or been corrected** — because this is the first thing that has ever been able to test it.

After that the engine is calibrated, and `AFTER_1_0.md`'s three streams continue as ordinary
operation. **This programme is not the product. It is what makes the product's central claim
checkable, once.**

---

## 7. The task statement handed to the blind operator

A template, not a script. Fill the bracketed parts from the subject project, and change nothing else
— every removed constraint costs a signal.

> You have been given a repository called the Ultimate Engine. It is a documentation and
> visualisation engine with a governance layer, and it is meant to be usable by someone who has
> never seen it before by reading the repository itself.
>
> Your task is about a **different** project, at `[path]`, which the engine has never been pointed at.
> For that project, use the engine to produce: its project documents, the interconnections between
> them, its blueprint, the graphs, and the derived JSON.
>
> Work only from the repository. **Do not guess.** If you cannot work out how to do something from
> the documents, stop, write down exactly what you were trying to do, what you read, and where the
> trail went cold — **that outcome is a result, not a failure, and it is more useful than a guess
> that happens to work.** Report what you produced, what the engine's own checks said about it, and
> everything you could not find your way to.

**What the statement deliberately withholds:** the names of the commands, the entry points, the
order of operations, and the fact that any of it is being measured. Adding any of those turns a
reachability test into a transcription exercise.
