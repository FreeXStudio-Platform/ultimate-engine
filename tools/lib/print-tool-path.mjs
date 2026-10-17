#!/usr/bin/env node
// Tiny CLI wrapper around engine-config.mjs's toolPath() for use from shell scripts that can't
// import ES modules directly (e.g. open.sh). Prints the resolved path (or nothing + exit 1).
import { toolPath } from './engine-config.mjs';

const name = process.argv[2];
const found = name ? toolPath(name) : null;
if (found) {
  process.stdout.write(found + '\n');
  process.exit(0);
} else {
  process.exit(1);
}
