# Ultimate Engine

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![A FreeXStudio product](https://img.shields.io/badge/a%20product%20of-FreeXStudio-black.svg)](https://freexstudio.com)

**A standalone, offline document, figure and blueprint engine with a governance layer.**
Write Markdown; get a self-contained, design-system HTML document whose figures are numbered, sourced,
explained, linked to the text and readable by a machine — and a rule layer that refuses to build a
document that leaks a secret, contradicts its own numbers, or claims more than it can prove.

Ultimate Engine is a product of **[FreeXStudio](https://freexstudio.com)** · licensed under the
[Apache License 2.0](LICENSE) · contributions welcome ([CONTRIBUTING.md](CONTRIBUTING.md)) ·
security reports: [SECURITY.md](SECURITY.md).

## Why it exists

Documentation rots in a predictable way: counts go stale, plans get written in the present tense,
citations point at files that moved, a chart quietly stops matching its data. Ultimate Engine turns
those failure modes into **failing checks** instead of review comments.

- **Figures that explain themselves** — 15 native figure kinds (flowchart, state, system map,
  dependency graph, sequence, isometric 3D, layered workflow, geo map, choropleth, sankey, bar, radar,
  pie, timeline, heatmap), 23+ chart families, Mermaid diagrams. Every figure carries a reader
  question, an insight, numbered captions, two-way links with the prose, and a data-source record.
- **Offline and deterministic** — no CDN, no browser, no network at build time; the same input gives
  the same bytes (golden renders are compared byte for byte).
- **A module explorer** — a zoomable, clickable map of a hierarchy with a panel and a reader.
- **A project census** — measures any repository's documents (fresh, outdated, stamped, crossed out)
  and code from its own git tree, and reports every number with the rule that produced it.
- **Fail-closed correctness gates** — one command, `python3 -m tools.health`, answers "is everything
  green?"; a skipped check is reported as unknown, never as a pass. Retained counter-examples prove
  each gate fires.
- **A leak/secret sanitizer** before every export, plus git hooks and a server-side secret scan.

## Quick start

```bash
git clone https://github.com/FreeXStudio-Platform/ultimate-engine && cd ultimate-engine
python3 -m pip install PyYAML                    # Python 3.11+; the tests spawn `python3`
npm ci && (cd tools/visual-engine && npm ci) && (cd tools/mermaid-engine && npm ci)
bash tools/hooks/install.sh                      # once per clone
python3 -m tools.health                          # structure, rules, consistency, build, tests

# Build the capability gallery — one working example of every renderable kind:
python3 -m tools.docgen.cli build examples/capability-gallery.md
```

Open `examples/capability-gallery.html` in a browser (toggle the theme) to see what it makes.
Releases are tagged `vMAJOR.MINOR.PATCH`; the tag equals `PROJECT_VERSION`, and `CHANGELOG.md` is the
history.

**Start here:**
- `examples/capability-gallery.html` — **one working example of every renderable kind**, in a
  single self-contained file: all 15 native docgen figure kinds, 5 chart-engine families, and a
  Mermaid diagram, each with a real `reader_question`/`insight` pair and every number sourced
  from a documented, reproducible measurement. Open it in a browser and toggle the theme. Build
  it yourself with `python3 -m tools.docgen.cli build examples/capability-gallery.md`; its
  sidecar (`capability-gallery_spec.json`) is a copy-paste reference for the JSON shape of
  every figure kind.
- `docs/design/FIGURE_SYSTEM.md` — **how a figure is scoped, numbered, explained, linked to the text and read by a machine**: the attribute contract, the hover law, the ids, `[[fig:ID]]`, the reading key under every figure, and the two AI-only JSON files (`<stem>.blueprint.json`, `<id>.figure.json`). Read it before changing how a figure looks or behaves.
- `CAPABILITIES.json` — an **index** of every capability, entry point and format, complete for the figure kinds it lists and extended in `governance` with the health system, the build cache and the git moat. **It is an index, not a proof**: what proves a capability works is the retained counter-example for it, not its presence here.
- `USAGE_GUIDE.md` — practical walkthroughs and worked examples for each engine.
- `CONFIGURATION.md` — how to point this at a host project's own layout (zero setup required).
- `INTERPRETATION.md` — how to extract meaning from a figure (not just render one), plus
  verified collision/precision guarantees and color/layout conventions per figure type.
- `skills/` — Claude Skills wrapping each engine, for an agent picking this package up cold.

## What's inside

```
tools/
  docgen/           Document generation engine (Python). Markdown -> self-contained
                    HTML/JSON (PDF optional via weasyprint). 7-gate leak/secret
                    sanitizer runs before every export. 15 native figure renderers, ALL
                    reachable through one <!-- figure:ID --> + sidecar-JSON pipeline:
                    flowchart/state/system-map/dependency-graph/sequence/isometric-3D/
                    layered-workflow/geo-map/CHOROPLETH (real country boundaries)/
                    sankey/bar/radar/pie/timeline/heatmap. Every kind accepts optional
                    reader_question/insight fields (see INTERPRETATION.md). Every figure
                    is numbered, scoped and explained, and text and figures link both
                    ways; `--formats html,blueprint` also writes the AI-only
                    <stem>.blueprint.json (docs/design/FIGURE_SYSTEM.md). Bridges to
                    visual-engine (echarts_bridge.py) and mermaid-engine
                    (mermaid_bridge.py) for figure kinds it doesn't natively cover.
  visual-engine/    Quantitative chart rendering engine (Node/ECharts 6.1.0, SSR).
                    23+ chart families. Ships its own MCP stdio facade ("doc-visuals",
                    7 tools) and a preset library of reviewed chart-job shapes.
  mermaid-engine/   Offline Mermaid-syntax rendering (Node, beautiful-mermaid, MIT) —
                    flowchart/sequence/class/state/ER/xychart. No browser, no CDN.
  graphify/         Codebase-cartography / blueprint-graph engine (Node). Vendors
                    force-graph@1 AND 3d-force-graph@1 (both MIT, sha384-pinned) —
                    force-directed, hierarchical-tree, radial, and real 3D layouts,
                    all fully offline. Builds a directory-structure graph of whatever
                    repo it's dropped into (build.mjs is generic); build-deps.mjs,
                    build-pipeline.mjs, build-coverage.mjs, and build-admin-catalog.mjs
                    are worked examples — see engine.config.json to point them at a
                    different codebase.
  project_index/    A flat JSON registry of every document/chart/graph/diagram built
                    for a project, plus an HTML dashboard — so large-scale work stays
                    navigable instead of losing track of what already exists.
                    `verify` checks the registry against the filesystem (stale entries,
                    duplicate paths, built-but-unregistered files) so the map can be
                    falsified rather than merely trusted.
  census/           Measures a project's documentation system from its own git tree
                    (documents, updated vs outdated, crossed out, stamped as a source of
                    truth and whether the stamps hold, completeness by dimension) and its
                    Python code hierarchy, then builds a report of varied figures and two
                    explorers. Every number carries its rule; no composite score.
  lib/              Shared Node config loader (engine-config.mjs) used by graphify
                    and (indirectly) visual-engine.

vault-graph-engine/
  A second, independent force-directed graph engine — vendors force-graph@1.51.4
  (MIT, sha384-pinned) plus VAULT_GRAPH_SPEC.md, a written design contract for an
  interactive node-graph navigation UI. This is NOT a copy of anything in tools/ —
  it's a separate, purpose-built graph engine from the second source project, kept
  distinct because it solves a different problem (an in-app navigation surface vs.
  graphify's codebase mapping). It has no implementation yet, only the vendored
  renderer + the spec — treat it as a design contract to build against, not a
  running tool. graphify's own hierarchical/radial layout (above) is the closest
  already-working generic building block if you need something like what it
  describes.

examples/           capability-gallery.md + _spec.json + the built .html — every
                    renderable kind in one document (see "Start here" above). Also the
                    reference for each figure kind's sidecar JSON shape.

engine.config.json  Universal path/tool configuration — every field has a working
CONFIGURATION.md    default; edit only to point this engine at a host project's own
                    doc-governance layout, source-tree shape, or non-default tools.
CAPABILITIES.json   Machine-readable capability index (see "Start here" above).
skills/             Claude Skills — one per engine plus a router, for an agent.
```

## How the pieces relate

- **docgen** is the authoritative document engine — it owns layout, typography,
  the 7-gate sanitizer, and native diagram rendering (flowcharts, sequence
  diagrams, sankeys, geo-maps, choropleth world maps, isometric 3D views).
- **visual-engine** is docgen's chart-rendering dependency for anything
  quantitative (bar/line/heatmap/scatter/treemap/etc.) — docgen calls out to it
  via `echarts_bridge.py` rather than duplicating chart logic.
- **mermaid-engine** is docgen's dependency for Mermaid-syntax diagrams
  specifically — reached via `mermaid_bridge.py`, same pattern as visual-engine.
- **graphify** is a separate, narrower tool: fast, token-cheap navigation of a
  known codebase via an interactive (force/hierarchical/radial/3D) graph view.
  It does not share code with docgen, visual-engine, or mermaid-engine.
- **project_index** is cross-cutting — a registry of what any of the above have
  produced for a project, not itself a rendering engine.
- **census** measures a *project's* documents and code (any project's, through a
  profile) and composes docgen, visual-engine and mermaid-engine into a report; it
  changes none of them.
- **vault-graph-engine** is unrelated to all of the above — a different
  project's own force-graph design spec, included because it was explicitly
  asked for. It has no implementation (see its section above).

## Running it

**Engine health — start here.** One command answers "is everything actually green?", replacing four
suites nobody ran together. It fails closed: a check that raises is a FAIL, and a SKIP is reported as
unknown, never as a pass.
```bash
bash tools/hooks/install.sh          # once per checkout — .git/hooks cannot arrive with a clone
python3 -m tools.health              # fast: structure, rule layer, consistency, build
python3 -m tools.health --full       # everything, including both npm suites
python3 -m tools.health --json       # machine-readable report on stdout
```
Every run appends one line to `.health/runs.jsonl` (timestamp, commit sha, dirty flag, duration,
counts, failed ids) — `--no-run-log` opts out. `tools/hooks/install.sh` installs the two git hooks:
`pre-commit` (classification placement + a secret scan of the staged index) and `pre-push` (engine
health + a secret scan of the commits being pushed). Health then fails if either goes missing,
drifts, or stops invoking its gates, so the moat cannot quietly become inert.

**docgen** (Python 3.11+):
```bash
pip install -r tools/docgen/requirements.txt
# Run from the Ultimate Engine/ root so `tools` resolves as a package:
python3 -m tools.docgen.cli build tools/docgen/sample.md

# One or many documents build as a corpus through a shared incremental cache. An unchanged
# document whose outputs still exist is skipped, and the run prints what it measured:
python3 -m tools.docgen.cli build tools/docgen/sample.md tools/docgen/sample-multi-figure.md \
    examples/capability-gallery.md -o build/ --formats html,json --cached
#   built 3 doc(s) in 3.359s — 0 reused from cache, 3 rebuilt
#   built 3 doc(s) in 0.003s — 3 reused from cache, 0 rebuilt      <- second run
python3 -m tools.docgen.cli index build/ -o build/index.html      # browsable PUBLIC docs index
```
The three paths are spelled out on purpose: `tools/docgen/*.md` looks tidier but also matches the
engine's own documentation, which carries no doc-system header — so the glob exits 1, blocks those,
and prints a `built N doc(s)` line counting files rather than documents.

*(The exact ratio is deliberately not restated here. It was `4 of 6` until `tools/docgen/gallery.md`
was converted to the canonical convention, which made it `3 of 6` in the same commit that wrote the
sentence — the third time this one paragraph has gone stale. `OG-90`; `docs/process/RULES.md` Rule 2.)*

The cache key covers the source, its sibling spec, the formats, the output directory, every file
under `tools/docgen/`, **the out-of-tree renderers** (`tools/mermaid-engine/`,
`tools/visual-engine/adapters/` and both `package-lock.json`), **and the doc-governance rule layer** — so a rule change that would newly
block a document invalidates it rather than serving a stale artifact. `--strict` ignores the cache
entirely: a skipped build cannot re-assert an advisory verdict.

**visual-engine** (Node >=20):
```bash
cd tools/visual-engine && npm install
npm test               # 30 unit tests
npm run simulate       # 22 acceptance simulations
node adapters/echarts/cli.mjs render <job.json>
node mcp/server.mjs     # starts the "doc-visuals" MCP stdio server
```

**mermaid-engine** (Node >=20):
```bash
cd tools/mermaid-engine && npm install
npm test                              # 6/6 diagram types
node render.mjs diagram.mmd -o out.svg
```

**graphify** (Node >=20, needs the `codemap` CLI — a clear error names it if missing):
```bash
node tools/graphify/build.mjs                # generic structure map of the host root
ENGINE_HOST_ROOT=/path/to/repo node tools/graphify/build.mjs   # ...or of any other tree
bash tools/graphify/open.sh graph             # serves + opens the interactive viewer
```
`graph-view.html` must be served over `http(s)://`, not opened as a bare `file://` path
(`open.sh` handles this for you). `build-deps.mjs` / `build-pipeline.mjs` /
`build-coverage.mjs` / `build-admin-catalog.mjs` are worked examples tuned to one
Python project's layout — see `CONFIGURATION.md` to point them at a different codebase.

**project_index** (Python, stdlib only):
```bash
python3 -m tools.project_index.cli register --id ... --path ... --type document --title "..."
python3 -m tools.project_index.cli dashboard   # writes PROJECT_INDEX.html
python3 -m tools.project_index.cli verify      # exit 1 if any entry no longer resolves
```

**census** (Python, stdlib only; the report step uses docgen and its bridges):
```bash
python3 -m tools.census measure PROFILE.json --root . --out census.json
python3 -m tools.census report  PROFILE.json --root . --out docs/census/   # builds the document
python3 -m tools.census inventory --engine-root .                          # how many figure models the engine can draw
```
Profile example: `examples/census.profile.example.json`; design and every definition: `docs/design/PROJECT_CENSUS.md`.

**vault-graph-engine**: no build step — `force-graph.min.js` is a drop-in
`<script>` include; read `VAULT_GRAPH_SPEC.md` for the intended node-sizing/
liveness behavior before wiring it into a UI. It is a spec, not a running tool
(see its section above).

## What was deliberately left out

See `PROVENANCE.md` for the full list and reasoning — in short: both sources'
own `node_modules`/`__pycache__` (regenerable via the install commands above),
brand logo artwork, one project's domain-specific attack-animation library, one
project's own contract-bank linter, and two pre-rendered demo files that turned
out to bake in the real project's actual internal changelog as sample content.
A neutral placeholder mark (`tools/docgen/assets/engine-mark-placeholder.svg`)
stands in for the removed logo so `docgen` still renders without a missing-file
error — swap it for a real mark before shipping anything built with this.
