---
name: document-engine
description: Build self-contained HTML/JSON/PDF documents with embedded diagrams — flowcharts, state/sequence/dependency diagrams, isometric 3D, Sankey, geographic point maps, and real country-boundary choropleth maps. Use when asked to create a document, report, blueprint document, or any of these diagram types.
---

# document-engine — Markdown + diagrams → real documents

Path: `tools/docgen/`. Python 3.11, stdlib-heavy. Entry point:
`python3 -m tools.docgen.cli build <file.md>`.

## The shape of a document

A Markdown file with a YAML front-matter header:
```markdown
---
id: WF-201
classification: public
title: My Document Title
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-08-18
---

# My Document Title

Body text. Use `## Heading` for sections.

<!-- figure:my-figure-id -->
```

The `id`'s prefix (`WF` in `WF-201`) must have a row in `docs/design/doc-system/DOC_MANIFEST.md`
(a bundled minimal example ships with one `WF` row — replace it with your own project's real
registry once you have doc types beyond the sample; see `../../CONFIGURATION.md`). Skipping this
is the #1 reason a build fails with "manifest_drift" — it's a deliberate fail-closed gate, not
a bug.

A `<!-- figure:ID -->` directive embeds a figure whose spec comes from a sidecar file named
`<same-basename>_spec.json` (a list of figure objects, or a single one).

## Figure kinds (the `"kind"` field in the sidecar spec)

| `kind` | What it renders | Notes |
|---|---|---|
| `flowchart` (default, omit `kind`) | Animated process flow, 9 node glyphs | `VisualSpec` shape |
| `state` | State machine diagram | Same `VisualSpec` shape, all nodes `NodeType.STATE` |
| `system_map` | Undirected component/system map | Same `VisualSpec` shape |
| `dependency_graph` | Directed call/dependency graph | Same `VisualSpec` shape |
| `sequence` | UML-style sequence diagram | No self-messages |
| `sankey` | Value-proportional flow diagram | |
| `geo_map` | Point/route map | Schematic, coarse by design |
| `choropleth` | Real country-boundary world map, value-to-color | `values: dict[country_name, float]` shape |
| `isometric3d` | True 3D isometric/axonometric | Up to 24 boxes |
| `bar` | Zero-baseline bar chart | Never a truncated axis |
| `radar` | Radar/spider chart | Needs >=3 axes |
| `pie` | Pie/donut chart | <=6 slices |
| `timeline` | Point-event timeline | NOT a Gantt (no durations/dependencies) |
| `heatmap` | Matrix heatmap | Always carries a color-scale legend |
| `layered_workflow` | 2.5D layered cross-plane workflow | Nodes have `layer`+`col`, not free x/y |
| `explorer` | A zoomable, clickable hierarchy (treemap with a panel, a reader and hover arrows); a block, not a picture | Tree of parts with `id`/`name`/`value`/`status`, `edges`, `documents`; see `docs/design/FIGURE_SYSTEM.md` §13 |
| `echarts` | Bridges to chart-engine (bar/line/pie/scatter/~20 more) | Needs `tools/visual-engine/` `npm install`ed |
| `mermaid` | Bridges to mermaid-engine (flowchart/sequence/class/state/ER/xychart via Mermaid syntax) | Needs `tools/mermaid-engine/` `npm install`ed |

That's 15 native picture kinds plus the `explorer` block, all reachable through the identical `<!-- figure:ID -->` + sidecar-JSON
pattern (verified end-to-end this session — see `PROVENANCE.md`) — no figure type requires a
separate manual Python call.

**Every *native* kind accepts optional `reader_question`/`insight` string fields** in its sidecar entry —
fill these in for anything meant to be a real source of truth, not just an illustration. See
`../../INTERPRETATION.md` for the full convention (mirrors chart-engine's own mandatory
`reader_question`/advisory `text_summary` job-packet fields) and for what precision/collision
guarantees each figure kind actually has, verified against code.

**Country names must match the bundled dataset's short/common form exactly**
(e.g. `"USA"`, not `"United States of America"`) — call
`tools.docgen.geo_map.list_choropleth_country_names()` to check spelling before authoring
values; an unmatched name fails the render on purpose (fail-closed) rather than silently
dropping a country.

## Native diagram types NOT covered here

- **Gantt charts, org charts / generic tree auto-layout, ER/class diagrams** — see
  `../../CAPABILITIES.json`'s `document-engine.notImplemented` for exactly what's missing and
  where to get it instead (chart-engine for Gantt, mermaid-engine for ER/class).
- **Data-series charts beyond docgen's own 5** (bar/radar/pie/timeline/heatmap) — use
  `kind: "echarts"` for the other ~19 types chart-engine has.

## Common mistakes

- Forgetting the DOC_MANIFEST row for a new id-prefix → `manifest_drift` blocking finding.
- A figure directive with no matching sidecar entry → the figure silently doesn't render (check
  the sidecar's `id` field matches the directive's `<!-- figure:ID -->` exactly).
- A numeric value in ANY figure (a `geo_map` point's `value`, a `choropleth`'s `values`) with no
  matching `DataSource` in the spec → fails closed (L16: "every number must be sourced"). This
  is enforced everywhere in this engine, not just here.
- Assuming `pdf` format always works — it degrades to `skipped(weasyprint absent)` if
  `weasyprint` isn't installed, rather than failing the whole build. Check `BuildResult.outputs`
  for what actually got written.
