<!-- title: DOC WRITING DOCTRINE -->
# Doc-Writing Doctrine — the cheapest path to the highest confidence

**Status:** FRAMEWORK — normative. This is a law file, not a suggestion file.
**Origin:** authored 2026-08-19 by Fable 5 as a decision brief for one project's document corpus
(`~/Desktop/CredMgr-Doc-Writing-Strategy.md`), generalised here into a project-independent
framework on operator instruction. The original's evidence base — 98 classified findings with
`file:line` evidence from a real 13,000-line corpus — is the reason this file is normative rather
than advisory. Do not weaken a rule here without evidence of the same weight.

**Independently corroborated 2026-08-19** by this engine's own reverification pass, which found
five shipping defects and a dead theme toggle in a package that had already passed three
"verified" sessions. Every one of them was a *checkable claim that was not checked*. Cross-links
to that evidence are marked **[UE-S4]** below.

---

## 0. The one line

> **Every expensive defect is a claim that was checkable and wasn't checked** — not a design
> nobody was smart enough to get right.

Spend the cheap model on writing, a script on checking, and the expensive model only where
judgement is the actual bottleneck.

---

## 1. The four decisions

1. **The strong model writes skeletons; the cheap model writes prose.** Cheaper *and* better than
   "cheap model writes everything, strong model reviews everything."
2. **Build the mechanical checker before writing anything.** Roughly two-thirds of real defects are
   `grep`-checkable. Buy the script once; it permanently removes the largest error class.
3. **Never terminate a verification loop on "the model stopped finding things." Terminate on the
   checker exiting 0.**
4. **Sequence documents by dependency, not by number.**

Measured expectation versus "cheap writes all, strong reviews all": **60–70% fewer strong-model
tokens, at higher confidence** — because the expensive pass stops being "read 13,000 lines of
possibly-wrong prose."

---

## 2. Why the ordering is the whole saving

A design error caught at **200 lines of spine** costs 200 lines to fix.
The same error caught after full prose costs **900 lines** — *plus* the strong model reading all
900 to find it.

"Cheap writes everything, then strong reviews everything" puts the expensive pass *after* the
corpus exists. That is the single most expensive possible ordering. Spine-first inverts it.

The second saving is subtler and just as large: **reading is far cheaper than writing.** Restrict
the strong model's late pass to *annotation only* — never rewriting — and you buy its judgement
while keeping its output tiny.

---

## 3. The pipeline

| # | Phase | Model | Output | Why this model |
|---|---|---|---|---|
| **0** | Extend the checker | cheap | new guards in `tools/corpus_check/` | Pure mechanics. Once. |
| **1** | **Spine** | strong | Per doc: section skeleton, the *decisions*, the invariants, and an explicit list of every claim that must resolve against source. **~200 lines of dense decisions, not prose.** | Only the strong model should decide what the design *is*. |
| **2** | **Flesh** | cheap | Full write-out: prose, tables, examples, figure briefs, JSON sidecars | Expansion against a fixed spec. |
| **3** | **Loop** | cheap | Run the checker → fix → repeat **until exit 0** | Mechanical, terminates, cheap. |
| **4** | **Annotate** | strong | **Only** `<!-- REVIEW: … -->` markers, inline. **No rewriting.** | Judgement, output-light. |
| **5** | **Resolve** | cheap | Fix each marker, re-run the checker | Mechanical once the defect is named. |

**Phase 2's hard rule:** change no decision. If a decision looks wrong, **stop and say so** rather
than fixing it. A cheap-model silent correction of a strong-model decision is how a corpus loses
its spine.

**Phase 4's hard rule:** change nothing but markers. Prioritise contradictions *between* documents
over anything local — those are the defects no single-document read can find.

---

## 4. The rule that matters most

> **Do not stop a verification loop when the model stops finding things.**

A model checking its own output converges on its own blind spots. **It goes quiet long before it
goes correct.**

Evidence this is not theoretical:
- One project's gates were **green** while **55 false claims** stood.
- Its build log's trap #1, verbatim: *"a green gate is not a correct artifact."*
- One index document claimed for **months** that a test prevented drift. That test had never existed.
- **[UE-S4]** This engine's `npm test` was green while its documented dark/light theme toggle did
  nothing at all, and while its collision gate was blind to an element it drew on every diagram.

Terminate on the checker's exit code. **A script cannot get bored, cannot agree with itself, and
cannot be persuaded.**

---

## 5. Phase 0 — the checker comes first

### The defect taxonomy it must cover

| Defect class | Mechanically catchable? |
|---|---|
| Symbol does not exist in source | **Yes** |
| A stated count disagrees with the real count | **Yes** |
| A cited test does not prove the claim | **Yes** |
| Marked *built*, exists only in tests | **Yes** |
| Marked *built*, unreachable at runtime | **Mostly** |
| Feature never existed, stated in present tense under an approved stamp | **Yes** |
| **Semantics inverted** (direction reversed, and self-contradicted three sections earlier) | **No** |

**≈⅔ mechanical, ≈⅓ semantic.** The mechanical two-thirds were never written because a model was
weak at reasoning. They were written because *nothing checked them* — and the strongest available
model, writing unchecked, lands the same defects.

### Mandatory guards

| Guard | Rule |
|---|---|
| `symbols` | Every backticked identifier must exist in the source tree, or its sentence must be marked `planned` |
| `counts` | Any "the N things that…" must match the real count in source |
| `test-refs` | Every cited test name must exist in the test tree |
| `built-claims` | Anything marked **built** whose only definition is under a test guard, or whose branch ends in an unconditional error, fails |
| `cross-doc` | When two documents enumerate the same set, the sets must match |
| `stamps` | A stamp whose recorded commit no longer matches the file body is invalid |
| `crossrefs` | Every internal link and document reference must resolve |
| `present-tense` | A thing marked `planned` may never be described in the present tense |
| `rendered-output` **[UE-S4]** | Guards run against **built artifacts too**, not only source |

### Two laws about the checker itself

1. **Validate against history, not hope.** Run it against the corpus *as it was* when a known
   defect list was compiled; it must independently rediscover a large share of those findings.
2. **Deliberately falsify every guard before trusting it.** Drop a real symbol, invent a fake one,
   claim a phantom count — each must produce the expected red.

> **A checker that cannot fail is worse than none**, because it converts "unverified" into
> "verified" without doing any work. Read real source off disk; never compare a copied literal
> against itself.
>
> **[UE-S4]** This engine's four correctness gates were each triggered on purpose before being
> reported as working — overlapping labels, an unsourced number, an unregistered id-prefix, an
> unmatched country name. Each refused the build and wrote nothing. That is the standard.

---

## 6. Document order — by dependency, not by number

Errors in foundational documents propagate silently into every document that reasons from them.
One inverted semantic in a foundational document had six other documents quietly reasoning from it.

- **Tier 1 — full strong-model spine, no shortcuts:** the documents everything else derives from
  (concept, data model, security/keys, the core graph or state model).
- **Tier 2 — strong-model spine, lighter:** architecture, threat model, interface/API surfaces.
- **Tier 3 — cheap-model-led, strong model only annotates:** everything else, plus reference and
  index documents.
- **Special case:** a subsystem whose proposals keep coming back `needs-revision` is *genuinely
  undesigned*. Give it its own strong-model spine session. Never fold it into a batch.

---

## 7. Where the strong model is genuinely irreplaceable

Only two things. Everything else is the cheap model plus a checker.

1. **Deciding the target design for unbuilt subsystems.** Judgement about what the system *should
   be*. No script and no amount of prose skill substitutes.
2. **Direction-and-soundness errors.** The archetype: a rule stated as applying "on both sides"
   when the code applies it in one direction only — every individual word plausible, passed every
   gate, and contradicted by the same document's own table three sections earlier. No grep finds
   that. A careful reader does.

---

## 8. Rules that must not be broken

1. **A planned thing is never written in the present tense.**
2. **A stamp on an edited body is invalid.** Re-harden, or mark `NEEDS RE-HARDENING`. Never leave
   an approval on a body you changed.
3. **When one section summarises another, distrust the summary.** One commit wrote *both* "cleared
   to send" (true) and "has gone to the team" (false) — in the same commit. There was never a
   window in which the file was internally consistent. **The summary is the most-read and the
   least-re-derived line in any document.**
4. **Grep the outputs, not just the source.** A brand font survived a "zero residue" sweep because
   it appeared only in rendered HTML. **[UE-S4]** The identical failure recurred here: a dead theme
   toggle and two invisible geometry defects were all found by measuring *rendered output*, and
   none was visible in source.
5. **Never run the full test suite under load.** Contention inside a short critical section fails
   tests that pass idle. Measure load before believing a red.
6. **Two sessions, one working tree: split file ownership up front** and commit with
   `git commit -- <paths>`, never a bare `git commit`.
7. **[UE-S4] Never let a run that regenerates baselines follow a run that checks them.** This
   engine's `npm run simulate` rewrites the goldens `npm test` compares against, so the documented
   `&&` ordering is load-bearing. Read the check result *before* regenerating anything.

---

## 9. Ready-to-use prompts

**Phase 0 — cheap model**
> Extend `tools/corpus_check/` with the guards in `docs/framework/DOC_WRITING_DOCTRINE.md` §5.
> Follow the existing guards' structure. Each must read real source off disk, never compare a
> literal to itself. **Deliberately falsify each guard before trusting it and show me the red.**
> Then run the full set against the corpus and report what it finds.

**Phase 1 — strong model**
> For `<DOC>`: write the spine only — section skeleton, the design *decisions*, the invariants
> that must hold, and an explicit list of every claim this document will make that must resolve
> against source. Roughly 200 lines of dense decisions. **Do not write prose.** Mark every unbuilt
> subsystem `planned` and give it its full target design in decision form.

**Phase 2 — cheap model**
> Fill `<DOC>` from its spine: full prose, tables, examples, figure briefs, JSON sidecar. **Change
> no decision** — if a decision looks wrong, stop and say so rather than fixing it. Then run
> `python3 -m tools.corpus_check` until exit 0.

**Phase 4 — strong model**
> Read `<DOC>`. Insert `<!-- REVIEW: … -->` markers wherever a claim is unsound, a direction is
> inverted, two sections contradict, or a design is weak. **Change nothing else — do not rewrite a
> single sentence.** Prioritise contradictions between documents over anything local.

---

## 10. How this binds to the rest of the engine

- The **checker** is the terminating condition for §4. It is the same discipline as docgen's
  fail-closed render gates, applied to prose instead of geometry.
- The **stamp** rule (§8.2) is the three-pass artifact contract already in force; `stamps` in §5
  is its mechanical enforcement.
- **Claim → source resolution** is `DataSource`/L16 generalised from numbers-in-figures to
  claims-in-prose: a claim with no resolvable source is treated exactly like a number with no
  `DataSource`.
- **Model routing** (§3) is the operator's global model-routing table applied per *phase* rather
  than per *task*.
