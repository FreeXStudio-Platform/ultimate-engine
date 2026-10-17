<!-- title: FIELD TRIAL ROUND 1 -->
# Field trial — round 1: can the engine document a FOREIGN project from zero?

**Status:** PLAN — the round log `docs/plan/FIELD_TRIAL.md` §4.7 requires. Written **when the round
was issued**, before any result existed, so the protocol cannot be trimmed to fit the outcome. The
programme is `FIELD_TRIAL.md`; this is one round of it and does not restate it.

**Issued:** 2026-08-31 · **Operator:** the human operator, as adjudicator (`FIELD_TRIAL.md` §2).

---

## 1. What this round actually tests

Not "do the gates still pass" — that is what the `1.0.1` audit established. This round tests **the
product claim itself, on a project that is not this one**:

> Given the engine and a codebase it has never seen, can an operator with no history here produce
> **the complete project document set, its blueprints, its graphs and its JSON** — and can a *second*
> agent then grasp that project from those visuals instead of reading the documents?

That is `docs/CHARTER.md`'s purpose stated as a task, and nothing inside this project has ever been
able to attempt it, because every agent that has touched the repository already had the answers.

Because the subject is **external**, this round also tests the portability claims the engine has
never had exercised: host-root resolution, the configuration chain, and whether the rule layer can
be relocated to serve a host project that is not the engine itself.

## 2. What was handed over

A package on the operator's Desktop containing **four things and nothing else**:

| item | what it is |
|---|---|
| `engine/` | **the instrument** — the engine's machinery and rule layer: the tools, the rulebook, taxonomy, manifest, classification and contradiction table, the method documents, and its own tests |
| `subject/` | **the project to document** — the *Absolute Canonical Framework 1.1.0*: a real governance framework with a Python runtime, eleven numbered domains, `975` tracked files, `27` Python modules and `257` markdown files of its own |
| `SYSTEM-INSTRUCTION.md` | what the engine is for, and the standing rules the operator works under |
| `PROMPT.md` | the task, in eight stages |
| `secret-scan/` | the external scanner the git hooks call; without it the hooks correctly refuse every commit |

**The subject was chosen after eliminating the alternatives, and the elimination is the record.** A
CredMgr v2 was considered and rejected: it already contains **18 document sets built by this engine**
(each document present as source, built HTML, a JSON sidecar and a figure spec, carrying doc-system front matter), so an operator pointed
at it would grade itself against answers already in the folder. CredMgr v1 was rejected for a
different reason — it is JavaScript, and **the blueprint layer's dependency graph is Python-only**
(`OG-243`), so the flagship artifact could not have been derived at all. The Absolute framework is
Python, has never been touched by this engine, and carries no engine artifacts of any kind.

**Removed from the instrument:** all of this project's build history and governance narrative — the
changelog, the handover, the registers, the lessons, the verification log, the session record, the
plans and phase documents, the archive. The operator gets the engine and its method, not the story
of how it was built. **The git history is replaced by a single commit** in both repositories; git
itself stays, because the corpus guards, the stamp checks, the depth ratchet and the staleness check
are git-dependent and cannot run without it.

**Nothing was removed from the subject.** It arrives exactly as it is, including its own 257
markdown files — which are the operator's *source material*, not its output.

**Provenance of the issued text.** The two briefs are hashed rather than copied into this repository,
because a second copy of one text is the drift defect `RULES.md` Rule 2 exists to catch:

| file | `shasum -a 256 \| cut -c1-16` |
|---|---|
| `SYSTEM-INSTRUCTION.md` | `2cc68016cce6a616` |
| `PROMPT.md` | `6e6ff1591d7160e8` |

## 3. The measured starting state — the round's baseline

Measured on the package before issue, pointing the engine at the subject, and recorded here so the
operator's report can be checked against it rather than believed:

| command (engine pointed at the subject) | result on delivery |
|---|---|
| `tools.blueprint build` | **succeeds** — derives `975` tracked files, `27` Python modules, `37` import edges, `257` markdown files |
| `tools.corpus_check` | `5 passed, 4 failed, 2 skipped; 49 findings` over the subject's own documents |
| `tools.docgen.cli check <subject doc>` | blocking header findings — correct: the subject's documents carry no doc-system header yet |

**Feasibility was proven before issue rather than assumed.** The engine really can be pointed at a
foreign project: `ENGINE_HOST_ROOT` resolves the host, `ENGINE_DOC_SYSTEM_DIR` relocates the rule
layer, both are documented in `CONFIGURATION.md`, and the combination produces a real derived map of
the subject and 49 real findings in its documents. **The command names are deliberately withheld from
the brief** — discovering them from the repository is the reachability half of the test, and the
proof above exists so that a failure to find them is read as a discoverability defect rather than as
an impossible task.

**One friction point is known and left in place:** with the rule layer relocated, a bare-name lookup
still resolves under the relocated directory, so at least one locked file is reported missing. It is
surmountable and it is exactly the kind of portability seam this round exists to surface.

## 4. What the round must produce, beyond a green check

A green gate set is **not** the deliverable and the brief says so: it is obtainable by writing very
little and claiming success. The deliverables are the document set, the blueprints, the graphs and
the JSON — and one measurement nothing in this repository has ever taken:

> **Stage 5 of the brief.** Answer a fixed set of questions about the project — its components and
> dependencies, what to change to extend it, its riskiest modules, its gate order, its document
> lifecycle — **from the blueprints, graphs, tables and figures alone, with the prose withheld.**
> Every question that cannot be answered from the visuals is a defect in the blueprint layer, which
> is the exact thing this engine exists to prevent.

## 5. Results

**Run and reviewed 2026-09-01.** The operator returned a `REPORT.md` with eleven findings and a
verdict of *DELIVERS WITH GAPS*. Every finding was re-derived here before anything was changed — a
trial report is evidence, not authority — and the disposition is `CHANGELOG.md` `[1.0.5]`, with each
repair carrying its own `OG-` row and red-first counter-example.

**Against the §3 baseline.** The round produced what it was asked for: seven governed documents with
strict HTML/JSON siblings, 17 embedded figures, three standalone Mermaid diagrams, a verified
`blueprint verify` over an authored `system.spec.json`, a 683-node file graph, and a machine layer
that answered 5/5 of the isolated-agent questions (4/5 on its first pass, corrected). The subject's
own verifier stayed red throughout on subject-owned conditions, and the round correctly did not touch
subject source to make it green.

**Findings by class.**

| class | count | disposition |
|---|---:|---|
| real engine defects | 5 | repaired: `OG-244`, `OG-245`, `OG-246`, `OG-247`, `OG-248` |
| subject-owned, correctly reported | 3 | not this engine's to repair; the subject is read-only by rule |
| refuted | 3 | see below — one was the trial's own packaging |
| design gap, named not closed | 1 | foreign-host registry provenance in `SURFACES.md` |

**The round produced a new class, and this is the signal `FIELD_TRIAL.md` §6's stop rule reads:**
*defects that only exist off the engine's own tree.* Every one of the five repairs was invisible to a
self-check for a structural reason, not by luck — `OG-244` needs a repository large enough for git to
start collecting (3/3 on 1,046 files, 0/3 on this repository's 362), `OG-246` needs a *disconnected*
package graph where this one is fully connected, `OG-247` needs two interpreters with different
dependency sets, `OG-248` needs a host whose directories do not match the builder's expected shape.
A self-check cannot generate any of those conditions. **Round 2 is warranted**, and the class tells it
what to vary: host size, graph shape, environment, and directory layout — not more of the same corpus.

**The most expensive finding was `OG-244`.** `RULES.md` Rule 3 names `tools.draft check` as the
mechanism for the rule that pays for itself fastest, and on a foreign host it did not return a verdict
at all. That is worse than a wrong verdict, and it had been true for every project larger than this
one since the gate was written.

### The trial's own packaging cost it a CRITICAL, and §2 must say so next round

The operator's first and highest-severity finding was *"the received engine cannot certify itself"*,
filed against a `27 PASS / 10 FAIL` health run. The absence it measured is **this document's §2
working as designed** — 26 tracked files are deliberately removed from the instrument, and health
reported their absence correctly. This repository at the same commit measures `HEALTHY — 38 passed,
0 failed, 0 skipped of 38` under `--full --strict`.

The brief never states that the instrument is stripped, so an operator whose first act is to check
the tool it was handed finds it broken and has no way to tell a packaging decision from a defect.
**That is a flaw in the round, not in the operator's judgement** — it spent the trial's first
CRITICAL, and the effort behind it, on the test harness. §2 of round 2's plan must state the removal
where the operator meets it, and give the expected health verdict for the package as issued.

## 6. The bound on what this round can conclude

**This round DOES measure portability** — the subject is external, so host-root resolution, the
configuration chain and the rule-layer relocation are all exercised for the first time. That is the
gap the earlier design of this round could not close.

**What it still cannot measure is language reach.** The subject is Python, and the blueprint layer's
dependency graph reads Python only (`OG-243`). A round on a Rust, JavaScript or Go subject would get
the document layer, the figures and the file-tree graph, but **no derived module graph** — the
flagship artifact. Round 1 therefore measures the engine at its best case for structure, and a
later round on a non-Python subject is what measures the rest.

**Two rules held that make the run safe:** the subject is a **copy**, never the live project
(`FIELD_TRIAL.md` §3 rule 1), and neither repository in the package has a remote, so no action inside
it can reach anything real.
