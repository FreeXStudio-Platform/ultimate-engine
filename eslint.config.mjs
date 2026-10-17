// Flat ESLint config (ESLint 9+) for this repo's ~2.5k lines of Node/mjs tooling code, which had
// no linter of any kind before P8-051 — `git ls-files '*.mjs' '*.js'` (minus node_modules and
// vendored *.min.js) turned up zero config files anywhere in the tree. Scope is deliberately the
// hand-written surface only: vendored third-party bundles (force-graph, 3d-force-graph) are
// excluded, matching the same "vendored, not audited" treatment they already get everywhere else
// (see engine.config.json security._readme).
//
// Measured baseline lives in tools/health/lint_baseline.json alongside ruff/mypy — see that
// file's _readme for why an unmeasured number is decoration, not a gate. This config produces
// the count SUITE-04 is expected to compare against; wiring SUITE-04 itself to invoke it is
// tracked separately (tools/health/checks.py is outside this lane's owned paths).
export default [
  {
    ignores: [
      "node_modules/**",
      "**/*.min.js",
      "tools/graphify/vendor/**",
      "vault-graph-engine/**",
      "graphify-out/**",
      "tools/visual-engine/renders/**",
      ".docgen/**",
      ".health/**",
    ],
  },
  {
    files: ["**/*.mjs", "**/*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        process: "readonly",
        console: "readonly",
        Buffer: "readonly",
        __dirname: "readonly",
        __filename: "readonly",
        URL: "readonly",
        fetch: "readonly",
        setTimeout: "readonly",
        setInterval: "readonly",
        clearTimeout: "readonly",
        clearInterval: "readonly",
        structuredClone: "readonly",
        performance: "readonly",
      },
    },
    rules: {
      // Correctness — the classes of bug this repo's own docs cite as real incidents
      // (an undefined identifier reference, e.g. the `RoutedEdge` fix cited in
      // lint_baseline.json's ruff note, is exactly what no-undef exists to catch).
      "no-undef": "error",
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "no-unreachable": "error",
      "no-dupe-keys": "error",
      "no-dupe-args": "error",
      "no-fallthrough": "error",
      "no-const-assign": "error",
      "no-import-assign": "error",
      "no-self-compare": "error",
      "no-template-curly-in-string": "warn",
      "use-isnan": "error",
      "valid-typeof": "error",
      "eqeqeq": ["error", "smart"],
      "no-var": "error",
      "prefer-const": "error",
    },
  },
];
