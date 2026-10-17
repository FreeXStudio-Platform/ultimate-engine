<!-- title: START NEXT SESSION -->
# Start the next session — copy-paste command

**Written:** 2026-08-22 at the close of Phase 3; rewritten in place 2026-09-01 when field-trial
round 1 was reviewed and its defects repaired. **The next session designs and issues round 2.**
**Starting state:** project `1.1.2`, rulebook `1.2.17`, `master` pushed and clean,
`python3 -m tools.health --full` → **38 passed, 0 failed, 0 skipped**.

## ▶ Open after the `1.1.0` merge — read this before the inherited brief below

The inherited field-trial brief below is still valid and has not been run. What the `1.1.0` merge (a downstream copy's figure
system, module explorer and project census) leaves open:

1. **`OG-262` — bring the nine native chart kinds to the figure contract** (bar, pie, radar, heat map, timeline, sankey, geo
   map, isometric, layered workflow): per-mark `data-*` + `<title>`, adjacency where it applies, an AI record, and the
   sankey's flows coloured by source. It is a feature, not a repair (`OG-262` says why), and the design is already written —
   `docs/design/FIGURE_SYSTEM.md` §2–§4 — so the work is mechanical: one renderer at a time, each with a test in
   `tools/tests/test_figure_system.py` and a case in `tools/tests/browser/figure_runtime_check.mjs`.
2. **The copy converging is the operator's call.** The copy's own history is merged here, so its sync from this repository's
   `master` is a plain merge in either direction. Two things it will see: this repository removed the copy's own description file
   and hand-over briefing from the tree (they describe the copy, not the engine), and de-branded the comments, test names and
   changelog text it imported — a merge in the other direction should keep the copy's own files and may take the reworded text.
3. **Consumers take the engine from this repository, by tag.** The latest release is tagged `v1.1.2` (`v` + `PROJECT_VERSION`); a product that
   vendors the engine updates its own copy from that tag. There is no second repository to publish to.
4. **Re-run the browser check on any change to `figure_runtime.js`, `figure-layer.mjs`, `visual.py` or `sequence_diagram.py`**:
   `PLAYWRIGHT_MODULE_DIR=<dir resolving playwright> python3 -m unittest tools.tests.test_figure_runtime_browser`. It skips,
   with the cause, where Playwright is absent — a skip is not a pass.
5. **Run python with PyYAML first on `PATH`** (`export PATH="<venv>/bin:$PATH"`): the suite spawns `python3`, and one without
   PyYAML fails five staged-scanner tests that have nothing to do with the change.

*(No commit sha is quoted here on purpose — it would go stale on the next commit and this file must
stay true. Run the health command; that is the live check. The numbers above are not decorative
either: `tools.health` `CONS-08` fails if this file misstates the project version, the rulebook
version, or the health floor — **including inside the launch command below**, which is the one line
a human actually executes. It has caught exactly that on this file four times now.)*

> **This file is rewritten in place, never appended.** It holds the command for the **next** session
> and nothing else. The Phase-7 launch prompt it used to carry was a superseded record kept long
> after the phase shipped; it lives in `git log` and in `CHANGELOG.md [1.0.0]`, which is where a
> record belongs. One file, one job.

---

## What the next session is

**Round 1 is closed.** It ran against a foreign subject, returned eleven findings, and this
repository re-derived every one of them: five were real engine defects and are repaired (`OG-244`
through `OG-248`), three were the subject's, two were wrong, and one was right for the wrong reason.
The full disposition is `CHANGELOG.md` `[1.0.5]` and `docs/plan/FIELD_TRIAL_ROUND_1.md` §5.

**The round produced a NEW CLASS**, which is the signal `FIELD_TRIAL.md` §6's stop rule reads:
*defects that exist only off this engine's own tree.* Every one of the five repairs was invisible to
a self-check for a structural reason — a repository large enough for git to start collecting, a
disconnected package graph, two interpreters with different dependency sets, a directory layout that
does not match a builder's shape. **So the programme continues and round 2 runs.**

**The next session designs and issues it.** Three things decide its shape, and none of them is "more
of the same corpus":

1. **Language reach is the one bound round 1 could not touch.** Its subject was Python, the engine's
   best case for structure, and the blueprint layer reads Python only (`OG-243`). A non-Python
   subject is what measures the rest — and `OG-243`'s own trigger is a host that genuinely needs the
   derived module map.
2. **The new class says what to vary:** host size, graph shape, environment, and directory layout.
   A subject that differs from round 1's on none of those cannot produce a new class.
3. **The brief must state that the instrument is stripped.** Round 1's operator spent its first and
   highest-severity finding measuring `FIELD_TRIAL_ROUND_1.md` §2's own packaging decision. That cost
   is the round's, not the operator's — see §5.

`FIELD_TRIAL.md` §3 rule 4 still reserves a fresh, never-seen subject for the final round, so round 2
must not spend it.

## Which model

**Run this session at the top tier (`fable`).** Round 2's design is a set of judgement calls that a
weaker model does not make more slowly — it makes them confidently and wrongly: which subject
actually varies the class, what the brief may and may not reveal without destroying the measurement,
and where the bound sits. Route mechanical work (file moves, packaging, lookups) downward from there.

---

## The command

```bash
cd <your clone> && claude --dangerously-skip-permissions --model fable --effort max "ultracode. You are a fresh session designing and issuing field-trial round 2. Work from files, never from memory; this prompt is a map and the repository is the territory. STEP 0 - ORIENT FROM THE DERIVED MAP. Run: cat blueprint/SYSTEM.md - that is the first command of the session, before any grep. Then cat blueprint/COMPLETENESS.md, then blueprint/SURFACES.md for anything at the level of a flag, check, guard, schema, figure kind or environment variable. All three are derived on every build and committed, so they cannot go stale the way a hand-kept overview does. Then HANDOFF.md, docs/process/SESSION_STATE.md, docs/plan/FIELD_TRIAL.md, and docs/plan/FIELD_TRIAL_ROUND_1.md - round 1 is CLOSED and section 5 holds its verdict, its findings by class, and the reason round 2 runs at all. STEP 1 - VERIFY THE FLOOR BEFORE TOUCHING ANYTHING. Run: (python3 -c 'import yaml' 2>/dev/null || python3 -m pip install --quiet --user PyYAML) && bash tools/hooks/install.sh && (cd tools/visual-engine && npm install --no-audit --no-fund) && (cd tools/mermaid-engine && npm install --no-audit --no-fund) && python3 -m tools.health --full Confirm 38 passed, 0 failed, 0 skipped at project 1.1.2 and rulebook 1.2.17 with master clean. Run heavy gates in a quiet window - a TIMEOUT under external machine load is a verdict to repeat, not a pass and not a corpus defect (OG-212). Never pipe a gate into tail and then test the exit code; you read the pipe status, not the gate. STEP 2 - READ WHAT ROUND 1 ACTUALLY BOUGHT, BEFORE DESIGNING ANYTHING. Round 1 produced a NEW CLASS - defects that exist only off this engine own tree - and every one of its five repairs was invisible to a self-check for a STRUCTURAL reason: a repository large enough for git to start collecting objects, a disconnected package graph, two interpreters with different dependency sets, a directory layout that did not match a builder shape. Read OG-244 through OG-248 in docs/process/OPEN_GATES.md and their counter-examples in tools/tests/. The design question for round 2 is not what else might break; it is which conditions this repository still cannot generate about itself. STEP 3 - CHOOSE THE SUBJECT BY ELIMINATION, AND RECORD THE ELIMINATION. FIELD_TRIAL.md section 3 rule 4 reserves a fresh never-seen subject for the FINAL round, so round 2 must not spend it. Language reach is the one bound round 1 could not touch: its subject was Python, the engine best case for structure, and the blueprint layer reads Python only (OG-243), whose own trigger is a host that genuinely needs the derived module map. Weigh that against the new class - host size, graph shape, environment, directory layout - and state plainly which of the two round 2 is buying, because a subject that varies neither cannot produce a new class. Write the elimination down the way round 1 did: each candidate, and the specific reason it was rejected. STEP 4 - PROVE FEASIBILITY BEFORE ISSUE, NEVER ASSUME IT. Point the engine at the candidate and measure what it actually derives, exactly as FIELD_TRIAL_ROUND_1.md section 3 did. A round issued on an assumption grades the assumption. If the derived map is empty because of OG-243, that is a RESULT to state in the brief bound, not a reason to hide the subject. STEP 5 - WRITE THE BRIEF, AND STATE WHAT ROUND 1 DID NOT. The instrument handed over is deliberately STRIPPED - FIELD_TRIAL_ROUND_1.md section 2 removes 26 tracked files - and round 1 brief never said so, so its operator spent its first and highest-severity finding measuring the packaging rather than the engine. Round 2 section 2 must state the removal where the operator meets it and give the expected health verdict for the package as issued. This is not coaching the operator: the stripping is a fact about the PACKAGE, not an answer to the task, and concealing it measured nothing except how long an operator takes to notice. Everything that IS the task - the command names, the configuration route, the host-root variables - stays withheld, because finding those is the reachability half of the test. STEP 6 - STANDING CONSTRAINTS. A ratchet may only TIGHTEN: never loosen a ceiling, lower a floor, delete or weaken a retained counter-example, or widen an exemption to make anything pass. Fix the CLASS and not the instance, and after narrowing anything attack its NEW edge. Every fix is red-first with a retained counter-example; a repair that cannot be expressed as a repeatable test is an accommodation. Derived work is committed and rebuilt LAST - blueprint after any doc or code change, because a retained test fails the push if it is stale and every later doc edit restales it. Secret-scan before every git add, redirected to a file with the exit code read directly, never piped. Never use --no-verify and never bypass the hooks. The server-side moat requires a pull request with a green secret-scan check on master: feature branch, push, PR, merge with a MERGE COMMIT - squash or rebase would orphan stamped commits and redden the stamps guard. STEP 7 - CLOSING. Done means: docs/plan/FIELD_TRIAL_ROUND_2.md written with its subject elimination, its measured baseline, its brief and its stated bound; the package assembled and verified to have no remote; OPEN_GATES.md current; CHANGELOG entry written; PROJECT_VERSION bumped once to match; SESSION_STATE.md rewritten in place and stamped at a real commit; START_NEXT_SESSION.md rewritten for the session that will REVIEW round 2; blueprint rebuilt last; health --full green; corpus_check clean; blueprint verify clean; and everything landed through a PR with the hooks active. Report the real state, including anything left unverified."
```

---

## What "done" looks like for that session

- Every returned finding is **verified against the artifact**, then recorded in `OPEN_GATES.md` with
  a disposition and reasoning a future verifier can attack.
- Every discoverability gap is closed **in the repository**, never by coaching the next operator.
- Every fix is red-first with a retained counter-example; **no ratchet loosened**.
- `FIELD_TRIAL_ROUND_1.md` §5 is complete, and the **new-class** question is answered — that is the
  question `FIELD_TRIAL.md` §6's stop rule reads, and "no new findings" is not the same answer.
- The floor is green, the records agree, the blueprint is rebuilt last, and everything is landed
  through a pull request with a merge commit.
