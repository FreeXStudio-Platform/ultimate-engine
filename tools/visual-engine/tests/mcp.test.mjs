import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { renderSVG } from "../adapters/echarts/render.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const fixture = JSON.parse(readFileSync(join(ROOT, "fixtures", "normal", "detector-coverage-heatmap.json"), "utf8"));

/** Recursively sort object keys so two structurally-equal payloads compare equal regardless of
 * property insertion order, and so a failing diff prints in a stable, readable order. */
function sortKeysDeep(value) {
  if (Array.isArray(value)) return value.map(sortKeysDeep);
  if (value && typeof value === "object") {
    return Object.keys(value).sort().reduce((acc, k) => { acc[k] = sortKeysDeep(value[k]); return acc; }, {});
  }
  return value;
}

/**
 * P8-079: the frozen contract used to compare tool NAMES only, which a `.sort()` on strings can
 * satisfy while the tools' actual shapes have drifted underneath it — exactly what happened when
 * `visual_get_theme`'s enum fell to 4 values while `listCapabilities()`/`visual_render` moved to 5
 * (P8-065/P8-083): every name-only assertion here kept passing throughout. Compare the full
 * contract — name, description, and inputSchema — instead.
 */
function normalizeTools(tools) {
  return tools
    .map((t) => sortKeysDeep({ name: t.name, description: t.description, inputSchema: t.inputSchema }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function mcpSession() {
  const proc = spawn("node", [join(ROOT, "mcp", "server.mjs")], { stdio: ["pipe", "pipe", "inherit"] });
  let buf = "";
  const pending = new Map();
  let nextId = 1;
  proc.stdout.on("data", (d) => {
    buf += d;
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx); buf = buf.slice(idx + 1);
      if (!line.trim()) continue;
      try { const m = JSON.parse(line); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } } catch {}
    }
  });
  const rpc = (method, params) => new Promise((res, rej) => {
    const id = nextId++;
    pending.set(id, res);
    setTimeout(() => rej(new Error(`timeout: ${method}`)), 15_000);
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
  return { proc, rpc };
}

test("MCP facade: handshake, tool surface, render parity, refusal, fallback", async () => {
  const { proc, rpc } = mcpSession();
  try {
    const init = await rpc("initialize", { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "test", version: "0" } });
    assert.equal(init.result.serverInfo.name, "doc-visuals");
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");

    const tools = await rpc("tools/list", {});
    const names = tools.result.tools.map((t) => t.name).sort();
    assert.deepEqual(names, [
      "visual_explain_selection", "visual_get_theme", "visual_list_capabilities",
      "visual_list_presets", "visual_render", "visual_render_batch", "visual_validate_job",
    ]);
    // frozen contract: the full tool surface (name + description + inputSchema) must match the
    // live server, not just the sorted name list — see normalizeTools() above.
    const snapshot = JSON.parse(readFileSync(join(ROOT, "mcp", "tool-schema-snapshot.json"), "utf8"));
    const liveNormalized = normalizeTools(tools.result.tools);
    const snapshotNormalized = normalizeTools(snapshot.tools);
    assert.deepEqual(snapshotNormalized, liveNormalized,
      "tool-schema-snapshot.json diverges from the live MCP tool surface — regenerate it");

    // counter-example: a real divergence (one enum value altered on one tool) MUST fail this
    // comparison — proves the check is not vacuous the way the names-only assert.deepEqual was.
    const tampered = liveNormalized.map((t) => t.name === "visual_get_theme"
      ? sortKeysDeep({ ...t, inputSchema: JSON.parse(JSON.stringify(t.inputSchema).replace('"document-theme"', '"bogus-theme"')) })
      : t);
    assert.notDeepEqual(tampered, liveNormalized, "counter-example setup: mutation must actually differ");
    assert.throws(() => assert.deepEqual(tampered, snapshotNormalized),
      /AssertionError/, "an altered enum value must fail the frozen-contract comparison");

    // MCP render must equal direct-adapter render byte-for-byte (simulation 21: fallback parity)
    const viaMcp = await rpc("tools/call", { name: "visual_render", arguments: { job: fixture, formats: ["svg"] } });
    const payload = JSON.parse(viaMcp.result.content[0].text);
    const direct = renderSVG(fixture);
    assert.equal(payload.meta.svg_sha256, direct.meta.svg_sha256, "MCP and direct adapter diverge");

    // restricted refusal has no override path through MCP
    const refused = await rpc("tools/call", { name: "visual_render", arguments: { job: { ...fixture, classification: "restricted" }, formats: ["svg"] } });
    assert.equal(refused.result.isError, true);
    assert.match(refused.result.content[0].text, /G-CONF/);
  } finally {
    proc.kill();
  }
});
