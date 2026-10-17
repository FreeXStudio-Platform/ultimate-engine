# DOC_MANIFEST.md — minimal bundled registry

This is a **minimal, bundled** doc-type registry — just enough for the engine's own sample
document (`tools/docgen/sample.md`, id `WF-201`) to build end-to-end out of the box, proving
the full pipeline (header parse → manifest-drift check → leak-gate → render → write) actually
works with zero setup.

**A real host project should replace this file with its own real registry** — one row per
document TYPE your project produces (keyed by id-prefix, e.g. `WF` covers every `WF-###`
instance), listing which classification tiers (`variants`) each type is allowed to exist in.
See `RULEBOOK.md` §L10/L18 if you're porting the engine's original, fuller governance model
from its source project (not bundled here — this file ships the eight rows needed for the
sample to build).

Location is configurable: `engine.config.json`'s `docSystem.docManifestPath`, or the
`ENGINE_DOC_MANIFEST_PATH` env var.

## Rule

Every document's header `classification:` must appear in its type's `variants` list here, or
the manifest-drift gate fails closed (`cli check` / `generator.build`'s header validation).
An id with no matching row is itself a blocking finding — an unregistered doc type never
silently passes.

| id | title | type | variants | content_role | surface | status |
|----|-------|------|----------|--------------|---------|--------|
| ADR | Architecture decision record | decision | commercial | project-doc | repo | active |
| CHG | Changelog entry | changelog | commercial | project-doc | repo | active |
| WF | Workflow / pipeline explainer | workflow | commercial | project-doc | web | active |
| SPEC | Specification | spec | commercial | project-doc | repo | active |
| SYS | System / architecture document | architecture | commercial | project-doc | repo | active |
| API | Interface reference | reference | commercial | project-doc | web | active |
| GUIDE | Usage guide | guide | commercial | project-doc | web | active |
| REF | Reference table | reference | commercial | project-doc | web | active |

Every row's `id` is a prefix registered in `TAXONOMY.md`, and every registered prefix has a row —
the two files are kept in agreement mechanically by `tools/health` (`CONS-01`, `CONS-02`). Without a
row, a doc type passes the taxonomy gate and is then refused by manifest-drift, which is how
**`ADR` and `CHG` — the two document types RULEBOOK L9 requires by name — were unbuildable** until
2026-08-20.

*Change history*

| date | change |
|------|--------|
| 2026-08-18 | Bundled minimal manifest created during Ultimate Engine consolidation. |
| 2026-08-20 | Corrected three documents that described this file as shipping "one row"; it has had **eight** since creation. A registry that misreports its own size is the defect class this engine exists to catch. |
| 2026-08-20 | Registered the remaining 7 `TAXONOMY.md` prefixes. Found by the Phase 1 deep verification pass: 7 of 8 known doc types were blocked by manifest-drift, including the `ADR` and `CHG` types L9 mandates. |
