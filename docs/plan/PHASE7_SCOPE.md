<!-- title: PHASE 7 SCOPE -->
# Phase 7 — the work it owns, and the work it must refuse

**Status:** PLAN — settled. **Written 2026-08-29** at the Phase-6 closeout, by the session that
closed Phase 6 and will not be the session that runs Phase 7.

`docs/plan/BUILD_PLAN.md` row 7 is one table cell. This is that cell at full width: every deliverable
Phase 7 owns, the order they have to happen in, and — the half that is usually missing — **what
Phase 7 must decline to do**, with the reason for each refusal written down where it can be argued
with rather than rediscovered.

`docs/plan/NEXT_SESSION.md` is the operating brief (how to start, the standing constraints, what
green looks like). This is the scope. Neither restates the other.

---

## 1. Phase 7 is different in kind from the six before it

Phases 1-6 **built** things. Phase 7 **proves** them, and the proving is the deliverable. That
single sentence decides almost every scoping question below: work that adds capability enlarges the
surface being verified *while it is being verified*, and is therefore out of scope even when it is
obviously good.

Two things follow, and they are the phase's whole character:

* **A verification phase does not converge on its own.** A completeness critic's question — *what
  did you never look at?* — can never return empty by construction. So the acceptance set is what
  ends the phase, and `RULES.md` Rule 5 (write it first, freeze it, prove at the close that it was
  never amended) is load-bearing here in a way it was not in a build phase.
* **Phase 7 is the phase where the verification debt comes due.** Three phases have now closed with
  round-two fixes that were written by the implementer and checked only by the implementer's own
  probes. That is recorded honestly — `OG-190`, `OG-203`, `OG-209` — and it is the largest single
  item of work below.

---

## 2. The work Phase 7 owns

Nine register rows, named in `BUILD_PLAN.md` row 7. A `SCHEDULED (Phase N)` deferral is only
honoured when the phase's own row names the key, so this list and that row move together or not at
all (`OG-171`), and `cross_doc` fails HIGH when they disagree.

| row | sev | the deliverable, stated as something falsifiable |
|---|---|---|
| `OG-31` | CRITICAL | A push carrying a planted secret with the verification-bypass flag is **rejected by something that is not a local hook**. Demonstrated by doing it, not asserted |
| `OG-09` | HIGH | `PROVENANCE.md` carries a hardening stamp that references a real commit and still covers the package at that commit |
| `OG-190` | MEDIUM | Pass 8's closures are re-attacked by verifiers who were handed the CLAIM and never the diff |
| `OG-203` | MEDIUM | The same, for Phase 5's round-two fixes |
| `OG-209` | MEDIUM | The same, for Phase 6's round-two fixes |
| `OG-207` | MEDIUM | `verified` is reachable: a decision about what evidence a node needs, and the gate that reads it |
| `OG-205` | MEDIUM | `CHANGELOG.md` stops being structurally exempt from the `counts` guard, or the exemption is stated with its bound |
| `OG-204` | LOW | Rung 2 of the depth ladder gets its evidence decided by someone who is not the ladder's author |
| `OG-136` | LOW | CI is wired. **Operator action — see §5** |

**One adjacent row, not accepted, worth knowing about.** `OG-193` (the archive can be forged in
lockstep) is `NOT_A_DEFECT` on `OG-46`'s reasoning, and its row says removing the
self-certification *"is `OG-31`'s territory and Phase 7's"*. If Phase 7 lands a server-side record,
`OG-193`'s bound narrows as a side effect. That is a **consequence to notice and write down**, not a
row to open.

### What each of these actually asks for

**`OG-31` — the server-side half of the moat.** The bypass flag is a total, silent bypass, and **no
client-side hook can defend against it**: the hook is not consulted. That is why this is a Phase-7
*deliverable* rather than a carried risk — it is the only place it can close. The exit condition
names a hostile act deliberately, because "we added a check" and "the attack is refused" are
different claims and only the second one is worth anything.

**`OG-09` — the stamp.** The stamp no longer covers the tree, and this is the row that makes
`verified` reachable at all: a node reaches `verified` only when its owning document is governed
**and** carries a stamp that still covers its body. Stamp **last**. A stamp on a body that is still
changing is invalid by `HANDOFF.md` standing rule 4, and Phase 7 changes bodies right up until it
stops.

**`OG-190` / `OG-203` / `OG-209` — the reverification.** Roughly a hundred closures across Pass 8
and its waves, plus two phases of round-two fixes. The discipline is `DEEP_VERIFICATION_PASS.md`'s
and it is absolute: **whoever built or fixed a thing never verifies it**, verifiers are handed the
CLAIM and never the diff, and the tree does not move while they run. Hand each verifier an explicit
commit sha.

**`OG-207` — making `verified` mean something.** It is currently zero across every node, and that
zero is honest rather than embarrassing. The question Phase 7 has to answer is *what evidence should
a node need*, and the answer has to be reachable for more than a handful of nodes or the state is
decorative. See §3 on why this must be decided before `OG-09`'s stamp, not after.

**`OG-204` — rung 2's evidence.** The rung tests "are the contents enumerable" by counting **public**
top-level definitions, which under-reads a delegation shim and an all-private module. It is
deliberately unresolved: `OG-198` and `OG-204` are both open records of the rule that a measurement
is not tuned by the session that benefits from tuning it.

---

## 3. The order, and why it is not arbitrary

1. **Health floor first**, before touching anything. `--full`, so a SKIP is a failure.
2. **Acceptance set second**, frozen and hashed, before any other work. Each `-k` token must select
   its *whole* group — a line saying "selects at least one test" is satisfied by a token matching
   one probe of eleven, which both Phase 5 and Phase 6 paid for.
3. **The reverification third**, while the tree is still quiet. It is read-only, it is the biggest
   item, and every later edit invalidates the sha the verifiers were given.
4. **Fixes fourth**, driven by what came back, severity-ordered.
5. **`OG-207` and `OG-204` fifth** — the measurement decisions. Both change what `verified` and
   rung 2 *mean*, so they must land before anything certifies a body against those meanings.
6. **`OG-31` sixth.** It is independent of the corpus work and can proceed in parallel, but its
   proof (the hostile push) must run against the final state.
7. **`OG-09`'s stamp LAST, and derived artifacts rebuilt immediately before it.** Every later edit
   restales both. This ordering is not a preference; getting it wrong is how `OG-09` came to exist.

### The model split — which lane gets which tier

`BUILD_PLAN.md` **D7** settles the principle: model routing is a *per-phase process decision*, and
the strong model writes spines and judges while the cheap one fleshes and loops. This is that
decision made concretely for Phase 7, because this phase's deliverable is **adversarial
verification** and that is the one activity where the tier genuinely changes the answer.

`DEEP_VERIFICATION_PASS.md` states why: *a model checking its own output converges on its own blind
spots — it goes quiet long before it goes correct.* A weak verifier does not return a slower answer,
it returns a **confident green**, which costs more than not running one. Phase 6's second round is
the evidence: the defect it caught was a fix that reached the code and the docstring but not the
published artifact, and that reads as fine to anything doing a surface check.

**Run the session at the top tier and route DOWNWARD from it.** The portfolio routing table puts
*final audits, security-critical design and adversarial verification* in Fable's tier, and that is
this entire phase's description — not one lane of it.

| lane | tier |
|---|---|
| Orchestrator — the acceptance set, sequencing, and the stop/continue judgement | **session tier** |
| The reverification verifiers (`OG-190`, `OG-203`, `OG-209`) | **session tier — never below** |
| `OG-31` — attacking the moat, and proving the hostile push is refused | **session tier — never below** |
| The round that attacks **Phase 7's own fixes** | **session tier — never below** |
| Implementation, document rewrites, applying a decided edit across files | Sonnet |
| Lookups, path checks, mechanical transforms | Haiku |

**Why downward rather than upward.** Both directions require an instruction to be followed, and they
fail differently: forgetting to route a cheap lane *down* costs money, while forgetting to route a
verifier lane *up* costs the phase its only real evidence. **Downward fails safe on the axis that
matters here**, which is why the session starts at the top tier rather than delegating up to it.

**Spend the top tier on this phase, not on a later pass.** Phase 7 *is* the final audit; there is no
second one to save it for. **And the last round — the one attacking Phase 7's own fixes — is the
lane that matters most**, because that is where the implementer-verified residue would otherwise
re-form for a fourth time (`OG-190`, `OG-203`, `OG-209` are the first three).

**One thing to check rather than assume.** `--model fable` is a documented CLI alias — measured
2026-08-29 against `claude --help`, which names `fable`, `opus` and `sonnet` as aliases for the
latest model — but a resolvable alias is not proof of entitlement. If the session did not start at
the top tier, **say so plainly in the first report** and route the verifier lanes up explicitly
through the subagent model override, rather than silently substituting a weaker tier into the one
place the tier changes the answer.

---

## 4. What Phase 7 must REFUSE

Each of these is genuinely tempting, which is why it is written down.

**4.1 — Do not re-litigate the `NOT_A_DEFECT` rows.** They carry reasoning specifically shaped to be
attacked, and re-opening one because it *feels* unresolved is the unbounded loop this register was
rebuilt to stop. **The exception is precise:** if the reverification produces *new evidence* against
a specific row, that row is re-opened — that row, on that evidence, and nothing adjacent to it.

**4.2 — Do not chase `verified` as a number.** Stamping documents whose bodies are still moving to
raise the count would be strictly worse than leaving it at zero, and `docs/process/AUTHORING_CONTRACT.md`
says so already. A false green is the most expensive kind of wrong this project has met; a
*deliberately* false green would be the worst thing Phase 7 could produce.

**4.3 — Do not run a separate "round three" on Phases 5 and 6.** Phase 7's reverification **is**
that round, and doing both is the same work billed twice. `OG-203` and `OG-209` are accepted by name
so this cannot be quietly skipped instead.

**4.4 — Do not build new capability.** No new guards, checks, surfaces, subcommands or engines
beyond what a named row above requires. Anything genuinely worth building is a finding to record,
not work to start. The last phase of a build is not where the surface grows.

**4.5 — Do not add documents to the corpus.** Every new document moves the charter's measured
counts, restales derived artifacts, and invalidates a stamp that Phase 7 exists to make valid.
Amend an existing document instead. If a new one is truly unavoidable, it lands **before** step 7 of
§3, never after.

**4.6 — Do not tune a measurement in the phase that benefits from tuning it.** Rung 2 (`OG-204`) and
`verified`'s bar (`OG-207`) both make numbers move. Decide them on their merits, record the
reasoning, and note explicitly which way the number went — a measurement change that happens to
flatter the phase that made it needs more evidence, not less.

**4.7 — Do not close `OG-31` with a better client-side hook.** The hook is not consulted when the
bypass flag is used. A stronger hook is not a smaller version of this fix; it is a different fix to
a different problem, and shipping it under this row's name would be a false closure.

**4.8 — Do not register the shared runner, and do not make a self-hosted lane a required context.**
See §5. A required status check whose runner label nobody serves does not fail — it queues forever
as `pending`, and blocks every merge **silently**. A self-hosted lane is evidence, never authority.

**4.9 — Do not lower the pinned lint and type ceilings as a goal.** `ruff = 0` and
`mypy --strict = 22` are ceilings that must not be *exceeded*. Driving 22 toward zero is a
refactor, it touches modules the reverification is simultaneously reading, and it is not this
phase's work.

**4.10 — Do not "tidy" the repository.** It was swept at the Phase-6 closeout: no orphan documents,
no dead branches, no worktrees, no stashes, no junk. The two byte-identical file pairs that remain
(`project-theme` / `project-theme-dark`, and `force-graph.min.js` in two engines) are **declared,
documented and test-asserted aliases**, not duplication. Deleting either breaks a suite.

**4.11 — Do not bypass the hooks while closing the bypass.** Not the verification-bypass flag, not
`core.hooksPath`. Phase 7 is the phase that shuts that hole; using it in the process would be
absurd, and it would also be the single most quotable thing in the record.

---

## 5. The one step no agent may perform

`OG-136` — registering this repository with the shared VPS2 runner — is an **operator** action, and
it is not a formality:

* A project agent must not register a shared runner (`~/.claude/rules/ci-cost-control.md` §9.3); the
  runner is operator-owned infrastructure belonging to no project.
* §9.1 is the part that bites: **GitHub does not fail a job whose runner label nobody serves — it
  queues it forever as `pending`, never as `failure`.** A required context pointing at an
  unregistered runner blocks every merge with no error to act on.

**Additive first; required only on measured evidence** (≥14 consecutive days online, ≥10 green runs,
zero queue stalls). Phase 7 may author the workflows. It may not register the runner, and it may not
make the lane required.

---

## 6. What "done" looks like

Repeated here **only** as the scope's own exit condition; `NEXT_SESSION.md` §6 is the operating copy
and the two must agree.

* The frozen acceptance set passes command by command, and is byte-identical to what was frozen.
* The hostile push is **refused**, demonstrated.
* `PROVENANCE.md`'s stamp references a real commit, and `blueprint completeness` reports a non-zero
  `verified` count **as a consequence** — not as a target that was aimed at.
* `tools.health --full` green · `corpus_check` clean · `blueprint verify` clean ·
  `blueprint completeness` exit 0.
* `CHANGELOG.md` carries the `1.0.0` entry; `PROJECT_VERSION` matches; `OPEN_GATES.md` is current.
* Every row in §2 is closed, or re-dispositioned with reasoning a verifier can attack. **A row that
  Phase 7 does not close does not roll forward** — this is the last phase, and there is no Phase 8
  to park it against.
