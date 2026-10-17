<!-- classification: public -->

# AI Visualization Engine

> **Not bundled (note added 2026-08-20).** `docs/claude/DOCUMENT_REWRITE_PROTOCOL.md` was part of this engine's source project and
> is not shipped with this package. This package's equivalent method document is `docs/framework/DOC_WRITING_DOCTRINE.md`.

### the project's data-chart infrastructure layer · installed 2026-08-08 · v1.0.0

> One sentence: **AI agents select and specify; approved engines render;
> project templates remain the visual authority.** This package adds Apache
> ECharts 6.1.0 (pinned) as the project's data-chart renderer behind a
> validated job interface, a project-theme adapter derived from the Atlas
> tokens, a constrained MCP facade, and a chart-selection knowledge base.
> It does **not** replace anything: `tools/docgen` stays the authoritative
> document/diagram engine, Recharts stays the app UI layer, mermaid stays the
> markdown drafting stage. Routing: `ENGINE_ROUTING_POLICY.json`.

## Quickstart

```bash
cd tools/visual-engine
npm ci                                  # exact pins, VERSION_LOCK.json
npm test                                # gates + determinism + regression
npm run simulate                        # 22 acceptance simulations → renders/ + evidence/
npm run build:themes                    # regenerate themes/ from tokens.json
npm run render -- render fixtures/normal/detector-coverage-heatmap.json \
  -o renders/current --formats svg,png,html --evidence
node adapters/echarts/cli.mjs render fixtures/normal/detector-coverage-heatmap.json \
  -o renders/current --formats svg,png,html --evidence   # the same thing, spelled out
npm run mcp                             # stdio MCP facade
```

**All five declared scripts are shown above.** `npm run render` was declared in `package.json` and
named by **nothing** in tracked content — no README, no `CAPABILITIES.json` entry, no health check
— while its four siblings had between 4 and 19 references each (`OG-134`). A script nobody
documents is a script nobody runs, and the first person to try it discovers whether it still works.
The `--` before the arguments is required: npm passes everything after it to the underlying
command rather than consuming it itself.

## Map of the folder

| Path | What |
|---|---|
| `AI_AGENT_SKILL.md` | **read this first as an agent** — the orchestration contract |
| `ENGINE_MANIFEST.json` · `VERSION_LOCK.json` · `INSTALLATION_ATTESTATION.json` | identity, pins, install evidence, rollback |
| `CAPABILITY_MATRIX.json` · `ENGINE_ROUTING_POLICY.json` | which engine owns which visual family |
| `SECURITY_POLICY.md` · `CHART_SELECTION_POLICY.md` · `RESKINNING_AND_THEME_POLICY.md` · `EXPORT_POLICY.md` | the four policy contracts |
| `adapters/echarts/` | direct (non-MCP) renderer: `render.mjs` API, `cli.mjs`, option builder, validator, theme adapter, HTML template |
| `adapters/existing/` | pointers to preserved engines (docgen, Recharts, mermaid, graphify) |
| `mcp/` | `server.mjs` facade + decision record, tool-schema snapshot, capability tests, fallback plan |
| `themes/` | GENERATED from `tools/docgen/assets/tokens.json` (Atlas v3.3) — `npm run build:themes` |
| `schemas/` | visual-job, render-result, chart-use-case, engine-capability |
| `knowledge/` | use-case catalog, project use cases, anti-patterns, decision tree, engine map, source registry |
| `presets/` | 22 project presets (detector, gates, docs, tiers, ops…) |
| `fixtures/` · `tests/` · `renders/golden/` · `evidence/` | test inputs, node:test suite, golden renders, per-render evidence |

## The two hard rules

1. **Determinism** — same job + same pins ⇒ byte-identical SVG (id-normalized,
   animation-free SSR, no force layouts). `renders/golden/` locks this; an
   engine upgrade that shifts bytes must be classified in `renders/diffs/`
   before re-pinning (spec §28).
2. **Fail closed** — an invalid, unsafe, oversized, or restricted job throws a
   gate error. There is no partial render and no silent default (T-R9).

## Provenance

Implementation directive: operator-delivered package
`VISUALIZATION_ENGINE_MCP_INTEGRATION_SYSTEM.md` v1.0.0
(2026-08-08). Research evidence: `knowledge/SOURCE_REGISTRY.json` +
`evidence/research/`. This package fulfils the planned "Apache ECharts once it
is available locally" dependency recorded in the engine's source project
(`docs/claude/DOCUMENT_REWRITE_PROTOCOL.md`, which is not bundled here).
