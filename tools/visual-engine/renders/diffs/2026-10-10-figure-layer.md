# Golden drift — 2026-10-10 — the figure layer (all 14 goldens)

**Classification: `FIGURE_LAYER_APPROVED`** — a deliberate engine change (OG-250 … OG-261), not an upgrade of ECharts
and not an unexplained regression. Every golden was re-rendered from its committed job and compared with the committed
SVG *before* re-baselining (`npm test` red first, then this record, then `npm run simulate`).

## What changed in every golden (additive, by design)

| Change | Why |
|---|---|
| Root gains `data-fig` / `data-fig-kind` / `data-fig-focus` / `data-fig-legend` and `class="ve-fig"` | One scope per figure; the document runtime reads these |
| One scoped `<style data-ve>` replaces ECharts' own `<style>` | ECharts' per-SVG `.zr-cls-N:hover{fill:…}` rules were renumbered from 0 in **every** chart, so 28 inlined charts shared eight class names with 28 different bodies |
| Every mark gains `data-s` / `data-i` / `data-t` / `data-k` / `data-id` (+ `data-nb` / `data-eg` / `data-en` on graphs) and a `<title>` | A dot used to carry only two numbers; nothing said what it was |
| `id` / `url(#…)` / `href="#…"` are prefixed with the figure scope | `zr-c0` / `zr-g0` existed in every chart; `url(#zr-g0)` resolved to the first gradient in the page |

Size grows 1.1×–3.3× (a style block, attributes and a title per mark). `SIM-12-dense` (2,500 marks) grows 9.5 %.

## What changed in the drawing, per family

| Golden | Family | Paths changed | Max shift | Reading |
|---|---|---|---|---|
| `SIM-12-dense`, `SIM-17-svg`, `SIM-20-print` | scatter, bar_horizontal, bar | 0 | 0 px | **Purely additive.** Same geometry, same fills, same text. |
| `SIM-08-queue-latency` | line | 22 of 43 | 34 px | Plot area re-flowed by the single layout pass (title, subtitle, legend, grid no longer overlap); line width 2 → 2.5, point size 5 → 7 (`themes/*.json`). |
| `SIM-03-stage-reconciliation` | funnel | 9 of 10 | 11 px | Tile labels take the readable ink (they were invisible dark-on-dark outside the tile). |
| `SIM-04-workflow-pipeline`, `SIM-11-topology` | graph | 10 of 17, 8 of 14 | 65 px, 67 px | Larger node symbols and a re-flowed layout; edge ink now a visible neutral rather than a 1px hairline. |
| `SIM-09-incident` | timeline | 9 of 14 | 48 px | Label placement moved clear of the dots; right edge no longer clipped. |
| `SIM-02`, `SIM-05`, `SIM-06`, `SIM-07`, `SIM-10`, `VIS-DET-001` | heatmap | 2–32 of 18–34 | 20 px | Plot area shifted 20 px for the legend/title block; **each cell label is now drawn in the ink its own cell needs** (WCAG ≥ 4.5:1 by `contrast.mjs`) and the 2 numerals at the ends of the scale legend are now printed (`texts` +2). The 1–7 `stroke-width` rules removed per golden are the label halos (`textBorderWidth: 0`). |

## What was verified, and what was not

- `npm test` was red on exactly three tests before this record (goldens, themes, MCP snapshot) and is green after
  `npm run build:themes`, the MCP snapshot regeneration and `npm run simulate`; the 22 acceptance simulations are unchanged.
- The behavioural claims (no hue change on hover, no flicker, adjacency lights neighbours and joining edges, a tooltip on
  every mark, nearest-mark assist) are **not** provable from bytes. They were measured in headless Chromium against a
  built document (`tools/tests/browser/figure_runtime_check.mjs`) — see `docs/design/FIGURE_SYSTEM.md`.
- Not re-measured here: the PNG export (`renderPNG`) of these figures. It rasterises the SVG; `SIM-17` PNG still passes
  `render.test.mjs`, the others were not individually inspected.
