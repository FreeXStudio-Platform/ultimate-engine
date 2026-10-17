<!-- classification: public -->

# Export policy

### SVG canonical · PNG convenience · HTML self-contained · 2026-08-08 · v1.0.0

| Format | Status | Notes |
|---|---|---|
| **SVG** (SSR) | **canonical** | deterministic, id-normalized, aria-labeled, provenance-stamped (`content-sha256`), embeds in docgen HTML/PDF and markdown |
| **PNG** | convenience | rasterized from the canonical SVG via @resvg/resvg-js at 2× width; system-font dependent → per-host deterministic only; never the archival format |
| **Interactive HTML** | first-class for exploration | fully self-contained (echarts.min.js inlined, zero CDN — docgen law), includes the static SVG as `prefers-reduced-motion`/`print` fallback, text summary as figcaption |
| **PDF embed** | via docgen/weasyprint | embed the SVG in a docgen document; print-theme recommended |
| **JSON (figure record)** | AI-only sidecar, `--formats json` / `formats: ["json"]` | `<visual_id>.figure.json`, schema `ultimate-engine/figure/1`: what every mark means (id, label, value, neighbours, plain-language description), how to read the chart, provenance (`svg.sha256`, `job.sha256`). Generated from the live ECharts model in the same render, so it cannot disagree with the SVG; meaning only, no geometry or colours. Hashes sit under a bare `sha256` key so docgen's leak-gate reads them as hashes. |

**Inline SVG carries the figure contract.** The canonical SVG is safe to inline next to other charts: its `id`s,
`url(#…)` references and its one `<style>` are scoped to the figure (`svg[data-fig="ve-<visual_id>"]`), and every mark
carries `data-*` attributes and a `<title>`. A consumer must not strip the `<style>` or rewrite `data-id`
(`docs/design/FIGURE_SYSTEM.md` §2–§3).

Rules: every export of a source-of-truth visual keeps its job JSON + evidence
file next to the render hash (Gate G8/G9). Static meaning must equal
interactive meaning — the HTML template renders the SAME option object, only
with animation re-enabled. Renders land in `renders/current/` (gitignored)
except golden fixtures in `renders/golden/` (committed).
