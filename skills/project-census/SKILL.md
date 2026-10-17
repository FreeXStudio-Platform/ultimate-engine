---
name: project-census
description: Measure a project's documentation system from its git tree — how many documents, how many updated or outdated, how many crossed out, which are stamped as a source of truth and whether the stamps still hold, what is complete — and draw it as a report with a varied set of figures plus two explorers. Use when asked "how many documents do we have / how many are outdated / are we working from the source of truth / how complete is the documentation".
---

# project-census — count the documentation, say how, and draw it

Path: `tools/census/`. Python, stdlib only; the report step uses `tools/docgen` (and the chart and Mermaid engines it bridges to).

## When to use it

A question about the *state of a project's documents*: how many, how fresh, what was crossed out, what is authoritative, what is missing. Not for "what did we build"
(that is `project-index`) and not for the engine's own module map (that is the blueprint).

## Steps

1. Write a profile (start from `examples/census.profile.example.json`; every key is optional; unknown keys are refused).
2. `python3 -m tools.census measure PROFILE.json --root <repo> --out census.json` — the numbers, each with its rule under `rules`.
3. `python3 -m tools.census report PROFILE.json --root <repo> --out <dir inside the repo>` — the document. Its `report.id` prefix must be registered in the host's manifest.
4. Read `docs/design/PROJECT_CENSUS.md` §1 for every definition before quoting a number, and print the report's "could not verify" section with it.

## Rules that do not bend

* **No composite completeness number.** Quote each dimension as *covered of total*.
* **Say what "outdated" means** (age, not falsehood) and what "cited" means (named, not necessarily used).
* **A stamp is judged on its body with stamp lines removed from both sides**; do not compare raw files.
* The census never writes outside `--out`.
