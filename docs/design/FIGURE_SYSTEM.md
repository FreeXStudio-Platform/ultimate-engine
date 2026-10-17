<!-- title: FIGURE SYSTEM -->
# Figure system — how a figure is scoped, explained, linked and read by a machine

**Status:** DESIGN — normative. This is the single source of truth for what a figure *is* once it leaves a
renderer: its attribute contract, its hover law, its ids, its numbering, the links that join it to the text around
it, and the two JSON files a machine reads instead of the picture. Written 2026-10-10 from a measured defect pass on a
document that inlined 28 engine charts and 19 diagrams into one page (`OG-250` … `OG-261` in
`docs/process/OPEN_GATES.md`).

**Why this file exists.** Every figure used to be correct *alone* and wrong *together*. A chart rendered fine in its own
file; inlined beside twenty-seven others it shared their CSS class names, their `<clipPath>` ids and their hover rules,
and nothing in the picture said what a dot was. The fixes are small; the reason they needed a design is that the
defects were all one shape — *a thing written as if local, shipped as if global* — and a fix per symptom would have left
the shape in place (`docs/process/RULES.md` Rule 1).

> **No counts are restated here** (`docs/process/RULES.md` Rule 2). Where a number matters, the sentence names the
> code that owns it.

---

## 1. The defect classes this design closes

| Class | What it looked like on the page | The one fix |
|---|---|---|
| **Global CSS from a local file** | Hover turned green marks black, blue marks nothing, orange marks flashing; a lens-shaped fill appeared between two points of an open curve | A figure ships ONE `<style>` and every selector in it starts with `svg[data-fig="<scope>"]` (§3) |
| **Global ids from a local file** | A sankey painted with the heat map's gradient; Mermaid arrowheads shared across diagrams | Every id a figure declares, and every reference to it, is prefixed with the figure's scope (§3) |
| **Hover that recolours** | `var(--fg)` cannot be lightened, so the "lighter" hover colour came out black or white | A hover state may change brightness, outline, thickness and opacity — never hue (§4) |
| **A mark that says nothing** | A dot, a tile, a numbered circle — with no title, no tooltip, no neighbours, no explanation of the number | Every mark carries meaning in the SVG itself, and every figure prints what its numbers mean (§2, §8) |
| **Ink chosen without the fill** | White labels on tan tiles; a thick halo round every letter | Label ink is chosen from the fill by contrast ratio; there are no halos (§6) |
| **Colour chosen without the word** | "Critical" drawn blue because blue is slot 0 of the palette | Severity and status words keep their reserved colours (§6) |
| **Text and picture that do not know each other** | A heading with no way to its graph; a graph with no way back; numbers in circles with no key | Numbered figures, linkable sections, `[[fig:ID]]`, a reading key per figure (§7) |
| **A document only a person can read** | An AI had to scrape geometry to learn what a chart said | `<stem>.blueprint.json` and `<id>.figure.json` (§9) |

---

## 2. The attribute contract

Every figure — an engine chart or a native diagram — is an inline `<svg>` that carries the same machine-readable
attributes. The runtime (§5), the CSS (§4) and the JSON (§9) are all derived from these, and nothing else is.

| Element | Attribute | Meaning |
|---|---|---|
| root `<svg>` | `data-fig` | The figure's scope: `ve-<visual_id>` for an engine chart, `fig-<slug>` for a native diagram |
| | `data-fig-kind` | The family (`graph`, `heatmap`, `flowchart`, `sequence`, …) |
| | `data-fig-focus` | Which marks stay lit while one is hovered: `item` · `series` · `index` · `adjacency` |
| | `data-fig-legend` | What a legend item isolates: `none` · `series` · `item` |
| a mark | `data-s` / `data-i` | Series index / data index (engine charts) |
| | `data-k` | Mark kind: `node` · `edge` · `badge` · `main` · `series` … |
| | `data-id` | Stable id of the mark **within its figure** (`s0.3`, `n2`, `e1`, `b1`) |
| | `data-nb` / `data-eg` / `data-en` | A node's neighbour ids / incident edge ids; an edge's two end ids |
| | `data-be` | On a numbered circle: the edge it numbers (so it lights with that edge) |
| | `<title>` child | The mark's meaning in plain language: native tooltip, screen-reader name, no-JavaScript fallback |

`data-id` values are **never** prefixed with the scope: they are names inside one figure, and the `data-nb` / `data-eg`
lists that reference them must keep matching. Scoping rewrites `id="…"` declarations only
(`docs/design/FIGURE_SYSTEM.md` §3; the regression is `test_scoping_never_rewrites_data_id…`).

Where it is produced: `tools/visual-engine/adapters/echarts/figure-model.mjs` (what each mark *means*, read from the live
ECharts model) and `figure-layer.mjs` (writes the attributes and the scoped CSS) for charts;
`tools/docgen/visual.py` and `sequence_diagram.py` for native diagrams.

---

## 3. Ids and scope

* An engine chart's scope is `ve-<visual_id>`; a native diagram's is `fig-<slug>` (`figure_support.fig_dom_id`).
* **In the SVG:** every `id="…"` the figure declares, and every `url(#…)`, `href="#…"` and `#id` selector that refers to
  it, is prefixed `"<scope>-"`. Idempotent: an id that already starts with the scope is left alone.
* **In the document:** `components.figure` applies the same scoping to *every* figure it embeds (including Mermaid and
  the native chart kinds), so two figures can never share a declaration whatever produced them.
* **In the CSS:** one `<style data-ve="<scope>">` per engine figure, and the native diagrams' hover CSS
  (`figure_support.native_figure_css`); every selector starts with `svg[data-fig="<scope>"]`. ECharts' own `<style>` and
  its renumbered `.zr-cls-N` classes are removed entirely: the engine owns no part of the hover design any more.

`test_scoping_ids_stops_one_figure_borrowing_anothers_gradient` and `tests/figure-layer.test.mjs` pin all three.

---

## 4. The hover law

> A hover or focus state **may** change brightness, outline, stroke thickness and opacity. It **may never** change a
> mark's hue, fill an open path, move a mark, or take the pointer away from it.
>
> **One declared exception (`OG-280`).** In a **graph**, while a node is focused, the lines that leave it, enter it or run both
> ways take the figure's direction palette (`--ve-out` blue, `--ve-in` pink, `--ve-both` white; darker values in the light
> theme). Here the hue IS the information: which modules a module calls and which call it. The exception is narrow by
> construction: only a graph's edges and arrowheads, only the three `var(--ve-…)` declarations, and the palette is no module's
> status colour (a test compares it with the theme palette) and clears 3:1 against both pages. The **module explorer** (§13) draws
> its hover arrows in the same two hues and is the second place the law is bent, for the same reason.

Consequences, each enforced by a test (`tests/figure-layer.test.mjs`, `tools/tests/test_figure_system.py`):

1. Hover rules contain no `fill` / `background` / `color` declaration — the single exception is a faint **neutral** wash
   over a legend item's own invisible hit area.
2. An open path (`fill="none"`: a line, a curve, a tree edge) keeps `fill:none` on hover; this is what removed the
   lens-shaped fill.
3. Text never intercepts the pointer (`pointer-events:none` on `text` / `tspan`); moving across a tile used to alternate
   between the shape and its label, which flickered.
4. Nothing under `:hover` sets `pointer-events:none` or a `transform`. An edge's wide transparent twin (`.edge-hit`) keeps
   its width while its edge is lit.
5. Outlines use `vector-effect:non-scaling-stroke`, so a thin ring on a scaled symbol stays thin.
6. Arrowheads use `markerUnits="userSpaceOnUse"` so lighting an edge does not grow its head.
7. A filled mark that draws a stroke in a colour of its own (`data-sk="own"`: a line symbol's ring, a box-plot outline, a bubble's
   rim) keeps that colour on hover and pin — it thickens (2.6 px) and brightens. Only a mark WITHOUT one (a bar, a slice, a tile)
   gets the ink outline. Repainting the ring made a hovered blue point turn black (`OG-269`, found by hovering a point in a built
   report, not by any byte-level test).

**Focus modes** (`data-fig-focus`): `item` lights one mark; `series` every mark of its series (a line chart);
`index` every mark sharing its data index within one ECharts series (a radar's polygon and its points);
`adjacency` the mark, its neighbours and the edges between them (graph, tree, sankey, every native diagram).

**No-script fallback.** For figures of up to 160 marks the same highlighting is generated as CSS with `:has()`, guarded by
`:not([data-ve-js])`. Larger figures drop the fallback and rely on the runtime. The runtime sets `data-ve-js`, so the two
never run together.

---

## 5. The runtime

`tools/docgen/assets/figure_runtime.js` — one copy per document, inlined by `generator._render_html` **only** when a
figure is present, no dependencies, no network, no `eval`. It reads the attributes above and writes two classes
(`ve-on`, `ve-pin`) and a tooltip's `textContent`; it never builds markup from data.

| Behaviour | Detail |
|---|---|
| Tooltip | A styled tooltip on hover or keyboard focus; the native `<title>` is withdrawn from marks it serves, so there is one tooltip, not two |
| Pin | Click pins a mark's details; `Esc` or a click elsewhere releases; a pinned tooltip survives the pointer leaving |
| Nearest-mark assist | A pointer within 14 px of a small dot (≤ 28 px) answers as that dot, up to a few hundred marks |
| Keyboard | Figures of at most 80 marks get tab stops; `Enter` pins |
| Adjacency / legend | Same result as the CSS fallback, for any size; a lit edge lights its numbered circle |
| Scroll | A transient tooltip hides on scroll |
| Direction (graphs) | Focusing a node classes each lit line `ve-out` (it leaves the node), `ve-in` (it enters) or `ve-both` (the reverse line exists too); the figure's own stylesheet paints them. The CSS-only fallback carries the same rules per node |
| Reference cards | Every number that points somewhere (`Fig. N`, the number before a heading, a back-link, a section chip) carries `data-ref`. Hover or focus it and a card says what it is and which documents it draws on, read from the page's JSON index (`#ve-doc-index`, §7). The link still navigates; the pointer can travel into the card; `Esc` closes it |

The runtime is exercised against a real built document in headless Chromium
(`tools/tests/browser/figure_runtime_check.mjs`, wrapped by `tools/tests/test_figure_runtime_browser.py`). It **skips,
naming the cause,** when node, the chart engine's dependencies, Playwright or a Chromium build are absent; a skip is
not a pass. Set `PLAYWRIGHT_MODULE_DIR` to a directory whose `package.json` resolves `playwright` to run it.

---

## 6. Ink and colour

* **Readable ink.** A label drawn on a fill takes the near-black or white that contrasts better with it; in the mid-tone
  band, where neither reaches WCAG AA, it steps to pure black or white (whose worst case is above 4.5:1). One rule in two
  languages — `contrast.mjs::inkFor` and `figure_support.ink_for` — held identical by a parity test. A fill that is not a
  literal colour (`var(--x)`, a gradient) cannot be measured and keeps the theme ink.
* **No halos.** Labels carry `textBorderWidth: 0`. A treemap/sunburst/heat-map label sits on its fill, not inside an
  outline.
* **Semantic colours** (`semantic-colors.mjs`). When at least two labels of a chart are severity or status words and they
  are at least half of the chart's labels, those labels take the reserved severity / status colours from the theme —
  Critical red, High bronze, Medium gold, **Low blue**, Info green, Unrated a neutral grey; proven / failed /
  cannot-verify likewise. Every other label keeps the categorical palette. `job.semantic_colors: false` opts out.
* **Series colours are distinct** (a radar's two polygons are two colours with a faded web behind them); a legend swatch
  is painted with the colour its series is drawn in (a native radar legend whose `key` was a series name used to paint
  `fill="files"`, which a browser renders black).

---

## 7. Numbered, linked, explained

`generator._render_markdown_body` owns the document layer.

* **Numbering.** Figures are numbered `Fig. 1 … N` in the order they are *placed*. A hand-written `Fig. 9 -` prefix in a
  caption is stripped, in the HTML, the in-SVG caption and the blueprint, so a picture never carries two contradicting
  numbers. A figure placed twice is refused (it would print one DOM id twice).
* **Anchors.** A figure is `id="fig-<slug>"`; a `##` section is `id="sec-<slug>"` (ties broken in document order); a line
  of a figure's reading key is `id="fig-<slug>-k<n>"`.
* **Both directions.** A section prints a chip row, one per figure it holds. A figure's caption links back to its
  section. A numbered circle inside the picture links to its line of the key. `[[fig:ID]]` in prose becomes a link
  "Fig. N"; a reference to a figure the document does not place is **refused**, not printed as dead text. Outside a
  document render (`_render_inline` called directly) the marker is left alone.
* **Every figure explains its numbers.** Under each figure, an open "What the numbers mean" block holds the kind's
  plain-language reading guide and — for a diagram with numbered circles — one line per circle (`reading_key`, the *same*
  function the renderer uses to draw the circle, so the picture and the key cannot disagree). An engine chart with at most
  30 primary marks also gets a "What each mark shows" table (mark · value · what it tells you); above that, the blueprint
  JSON carries the full list.
* **Numbers that explain themselves (`OG-283`).** A number in a document is a reference, and a bare number is a riddle: the report
  printed `↑ 8` after every figure of its eighth section and nothing said what section 8 was. `doc_index.build` collects, from
  what the render already learned, one small JSON index (`#ve-doc-index`: per section its number, title, first sentence, figures
  and the documents it draws on; per figure its number, kind, title, section, the question it answers and its sources). The page
  embeds it; the runtime shows a card for any `data-ref`. A section's documents are the data sources of its figures plus the file
  paths its text names in code spans; each card row says which. A leading ordinal is kept whole (`8. Modules` is `↑ 8 · Modules`:
  the first `". "` used to be read as the end of a sentence). A document with no figures gets no index and is byte-identical.
* **Size.** See §12: a figure's size is decided by the standard, not by the width of the column. The text keeps its 68-character
  measure; a figure sits in a full-width framed canvas, centred, and node-and-edge diagrams sit on the faint blueprint grid.

### Authoring fields (all optional; defaults are derived)

| Where | Field | Values / default |
|---|---|---|
| diagram node | `tone` | `blue` `gold` `green` `red` `bronze` `steel` `none`; default by node type (sources blue, decisions gold, gates green, stores bronze) |
| diagram edge | `role` | `flow` `return` `async` `error` `link`; default `flow` if `main`, `async` if dashed, else `link` |
| | `phase` | `raw` `processed` `verified` `flagged`; default by position on the main path (first raw, last verified), so the travelling dot visibly changes colour as the data is worked on |
| | `note` | One plain sentence for the key and the tooltip |
| sequence message | `kind` | `call` `return` `async` `error`; default by direction and style (dashed = async, right-to-left solid = return) |
| | `note` | As above |
| prose | `[[fig:ID]]` | Link to the figure with that sidecar id |

---

## 8. Native diagram geometry

* **Numbered circles** have radius 12, are placed by a deterministic candidate search (`visual._badge_positions`) that
  the collision gate *shares* — the gate and the renderer cannot disagree about where a circle is — and keep the engine's
  minimum gap from every node, label and other circle. A circle that had to move off its edge keeps a hairline leader.
* **Sequence diagrams** reserve 24 px under a title so the heading never sits on the first row of participants. A spec
  whose `height` clears the requirement without the reserve is drawn at the requirement with it (at most 24 px taller);
  one short of the OLD requirement is still refused. A rendering improvement must not turn a document that built into one
  that does not (`OG-267`).
* **Arrowheads** are 14 user units and do not scale with stroke width.
* **A highlighted node** is filled with the navy shield, so its label takes the light ink (`node-label-hl`, 4.5:1 or better on the
  fill); every other node keeps the page ink. Dark text on navy was unreadable (`OG-270`).
* **A lifeline is cut behind a message label that crosses it**, so a label centred on a participant is not struck through by the
  dashed line (`OG-271`). No plate and no halo: the line simply is not drawn where the text is.
* **A figure's own legend is printed once.** When the SVG draws its key, the caption block does not add a second text copy; and the
  mark table drops its `Value` column when no mark carries a number (a tree's marks are paths) (`OG-272`).
* **A spec token is never free text in markup.** A node's `tone` is printed into a `class` attribute, so it is one of the six colour
  families, `none` or empty — anything else is refused when the spec is read and again at the glyph (`OG-273`; the other class
  tokens, edge role and dot phase, already fell back through a closed set). A per-cell ink is a `style` declaration as well as an
  attribute, because a stylesheet rule outranks an attribute (`OG-275`, seen in a browser: every heatmap value was the page ink).
  Two figures whose ids normalise to one DOM id are refused rather than sharing an anchor (`OG-276`). A boxplot row is read as its
  last five numbers, whichever shape the chart library returns (`OG-274`).

---

## 9. What a machine reads

| File | Written by | Schema | Contents |
|---|---|---|---|
| `<visual_id>.figure.json` | `node adapters/echarts/cli.mjs … --formats json` (also `visual_render` with `formats: ["json"]`) | `ultimate-engine/figure/1` | id, kind, title, reader question, summary, how-to-read, series, legend, **every mark** (id, kind, label, value, neighbours, a plain-language description) and provenance (engine, theme, `svg.sha256`, `job.sha256`) |
| `<stem>.blueprint.json` | `docgen build … --formats html,blueprint` | `ultimate-engine/blueprint/1` | the document header; every section with its Markdown source; every figure numbered with caption, reader question, insight, how-to-read, reading key, data sources and — for an engine chart — the whole figure record; every `[[fig:]]` reference; and the `links` graph (`contains` / `described-by` / `references`) |

Both are generated from the **same render pass** as the HTML, so they cannot describe a different document. The blueprint
passes the same leak-gate as every other output before it is written. Two hashes sit under a bare `sha256` key
(`svg.sha256`, `job.sha256`) on purpose: the gate's high-entropy fallback waives a 64-hex run only when the word `sha256`
stands alone beside it, and `svg_sha256` does not.

The blueprint is *not* the module map (`blueprint/` at the repository root, `python3 -m tools.blueprint`); it is the
per-document twin of a rendered document.

---

## 10. Verification and re-baselining

| Layer | Where | What it proves |
|---|---|---|
| Contract (bytes) | `tools/visual-engine/tests/figure-layer.test.mjs` | scope, selector scoping, hover law, id uniqueness across figures, meaning on every mark, the AI record matches the SVG, determinism, no halos, contrast, semantic colours |
| Document layer | `tools/tests/test_figure_system.py` | id scoping incl. the `data-id` regression, native CSS law, key ↔ circles, badge gaps, sequence kinds, numbering, chips, back-links, `[[fig:]]`, refusals, blueprint twin, ink parity JS ↔ Python |
| Behaviour (browser) | `tools/tests/browser/figure_runtime_check.mjs` | hover/flicker/adjacency/tooltip/pin/Esc/keyboard/nearest-mark/navigation in real Chromium |
| Size (bytes + browser) | `tools/tests/test_figure_size_standard.py`, `tools/tests/browser/figure_size_check.mjs` | the arithmetic the document hands the stylesheet, the stylesheet's text, and what Chromium draws at five viewports against the standard re-derived from its constants |
| Refinements | `tools/visual-engine/tests/refinements.test.mjs` | where a graph's names go, ring proportions, source colours, direction lists, isolated nodes, the direction palette, treemap label fitting on the live layout, the radar web, boxplot candles |
| Index and cards | `tools/tests/test_doc_index.py` | the pure functions, and that no `data-ref` in a built page dangles |
| Goldens | `tools/visual-engine/renders/golden/`, `renders/diffs/` | any change to a render is classified in `renders/diffs/` *before* `npm run simulate` re-baselines |

Re-baselining order (unchanged, and still unenforced by tooling): `npm test` red → write the drift record →
`npm run build:themes` → regenerate the MCP snapshot → `npm run simulate`. Running `simulate` first erases the signal.

---

## 11. Deliberately not done

Recorded as `OG-262` (`NOT_A_DEFECT`, with reasoning) rather than left implicit:

* The **native chart kinds** (bar, pie, radar, heat map, timeline, sankey, geo map, isometric, layered workflow) keep a
  static look: they have no hover state to get wrong, their numbers are printed, and each kind has a reading guide. Giving
  them the full per-mark contract is a feature, not a repair, and is the first item of `docs/plan/START_NEXT_SESSION.md`.
* The layered-workflow renderer draws a connector straight across intervening layers when the spec asks for one; routing
  around boxes is a layout feature.
* ~~A native flow edge's label sits 18 px from the line, so a long label beside a VERTICAL edge can touch it~~ — **closed by `OG-284`
  without the collision-aware placement this note said it needed**: the label is drawn after the edges and a stroke in the page's own
  ground (`paint-order: stroke`) cuts the line away behind the word. Nothing is moved, so the fail-closed collision gate sees the same
  geometry as before (the mistake `OG-267` warned about was moving labels; cutting the line moves nothing).

---

## 12. Size

Measured on the 2026-10-10 report (`OG-277`). A native diagram is a bare `viewBox`: it has no size of its own, so the page
stretched it to the width of the column. 960 x 740 was shown at 1150 x 886 (x1.2), taller than a laptop screen and so big
that the reviewer had to zoom the browser out to photograph it; the build before drew the same picture at x0.61, where its
12 px labels were 7 px. Nobody had decided a size. **The standard decides it, once, for every figure**, from constants in
`figure_support.py` that the stylesheet (`tokens.py`) and the browser check read:

| Rule | Statement | Constant |
|---|---|---|
| FS-1 | A figure is never larger than its design size times its enlargement ceiling: **1** for an engine chart, a Mermaid diagram or any tall figure; **1.3** for a landscape diagram drawn on an abstract canvas (a native flow, state or sequence diagram) | `FIG_UP_SCALED` |
| FS-2 | A landscape figure fits one screen: its height is at most `min(82vh, 700px)`, so figure and caption fit a laptop without zooming out. The width shrinks to keep the aspect ratio; nothing is letterboxed | `FIG_FIT_VH`, `FIG_FIT_H_PX` |
| FS-3 | ... but never below 80% of the design size, so a 12 px label stays above 9 px; the page scrolls rather than the text shrinking past reading | `FIG_MIN_SCALE` |
| FS-4 | A tall or square figure (height at least 90% of width) is read by scrolling and is exempt from FS-2 (and is never enlarged) | `FIG_TALL_RATIO` |
| FS-5 | No figure is wider than 1150 px, whatever the monitor; on a phone the column is the limit | `FIG_MAX_W_PX` |

The width is the smallest of the column, FS-5, FS-1 and the FS-2 width (floored by FS-3). The document hands the stylesheet each
picture's design size (`--fw` x `--fh` from its root `viewBox`) and ceiling (`--up`) on the framed canvas
(`components.svgwrap_open`); a picture it cannot measure keeps the plain "fit the column" rule and is given no invented numbers.
Results at a 1440 x 900 viewport: a 960 x 740 flow is 908 x 700 (x0.95); a 900 x 540 sequence is 1150 x 690 (x1.28, unchanged);
every 620-px engine chart is 620 px wide, unchanged.

**The look that rides with it.** Node-and-edge diagrams (`GRID_KINDS`: flow, state, system map, dependency graph) sit on the faint
blueprint grid again, but as ground, not as data: 22 px cells in 6% of the page ink (`--grid-line`), where the old grid used the
border colour and was loud. Charts, sequence diagrams and foreign engines do not (the grid showed through every plot area, and a
sequence has no free layout). A native diagram's step numbers are 34 px across with a 17 px digit; its title paints with the
page ink (it was an SVG `<text>` with no fill: black on a dark page); an edge label is cut out of the line it sits beside (a
ground-coloured stroke painted under the glyphs).

---

## 13. The module explorer (kind `explorer`)

Raised by the operator reading the report's module section (2026-10-10, item 10): fourteen modules, thirty-one packages and
three hundred submodules were three static pictures, and a reader who wanted to know what lives inside one module, what it
calls and which document describes it had to hold the whole thing in their head. What was asked for: start zoomed out; click a
section and zoom into it, animated, to see its submodules; zoom out; go into another; click to see what a part connects to and
the documents about it, readable in place.

**What it is.** A figure kind that is a *block*, not a picture: it has no design size, so it takes the column (the framed canvas
is `svgwrap--block`, with no padding and no frame of its own, and the explorer carries its own border). It is numbered, anchored
and indexed like any figure, and it is built from one spec (`tools/docgen/explorer.py`; the structure is `ExplorerSpec`).

| Part of the spec | Meaning |
|---|---|
| `root` | A tree of parts: `id`, `name`, `kicker`, `summary`, `status`, `value` (leaves only; a parent is the sum of its children), `facts`, `lists`, `docs`, `refs`, `children`. At most 700 parts, depth 5, 60 children per part |
| `statuses`, `kinds` | The colour legend (a closed tone vocabulary: blue, gold, green, red, bronze, steel) and the kinds of connection |
| `edges` | `src` -> `dst` with a weight and a kind, between ANY two parts, at any depth; at most 3000. Exact, never rolled up: an edge between two packages is listed on those two packages, not on their modules |
| `documents` | The dossiers a part can open: structured blocks (`h`, `p`, `ul`, `kv`, `table`, `code`), every string escaped; there is no markdown and no inline HTML, so a document cannot inject markup |

**Layout** is a squarified treemap per parent, computed once in Python on a normalised 1000 x 620 stage and mapped into the
parent's rectangle (5 units of inset, 2.5 of gap): area is value, a part with no value still gets 1.2% of its parent so it can be
clicked, and a system of parts with no values at all is laid out evenly. The camera is the SVG `viewBox`; a zoom is an animation of
it, so the layout is the same at every zoom and a parent's children are exactly the picture a reader sees one level in.

**The runtime** (`assets/explorer_runtime.js`, inlined once, only when the document holds an explorer): a click glides the camera
to the part (560 ms, ease in-out, width and height change by one ratio so the target grows rather than slides); a name in the
panel or the trail that lives in another branch zooms out to the common ancestor and in again (two 380 ms halves). Labels are an
HTML overlay laid on the settled stage, not SVG text: they wrap at spaces, centre, clamp at three lines and never break inside a
word, and they are not distorted by the camera's non-uniform scaling. Hovering or focusing a part draws its connections to its
siblings as arrows (blue: it calls, pink: it is called by); the panel lists the same connections as buttons and the dossiers it can
open in a reader laid over the map. Tab reaches the map, arrows move between parts, Enter opens one, Escape closes the reader and
then goes up, Backspace goes up, Home returns to the whole system; every move is announced in a status line. `prefers-reduced-motion`
turns every glide into a cut. The state is exposed for a test (`window.__veExplorers[id].state()` and `data-settled`).

**Hover law.** A tile changes outline, thickness and brightness only. The explorer's arrow colours (blue and pink, the same two as
the graph kind's direction palette, a different pair of values per theme) are the **second declared exception** to the law of §4,
for the same reason as the first: the hue is the information.

**The arrow words** (`OG-297`) belong to the spec, not the engine: an optional `arrows` object (`out`, `in`, `out_detail`, `in_detail`, each short text, unknown keys refused)
sets the legend labels and the sentence in the reading guide, so a map of documents says "cites / cited by" and a map of packages "imports / imported by". Without it the wording is
the original code wording, byte for byte.

**Without script and in print** the explorer is a nested `<details>` outline carrying every name, size, status, summary, fact, list,
connection and document (a test compares it with the spec), so a reader without script, a printer and a machine lose nothing. The
document's blueprint JSON carries the whole hierarchy.

**Verified in a real browser** (`tools/tests/browser/explorer_check.mjs`, 53 checks in Chromium): the start state, labels centred on
their own tiles and never broken, hover arrows and their colours in both themes, the glide (strictly between the two frames
mid-way), the panel, the trail, a cross-branch jump through a connection button, Zoom out, Whole system, Escape, the reader (no
duplicate id), keyboard, reduced motion, label contrast at least 4.5:1 on every tone in both themes, a resize, a 390 px screen
(no sideways scroll, panel under the map), print, and no script.

**Found while building it** (`OG-286`): `.svgwrap svg { height: auto }` out-ranks a class, so the world SVG's own box changed
shape with the camera's `viewBox` and every tile was drawn at the wrong height after the first zoom; labels and tiles disagreed by
200 px. The two layers now have a selector that out-ranks it, and the browser check compares every label with its tile.

**Deliberately not done.** The view is not in the URL (no deep link to a zoom level); no search box; no wheel or pinch zoom (a click, a
button or a key); not run in Firefox or Safari, nor with a screen reader; a part's connections are drawn only to its siblings (the
panel lists the rest).
