# doc-visuals MCP facade

Constrained MCP wrapper over the direct ECharts adapter. See
`approved-server.json` (selection decision + rejected candidates),
`tool-schema-snapshot.json` (frozen tool contracts),
`capability-test-results.json` (live handshake/render/refusal evidence) and
`fallback-plan.md` (the mandatory non-MCP path).

Run: `npm run mcp` (stdio). **No repo-root `.mcp.json` ships with this engine, and that is
deliberate** — an MCP registration names a host project's absolute paths, so the engine cannot
carry one and stay domain-neutral. A host wires it up with `mcp/config.example.json`. This line
read *"registered project-wide via repo-root `.mcp.json`"* until 2026-08-22 (`P6-10`), which
described the source project rather than this package.
Restricted-classification jobs are always refused here; the tool surface is
the seven-tool `visual_*` set (see `tool-schema-snapshot.json` for the frozen
contract) — nothing else is exposed.
