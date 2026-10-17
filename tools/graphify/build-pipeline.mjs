#!/usr/bin/env node
/* tools/graphify/build-pipeline.mjs — the PIPELINE graph (model #4): a curated stage-flow diagram.
 *
 * Unlike deps (parsed from real code) this is a CURATED flow — one project's own narrative of how
 * work moves through it, step by step, each step grounded in a real module. The steps themselves
 * are DATA (see pipeline.example.json), not hardcoded here, so describing your own pipeline means
 * authoring your own steps file (same shape) and pointing engine.config.json's
 * graphify.pipelineStepsFile at it — never editing this script.
 * Writes graphify-out/{pipeline.json, pipeline-data.js, build.log}. LOCAL-only. Usage: node tools/graphify/build-pipeline.mjs
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { graphifyConfig } from '../lib/engine-config.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, '..', '..', 'graphify-out');

// pipelineStepsFile config value: null -> bundled worked example; otherwise a host-project-authored
// file in the same {laneColors, steps} shape (steps: [id, label, module, lane, [downstream ids]]).
const stepsFilePath = graphifyConfig().pipelineStepsFile || join(HERE, 'pipeline.example.json');
const { laneColors: LANEC, steps: STEPS } = JSON.parse(readFileSync(stepsFilePath, 'utf8'));

const nodes = STEPS.map(([id, label, mod, lane]) => ({ id, label, type:'step', lane, module: mod, color: LANEC[lane] || '#fb7185' }));
const links = STEPS.flatMap(([id,,,, outs]) => outs.map(t => ({ source: id, target: t, kind: 'flows-to' })));

try { if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true }); } catch {}
const nodeLink = { directed: true, multigraph: false, graph: { name: 'pipeline' }, nodes, links };
try { writeFileSync(join(OUT, 'pipeline.json'), JSON.stringify(nodeLink, null, 2)); } catch {}
try { writeFileSync(join(OUT, 'pipeline-data.js'), 'window.GRAPH = ' + JSON.stringify({ meta:{ name:'pipeline' }, nodes, links }) + ';\n'); } catch {}
try { writeFileSync(join(OUT, 'build.log'), `${new Date().toISOString()} graph=pipeline nodes=${nodes.length} links=${links.length} status=ok\n`, { flag: 'a' }); } catch {}
console.log(`[/pipeline] ${nodes.length} steps · ${links.length} flows`);
console.log(`  flow: ${STEPS.map(s => s[0]).join(' → ')}`);
console.log(`  view: graph-view.html?g=pipeline   ·   query (separate tool, see README): graphify query "<q>" --graph graphify-out/pipeline.json`);
