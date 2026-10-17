# graphify — manual, local-only system view (NO VPS / NO deploy)

A queryable directory-level map of the engine + whole system, for token-cheap navigation and
"how is this connected / what are we missing" questions. **Manual only** — never auto-runs, never deploys.

```bash
node tools/graphify/build.mjs                                  # (re)build graphify-out/graph.json from codemap
graphify query "<question>" --graph graphify-out/graph.json --budget 1500   # ask it without loading the corpus
```

**`graphify query` is a SEPARATE tool, not bundled with this package** — a pipx-installed CLI
(package name `graphifyy`) that happens to share the name "graphify" with this directory. It is
NOT this package's `tools/graphify/` scripts, ships no source here, and running the command
above without installing it separately will fail with "command not found." Everything else on
this page (`build.mjs` and its four siblings, `graph-view.html`) is fully self-contained in this
package and needs no separate install. If you don't have `graphify query` installed and don't
want to, use `graph-view.html` (below) to explore the built graph interactively instead — it
needs nothing beyond what's already in this directory.

- Output `graphify-out/` is local-only scratch output (gitignore it in a host repo) — never committed or pushed anywhere.
- Rebuild whenever you want a fresh view; it reads the current tree via `codemap` (deterministic, no model, no tokens).
- This is for understanding/structure only — it touches nothing in the engine and deploys nowhere.
- `build.mjs` (the structure graph) is host-agnostic and works against ANY codebase `codemap` can index.
  Which tree it maps comes from the standard host-root resolution (`ENGINE_HOST_ROOT` >
  `engine.config.json`'s `docSystem.hostRoot` > `git rev-parse --show-toplevel` > this engine's own
  directory) — so `ENGINE_HOST_ROOT=/path/to/repo node tools/graphify/build.mjs` maps that repo without
  copying anything anywhere. Output always goes to this engine's own `graphify-out/` regardless of what is
  being scanned, so mapping a tree never writes into it. `build-deps.mjs` / `build-coverage.mjs` /
  `build-pipeline.mjs` / `build-admin-catalog.mjs` are worked EXAMPLES tuned to one specific project's
  `src/`-rooted Python layout — see `engine.config.json`'s `graphify` section to point them at a
  different codebase, or copy+adapt them for a non-Python project.

## Viewing a graph — `graph-view.html`

Open `tools/graphify/graph-view.html?g=graph` (or `?g=deps|pipeline|coverage`) after building. Four controls:
- **Fit** — recenter/zoom to the whole graph.
- **Layout** — cycles Force → Tree ↓ → Radial ⊙. Tree/Radial use `dagMode`, a feature already built into
  the vendored 2D library (vasturiano/force-graph) — no new dependency. Best for directed/hierarchical
  graphs (e.g. `deps`); a graph with cycles falls back to plain force layout silently (the library's own
  behavior, not an error).
- **3D** — toggles a real WebGL 3D view, lazy-loaded from `vendor/3d-force-graph.min.js` (vendored
  locally, MIT, ~1.3MB — bundles three.js). **Fixed 2026-08-18**: this used to fetch
  `https://unpkg.com/3d-force-graph@1` live at click-time, silently failing offline. It is now fully
  offline-capable, matching the 2D library's own "no runtime CDN" rule (see `vendor/PROVENANCE.md`).
- Search box — type + Enter to find and center on a node by label/id substring.

Must be served over `http(s)://`, not opened as a bare `file://` path — browsers block the `?g=`
query-driven script injection under the `file:` origin's security model. `python3 -m http.server` from
the engine root (or any static file server) works.
