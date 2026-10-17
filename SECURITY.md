# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

- Use GitHub's **"Report a vulnerability"** button on the repository's *Security* tab (private
  vulnerability reporting), or
- email **admin@freexstudio.com** with a description, the affected version (`PROJECT_VERSION`), and
  steps to reproduce.

You will get an acknowledgement within 5 working days. Please give us a reasonable period to fix the
issue before disclosing it publicly; we will credit you in the changelog unless you prefer otherwise.

## Supported versions

Only the latest release (the newest `vMAJOR.MINOR.PATCH` tag) receives fixes.

## What the engine defends, and what it does not

The document engine sanitizes what it *exports* (secret, PII and path leak gates), and the repository
ships a git "moat" (pre-commit / pre-push hooks plus a server-side secret scan). The honest bounds of
that protection — including what a client-side hook cannot stop — are written down in
[`docs/process/THREAT_MODEL.md`](docs/process/THREAT_MODEL.md); read it before relying on a gate.
Supply-chain posture for the chart engine's npm dependencies is in
[`tools/visual-engine/SECURITY_POLICY.md`](tools/visual-engine/SECURITY_POLICY.md).
