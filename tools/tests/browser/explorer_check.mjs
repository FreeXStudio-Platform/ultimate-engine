// Browser check of docgen's module explorer (tools/docgen/assets/explorer_runtime.js) against a REAL built document,
// driven by real pointer and keyboard events in headless Chromium.
//
//   node tools/tests/browser/explorer_check.mjs <built.html> [screenshot-dir]
//
// Why a browser: a zoom that glides, labels that sit centred in rectangles that moved, arrows that follow a hover and a panel
// that follows a click are not knowable from bytes. The explorer's Python side is pinned by tools/tests/test_explorer.py;
// this file is the other half: does the thing a reader touches actually behave.
//
// The built document must contain ONE explorer whose figure id is "map" (its DOM id is "fig-map") built from the fixture in tools/tests/test_explorer_browser.py
// (system > api (routes (handlers, schemas), deps), db (models), bank).
//
// Exit codes: 0 = every check passed · 1 = a check failed · 3 = Playwright / a browser is not available (a SKIP, never a pass).
/* global document, window, getComputedStyle */
import fs from "node:fs";
import path from "node:path";
import { launchOrSkip, checks } from "./_launch.mjs";

const FILE = path.resolve(process.argv[2]);
const SHOTS = process.argv[3] ? path.resolve(process.argv[3]) : null;
if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
const b = await launchOrSkip();
const { ok, finish } = checks();
const errors = [];

async function open(ctxOpts = {}, viewport = { width: 1300, height: 1000 }) {
  const ctx = await b.newContext({ viewport, ...ctxOpts });
  const page = await ctx.newPage();
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("file://" + FILE);
  return { ctx, page };
}
const settled = (page) => page.waitForFunction(() => document.querySelector("[data-ve-explorer]").getAttribute("data-settled") === "1", null, { timeout: 4000 });
const state = (page) => page.evaluate(() => window.__veExplorers["fig-map"].state());
const visibleIds = (page) => page.evaluate(() => [...document.querySelectorAll(".ve-n:not(.ve-off)")].map((e) => e.getAttribute("data-id")).sort());
const tile = (page, id) => page.locator(`.ve-n[data-id="${id}"]`);
const shot = async (page, name) => { if (SHOTS) await (await page.locator("[data-ve-explorer]")).screenshot({ path: path.join(SHOTS, name + ".png") }); };
const near = (a, c, tol) => Math.abs(a - c) <= tol;

try {
// ------------------------------------------------------------------------------------------------------------------ start
{
  const { ctx, page } = await open();
  await page.locator("[data-ve-explorer]").scrollIntoViewIfNeeded();
  await settled(page);
  ok("the runtime takes over the explorer", await page.evaluate(() => document.querySelector("[data-ve-explorer]").getAttribute("data-ve-js") === "1"));
  ok("the map starts zoomed out on the whole system", (await state(page)).focus === "system");
  ok("only the top-level parts are drawn at the start", JSON.stringify(await visibleIds(page)) === JSON.stringify(["api", "bank", "db", "tiny"]));
  ok("the plain outline is hidden once the map is live", await page.evaluate(() => getComputedStyle(document.querySelector(".ve-ex-fallback")).display === "none"));
  ok("the panel says what the whole system is", (await page.locator(".ve-ex-title").innerText()) === "The system");
  ok("the Zoom out button is disabled at the top", await page.locator('[data-act="out"]').isDisabled());

  // labels: centred, inside their tile, no word broken
  const labelInfo = await page.evaluate(() => {
    const out = [];
    for (const l of document.querySelectorAll(".ve-ex-label")) {
      const r = l.getBoundingClientRect();
      const t = document.querySelector(`.ve-n[data-id="${[...document.querySelectorAll(".ve-n:not(.ve-off)")].find((n) => { const q = n.getBoundingClientRect(); return Math.abs(q.left - r.left) < 2 && Math.abs(q.top - r.top) < 2; })?.getAttribute("data-id")}"]`);
      const n = l.querySelector(".ve-ex-label-n");
      out.push({
        text: n.textContent, tile: !!t, centred: getComputedStyle(l).textAlign === "center" && getComputedStyle(l).justifyContent === "center",
        wordsFit: n.scrollWidth <= n.clientWidth + 1, weight: getComputedStyle(n).fontWeight,
        wrap: getComputedStyle(n).overflowWrap + "/" + getComputedStyle(n).wordBreak,
      });
    }
    return out;
  });
  ok("every drawn part big enough carries a label", labelInfo.length >= 2, `${labelInfo.length} labels`);
  ok("each label sits exactly on its own tile", labelInfo.every((l) => l.tile));
  ok("labels are centred", labelInfo.every((l) => l.centred));
  ok("labels are bold and never break inside a word", labelInfo.every((l) => Number(l.weight) >= 600 && l.wordsFit && l.wrap === "normal/normal"), JSON.stringify(labelInfo.map((l) => l.wrap)));
  const clipped = await page.evaluate(() => [...document.querySelectorAll(".ve-ex-label")].filter((l) => {
    const n = l.querySelector(".ve-ex-label-n");
    return n.scrollWidth > n.clientWidth + 1 || l.scrollHeight > l.clientHeight + 1 || [...l.children].some((c) => c.scrollWidth > l.clientWidth);
  }).map((l) => l.textContent.slice(0, 20)));
  ok("no label is clipped: a name that cannot fit whole is shrunk, then reduced, then left to the tooltip", clipped.length === 0, JSON.stringify(clipped));
  ok("a part too small for any label is still a part (it has a tile, a tooltip name and a panel)", await page.evaluate(() => { const t = document.querySelector('.ve-n[data-id="tiny"]'); return !!t && /Telemetryinstrumentation/.test(t.getAttribute("aria-label")); }));
  await shot(page, "01-whole");

  // hover arrows
  await tile(page, "api").hover();
  const outArrow = await page.evaluate(() => {
    const p = document.querySelector(".ve-ex-links path.ve-ex-arrow.ve-ex-out");
    return p ? { stroke: getComputedStyle(p).stroke, cls: p.getAttribute("class"), head: p.getAttribute("marker-end") } : null;
  });
  const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme") || "dark");
  const PAL = { dark: { out: "rgb(76, 201, 240)", in: "rgb(245, 138, 192)" }, light: { out: "rgb(10, 122, 161)", in: "rgb(184, 51, 125)" } };
  ok("hovering a part draws what it calls in the out colour", !!outArrow && outArrow.stroke === PAL[theme].out, `${theme}: ${JSON.stringify(outArrow)}`);
  ok("the arrow has a head", !!outArrow && /^url\(#fig-map-head-out\)$/.test(outArrow.head), outArrow && outArrow.head);
  ok("a tip names the part and says what a click does", await page.evaluate(() => { const t = document.querySelector(".ve-ex-tip"); return !t.hidden && /Ingress/.test(t.textContent) && /zoom in/i.test(t.textContent); }));
  await tile(page, "db").hover();
  const inArrow = await page.evaluate(() => { const p = document.querySelector(".ve-ex-links path.ve-ex-arrow.ve-ex-in"); return p ? getComputedStyle(p).stroke : null; });
  ok("hovering the other end draws the same edge in the in colour", inArrow === PAL[theme].in, `${theme}: ${inArrow}`);
  await shot(page, "02-hover");
  await page.mouse.move(2, 2);

  // zoom in
  const before = await state(page);
  await tile(page, "api").click();
  ok("a click starts a glide (the map is not settled mid-way)", await page.evaluate(() => document.querySelector("[data-ve-explorer]").getAttribute("data-settled") === null));
  await page.waitForTimeout(220);
  const mid = await state(page);
  await settled(page);
  const after = await state(page);
  ok("the camera moves to the clicked part", after.focus === "api" && after.camera.w < before.camera.w * 0.9, JSON.stringify(after.camera));
  ok("the clicked part's own parts are what is drawn", JSON.stringify(await visibleIds(page)) === JSON.stringify(["api.deps", "api.routes"]));
  ok("the trail shows where you are", JSON.stringify(await page.locator(".ve-ex-crumb").allInnerTexts()) === JSON.stringify(["The system", "Ingress & API"]));
  ok("the panel describes the part: status, size, text, facts", await page.evaluate(() => {
    const p = document.querySelector(".ve-ex-panel").textContent;
    return /Ingress & API/.test(p) && /leaky/.test(p) && /The public door/.test(p) && /Files/.test(p) && /Invariants/.test(p);
  }));
  ok("the panel lists what the part connects to as buttons that name their target", await page.evaluate(() => [...document.querySelectorAll(".ve-ex-panel .ve-ex-chip")].some((c) => c.getAttribute("data-go") === "db")));
  ok("the status line says where you landed", /Showing Ingress & API/.test(await page.locator(".ve-ex-status").innerText()));
  ok("mid-glide the camera was strictly between the two frames", mid.moving && mid.camera.w < before.camera.w - 1 && mid.camera.w > after.camera.w + 1, `${before.camera.w} > ${mid.camera.w} > ${after.camera.w}`);
  await shot(page, "03-api");

  // labels follow the camera: each label sits on its (new) tile
  const aligned = await page.evaluate(() => {
    const tiles = [...document.querySelectorAll(".ve-n:not(.ve-off)")].map((n) => n.getBoundingClientRect());
    return [...document.querySelectorAll(".ve-ex-label")].every((l) => { const r = l.getBoundingClientRect(); return tiles.some((q) => Math.abs(q.left - r.left) < 2 && Math.abs(q.top - r.top) < 2 && Math.abs(q.width - r.width) < 2); });
  });
  ok("after the glide every label sits on its tile again", aligned);

  // go deeper, then to a part in another branch through the panel
  await tile(page, "api.routes").click();
  await settled(page);
  ok("a second click goes one level deeper", (await state(page)).focus === "api.routes" && JSON.stringify(await visibleIds(page)) === JSON.stringify(["api.routes.handlers", "api.routes.schemas"]));
  ok("the trail grows", (await page.locator(".ve-ex-crumb").count()) === 3);
  await page.locator('.ve-ex-crumb', { hasText: "The system" }).click();
  await settled(page);
  ok("a name in the trail takes you straight back up", (await state(page)).focus === "system");

  // cross-branch jump through the panel (system -> api -> back out by chip to db)
  await tile(page, "api").click(); await settled(page);
  await page.locator('.ve-ex-panel .ve-ex-chip[data-go="db"]').first().click();
  const t0 = Date.now();
  await settled(page);
  const cross = await state(page);
  ok("a connection button zooms out and in to a part in another branch", cross.focus === "db", cross.focus);
  ok("that took a visible glide, not a cut", Date.now() - t0 >= 250, `${Date.now() - t0} ms`);
  await shot(page, "04-db");

  // whole system, zoom out, escape
  await page.locator('[data-act="reset"]').click(); await settled(page);
  ok("Whole system returns to the top", (await state(page)).focus === "system" && near((await state(page)).camera.w, 1000, 0.5));
  await tile(page, "api").click(); await settled(page);
  await page.locator('[data-act="out"]').click(); await settled(page);
  ok("Zoom out goes up exactly one level", (await state(page)).focus === "system");
  await tile(page, "api").click(); await settled(page);
  await page.keyboard.press("Escape"); await settled(page);
  ok("Escape goes up one level", (await state(page)).focus === "system");

  // reader
  await tile(page, "api").click(); await settled(page);
  await page.locator(".ve-ex-doc-btn").first().click();
  ok("a document opens in place", await page.evaluate(() => { const r = document.querySelector(".ve-ex-reader"); return !r.hidden && /What it is/.test(r.textContent) && /public door/.test(r.textContent) && !!r.querySelector("table"); }));
  ok("the opened copy carries no duplicate id", await page.evaluate(() => document.querySelectorAll('[id$="-doc-d-api"]').length === 1));
  ok("the reader covers the map and a button returns to it", await page.evaluate(() => { const r = document.querySelector(".ve-ex-reader").getBoundingClientRect(); const s = document.querySelector(".ve-ex-main").getBoundingClientRect(); return Math.abs(r.width - s.width) <= 2 && Math.abs(r.height - s.height) <= 2; }));
  await shot(page, "05-reader");
  await page.locator('[data-act="close-doc"]').click();
  ok("Back to the map closes the reader", await page.evaluate(() => document.querySelector(".ve-ex-reader").hidden));
  await page.locator(".ve-ex-doc-btn").first().click();
  await page.keyboard.press("Escape");
  ok("Escape closes the reader before it goes up", (await state(page)).focus === "api" && (await page.evaluate(() => document.querySelector(".ve-ex-reader").hidden)));
  await page.locator('[data-act="reset"]').click(); await settled(page);

  // keyboard
  const cursorId = await page.evaluate(() => document.querySelector('.ve-n[tabindex="0"]')?.getAttribute("data-id"));
  ok("exactly one tile is in the tab order", (await page.locator('.ve-n[tabindex="0"]').count()) === 1 && !!cursorId);
  await page.locator('.ve-n[tabindex="0"]').focus();
  const first = await page.evaluate(() => document.activeElement.getAttribute("data-id"));
  let moved = null;
  for (const key of ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"]) {
    await page.keyboard.press(key);
    const now = await page.evaluate(() => document.activeElement.getAttribute("data-id"));
    if (now && now !== first) { moved = now; break; }
  }
  ok("arrow keys move between parts", !!moved, `${first} -> ${moved}`);
  await page.locator('.ve-n[data-id="api"]').focus();
  ok("a part focused by keyboard shows its connections like a hovered one", await page.evaluate(() => document.querySelectorAll(".ve-ex-links path.ve-ex-arrow").length > 0));
  await page.keyboard.press("Enter"); await settled(page);
  ok("Enter opens the focused part", (await state(page)).focus === "api");
  await page.keyboard.press("Escape"); await settled(page);

  // colours: label contrast on every tone, both themes
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    const contrast = await page.evaluate(() => {
      const c = document.createElement("canvas"); c.width = c.height = 1; const g = c.getContext("2d", { willReadFrequently: true });
      const setFill = (c) => { g.fillStyle = c; }; const rgb = (v) => { g.clearRect(0, 0, 1, 1); setFill("#000"); setFill(v); g.fillRect(0, 0, 1, 1); const d = g.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2]]; };
      const lum = ([r, gg, bb]) => { const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(gg) + 0.0722 * f(bb); };
      const out = [];
      for (const n of document.querySelectorAll(".ve-n:not(.ve-off)")) {
        const fill = rgb(getComputedStyle(n).fill);
        const lab = [...document.querySelectorAll(".ve-ex-label")].find((l) => Math.abs(l.getBoundingClientRect().left - n.getBoundingClientRect().left) < 2);
        if (!lab) continue;
        const ink = rgb(getComputedStyle(lab).color);
        const a = lum(fill), bl = lum(ink);
        out.push({ id: n.getAttribute("data-id"), ratio: (Math.max(a, bl) + 0.05) / (Math.min(a, bl) + 0.05) });
      }
      return out;
    });
    ok(`label text reads on every tone in the ${theme} theme (>= 4.5:1)`, contrast.length > 0 && contrast.every((c) => c.ratio >= 4.5), JSON.stringify(contrast.map((c) => c.id + ":" + c.ratio.toFixed(1))));
  }
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));
  const lightArrow = await (async () => { await tile(page, "api").hover(); return page.evaluate(() => { const p = document.querySelector(".ve-ex-links path.ve-ex-arrow.ve-ex-out"); return p ? getComputedStyle(p).stroke : null; }); })();
  ok("the arrow colours have a light-theme pair", lightArrow === "rgb(10, 122, 161)", String(lightArrow));
  await shot(page, "06-light");
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  await page.mouse.move(2, 2);

  // resize: labels follow
  await page.setViewportSize({ width: 900, height: 900 });
  await page.waitForTimeout(150);
  const afterResize = await page.evaluate(() => {
    const tiles = [...document.querySelectorAll(".ve-n:not(.ve-off)")].map((n) => n.getBoundingClientRect());
    const labels = [...document.querySelectorAll(".ve-ex-label")];
    return labels.length > 0 && labels.every((l) => { const r = l.getBoundingClientRect(); return tiles.some((q) => Math.abs(q.left - r.left) < 2 && Math.abs(q.width - r.width) < 2); });
  });
  ok("resizing the window re-places the labels", afterResize);
  await ctx.close();
}

// ------------------------------------------------------------------------------------------------------ reduced motion
{
  const { ctx, page } = await open({ reducedMotion: "reduce" });
  await settled(page);
  await tile(page, "api").click();
  const st = await state(page);
  ok("with reduced motion the zoom is a cut: settled the moment the click returns", st.focus === "api" && !st.moving && await page.evaluate(() => document.querySelector("[data-ve-explorer]").getAttribute("data-settled") === "1"));
  ok("with reduced motion the camera frame is exactly the part's rectangle", await page.evaluate(() => { const s = window.__veExplorers["fig-map"].state().camera; const d = JSON.parse(document.querySelector(".ve-ex-data").textContent); const r = d.nodes.api.r; return Math.abs(s.x - r[0]) < 0.01 && Math.abs(s.w - r[2]) < 0.01; }));
  await ctx.close();
}

// ----------------------------------------------------------------------------------------------------------- narrow screen
{
  const { ctx, page } = await open({}, { width: 390, height: 800 });
  await settled(page);
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  ok("on a phone-width screen nothing scrolls sideways", fits);
  ok("on a phone-width screen the panel sits under the map", await page.evaluate(() => { const s = document.querySelector(".ve-ex-stage").getBoundingClientRect(); const p = document.querySelector(".ve-ex-panel").getBoundingClientRect(); return p.top >= s.bottom - 1; }));
  await tile(page, "api").click(); await settled(page);
  ok("on a phone-width screen a tap zooms", (await state(page)).focus === "api");
  await shot(page, "07-phone");
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------------- print + no script
{
  const { ctx, page } = await open();
  await settled(page);
  await page.emulateMedia({ media: "print" });
  ok("printed, the map gives way to the full outline", await page.evaluate(() => getComputedStyle(document.querySelector(".ve-ex-main")).display === "none" && getComputedStyle(document.querySelector(".ve-ex-fallback")).display !== "none"));
  await ctx.close();
}
{
  const { ctx, page } = await open({ javaScriptEnabled: false });
  ok("without script the map is hidden and the outline is shown", await page.evaluate(() => getComputedStyle(document.querySelector(".ve-ex-main")).display === "none" && getComputedStyle(document.querySelector(".ve-ex-fallback")).display !== "none"));
  ok("without script the outline carries the parts", await page.evaluate(() => { const t = document.querySelector(".ve-ex-fallback").textContent; return /Ingress & API/.test(t) && /Persistence/.test(t) && /Contract bank/.test(t); }));
  await ctx.close();
}

} catch (e) { ok("every check ran to the end", false, String(e).split("\n").slice(0, 2).join(" ")); }
ok("the page raised no console error", errors.length === 0, errors.slice(0, 3).join(" | "));
await b.close();
finish();
