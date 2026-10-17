---
name: chart-engine
description: Render deterministic data-series charts (bar, line, area, scatter, bubble, pie, donut, heatmap, sankey, funnel, tree, treemap, sunburst, boxplot, radar, timeline, and Gantt via custom series) to SVG/PNG/interactive HTML. Use when asked for a chart, graph of numeric data, or dashboard visual — not for document-structure diagrams (see document-engine) or Mermaid syntax (see mermaid-engine).
---

# chart-engine — deterministic data charts

Path: `tools/visual-engine/`. Node.js, Apache ECharts 6.1.0, server-side rendered (no browser).
Setup once: `npm install` inside `tools/visual-engine/`.

Entry points:
- CLI: `node adapters/echarts/cli.mjs render <job.json>`
- MCP server: `mcp/server.mjs` (7 tools — `visual_render`, `visual_validate_job`,
  `visual_list_capabilities`, `visual_list_presets`, `visual_get_theme`, `visual_render_batch`,
  `visual_explain_selection`)
- From docgen: `kind: "echarts"` in a figure sidecar spec (see `../document-engine/SKILL.md`)

## Chart families (23+ named types)

bar, bar_grouped, bar_stacked, bar_horizontal, line, line_step, area, area_stacked, scatter,
bubble, pie, donut, heatmap, matrix, sankey, funnel, graph (node-link, layout locked —
never force-directed, for determinism), tree, treemap, sunburst, boxplot, radar, timeline,
scorecard. Full detail + exact job-packet shape: `schemas/visual-job.schema.json` and
`knowledge/CHART_USE_CASE_CATALOG.json`.

## Gantt charts

Not a named preset — use ECharts' own officially-documented pattern: a `custom` series with
`renderItem` (one rect per task, positioned by a time axis + category axis). This is a real,
current, official ECharts recipe (verified against ECharts' own docs/examples during this
package's consolidation), not a workaround. No new preset exists for it yet in this engine —
build the job packet directly if you need one.

## Export formats

- **SVG** — canonical, deterministic (byte-identical on repeat render of the same job),
  content-sha256-stamped. Use this as your default/archival format.
- **PNG** — a rasterization convenience, never treat as archival.
- **Interactive HTML** — fully self-contained (echarts.min.js inlined, no CDN), with a static
  SVG fallback for print/reduced-motion.
- **PDF** — not native here; embed the SVG into a docgen document instead.

## What this engine will refuse, on purpose

- **3D charts** — no `echarts-gl` (confirmed incompatible with the pinned ECharts 6.1.0 as of
  this package's research; do not add it). For genuine 3D, use document-engine's
  `isometric3d.py` instead — real 3D projection math, a different tool for a different need.
- **Geographic/choropleth maps** — none of that logic lives here. Use document-engine's
  `geo_map.py` (`render_choropleth` for real country boundaries, `render_geo_map` for
  schematic point/route maps).
- **Dual/secondary axes** — explicitly refused by policy (`ENGINE_ROUTING_POLICY.json`), not a
  code limitation.
- **Force-directed graph layouts** — the `graph` series only allows `circular` or an explicit
  preset layout, never `force`, so SVG output stays deterministic. For a genuinely
  force-directed interactive graph, use graph-engine instead (`../graph-engine/SKILL.md`) —
  different tool, different determinism tradeoff (graph-engine's output is an interactive HTML
  viewer, not a static byte-stable SVG).

## Verify before trusting a fresh install

`npm test` (30 unit tests) and `npm run simulate` (22 acceptance simulations) — both should be
green. If either fails after a fresh `npm install`, something about the local Node/npm
environment differs from what this package was built against; don't proceed to render real
work until both pass.
