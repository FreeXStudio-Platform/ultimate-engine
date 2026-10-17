# Golden drift — 2026-10-10 — hover keeps a mark's own stroke colour (all 14 goldens)

**Classification: `FIGURE_LAYER_APPROVED`** — a deliberate change to the figure layer's hover rules (`OG-269`), not an
upgrade of ECharts and not an unexplained regression. Every golden was re-rendered from its committed job and compared
with the committed SVG *before* re-baselining (`npm test` red first, then this record, then `npm run simulate`).

Found by hovering a point in the rebuilt insight report: a line chart's white-filled, blue-ringed point turned its ring
**black** (`rgb(74,127,193)` → ink). The hover rule repainted the stroke of *every* filled mark, which is right for a bar
or a slice (it has no stroke of its own) and wrong for a mark whose stroke IS its colour.

## What changed in every golden (additive)

| Change | Why |
|---|---|
| Marks that draw a stroke in a colour of their own gain `data-sk="own"` (a line symbol's ring, a box-plot outline, a bubble's rim; white and grey seams do not) | The stylesheet needs to tell a coloured stroke from a separator without parsing colours at hover time |
| The scoped `<style>` splits the filled-mark hover rule in two, and the pin rule likewise: marks without their own stroke keep the ink outline; own-stroke marks thicken (2.6 px) and brighten, and never repaint | A hovered blue point must stay blue |

Size grows by about 600 bytes per golden (one extra rule, one extra pin rule, a few attributes). **No path, fill or text
changes** (`pathsSame` for all 14, `fillChanged` 0, `textsSame`). Geometry is untouched.

## What was verified, and what was not

- Contract test `tests/figure-layer.test.mjs` ("a mark that draws a stroke in its own colour keeps it on hover and pin"):
  fails against the previous layer, passes after. The real-browser assertion in `figure_runtime_check.mjs` reads the
  computed stroke of a hovered line-chart point before and while hovered: `rgb(74,127,193)` → `rgb(234,238,245)` against the
  previous layer (FAIL), identical after (PASS).
- Not re-measured here: the PNG export of these figures (it rasterises the SVG, which is unchanged in geometry).
