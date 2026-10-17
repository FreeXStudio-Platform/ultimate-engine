<!-- classification: public -->

# Reskinning and theme policy

### appearance may change, semantics may not · 2026-08-08 · v1.0.0

**Authority chain:** Atlas `brand.css` v3.3 → `tools/docgen/assets/tokens.json`
(vendored) → `adapters/echarts/theme-adapter.mjs`'s `buildAllThemes()`, computed
**in memory** at render time. That is the true terminus: `render.mjs`'s
`themes()` calls `buildAllThemes()` fresh and never reads a file back.
`themes/*.json` (GENERATED — never hand-edit; `npm run build:themes` after
re-vendoring) is a tracked **snapshot** of that in-memory output, kept for a
human/host-project reading the palette without running node and for
`tools/docgen`'s build-cache fingerprint — it is not a runtime dependency of
this engine, and hand-editing it changes nothing about what actually renders.
A test (`tests/reskin.test.mjs`) asserts the tracked snapshot matches the
generator so it cannot drift silently. *(Corrected 2026-08-23, P8-082 — this
line previously named `themes/*.json` as the chain's terminus, implying a
downstream consumption that does not exist.)*

- Five approved themes: `project-theme` (dark, native), `project-theme-dark`,
  `project-theme-light`, `print-theme`, `document-theme`. Agents never invent
  colors, fonts, or new themes.
  - `project-theme` and `project-theme-dark` are a **deliberate, byte-identical
    alias pair** (`buildAllThemes()` calls `buildTheme(t, "dark")` for both) —
    `project-theme` is the native/default name, `project-theme-dark` lets a
    caller be explicit about mode without an alias-resolution step. Not drift
    (P8-123).
  - `document-theme` is for a chart **inlined into a docgen document**: its ink
    and hairline values are CSS custom properties (`var(--fg)`, `var(--mute)`,
    `var(--faint)`) rather than literal hex, so the chart follows that
    document's live theme — including the runtime light/dark toggle — instead
    of baking in a palette decided at render time. `visual_get_theme` and
    `visual_render`/`visual_validate_job` accept it identically (P8-065/P8-083
    — `visual_get_theme` used to reject it via a separately hand-maintained
    4-value enum that had fallen behind the other two).
- Categorical palette = the six Atlas hues in docgen's order (shield-hi,
  bronze-hi, gold-hi, verify, ember-hi, shield-dim). Max 6 series — same cap
  as the pie law.
- **Severity lattice is semantic, not decorative**: crit `#C0282A` · high
  `#C4762A` · med `#B89020` · low `#4A7FC1` · info `#3DA875`. Used only where
  severity is the actual meaning (preset `semantics.severity_items`).
- Heat ramp `rgb(15,32,64) → rgb(74,127,193) → rgb(237,184,74)` — identical to
  docgen charts.py.
- Fonts: Inter body, Space Grotesk display, JetBrains Mono numerals — matching
  docgen (the known Atlas display-font fork is docgen's, documented in the
  Phase-0 inventory; this engine follows docgen, the document authority).

**The reskin law (spec §15.6):** a theme/reskin may alter color, typography,
stroke, spacing, background, legend, framing, emphasis. It may NOT alter data,
grouping, series membership, axis scale, units, sort meaning, thresholds,
severity mapping, category identity, edge direction, missing-data meaning, or
uncertainty. Enforced by the semantic checksum: `option_sha256` is computed on
the option AFTER theme application only via ECharts' theme registry (themes
never touch `series[].data`), and the reskin regression test renders the same
job under all five themes and asserts identical decoded data series.

## Reserved colours and readable ink (added 2026-10-10)

- **Severity and status colours are reserved.** `theme.severity` (crit, high, med, med-hi, low, info) and the semantic
  verify / ember / gold inks mean something and are applied by label (`semantic-colors.mjs`): *Critical* is red, *Low* is
  **blue**, *Info* is green, *Unrated* a neutral grey. A reskin may change their values within the Atlas tokens; it may not
  move a meaning to a different colour, and a chart may not hand them out by palette position.
- **Label ink follows the fill, not the theme.** A label drawn on a mark takes near-black or white by WCAG contrast (pure
  black/white in the mid-tone band); labels have no outline. A reskin that changes a fill changes its label ink with it —
  no theme supplies label ink for a coloured tile.
- **Hover never changes hue** in any theme. Reskinning may change the *outline* colour of a hovered mark, not its fill.

