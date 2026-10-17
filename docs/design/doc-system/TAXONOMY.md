# TAXONOMY.md — doc-type id-prefix registry

The vocabulary of document **types**. Every document id has the shape `<PREFIX>-<NNN>`, and its
prefix must appear in the table below or the id-prefix gate fails closed (RULEBOOK L2/L5).

This registry answers one question only: **is this a known doc type?** It does *not* say which
classification tiers the type may exist in — that is `DOC_MANIFEST.md`'s job (L18), and the two are
independent gates. A prefix listed here with no `DOC_MANIFEST.md` row is a known type that is not
yet registered for any tier; it passes the prefix check and is still refused by manifest-drift.

**Prefix extraction is longest-match.** An id is split on its **final** `-<digits>` segment, so
`SOC-S-003` yields the prefix `SOC-S`, not `SOC`. Prefixes may therefore contain internal hyphens.

**This file is locked** — it is listed in `VERSION.json`'s `rulebook_files`. Editing it without
following L9 trips the rulebook hash-gate.

## Rule

Every document's id-prefix must appear in the `prefix` column below. Fail-closed in both
directions: an id with no extractable prefix is a blocking finding, and an empty prefix set (this
file absent or unreadable) blocks **every** document rather than silently accepting anything.

## Registry

This is a **minimal, bundled, generic** vocabulary — the same philosophy as the bundled
`DOC_MANIFEST.md`. A real host project replaces it with its own doc types.

| prefix | name | covers |
|--------|------|--------|
| ADR | Architecture decision record | One decision, its context, alternatives, and consequences. Required by L9 on any locked-rule change. |
| CHG | Changelog entry | One recorded change. `CHG-700` is the entry L9 requires on a locked-rule edit. |
| WF | Workflow / pipeline explainer | How a process runs end to end. The bundled sample document is `WF-201`. |
| SPEC | Specification | The normative contract for a component or interface. |
| SYS | System / architecture document | Structure, boundaries, and the connections between parts. |
| API | Interface reference | A callable surface: endpoints, parameters, errors. |
| GUIDE | Usage guide | Task-oriented instructions for an operator or consumer. |
| REF | Reference table | Enumerated facts: options, codes, limits, defaults. |

`ENGINE_PLAN.md` §4b records the fuller, domain-specific vocabulary this engine's source project
used (`DET`, `ENG`, `WF`, `SYS`, `ATK`, `SOC-S`, `SOC-E`, `API`, `SDK`, `BENCH`, `TM`, `EDU`, `VER`).
It is retained there as a worked example of a host project's taxonomy — including the hyphenated
`SOC-S`/`SOC-E` shape the extractor handles — and is deliberately **not** adopted here, because this
engine is domain-neutral.

*Change history*

| date | change |
|------|--------|
| 2026-08-19 | Registry created (Phase 1) with a generic bundled vocabulary. `ADR` and `CHG` are included because L9 requires both document types by name. |
