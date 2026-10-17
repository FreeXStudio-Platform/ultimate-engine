<!-- title: USAGE GUIDE -->
# Usage Guide

Practical, worked-example orientation to every engine in this package. For the exhaustive,
machine-readable capability list, read `CAPABILITIES.json`. For path/tool configuration, read
`CONFIGURATION.md`. For "what got copied from where and why", read `PROVENANCE.md`. For how to
make a figure carry real meaning — `reader_question`/`insight` fields, precision/collision
guarantees, and color/layout conventions per figure type — read `INTERPRETATION.md`. For an
agent picking this package up cold, the `skills/` directory has one focused skill per engine —
start there if you're an agent, start here if you're a person.

## Zero-setup quick start

```bash
cd "Ultimate Engine"

# Is the engine green? One command, fails closed, never calls a SKIP a pass.
bash tools/hooks/install.sh && python3 -m tools.health --full

# Document engine (Python — needs PyYAML; everything else is stdlib)
#   python3 -m pip install PyYAML     <- required: the doc-system header parser uses it, and
#                                        without it every docgen entry point fails at import.
#   The old line here said "no install needed beyond stdlib", which was false and was the exact
#   sentence a new user trusts. tools/docgen/requirements.txt additionally pins weasyprint, which
#   only the PDF path needs — do not install it for the core path.
python3 -m tools.docgen.cli build tools/docgen/sample.md
# Many documents as one corpus, through the incremental cache (second run is near-free):
python3 -m tools.docgen.cli build tools/docgen/sample.md examples/capability-gallery.md \
    -o build/ --formats html,json --cached
# -> tools/docgen/sample.html — open it in a browser, toggle dark/light, see the embedded
#    flowchart diagram render.

# Chart engine (Node — one-time npm install)
cd tools/visual-engine && npm install && npm test && npm run simulate && cd ../..
# -> npm test:     30/30 unit tests
# -> npm simulate: 22/22 acceptance simulations
# `npm test` alone runs the unit suite ONLY — it does not run the simulations, and the line here
# used to claim both. Order matters and is load-bearing: `simulate` REWRITES the goldens that
# `npm test` compares against, so test must run first (LESSONS.md L-05).

# Mermaid engine (Node — one-time npm install)
cd tools/mermaid-engine && npm install && npm test && cd ../..
# -> 6/6 diagram types render clean.

# Graph engine (Node — needs `codemap` on PATH, no npm install: zero deps)
node tools/graphify/build.mjs
bash tools/graphify/open.sh graph
# -> opens an interactive force-directed graph of this very package's own file tree.
```

Every one of these was actually run and verified during this package's own consolidation —
these are not hypothetical commands.

## Worked example: a document with three different figure types

This exact example is bundled and verified working — `tools/docgen/sample-multi-figure.md` +
`sample-multi-figure_spec.json`. Build it yourself: `python3 -m tools.docgen.cli build
tools/docgen/sample-multi-figure.md` (after `npm install` in `tools/visual-engine/` and
`tools/mermaid-engine/`).

```markdown
---
id: WF-501
classification: public
title: Quarterly Ops Review
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-08-18
---

# Quarterly Ops Review

## Where customers are

<!-- figure:customer-map -->

## Deployment pipeline

<!-- figure:deploy-flow -->

## Incident trend

<!-- figure:incident-chart -->
```

Sidecar `sample-multi-figure_spec.json` (next to the `.md` file, same basename) — every figure
kind, including the choropleth, is a plain sidecar entry (`kind: "choropleth"`), the same
declarative pattern as every other figure type — no separate Python call needed:

```json
[
  {
    "id": "customer-map",
    "kind": "choropleth",
    "title": "Customers by Country",
    "caption": "Customers by country, CRM export.",
    "unit": " customers",
    "values": { "USA": 420, "Germany": 210, "India": 340, "Brazil": 88, "Australia": 65 },
    "data_sources": [{ "kind": "metric", "ref": "crm-2026-08" }]
  },
  {
    "id": "deploy-flow",
    "kind": "mermaid",
    "caption": "Deploy pipeline, current state.",
    "code": "graph TD\n  A[Push] --> B{Tests pass?}\n  B -->|Yes| C[Deploy staging]\n  B -->|No| D[Notify]\n  C --> E[Deploy prod]"
  },
  {
    "id": "incident-chart",
    "kind": "echarts",
    "caption": "Incidents per week, last quarter.",
    "job": {
      "visual_id": "incident-chart",
      "reader_question": "How many incidents occurred each week last quarter?",
      "classification": "public",
      "data_shape": "table",
      "selected_visual": "line",
      "title": "Weekly incidents",
      "text_summary": "Incidents peaked at 4 in week 3 and dropped to 0 by week 4.",
      "data": { "dimensions": ["week", "count"], "source": [["W1", 2], ["W2", 1], ["W3", 4], ["W4", 0]] }
    }
  }
]
```

`values` keys must match the bundled dataset's country names exactly (short/common form, e.g.
`"USA"` not `"United States of America"`) — call
`tools.docgen.geo_map.list_choropleth_country_names()` to check spelling; an unmatched name
fails the render on purpose. `visual_id`/`reader_question`/`classification`/`data_shape` are
chart-engine's own required job-packet fields (see `skills/chart-engine/SKILL.md` if you're
authoring one from scratch, or copy a preset from `tools/visual-engine/presets/`).

Build it: `python3 -m tools.docgen.cli build tools/docgen/sample-multi-figure.md` (after
`npm install` in `tools/visual-engine/` and `tools/mermaid-engine/`). Verified this session:
all three figures render correctly, theme-reactive, zero network requests.

## Worked example: figures that explain themselves and link to the text

Every figure is numbered (`Fig. 1 … N`, in the order you place it), anchored (`fig-<slug>`) and explained; every `##`
section is a link target (`sec-<slug>`) that lists its figures as chips, and each figure links back to its section. Two
things are yours to write:

```markdown
## Deployment pipeline

The pipeline is shown in [[fig:deploy-flow]]; step 3 is where the gate runs.

<!-- figure:deploy-flow -->
```

`[[fig:deploy-flow]]` becomes a link "Fig. 2". A reference to a figure the document does not place **fails the build**
(it is never printed as dead text), and so does placing one figure twice. Hand-written `Fig. N —` prefixes in captions
are dropped: the document numbers its own figures.

For a node/edge diagram the sidecar may add meaning that the engine draws and explains (all optional):

```json
{
  "id": "deploy-flow", "kind": "flowchart", "title": "Deploy", "caption": "Deploy pipeline.",
  "nodes": [
    {"id": "push", "type": "source", "label": "Push", "x": 40, "y": 120},
    {"id": "gate", "type": "gate", "label": "Tests", "x": 340, "y": 120, "tone": "green"}
  ],
  "edges": [
    {"src": "push", "dst": "gate", "label": "commit", "main": true, "note": "Every push starts a run."},
    {"src": "gate", "dst": "push", "label": "red", "role": "error", "style": "dashed"}
  ]
}
```

`main: true` edges get a numbered circle, a dot that changes colour as the data is worked on (`phase`: `raw` →
`processed` → `verified` by position unless you set it) and a line in the key under the figure. `role` picks the arrow's
colour (`flow` `return` `async` `error` `link`); sequence messages take `kind` (`call` `return` `async` `error`).

For a chart, name what you draw — an unnamed dot is a number in a small circle:

```json
"data": { "dimensions": ["files", "lines"], "source": [[12, 340], [40, 2100]],
          "names": ["parser", "renderer"], "notes": ["Reads the header.", "Draws every figure."] }
```

Under each figure the document prints "What the numbers mean" (the reading guide, the key to the numbered circles) or
"What each mark shows" (a table, for an engine chart of up to 30 marks). Hover or tab to a mark for a tooltip, click to
pin it, `Esc` to release.

**For a machine**, build with `--formats html,blueprint`:

```bash
python3 -m tools.docgen.cli build doc.md -o out --formats html,blueprint
# out/doc.html            the document
# out/doc.blueprint.json  sections (with Markdown source), numbered figures (with their keys and per-mark records),
#                         every [[fig:]] reference, and the contains / described-by / references link graph
node tools/visual-engine/adapters/echarts/cli.mjs render job.json -o out --formats svg,json
# out/<visual_id>.figure.json   what every mark means, from the live model — meaning only, no geometry
```

Design, rules and the exact fields: `docs/design/FIGURE_SYSTEM.md`.

## Worked example: a codebase graph, three ways to look at it

```bash
node tools/graphify/build.mjs         # structure graph
bash tools/graphify/open.sh graph
```
In the viewer: click **Layout** once for a top-down hierarchical tree, again for a radial
layout, again to return to force-directed. Click **3D** for a real WebGL view (loads a locally
vendored ~1.3MB library on first use — no network, verified via network-request inspection
during this package's build). All four views are the SAME underlying graph data — just
different layout algorithms on it.

## Worked example: tracking what you've built across a long project

```bash
# After finishing the ops-review document above:
python3 -m tools.project_index.cli register \
  --id quarterly-ops-review --path quarterly-ops-review.html --type document \
  --title "Quarterly Ops Review" --section "Q3 2026" \
  --summary "Customer map, deploy pipeline, incident trend" \
  --tags "ops,quarterly" --status final --created 2026-08-18 --engine document-engine

# Weeks later, in a fresh session, before building something that might be a duplicate:
python3 -m tools.project_index.cli search "ops review"
python3 -m tools.project_index.cli dashboard   # PROJECT_INDEX.html — a real navigable page
```

## Worked example: how many documents do we have, and in what state?

```bash
cp examples/census.profile.example.json census.profile.json     # edit the paths, the archive globs, the stamp pattern
python3 -m tools.census measure census.profile.json --root . --out census.json
python3 -m tools.census report  census.profile.json --root . --out docs/census/
python3 -m tools.census inventory --engine-root .               # how many figure models the engine can draw
```

The report answers eight questions with a number and its rule each (documents, updated, outdated, crossed out, stamped, whether the stamps hold, whether the
work cites them, completeness per dimension) and draws each with a different kind of figure, plus an explorer for the documentation tree and one for the code.
`docs/design/PROJECT_CENSUS.md` defines every number; read it before quoting one.

## Choosing between overlapping capabilities

Several engines can technically produce a "diagram." Rule of thumb:

| You have... | Use |
|---|---|
| Numeric/tabular data to chart | chart-engine (`kind: "echarts"`) |
| Mermaid syntax already written, or the user explicitly says "mermaid" | mermaid-engine (`kind: "mermaid"`) |
| A process/flow you're describing from scratch, want animation + docgen's own glyph vocabulary | docgen's native `flowchart` (`kind: "flowchart"`, the default) |
| A codebase or system's actual structure to explore interactively | graph-engine (not embeddable in a document — it's its own interactive viewer) |
| Country/region-level data | docgen's `kind: "choropleth"` (real boundaries, value-per-country) or `kind: "geo_map"` (schematic points/routes) — choropleth for "value per country", points/routes for "specific named locations and connections between them" |
| Genuine 3D spatial/architecture structure | docgen's `isometric3d.py` |

When two engines could both technically do it, prefer the one with native docgen integration
(fewer moving parts, same theme system) unless the other has a capability docgen's native
renderers lack (e.g. chart-engine's ~19 extra chart types, mermaid-engine's ER/class diagrams).

## Verifying the whole package after any change

```bash
# From the Ultimate Engine/ root:
cd tools/visual-engine && npm install && npm test && npm run simulate && cd ../..
cd tools/mermaid-engine && npm install && npm test && cd ../..
python3 -m tools.docgen.cli build tools/docgen/sample.md   # then rm the output — it's a demo, not a deliverable
node tools/graphify/build.mjs && rm -rf graphify-out        # same — scratch output

# The broadest single check — builds every figure kind the engine has, through the real CLI,
# and fails closed if any renderer's collision/sourcing gate rejects its geometry:
python3 -m tools.docgen.cli build examples/capability-gallery.md
```

**Keep `npm test` before `npm run simulate`.** `run_simulations.mjs` rewrites
`renders/golden/*` — the same baselines `tests/regression.test.mjs` compares against — so running
simulate first silently re-baselines any rendering change and destroys the drift signal. The `&&`
above is doing real work; don't split it into two independent commands.

If a golden legitimately drifts, classify it under `tools/visual-engine/renders/diffs/` before
re-baselining (see `2026-08-19-axis-name-placement.md` for the format and a worked example).
If all of these pass, the core of every engine is confirmed working. See `PROVENANCE.md` for
the fuller verification record (deep completeness audits, portability sweeps, de-branding
re-sweeps) from this package's own construction.

## What this package deliberately does NOT do

See `CAPABILITIES.json`'s `notImplemented` fields on each engine for the exhaustive, verified
list. In short: no Gantt-as-a-preset (use chart-engine's custom-series recipe), no generic
auto-layout for docgen's own node/edge diagrams (graph-engine has auto-layout, but for its own
graph data, not docgen figures), no swimlane/BPMN-lane diagrams, no Venn diagrams, no
mindmap/kanban/gitgraph (Mermaid types the underlying library doesn't implement). These are
named, researched gaps, not oversights — each entry says what to use instead where one exists.
