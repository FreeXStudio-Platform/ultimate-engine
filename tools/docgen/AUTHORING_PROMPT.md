<!-- classification: public -->
# The  Document Authoring Prompt
### tools/docgen · 2026-07-04 · v1.0 · paste this into any agent that authors an  doc, diagram, or report

> The single master prompt that makes every generated document come out at the same premium bar:
> black-and-white editorial base, color only as an event, nothing ever overflowing its box,
> every motion guarded, every claim real. Load it verbatim before authoring; the checklists at the
> bottom are the exit gate.

---

## THE PROMPT (copy from here)

You are authoring a document in this system. Follow this contract exactly; it outranks your defaults.

**Sources of truth (read before writing):** `tools/docgen/assets/tokens.json` + `tokens.py` +
`components.py` (the visual law) · `docs/design/doc-system/RULEBOOK.md` (the locked laws) ·
`docs/design/doc-system/TAXONOMY.md` + `DOC_MANIFEST.md` (doc types and their tiers).
Also: `tools/docgen/gallery.md` (what each component looks like) · `tools/docgen/README.md` (build
conventions). Author Markdown; **`python3 -m tools.docgen.cli build FILE.md` supplies the design.**

> **Build with the CLI.** `python3 -m tools.docgen.cli build FILE.md` is the build path, and
> since 2026-08-22 it is the only one: a second, older renderer (`build.py`) with an
> incompatible input convention was deleted, because this prompt is copied verbatim by
> authoring agents and pointing at it taught a convention the canonical build cannot read.
> Recorded as `OG-73`; git history is the archive.

*(Corrected 2026-08-20. This list previously pointed at three documents that belong to the engine's
source project and are **not bundled here** — `docs/design/DOC_DESIGN_SYSTEM.md` (visual law),
`docs/DOC_CLASSIFICATION_AND_INVENTORY.md` (tier law) and `docs/INDEX.md`. Their roles are now
served by the files named above. An authoring prompt is copied verbatim by agents, so a dead pointer
inside it is not a cosmetic defect — it sends every author to a file that does not exist.)*

**1 — Identity block first.** Line 1: YAML front-matter declaring `classification: public|confidential|secret` (the engine's own
tiers — the `PUBLIC|GITHUB|COMMERCIAL|CONFIDENTIAL` vocabulary this line used to teach belongs to
the project this engine was extracted from, and nothing here implements it).
Then `# Title` (one h1). A doc without a valid front-matter header does not build —
`python3 -m tools.docgen.cli check FILE.md` fails it, and that is the command to run. *(The
`### kicker · date · version` line and the `>` lead paragraph belong to `build.py`'s convention, not
to this one; the canonical renderer takes those values from the front matter instead.)*

**2 — The color rule (non-negotiable).** Everything defaults to ink `#0a0a0a` on paper `#ffffff` with the
five greys.  blue exists in exactly three sanctioned places: links/active-TOC (`--accent-hi #4A7FC1`,
the template does this for you), ONE `.note.brand` per page at most for the single thing the reader must
not miss, and ONE accent element per diagram — the focal node OR the money path, never both, never a
label fill on top of an accent stroke. If you are coloring a second thing, you are wrong.

**3 — Nothing escapes its box.** The template hardens containment (overflow-wrap on every text element,
`min-width:0` on grid children, tables/code in their own scroll containers, clamped stat numbers) — do not
fight it: never set `white-space:nowrap` on prose, never fix widths in px on text containers, keep SVG
text ≤ the width its node allows (SVG text cannot wrap — shorten the label or widen the node). Any raw-HTML
component you add must come from the gallery; invented one-off CSS is a defect.

**4 — Type scale is fixed.** h1 clamp(34→62), h2 clamp(24→38), h3 20, h4 = mono uppercase tracked label,
body 16/1.6 at ≤46em, mono voice for kicker/labels/badges/table-headers/captions/TOC. Do not introduce
new sizes; if a element "needs" a new size, you picked the wrong component.

**5 — Motion is rare, purposeful, and guarded.** Allowed: the template's section reveal + TOC scroll-spy
(free), ONE traveling flow-dot or focal pulse per diagram to show direction (CSS keyframes, `.flowdot`
pattern from the gallery), nothing else. Every animation you add must sit behind
`@media (prefers-reduced-motion: reduce){ … animation:none }`. No parallax, no bouncing, no decoration.

**6 — Diagrams are hand-built inline SVG** inside `<figure class="svgwrap">…<figcaption class="figcap">
Fig. N — caption with a legend when shape/fill encodes state</figcaption></figure>`. `viewBox` set,
`role="img"` + a descriptive `aria-label`, nodes hollow-ink by default, terminal nodes filled ink,
edges grey 1.5 with arrowheads, dashed = optional/secondary, hatch pattern = opaque bundle, ≥1 figure
wherever the content has a flow/pipeline/structure.

**7 — Reality only (KB-010).** Every number, count, path, flag, and control must resolve to the real
repo/runtime — cite `file:line` or the command that proves it. If something is planned, say planned.
A beautiful fabricated doc is worse than an ugly honest one.

**8 — Tier hygiene.** GITHUB/COMMERCIAL docs never carry cost math, margins, wallet/infra secrets, or
exploit-enabling detail — that content goes to `docs/confidential/` (git-ignored) and the shared doc
gets a sanitized pointer. When in doubt, treat as CONFIDENTIAL and ask.

**9 — Structure encodes truth.** Numbered sections/medallions are for real sequences and real section
order; `ol.steps` only for genuine procedures (with `in:/out:` on each step); tags for enumerable sets;
tables get an ink header row and mean something per-row. No decorative numbering, no emoji in shipped
docs, no filler sections.

**10 — Exit gate (all must pass before you call it done):**
- `python3 -m tools.docgen.cli check FILE.md` → OK.
- Build it, open it, and scan: at 320 / 768 / 1280 px there is **zero** horizontal page scroll and zero
  element whose content escapes its border (tables/code scrolling inside their own containers is the
  one sanctioned exception). If you can run a browser (Playwright/preview), run the overflow scan;
  if not, keep unbroken tokens out of unwrappable spots (headings, SVG text, badges).
- Reduced-motion pass: emulate `prefers-reduced-motion: reduce` → nothing moves, nothing disappears
  except the flow-dot (which hides by design).
- Color audit: count the accent-colored elements on the page; each one must be individually justifiable.
- Links/anchors resolve; figures numbered in order; TOC matches sections; changelog row appended;
  INDEX row exists (add it if the doc is new).

## Changelog

| date | version | change |
|---|---|---|
| 2026-07-04 | 1.0 | authored (operator directive: wrap-safety + motion + accent discipline + "best prompt") |
