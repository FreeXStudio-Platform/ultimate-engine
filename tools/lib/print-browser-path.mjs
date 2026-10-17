#!/usr/bin/env node
// Tiny CLI wrapper: prints the first EXISTING candidate path for a browser named in
// engine.config.json's "browsers" section (e.g. "chrome", "edge"), for use from shell scripts.
import { existsSync } from 'node:fs';
import { browserCandidates } from './engine-config.mjs';

const name = process.argv[2];
const found = (name ? browserCandidates(name) : []).find((p) => existsSync(p));
if (found) {
  process.stdout.write(found + '\n');
  process.exit(0);
} else {
  process.exit(1);
}
