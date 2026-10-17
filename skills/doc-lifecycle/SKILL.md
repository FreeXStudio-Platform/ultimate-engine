---
name: doc-lifecycle
description: Take a document through the six steps a governed document owes — tag, wire, date, version, changelog, stamp — and check how far it has got. Use when creating a governed document, when bringing an existing document under the doc-system, when a document needs a new version cut or archiving, or when asked how complete the documentation is.
---

# doc-lifecycle — the six steps, and the command that says where you stopped

Normative source: `docs/process/AUTHORING_CONTRACT.md`. That file is the contract; this is how to
carry it out. **Neither of them enforces anything**, and **five of the six steps are gated by
machinery that exists** — the contract names which gate owns which. **Step 5 is not gated at all**:
nothing checks, per document, that its change was recorded. Read the contract's note on that before
assuming otherwise; an earlier version of this sentence said "every step", and it was wrong.

## Before anything: read where you already are

```bash
python3 -m tools.blueprint completeness
```

Per governed document, which of the six steps is complete. Guessing is the failure this replaces —
each step is individually cheap and silently skippable, so the only reliable answer is the derived
one.

## The six steps, in order

**Order matters only at the ends.** Tag first, because nothing can address a document with no id.
Stamp last, because a stamp certifies a body, and a body still changing cannot be certified.

### 1. tag — give it a header

```markdown
---
id: WF-201
classification: public
title: My Document Title
surface: web
audience: technical
owner: sami
status: draft
export_allowed: true
last_reviewed: 2026-08-29
---
```

`classification` decides where the document may live: RULEBOOK L14 permits a non-public document
only inside the git-ignored vault, and the pre-commit hook refuses a misplaced one.

### 2. wire — make sure the document's TYPE PREFIX has a manifest row

`docs/design/doc-system/DOC_MANIFEST.md` is keyed by **type prefix** — `ADR`, `CHG`, `WF`, `SPEC`,
`SYS`, `API`, `GUIDE`, `REF` — **not by document id**. So a `WF-201` document is wired by the
existing `WF` row and needs no new row at all.

**Do not add a row per document.** An earlier version of this step said "add a row", and following
it literally makes `tools.health` `CONS-02` report a disagreement, because the manifest and the
taxonomy would no longer agree about the registered prefix set. Add a row only when you are
introducing a genuinely new document TYPE, and then register the same prefix in `TAXONOMY.md`.

### 3. date — record when it was last reviewed

`last_reviewed` in the header. Staleness should be visible rather than inferred.

### 4. version — cut a real generation

```bash
python3 -m tools.docgen.cli archive cut <path> --date YYYY-MM-DD
python3 -m tools.docgen.cli archive list
```

A number in the header with no snapshot behind it is a claim, not a version — the `identity` guard
refuses one the archive does not hold. `cut` also refuses a generation identical to the one before
it (`OG-197`), so re-cutting out of habit is caught rather than recorded twice.

### 5. changelog — record the change

An entry in `CHANGELOG.md`: date, version, file, section. **No gate checks this per document** —
`CONS-05` only asserts `PROJECT_VERSION` matches the newest heading, and never looks at a document.
The completeness report reports the step; nothing enforces it.

### 6. stamp — certify the body, last

Only once the body has stopped moving. A stamp on an edited body is invalid (`HANDOFF.md` standing
rule 4), and `verified_state` must match what the stamp actually supports — the `stamps` and
`identity` guards adjudicate that on every corpus run.

## Check your work before committing

```bash
python3 -m tools.draft check <path>
python3 -m tools.corpus_check
```

`draft check` splices the candidate into a throwaway copy of the tree and reports the **difference**
it would introduce — including findings that land on *other* documents because yours moved a fact
they state. It is at its strongest on a document that does not exist yet; after an in-place edit the
tree already contains your change, so run `corpus_check` as well.

## What this skill will not do for you

- **It will not make `verified` a target.** That state is currently zero across this repository and
  the number is honest. Stamping documents whose bodies are still moving to raise it would be worse
  than leaving it at zero.
- **It does not apply to ungoverned documents.** A document opts into the lifecycle by carrying a
  header. Most of this repository's Markdown does not — that is the charter's purpose 2, a
  measurement to improve rather than a violation to punish.
