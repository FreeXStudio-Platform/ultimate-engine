# Third-party notices

Ultimate Engine includes or installs the following components. Each stays under its own license, and those licenses
apply to those components in place of the Ultimate Engine license.

## Included in the package

| Component | Use | License |
|---|---|---|
| Inter, JetBrains Mono, Space Grotesk typefaces | Embedded in pages | SIL Open Font License 1.1 (full text: `tools/docgen/assets/fonts/LICENSE-OFL.txt`) |
| force-graph and 3d-force-graph, by Vasco Asturiano | Graph views (`tools/graphify/vendor/`) | MIT License |
| Country boundaries (`world-countries-110m.geojson`) | Maps; derived from Natural Earth (public domain) as redistributed by the D3 Graph Gallery | Public domain data; MIT License for the redistribution |

### MIT License (for the components marked MIT above)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy,
modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice
shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY
OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Installed on your computer when you install (not part of the package)

Python: **PyYAML** (MIT), **defusedxml** (Python Software Foundation License).

Chart component (npm): **Apache ECharts** (Apache-2.0), **@resvg/resvg-js** (MPL-2.0), **@modelcontextprotocol/sdk** (MIT),
**zod** (MIT), and their dependencies under their own licenses.

Mermaid component (npm): **beautiful-mermaid** (MIT) and its dependencies, including **elkjs** (EPL-2.0).

Optional, installed by you: **WeasyPrint** (BSD-3-Clause) for PDF export.

The exact versions are pinned in the package's lock files, and each installed package carries its own license file.
