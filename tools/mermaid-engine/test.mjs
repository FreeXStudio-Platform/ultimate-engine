#!/usr/bin/env node
// Smoke test: render one real example of each of the 6 supported diagram types to both SVG and
// ASCII, and confirm each output is non-trivial and well-formed. Not a golden-file regression
// suite (beautiful-mermaid ships its own) — this exists to prove THIS engine's wiring works.
import { renderMermaidSVG, renderMermaidASCII } from 'beautiful-mermaid';

const SAMPLES = {
  flowchart: `graph TD\n  A[Start] --> B{Decision}\n  B -->|Yes| C[Action]\n  B -->|No| D[End]`,
  sequence: `sequenceDiagram\n  participant A as Client\n  participant B as Server\n  A->>B: request\n  B-->>A: response`,
  class: `classDiagram\n  class Animal {\n    +String name\n    +makeSound()\n  }\n  Animal <|-- Dog`,
  state: `stateDiagram-v2\n  [*] --> Idle\n  Idle --> Running : start\n  Running --> Idle : stop\n  Running --> [*]`,
  er: `erDiagram\n  CUSTOMER ||--o{ ORDER : places\n  ORDER ||--|{ LINE_ITEM : contains`,
  xychart: `xychart-beta\n  title "Sales"\n  x-axis [jan, feb, mar]\n  y-axis "Revenue" 0 --> 100\n  bar [20, 55, 80]`,
};

let failed = 0;
for (const [type, code] of Object.entries(SAMPLES)) {
  try {
    const svg = renderMermaidSVG(code);
    if (!svg.includes('<svg') || svg.length < 100) throw new Error('SVG output looks empty/malformed');
    const ascii = renderMermaidASCII(code);
    if (!ascii.trim() || ascii.length < 10) throw new Error('ASCII output looks empty');
    console.log(`PASS  ${type.padEnd(10)} svg=${svg.length}B ascii=${ascii.length}B`);
  } catch (err) {
    failed++;
    console.error(`FAIL  ${type.padEnd(10)} ${err instanceof Error ? err.message : err}`);
  }
}

console.log(`\n${Object.keys(SAMPLES).length - failed}/${Object.keys(SAMPLES).length} diagram types render clean`);
process.exit(failed > 0 ? 1 : 0);
