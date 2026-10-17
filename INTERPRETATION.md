<!-- title: INTERPRETATION -->
# Interpretation — reading the meaning out of a blueprint, not just admiring it

A figure this engine produces is a VIEW of the same underlying system, calculation, or dataset
that the surrounding document already describes in prose and numbers — not decoration bolted on
afterward. This file is two things: (1) the mechanism for carrying a figure's *meaning* as data,
not just its geometry, so an agent (or a person) can extract the insight without re-deriving it
by eyeballing pixels, and (2) a verified account of what precision this engine actually
guarantees per figure type, and which color/layout conventions are real industry standards
versus this engine's own house style versus genuinely left to whoever is authoring the figure.

## Part 1 — the interpretive layer

### The mechanism

Every figure spec in this engine (`VisualSpec`, `SequenceSpec`, `SankeySpec`, `GeoMapSpec`,
`ChoroplethSpec`, `IsometricSpec`, `BarSpec`, `RadarSpec`, `PieSpec`, `TimelineSpec`,
`HeatmapSpec`, `LayeredSpec`, `MermaidFigureSpec` — every docgen native type) carries two
optional string fields:

- **`reader_question`** — the concrete question this specific figure answers. Mirrors
  chart-engine's own job-packet field of the same name, which is *mandatory* there (min 8
  characters, enforced by `visual-job.schema.json`) — docgen's native figures make it optional
  (nothing existing breaks) but the convention and the field name are deliberately identical, so
  authoring a figure asks the same question regardless of which of the five engines renders it.
- **`insight`** — the plain-language conclusion a reader should walk away with: the thing the
  picture makes obvious that the raw numbers or prose alone don't. Mirrors chart-engine's own
  `text_summary` field, which that engine's own Gate G7 treats as required before a chart may
  enter a "source-of-truth" document (advisory otherwise — a chart can exist as a draft without
  one, but isn't authoritative until it has one). The same convention applies here: fill these in
  for anything meant to be a real source of truth, not just a technically-correct picture.

Both are surfaced *visibly* in the rendered document — `components.figure()` renders them as a
distinct "figure-insight-block" directly under the figure, styled differently from the plain
caption (see `tools/docgen/tokens.py`'s `.figure-insight-block`/`.figure-reader-question`/
`.figure-insight` CSS). A reader does not have to infer the point of a chart from its shape
alone; the point is written next to it. Verified this session: built a real multi-figure
document exercising all 6 previously-unwired kinds (bar/radar/pie/timeline/heatmap/
layered_workflow) with `reader_question`/`insight` on every one — every block rendered
correctly, screenshotted and text-extracted.

For chart-engine figures embedded via `kind: "echarts"`, `generator.py` reads
`reader_question`/`text_summary` straight out of the nested job packet (chart-engine's own
mandatory/advisory fields) rather than requiring them to be duplicated — one field, one meaning,
regardless of which engine's job shape carries it.

### Why this matters more than the visual itself

The operator's own framing, preserved here because it's the point of this whole section: a
blueprint or graph is not created for its own sake. The same system that's fully documented in
prose and worked out on paper as calculations gets a SECOND, different view as a figure — and
that second view exists specifically because a graph, chart, or diagram surfaces patterns
(trends, outliers, clusters, structural relationships, risk concentration) that raw numbers and
text alone don't make visible. `insight` is where that extraction actually gets written down,
so it isn't lost the moment the figure is generated. A figure with an empty `insight` is either
a genuine work-in-progress or purely illustrative — treat it as unverified, not as a completed
analysis, the same way an unsourced number is treated as unverified (L16).

### Interconnection — documents, figures, and project_index as one system

- Every figure's `data_sources` (`DataSource.ref`) ties its numbers back to where they came
  from — the same mechanism whether the figure is a bar chart, a choropleth, or a sequence
  diagram. **This is a convention the engine carries, not a gate it enforces:** every spec's
  `data_sources` defaults to an empty list (`models.py`), so a figure with numbers and no
  `DataSource` renders without complaint today. This bullet previously claimed the opposite —
  "a number with no `DataSource` fails the render (L16, fail-closed)" — which was never true, and
  citing `check_*_collisions` as its evidence made it worse, since collision checks are about
  label overlap and have nothing to do with provenance. Making the convention into a gate is
  real work with a wide blast radius (every existing figure lacking sources would start failing),
  so it is recorded as `OG-63`, not quietly asserted here.
- `reader_question`/`insight` tie the figure's *meaning* back to the document's own prose — the
  figure is answering a question the document (or the calculation behind it) already raised.
- `tools/project_index/` ties documents, charts, graphs, and diagrams to each other across an
  entire project — register what a figure or document is *for* (`section`, `tags`, `summary`),
  so a later session can ask "what have we already established about X" and get a real answer
  instead of re-deriving it. See `tools/project_index/README.md`.

Together: prose explains the reasoning, calculations back the numbers, `DataSource` traces the
numbers to their origin, the figure re-presents the same system in a form that surfaces what raw
numbers don't, `reader_question`/`insight` write down what that surfacing revealed, and
`project_index` remembers that any of this happened. None of these layers is optional if the
goal is a real source of truth rather than a good-looking picture.

## Part 2 — precision guarantees, verified against actual code (not asserted from memory)

### What's fail-closed and load-bearing, checked file-by-file this session

Every native figure renderer in docgen (`charts.py`, `visual.py`,
`diagram_graphs.py`, `sequence_diagram.py`, `isometric3d.py`, `geo_map.py`, `sankey.py`,
`layered_workflow.py`, plus the choropleth extension) ships its own `check_*_collisions`
function, confirmed present in every module by direct grep, not assumed from a shared base
class. *(No renderer COUNT is stated here on purpose: it read "11" while the engine had more, and
a number nobody re-derives is decoration — Phase 3's `counts` guard exists for exactly this.)* Concretely, this means:

- **Text never overlaps, never escapes its box.** Every label gets a conservatively
  over-estimated bounding box (`_text_box`, `visual.py` — deliberately over-, not
  under-estimated, so the gate can never let a real overlap slip through); two boxes that
  intersect, or sit closer than the minimum gap, is a BLOCKING finding — the render raises
  rather than shipping a document with garbled text. Verified directly in `charts.py`'s
  `check_bar_collisions` (bounding boxes computed per bar+label, checked pairwise) and mirrored
  in every sibling renderer.
- **Lines don't overlap nodes they don't terminate at.** `visual.py`'s edge router
  (`_route_edge`) explicitly routes around every non-endpoint node's bounding box (orthogonal/
  elbow routing, not straight-line-through-anything) — confirmed in source, not just claimed in
  the module docstring.
- **Anchor points can't drift, structurally.** Every edge/connector/link/message in every
  docgen spec references a node/actor/point by `id`, and the renderer computes the actual
  connection coordinates FROM that referenced object's real position at render time — there is
  no separate, independently-specified "line start/end coordinate" that could fall out of sync
  with where the node actually is. A dangling reference (an edge pointing at an id that doesn't
  exist) is itself a blocking finding, not a silently-misplaced line.
- **Determinism.** Every renderer rounds floats to 2dp and uses stable ordering — the same spec
  renders byte-identical output twice in a row (the same discipline chart-engine's own golden-
  render regression tests lock in). A figure's geometry doesn't shift between builds.

### What "the gate passed" is actually worth — measured 2026-08-19

The gates above are sound on everything they are told to look at, and that qualifier is
load-bearing. A gate cannot enforce what it was never given a box for. Two real instances were
found on 2026-08-19 by rendering a 21-figure document and measuring every text bounding box in a
browser, rather than by re-reading the checkers:

- `visual.py` drew a numbered badge on every `main` edge and never added it to the collision box
  list — so it overlapped its own edge label systematically, 3×3px, invisibly to the gate.
- `isometric3d.py` compared boxes only against each other, never against the canvas, so a scene
  projecting past its own fixed `viewBox` was silently clipped.

Both are fixed and both are now checked. The durable lesson is the method, not the two bugs: **the
way to find the next gap is another rendered-output measurement.** After that fix, the same
document measured 262 text elements across 21 figures with zero overlaps and zero out-of-box text,
in both themes — which is what "the gate passed" is worth on the cases exercised, and no more.

So: trust the gate, and re-measure after changing a renderer. The sweep is cheap — walk every
`<text>`/`<tspan>`, compare bounding boxes pairwise for intersection, and check each against its
`<svg>`'s own box. `examples/capability-gallery.md` exists partly to give that sweep something
comprehensive to run against.

### What relies on a third-party layout algorithm instead (real, not a gap — different tools for different needs)

- **mermaid-engine** delegates layout to `elkjs` (Eclipse Layout Kernel — beautiful-mermaid's
  own real dependency, confirmed via `npm view`), a mature, purpose-built automatic-graph-layout
  library used broadly in the diagramming-tool ecosystem specifically because it already solves
  node placement/edge routing without overlaps for arbitrary graphs. This engine doesn't
  re-validate ELK's output; it inherits its guarantees. `render.mjs` only post-processes the
  output to strip the CDN font import (see `tools/mermaid-engine/README.md`) — it never touches
  the actual layout.
- **chart-engine** (ECharts) has its own gate system (`G-STRUCT`/`G-SEC`/`G-SIZE`/`G-CHART`/
  `G-CONF`/`G-ROUTE`) plus a mature, independently-tested rendering engine — this engine's own
  30 unit tests + 22 acceptance simulations lock in that behavior, but the actual layout math is
  ECharts', not reimplemented here.

### Where NO overlap guarantee exists — disclosed honestly, not glossed over

- **graph-engine's force-directed layout** (the default mode in `graph-view.html`) is a
  physics simulation, not a solved-layout algorithm — it does NOT guarantee zero node overlaps
  or zero edge crossings at every node count, especially on dense graphs. The Tree/Radial
  `dagMode` layouts (wired up this session) are more structurally predictable for genuinely
  hierarchical data, but pick force-directed only when an approximate, exploratory layout is
  what's wanted, not when exact non-overlap matters. This is disclosed here precisely because it
  would be dishonest to claim graph-engine has the same guarantee docgen's own renderers do —
  it doesn't, by the nature of force simulation.

## Part 3 — color and element conventions: real standards vs. this engine's house style vs. your call

### Real, broadly-recognized conventions this engine already follows

- **Bar charts never truncate the value axis (zero baseline).** A universal data-honesty
  convention (a truncated axis exaggerates differences) — enforced as a blocking rule in
  `charts.py`, not a style choice.
- **Pie/donut charts cap at ~6 slices.** A real, widely-cited readability limit (beyond ~6
  wedges, relative-size comparison by eye breaks down) — enforced as a blocking rule.
- **Heatmaps always carry a color-scale legend.** Without one, a heatmap's colors are
  uninterpretable — enforced as a blocking rule, not left optional.
- **Sequential (single-hue, light-to-dark) color scales for one-directional/ordered data**
  (this engine's choropleth 5-bucket `color-mix()` ramp, and the achromatic severity ramps
  elsewhere in `tokens.py`) is a real cartography/data-viz convention (the same family as
  ColorBrewer's "sequential" schemes) — appropriate specifically because the underlying data
  (customer count, severity, coverage percentage) has a genuine low-to-high order. A
  **diverging** scale (two hues meeting at a neutral midpoint) is the correct convention instead
  when data has a meaningful zero/center with real positive AND negative directions (e.g.
  profit/loss, above/below target) — **not implemented in this engine's choropleth today**; if
  you need one, that's a real, disclosed gap, not a hidden limitation.
- **Red/amber/green (or equivalent hue triad) for danger/warning/good** is about as close to a
  universal software convention as exists. This engine's own severity/status vocabulary (`ember`
  = danger, `gold` = warning, `verify` = good, in `tokens.py`) follows that convention in
  spirit — the exact hex values are this engine's own inherited palette (see below), not
  independently standardized, but the hue *role* assignment matches common practice.

### This engine's own house style — a real, deliberate, but NOT industry-mandated convention

- **At most one accent color per figure** (plus its severity sibling where relevant) — B&W/ink
  base, color reserved for the one thing that matters in that specific figure. This is a
  documented design law across every docgen renderer, consistently enforced, but it is this
  engine's own opinionated choice (a legitimate, well-reasoned one — color-as-decoration is a
  real, common data-viz mistake this avoids), not something every graph/document engine in the
  world follows. If a host project's own design system wants a different color philosophy
  (e.g. a categorical multi-hue palette throughout), that's a legitimate override — see below.
- **The actual color hex values currently baked into `tokens.py`** are this engine's inherited
  palette from its original source project (kept deliberately — see `PROVENANCE.md`, "What was
  deliberately not renamed"). They are NOT parameterized through `engine.config.json` today —
  changing them means editing `tokens.py` directly. If a host project wants its own brand
  colors instead of the inherited palette, that is a real, current gap: there is no config-file
  path for it yet, only a code edit.

### Genuinely no universal standard — left to whoever is authoring the figure

- **Network/graph layout algorithm** (force-directed vs. hierarchical-tree vs. radial) has no
  single correct answer — it depends on whether the data has a real hierarchy, how dense it is,
  and what question the reader is asking. graph-engine deliberately exposes all three as a
  runtime toggle (the Layout button) rather than picking one — the agent or reader chooses per
  graph, per moment, based on what they're trying to see.
  Presets are used
  when they exist; when nothing project-specific has been reviewed, the agent is expected to
  pick the closest visual family to the data shape and say so via `explain_selection`
  (chart-engine's own MCP tool for exactly this).
- **Mermaid's 15 built-in themes** — no forced choice; pick to match the surrounding document's
  own theme (see the `--mermaid-bg`/`--mermaid-fg` alias pattern in `tools/docgen/tokens.py` for
  the default "match the host document" behavior) or a fixed theme if the figure needs to look
  the same regardless of reader theme preference.
- **Whether a given dataset is better shown as a table, a chart, or both** — genuinely
  context-dependent; chart-engine's own `knowledge/CHART_ANTI_PATTERNS.json` and
  `CHART_USE_CASE_CATALOG.json` document known-bad choices and typical-good ones respectively,
  but neither is a hard rule the gates enforce — use them as a reviewed starting point, not a
  mandate.

## Summary for an agent about to author a figure

1. Fill in `reader_question` and `insight` for anything meant to be authoritative — see Part 1.
2. Trust the fail-closed collision gates for text/line correctness in every docgen-native
   figure and in chart-engine — you do not need to manually verify pixel positions; if the gate
   passes, the geometry is genuinely correct, not just "probably fine." For mermaid-engine and
   graphify's force-directed mode, see Part 2's honest caveats.
3. Follow the real conventions in Part 3 (zero-baseline bars, ≤6 pie slices, mandatory heatmap
   legends, sequential-vs-diverging color scale choice) — these aren't optional style
   preferences, several are enforced, and the rest are genuine best practice.
4. Where Part 3 says "no universal standard" — make a deliberate choice and, where the tooling
   supports it (chart-engine's `explain_selection`), say why.

---

## A figure explains its own numbers (added 2026-10-10)

Interpretation used to be the *author's* job (`reader_question`, `insight`). It is now also the *document's*: a figure
that puts a number, a colour or a numbered circle in front of a reader must say what it means, in the figure's own block,
without the reader hunting through the prose.

- **Numbered circles** (diagrams): printed under the figure as a key — one line per circle, `Step A → Step B · label ·
  note`, generated by the same function that draws the circle, so the number in the picture and the line in the key cannot
  disagree. Click a circle to jump to its line.
- **Marks** (engine charts): hover or focus for a tooltip; "What each mark shows" lists mark · value · what it tells you
  for charts of up to 30 marks; the AI record lists all of them.
- **Colour** carries meaning only where the meaning is stated: severity and status words use the reserved colours (Critical
  red … Low **blue** … Info green); a diagram's node tone, edge role and dot phase are named in its reading guide. Colour is
  never the only carrier — every mark also has a label or a title.
- **The text points at the picture and back.** `[[fig:ID]]`, the section's chip row and the figure's "↑ section" link
  mean a reader can start from either side.

The collision/precision guarantees above are unchanged; what is new is that the guarantees are now *visible* to the reader
and *readable* by a model (`<stem>.blueprint.json`). Rules: `docs/design/FIGURE_SYSTEM.md`.

