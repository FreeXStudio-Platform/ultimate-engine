// Browser check of docgen's figure runtime (tools/docgen/assets/figure_runtime.js) against a REAL built document:
// native diagrams plus engine charts, driven by real pointer and keyboard events in headless Chromium.
//
//   node tools/tests/browser/figure_runtime_check.mjs <built.html> [screenshot.png]
//
// Why a browser: hover colour, flicker, adjacency, tooltips and pinning are not knowable from bytes. Three of the
// defects this check exists for passed every byte-level test (OG-250..261) — including an id-scoping bug that broke
// every adjacency highlight and was found only by hovering a node.
//
// Exit codes: 0 = every check passed · 1 = a check failed · 3 = Playwright / a browser is not available (the caller
// reports a SKIP with this cause; it is never read as a pass).
/* global document, window, location, getComputedStyle */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..", "..");
function loadPlaywright() {
  const bases = [process.env.PLAYWRIGHT_MODULE_DIR, process.cwd(), ROOT, path.join(ROOT, "tools", "visual-engine")]
    .filter(Boolean).map((d) => path.join(d, "package.json"));
  for (const base of bases) {
    for (const name of ["playwright", "playwright-core", "@playwright/test"]) {
      try { return createRequire(base)(name); } catch { /* try the next */ }
    }
  }
  return null;
}
function chromiumPath() {
  const cache = path.join(process.env.HOME || "", "Library", "Caches", "ms-playwright");
  const linux = path.join(process.env.HOME || "", ".cache", "ms-playwright");
  for (const dir of [cache, linux]) {
    if (!fs.existsSync(dir)) continue;
    for (const d of fs.readdirSync(dir).filter((x) => /^chromium_headless_shell-/.test(x)).sort().reverse()) {
      const sub = fs.readdirSync(path.join(dir, d)).find((x) => x.startsWith("chrome-headless-shell"));
      if (!sub) continue;
      for (const bin of ["chrome-headless-shell", path.join("chrome-headless-shell-mac-arm64", "chrome-headless-shell")]) {
        const full = path.join(dir, d, sub, bin);
        if (fs.existsSync(full)) return full;
      }
    }
  }
  return undefined;
}
const pw = loadPlaywright();
if (!pw) { console.log("SKIP: playwright is not installed (set PLAYWRIGHT_MODULE_DIR or `npm i -D playwright`)"); process.exit(3); }
let b;
try {
  const exe = chromiumPath();
  b = await pw.chromium.launch(exe ? { executablePath: exe } : {});
} catch (e) { console.log("SKIP: no Chromium available — " + String(e).split("\n")[0]); process.exit(3); }

const FILE = path.resolve(process.argv[2]);
const SHOT = process.argv[3] || null;
const page = await b.newPage({ viewport: { width: 1300, height: 1000 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto('file://' + FILE);
await page.waitForTimeout(400);
const out = [];
const ok = (name, cond, extra = '') => { out.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  — ' + extra : ''}`); };

// ---- runtime booted
const boot = await page.evaluate(() => ({
  flag: !!window.__veFigures,
  figs: document.querySelectorAll('svg[data-fig]').length,
  js: document.querySelectorAll('svg[data-fig][data-ve-js]').length,
  nativeTitles: document.querySelectorAll('svg[data-fig] [data-tip]').length,
  leftoverTitles: document.querySelectorAll('svg[data-fig] [data-tip] > title').length,
}));
ok('runtime booted on every figure', boot.flag && boot.figs === boot.js, JSON.stringify(boot));
ok('native <title> withdrawn where a styled tooltip replaces it', boot.leftoverTitles === 0 && boot.nativeTitles > 10);

const centre = async (sel) => {
  const found = await page.evaluate((s) => { const el = document.querySelector(s); if (!el) return false; el.scrollIntoView({ block: 'center' }); return true; }, sel);
  if (!found) return null;
  await page.waitForTimeout(200); // let the scroll event land before the pointer moves (tooltips hide on scroll)
  return page.evaluate((s) => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height }; }, sel);
};
const lit = async (fig) => page.evaluate((f) => [...document.querySelectorAll(`svg[data-fig="${f}"] .ve-on`)].map((e) => e.getAttribute('data-id')).filter(Boolean), fig);
const tip = async () => page.evaluate(() => { const t = document.querySelector('.ve-tip'); return t && !t.hidden ? t.innerText : null; });

// ---- native flowchart: hover a node → tooltip + its neighbours light
const fl = 'svg[data-fig="fig-flow"]';
let p = await centre(`${fl} [data-k="node"][data-id="n1"]`);
await page.mouse.move(p.x, p.y); await page.waitForTimeout(250);
let t = await tip(); let l = await lit('fig-flow');
ok('flowchart node: tooltip shows its label', !!t && /Step 1/.test(t), JSON.stringify(t));
ok('flowchart node: itself, neighbours and joining edges stay lit', ['n1', 'n0', 'n2'].every((i) => l.includes(i)) && l.some((i) => /^e/.test(i)), JSON.stringify(l));
ok('flowchart node: an unrelated node is NOT lit', !l.includes('n3'), JSON.stringify(l));
const fillBefore = await page.evaluate((s) => getComputedStyle(document.querySelector(s + ' [data-k="node"][data-id="n1"] rect, ' + s + ' [data-k="node"][data-id="n1"] path')).fill, fl);
// ---- hovering must not change hue
await page.mouse.move(2, 2); await page.waitForTimeout(250);
const fillAfterLeave = await page.evaluate((s) => getComputedStyle(document.querySelector(s + ' [data-k="node"][data-id="n1"] rect, ' + s + ' [data-k="node"][data-id="n1"] path')).fill, fl);
ok('flowchart node: fill identical hovered vs not hovered (no hue change)', fillBefore === fillAfterLeave, `${fillBefore} / ${fillAfterLeave}`);
ok('leaving a figure clears the highlight and hides the tooltip', (await lit('fig-flow')).length === 0 && (await tip()) === null);

// ---- edge hit target: hovering the wide transparent twin lights the edge and both ends
p = await centre(`${fl} path.edge-hit[data-id="e1"]`);
await page.mouse.move(p.x, p.y); await page.waitForTimeout(250);
l = await lit('fig-flow');
ok('flowchart edge: lights itself and both end nodes', l.includes('e1') && l.includes('n1') && l.includes('n2'), JSON.stringify(l));
const hitW = await page.evaluate((s) => getComputedStyle(document.querySelector(s + ' path.edge-hit[data-id="e1"]')).strokeWidth, fl);
ok('flowchart edge: the pointer target does not shrink while lit', parseFloat(hitW) >= 10, hitW);

// ---- badge: click navigates to its key line
p = await centre(`${fl} a.fig-badge`);
await page.mouse.click(p.x, p.y); await page.waitForTimeout(250);
const hash = await page.evaluate(() => location.hash);
const target = await page.evaluate(() => { const e = document.querySelector(':target'); return e ? e.tagName + '#' + e.id : null; });
ok('numbered circle: click jumps to its line in the key', /^#fig-flow-k\d+$/.test(hash) && /^LI#fig-flow-k/.test(target || ''), `${hash} → ${target}`);
const badgeR = await page.evaluate((s) => parseFloat(document.querySelector(s + ' a.fig-badge circle').getAttribute('r')), fl);
ok('numbered circle: large enough to read and to hit (r >= 17)', badgeR >= 17, `r=${badgeR}`);

// ---- click pins a mark; Escape releases
await page.mouse.move(2, 2); await page.waitForTimeout(150);
p = await centre(`${fl} [data-k="node"][data-id="n2"]`);
await page.mouse.click(p.x, p.y); await page.waitForTimeout(250);
t = await tip();
const pinned = await page.evaluate(() => document.querySelectorAll('.ve-pin').length);
ok('click pins the mark and says how to release it', pinned === 1 && /pinned/.test(t || ''), JSON.stringify(t));
await page.mouse.move(p.x + 400, p.y + 200); await page.waitForTimeout(200);
ok('a pinned tooltip survives the pointer leaving', (await tip()) !== null);
await page.keyboard.press('Escape'); await page.waitForTimeout(200);
ok('Escape releases the pin', (await page.evaluate(() => document.querySelectorAll('.ve-pin').length)) === 0 && (await tip()) === null);

// ---- sequence: hover a participant lights its messages
const sq = 'svg[data-fig="fig-seq"]';
const actor = await page.evaluate((s) => { const e = document.querySelector(s + ' [data-k="node"]'); return e ? e.getAttribute('data-id') : null; }, sq);
p = await centre(`${sq} [data-k="node"][data-id="${actor}"]`);
await page.mouse.move(p.x, p.y); await page.waitForTimeout(250);
l = await lit('fig-seq');
ok('sequence: hovering a participant lights its messages', l.length >= 3, JSON.stringify(l));
await page.mouse.move(2, 2);

// ---- engine graph: adjacency + counts in the tooltip
const gr = 'svg[data-fig="ve-SIM-04-workflow-pipeline"]';
const node = await page.evaluate((s) => { const e = document.querySelector(s + ' [data-k="node"][data-nb]'); return e ? e.getAttribute('data-id') : null; }, gr);
p = await centre(`${gr} [data-k="node"][data-id="${node}"]`);
await page.mouse.move(p.x, p.y); await page.waitForTimeout(250);
t = await tip(); l = await lit("ve-SIM-04-workflow-pipeline");
ok('engine graph node: tooltip carries its connection count', !!t && /connection/.test(t), JSON.stringify(t));
ok('engine graph node: neighbours and edges light', l.length >= 3, JSON.stringify(l));
// ---- engine graph: DIRECTION. While a node is focused, the lines leaving it, entering it or running both ways are classed and
// painted from the figure's direction palette - the one declared exception to "a hover never changes hue" (the hue IS the data).
const ends = await page.evaluate((s) => [...document.querySelectorAll(s + ' [data-k="edge"][data-en]')].map((e) => [e.getAttribute('data-id'), ...e.getAttribute('data-en').split(' ')]), gr);
const edgeIds = [...new Set(ends.map((e) => e[0]))];
const endsOf = (id) => ends.find((e) => e[0] === id).slice(1);
const hub = await page.evaluate((s) => [...document.querySelectorAll(s + ' [data-k="node"][data-id]')].map((n) => n.getAttribute('data-id')), gr);
const both = hub.find((n) => edgeIds.some((e) => endsOf(e)[0] === n) && edgeIds.some((e) => endsOf(e)[1] === n));
ok('engine graph: the fixture has a node with lines both leaving and entering it', !!both, String(both));
p = await centre(`${gr} [data-k="node"][data-id="${both}"]`);
await page.mouse.move(2, 2); await page.waitForTimeout(150);
await page.mouse.move(p.x, p.y); await page.waitForTimeout(300);
const dirs = await page.evaluate((s) => {
  const pick = (c) => [...new Set([...document.querySelectorAll(`${s} [data-k="edge"].${c}`)].map((e) => e.getAttribute('data-id')))].sort();
  const sample = (c) => { const e = document.querySelector(`${s} path[fill="none"][data-k="edge"].${c}`); return e ? getComputedStyle(e).stroke : null; };
  return { out: pick('ve-out'), in: pick('ve-in'), both: pick('ve-both'), outStroke: sample('ve-out'), inStroke: sample('ve-in') };
}, gr);
const wantOut = edgeIds.filter((e) => endsOf(e)[0] === both && endsOf(e)[1] !== both && !edgeIds.some((r) => endsOf(r)[0] === endsOf(e)[1] && endsOf(r)[1] === both)).sort();
const wantIn = edgeIds.filter((e) => endsOf(e)[1] === both && endsOf(e)[0] !== both && !edgeIds.some((r) => endsOf(r)[0] === both && endsOf(r)[1] === endsOf(e)[0])).sort();
ok('engine graph: every line leaving the focused node is classed "out"', JSON.stringify(dirs.out) === JSON.stringify(wantOut), JSON.stringify([dirs.out, wantOut]));
ok('engine graph: every line entering it is classed "in"', JSON.stringify(dirs.in) === JSON.stringify(wantIn), JSON.stringify([dirs.in, wantIn]));
ok('engine graph: out and in are painted in two different colours', !!dirs.outStroke && !!dirs.inStroke && dirs.outStroke !== dirs.inStroke, `${dirs.outStroke} / ${dirs.inStroke}`);
const pageTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme') || 'dark');
const palette = { dark: ['rgb(76, 201, 240)', 'rgb(245, 138, 192)'], light: ['rgb(10, 122, 161)', 'rgb(184, 51, 125)'] }[pageTheme];
ok(`engine graph: the direction colours are the declared ${pageTheme}-theme palette, not an accident`, !!palette && dirs.outStroke === palette[0] && dirs.inStroke === palette[1], `${dirs.outStroke} / ${dirs.inStroke}`);
// the other theme, by flipping the page's own switch: the figure follows it
await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), pageTheme === 'dark' ? 'light' : 'dark');
await page.waitForTimeout(150);
const other = await page.evaluate((s) => { const e = document.querySelector(`${s} path[fill="none"][data-k="edge"].ve-out`); return e ? getComputedStyle(e).stroke : null; }, gr);
const otherWant = { dark: 'rgb(76, 201, 240)', light: 'rgb(10, 122, 161)' }[pageTheme === 'dark' ? 'light' : 'dark'];
ok('engine graph: the direction colours follow the page theme', other === otherWant, `${other} want ${otherWant}`);
await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), pageTheme);
await page.mouse.move(2, 2); await page.waitForTimeout(250);
const left = await page.evaluate((s) => document.querySelectorAll(`${s} .ve-out, ${s} .ve-in, ${s} .ve-both`).length, gr);
ok('engine graph: leaving the node removes every direction class', left === 0, `${left} left`);
const strayDir = await page.evaluate(() => [...document.querySelectorAll('svg[data-fig]')].filter((s) => s.getAttribute('data-fig-kind') !== 'graph' && s.querySelector('.ve-out,.ve-in,.ve-both')).length);
ok('direction classes appear only on graphs', strayDir === 0);
// nearest-mark assist: on a line chart's small point symbols, a pointer a few px beside the dot still answers
const ln = 'svg[data-fig="ve-SIM-08-queue-latency"]';
const dot = await page.evaluate((s) => {
  for (const e of document.querySelectorAll(s + ' [data-s][data-id]')) {
    const r = e.getBoundingClientRect(); if (r.width > 0 && r.width <= 12 && r.height <= 12 && e.getAttribute('data-k') !== 'edge') return e.getAttribute('data-id');
  } return null;
}, ln);
p = await centre(`${ln} [data-id="${dot}"]`);
await page.mouse.move(2, 2); await page.waitForTimeout(150);
await page.mouse.move(p.x + p.w / 2 + 6, p.y); await page.waitForTimeout(250);
ok('nearest-mark assist: a pointer just beside a small dot still finds it', (await tip()) !== null, JSON.stringify(await tip()) + ' dot=' + dot + ' w=' + p.w);
// a point that draws its own coloured ring keeps that colour while hovered (OG-269: a blue point turned black)
const dotSel = `${ln} [data-id="${dot}"]`;
await page.mouse.move(2, 2); await page.waitForTimeout(150);
const ringBefore = await page.evaluate((s) => getComputedStyle(document.querySelector(s)).stroke, dotSel);
await page.mouse.move(p.x, p.y); await page.waitForTimeout(250);
const ringHover = await page.evaluate((s) => getComputedStyle(document.querySelector(s)).stroke, dotSel);
ok('engine point: its ring keeps its colour while hovered (no black)', ringBefore === ringHover && ringBefore !== 'none', `${ringBefore} / ${ringHover}`);
await page.mouse.move(2, 2);

// ---- engine bars: legend/series; hover colour is unchanged
const br = 'svg[data-fig="ve-SIM-17-svg"]';
const bar = await page.evaluate((s) => { const e = document.querySelector(s + ' [data-s][data-id]:not([data-t="legend"])'); return e ? e.getAttribute('data-id') : null; }, br);
const barSel = `${br} [data-id="${bar}"]`;
const fillBar0 = await page.evaluate((s) => getComputedStyle(document.querySelector(s)).fill, barSel);
p = await centre(barSel);
await page.mouse.move(p.x, p.y); await page.waitForTimeout(250);
const fillBar1 = await page.evaluate((s) => getComputedStyle(document.querySelector(s)).fill, barSel);
ok('engine bar: tooltip shows the exact value', /\d/.test((await tip()) || ''), JSON.stringify(await tip()));
ok('engine bar: fill unchanged while hovered (no black/white/flash)', fillBar0 === fillBar1, `${fillBar0} / ${fillBar1}`);
await page.mouse.move(2, 2);

// ---- native heatmap: each value is painted in the ink chosen for ITS cell. A `fill` attribute loses to any stylesheet
// rule, and `.chart-value{fill:currentColor}` painted every value one colour until the ink rode in `style` (OG-275).
const heatInks = await page.evaluate(() => [...document.querySelectorAll('figure#fig-heat svg text.chart-value[fill]')]
  .map((t) => ({ declared: t.getAttribute('fill'), computed: getComputedStyle(t).fill })));
const toRgb = (hex) => { const h = hex.replace('#', ''); const n = parseInt(h.length === 3 ? h.replace(/./g, '$&$&') : h, 16); return `rgb(${n >> 16}, ${(n >> 8) & 255}, ${n & 255})`; };
ok('native heatmap: all four cell values are painted in the ink their cell asked for',
  heatInks.length === 4 && heatInks.every((h) => h.computed === toRgb(h.declared)), JSON.stringify(heatInks));
ok('native heatmap: light and dark cells do not share one ink', new Set(heatInks.map((h) => h.computed)).size >= 2, JSON.stringify(heatInks.map((h) => h.computed)));

// ---- keyboard: Tab reaches a mark, focus shows the tooltip, Enter pins
await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
const focused = await page.evaluate(() => { const a = document.activeElement; return a ? (a.getAttribute('data-id') || a.tagName) : null; });
ok('keyboard: Tab lands on a figure mark or link', !!focused, String(focused));

// ---- chips and refs navigate
await page.evaluate(() => { location.hash = ''; window.scrollTo(0, 0); });
await page.click('a.fig-ref[href="#fig-flow"]'); await page.waitForTimeout(150);
ok('text → figure: a [[fig:]] reference jumps to the figure', (await page.evaluate(() => location.hash)) === '#fig-flow');
await page.click('figure#fig-flow a.fig-up'); await page.waitForTimeout(150);
ok('figure → text: the figure links back to its section', /^#sec-/.test(await page.evaluate(() => location.hash)));
ok('section → figure: chips exist for every figure', (await page.evaluate(() => document.querySelectorAll('a.fig-chip').length)) === 6);

// ---- reference cards: a number says what it is. The index ships in the page; hover or focus a reference and a card appears.
const cardText = async () => page.evaluate(() => { const c = document.querySelector('.ve-card'); return c && !c.hidden ? c.innerText : null; });
await page.evaluate(() => { location.hash = ''; window.scrollTo(0, 0); });
await page.mouse.move(2, 2); await page.waitForTimeout(300);
ok('reference card: absent until a reference is touched', (await cardText()) === null);
p = await centre('a.fig-ref[href="#fig-flow"]');
await page.mouse.move(p.x, p.y); await page.waitForTimeout(400);
let card = await cardText();
ok('reference card: hovering "Fig. N" in the text says what the figure is', !!card && /FIG\. 1/i.test(card) && /pipeline/i.test(card), JSON.stringify(card));
ok('reference card: and where it lives', /Section/.test(card || '') && /First section/.test(card || ''), JSON.stringify(card));
ok('reference card: and the question the figure answers', /What happens, in order\?/.test(card || ''), JSON.stringify(card));
// the pointer can travel from the reference into the card and click its link
const cb = await page.evaluate(() => { const r = document.querySelector('.ve-card').getBoundingClientRect(); return { x: r.left + 20, y: r.top + r.height / 2 }; });
const refBox = await page.evaluate(() => { const r = document.querySelector('a.fig-ref[href="#fig-flow"]').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.bottom }; });
await page.mouse.move(refBox.x, refBox.y + 2, { steps: 4 });
await page.mouse.move(cb.x, cb.y, { steps: 6 }); await page.waitForTimeout(350);
ok('reference card: stays open while the pointer is inside it', (await cardText()) !== null);
await page.click('.ve-card a.ve-card-link'); await page.waitForTimeout(250);
ok('reference card: its section link navigates and closes it', /^#sec-/.test(await page.evaluate(() => location.hash)) && (await cardText()) === null);
// a section's back-link and a heading number
await page.evaluate(() => { location.hash = ''; window.scrollTo(0, 0); });
p = await centre('figure#fig-flow a.fig-up');
await page.mouse.move(p.x, p.y); await page.waitForTimeout(400);
card = await cardText();
ok('reference card: a back-link opens its SECTION (title, the figures in it)', /section/i.test(card || '') && /Fig\. 1/.test(card || '') && /pipeline/i.test(card || ''), JSON.stringify(card));
await page.mouse.move(2, 2); await page.waitForTimeout(500);
ok('reference card: moving away closes it', (await cardText()) === null);
const secN = await page.evaluate(() => { const e = document.querySelector('.sec-n'); return e ? { n: e.textContent, ref: e.getAttribute('data-ref') } : null; });
ok('heading number: the number before a numbered heading is a reference', !!secN && secN.n === '3' && /^sec-3/.test(secN.ref), JSON.stringify(secN));
await page.focus('.sec-n'); await page.waitForTimeout(300);
card = await cardText();
ok('heading number: keyboard focus shows the section card', /section 3/i.test(card || '') && /Charts/.test(card || ''), JSON.stringify(card));
await page.keyboard.press('Escape'); await page.waitForTimeout(150);
ok('reference card: Escape closes it', (await cardText()) === null);
const doubled = await page.evaluate(() => document.querySelectorAll('a[data-ref][title], .sec-n[title]').length);
ok('reference card: the link carries no native tooltip of its own (one explanation, not two)', doubled === 0, `${doubled}`);

ok('no console or page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
console.log(out.join('\n'));
if (SHOT) {
  await page.evaluate(() => { location.hash = ''; window.scrollTo(0, 0); });
  p = await centre(`${fl} [data-k="node"][data-id="n1"]`);
  await page.mouse.move(p.x, p.y); await page.waitForTimeout(300);
  await page.screenshot({ path: SHOT });
}
await b.close();
process.exit(out.some((l) => l.startsWith('FAIL')) ? 1 : 0);
