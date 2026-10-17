---
name: graph-engine
description: Generate and view interactive codebase/system graphs — directory structure, dependency graphs, pipeline-flow diagrams, coverage graphs — with force-directed, hierarchical-tree, radial, and real 3D layouts. Use when asked to map, visualize, or explore how a codebase or system is structured/connected, or for any node-link graph that needs interactive exploration rather than a static image.
---

# graph-engine — interactive node-link graphs

Path: `tools/graphify/`. Node.js. Fully offline (both the 2D and 3D rendering libraries are
vendored locally — no CDN, verified this session).

## Build a graph, then view it

```bash
node tools/graphify/build.mjs              # structure graph of the current host root
ENGINE_HOST_ROOT=/path/to/repo node tools/graphify/build.mjs   # ...or of any other tree
node tools/graphify/build-deps.mjs         # dependency graph — Python src/-rooted example
node tools/graphify/build-pipeline.mjs     # pipeline-flow graph — from pipeline.example.json (data, not code)
node tools/graphify/build-coverage.mjs     # coverage graph — detector-plugin-shaped example

# Then view — MUST be served over http(s)://, not opened as a bare file:// path
# (the ?g= query-driven script injection is blocked under the file: origin's security model):
bash tools/graphify/open.sh graph      # auto-serves + opens an app window
# or manually: python3 -m http.server <port>, then open tools/graphify/graph-view.html?g=graph
```

Only `build.mjs` is host-agnostic out of the box. **Which tree it maps** comes from the same
host-root resolution everything else in this engine uses — `ENGINE_HOST_ROOT` env var >
`engine.config.json`'s `docSystem.hostRoot` > `git rev-parse --show-toplevel` > this engine's
own directory (see `CONFIGURATION.md`). Output always lands in this engine's own
`graphify-out/`, whatever is being scanned, so mapping a tree never writes into it — safe to
point at a read-only or sensitive directory. The other three are **worked examples**
tuned to one Python project's `src/`-rooted layout — either point `engine.config.json`'s
`graphify.srcRoot`/`detectorsDir`/`frontendPublicDir` at your own project's shape, or copy the
files and adapt the parsing logic for a different language. `build-pipeline.mjs` is the
easiest to adapt: its steps are external DATA (`pipeline.example.json`), not code — author your
own file in the same shape and point `graphify.pipelineStepsFile` at it.

## Viewer controls (`graph-view.html`)

- **Fit** — recenter/zoom to the whole graph.
- **Layout** — cycles Force → Tree ↓ → Radial ⊙. Uses `dagMode`, a feature already built into
  the vendored force-graph library — best for directed/hierarchical graphs (e.g. `deps`); falls
  back to force layout silently for graphs with cycles.
- **3D** — real WebGL 3D, lazy-loaded from a locally vendored file (not a CDN — this was a real
  bug, fixed this session; see `PROVENANCE.md` if you're auditing for regressions).
- Search box — find + center on a node by label/id substring.

## What this engine does NOT do

- **Clustering / community detection** — node `type` only drives a flat color legend, not a
  computed grouping layout.
- **Subgraph filtering** — search centers/zooms to the first match; there's no isolate-by-type
  filter UI.

If you need either, that's unbuilt — don't claim graph-engine has a capability it doesn't; say
so and either build a small addition or use the raw `graph.json`/`deps.json` node-link output
with your own filtering logic instead.

## `vault-graph-engine/` — a spec, not a working tool

A sibling directory at the package root, `vault-graph-engine/`, contains a design spec
(`VAULT_GRAPH_SPEC.md`) for a specific sibling product's future in-app credential-vault
graph UI, plus a copy of the same vendored 2D library. **It has zero consuming
implementation** — no code reads the spec or produces a working view. Don't present it as a
working capability. If you need something like what it describes (radial hierarchy layout,
per-kind node sizing, a tree-view toggle), graph-engine's own Tree/Radial `dagMode` layouts
(above) are the closest already-working generic equivalent — build product-specific chrome
(lock icons, grant overlays, etc.) as a separate downstream integration, not inside this
generic engine.
