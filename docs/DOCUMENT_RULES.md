# DOCUMENT_RULES.md — how documents are written, linked, kept true and read

The rules every project follows when it builds its documents with Ultimate Engine. They were drawn from the engine's
own rules and from what projects that built large document sets with it recorded: what failed, what worked, and what
they removed as redundant. Process rules (who approves, how work is split into packets, when to stop and recalibrate)
belong to the project's framework, not here; this file is about documents.

**This file is locked** — it is listed in `VERSION.json`'s `rulebook_files`. Editing it without following L9 trips the
rulebook hash-gate. The types, their order and their sections are in `document_types.json` (readable copy:
`DOCUMENT_TYPES.md`); the laws and how each is enforced are in `RULEBOOK.md`.

Each rule names how it is enforced: **checked** (a command refuses or reports it), or **review** (no check exists; a
reviewer holds the line). A rule without a check is never described as checked. The findings each rule answers are in
the engine's field-report register; the provisos below say how a rule applies when a project's situation differs.

## Rank: which rule wins

When two rules pull in different directions, the higher rank wins, the lower one is applied as far as it still can be,
and the conflict is written down as a decision record (`ADR`):

1. **Safety and classification** — D15: nothing secret or private leaks, whatever any other rule asks.
2. **Authority** — D4: which source decides what is intended and what exists.
3. **Truth** — D5, D7, D17: one home per fact, claims with their status and proof, stable identifiers.
4. **Verification** — D12, D14, D19: stamps, checks that can fail, checks that give the same answer everywhere.
5. **Structure** — D1, D2, D3, D8, D18: documents first, types and sections, order, links, adoption.
6. **Machine layer and figures** — D6, D9, D10: written versus generated, the map and records, figures.
7. **Form** — D11, D13, D16: writing limits, retirement, the writer's checklist.

These rules sit below the project's own process rules about **who may act** (scope, approval, separation of duties):
the framework decides who may change a document; these rules decide what a correct document is.

---

## D1 — Documents come first, and are where finished work ends

Write the documents before the code they govern. A project starts from its brief (`BRF`), even when the idea is one
sentence; requirements (`REQ`) say what must be true, the architecture (`SYS`) says how, and the plan (`PLAN`) and the
verification plan (`TEST`) say in what order and how it is proven. Code implements documents.

Documents state the **target design**. Where built code differs, the difference is a deviation row in the findings
document (`FND`), never a quiet edit of the design to match the code. Each claim is one of: built and conforming, built
but deviating (with its deviation row), or designed and not yet built. A target is never presented as built.

Work is finished when its document says so: the requirement it closes, the evidence that shows it holds, and the
document's state. **Enforced:** checked — `ultimate-engine doc-map` lists the documents every project needs and which
are missing (`next`); review for the rest.

## D2 — Every document has a type, and its type fixes its sections

The id prefix is the type (`REQ-001` is requirements). The catalog gives each type its purpose, when it is needed,
what it builds on and the sections it must hold, in order. `ultimate-engine new <TYPE> "<title>"` writes a document
with every section in place and links it to the documents of the types it builds on.

A section that does not apply says so: `N/A — <reason>`. A required operational or data section with nothing to show
says `None yet, because …`. A section is never left silently empty and never holds a placeholder.
**Enforced:** checked — `docgen check` reports missing and empty sections, and they block under `--strict`, which a
verifier runs before stamping a document (D12).

## D3 — The order of writing

Write by tier, each document after the ones it builds on:

1. **Start** — the project brief, the glossary (`GLO`) and the project state page (`STATE`).
2. **Decide what** — requirements.
3. **Decide how** — architecture; the data model (`DATA`) when the system stores data; security and privacy (`SEC`)
   when it has users, personal data, secrets, money or a network surface.
4. **Contracts** — one component specification (`SPEC`) per part of the architecture that holds behaviour; the
   interface reference (`API`) when the system exposes one.
5. **Deliver and prove** — the plan, the verification plan, and the findings document once building starts.
6. **Operate and explain** — the runbook (`OPS`) when the system runs for others; guides, references and workflow
   explainers when readers need them.
7. **Any time** — decision records (`ADR`) and change records (`CHG`).

Cross-cutting documents (security, data, failure handling) are written **before** the parts that depend on them, not at
the end; projects that left them late never wrote them. Pilot one part end to end, fix the templates and checks it
exposes, and only then write the rest. **Enforced:** checked — `doc-map` gives the reading order and flags a document
that depends on one that does not exist; review for the writing order.

## D4 — Order of authority

When two sources disagree, the higher one wins, and the lower one is corrected:

1. the owner's stated requirements and the project brief;
2. the approved documents (requirements, architecture, specifications, decisions);
3. code, tests and raw evidence — these decide what **exists**; documents decide what is **intended**;
4. generated output (pages, indexes, maps, figures).

A figure never overrides prose; prose never overrides the data a figure was drawn from. Security and the
classification of a document outrank every other consideration (RULEBOOK L1). **Enforced:** review; the tie-breakers
are in `CONTRADICTION.md`.

## D5 — One fact, one home

Every fact has one place where it is written; everywhere else points at it or repeats it word for word under a marker
a check reads. A number code can derive is not typed into prose: point at the derivation, or let a check re-derive it
on every run. Status is never restated by hand in a second document. The repair for a restated fact is usually
deletion, not correction. **Enforced:** checked where a guard re-derives the fact (counts, symbols, references); review
elsewhere.

## D6 — Written and generated are kept apart

Canonical: prose, specs that figures are drawn from, registers, and the machine files a person writes. Generated:
pages, figures, indexes, the document map, the per-document records, change-log tables and back-links. Fix the source,
never the output; never hand-edit a generated file; regenerate it, and commit it with a check that the committed copy
is current. Generated files carry no timestamps or counts that change on every run, so two branches never conflict over
them. Generators touch only the paths they own. **Enforced:** checked — `doc-map --check` and the engine's staleness
ratchets refuse a stale committed copy.

## D7 — Claims carry their status and their proof

Each claim about the system is labelled: **built**, **partly built**, **designed**, **interim**, **forecast** or
**derived**. A check's result is **passed**, **failed**, **blocked** (it could not run: a missing tool, a setup problem —
never counted as failed or passed) or **not run**. A designed claim names the proof that will show it once built. No readiness percentages, scores or
"almost done". Something that could not be checked is written `CANNOT_VERIFY` with the reason, never guessed. A claim
about code cites the code (`path:line` or a symbol), not another document; a claim that something runs in production
cites what ran, not only the code. Words such as *every*, *only*, *never* and *all* need the check that proves them.
**Enforced:** review; the corpus guards check that cited paths and symbols exist.

## D8 — Links: what a document builds on and what it covers

`depends_on` lists the documents a document builds on, by id; `covers` lists the blueprint parts (container ids in
`system.spec.json`) it describes; `summary` is the one line a reader or an AI uses to decide whether to open it. Every
link must resolve. A change to a document affects every document that depends on it. Every part of the system needs a
document that covers it; a part no document covers is a gap, listed in the map. **Enforced:** checked — the header gate
refuses a malformed link; `doc-map` refuses an id or part that does not exist and a circle of dependencies, and lists
uncovered parts.

## D9 — The machine-readable layer

Two generated files let an AI read a project without opening every page:

- **`DOCUMENT_MAP.json`** (`ultimate-engine doc-map`) — every document with its type, tier, title, summary, status,
  verified state, links in both directions, covered parts and missing sections; the order to read them; the parts no
  document covers; the documents the project still needs; and every broken link. An AI opens this first.
- **`<stem>.blueprint.json`** (`build --formats blueprint`) — one built document as data: its header, type, links,
  every section with its Markdown source, every figure with the question it answers, how to read it and what each mark
  means, and the links between text and figures. Read it instead of the page.

Both are derived; neither is edited. Paths are relative to the project, so neither carries a home directory.
**Enforced:** checked — both pass the same gates as the page; `doc-map --check` refuses a stale map.

## D10 — Figures answer one question each

A figure exists to answer one reader question, named in its spec with the insight it shows; if no figure answers a
question better than a sentence, there is no figure. Every node, edge and mark is explained in writing. Figures are
drawn from a committed spec and real data, never placeholder data, in light and dark, and pass the colour-vision gate.
Each figure appears once; other places refer to it by number. A figure drawn by hand is not evidence that the engine
drew it: a figure offered as engine output carries its spec and the record the build wrote beside it. **Enforced:** checked — the figure gates and
`ultimate-engine cvd check`.

## D11 — Writing limits

About 800 words per section and 40 words per sentence. One subject per document; when a document grows a second
subject, split it. Plain words before technical ones; define a term in the glossary once and use it the same way
everywhere. Headings of a verified document are not renamed. Dates are written in full (`2026-11-27`), never "today"
or "last week". **Enforced:** review.

## D12 — Stamps, verification and drift

A document is **verified** only after someone other than its author has checked it against the code and the evidence,
and its stamp binds the exact content: the stamp is a content hash (`@ sha256:<hex>`) that leaves out only the
generated blocks and the stamp line itself, so a squash merge does not void it. The author, the verifier and the person
who fixes the findings are different people or different agent runs.

Before stamping, the verifier runs `docgen check --strict`: a verified document has every section of its type. Any edit after the stamp voids it: the document is unverified again until it is re-verified. A document whose cited
code has changed is marked for review, not silently trusted; a broken reference is work, a changed citation is a
notice. Status is replaced in place at the top of a document, never appended below as a dated "latest" section.
Unchanged content is never re-stamped to refresh a date. Proof ages by class, not by calendar alone: a claim about
code is due for review when a file it cites changes; a claim about live state, security or money is due after a period
the project sets (30 days unless it says otherwise); everything else has a long backstop (180 days). Due for review is a
notice, not a failure, except for a claim the project marks critical. **Enforced:** checked — the identity and stamp gates refuse
`verified` without a stamp that matches the body; review for separation of duties (`DEEP_VERIFICATION_PASS.md`).

## D13 — Superseding and retiring documents

A document is superseded by a newer one, never edited into a different subject. Before an old document is retired,
every claim in it is carried into its successor, marked obsolete or wrong, or kept as a record, and a second reviewer
checks that map. Retire by a reversible move with a manifest (path, hash, reason); git keeps the history. A retired
document leaves the reach of anyone writing new documents, because old and new text blend. Dated records (findings,
audits, session notes) are kept as written and are never rewritten to look current. Living documents and dated records
are kept in separate folders, and records have a retention the project states. Evidence that must not change is bound
to a preserved copy, never to a living document by hash, so the living document can still be corrected. **Enforced:** checked —
`docgen archive cut` writes the snapshot and its hash; review for the claim map.

## D14 — Checks before prose, and checks that can fail

Build the check before writing the prose it checks, and run it on the document's skeleton first. A check is trusted
only after it has been seen to fail on a planted defect: a false approval, a cycle, a stale output, an empty result,
a secret. A builder that produces an empty result exits non-zero. Every check states what it cannot see. A check that
never ran has not passed, and a skipped step is not a pass. **Enforced:** review; the engine's own checks follow it.

## D15 — Classification and leaks

Every document carries one classification: public, confidential or secret; an unreadable one is read as secret.
Non-public documents live only under the confidential folder and never render to the web. Public pages pass the leak
gate: no secret, key, home path, private address or internal reference survives into them. A secret is never written in
a document, only where it is kept and its name. **Enforced:** checked — RULEBOOK L2, L3, L14 and the leak gates.

## D16 — The writer's checklist

Before handing a document to a verifier, its writer checks, from the defects projects found most often:

1. every *every / only / never / all* is proven by a check or removed;
2. every list that claims to be complete says what it is complete against;
3. every failure path has an exit and a recovery;
4. no name, path, command or number is invented: each resolves;
5. no fact is restated from another document (D5);
6. no section is empty or a placeholder (D2);
7. nothing designed is described as built (D7);
8. the document's links resolve and its summary is one true sentence (D8).

**Enforced:** review.

## D17 — Identifiers are stable

Every id — of a document, a requirement, a component, a figure, a decision — is defined once, in one place, and never
reused or renumbered once anything cites it. A replaced item keeps its id and is marked superseded; a new item takes a
new id. When several people or sessions write at once, one registry hands out ids, and two items with one id is a
blocking defect, not a merge detail. Document ids follow `<PREFIX>-<NNN>`, the prefix being the type. **Enforced:**
checked for documents — `doc-map` refuses two documents with one id, and `new` takes the lowest free id; review for ids
inside documents.

## D18 — Existing projects and existing documents

A project that already has code or documents does not start by rewriting them. First take the inventory without
changing anything (`ultimate-engine doc-map` lists what has an id; anything without one is listed by the project as
"not yet typed"), then record **what exists** — measured, with unknowns marked — in the project state and the
architecture, then add the brief and the requirements for what is intended, and adopt the old documents one at a time
by giving each an id, a type and its missing sections. A document that is no longer true is retired (D13), not edited
into a new subject. Never move or rename a file that scripts or links depend on as part of adoption. **Enforced:**
review; `doc-map` shows progress.

## D19 — Checks give the same answer everywhere

A check runs from the repository alone and gives the same result on any machine: its inputs are committed or pinned by
hash, its tools are pinned, and nothing it needs lives only on one computer. A check whose result depends on a local
file, a secret list present on one machine or a network service is either made hermetic or reports `blocked` with the
reason. A result recorded as evidence names the commit, the tool versions and the machine class it ran on.
**Enforced:** review; the engine's own pinned releases and checks follow it.

---

## Provisos: when a project's situation differs

| Situation | How the rules apply |
|---|---|
| **No code yet** | Every claim is *designed*; D7's code anchor is replaced by the proof that will show it once built; operational and data sections say `None yet, because …`. The minimum set still applies. |
| **Existing code or documents** | D18 first. Claims about what exists cite the code; the target design and its deviations (`FND`) are written before new building starts. |
| **A small project** | The minimum set still applies; each document may be short, and sections that do not apply say `N/A — reason`. Optional types are written only when their "needed" condition holds. |
| **The project's own header dialect** | A front-matter profile maps it; the rules apply to what the profile maps. A profile never makes a document public. |
| **Several repositories** | Each document lives in one repository; another repository cites it at a fixed revision and never copies it. `depends_on` names documents of the same project. |
| **Public and private documents** | D15 outranks every other rule: a private document is never linked from, quoted in or built into a public one. |
| **The engine pinned in a project** | The project's pinned release decides which rules apply; a newer engine's rules apply only after the project pins it and rebuilds. |
| **A rule that cannot be met** | Record why in the document (or an `ADR` when it affects several), with the bound and the owner. A rule is never silently skipped. |

## Terms

- **Document** — a Markdown file with a header whose `id` has a catalog prefix.
- **Record** (`<stem>.blueprint.json`) — one built document as data. **Map** (`DOCUMENT_MAP.json`) — every document of a
  project as data.
- **Blueprint** — in this engine, the system map derived from `system.spec.json` (containers and the documents that
  cover them). The per-document record is called the record, not the blueprint, in these rules; a project's own
  "blueprint" documents are figures inside its architecture and specifications.
- **Verified** — checked by someone other than the author, with a stamp that matches the body (D12).
- **Drift** — a difference between what a document cites and what now exists.

## Scenarios this rule set was checked against

| Scenario | Rules that decide it | Outcome |
|---|---|---|
| One sentence, empty folder | D1, D3 | `init --idea` writes the brief; `doc-map` lists the rest of the minimum set in order. |
| Code already deviates from the design | D1, D7 | A deviation row in `FND`; the design is not edited to match. |
| A verified document is edited | D12 | Its stamp is void; it is unverified until re-verified with `check --strict`. |
| A check could not run | D7, D14 | `blocked` or `not run`, never a pass; the gate stays open. |
| Two sources disagree | D4, Rank | The higher authority wins; the other is corrected and the conflict recorded. |
| Two sessions create the same id | D17 | Blocking; one item is renumbered before anything cites it, or the registry assigns ids. |
| A secret appears in a draft | D15, Rank 1 | Removed before commit; nothing else outranks it. |
| A figure has no data source | D10 | Refused by the figure gates. |
| An old document set is replaced | D13, D18 | Claim map, second reviewer, reversible move; retired part by part. |
| A link names a document that does not exist | D8 | `doc-map` exits 1. |
| A check passes on one machine and fails on another | D19 | Made hermetic or reported `blocked`; not recorded as passed. |
| A claim about production is backed only by code | D7 | Not accepted; it cites what ran. |
| A host's engine updates under a build | Provisos | A pinned copy never updates itself; the project re-pins deliberately. |
| A rule cannot be met in a project | Provisos | Recorded with bound and owner; never skipped silently. |

---

*Change history*

| date | change |
|------|--------|
| 2026-11-27 | Created with the document-type catalog (2.1.0). Rules D1–D19, their rank, provisos, terms and the scenarios they were checked against, drawn from the engine's own rules and from the lessons projects recorded while building document sets with it (rulebook 1.3.1). |
