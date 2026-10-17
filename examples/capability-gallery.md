---
id: WF-301
classification: public
title: Capability Gallery — every renderable kind, one real dataset
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-08-19
---

# Capability Gallery — every renderable kind, one real dataset

One working example of every figure kind this engine can render, in a single self-contained
HTML document, built through the ordinary `python3 -m tools.docgen.cli build` path. Nothing
here is a mock: every number comes from a real measurement recorded in the **Data provenance**
section below, and every figure carries a `reader_question`/`insight` pair
(see `INTERPRETATION.md`).

The dataset is deliberately mundane — the *structure* of a real, unrelated local directory
tree (a credential-vault application, referred to below as the **measured tree**) surveyed with
nothing but `find`, `wc -l`, `ls` and `codemap`. No file contents were read except line counts
over nine JavaScript modules, no credential material was touched, and the tree's secret-bearing
directories were excluded from every survey by path. The point is that the engine renders
whatever real structure you hand it, and that the numbers on every figure can be re-derived by
hand from the commands listed at the end.

Two figures are the exception, and say so on their own captions: a filesystem has no
geographic dimension, so the geo-map and choropleth are sourced from this engine's own
bundled boundary dataset (`tools/docgen/assets/world-countries-110m.geojson`) instead.

## Data provenance

Every figure below cites one of six measurement runs. All are read-only, all are
reproducible, and the exact commands are listed in the closing section.

| Source ref | What it measured | Headline |
|---|---|---|
| `fs-ext-mix` | File-extension mix, 155 files | md 41 · js 27 · gz 12 · log 11 · json 11 |
| `fs-linecount` | `wc -l` over 9 library modules | 5,224 lines total |
| `fs-dircount` | Files per directory, via codemap | 29 directories, 96 graph nodes |
| `fs-mtime` | Last-modified month, 198 files | Apr 34 · May 3 · Jun 3 · Jul 71 · Aug 87 |
| `fs-depth` | Path-depth distribution, 198 files | d1 11 · d2 98 · d3 75 · d4 14 |
| `geojson-110m` | Bundled boundary dataset | 177 countries, 286 polygons |

## 1 — Process flow (native `flowchart`)

The engine's own build pipeline, including the four fail-closed gates that were deliberately
triggered to confirm they refuse a build rather than silently passing it.

<!-- figure:build-pipeline -->

## 2 — State machine (native `state`)

<!-- figure:doc-states -->

## 3 — System map (native `system_map`, from graphify)

<!-- figure:cred-structure -->

## 4 — Dependency graph (native `dependency_graph`)

<!-- figure:engine-deps -->

## 5 — Sequence diagram (native `sequence`)

<!-- figure:build-sequence -->

## 6 — Isometric 3D (native `isometric3d`)

<!-- figure:dir-volumes -->

## 7 — Layered workflow (native `layered_workflow`)

<!-- figure:depth-layers -->

## 8 — Geographic points (native `geo_map`)

<!-- figure:polygon-hotspots -->

## 9 — Choropleth (native `choropleth`)

<!-- figure:polygon-choropleth -->

## 10 — Sankey (native `sankey`)

<!-- figure:file-partition -->

## 11 — Bar chart (native `bar`)

<!-- figure:module-size -->

## 12 — Radar (native `radar`)

<!-- figure:dir-profile -->

## 13 — Pie (native `pie`)

<!-- figure:ext-mix -->

## 14 — Timeline (native `timeline`)

<!-- figure:activity-months -->

## 15 — Heatmap (native `heatmap`)

<!-- figure:dir-ext-matrix -->

## 16 — Mermaid flowchart (bridge to mermaid-engine)

<!-- figure:graphify-pipeline -->

## 17 — Line chart (bridge to chart-engine)

<!-- figure:cumulative-files -->

## 18 — Treemap (bridge to chart-engine)

<!-- figure:dir-treemap -->

## 19 — Box plot (bridge to chart-engine)

<!-- figure:linecount-spread -->

## 20 — Funnel (bridge to chart-engine)

<!-- figure:filter-funnel -->

## 21 — Horizontal bar (bridge to chart-engine)

<!-- figure:polygon-bars -->

## How every number here can be re-derived

Run these from the root of the measured tree (`$TREE`). They are read-only and touch no file
contents beyond counting lines in nine JavaScript modules.

| Ref | Command |
|---|---|
| `fs-ext-mix` | `find . -type f -not -path "./node_modules/*" -not -path "./.git/*" -not -path "./store/*" -not -path "./keys/*" -not -path "./wallets/*" \| sed -n 's/.*\.\([A-Za-z0-9]*\)$/\1/p' \| sort \| uniq -c \| sort -rn` |
| `fs-linecount` | `wc -l lib/*.js` |
| `fs-dircount` | `ENGINE_HOST_ROOT=$TREE node tools/graphify/build.mjs` |
| `fs-mtime` | `find . -type f -not -path "./node_modules/*" -not -path "./.git/*" -exec stat -f "%Sm" -t "%Y-%m" {} \; \| sort \| uniq -c` |
| `fs-depth` | `find . -type f -not -path "./node_modules/*" -not -path "./.git/*" \| awk -F/ '{print NF-1}' \| sort -n \| uniq -c` |
| `geojson-110m` | Parse `tools/docgen/assets/world-countries-110m.geojson`; count geometry parts per feature |

The two file-count denominators differ on purpose. `fs-ext-mix` counts 155 files because it
excludes the vault-scoped `store/`, `keys/` and `wallets/` directories; `fs-mtime` and
`fs-depth` count all 198 because path depth and modification month reveal nothing about
contents. The Sankey in section 10 reconciles the two figures explicitly.

`fs-dircount` reports smaller per-directory counts than a bare `find` for some directories
(`dev` 7 vs 12, `wallets` 4 vs 5, `keys` 3 vs 4) because `codemap` applies its own ignore
rules. Figures citing `fs-dircount` use the codemap numbers throughout; figures citing
`fs-ext-mix` use the `find` numbers throughout. Neither set is silently mixed.
