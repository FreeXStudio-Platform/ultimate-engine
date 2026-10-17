---
name: mermaid-engine
description: Render Mermaid-syntax diagrams (flowchart, sequence, class, state, ER, XY-chart) to SVG or ASCII, fully offline. Use specifically when the user says "mermaid" or provides/wants Mermaid diagram-language text — for other diagram needs, prefer document-engine or chart-engine, which have broader native coverage.
---

# mermaid-engine — offline Mermaid rendering

Path: `tools/mermaid-engine/`. Node.js, `beautiful-mermaid` (MIT). Setup once: `npm install`
inside `tools/mermaid-engine/`.

```bash
node render.mjs diagram.mmd -o diagram.svg
node render.mjs diagram.mmd --ascii
printf 'graph TD\nA-->B\n' | node render.mjs --stdin
```

> **The header and the first statement must be on separate lines.** `graph TD; A-->B` is valid upstream Mermaid, but the vendored `beautiful-mermaid` parser rejects it with `Invalid mermaid header`. This quickstart documented the inline form and had never been run (`OG-142`).

## Supported — exactly 6 types (a verified, real limit, not a partial implementation)

`graph`/`flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram-v2`, `erDiagram`,
`xychart-beta`. Verified this session: `npm test` renders one real example of each to both SVG
and ASCII.

## NOT supported — say so plainly, don't attempt a workaround here

`gantt`, `gitGraph`, `mindmap`, `journey`, `kanban`, `pie`, `quadrantChart`, `timeline` are not
implemented by the underlying library. For Gantt specifically, use chart-engine's ECharts
custom-series recipe instead (`../chart-engine/SKILL.md`) — that's a real capability elsewhere
in this package, not a dead end. For the rest, there's no equivalent in this package today;
don't fake one.

## Embedding a Mermaid figure inside a docgen document

Use `kind: "mermaid"` in the document's figure sidecar spec (see `../document-engine/SKILL.md`)
— `tools/docgen/mermaid_bridge.py` handles the render call. **Do not call
`tools/mermaid-engine/render.mjs` output raw into a themed document without going through the
bridge** — the bridge defaults `bg`/`fg` to `var(--mermaid-bg)`/`var(--mermaid-fg)` (aliases
defined in `tools/docgen/tokens.py`) so the diagram tracks the document's dark/light theme
toggle. Passing literal `var(--bg)`/`var(--fg)` directly is a real bug (a CSS self-reference
cycle — the property becomes invalid, producing solid-black boxes with invisible text; this
actually happened during this package's build and is documented in `mermaid_bridge.py`'s
docstring and `PROVENANCE.md` if you want the full story).

## The CDN-font fix, if you ever call the library directly

`beautiful-mermaid`'s raw SVG output injects a live Google Fonts `@import` with no way to
disable it via its own options — `render.mjs` strips this and substitutes a system-font stack
before returning output. If you ever bypass `render.mjs` and call `renderMermaidSVG`/
`renderMermaidASCII` from `beautiful-mermaid` directly, you will get the CDN reference back —
always render through this package's `render.mjs`, never the library directly, to keep every
output genuinely offline.
