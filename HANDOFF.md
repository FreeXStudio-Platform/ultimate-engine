# HANDOFF — start line for the next session

> ## ▶ READ `blueprint/SYSTEM.md` FIRST — before this file, before the charter, before anything
>
> It is a **derived** map of the whole repository: the risky core (which modules break the most if
> you get them wrong), every package, the gate spine in adjudication order, all three registries,
> the document set by classification, and every open register row. It is regenerated from the tree
> by `python3 -m tools.blueprint build` and a retained counter-example fails the push if the
> committed copy is stale — so unlike a hand-written overview it **cannot** quietly go wrong.
>
> **Why this line exists, measured 2026-08-23.** Before the map, this repository's navigation layer
> was empty: `PROJECT_INDEX.json` held **1** artifact for 295 tracked files, the content
> index had never been generated, and the dependency graph reported **0 nodes** across ~75 real modules —
> in a directory that was gitignored, so nothing survived to the next session. Every dispatched
> agent re-derived the tree by hand at **200–350k tokens each**, roughly thirty times over. This
> engine exists to stop exactly that, and it was not switched on for itself.
>
> Read the map, then open only what it points at. Prose is the expensive way to learn a system.

**Written:** 2026-08-22 at the close of Phase 3; rewritten 2026-08-29 at the close of Phase 6 and
again at its closeout.
**Read `docs/CHARTER.md` first** — it states what this project is and the two purposes it serves
at once, and it is the anchor a long build drifts away from. Then this file, then `docs/plan/NEXT_SESSION.md`, then `docs/plan/BUILD_PLAN.md`,
then `docs/framework/DOC_WRITING_DOCTRINE.md`, then `docs/process/DEEP_VERIFICATION_PASS.md`.
These files are self-contained. **Nothing important lives only in a previous chat.**

---

## Where things stand

| | |
|---|---|
| Repo | `github.com/FreeXStudio-Platform/ultimate-engine` |
| Local | your clone, branch `master`, one worktree, no stashes |
| Project version | **`1.1.2`** (`PROJECT_VERSION`; scheme + history in `CHANGELOG.md`) — `1.1.2` prepared the repository to be public (licence, policies, templates, CI, README; `OG-310`); `1.1.1` made the census example profile build in a plain engine tree (`OG-308`, `OG-309`); `1.1.0` was the merge of a downstream copy's work into this repository, the first MINOR since `1.0.0`: the **figure system** (`OG-250` … `OG-268`: every figure is scoped, numbered, explained and linked to the text, and a machine reads a document through `<stem>.blueprint.json` — `docs/design/FIGURE_SYSTEM.md`), the **size standard** and reference cards, the **module explorer** (a zoomable, clickable hierarchy with a panel and a reader), the **documentation census** (`tools/census`, a measurement of any repository's documents and code, drawn with ten kinds of figure) and the defects each of those found in review (`OG-269` … `OG-303`), plus the copy's views-registry fix for a host that owns its own `tools/project_index` and its dependency and lint-ceiling work. **Two builds called `1.0.7` exist and are different:** this repository's (Dependabot alerts) keeps `[1.0.7]`; the copy's is kept as `[1.0.7+copy]`, and the copy's other builds keep their own numbers `1.0.8` … `1.0.14` — the full mapping is in the `[1.1.0]` entry of `CHANGELOG.md` |
| Rulebook version | **`1.2.17`** (`docs/design/doc-system/VERSION.json` — a *different* versioning system; see the table at the top of `CHANGELOG.md`. Last bumped `1.2.16` → `1.2.17` at the Phase-7 close, `OG-214`; the audit changed no hash-locked file, so it holds) |
| Build state | **The build is done (`1.0.0`), the full-system audit is done (`1.0.1`), and field-trial round 1 has RUN, RETURNED and been ADJUDICATED (`1.0.5`).** There is no Phase 8. Round 1 pointed the engine at an EXTERNAL subject — the *Absolute Canonical Framework* — and the returned report's eleven findings were each re-derived here before anything changed: **five were real engine defects and are repaired** (`OG-244` the draft gate crashing on any host large enough for git to start collecting, `OG-245` generated whitespace, `OG-246` ELK component spacing, `OG-247` child interpreter and import path, `OG-248` vacuous graph builders — `OG-248` supersedes `OG-241`), three were the subject's own and correctly not repaired, two were wrong, and one was right for the wrong reason. **The round produced a NEW CLASS** — defects that only exist off this engine's own tree — which is the signal `FIELD_TRIAL.md` §6's stop rule reads, so **round 2 is warranted**. One design gap is named and deliberately not closed: on a foreign host `blueprint build` publishes THIS engine's registries in the host's `SURFACES.md` and `verify` passes, because it checks tree ownership and not registry provenance. **The next session decides and runs round 2 — its brief is `docs/plan/START_NEXT_SESSION.md`, and it should run at the top tier.** |
| Health | `python3 -m tools.health --full` → **38 passed, 0 failed, 0 skipped** (on a quiet machine; `SUITE-05` times out under heavy external load — `OG-212`). The three real-browser tests run when `PLAYWRIGHT_MODULE_DIR` names a directory that resolves `playwright`; without it they SKIP, with that cause, and the suite reports them |
| Hardening stamp | `PROVENANCE.md` is **NEEDS RE-HARDENING**: on 2026-10-16 its body was edited for the public release — machine-specific absolute paths replaced by placeholders, no claim changed — so its `Approved With Known Risks` stamp (`96b90d8`) no longer covers the body; re-harden it (three-pass, pass 3) to restore it (verified: `corpus_check --guard stamps` → drift declared for that one document, none other) |
| Second stamp | The threat model's `Verified` stamp still covers its body at `96b90d8` (`OG-09`); this work did not touch it |

## ✅ Phase 7 is complete — the build ended at `1.0.0`

The last phase proved rather than built. Its record is `CHANGELOG.md [1.0.0]`, the raw reverification
findings are `VERIFICATION_LOG.md` Pass 9, and what the work becomes now is `docs/plan/AFTER_1_0.md`.
The section below is the Phase-6 record it built on, kept as history.

## ✅ Phase 6 was complete, and unblocked Phase 7

Phase 6 built **procedure encoding** (`BUILD_PLAN.md` row 6) against an acceptance set `A-1`…`A-8`
frozen before any code existed. The map can now say not just what exists, but **how far we got**.

```bash
python3 -m tools.blueprint completeness
```

- **Three states, per node, from evidence** — `sketched` · `documented` · `verified`. The measured
  counts are derived, so read them from the command rather than from here — this line carried a
  stale triple for three commits, which is `RULES.md` Rule 2 catching the file that states it. The
  claim that matters is stable: **`verified` is 0**, and the zero is the honest one — `verified`
  demands a stamp that still covers the owning document's body, and no document that owns a
  container is governed yet. That is the charter's purpose 2 as a number instead of an intention.
- **The ladder is enforced, not merely reported.** Each container declares a `depthFloor` it cannot
  fall below — and cannot write *beneath* its own measurement either, because a floor with slack is
  a regression scheduled in advance.
- **The six-step lifecycle** — tag / wire / date / version / changelog / stamp — per governed
  document, each step read from the artifact that owns it. `docs/process/AUTHORING_CONTRACT.md` is
  the contract, `skills/doc-lifecycle/SKILL.md` is how to carry it out, and **neither enforces
  anything**: the existing gates keep doing that, and a probe asserts every guard the contract
  credits is really in the registry.

**`OG-198` was closed by the phase that accepted it, not the phase that measured it** — the six
undocumented modules are documented and no container reports `sketch`. Four containers now sit at
`shape` because a `__main__.py` shim has no public definitions by design; widening rung 2 to fix
that would have raised four floors in the same change that authored them, so it is `OG-204`,
scheduled to Phase 7. The pattern `OG-198` existed to refuse, refused again one layer up.

---

## ✅ The Phase-6 closeout — what it swept, and the false green it found

**A gate that had been dead for two phases.** `cross_doc` refuses a `SCHEDULED (Phase N)` row whose
phase the plan marks COMPLETE, and it reads that marker **inside phase N's own table row**. Phases
1-3 carry one; phases 4, 5 and 6 shipped without one, because completion had migrated into the
status paragraph at the top of the file. So the branch could not fire, and `OG-07` and `OG-63` —
both deferred to Phase 4, both finished *inside* Phase 4 — sat in `## Open` ever since while every
gate reported clean. That is `OG-210`, and `L-38` is the lesson: **a convention a gate reads, and
that nothing enforces, is a gate with an expiry date.**

Closed class-first: `CONS-13` reconciles the plan's prose against its row markers both ways and
fails when it can derive neither side; `phase_rows` and `marks_complete` are exported so the two
readers share one definition; phases 4-6 carry their markers, which made `cross_doc` name both stale
rows at HIGH on the next run — **the fix falsified by the guard it repaired**, not by assertion.

**Swept and clean:** no orphan documents, no dead branches, no worktrees, no stashes, no junk, one
empty ignored directory removed. Two byte-identical file pairs remain and are **declared aliases
with tests behind them** — `project-theme` / `project-theme-dark`, and the vendored
`force-graph.min.js` shared by two independent graph engines. **Do not "tidy" either away**; both
have a suite that fails if you do.

**Phase 7 is defined at full width** in `docs/plan/PHASE7_SCOPE.md` — the nine rows it owns, the
order they must happen in, and the eleven things it must refuse to do.

**Not claimed:** this closeout's own work is implementer-verified only, the same residue `OG-209`
records for Phase 6. Retained counter-examples falsify it in both directions; that is evidence, not
an independent second opinion.


---

## ✅ Phase 5 was complete, and unblocked Phase 6

Phase 5 built **the blueprint layer** (`BUILD_PLAN.md` row 5) against an acceptance set `A-1`…`A-9`
written into the plan before any code existed. Every line passes.

**What changed for a reader: the map stopped being a list of names.** Before this phase
`blueprint/SYSTEM.md` could tell you a module existed and that eleven guards existed, and nothing
about the relationship between them. It now answers, without opening the tree:

- **which container owns this module, and which document owns that container** — 97 of 97 modules
  resolve to exactly one container, and `blueprint verify` exits 1 the moment one does not;
- **how deep it actually is** — `D4`'s C4 ladder, measured from evidence rather than asserted, so
  the map reports *where we stopped* instead of where somebody hoped we had got to;
- **what will refuse me if I change it** — 309 gatekeeper relationships, derived from what the gates
  themselves import, run as a subprocess, and name — rather than from a table anybody maintains;
- **the six surfaces Phase 4 measured itself opening the tree for anyway** — `blueprint/SURFACES.md`
  carries the schemas, the configuration and its environment variables, the CLI command and flag
  inventory, the guard contract, the figure kinds, and what each health check *asserts*.

**One file in that map is authored and everything else is derived.** `system.spec.json` carries only
the judgements no artifact owns — the containers, their purpose, their owning document. `verify`
checks every fact in it against the tree, which is the only thing that keeps a judgement file from
becoming the hand-kept overview this whole layer exists to replace.

**Phase 6 ran two verification rounds, and BOTH refuted the work.** Round 1 (three verifiers,
each handed the claim and never the diff) refuted the headline exit condition: the published state
definitions were not what the code measured, three of six lifecycle steps did not read the artifact
they name, and the depth ratchet was an equality lock a one-line edit defeated. Round 2 sent those
fixes back to the verifiers that found them, and **both refuted the fixes** — a definition corrected
in the code and the docstring but **not in the rendered artifact readers open**, and a ratchet
defeated by adding one commit, because its memory was `HEAD` and `HEAD` is written by the commit
under scrutiny. The memory is now the highest floor ever committed across the spec's history, the
enforcement is `CONS-12` against the real repository, and both attacks are falsified in labs with
genuine history. The residue — those round-2 fixes are implementer-verified only — is `OG-209`.

**Five independent verifiers refuted Phase 5's headline exit condition, and they were right.**
Each was handed the CLAIM and never the diff, and worked read-only against the committed sha. The
gatekeeper column — the one thing Phase 5 added over Phase 4 — was wrong in *both* directions: a
bare substring test made a gate that `import`s and executes a module invisible (15 relationships),
while the root node `tools` collected 38 gatekeepers because every gate contains that substring.
The CLI surface published `python3 -m tools.project_index`, **a command that cannot run**. Eight of
26 environment variables were synthesised from a convention neither resolver follows. And the class
root of `OG-166` turned out to be unfixed in a fourth consumer — `CONS-07`, the check that owns the
*hash-locked rulebook's* citations, still resolved them against raw text, so a symbol appearing only
in a comment satisfied it.

**The fixes then went back to the verifiers that found the defects, and a second round found them
incomplete** — including one CRITICAL where the corrected data reached `SYSTEM.json` and never the
rendered document, and one regression the first fix introduced (the git moat reporting that nothing
guards it). Both rounds are written up in `CHANGELOG.md` `[0.6.0]`. Three lessons worth carrying: **a probe written to match your implementation's scope cannot see your
implementation's blind spot** — two of mine globbed the same pinned directory their subject did —
**a substring test is not a resolution**, which is `LESSONS.md` L-24 arriving for the fourth and
fifth time in this repository; and **modelled is not published** — a fix that lands in the derived
model but not in the rendered document has not closed the finding it was written for.

**Two findings the phase raised on itself, both recorded rather than quietly fixed:**

- **`OG-198`** — six modules have no docstring, so four containers measure at depth 0. Deliberately
  **not** fixed by the session that built the ladder: six one-line docstrings would have moved every
  one of them within minutes, and a metric tuned by its own author in the run that introduced it has
  stopped measuring anything. Phase 6 accepts it by name.
- **`OG-199`** — docgen's dependency-graph renderer draws every edge as a straight line between two
  centres and `Edge` carries no waypoints, so a graph this dense cannot be drawn cleanly at any
  placement (measured across four ELK algorithms, at two levels of granularity; the count never
  reached zero). ELK's own half is clean — **0** placement findings — and `blueprint layout`
  deliberately writes **no SVG** rather than emit a diagram the collision gate refused.

**A defect the phase found in a neighbouring guard and fixed at the class level.** Seventeen gates are
named with a dot, so every one of them is shaped exactly like a `module.symbol` citation. Adding a
register row that named `tools/docgen/visual.py` switched on checking for a `visual.collision`
written months earlier as a gate token, and `symbols` reported — correctly by its own rule, wrongly
in fact — that `visual.py` defines no `collision`. The guard now reads the gate universe from
`PRECEDENCE` itself, so it cannot drift from the gates that exist, and both directions are retained.

---

## ✅ Phase 4 was complete, and unblocked Phase 5

Phase 4 built **document identity + archive** (`BUILD_PLAN.md` row 4) against an acceptance set
`A-1`…`A-9` written into the plan before any code existed. Every line passes; two of them deviated
from what was first written, and both say so in place rather than being quietly reworded.

**No row blocks Phase 5.** The two that Phase 4 raised were closed on 2026-08-24, both by the
session that raised them — so both closures were handed to independent verifiers, because
`DEEP_VERIFICATION_PASS.md`'s load-bearing law is that whoever fixed the work must not be the one
who verifies it. **Both verifiers came back with real defects, and both were right** — `OG-195`
(the `OG-191` closure was incomplete four ways, including a 17th gate still invisible because it is
written as `gate=GATE` against a module constant) and `OG-196` (the quantity detector missed the
very repro that closed `OG-194` once re-punctuated, and refused a build on a patent number). Both
are fixed and recorded. That round is why separation of duties is worth paying for: neither defect
was reachable from inside the work that produced it.

- **`OG-191`** — sixteen emitted gate labels contained a dot, which CONS-04's label regex could not
  match, so none had a position in the precedence spine and a **blocking** finding from any of them
  sorted below every advisory. Closed by widening the pattern and then ranking and mapping all
  sixteen from the messages they actually emit: `.source` → row 8, `.collision` → row 9,
  `.rule`/`.bounds` → declared exempt because no second law contends with "bar chart has no items".
  The same blind pattern was found in a second consumer and widened with it.
- **`OG-194`** — L16 was unenforced for quantities written into a structural figure's free text.
  Closed by detecting a *quantity* — currency, percentage, thousands-separated — rather than by
  demanding a data series from every flowchart, which is the provenance theatre those kinds were
  exempted from. `Stage 2` and `HTTP 200` are identifiers and stay accepted.

**One correction landed rather than being deferred:** the `identity` guard's docstring claimed a
forged-to-match archive would be *"correctly refused here"*. It would not be — body, snapshot and
recorded sha256 can be edited in lockstep. The false claim is deleted and the real bound is stated
where a reader meets it (`OG-193`, `NOT_A_DEFECT` on `OG-46`'s reasoning: self-certification is the
accepted bar, and its defence is a reviewable diff, not detection).

Pass 8's residue (`OG-190`) remains scheduled to Phase 7, unchanged.

| pass | date | commit | lanes | findings | what it attacked |
|---|---|---|---|---|---|
| 6 | 2026-08-22 | `c956619` | 11 | **80** — 4 CRITICAL, 27 HIGH, 37 MEDIUM, 12 LOW | Phase 3's own work |
| 7 | 2026-08-22/23 | `35cd4f8` | 12 | **91** — 7 CRITICAL, 34 HIGH, 29 MEDIUM, 21 LOW | **Pass 6's fixes** |
| 8 | 2026-08-23 | `ba0294a` | 13 of 14 | **129** — 4 CRITICAL, 45 HIGH, 53 MEDIUM, 27 LOW | never-executed surfaces, the exemption family, the counter-examples themselves |

**Every finding from all three passes is closed** — Pass 6 dispositioned to `OG-78`…`OG-93`, Pass 7 to `OG-94`…`OG-139`, Pass 8 onward from `OG-140`; derive the live span with `grep -oE '^\| OG-[0-9]+' docs/process/OPEN_GATES.md | sort -u | tail -1`. Two deliberate deferrals that
carry their reasoning: `OG-116` (built, measured, rejected — the fix reported 11 correct sentences to
catch one wrong one) and `OG-136` (CI on the VPS2 runner — Phase 7 work, and an operator action).

Each verifier was handed a *claim to attack* and never the diff; the live tree was read-only;
falsification happened in disposable `git archive` labs.

**Pass 7's lesson, in one line: five of six Pass-6 narrowings had a hole one step over from where
the fix landed.** `LESSONS.md` `L-26` was written during Pass 6 and demonstrated against Pass 6.

**It broke the claims, which is what it is for.** The most valuable single result: `stamps` was
reporting a **false green on the live tree** — found independently by three agents — on the document
a crashed session is told to read first. The narrowing that had closed the same guard's "blanket
amnesty" hole *in the same session* had moved the hole rather than closing it.

Raw findings verbatim: `docs/process/VERIFICATION_LOG.md` Pass 6. Disposition: `OPEN_GATES.md`.
What changed: `CHANGELOG.md` `[0.4.1]` and `[0.4.2]`. The lessons they paid for: `LESSONS.md` `L-26`–`L-31`.

**How the system fits together is now written down**: `docs/design/ARCHITECTURE.md` — outer shape,
layering, the document journey, six gate boundaries, the three deliberate fail-**open** paths, and
what is deliberately *not* guarded.

## ✅ The phase gate is satisfied for Phase 5

The operator's phase gate — *a phase does not begin while a known defect is open* — is
**satisfied**. `docs/process/OPEN_GATES.md` carries no blocking row of any phase number. Derive it,
and do not narrow it to one number:
`awk -F'|' '/^\| OG-/ && $4 ~ /BLOCKS/ {print $2, $4}' docs/process/OPEN_GATES.md`. The register's
vocabulary writes the label with the literal NEXT phase number, so an accounting that measured
`BLOCKS_PHASE_3` specifically was structurally incapable of seeing the only failure it exists to
report (`OG-172`). The `counts` guard now re-derives the number from the `## Open` table at CRITICAL
severity, so the sentence in `BUILD_PLAN.md` cannot drift from the register again.

Seven verification passes are recorded in `docs/process/VERIFICATION_LOG.md`. **The total is not
restated here** — it was carried as `379` across three passes, never re-derived, and two Pass-6
verifiers reported it false with no register row to show for it (`OG-145`). Derive it:
`grep -cE '^\| P[0-9]+-[0-9]+ \|' docs/process/VERIFICATION_LOG.md` for the tabulated passes.
Every finding is fixed, demoted to
`NOT_A_DEFECT` with reasoning a future verifier can attack, or scheduled to a phase whose
`BUILD_PLAN.md` row **names that work** — which is the only deferral the gate permits.

**The scheduled rows are not enumerated here.** This sentence used to list them, said "Five" and
then named six, and the register showed four — a hand-maintained enumeration that disagreed with
its own count *and* with `docs/process/SESSION_STATE.md` (`OG-90`). Derive it:

```bash
awk -F'|' '/^\| OG-/ && $4 ~ /SCHEDULED/ {print $2, $4}' docs/process/OPEN_GATES.md
```

**Start with `docs/CHARTER.md`.** Phase 3 built the corpus checker, and this repository's own
tracked documents are the corpus it is pointed at — not three fixtures. The count is not restated
here on purpose: `docs/CHARTER.md` states it once, `CONS-09` and the `counts` guard both re-derive
it, and the two places this file used to state it disagreed with each other (`OG-90`). That is purpose 2, and it is
what turns the residual doc-claim findings from a hand-maintained list into a gate.

## The registers — read these instead of remembering

| file | holds |
|---|---|
| `CHANGELOG.md` | Every change: date, time, version, file, section. Build-work versioning. |
| `docs/process/OPEN_GATES.md` | **Everything not done** — each with severity, disposition, evidence, and what closing it means. |
| `docs/process/RULES.md` | **The two preventive rules**, measured from 203 defects: no assertion without a retained counter-example; a document never restates a fact code owns. Read with `LESSONS.md` — that one is after-the-fact, this one is before. |
| `docs/process/LESSONS.md` | One numbered lesson per real defect here — the count is not restated, because it changes every session. Re-derive it: `grep -oE '^## L-[0-9]+' docs/process/LESSONS.md \| tail -1`. |
| `docs/process/ABSENT_PATHS.md` | Paths this repo names but deliberately does not contain, with reasons. Machine-read by `CONS-06`. |
| `PROVENANCE.md` | Hardening history + risks R1–R6 with bounds, owners, triggers. |
| `docs/CHARTER.md` | **What this project IS** — and the two purposes it serves at once: build the engine, and be the engine's own test corpus. Read before planning any phase. Carries the anti-drift rule. |
| `docs/process/THREAT_MODEL.md` | What the git moat defends against and what it cannot. Normative for `tools/hooks/*`. |
| `docs/process/SESSION_STATE.md` | **Read this first after a crash.** The stamped, per-item checklist of what the last session actually finished, with the proof for each — so no work is lost and none is done twice. Its `## What is NOT done` section points here. |
| `docs/process/VERIFICATION_LOG.md` | **The raw findings of every deep pass, verbatim**, before any curation. Read it to answer *"what did the pass actually say?"*; read `OPEN_GATES.md` for *"what is still open?"*. |
| `docs/design/doc-system/CLASSIFICATION.md` | The header, the three tiers, surface, and the L14 placement rule — the normative statement 18 code sites cite. |

---

## First command after a reboot or fresh clone

```bash
cd <your clone> && \
  (python3 -c 'import yaml' 2>/dev/null || python3 -m pip install --quiet --user PyYAML \
     || python3 -m pip install --quiet --break-system-packages PyYAML) && \
  bash tools/hooks/install.sh && \
  (cd tools/visual-engine && npm install --no-audit --no-fund) && \
  (cd tools/mermaid-engine && npm install --no-audit --no-fund) && \
  python3 -m tools.health --full
```

**PyYAML is a real dependency, not a nicety** — the doc-system header parser imports it, so on a
`python3` without it the documented bootstrap ends UNHEALTHY with 6 failures. No handover document
mentioned it before 2026-08-20. Do **not** install `tools/docgen/requirements.txt` for the core
path: it also pins `weasyprint`, which only the PDF export needs.

**`tools/hooks/install.sh` is not optional and is why this block changed.** `.git/hooks/` is not
version-controlled, so the git moat cannot arrive with a clone — it has to be installed once per
checkout. `STRUCT-03` and `STRUCT-04` **fail** when the hooks are missing, so a fresh clone that
skips this step reports a red engine that is not actually broken. The installer is idempotent; re-run
it after every pull.

`tools.health` is the single entry point — structure, rule layer, cross-file consistency, build, and
both npm suites, in that order. **It replaces three of the four: both packages' `npm test` plus `project_index verify`.**
`npm run simulate` (22 acceptance simulations) is still a manual step — nothing in `tools/health`
invokes it, and a green `--full` does not cover it. Exit 0 means green;
it never reports SKIP as a pass, and it appends one line per run to `.health/runs.jsonl`.

> **`npm test` must run before `npm run simulate`** if you run them manually — `simulate` rewrites
> the goldens `npm test` compares against. The documented `&&` ordering is load-bearing
> (`LESSONS.md` L-05).

---

## What Phase 5 delivered

- **`system.spec.json` + `blueprint verify`** — the authored decomposition, and the gate that checks
  every fact in it against the tree. Seven drift classes, each planted in a throwaway copy, shown
  red, restored: an empty package, an empty module, an unassigned module, an ambiguous claim, an
  untracked owning document, a duplicate container id, and a stale committed map. **There is no
  catch-all container**, deliberately — one would switch the `unassigned` finding off permanently,
  and that is the finding that fires when somebody adds a package and forgets the decomposition.
- **The depth ladder** (`D4`) — six rungs, contiguous, measured from evidence: a docstring, an
  enumerable inside, a gatekeeper, a retained counter-example, a governed document claiming a
  verified state. A container is only as deep as its shallowest module. At Phase 5's close nothing
  reached `detail`, honestly, because no governed document claimed a verified state; the Phase-7
  close changed that — `docs/process/THREAT_MODEL.md` is governed and stamped `verified`, and the
  `moat` container it owns now reaches the top state (`OG-09`, `OG-207`).
- **Gatekeepers, both directions** — what guards a module, and what a module emits. The emitted half
  imports `_gate_labels_via_ast` rather than copying it; `OG-195`'s closure note recorded that this
  helper had already been the second consumer of one root twice, and this is the third.
- **`blueprint/SURFACES.md`** — the six inventories, each derived from the artifact that owns it.
  Building the CLI one found two defects in its own first version: nested subcommands flattened, so
  the map advertised a `cut` command that does not exist rather than `archive cut`; and unassigned
  `add_parser` calls invisible, so the blueprint package reported **no commands at all**.
- **ELK auto-layout** (`D5`) at zero new dependency — `elkjs` was already in the tree under the
  mermaid engine. The gap rule docgen enforces is encoded in the layout options instead of iterated
  by hand, which is the cost D5 named; the result is fed to docgen's own collision gate, and the
  verdict is split into what ELK owns (placement — must be zero) and what the renderer owns
  (routing — `OG-199`).
- **The derived SQLite index** (`D1`) with FTS5 — gitignored, rebuildable, never authoritative, and
  it **refuses to write an empty one**. `query` runs the canonical joins; `search` runs full text
  over the corpus.
- **One duplication removed rather than left** — the Phase-5 probes needed a throwaway-lab helper
  `test_corpus_check.py` already had, and writing the second copy WAS the finding: the two had
  already drifted. Both now import `tools/tests/lab.py` (`RULES.md` Rule 1).

## What Phase 4 delivered

- **Document identity on `DocHeader`** (`OG-07`) — `version`, `revision`, `produced_by`,
  `verified_state`, all optional, so every document that predates them parses and validates
  unchanged. `revision: 0` is a claim with teeth: it asserts the live bytes ARE the archived bytes,
  and the archive re-derives that rather than believing it.
- **The archive** — `docgen archive cut` / `docgen archive list`. Snapshots live under a per-document
  id in `docs/archive/`, beside a machine-written history table carrying only what a directory
  listing cannot re-derive: date, commit, who cut it, and the snapshot's sha256. **Supersession is
  derived, never stored** — a version is superseded exactly when a higher one exists.
- **`docs/current/` was deliberately not created**, though `BUILD_PLAN.md` row 4 names it. The live
  tree already serves that role: relocating every governed document into a parallel directory would
  break every path every other document cites, for nothing the archive does not already give.
- **Three documents frozen**, and one superseded the same day: `CONTRADICTION.md` reached v2 because
  the provenance work below made its row 8 fire for the first time, so its recorded outcome stopped
  being true. The gate caught the drift **before** v2 was cut, and v1 survives byte-identical.
- **Figure provenance is a gate** (`OG-63`) — RULEBOOK L16 was enforced for two figure kinds out of
  eleven; every other numeric spec declared `data_sources` with an empty default nothing read.
  `EChartsFigureSpec` gained the field it never had. The gate's own new edge was attacked and
  closed: a source with an empty `ref` satisfied a non-empty-list check completely.
- **`docgen build` reported BLOCKED and wrote the artifact anyway** — older than the gate, found
  while wiring it. Every write is now gated on the pre-format blocking findings, so the header
  findings that were already being ignored are covered too.
- **A stamp could never have been accepted.** The `stamps` guard compared a stamped file against its
  stamped commit with `git diff`, which also sees the stamp line — and the file at the commit a
  stamp names can never contain that stamp. The accepted state was unreachable, so the guard could
  only ever fire. Both guards now compare the **body**, stamps stripped from both sides;
  `PROVENANCE.md`'s real drift is still detected, verified rather than assumed.

## What Phase 3 delivered

- **`tools/corpus_check/` — a guard set over this repository's own tracked documents**, not over
  fixtures (`docs/CHARTER.md` purpose 2). `python3 -m tools.corpus_check` exits 0 on a clean corpus;
  `tools.health` runs it as `CONS-11`, so there is still one command to remember.
- **Every guard was falsified red before being trusted**, and the failing input is retained in
  `tools/tests/test_corpus_check.py` — 71 → 111 counter-examples, run by `SUITE-05` every pass.
- **One Markdown table reader** (`tools/lib/md_table.py`). Five readers, two dialects, measured
  disagreeing on the manifest's own header cell; now one, with the four previous ones delegating.
- **`OG-64`/`OG-65`** — Gate 10 now derives contrast pairs from the built stylesheet, and the raster
  exports follow the theme instead of baking a dark ground.
- **`OG-73`** — the second document engine is deleted; its only document was converted to the
  canonical convention, taking the governed corpus 3 → 4.
- **`OG-74`/`OG-75`** — the register carried eleven duplicate primary keys and five rows had lost a
  column. Renumbered, restored, and both classes are now refused by the `register` guard.

## What Phase 2 delivered

- **`build --cached`** — the cache is on the CLI, `build` takes one or many documents as a corpus,
  and every cached run prints a measured line. A second build of an unchanged 3-document corpus:
  **3.359s → 0.003s**, `0 reused / 3 rebuilt` → `3 reused / 0 rebuilt`.
- **The git moat is live** — `tools/hooks/pre-push` (engine health + a secret scan of the pushed
  commits) and `tools/hooks/pre-commit` (classification placement + a secret scan of the index),
  both installed by `tools/hooks/install.sh` and both verified live by health.
- **Health logs by default** — append-only JSONL at `.health/runs.jsonl`.
- Closed: `OG-10`, `OG-14`, `OG-15`, `OG-24`. Checks went 20 → 23.

## What the deep pass found — read this before trusting anything green

Phase 2 was reported complete, green, and falsified four ways. Eleven independent agents then found
**two CRITICAL defects in exactly that work**:

1. **The secret gate was reading the wrong artifact.** The pre-push hook scanned the *working tree*
   while certifying *pushed commits* — so committing on a side branch, switching away, and pushing
   sailed through clean. All four original falsifications had put their probe in the working tree.
2. **A cache hit bypassed a blocking gate.** The cache key covered the document and `*.py` but not
   the rule layer, so editing `DOC_MANIFEST.md` to make a document illegal left it building green
   from cache.

Both are fixed and re-falsified; the generalisations are `LESSONS.md` **L-15** and **L-16**. The
standing lesson underneath: *a gate proven to fire has not been proven to be looking at the right
thing.*


> **`--no-verify` bypasses ALL of this, silently.** `git commit --no-verify` and
> `git push --no-verify` skip every hook with exit 0 and no output. Unlike `ENGINE_SKIP_PREPUSH=1`
> / `ENGINE_SKIP_PRECOMMIT=1`, which announce themselves loudly by design, git's own flag leaves no
> artifact for an audit to inspect. **No client-side hook can defend against it** — closing it needs
> a server-side required check, which is why it is `OG-31` and scheduled to Phase 7 rather than
> claimed as fixed here. Two things reduce the blast radius today: pre-push scans **every commit in
> the pushed range**, so a secret committed with `commit --no-verify` is still caught when the push
> happens normally; and the same is now true of classification placement.

---

## Standing rules for every session on this repo

1. **Terminate verification loops on the checker's exit code, never on "I stopped finding things."**
2. **Deliberately falsify every new gate before trusting it.** Show the red, then restore green —
   and put the probe **only** in the artifact the gate certifies, nowhere else (L-15).
3. **Grep the outputs, not just the source.** Every defect in the last three passes was invisible in
   source and visible in rendered or executed output.
4. **A stamp on an edited body is invalid.** Re-harden or mark `NEEDS RE-HARDENING`.
5. **A planned thing is never written in the present tense.**
6. Run `~/.claude/scripts/secret-scan.sh` before any `git add`. Never hand-roll the patterns.
7. Commit with explicit paths when two sessions might share the tree.
8. **Every phase ends with the deep verification pass** (`docs/process/DEEP_VERIFICATION_PASS.md`) —
   assumed, never requested.
9. **Whoever did the work never verifies it.** Fresh verifier agents that never saw the
   implementer's reasoning. The implementer may orchestrate and synthesise, never green-light.
10. **Write it down as you go.** A finding held in context is lost to the next compaction or crash.
11. **Never mutate the tree while verifiers are running** (`LESSONS.md` L-09).
12. **Never pipe a gate into `tail`/`head` and then test `$?`** (`LESSONS.md` L-12).
13. **Any skip-if-unchanged optimisation inherits the contract of everything it skips** (L-16).
14. **An exemption marker is a switch that turns a guard OFF.** Audit every entry against the
    corpus — count what it is currently suppressing — not against what you meant it to mean
    (`LESSONS.md` L-23).
15. **An environment fact is not a finding about the artifact.** A missing dependency is a SKIP with
    its cause named, never a FAIL — a gate that fails closed on the innocent teaches people to
    bypass it, and this one took the whole moat down (`L-25`).
16. **Keep the positive control.** The defect above was invisible to twenty adversarial cases and
    obvious to the one asking whether a clean push still works.
17. **`--no-verify` is a total, silent bypass of the moat** — never use it except to reproduce a
    gate defect deliberately, and say so in the report when you do (`OG-31`).

---

## Decisions already taken — do not re-litigate

Full reasoning in `docs/plan/BUILD_PLAN.md` §2. Summary:

- **D1** Documents are the source of truth; SQLite is a **derived, gitignored, rebuildable index**
  (stdlib `sqlite3`, FTS5 verified available — zero new dependency).
- **D2** **Saga: do not install.** A Jira-like task tracker; we need artifact/claim governance, and
  it would become a second source of truth.
- **D3** Reuse git for history; build only the semantic layer on top.
- **D4** Adopt the **C4 depth ladder** (Context → Container → Component → Code) as the encoded
  procedure — a proven standard rather than a private invention.
- **D5** **Wire ELK for auto-layout — already in the tree** (`elkjs`, transitive via
  `beautiful-mermaid`). Zero new dependency.
- **D6** `d2` and `dot` are installed and may be **optional** renderers with graceful degradation.
  Never required.
- **D7** Model routing is **per phase**: strong model writes spines + annotates only; cheap model
  fleshes, loops, resolves; the script terminates the loop.
