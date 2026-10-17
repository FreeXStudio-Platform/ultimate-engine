# Golden drift — 2026-10-10 — the operator's second review of the report's charts (all 14 goldens)

**Classification: `FIGURE_REFINEMENT_APPROVED`** — deliberate changes to the figure layer and to the graph builder
(`OG-278` … `OG-282`), not an ECharts upgrade and not an unexplained regression. Every golden was re-rendered from its
committed job and compared with the committed SVG *before* re-baselining (`npm test` red first on `golden renders reproduce
byte-identically from their jobs`, then this record, then `npm run simulate`).

Found by reading the rebuilt insight report in a browser, chart by chart.

## 12 of 14 goldens: one added rule

`SIM-02`, `-03`, `-05`, `-06`, `-07`, `-08`, `-09`, `-10`, `-12`, `-17`, `-20`, `VIS-DET-001` (heatmap, funnel, line,
timeline, scatter, bar): **+107 to +124 bytes each, nothing else.** The scoped `<style>` gains

```
svg[data-fig="…"][data-ve-js] [data-s].ve-on[data-k="edge"]:not([fill="none"]){fill-opacity:1}
```

— a lit edge's ARROWHEAD is a filled shape, and the existing lit-edge rule only raised stroke opacity, so a lit line ended in a
half-transparent head. No path, fill, text or title changes (`pathsSame`, `fillChanged` 0, `textsSame` for all twelve).

## 2 of 14 goldens (`SIM-04-workflow-pipeline`, `SIM-11-topology`, the graphs): the ring and the direction palette

| Change | Why |
|---|---|
| The builder lays the circular ring out itself (`layout` reaches ECharts as `none` with fixed positions) and gives it the **proportions of its box** | ECharts' view fit stretches x and y independently; with unit-circle coordinates in a non-square box every node symbol was squashed into an ellipse (measured: 80x94 px for a 47.8 px symbol) |
| Each node's label faces away from the ring: right half `right`, left half `left`, a node within ~9° of the vertical `top`/`bottom` (text-anchor `start` x7 becomes `start` x3, `middle` x2, `end` x2 on SIM-04) | ECharts put every label to the right of its dot; on the left half those labels sat inside the circle, on top of the lines |
| Left and right margins are sized from the labels each side actually carries | A long name on one side no longer takes room from the other |
| Each link carries its source node's colour | ECharts 6 does not honour `lineStyle.color: "source"` (probed: three nodes, three colours, one stroke on every edge). The two goldens' nodes carry no colour of their own, so their edges stay `#4A7FC1` (unchanged); the report's graph, whose nodes are coloured by conformance, now draws every line in the colour of the module it leaves |
| Graph figures gain the direction palette (`--ve-out` / `--ve-in` / `--ve-both`, dark and light) and the rules that use it: +5.9 KB on SIM-04, +4.0 KB on SIM-11 | While a node is focused, the lines leaving it, entering it or running both ways are drawn in the palette; the CSS-only fallback carries one rule per node and direction (the diagrams people read are under 160 marks, so the fallback stays) |
| A node that no link touches is outlined in dashes and its tooltip says "isolated: no connection in the data" | The report's `configuration` module drew with no line at all and nothing said whether that was a design or a bug |

Path **values** change for the two graphs (`17->17`, `14->14` paths, the same counts) because the ring is laid out in the
box's proportions; **counts, fills and text strings are unchanged** (`fillChanged` 0, `textsSame`).

## No golden exists for the other three changes — and the tests say so

The treemap (centred, fitted, wrapped names), the radar (a visible web) and the boxplot (lit candles) have no committed
golden. They are pinned by `tests/refinements.test.mjs` instead (names never broken inside a word and every line inside its
tile, checked on the live layout; web opacity band; gradient body with a lighter rim) and by the report's own render.

## What was verified, and what was not

- `tests/refinements.test.mjs` (16 cases) fails against the previous builders and passes after; the hover-law test now names
  its one declared exception (the graph direction palette) and nothing else may recolour.
- Real-browser: `figure_runtime_check.mjs` hovers a graph node and reads the classes and computed strokes of its lines in both
  themes (`out` `rgb(76, 201, 240)` / `in` `rgb(245, 138, 192)` dark; `rgb(10, 122, 161)` / `rgb(184, 51, 125)` light).
- Not re-measured here: the PNG export of these figures (it rasterises the SVG, whose geometry changed only for the two graphs).
