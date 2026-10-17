#!/usr/bin/env node
/**
 * ELK auto-layout bridge — an edge list in, coordinates out.
 *
 * WHY THIS EXISTS
 * ===============
 * docgen's documented gap since the beginning: *"no auto-layout algorithm exists in docgen for a
 * plain edge-list"* — every node diagram needs hand-supplied `x`/`y`, and the hand-layout
 * iterations against the 1.5x-short-side gap rule were the largest authoring cost measured in the
 * gallery build. `BUILD_PLAN.md` D5 records the decision and the reason it is nearly free:
 * `elkjs` is ALREADY in this tree as a transitive dependency of `beautiful-mermaid`, so wiring it
 * costs **zero new dependency**.
 *
 * CONTRACT
 * ========
 * stdin  : {"nodes":[{"id","width","height"}...], "edges":[{"source","target"}...], "options":{}}
 * stdout : {"ok":true,"nodes":[{"id","x","y","width","height"}...],"width","height"}
 *          {"ok":false,"error":"..."} on any failure, with exit code 1.
 *
 * **Never partially succeeds.** A layout that placed some nodes and defaulted the rest to (0,0)
 * would render as a legible diagram with a pile in the corner — the kind of wrong output that
 * looks like a design choice. Either every node has real coordinates or this reports failure.
 *
 * DETERMINISM IS A REQUIREMENT, NOT A PREFERENCE
 * =============================================
 * The output of this script is COMMITTED and checked against a fresh run (`blueprint layout
 * --check`). ELK's layered algorithm is deterministic for a fixed input and version, and the input
 * is sorted by the caller before it arrives here, so two runs on one tree produce identical bytes.
 * If that ever stops being true the check fails loudly, which is the correct outcome: a derived
 * artifact that cannot be re-derived is not derived, it is just a file.
 */

import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// elkjs lives under the mermaid engine's node_modules (transitive via beautiful-mermaid), which is
// not on this script's own resolution path. Resolve it explicitly rather than requiring a second
// install: a duplicate dependency is a version-skew defect waiting to happen, and D5's whole
// argument is that this costs nothing.
const ELK_PATH = path.join(HERE, '..', 'mermaid-engine', 'node_modules', 'elkjs', 'lib', 'elk.bundled.js');

function fail(message) {
  process.stdout.write(JSON.stringify({ ok: false, error: message }) + '\n');
  process.exit(1);
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf8');
}

async function main() {
  let ELK;
  try {
    const require = createRequire(import.meta.url);
    ELK = require(ELK_PATH);
  } catch (err) {
    fail(`elkjs not resolvable at ${ELK_PATH}: ${err.message}`);
    return;
  }

  let input;
  try {
    input = JSON.parse(await readStdin());
  } catch (err) {
    fail(`stdin is not valid JSON: ${err.message}`);
    return;
  }
  const nodes = Array.isArray(input.nodes) ? input.nodes : [];
  const edges = Array.isArray(input.edges) ? input.edges : [];
  if (nodes.length === 0) {
    // An empty layout is not a result. `RULES.md` Rule 6: a builder that produces an empty result
    // exits non-zero, because an empty map is a confident lie every downstream reader believes.
    fail('no nodes supplied — an empty layout is not a result');
    return;
  }

  const graph = {
    id: 'root',
    layoutOptions: Object.assign(
      {
        'elk.algorithm': 'layered',
        'elk.direction': 'DOWN',
        // THE GAP RULE, ENCODED ONCE INSTEAD OF ITERATED BY HAND.
        // docgen refuses any pair of nodes closer than 1.5x the larger node's short side, and with
        // 48px-tall boxes that is 72px. The first version of this file used ELK's own 48px default
        // and docgen rejected the result with two gap violations — which is exactly the
        // hand-layout loop D5 exists to remove, reproduced mechanically. These numbers clear the
        // rule with margin, and `blueprint layout` asserts zero node-placement findings so a future
        // change to either side is caught rather than eyeballed.
        'elk.spacing.nodeNode': '100',
        // `nodeNode` governs NEIGHBOURS INSIDE one component. Nodes with no edge between them are
        // separate ELK COMPONENTS, laid out at `componentComponent` — default 20px, below the 72px
        // docgen refuses. This engine's own package graph is fully connected, so the split never
        // showed here; a foreign host with a sparse import graph produced a layout ELK called ok
        // and the renderer rejected with four gap violations (`OG-246`). Same conservative
        // distance as peer nodes, for the same reason.
        'elk.spacing.componentComponent': '100',
        'elk.layered.spacing.nodeNodeBetweenLayers': '140',
        'elk.edgeRouting': 'ORTHOGONAL',
      },
      input.options || {},
    ),
    children: nodes.map((n) => ({
      id: String(n.id),
      width: Number(n.width) || 160,
      height: Number(n.height) || 48,
    })),
    edges: edges.map((e, i) => ({
      id: `e${i}`,
      sources: [String(e.source)],
      targets: [String(e.target)],
    })),
  };

  try {
    const elk = new ELK();
    const laid = await elk.layout(graph);
    const placed = (laid.children || []).map((c) => ({
      id: c.id,
      x: Math.round(c.x),
      y: Math.round(c.y),
      width: Math.round(c.width),
      height: Math.round(c.height),
    }));
    if (placed.length !== nodes.length || placed.some((p) => !Number.isFinite(p.x) || !Number.isFinite(p.y))) {
      fail(`ELK placed ${placed.length} of ${nodes.length} node(s) — refusing a partial layout`);
      return;
    }
    // LEGALISE. `elk.spacing.nodeNode` governs neighbours in a layer, but two nodes with a routed edge BETWEEN them
    // are separated by that edge's dummy node, and ELK then spaces them by the edge-to-node distance (10px by
    // default) — measured: 'tools.project_index' and 'tools.corpus_check.guards' came out 32px apart in one row once
    // the graph gained a module, below the 72px docgen refuses. Raising the option does not close the class (the
    // next arrangement finds the next dummy), so a deterministic pass guarantees it: within a row, shift a node right
    // until it clears its left neighbour by MIN_GAP. Rows of the layered layout share `y`; nodes in different rows are
    // at least `nodeNodeBetweenLayers - height` apart, which already clears the rule.
    const minGap = Number(input.minGap) || 100;
    const byRow = new Map();
    for (const p of placed) {
      if (!byRow.has(p.y)) byRow.set(p.y, []);
      byRow.get(p.y).push(p);
    }
    let right = Math.round(laid.width || 0);
    for (const row of byRow.values()) {
      row.sort((a, b) => a.x - b.x || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
      for (let i = 1; i < row.length; i++) {
        const need = row[i - 1].x + row[i - 1].width + minGap;
        if (row[i].x < need) row[i].x = need;
      }
      for (const p of row) right = Math.max(right, p.x + p.width);
    }
    placed.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    process.stdout.write(
      JSON.stringify({
        ok: true,
        algorithm: graph.layoutOptions['elk.algorithm'],
        width: right,
        height: Math.round(laid.height || 0),
        nodes: placed,
      }) + '\n',
    );
  } catch (err) {
    fail(`ELK layout failed: ${err.message}`);
  }
}

main();
