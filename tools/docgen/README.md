<!-- classification: public -->
# tools/docgen — the document build
### docs track · 2026-07-04 · v1.0 · DS-2 deliverable

> Authors write Markdown; this build supplies the premium design. One command turns a compliant `.md`
> into a self-contained HTML document in the design system (`tokens.py` + `components.py` +
> `assets/tokens.json`; the source project's `DOC_DESIGN_SYSTEM.md` is not bundled here)
> — B&W editorial base, mono system voice, one accent, no network references.

## What lives here

| file | role |
|---|---|
| `template.html` | the base skeleton: full design-system CSS + hero/TOC/section/footer slots |
| `AUTHORING_PROMPT.md` | the master prompt any agent loads before authoring a doc/diagram — design law + wrap/motion/accent rules + exit gate |
| `gallery.md` / `demo/gallery.html` | every component exercised once — visual test + author reference |
| `demo/` | committed reference renders (proof the build works on real docs) |
| `trash-sweep.sh` | gated 7-day sweep of `docs/archives/_trash/<date>/` (dry-run by default) |

## Authoring conventions (items 1–3 are enforced by `--check`; 4–7 are the design contract the DS-3 header/audit pass verifies)

1. First lines carry YAML front-matter declaring `classification: public|confidential|secret` (the engine's own
tiers — the `PUBLIC|GITHUB|COMMERCIAL|CONFIDENTIAL` vocabulary this line used to teach belongs to
the project this engine was extracted from, and nothing here implements it).
2. `# Title` — one h1.
3. `### kicker · date · version` directly under the title → hero kicker + badges.
4. A `>` blockquote after that → the hero lead.
5. `## Sections` become numbered medallion sections with TOC entries.
6. Diagrams are raw-HTML figures: `<figure class="svgwrap"><svg role="img" aria-label="…">…</svg><figcaption class="figcap">Fig. N — …</figcaption></figure>` — hand-built inline SVG, one accent max.
7. Components beyond Markdown (steps, tags, cards, stats, brand notes) are raw HTML per `gallery.md`.

## Usage

```bash
python3 -m tools.docgen.cli check docs/SOME_DOC.md   # conventions gate
python3 -m tools.docgen.cli build docs/SOME_DOC.md     # writes HTML beside the source
python3 -m tools.docgen.cli build IN.md -o OUTDIR   # explicit output directory
```

Dependency: `python3 -m pip install markdown` (the only requirement; no pins, no network at build time).

## Design contract

- Output is **self-contained**: CSS inlined from `template.html`, no CDN/fonts/scripts fetched.
- Tables always scroll in their own container; the page never scrolls sideways.
- Scroll-reveal and TOC scroll-spy are guarded by `prefers-reduced-motion`.
- Color rule: everything ink/paper/grey; `--accent-hi` for links/active TOC; at most ONE accent element per diagram.

## Changelog

| date | version | change |
|---|---|---|
| 2026-07-04 | 1.0 | DS-2: template + generator + gallery + demo renders shipped |
| 2026-07-05 | 2.0 | doc-system engine (ENGINE_PLAN.md) supersedes the DS-2 build for new documents — see below |

---

<!-- classification: public -->
## The doc-system ENGINE (v2 — supersedes the DS-2 build above for new documents)

> Governed by `docs/design/doc-system/RULEBOOK.md` (locked L1-L23), `CLASSIFICATION.md` (3 tiers +
> leak-gate), `DESIGN_SYSTEM.md` (Atlas tokens/components). Build plan: `ENGINE_PLAN.md`.

### Modules

| module | role |
|---|---|
| `models.py` | shared dataclasses/enums every module imports from (`DocHeader`, `Tier`, `VisualSpec`, `GateResult`, ...) |
| `tokens.py` | loads `assets/tokens.json` (vendored Atlas tokens) → `build_css()`: dark+light themes, `.t-*` type roles, component CSS |
| `components.py` | HTML partials: `masthead`, `classification_badge`, `section`, `data_table`, `figure`, `callout`, `theme_toggle`, `logo_svg`, `verified_stamp`, `contrast_ratio`/`wcag_aa_ok` |
| `classification.py` | header parse + validate (RULEBOOK L2/L5/L14) |
| `export_sanitizer.py` | the 7-gate leak-gate (RULEBOOK L4/L6/L14; credential/token + bidi/zero-width pattern dialect, formerly jury KB-004, retired 2026-07-25) |
| `visual.py` | `VisualSpec` → SVG renderer: glyphs, edge routing, motion (the "dot"), collision validator |
| `doc_manifest.py` | `DOC_MANIFEST.md` table reader |
| `fetch_public_fact.py` | SSRF-hardened public-fact fetcher: pinned-IP connect, manual redirect re-validation, RFC-1918/loopback/link-local/metadata blocking (formerly jury KB-005, retired 2026-07-25) |
| `generator.py` | `build(md_path, formats=...)` — MD → self-contained HTML/JSON(/PDF), gate re-run on final rendered bytes before write |
| `cli.py` | `python -m tools.docgen.cli {build,render,manifest,check}` |

### Usage (v2 engine)

```bash
# Build the sample doc to self-contained HTML (gate runs on the rendered output before write)
.venv/bin/python -m tools.docgen.cli build tools/docgen/sample.md --formats html

# Render a standalone VisualSpec to SVG
.venv/bin/python -m tools.docgen.cli render tools/docgen/sample_spec.json -o /tmp/sample.svg

# List DOC_MANIFEST.md rows
.venv/bin/python -m tools.docgen.cli manifest

# Best-effort structural check (header + manifest-drift; full hash-gate once validate_doc_system.py lands)
.venv/bin/python -m tools.docgen.cli check tools/docgen/sample.md
```

Every document begins with the YAML front-matter header (`CLASSIFICATION.md`): `id`,
`classification` (`public|confidential|secret`), `title`, `audience`, `owner`, `status`,
`export_allowed`, `surface`, `last_reviewed`. Only `classification: public` may set
`export_allowed: true` — the gate blocks any mismatch, missing field, or leaked secret/PII/
detector-internal before a byte is written. See `sample.md` for a minimal worked example.

Dependency-free at the core (stdlib + PyYAML for header parsing); PDF output degrades
gracefully to `pdf: skipped(weasyprint absent)` when `weasyprint` is not installed — HTML is
the canonical, always-available output.

Tests: `.venv/bin/python -m pytest tests/docgen/ -q`.

### Figures: numbered, scoped, linked (2026-10-10)

`generator._render_markdown_body` numbers figures in placement order, anchors them (`fig-<slug>`), makes `##` sections
link targets (`sec-<slug>`) with a chip row, resolves `[[fig:ID]]` in prose, and prints a reading guide / key / mark table
under every figure. Every id inside every embedded figure is scoped to it (`figure_support.scope_svg_ids`), and one
inline runtime (`assets/figure_runtime.js`) adds tooltips, click-to-pin and adjacency highlighting. Output formats are
`html`, `json`, `blueprint` (`<stem>.blueprint.json`, the machine twin of the render) and `pdf`. Design:
`docs/design/FIGURE_SYSTEM.md`. A new figure KIND is still one row in `generator._FIGURE_KINDS`; give it a `guide` (its
plain-language reading) and, if it has numbered parts, a `present` hook that returns the key.

