<!-- title: AUTHORING CONTRACT -->
# The authoring contract — six steps a governed document owes

**Status:** PROCESS — normative for authoring. **Established 2026-08-29** as `docs/plan/BUILD_PLAN.md`
row 6's *"skills + rules that mandate tag/wire/date/version/changelog/stamp"*.

Read with `docs/process/RULES.md` (the six preventive rules) and
`docs/framework/DOC_WRITING_DOCTRINE.md` (the method). This file is narrower than either: it is the
**lifecycle of one document**, from the moment it is created to the moment it can honestly claim to
have been verified.

---

## Why a contract rather than a habit

Because the steps are individually cheap, collectively load-bearing, and silently skippable. A
document that is written but never wired into the manifest is invisible to the index. One that is
versioned but never archived claims a generation that does not exist. One that claims a verified
state with no stamp behind it is the single most expensive kind of wrong this project has met — it
is a *false green*, and every document downstream reasons from it.

**The contract is mostly not a new gate.** Five of the six steps are already enforced by machinery
that exists, and this file names which. What did not exist before Phase 6 was a statement of the
whole sequence in one place, and a report that says how far each document has got.

> **Step 5 is the exception, and saying so is the point.** An earlier version of this table credited
> `CONS-05` with enforcing the changelog step. It does not: `CONS-05` compares `PROJECT_VERSION` to
> the newest heading in `CHANGELOG.md` and never looks at a document at all. **No gate checks that a
> given document's change was recorded** — the completeness report *reports* it, and that is all.
> The same version of this table also credited the `tier` gate with checking the header; `tier`
> lives in `export_sanitizer.py` and decides export eligibility, which is a different job in a
> different file. Both errors were found by a verifier reading the claims against the source, which
> is exactly the check a document mandating a procedure most needs and least often gets.
>
> **What is checked mechanically, and what is not (`OG-208`).** A retained probe asserts that every
> guard and gate credited in this table exists in a live registry — a fabricated name fails. It
> **cannot** tell whether a real gate has been credited with the wrong job: swapping `manifest_drift`
> for `wcag_contrast` would pass, because both are registered. Misattribution is caught by review,
> and this note is the evidence that review catches it.

---

## The six steps

| # | step | what it means | who enforces it |
|---|---|---|---|
| 1 | **tag** | The document carries a doc-system header: an `id`, a `classification`, a `surface`, an `owner`, a `status`. | `tools/docgen/classification.py` — the `header` gate |
| 2 | **wire** | Its **type prefix** (`WF`, `ADR`, …) has a row in `docs/design/doc-system/DOC_MANIFEST.md`, so the index and the taxonomy know the type exists. The manifest is keyed by prefix, **not by document id** — a new document of an existing type needs no new row. | the `manifest_drift` gate; `tools.health` `CONS-02` asserts the manifest and the taxonomy agree both ways |
| 3 | **date** | It records when it was last reviewed, so staleness is visible rather than inferred. | `tools/docgen/classification.py` validates the header field |
| 4 | **version** | A generation exists **on disk** under `docs/archive/`, cut with `python3 -m tools.docgen.cli archive cut`. A number in the header with no snapshot behind it is a claim, not a version. | the `identity` corpus guard, which refuses a version the archive does not hold |
| 5 | **changelog** | The change is recorded in `CHANGELOG.md` with its date, version, file and section. | **Nothing, per document** — see the note below. `CONS-05` asserts only that `PROJECT_VERSION` matches the newest heading |
| 6 | **stamp** | A content-certifying stamp covers the body, and `verified_state` matches it. | the `stamps` and `identity` corpus guards |

**The order matters only at the ends.** Tag first, because nothing else can address a document that
has no id. Stamp last, because a stamp certifies a body, and a body that is still changing cannot
be certified — this is why `HANDOFF.md` standing rule 4 says a stamp on an edited body is invalid.

---

## Where you are: read the report, do not guess

```bash
python3 -m tools.blueprint completeness
```

`blueprint/COMPLETENESS.md` carries the same thing rendered: per governed document, which of the six
steps is complete, each derived from the artifact that owns it — the header for tag and date, the
manifest for wire, the archive for version, `CHANGELOG.md` for changelog, the stamp for stamp.

**The report reports; it does not enforce.** Two enforcers of one rule is the defect this engine
exists to catch, so the gates in the table above stay the enforcement and this stays the answer to
*how far did we get*.

---

## What the contract deliberately does NOT require

- **It does not apply to ungoverned documents.** A document opts into the lifecycle by carrying a
  doc-system header. Most of this repository's Markdown does not, and that is the charter's purpose
  2 — a measurement to improve, not a violation to punish.
- **It does not require a stamp before a document is useful.** Steps 1–3 make a document addressable
  and reviewable, which is most of the value. Steps 4–6 are what let it claim to be *verified*, and
  a document that never claims that owes them nothing.
- **It does not make `verified` a target to chase.** `verified` is currently **zero** across every
  node in this repository, and that number is honest: no document that owns a container is governed
  yet. Raising it by stamping documents whose bodies are still moving would be worse than leaving it
  at zero.

---

## The failure this exists to prevent, measured

Every one of the six steps has been skipped in this repository at least once, and each cost
something:

- **tag** — a `classification: secret` document placed in the one directory the engine tells you to
  use committed and pushed clean, because the directory was not gitignored (`.gitignore`'s vault
  block records it).
- **wire** — the manifest was described as shipping one row when it ships eight.
- **date** — stamps went stale and the drift was found by hand, three passes running.
- **version** — `archive cut` would have cut a generation byte-identical to the one before it, so
  two directories would have described one document state (`OG-197`).
- **changelog** — a gate count went stale twice while nothing measured it (`RULES.md` Rule 2).
- **stamp** — `PROVENANCE.md`'s stamp stopped covering the tree and the honest state had to be
  written into `HANDOFF.md` by hand (`OG-09`, still open, scheduled to Phase 7).
