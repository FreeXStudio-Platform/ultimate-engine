# Vendored libraries — provenance (verify before trusting)
| file | source (pinned) | size | sha384 |
|------|------------------|------|--------|
| force-graph.min.js | https://unpkg.com/force-graph@1/dist/force-graph.min.js |   177599 | `1e6e86a50713348e55a868064bb94bc531ad105731bbf90e555d01ee8cc8651bbd6e5595be282fe61b6d250676a99998` |
| 3d-force-graph.min.js | https://unpkg.com/3d-force-graph@1.80.0/dist/3d-force-graph.min.js | 1313897 | `63b6c2d8f04abbcba3c6dbe8e7e67ad4e786752551cc5b185812b88b97672ff53a6850d3a1d93ad6a3949137c89dac52` |

Downloaded 2026-06-29 (force-graph.min.js) and 2026-08-18 (3d-force-graph.min.js).
Vendored so the dashboard loads NO runtime CDN script (supply-chain control + offline). To update:
re-download the pinned URL, diff the size/sha, review, then bump this file.

**3d-force-graph.min.js fixes a real gap, not a cosmetic addition**: `graph-view.html`'s 3D toggle
previously injected `<script src="https://unpkg.com/3d-force-graph@1">` at click-time — a live,
unpinned, unchecksummed runtime CDN fetch that directly contradicted this file's own "no runtime
CDN script" rationale for the 2D library, and failed silently with no network. It is now vendored
here on the same terms as force-graph.min.js. License: MIT (github.com/vasturiano/3d-force-graph).
Bundles three.js as a transitive dependency (peer range `>=0.179 <1`) — this is why the file is
~1.3MB versus the 2D library's ~174KB; that size delta is the real, load-bearing cost of true WebGL
3D rendering and was accepted deliberately rather than left as an unvendored CDN shortcut.
