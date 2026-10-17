---
name: ultimate-engine
description: Router for the Ultimate Engine — a self-contained, offline document/blueprint/graph/chart/diagram generation toolkit. Use when the user asks to create, generate, or build a document, report, blueprint, diagram, chart, graph, map, or Mermaid diagram, or asks what visualization/document capability is available. Points to the specific sub-skill for the task.
---

# Ultimate Engine — capability router

This package (the directory this skill lives in, two levels up) is a complete, offline,
project-agnostic document + visualization toolkit: five engines, zero required network access,
zero required configuration. Before reaching for anything else (a chart library from scratch,
a new Mermaid install, hand-rolled SVG), check whether this package already covers it — it
almost certainly does. Read `CAPABILITIES.json` at the package root for the exhaustive,
verified list; this skill is the fast triage layer on top of it.

## Which engine for which ask

| The user wants... | Use | Sub-skill |
|---|---|---|
| A document/report (Markdown → styled HTML/PDF) | `tools/docgen/` | `skills/document-engine/SKILL.md` |
| A flowchart, state diagram, dependency graph, sequence diagram, isometric 3D diagram, Sankey, point/route map | `tools/docgen/` (native renderers) | `skills/document-engine/SKILL.md` |
| A **choropleth** (real country-boundary world map, value-to-color) | `tools/docgen/geo_map.py`'s `render_choropleth` | `skills/document-engine/SKILL.md` |
| A **data chart** — bar/line/pie/scatter/funnel/treemap/boxplot/radar/heatmap/~20 more | `tools/visual-engine/` | `skills/chart-engine/SKILL.md` |
| A **Gantt chart** | `tools/visual-engine/` via an ECharts custom-series job (see CAPABILITIES.json → `chart-engine.capabilities.ganttViaCustomSeries`) | `skills/chart-engine/SKILL.md` |
| A **Mermaid** diagram specifically (user says "mermaid" or pastes Mermaid syntax) | `tools/mermaid-engine/` | `skills/mermaid-engine/SKILL.md` |
| A **codebase structure / dependency / pipeline graph**, interactive (2D/3D/hierarchical) | `tools/graphify/` | `skills/graph-engine/SKILL.md` |
| "What have I already built for this project?" / avoiding losing track in a large project | `tools/project_index/` | `skills/project-index/SKILL.md` |
| "How many documents / how many are outdated / are we working from the source of truth / how complete is the documentation?" | `tools/census/` | `skills/project-census/SKILL.md` |
| Taking a **governed document** through tag → wire → date → version → changelog → stamp, or asking how complete the documentation is | `tools/blueprint/completeness.py`, `docs/process/AUTHORING_CONTRACT.md` | `skills/doc-lifecycle/SKILL.md` |

## Before doing anything else

1. **Check `engine.config.json` / `CONFIGURATION.md`** if you're working inside a host project
   that has its own doc-governance layout, source tree shape, or path conventions — most things
   work with zero config, but don't assume; a wrong default silently producing output in the
   wrong place is worse than a 10-second config check.
2. **Install once per engine, per machine**: `tools/visual-engine/` and `tools/mermaid-engine/`
   both need `npm install` before first use (they ship `package.json` but not `node_modules/` —
   deliberately, to keep the package small and portable; native bindings are
   machine/platform-specific, so vendoring them would hurt portability, not help it).
   `tools/docgen/` needs `pip install -r requirements.txt` (stdlib-heavy; `weasyprint` is the
   only optional dependency, for PDF — everything else works without it).
3. **Everything runs offline, on purpose.** No engine in this package makes a network call to
   render anything (verified this session, including fixing two real violations — see
   `PROVENANCE.md`). If you ever see a `fetch`/CDN URL/API call appear in a render path, that is
   a regression, not a feature — fix it, don't work around it.

## The one cross-cutting gotcha worth knowing up front

**Theme-reactive SVG figures use CSS custom properties, not baked hex colors** — every native
docgen figure (and, since this session, embedded Mermaid figures too) resolves its colors via
`var(--fg)`/`var(--bg)`-style references so one document works in both the dark and light theme
toggle without a re-render. If you ever add a new figure type or embed a third-party SVG
renderer, do NOT default it to hardcoded hex — and do NOT let it set a `--bg`/`--fg` custom
property locally on its own root element with a value of literally `var(--bg)`/`var(--fg)`
(that is a genuine CSS cycle — the property becomes invalid, not "inherits from the page" —
this bit the Mermaid integration; see `tools/docgen/mermaid_bridge.py`'s docstring and
`tools/docgen/tokens.py`'s `--mermaid-bg`/`--mermaid-fg` alias pattern for the fix to copy).

**The same trap, second form: never stamp `data-theme` on anything inside the page.** The
palette is declared on `[data-theme="dark"]` / `[data-theme="light"]` and the toggle sets that
attribute on `<html>`. Any element *below* `<html>` that also carries `data-theme` re-declares
the whole palette on itself, so it and everything inside it keep those colours while the rest
of the page switches — the toggle appears to do nothing, or does it to only part of the page.
Two live instances of this were found and fixed on 2026-08-19: a hardcoded `<body
data-theme="dark">` (which made the light theme completely unreachable) and a `data-theme`
stamped on every figure `<svg>` by four native renderers (which left 7 of 21 figures dark in
light mode). Renderers now stamp it **only** when a caller explicitly pins a theme for a
standalone SVG (`cli.py render --theme`); embedded figures inherit. If you add a renderer,
inherit — don't stamp.
