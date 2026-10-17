#!/usr/bin/env node
/* tools/mermaid-engine/render.mjs — Mermaid text -> SVG (or ASCII), fully offline.
 *
 * Renders exactly 6 diagram types: flowchart, sequence, class, state, ER, xychart. Mermaid's
 * gantt/git-graph/mindmap/kanban/etc. are NOT supported by the underlying library — see
 * README.md for why, and where Gantt-equivalent capability lives instead in this engine
 * (tools/visual-engine, via an ECharts custom-series job).
 *
 * Usage:
 *   node tools/mermaid-engine/render.mjs <input.mmd> [-o out.svg] [--ascii] [--bg '#hex'] [--fg '#hex'] [--theme name]
 *   printf 'graph TD\nA-->B\n' | node tools/mermaid-engine/render.mjs --stdin
 *
 * NOTE (OG-142): the header and the first statement must be on SEPARATE LINES.
 * `graph TD; A-->B` is valid upstream Mermaid but `beautiful-mermaid`, the vendored
 * parser, rejects it with `Invalid mermaid header`. This usage line documented the
 * inline-semicolon form and had never been run.
 *
 * Exit codes: 0 = rendered, 1 = usage/IO error, 2 = the diagram text itself is invalid Mermaid
 * (mirrors this engine's fail-closed convention elsewhere — see docgen's gate error codes).
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { renderMermaidSVG, renderMermaidASCII, THEMES } from 'beautiful-mermaid';

function parseArgs(argv) {
  const opts = { input: null, out: null, ascii: false, bg: null, fg: null, theme: null, stdin: false, transparent: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-o' || a === '--out') opts.out = argv[++i];
    else if (a === '--ascii') opts.ascii = true;
    else if (a === '--bg') opts.bg = argv[++i];
    else if (a === '--fg') opts.fg = argv[++i];
    else if (a === '--theme') opts.theme = argv[++i];
    else if (a === '--transparent') opts.transparent = true;
    else if (a === '--stdin') opts.stdin = true;
    else if (!a.startsWith('-')) opts.input = a;
  }
  return opts;
}

// beautiful-mermaid's SVG output unconditionally injects a live Google Fonts @import — a CDN
// reference this engine's own policy forbids at runtime (engine.config.json's
// security.allowRuntimeCDN, false everywhere else in this engine: force-graph, 3d-force-graph,
// and ECharts are all vendored). There is no library option to suppress it (confirmed: passing
// a custom `font` value just changes the *name* requested from the same CDN, not whether the
// @import is emitted). Strip the @import and fall back to a system-font stack instead — this is
// a one-line CSS change, not a rendering-quality regression: system UI fonts are legible and
// this only affects on-screen text rendering, never the diagram geometry.
const SYSTEM_FONT_STACK = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
function stripCdnFontImport(svg) {
  return svg
    .replace(/@import url\(['"]https:\/\/fonts\.googleapis\.com[^)]*\)\s*;?\s*/g, '')
    .replace(/font-family:\s*'[^']*',?\s*system-ui,\s*sans-serif;/g, `font-family: ${SYSTEM_FONT_STACK};`);
}

function readStdin() {
  try {
    return readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const text = opts.stdin ? readStdin() : opts.input ? readFileSync(opts.input, 'utf8') : null;
  if (!text || !text.trim()) {
    process.stderr.write('usage: render.mjs <input.mmd> [-o out.svg] [--ascii] [--bg color] [--fg color] [--theme name] [--transparent]\n');
    process.stderr.write('       (--bg/--fg accept any CSS color, including var(--name) to inherit a host page\'s theme)\n');
    process.stderr.write('       (or pipe text in with --stdin)\n');
    process.exit(1);
  }

  const renderOpts = {};
  if (opts.bg) renderOpts.bg = opts.bg;
  if (opts.fg) renderOpts.fg = opts.fg;
  // ⚠ **`--theme` WAS A COMPLETE NO-OP** (`OG-173`). The library takes `bg`/`fg`, not a theme
  // NAME, so `renderOpts.theme` was passed and silently ignored: every value — including
  // `totally-fake-theme` — produced byte-identical SVG and exited 0, while README.md documents the
  // flag as selecting "one of beautiful-mermaid's 15 built-in themes". A caller asking for `nord`
  // got the default palette and no signal that anything had happened.
  //
  // The 15 themes are real; each is a `{bg, fg}` pair in the library's `THEMES` export. Resolve
  // the name through it, and REFUSE an unknown one rather than rendering something the caller did
  // not ask for — a flag that silently ignores its argument is worse than one that does not exist.
  if (opts.theme) {
    const theme = THEMES[opts.theme];
    if (!theme) {
      process.stderr.write(
        `mermaid-engine: unknown --theme '${opts.theme}'. Available: ${Object.keys(THEMES).join(', ')}\n`,
      );
      process.exit(1);
    }
    // Explicit --bg/--fg win: they are the more specific request.
    if (!opts.bg) renderOpts.bg = theme.bg;
    if (!opts.fg) renderOpts.fg = theme.fg;
  }
  if (opts.transparent) renderOpts.transparent = true;

  let output;
  try {
    output = opts.ascii ? renderMermaidASCII(text, renderOpts) : renderMermaidSVG(text, renderOpts);
    if (!opts.ascii) output = stripCdnFontImport(output);
  } catch (err) {
    // Fail-closed with the library's own parse error, not a swallowed/garbled one — mirrors this
    // engine's convention elsewhere (docgen's gates, visual-engine's G-* codes) of surfacing the
    // real reason rather than a generic failure.
    process.stderr.write(`mermaid-engine: invalid diagram — ${err instanceof Error ? err.message : String(err)}\n`);
    process.exit(2);
  }

  if (opts.out) {
    writeFileSync(opts.out, output);
    process.stdout.write(`wrote ${opts.ascii ? 'ascii' : 'svg'}: ${opts.out}\n`);
  } else {
    process.stdout.write(output + '\n');
  }
}

main();
