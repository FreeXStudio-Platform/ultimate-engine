---
id: REF-401
classification: public
title: Docgen Component Gallery
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-08-22
---

# Docgen Component Gallery

Every component the document design system ships, exercised once — this page is both the visual
test of the rendered stylesheet and the author's reference for what Markdown turns into. Build it
with `python3 -m tools.docgen.cli build tools/docgen/gallery.md`.

## Typography and prose

Body text is the humanist sans at 16px/1.6, capped near a 46em measure. Inline `code` gets the mono
voice with a soft chip. Links look like [this internal reference](../../docs/CHARTER.md). **Bold** carries
weight-700; headings track tight.

### An h3 subsection

h3 is a prose subheading. The h4 below is the mono "system voice" label:

#### System-voice label (h4)

Ordinary paragraphs continue underneath.

## Tables (ink header + zebra)

| detector | chain | severity | status |
|---|---|---|---|
| `reentrancy_basic` | universal | critical | shipped |
| `anchor_signer_check` | solana | high | beta |
| `cairo_felt_overflow` | starknet | medium | shipped |
| `vyper_default_visibility` | universal | high | calibrating |

Wide tables scroll inside their own container — the page never scrolls sideways.

## Notes and callouts

> A plain blockquote in body Markdown renders as the standard ink note. Use it for constraints,
> warnings, and "read this first" context.

<div class="note brand"><span class="lab">Brand-critical note</span>
The <code>.brand</code> variant carries the one accent this page is allowed. Reserve it for
the single thing the reader must not miss.</div>

## Steps (procedures with in/out lines)

<ol class="steps">
<li><strong>Author the Markdown</strong> with YAML front matter, an h1, and prose.
<span class="io">in: conventions · out: a compliant .md source</span></li>
<li><strong>Build</strong> with <code>python3 -m tools.docgen.cli build FILE.md</code>.
<span class="io">in: .md · out: self-contained .html in the output directory</span></li>
<li><strong>Verify</strong> with <code>cli check</code> in the docs session gate before shipping.
<span class="io">in: .md · out: OK / FAIL with reasons</span></li>
</ol>

## Tags, cards and stats

<span class="tag">reentrancy</span><span class="tag">access_control</span><span class="tag">defi</span><span class="tag">l2</span><span class="tag">cairo</span>

<div class="row c2">
<div class="card"><h4>Hard card</h4><p>1.5px ink border — primary grouping.</p></div>
<div class="card soft"><h4>Soft card</h4><p>1px grey border — secondary grouping.</p></div>
</div>

<div class="statgrid">
<div class="stat acc"><div class="n">514</div><div class="l">detectors</div></div>
<div class="stat"><div class="n">99.2%</div><div class="l">bank recall</div></div>
<div class="stat soft"><div class="n">9,706</div><div class="l">tests green</div></div>
</div>

## Figures (hand-built inline SVG)

<figure class="svgwrap"><style>
@keyframes docgen-flow{0%{transform:translateX(0);opacity:0}12%{opacity:1}88%{opacity:1}100%{transform:translateX(384px);opacity:0}}
.flowdot{animation:docgen-flow 3.2s linear infinite}
@media (prefers-reduced-motion:reduce){.flowdot{animation:none;opacity:0}}
</style><svg viewBox="0 0 640 150" role="img" aria-label="Three-node pipeline: markdown source flows through the docgen build into a self-contained HTML document; the build step is the highlighted focal node; a single dot travels the pipeline to show direction.">
<defs><marker id="ga" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#5e5e5e"/></marker></defs>
<circle class="flowdot" cx="120" cy="75" r="4" fill="#0a0a0a"/>
<rect x="20" y="45" width="160" height="60" rx="8" fill="#fff" stroke="#0a0a0a" stroke-width="2"/>
<text x="100" y="72" text-anchor="middle" font-family="ui-monospace,Menlo,monospace" font-size="12" font-weight="700">source.md</text>
<text x="100" y="90" text-anchor="middle" fill="#5e5e5e" font-family="ui-monospace,Menlo,monospace" font-size="9.5">conventions + tables + raw HTML</text>
<line x1="180" y1="75" x2="238" y2="75" stroke="#5e5e5e" stroke-width="1.5" marker-end="url(#ga)"/>
<rect x="242" y="45" width="160" height="60" rx="8" fill="#fff" stroke="#4A7FC1" stroke-width="2.5"/>
<text x="322" y="72" text-anchor="middle" fill="#0a0a0a" font-family="ui-monospace,Menlo,monospace" font-size="12" font-weight="700">docgen build</text>
<text x="322" y="90" text-anchor="middle" fill="#5e5e5e" font-family="ui-monospace,Menlo,monospace" font-size="9.5">sectionize · TOC · polish · inline CSS</text>
<line x1="402" y1="75" x2="460" y2="75" stroke="#5e5e5e" stroke-width="1.5" marker-end="url(#ga)"/>
<rect x="464" y="45" width="160" height="60" rx="8" fill="#0a0a0a"/>
<text x="544" y="72" text-anchor="middle" fill="#fff" font-family="ui-monospace,Menlo,monospace" font-size="12" font-weight="700">doc.html</text>
<text x="544" y="90" text-anchor="middle" fill="#cfcfcf" font-family="ui-monospace,Menlo,monospace" font-size="9.5">self-contained · no network</text>
</svg><figcaption class="figcap">Fig. 1 — the docgen pipeline. Hollow = source; accent = the transform; solid ink = terminal artifact; the traveling dot shows direction (hidden under reduced motion).</figcaption></figure>

## Code blocks

```bash
# validate then build
python3 -m tools.docgen.cli check tools/docgen/gallery.md
python3 -m tools.docgen.cli build tools/docgen/gallery.md -o .docgen/gallery
```

## Changelog

| date | version | change |
|---|---|---|
| 2026-07-04 | 1.0 | DS-2: gallery created alongside template + generator |
