# Change log

Version numbers are `MAJOR.MINOR.PATCH`. A large change moves MAJOR, a new capability moves MINOR, and fixes move PATCH.
Every version from 2.0.0 has its own download on the [releases page](https://github.com/FreeXStudio-Platform/ultimate-engine/releases).

## 2.1.0 — 28 November 2026 · Stable release

The document system: Ultimate Engine now takes a project from one sentence to a complete, linked set of documents.

### New: documents
- **18 document types**, from the project brief to the runbook, in the order a project writes them, each with its purpose, when it is needed, what it builds on and its required sections ([documents](docs/DOCUMENTS.md)).
- **Document rules** — how documents are written, linked and kept true: documents first, one fact in one place, claims with their proof, stamps that break when the text changes, stable identifiers, adopting an existing project, with a rank order for conflicts ([rules](docs/DOCUMENT_RULES.md)).
- **`ultimate-engine init --idea "…"`** — the first document is the project brief, with your idea in it.
- **`ultimate-engine new TYPE "title"`** — a new document with every section in place, linked to the documents it builds on.
- **`ultimate-engine doc-map`** — one file an AI reads first: every document, its links, what is missing, and the order to read them.
- **Links between documents** — `depends_on`, `covers` and `summary` in the header, checked.
- **Section checks** — `ultimate-engine check` says which required sections are missing or empty.

### New: pin a version in a project or on a build server
- **`ultimate-engine pin`** — one signed release for one project, checked before each use, with no automatic update ([pinning](docs/PINNING.md)).

### Changed
- **License 1.1 and the privacy notice.** The license now allows a pinned copy for a project, says that what `init`, `new` and `doc-map` write is yours, and names `--accept-license` as acceptance; the privacy notice lists what `doc-map` and `pin` write and that neither uses the network. Because the texts changed, an installed 2.0.0 shows them and waits for you to accept before it installs 2.1.0: run `ultimate-engine update`.
- The starter document is now the project brief (`project-brief.md`), replacing `first-document.md`.
- The rule layer that `init` copies is version 1.3.1.

## 2.0.0 — 27 November 2026

The first release of Ultimate Engine as a signed, installable product. It includes everything built since 1.1.2.

### New: the product
- **Installer and menu** — `./install.sh`, then `ultimate-engine`: license acceptance, optional components, `init`, `verify`, `rollback`, `uninstall`.
- **Weekly automatic update** — signed releases only; the previous version is kept; a changed license or privacy notice waits for your acceptance; nothing updates on build servers that set `CI`.
- **Signed downloads** — every release has a signed manifest and checksums ([how to verify](docs/VERIFY.md)).
- **New terms** — the Ultimate Engine Free Use License 1.0, a privacy notice and third-party notices.
- **Drawing commands** — `ultimate-engine chart` and `ultimate-engine mermaid` write into your project.

### New: charts, diagrams and blueprints
- **Chart catalog** — 78 kinds, each drawn in light and dark from a sample and measured in a browser.
- **Skills for AI agents** — one per kind, plus a router from a question to the right kind.
- **Structural views** — C4 model, deployment with trust zones, data flow, decision tree, error-code map, centrality map.
- **Security views** — story strip, before-and-after code pair, severity matrix with incident timeline.
- **Charts** — Gantt, Pareto, waterfall, fan, learning curve, saturation, break-even, tornado.
- **Standalone figures** — draw any document figure alone, in light or dark.
- **Design tokens** — every renderer reads your colours from one token file.

### New: documents and governance
- **Colour-vision check** — simulates three kinds of colour blindness and greyscale; refuses a chart only colour tells apart.
- **Public export** — strips internal markers from what you publish, and refuses to write if one is left.
- **Strict mode** — warnings can block a build before anything is written.
- **Front-matter profiles** — build your own document header format without rewriting documents.
- **Content-hash approval stamps** that survive history changes.
- **All-or-nothing builds** — a refused build leaves nothing half-written.

### Safer
- About forty inputs that drew a confident wrong picture are now refused.
- XML is parsed by one hardened reader; document types and entities are refused.
- The engine does not run programs or Python code found inside the project folder you work in, unless you opt in.
- Reading a downloaded repository (census, document history) switches off the programs its git settings name.
- Dependencies are installed only when each file matches a pinned checksum.
- Dependencies are updated; no known vulnerabilities at release.

### Fixed
- Dark-theme contrast in the severity matrix.
- Several cases where Markdown content was silently dropped.

### If you used 1.1.2
- Python needs `PyYAML` and `defusedxml` (the installer handles this).
- Inputs listed under "Safer" now fail where they used to draw.
- Chart presets named `detector-*` are now `rule-*`.
- A figure that shows data needs its data sources named.
- 1.1.2 was released under Apache-2.0, which still applies to copies obtained then. 2.0.0 uses the new license.

### Known limits
- 42 of 78 kinds write a full per-item machine-readable record today; the others are described by their question, insight, reading guide and links.
- Checked in Chromium; not yet in Firefox, Safari or with screen readers.

### Coming next (plans, not promises)
Automatic layout for structural diagrams · cycle and hub marking in dependency graphs · histogram and density charts ·
standalone images that follow the page's light or dark theme · one annotation layer across charts · small multiples ·
machine-readable records for the remaining kinds.

## What went into 2.0.0, step by step

These development versions came after 1.1.2. They were not released on their own; all of them are part of 2.0.0.

| Version | Date | What it added |
|---|---|---|
| 1.4.0 | 26 November 2026 | The chart catalog, agent skills and the new figure kinds brought together; pinned releases; public export |
| 1.3.2 | 11 November 2026 | Code quality findings cleared |
| 1.3.1 | 11 November 2026 | The safety-gate tests run on Linux |
| 1.3.0 | 10 November 2026 | Story strip, code pair and severity-and-incident figures; public export mode; a release that tests itself before it publishes |
| 1.2.9 | 24 October 2026 | Two high-severity advisories in the chart engine's dependencies fixed; design tokens you can replace |
| 1.2.8 | 21 October 2026 | Content-hash approval stamps; releases you can pin |
| 1.2.7 | 20 October 2026 | One hardened XML reader; two new refusals; clearer reading guides |
| 1.2.6 | 20 October 2026 | The colour-vision check works without the chart catalog |
| 1.2.5 | 20 October 2026 | One agent skill per figure kind, and a router from a question to a kind |
| 1.2.4 | 20 October 2026 | C4, deployment, data-flow, decision-tree, error-map and centrality figures |
| 1.2.3 | 20 October 2026 | Gantt, Pareto, waterfall, fan, learning-curve, saturation, break-even and tornado charts |
| 1.2.2 | 20 October 2026 | The colour-vision check, with patterns so charts do not rely on colour alone |
| 1.2.1 | 20 October 2026 | Front-matter profiles; three cases of dropped Markdown content fixed |
| 1.2.0 | 20 October 2026 | The chart catalog: every figure kind drawn in light and dark and measured |

## Earlier releases: 1.0.0 to 1.1.2

These were released under the Apache License 2.0, which still applies to copies obtained then. They are not offered as downloads here.

| Version | Date | What it added |
|---|---|---|
| 1.1.2 | 16 October 2026 | License, community and security policies, issue templates and automated checks |
| 1.1.1 | 16 October 2026 | The project-census example profile builds as shipped |
| 1.1.0 | 11 October 2026 | Figures numbered, explained, linked to the text and readable by machines; the module explorer; the project census |
| 1.0.1 – 1.0.7 | 31 August – 18 September 2026 | A full audit of 1.0.0, trials documenting a project from nothing, defect fixes and dependency security updates |
| 1.0.0 | 30 August 2026 | The first complete release, independently re-checked, with safety gates that cannot be switched off by accident |

