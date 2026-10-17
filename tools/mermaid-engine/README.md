# mermaid-engine

Offline Mermaid diagram rendering — flowchart, sequence, class, state, ER, and XY-chart — to SVG
or ASCII. No browser, no headless Chromium, no CDN at runtime.

## Why this exists

`tools/docgen` and `tools/visual-engine` cover documents, structural diagrams, and data charts,
but neither speaks Mermaid's text syntax — the most widely recognized "type a diagram as text"
format. This engine fills that gap with `beautiful-mermaid` (MIT, npm), a pure-TypeScript
reimplementation that renders synchronously with zero DOM dependency — not the official
`mermaid` package (which still requires a real or shimmed browser DOM to lay out text; see
`PROVENANCE.md` for the research trail behind this choice).

## Usage

```bash
npm install                                  # once, ~4 packages, no browser/Chromium
node render.mjs diagram.mmd -o diagram.svg   # SVG
node render.mjs diagram.mmd --ascii          # ASCII (for terminal/plain-text output)
printf 'graph TD\nA-->B\n' | node render.mjs --stdin
```

> **The header and the first statement must be on separate lines.** `graph TD; A-->B` is valid upstream Mermaid, but the vendored `beautiful-mermaid` parser rejects it with `Invalid mermaid header`. This quickstart documented the inline form and had never been run (`OG-142`).

Options: `--bg '#hex'`, `--fg '#hex'` (the two-color theme system — every other color is derived
from these), `--theme name` (one of beautiful-mermaid's 15 built-in themes; an unknown name is REFUSED with the list, and explicit `--bg`/`--fg` win over the theme's own pair).

## Supported diagram types (exactly 6 — this is the real, verified scope)

| Mermaid syntax | Type |
|---|---|
| `graph` / `flowchart` | Flowchart |
| `sequenceDiagram` | Sequence diagram |
| `classDiagram` | Class diagram |
| `stateDiagram-v2` | State diagram |
| `erDiagram` | Entity-relationship diagram |
| `xychart-beta` | XY chart (bar/line/combined) |

Verified working via `npm test` (`test.mjs` — real end-to-end render of one example of each
type, checked into this session's evidence).

## NOT supported, and where to go instead

Mermaid's `gantt`, `gitGraph`, `mindmap`, `journey`, `kanban`, `pie`, `quadrantChart`, and
`timeline` diagram types are **not implemented by the underlying library** — this is a real,
verified limit of `beautiful-mermaid` (confirmed against its own source, not assumed from the
README). If you need one of these:

- **Gantt / task timelines**: use `tools/visual-engine`'s ECharts adapter with a `custom` series
  (`renderItem` + time axis + category axis — one rect per task). This is ECharts' own
  documented, official Gantt recipe, not a workaround — see `CAPABILITIES.json`.
- **Pie charts**: `tools/visual-engine` already has a native `pie`/`donut` chart type — no need
  for Mermaid's.
- **Mindmap / kanban / git-graph / journey / quadrant / timeline**: no equivalent exists
  elsewhere in this engine today. Genuinely out of scope until a specific need justifies adding
  a dedicated renderer (see `PROVENANCE.md`'s research notes for what was evaluated and why
  nothing was adopted for these).

## Why not the official `mermaid` package or `mermaid-cli`

Researched and rejected deliberately, not overlooked — see `PROVENANCE.md` for the full
comparison. Short version: the official `mermaid` npm package cannot render to SVG in bare
Node.js (it needs real DOM text-measurement APIs); the only ways to get 100%-official-fidelity
rendering are a real headless browser (`@mermaid-js/mermaid-cli`, via Puppeteer) or a DOM-shim
package — both pull in a real or fake browser stack, and Puppeteer alone means vendoring an
~150-280MB platform-specific Chromium binary. That directly conflicts with this engine's
portability goal (see `../../CONFIGURATION.md`) far more than accepting a 6-type-instead-of-20+
scope limit does. `beautiful-mermaid` was chosen for genuine production adoption (MIT,
real npm downloads, active maintenance) over the even-lighter-but-unproven Rust/WASM
reimplementations (Merman/mmdr/Selkie — all alpha-tagged as of this research).

## A note on the rendered SVG's fonts

`beautiful-mermaid` unconditionally injects a live `@import url('https://fonts.googleapis...')`
into its SVG output — there is no library option to suppress this (confirmed: passing a custom
`font` value only changes which font name is requested from the same CDN). `render.mjs` strips
this and substitutes a system-font stack (`system-ui, -apple-system, "Segoe UI", Roboto,
sans-serif`) before writing output, so every SVG this engine produces is genuinely offline —
consistent with `engine.config.json`'s `security.allowRuntimeCDN: false` and how
`tools/graphify`'s vendored force-graph/3d-force-graph libraries are handled. If you call
`beautiful-mermaid` directly instead of going through `render.mjs`, you will get the CDN
`@import` back — always render through this wrapper, not the library directly.

## License

`beautiful-mermaid` MIT (Craft Docs). Its own dependencies: `elkjs` (layout engine,
`EPL-2.0 OR GPL-3.0-or-later` — weak-copyleft but OSI-approved and safe to use as an unmodified
library dependency, not a pure-permissive license if that distinction matters for your use),
`entities` (HTML entity encoding, MIT).
