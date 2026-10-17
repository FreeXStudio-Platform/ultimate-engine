<!-- title: CHANGELOG -->
<!-- record: append-only -->
# CHANGELOG — build-work versioning

**What this file versions:** the **build work on this engine** — what was done, when, to which file
and section, at which project version. It is the record an operator reads to answer *"where are we,
and what landed?"* without reading git.

> ## ⚠ THIS IS NOT THE DOCUMENT-SYSTEM VERSION
>
> Two versioning systems exist in this repository and they must never be confused:
>
> | | `CHANGELOG.md` + `PROJECT_VERSION` (**this file**) | `docs/design/doc-system/VERSION.json` |
> |---|---|---|
> | Versions | The **build work** on the engine | The **locked rulebook's** content |
> | Bumped when | A phase or fix lands | A locked rule file's bytes change |
> | Read by | Humans, to know where the project stands | `validate_doc_system.py`, mechanically |
> | Failure if wrong | A confused operator | The **hash-gate blocks the build** (RULEBOOK L9) |
>
> Editing one never implies editing the other. A rule change bumps **both** — the rulebook hash
> because its bytes changed, and this changelog because build work happened.

## Version scheme

`MAJOR.MINOR.PATCH`, tied to `docs/plan/BUILD_PLAN.md`'s seven phases:

- **MINOR** — one completed phase (Phase 1 → `0.2.0`, Phase 2 → `0.3.0`, … Phase 7 → `1.0.0`); after `1.0.0` there is no next phase, and a MINOR marks an additive capability line merged in as a unit (`1.1.0`: the figure system, the module explorer and the project census)
- **PATCH** — fixes, corrections, or process work inside a phase
- **MAJOR** — `1.0.0` on Phase 7 (harden + stamp); reserved thereafter for a breaking engine change

The current version is recorded in `PROJECT_VERSION` at the repo root, single line, no prefix.

---

## [1.1.2] — 2026-10-16 · Ready to be public: licence, policies, templates, CI and a clean text (`OG-310`)

An audit for publication found the engine working and the repository not ready to be seen. Added: the **Apache-2.0** `LICENSE` and a `NOTICE`
(FreeXStudio, with the bundled third-party material named — typefaces under the OFL, force-graph under MIT, country boundaries from Natural Earth);
`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` and `CITATION.cff`; issue forms and a pull-request template; `CODEOWNERS`; weekly grouped
`dependabot.yml`; and `ci.yml`, which runs `python3 -m tools.health` on non-draft pull requests (additive: it is not a required check until it has run
green). The README now opens with what the engine is, why it exists and a quick start, and names its maker and website. The three manifests declare
`Apache-2.0` (their lock roots and both `VERSION_LOCK.json` attestations re-derived; no package changed). The operating-system username and workspace
paths that two documents carried are replaced by placeholders; `PROVENANCE.md`'s stamp is therefore declared NEEDS RE-HARDENING in `HANDOFF.md`.

**Found by the first CI run on GitHub (`OG-311`):** `SUITE-04` looked for `uvx` before judging the lint baseline, so on a machine without it a raised ceiling or a
narrowed invocation reported SKIP, not red. Both rules are now judged first; only the measurement is skipped. The old-release differential in
`test_front_matter_token.py` reads a committed fixture when its commit is not in the clone (a published snapshot has no such commit).

**Scanned and clean:** gitleaks over all 188 commits (no findings); no secrets, tokens, keys, e-mail addresses or IP addresses in the current files.
**Not clean, and said so:** seven commits carry a personal address in their metadata. History cannot drop that without being rewritten, so the public
repository is created from a snapshot of this tree rather than from this history.

**Where it will live:** the public repository is `FreeXStudio-Platform/ultimate-engine` (the FreeXStudio organization), created private and filled from a two-commit
snapshot of this release; it stays private until the owner says go. The repository's own links already point there.

Project version `1.1.1` → `1.1.2`. Blueprint rebuilt last.

## [1.1.1] — 2026-10-16 · The census example profile builds in a plain engine tree (`OG-308`, `OG-309`)

Found by comparing the merged engine with the downstream copy it came from, file by file and by building the same inputs with both: of 417 shared
files 367 are byte-identical, and every one of the 50 that differ is a comment, a message, a fixture, a dependency version or a record — no engine
code differs. The one defect that comparison surfaced is in a shipped example, identical in both: `examples/census.profile.example.json` named
`report.classification: "internal"`, a tier the engine's own law (public, confidential, secret) does not have, so a plain tree read it as `secret`
and refused the report (`OG-308`). The example is now `public` / `web` / export-allowed and builds the census on the engine's own tree; a test pins it
to a tier the engine accepts, red-first. A redundant `import re` that a downstream review flagged in the same test file is removed (`OG-309`).

Project version `1.1.0` → `1.1.1`. Python tests 909 → 910 (`_PYTEST_HARD_FLOOR` 728 still holds: 80% of 910 is 728). Blueprint rebuilt last.

## [1.1.0] — 2026-10-11 · A downstream copy's figure system, module explorer and project census merged — and what merging them showed

A downstream copy of this engine forked at `1.0.5`, merged this repository's `1.0.6` (`OG-249`) on 2026-09-07, and then built for a month:
a figure system (every figure scoped, numbered, explained and linked to the text, and readable by a machine), a zoomable module explorer,
a project census sub-engine, a size standard, reference cards, dependency and lint-ceiling work, and a views-registry fix for a host that
owns its own `tools/project_index` — `OG-250` … `OG-303`, builds `1.0.7` … `1.0.14` of the copy, release tag `1.0.21` in the copy's numbering.
**This entry is the merge of that release into `master`.** Nothing was re-implemented here: the copy's tree arrives as it was built, and
everything below is the decisions the merge itself required and what it found. The copy's own entries follow unchanged apart from
de-branding (below), each still under the number it carried.

### The version, and the collision

Both repositories called their own build `1.0.7`, with different content. The new version is **`1.1.0`**: above both lines, and a MINOR because
the copy's builds reach `1.0.14`, so no patch number is free of a collision and what arrives is an additive capability line, not a fix
(the scheme above is amended to say so; no entry body was edited).

| build | origin | where it is in this file |
|---|---|---|
| `1.0.7` | this repository — nine Dependabot alerts | `[1.0.7]`, untouched |
| `1.0.7` | the copy — the views registry in a host that owns `tools/project_index` | `[1.0.7+copy]` — the one heading re-labelled (semver build metadata), so there is no second `[1.0.7]` |
| `1.0.8` … `1.0.14` | the copy — figure system, review findings, explorer, census | `[1.0.8]` … `[1.0.14]`, same numbers, same text |
| `1.1.0` | this merge | this entry |

Two numbers are easy to confuse in the imported entries: a build number (`1.0.8` … `1.0.14`) and the copy's *release tag* number (`1.0.15` …
`1.0.21`), which runs ahead of it; the imported entries for `1.0.9` … `1.0.14` state theirs. "Base `1.0.12`" in imported comments and test names means the
engine release a host was pinned to before the front-matter token fix — the copy's tag number — not a build of this repository.

### What the merge was, measured

- **The briefing's forecast was wrong, and the merge showed why.** It predicted 18 conflicting files, derived from `185725a1` as the shared
  base. The merge base is `a0a09f0` — this repository's own `1.0.6`, which the copy had already merged — so **9** files conflicted, not 18, and
  the four code files the briefing told the reviewer to three-way-review (`tools/blueprint/completeness.py`, the `identity` and `stamps` guards,
  `test_git_paths_from_scanned_root.py`) **auto-merged**. They were reviewed anyway: every line `OG-249` (`34bb23c`) added is present in the
  merged files (9, 1, 1 and 112 of 113 lines; the 113th is the copy's `head, body` → `_head, _body` lint rename in the same test), no removed
  line came back, and `OG-249`'s retained counter-examples pass beside the copy's.
- **The nine conflicts, and the rule applied to each.** `PROJECT_VERSION` → `1.1.0`. `CHANGELOG.md` — both histories kept, interleaved by date, every
  entry once. `HANDOFF.md`, `docs/plan/START_NEXT_SESSION.md`, `docs/process/SESSION_STATE.md` — per-session records, rewritten for the merged
  state, not merged. `blueprint/SYSTEM.json` and `SYSTEM.md` — derived; the copy's taken to finish the merge, then everything regenerated last.
  `tools/visual-engine/package-lock.json` and `VERSION_LOCK.json` — see the next item. `docs/process/OPEN_GATES.md` merged without a conflict and
  holds no duplicate key; the copy's `OG-250` … `OG-303` are unique in it.
- **Dependencies: the higher version of each.** The copy's lock carries `proxy-addr` 2.0.8 (a CRITICAL advisory), `ip-address` 10.7.3, `fast-uri` 3.1.8
  and the direct pin `@modelcontextprotocol/sdk` 1.32.1, and the root lint toolchain's `brace-expansion` 5.0.12; this repository's carried `hono`
  4.13.8, which was *above* the copy's 4.13.7. The copy's lock was taken and `npm update hono` run — one package changed (version, resolved,
  integrity), to 4.13.13. `npm audit` reads **0** in each of the three tracked lockfiles (root, `tools/mermaid-engine`, `tools/visual-engine`), and
  the `visual-engine` attestation was re-derived after the diff was read.
- **Not imported:** the copy's file describing itself and its hand-over briefing for this merge. Both describe the copy, not the engine, and the
  briefing's measured numbers were the ones just shown to be off. A copy merging this `master` back will see them as deleted and should restore
  its own description file.
- **De-branded:** the imported comments, docstrings, test names, fixtures and changelog text no longer name the host project or carry its
  register ids; what was measured is kept. Runner labels in the CI-cost fixtures became neutral (`pool-a`, `proj-a`). The census suite's own
  guard that its files name no project is assembled from fragments so that the test file stays name-free too.

### Two defects the merge found in the imported tests (`OG-304`, `OG-305`)

A differential that named its "before" release by a tag no clone of this repository has, pinned now to commit `185725a1` with the five readers'
patterns shown byte-identical at the old release and at that commit; and a test that read one named project's checkout from a hard-coded path,
now environment-driven (`ENGINE_TEST_HOST_ROOT` / `ENGINE_TEST_HOST_DOCS`) and skipped, with that cause, when unset.

### Where the release lives

The engine stays in this repository. This merge is tagged `v1.1.0` here (`v` + `PROJECT_VERSION`), and a product that vendors the engine takes
that tag from this repository and updates its own copy. A step in the copy's briefing that would also have published the engine to a second
repository was not carried out: the operator decided the engine has one home. The two scripts written for that step were removed again before
this landed; the register rows and fixes found along the way (`OG-304` … `OG-307`) are unaffected.

### Verification

All of it on the final tree, by the commands the briefing names; the machine was NOT quiet (other work on it held the load average between 7 and 167), so
every timing-sensitive result below is a pass inside its limit, not a measurement of speed.

- **`python3 -m tools.health --full`** → **38 passed, 0 failed, 0 skipped of 38** on commit `36fafef` (clean tree, 887 s, with `PLAYWRIGHT_MODULE_DIR` set so the browser tests ran; 909 Python tests ran, 1 skipped by design, hard floor 728). The first run of the merged tree read 35 of 38 and named three things, each a consequence of the
  merge: the state documents' version claims (`CONS-08`), a `mypy` error the latest release saw in an imported test (`SUITE-04`, `OG-307`), and the
  moat harness's clean-push control, which fails whenever any other check is red (`SUITE-06`, "the moat is NOT implicated"). A later run read 37 of 38:
  the corpus-count probe, which requires every live document that writes `<n> guards` to be named, found this record's own wording.
- **`python3 -m unittest discover -s tools/tests -t .`** → **909 ran**, 0 failures. **Skips:** 1 — the host-documents test, which needs
  `ENGINE_TEST_HOST_ROOT` (`OG-305`); without Playwright 3 more skip, with the cause printed. The charter's document count went 78 → 76 because two of the
  copy's files were not imported (`docs/CHARTER.md`).
- **The three real-browser tests**, which skip where Playwright is absent, were RUN: Playwright 1.63.0 against the cached Chromium 1243
  (`PLAYWRIGHT_MODULE_DIR=<dir> python3 -m unittest tools.tests.test_figure_runtime_browser tools.tests.test_explorer_browser tools.tests.test_figure_size_standard`)
  → 24 tests, OK, none skipped.
- **The chart engine** (`tools/visual-engine`, `npm ci` first): `npm test` **86 of 86**, goldens and themes reproduced byte-for-byte and untouched in
  the tree; then `npm run simulate` **22 of 22**, which rewrote only two evidence records (`OG-306`, not a rendering change).
  `tools/mermaid-engine`: 6 of 6 diagram types.
- **`python3 -m tools.corpus_check`** → 11 of 11 guards, 0 findings. **`python3 -m tools.blueprint build` then `verify`** → clean, run last;
  `blueprint layout` wrote 0 placement findings.
- **Dependencies:** `npm audit` 0 in each of the three tracked lockfiles; `uvx ruff check tools/` 0 and `uvx mypy --strict tools/` 0.
- **Not verified:** Firefox, Safari, a screen reader, the PNG export of the new SVGs, and any independent adjudication of the merge — it is
  implementer-verified, the residue `OG-209` already records for earlier work.

## [1.0.14] — 2026-10-10 · What the host's review of the vendoring PR found (`OG-300` … `OG-303`)

The consumer's pull request that vendored `1.0.13` was read by two automated reviewers (a code reviewer and CodeQL's quality pass). The engine's own 900 tests and its health had
been green; three of what they raised were real. All are fixed here, in the copy, and the host re-vendors the tag.

### Fixed

* **A stray entry in an explorer's `edges`, `statuses` or `kinds` was dropped silently** (`OG-300`): a schema typo built a diagram that looked complete and was missing a
  connection. Every entry must be an object; one that is not is refused with its list and position.
* **A census of a repository with no live, unmarked document could not be built** (`OG-301`): the report always named the age heat map, which is only drawn when there is
  a live document to age, so the document generator refused the report. A directive is now written only for a figure that was built.
* **A graph name too long for its side swallowed the canvas** (`OG-302`): on a 300 px graph one 100-character name pushed the margins past the canvas and left a negative plotting
  box with every coordinate reversed. A side now takes at most 38% of the canvas, a name that does not fit is truncated with an ellipsis (the full name stays in the tooltip and the
  marks table), and a canvas too small for any box is refused. A name that fits is drawn exactly as before (the goldens are unchanged).
* **Four code-quality notes** (`OG-303`): an unused helper in the explorer runtime, a redundant-looking write in the browser check (it is deliberate: assigning an invalid colour is
  ignored, so the reset to black is what makes an invalid value readable; it is now a named helper), a mixed import style and an imprecise assertion in two tests.

### Derived work

The health floor for the Python suite raised to 728 (909 tests, counted on the final tree); blueprint and layout rebuilt last. Project version `1.0.13` → `1.0.14`; the copy's release tag number
is `1.0.21`.

## [1.0.13] — 2026-10-10 · The project census, and what drawing it found (`OG-292` … `OG-299`)

The operator asked how many documents the project holds, how many are updated or outdated, how many are crossed out, how many are stamped as a source of
truth, whether the work follows them and how complete the documentation system is — answered as a report with several different kinds of figure, built with
the engine, and made a feature of the engine for any project.

### Added

* **`tools/census`** (`docs/design/PROJECT_CENSUS.md`, `skills/project-census/SKILL.md`, `examples/census.profile.example.json`, `OG-295`): one deterministic
  measurement (`census/1`) of a project's documentation from its own git tree — documents, updated and outdated (live, unmarked, within the window), crossed
  out (archived, marked in the header, deleted; a rename is followed, not counted as a removal), stamped and authoritative, stamp state judged on the body with the
  stamp lines removed from both sides (VALID, DRIFTED, INVALIDATED, UNVERIFIABLE, UNRESOLVED), whether the work cites them, completeness as covered-of-total per
  dimension with **no composite number** — plus the Python code hierarchy read with `ast`. A profile carries a project's own conventions (unknown keys refused).
  `python3 -m tools.census measure | report | inventory`.
* **A report of varied figures and two explorers**: a flow (Sankey), a stacked bar, a heat map, a bar, a donut, a radar, a timeline, an XY chart, an ER diagram, a
  layered diagram, the documentation explorer and the code explorer — each chosen once for the question it answers.
* **`inventory`**: how many figure models the engine can draw, counted from its own registries (46 named models: 15 native figures plus the explorer, 24 chart-engine
  visuals, 6 Mermaid types; 28 distinct kinds once variants and names two engines share are counted once).

### Fixed (found by looking at the first real census report)

* **A stacked bar drew three names under twelve bars** (`OG-292`): every category name is shown, tilted and cut when it must be.
* **A radar cut long axis names off at the canvas edge; a layered diagram drew planes as wide as the whole figure's node count and ran labels through their boxes**
  (`OG-293`): labels wrap and fit, planes span their own columns, nodes are opaque; a radar whose names already fit is byte-identical.
* **A Mermaid ER diagram silently dropped relationships** (`OG-294`): six declared, three drawn. The bridge now refuses a diagram that drew fewer than it declares.
* **A Mermaid figure could not declare its data sources** (`OG-296`): an XY chart or a counted ER diagram could only be refused by the provenance gate; the figure now takes `data_sources` like every other data-carrying kind.
* **The explorer said "calls / called by" about documents** (`OG-297`): the arrow legend and the reading guide were written for code. A spec now carries an optional
  `arrows` object (`out`, `in`, `out_detail`, `in_detail`); the documentation explorer says "cites", the code explorer "imports", and a misspelt key is refused.
* **A plane's name in a layered diagram was struck through by the connectors that cross it** (`OG-298`): headings are drawn after the connectors with a
  paper-coloured knockout, nodes stay on top.
* **Two limits of the Mermaid XY chart, recorded and not patched** (`OG-299`, open): its renderer is a third-party library that names the series "Bar 1" and "Line 1"
  and draws the line as a smoothed curve that can dip below zero between points. The census report says so under the figure.

### Derived work

Blueprint and ELK layout rebuilt last (the new module claimed by its own container); the health floor for the Python suite raised to 725 (906 tests, counted on the final tree). Project version `1.0.12` → `1.0.13`; the
The copy's release tag number is `1.0.20`.

## [1.0.12] — 2026-10-10 · The module explorer (`OG-285` … `OG-291`)

The operator's second review of the report asked for one more thing that is not a fix: the module section, three static pictures of a
hierarchy of three hundred parts, should be explorable — start zoomed out, click a part and glide into it, see what it connects to and
the documents about it, go back out and into another.

### Added

* **A figure kind `explorer`** (`OG-285`, `tools/docgen/explorer.py`, `assets/explorer_runtime.js`, `docs/design/FIGURE_SYSTEM.md` §13):
  a zoomable treemap of a whole hierarchy (at most 700 parts, depth 5) with a panel, a reader and hover arrows. A click glides the
  camera into the part (560 ms; a part in another branch zooms out to the common ancestor and in again); the panel says what the part is,
  its size and colour state, what it calls, who calls it (each name a button that takes you there), its facts and lists, and the
  documents about it, which open in a reader laid over the map; hovering or focusing a part draws its connections to its siblings
  (blue: it calls, pink: it is called by). Tab, arrows, Enter, Escape, Backspace and Home work; `prefers-reduced-motion` makes every
  glide a cut. Connections are exact (an edge between two packages is listed on those packages), documents are structured blocks with
  every string escaped, and the runtime builds DOM with `createElement` / `textContent` only.
* **Without script, in print and for a machine it loses nothing**: the same content is a nested `<details>` outline (a test compares it
  with the spec) and the document's blueprint JSON carries the hierarchy.
* **The framed block** (`svgwrap--block`): a figure that is not a picture takes the column with no padding or frame of its own.

### Fixed (found while building it, by the browser check and a screenshot)

* **The world SVG's box followed the camera** (`OG-286`): `.svgwrap svg { height: auto }` out-ranks a class, so after the first zoom
  every tile was drawn 217 px too tall and every label sat apart from its tile.
* **CSS escapes written inside a Python string became control characters** (`OG-287`).
* **A click took the keyboard focus with it** (`OG-288`): the clicked tile is hidden by the zoom and Escape stopped working.
* **A long unbreakable name pushed a phone sideways** (`OG-289`): a figure's marks table keeps two columns on one line; below 640 px they may wrap.
* **The engine's tests and probes committed to the real repository from a linked worktree's hook** (`OG-291`): `GIT_DIR` inherited from the hook made every scratch `git init` the real repository; `tools/gitenv.py` scrubs the repository-local variables on import of `tools.health`, `tools.tests` and `tools.draft`, pinned by a test that runs the real draft gate under a hostile `GIT_DIR`.
* **A name was cut inside a word on a narrow tile** (`OG-290`): found on the report's real hierarchy; each label is now measured after it is placed and shrunk, reduced or left out.

### Derived work

`FIGURE_SYSTEM.md` §13 and a second declared exception to the hover law (the explorer's two arrow hues, §4); 39 Python tests and a
53-check Chromium script; the blueprint rebuilt last. Project version `1.0.11` → `1.0.12`; the copy's release tag number is `1.0.19`.

## [1.0.11] — 2026-10-10 · The operator's second review of the report: sizes, names, directions, numbers (`OG-277` … `OG-284`)

The report was rebuilt with `1.0.10` and read again by its operator, figure by figure, against screenshots of the build before. Ten
points came back; seven of them are defects in the engine, not in the report. The size one is the root of four of them.

### Fixed

* **A native diagram was shown at the width of the column** (`OG-277`, HIGH): a bare `viewBox` has no size of its own, so a
  960 x 740 flow was drawn at 1150 x 886 (x1.2) — taller than a laptop screen — where the build before drew it at x0.61. **The figure
  size standard** (`FS-1` … `FS-5`, `docs/design/FIGURE_SYSTEM.md` §12) decides every figure's size from constants in
  `figure_support.py`: never above its design size times its enlargement ceiling, a landscape figure fits `min(82vh, 700px)` but
  never shrinks below 80%, a tall figure is exempt, nothing is wider than 1150 px. A 960 x 740 flow is now 908 x 700; the approved
  sequence (1150 x 690) and every 620-px chart are unchanged. Checked in real Chromium at five viewports against the standard
  re-derived from its constants (fails with `want 908 got 1150` against the previous stylesheet).
* **Node-and-edge diagrams are back on the blueprint grid, faded** (`OG-277`): 22 px cells in 6% of the page ink; charts, sequence
  diagrams and foreign engines stay plain. Step numbers are 34 px across (was 24) with a 17 px digit.
* **A native diagram's title was black on a dark page** (`OG-277`): the SVG `<text>` had no fill and the stylesheet never named it.
* **An edge label was struck through by its own line** (`OG-284`): the label is now cut out of the line (a ground-coloured stroke
  painted under the glyphs) — the defect `FIGURE_SYSTEM.md` §11 had recorded as "needs a collision-aware placement" (the cut needs
  none).
* **Treemap names sat in a corner and broke inside words** (`OG-278`): names are centred in the tile, in the display face, bold, and
  fitted on the **live layout** (one deterministic second pass reads every tile's real size): the largest size that fits, wrapped at a
  space, underscore or hyphen, shrunk before it is cut, shortened only when most of it survives, left out when almost none does (the
  tooltip names every tile); a big tile earns a bigger name; a group's header takes two lines when the group is tall enough.
* **A graph's names overlapped its lines, its nodes were ellipses and its lines were one colour** (`OG-279`, `OG-280`): the builder
  lays the ring out itself, in the proportions of its box (ECharts' view fit stretches x and y independently and squashed every
  symbol), so each name faces away from the ring (right half right, left half left, a pole above or below); a graph asking for a layout
  the schema does not declare (`force`) is refused instead of reaching ECharts; each link carries its source node's colour (ECharts 6
  ignores `lineStyle.color: "source"`: measured, one stroke on 34 of 34 edges).
* **A radar's web vanished** (`OG-281`): it was made quiet in `1.0.9` and was now invisible; rings and spokes sit at about half the ink
  with a hair of banding, and a test keeps them in a band that is seen yet quieter than the data.
* **A boxplot was a hollow outline** (`OG-282`): candles are lit bodies (a gradient from the series blue half-way toward the palette
  green) in a lighter rim.
* **A number in a document said nothing** (`OG-283`): every back-link read `↑ 8` because `8. Modules` was cut at its first `". "`.
  A leading ordinal is now kept whole (`↑ 8 · Modules`).

### Added

* **Direction colours in a graph** (`OG-280`): while a node is focused, the lines leaving it are blue, the lines entering it pink and a
  two-way link white (darker values in the light theme); the CSS-only fallback carries the same rules. This is the **one declared
  exception to the hover law** (`FIGURE_SYSTEM.md` §4): the hue is the information, the palette is no module's status colour, and a test
  keeps it so.
* **An isolated node is outlined in dashes** and its tooltip says "isolated: no connection in the data" (`OG-280`); a node may carry a
  `note` that travels with it into the tooltip and the marks table. (In the report, `configuration` draws with no line: the data lists
  no allowed edge into it although 26 packages import it — an omission in the source, now visible in the picture.)
* **Reference cards** (`OG-283`): every number that points somewhere (`Fig. N`, the number before a heading, a back-link, a section
  chip) carries `data-ref`; hover or focus it and a card says what it is — title, kind, section, the question it answers — and which
  documents it draws on, read from a small JSON index the page embeds (`doc_index.py`, `#ve-doc-index`). A document with no figures
  is unchanged.

### Derived work

All 14 chart goldens re-baselined and classified (`tools/visual-engine/renders/diffs/2026-10-10-figure-refinements.md`: twelve gain one
rule, the two graphs change as above); the blueprint rebuilt last; the health floor for the Python suite raised to 645 (807 tests).
Project version `1.0.10` → `1.0.11`; the copy's release tag number is `1.0.18`.

## [1.0.10] — 2026-10-10 · The consumer's code review found four more (`OG-273` … `OG-276`)

`1.0.9` went to a consumer as a pull request and the reviewer of that pull request — an automated code review reading the vendored
figure code cold — raised four findings. Each was checked against the code, not taken on trust: three were real and one was not a
defect on the path that ships (and is now pinned).

### Fixed

* **A node's `tone` is a closed vocabulary** (`OG-273`, P1): it was printed into an SVG `class` attribute as free text, so a crafted
  spec closed the attribute and added its own — `tone: 'x" onclick="alert(1)'` produced a live `onclick`. Reproduced on the previous
  tag. `glyphs.validate_tone` allows `blue`, `gold`, `green`, `red`, `bronze`, `steel`, `none` and the empty string; the glyph sink
  refuses anything else and the spec reader refuses it up front, naming the node.
* **A native heatmap's per-cell ink reaches the screen** (`OG-275`, P2): the chosen ink was a `fill` attribute, and the stylesheet's
  `.chart-value{fill:currentColor}` outranks any attribute, so every value was painted the page ink. Reproduced in a real browser
  (all four values of a two-tone grid computed to `rgb(11, 14, 20)`); the ink now also rides in the element's `style`.
* **Two figures cannot share one DOM id** (`OG-276`, P2): `A_B` and `A-B` both became `fig-a-b`. The outline scan refuses the second,
  naming both ids and the DOM id they collide on.

### Hardened

* **A boxplot row is read as five statistics** (`OG-274`, P1 as raised): the reviewer expected the model to hand back
  `[min, q1, median, q3, max]` and feared a six-field read would shift every statistic. Probed on echarts 6.1.0 the live model hands
  back `[categoryIndex, min, q1, median, q3, max]`, so the read was right on the shipped path; it was also unpinned. `boxStats` now
  takes the last five numbers and the category is the row's own position, with a real-render test and a unit test of both shapes.

### Derived work

No golden changed (65/65). The blueprint was rebuilt last. The health floor for the Python suite is raised to 616 (770 tests).
Project version `1.0.9` → `1.0.10`; the copy's release tag number is `1.0.17`.

## [1.0.9] — 2026-10-10 · The first look at a rebuilt report found four more (`OG-269` … `OG-272`)

The figure system of 1.0.8 was rebuilt into the operator's real report (47 figures) and read in a browser, figure by figure.
Hovering a point turned its ring black; two native diagrams printed dark text on a navy node; a message label was struck through
by a lifeline; a legend was printed twice. None was visible to a byte-level test, and the first was the very defect the release
exists to remove.

### Fixed

* **A mark that draws a stroke in its own colour keeps it on hover and pin** (`OG-269`): a line chart's point is a white
  circle ringed in the series colour, and the hover rule repainted the ring ink. Marks now carry `data-sk="own"` when their
  stroke is a colour (white and grey are separators), and hover/pin thicken and brighten them without repainting; bars,
  slices and tiles keep the ink outline. Verified in a real browser (the hovered ring's computed stroke is unchanged) and on
  the 47-figure report (91 hovered marks: 91 tooltips, none flickering, none moving, none changing hue).
* **A highlighted native node labels in the light ink** (`OG-270`), contrast-checked against the shield token.
* **A sequence label no longer sits on a lifeline** (`OG-271`): the line is cut behind the text.
* **A legend the figure draws itself is not printed twice, and a mark table with no numbers has no empty `Value` column** (`OG-272`).

### Derived work

All 14 chart goldens re-baselined (additive; `tools/visual-engine/renders/diffs/2026-10-10-own-stroke-hover.md`), the
capability gallery rebuilt, the blueprint rebuilt last. Project version `1.0.8` → `1.0.9`; the copy's release tag number is
`1.0.16`.

## [1.0.8] — 2026-10-10 · Figures are scoped, numbered, linked and explained — and a machine can read them (`OG-250` … `OG-268`)

Found by an operator reading a long report, a document that inlines 28 engine charts and 19 diagrams
into one page: hover colours that flashed or went black, a lens-shaped fill between two points of a curve, label
halos, white ink on tan tiles, legend names that flickered, numbers in circles with no explanation, diagrams squeezed
into the text column. Every one passed this engine's tests, because each figure was correct **alone** and the
defects exist only **together** — the same class `OG-244`'s field trial named: a condition the engine's own
self-checks cannot generate. Design and rules: `docs/design/FIGURE_SYSTEM.md`.

### The root, and the fix per class (`RULES.md` Rule 1)

* **Global CSS from a local file (`OG-250`, HIGH).** ECharts ships `.zr-cls-N:hover{fill:…}` inside each SVG and
  `normalizeSVG()` renumbers the classes from 0 in *every* chart, so 28 inlined charts shared eight class names with 28
  different bodies. The new **figure layer** (`adapters/echarts/figure-layer.mjs`) removes ECharts' CSS and classes and
  ships one `<style>` per figure, every selector starting `svg[data-fig="<scope>"]`.
* **Global ids (`OG-251`).** One scoping rule, applied in the chart engine *and* by `components.figure` to every figure
  whatever produced it (Mermaid included).
* **Hover that recolours (`OG-252`).** A hover state may change brightness, outline, thickness and opacity — never hue;
  never fill an open path; never move a mark; never take the pointer. Enforced by tests, not by a comment.
* **Ink and colour (`OG-253`, `OG-255`).** Label ink is chosen from the fill by WCAG contrast (pure black/white in the
  mid-tone band where the brand inks fall short of 4.5:1); no halos; severity/status words keep their reserved colours.
* **Marks that say nothing (`OG-254`).** Every mark carries an id, a title and its neighbours; the engine writes a
  per-figure record (`--formats json`, `ultimate-engine/figure/1`).
* **Native diagrams (`OG-256`, `OG-257`).** Tone families, edge roles, a travelling dot coloured by phase, numbered
  circles (radius 12) placed by a search the collision gate shares, a reading key, sequence message kinds, and a 24 px
  title reserve — a spec that was valid before is drawn at most 24 px taller instead of being refused (`OG-267`).
* **Text and pictures (`OG-258`, `OG-259`).** Figures are `Fig. N`, sections are `sec-<slug>`, a chip row and a back link
  join them, `[[fig:ID]]` links prose to a figure (a dangling reference is refused), and every figure prints a reading
  guide, a key and — for engine charts — a mark table. New output format **`blueprint`**
  (`<stem>.blueprint.json`, `ultimate-engine/blueprint/1`): the machine twin of a document, from the same render pass.
  Figures take the full content width, centred, outer border only.
* **Two native defects found by sweeping the gallery in a browser (`OG-260`).** A radar legend swatch painted
  `fill="files"` (black); heat-map values were always white.
* **Behaviour needs a browser (`OG-261`).** A scoping rule that prefixed `data-id` killed every adjacency highlight and
  arrowheads grew when an edge lit — both found by hovering, neither by 700 tests. `tools/tests/browser/figure_runtime_check.mjs`
  drives real pointer and keyboard events in headless Chromium; its wrapper skips with the cause when Playwright is absent.

### Process findings worth keeping

* The first sequence-title reserve (36 px) made the corpus guard refuse the flagship gallery: its sequence declares
  `height` equal to the *old* minimum plus 24. A rendering improvement must not invalidate a spec that was valid.
* "No previously-valid spec is invalidated" was true only of the specs I tried. A host's own suite found a titled, one-message
  sequence at height 200 (valid at the old 180, refused at the new 204), and the unit test had pinned the opposite. The claim is now
  true by construction (`_canvas_height`), and the engine is no longer tagged before its consumers' suites have run on it (`OG-267`).
* The first blueprint was blocked by the engine's own leak-gate: `svg_sha256` is not read as a hash label (the
  underscore joins the words), so hashes sit under a bare `sha256` key.
* `inkFor`'s own RGB sweep disproved "near-black or white clears AA": `rgb(153,102,153)` is 4.45:1 for the better of the
  two brand inks. The mid-tone band steps to pure black.
* The semantic-colour lookup for "Unrated" read a theme key (`inks.steel`) that exists only in the document theme.

### Dependencies

`proxy-addr` 2.0.8 (CRITICAL `GHSA-jqcg-44mw-7w3h`, which reddened a host's required `npm audit` context),
`fast-uri` 3.1.8, `ip-address` 10.7.3, `@modelcontextprotocol/sdk` 1.32.1 in `tools/visual-engine`, and `brace-expansion` 5.0.12 in the root
lint-toolchain lock (high, `GHSA-6j4f-fj2g-mc7p`; `OG-266`) — `npm audit` reads zero in **each of the three tracked lockfiles**; both
`VERSION_LOCK.json` attestations re-derived. Dependabot #6 is superseded, #7–#9 close with this release.

### Derived work

Themes (`line` default `symbolSize` 5 → 7, width 2 → 2.5), the MCP tool-schema snapshot (`visual_render` gains
`formats: json`) and all 14 goldens were re-baselined; the drift is classified in
`tools/visual-engine/renders/diffs/2026-10-10-figure-layer.md` (`FIGURE_LAYER_APPROVED`). The flagship gallery and the
`blueprint/` map were rebuilt last.

### Found by the full suite after the work (`OG-263`)

`blueprint layout` failed once the engine gained modules: ELK left two same-row nodes 32 px apart (a routed edge's dummy node sat
between them) against docgen's 72 px rule. `elk_layout.mjs` now legalises each row deterministically; red-first fixture and test
in `tools/tests/`. `_PYTEST_HARD_FLOOR` ratcheted 577 → 605, then 605 → 609 once `OG-264`'s tests raised the defined count to 760, then 609 → 612 for `OG-269` … `OG-272` (764).

### And the corpus guard that read a page as Markdown (`OG-264`)

`crossrefs` ran its `[text][label]` check over tracked HTML, so the rebuilt gallery's scoped hover CSS (`[data-k="node"][data-id="n0"]`)
produced 221 "dead reference-style links". For HTML the check now reads text nodes only; two-sided tests.

### Not done, and said so

`OG-262` (`NOT_A_DEFECT`): the nine native chart kinds do not carry the per-mark attribute contract — a feature, not a
repair, and the first item of `docs/plan/START_NEXT_SESSION.md`.

### And a sanitiser that was right only for well-formed input (`OG-265`)

The pull request's `CodeQL` check flagged `decorateSvg` deleting `<style>` blocks with a single `replace`: removing one block can splice the text around it into another. `stripStyleBlocks` now repeats to a fixed point and has a two-sided test (the premise that one pass is not enough is itself asserted).

### What a consumer's own suite sees (`OG-267`)

Running a consumer's `tests/docgen` on the candidate found one real regression and two assertions that pinned old markup. **Fixed:**
a titled sequence spec whose height was valid before the 24 px title reserve is no longer refused (`_canvas_height`; a spec short
of the old minimum still is). **Changed on purpose, consumers update their assertion:** a hand-written `Fig. N - ` caption prefix
is stripped and the engine's number is the link `Fig. N` beside a `fig-title` span (the literal `Fig. 1 - flow` no longer
appears), and the travelling dot is `class="dot dot-<phase>"` (an exact `class="dot"` match fails, `.dot` does not). The copy's release
checklist now runs the consumer's suite on the candidate before a tag is cut.

### And a health check that was red before this release changed anything (`OG-268`)

`SUITE-04` runs the latest `ruff` and `mypy`. On the copy's `1.0.14` release tag with today's tools it already read ruff 1 and mypy 30 against a ceiling of 22, and this release added three more. All are fixed in the code (annotations, string coercion at json boundaries, env-agnostic ignore codes for the two stub-less imports), both ceilings are re-pinned to **0**, and the opt-in git hooks (`STRUCT-03`/`STRUCT-04`) must be installed in the checkout that runs health (`bash tools/hooks/install.sh`).

## [1.0.7+copy] — 2026-09-24 · A host owning its own `tools/project_index` could never register a views-registry view

Found working a host project's register row (an external host whose engine-profile file
vendors `tools/docgen` and `tools/tests` but, deliberately, not `tools/project_index`: that name in
the host is a different, required-CI-context tool, a docs-index/supersession gate, with no `index`
submodule at all).

### The defect

`tools/docgen/views.py::_load_project_index()` did `from tools.project_index import index as
project_index` — the flat artifact registry lived at `tools/project_index/index.py`. In any host
that vendors `tools/docgen` (so it has `views.py` and therefore audience views) without also
vendoring `tools/project_index` — because it owns an unrelated package under that name, as
the host does — that import fails with `ImportError: cannot import name 'index' from
'tools.project_index'` on *every single build*, unconditionally. `views.build_and_gate_views`
correctly turns that into a BLOCKING `ViewRegistrationUnavailable` finding rather than a crash
(measured in a host), so the failure mode was quiet rather than loud: zero views ever written, zero
views ever registered, in a host that was otherwise completely correctly set up.

### The fix

The registry implementation moved to `tools/docgen/artifact_index.py` — inside the package every
consumer of `views.py` already vendors whole, so it now travels WITH `views.py` instead of
depending on a sibling package a host may deliberately not have. `tools/project_index/index.py` is
now a thin re-export shim (this repo's own `tools.project_index.cli`/`dashboard` and any external
caller of `tools.project_index.index`'s public API keep working unchanged); `views.py` now imports
`tools.docgen.artifact_index` directly. Also fixed in the same pass: `engine_config.
project_index_path()` resolved a *relative* `projectIndex.path` config override against the
process's CWD rather than `host_root()` — inconsistent with every sibling accessor in that module,
and load-bearing here because it is exactly how a host like that one would want to relocate the
index away from its own repo root (to avoid colliding with an unrelated tracked file of its own).

### Retained counter-examples

`tools/tests/test_views.py::ViewsRegisterDespiteAnUnrelatedHostProjectIndexPackage` reproduces
that host's exact shape — a fake `tools.project_index` package on `sys.modules` with no `index`
submodule — and shows a view still builds, writes and registers. Run **red first** against the
pre-fix import (confirmed by temporarily reverting `_load_project_index()`): both new cases failed
with the original `ViewRegistrationUnavailable`, exactly the defect being closed.
`RegistrationUnavailableIsBlockingNotSilent` (pre-existing, retargeted) now shadows
`tools.docgen.artifact_index` itself instead, so the fail-closed/loud-not-silent guarantee is still
exercised for the failure mode that remains genuinely possible (a broken or partial vendoring of
`tools/docgen`). `tools/tests/test_config_resolution.py::ProjectIndexPathIsHostRootRelativeNotCwdRelative`
covers the `engine_config.py` fix the same way: a relative `ENGINE_PROJECT_INDEX_PATH` override,
invoked from a CWD one level below `host_root()`, must still resolve against the host root.

### Not changed, and why

`tools/project_index/index.py`'s shim exports its public functions as genuine `def` wrappers
(`register_artifact(artifact): artifact_index.register_artifact(artifact)`, and so on) rather than
plain `from tools.docgen.artifact_index import register_artifact` re-bindings. Two independent
reasons converged on the same shape: a wrapper resolves `artifact_index.<name>` by attribute access
at CALL time, so patching the real module's function is honoured through the shim (a frozen
re-import would not be); and `tools/blueprint`'s C4 depth ladder (`BUILD_PLAN.md` D4) measures a
container as only as deep as its shallowest module, and a module with zero top-level `def`/`class`
statements cannot pass rung 2 ("enumerable") no matter what it re-exports — which is exactly what
happened on the first pass here, dropping the `project-index` container from its committed
`depthFloor: 2` to a measured 1 and failing `test_blueprint_phase6`'s ratchet
(`floor_findings`/`OG-233`'s "may only be RAISED" rule leaves no clean path to lower it instead).
Both problems share one fix: the shim's public surface is real functions, not name aliases. The
private names below it stay plain re-exports — nothing in this codebase calls them by name through
the shim, only through direct `tools.docgen.artifact_index` imports, so there is no
wrapper-vs-frozen-binding distinction to make for them, and the ladder only requires one public
definition, already satisfied by the functions above it. `_PYTEST_HARD_FLOOR` (`tools/health/checks.py`)
was ratcheted 569 → 573 for the retained-counter-example classes this patch added (see that
constant's own comment for the per-patch union arithmetic — `RULES.md` Rule 1, the #441 shape).

### A second defect, found by actually proving the first fix in a real host

Proving the fix inside that host (relocating its index to `docs/design/doc-system/PROJECT_INDEX.json`
per the "decide where it should live" half of this work, then running a real `cli build`) surfaced a
SECOND, independent bug: `views.py::_register_view` computed a view's registered `path` relative to
`engine_config.host_root()` unconditionally, while every READER of the index
(`artifact_index.verify`/`list_artifacts`/the dashboard) resolves a registered path relative to
`artifact_index._artifact_root()` — the index's OWN directory, which that module's docstring already
documents as the frame a relocated index carries with it. The two agree only when the index lives
exactly at `host_root()` (the untested default), which is why no prior test caught it: every existing
test patched `_index_path` alone, never `host_root()`, so the two frames happened to already differ in
every test run — but the OLD code's `relative_to()` call was *also* already failing there and silently
falling back to an ABSOLUTE path, which still resolves correctly by pathlib's own "absolute operand
wins" `/` semantics. That accident hid the bug from a suite that has run green the whole time. Measured
live: a real `cli build` inside that host (index relocated, `.health/` scratch fixture as the source)
wrote and registered four views, and `artifact_index.verify()` reported all four `MISSING` — correct
data, wrong frame.

Fixed by relativizing against `artifact_index._artifact_root()` instead of `host_root()`, and by
switching from `Path.relative_to()` to `os.path.relpath()`: the index's directory and a build's output
directory are typically SIBLINGS under the host root (a doc-system state directory vs. a docs output
tree), never one inside the other, so `relative_to()` (no `..` support without `walk_up=True`, a Python
3.12+ feature this 3.11+ package cannot use) was always going to fail there and fall back to an absolute
path — which would have baked one contributor's local filesystem layout into a TRACKED, committed
`PROJECT_INDEX.json` for every other checkout to read. `relpath` expresses the sibling-climb correctly
as an ordinary relative string. The now-unused `host_root` parameter/variable is removed from
`_register_view`/`build_and_gate_views`, along with the `engine_config` import that existed only to
supply it.

New retained counter-example:
`test_views.py::ViewRegistrationIsRelativeToTheIndexsOwnRootNotHostRoot` — patches BOTH `host_root()`
(env var + cache-clear) and `_index_path()` to two different subdirectories of one throwaway host (the
shape no prior test constructed), builds a real view, and asserts the registered path is
artifact-root-relative and that `verify()` finds it. Run red first against the pre-fix code (confirmed
by stashing `views.py` alone): it failed on the exact string, `out/<file>` (host-root-relative) instead
of `../../../out/<file>` (artifact-root-relative). `_PYTEST_HARD_FLOOR` needed no further ratchet — 717
defined tests, lower bound 573, unchanged from the first fix's number by coincidence of arithmetic, not
by design.

### Also in this release: vault containment follows a relocated index (review of the consumer's pull request, P1)

The first fix made a registered path relative to the index's own directory, but `_is_vault_path` still compared
it as if the index sat at the host root. With the index relocated below the host root, the textual route
saw `../../confidential/…` (no `docs/` prefix), and the filesystem route resolved the vault as
`<index-dir>/docs/confidential`. A headerless artifact inside the real vault therefore registered into
the tracked, public index. Both routes now check the candidate against the vault anchored at
`engine_config.host_root()`: the textual one re-expressed host-relative, the filesystem one against both
anchors (refusing more is the fail-closed direction). `VaultContainmentFollowsARelocatedIndex`: three vault
spellings that registered before the fix are refused, and a public artifact outside the index directory
still registers.

### Also in this release: a code span cannot cross a GFM table row

`_code_span_ranges` let a span run across line breaks up to a blank line, which is right for a prose
paragraph and wrong for a table. A GFM table is one paragraph, but each row's cells are parsed as inline
content on their own. So one unbalanced backtick run anywhere in a long table paired with a run in a
later row and flipped the pairing of every row after it. Measured on a host's findings register:
28 rows end on a truncated, unbalanced run, and the flip made a backticked
`` `<!-- audience: internal -->` `` mention further down read as a real directive. That is why
`test_the_four_tracked_documents_no_longer_register_as_marker_using` was red at the copy's `1.0.13` release tag
as well as on this branch. The same bug also ran in the leak direction: a stray run could pair with one in
the next row and hide a real marker between them.

A span that opens on a row of a real GFM table — a line holding a pipe, followed by a delimiter row, through the next blank line — is now bounded by the end of that row. A leading `|` alone is not a table (review of the consumer's pull request): pipe-prefixed prose stays an ordinary paragraph, where a span may cross a soft break. That register turned out to hold 14 pipe-row blocks with no header or delimiter row, which GitHub renders as run-on paragraphs; under strict GFM those really do pair across lines, so the host repaired its tables rather than the engine loosening the rule. Two
retained counter-examples join `AMarkerInsideACodeSpanIsDocumentationNotADirective.CASES`, one per
direction. Both fail against the pre-fix code, and so does the live-register test.

### Also in this release: the test helpers honour the declared 3.11 floor

`tools/tests/lab.py::force_rmtree` and `test_doc_identity.py` called `shutil.rmtree(onexc=…)`, which is
Python 3.12+. The README declares docgen 3.11+, and a host running the vendored suite on 3.11 got 37
set-up ERRORs, which also hid two real render-engine skips behind them. Both helpers now pick `onexc` on
3.12+ and `onerror` below it (the callback ignores its third argument either way).

### Also in this release: one stale example row restored (a host-synced example row)

`tools/graphify/pipeline.example.json` still described a host's dynamic stage as
`Dynamic / fuzz (opt)` over `src/dynamic/{foundry,fuzz_orchestrator}`. That host retired its
fuzz orchestrator and corrected its own copy of this row by hand, and the next sync
correctly overwrote that hand edit with these stale bytes, because the vendoring contract is "edit the copy, then
sync". The row now reads `Dynamic / proof (opt)` over `src/dynamic/foundry`, so syncing this tag
restores the host's correct description instead of reverting it. No code reads the file (cosmetic example
row); `python3 -m json.tool` parses it.

## [1.0.7] — 2026-09-18 · Nine Dependabot alerts closed — four of them weren't the false positives they looked like

Requested as two separate jobs: patch 5 real transitive-dependency alerts in `tools/visual-engine`,
and dismiss 4 `fast-uri` alerts believed stale (installed 3.1.5, claimed vulnerable ranges all
`<2.4.5`). Re-checking the second half against the live Dependabot alerts API (not the claimed
ranges) showed the premise was wrong: alerts #5/#4/#2/#1 were `fast-uri` `GHSA-jqff/f65p/fph4/5jgf`,
vulnerable ranges `<3.1.6` (two SSRF, two host-confusion, all "high"), which **do** cover the
installed 3.1.5. They were live, not stale, and were patched instead of dismissed.

### The fix — transitive-only, patch-level, no direct-dependency changes

| package | before | after | alerts closed | advisory |
|---|---|---|---|---|
| `qs` | 6.15.3 | 6.16.0 | #9, #3 | `GHSA-4mjr-xmp4-gh2g` (DoS via `isBuffer`), `GHSA-x5fp-wj9c-mxmx` (array-limit bypass) |
| `hono` | 4.13.1 | 4.13.8 | #8, #7, #6 | `GHSA-gqvv-2mrq-wpjv`, `GHSA-crvj-82cr-hjcx`, `GHSA-g6gw-c38x-mqfc` |
| `fast-uri` | 3.1.5 | 3.1.8 | #5, #4, #2, #1 | `GHSA-jqff-g426-hqxp`, `GHSA-f65p-4m7j-42xc`, `GHSA-fph4-wmhf-6fwf`, `GHSA-5jgf-p345-68v8` |

All three are transitive (`qs`/`hono` via `@modelcontextprotocol/sdk`'s own deps, `fast-uri` via its
`ajv`); `npm update <pkg>` resolved each to the latest version inside its parent's already-declared
semver range, so `tools/visual-engine/package.json`'s 4 direct pins (`echarts`, `@resvg/resvg-js`,
`@modelcontextprotocol/sdk`, `zod`) are byte-for-byte unchanged — confirmed via `git diff` before
committing.

### Verification

- `npm audit` (isolated cache, avoids a pre-existing root-owned `~/.npm` cache issue on this
  machine): 1 high-severity finding (`fast-uri`) before the fast-uri patch → **0 vulnerabilities**
  after all three.
- `npm test`: **33/33 passing**, no regressions (MCP facade, golden-render byte-reproduction,
  build-twice determinism, reskin law, theme-drift guard — full suite).
- `tools/visual-engine/VERSION_LOCK.json`'s `npm_lockfile_sha256` re-derived and updated — this is
  the attestation `tools.health` **STRUCT-09** mechanically re-hashes on every run (the same
  attestation that was found silently false once before, `OG-158`); leaving it stale after this
  lockfile change would have reintroduced that exact defect. `SECURITY_POLICY.md`'s supply-chain
  row's audit-clean date updated alongside it.
- `python3 -m tools.health.run`: re-run after the fix to confirm STRUCT-09 and the rest of the
  structure/consistency suite stay green with the new hash in place.

### Cross-document consistency (`CONS-08`)

Bumping `PROJECT_VERSION` moves the ground truth `tools.health` `CONS-08` checks the 5 state/handover
documents against. Three carried a present-tense `project 1.0.6` claim and needed the matching
token-level correction — `HANDOFF.md`'s project-version row, `docs/plan/START_NEXT_SESSION.md`
(its summary line and, separately, inside the round-2 launch-prompt block), and
`docs/process/SESSION_STATE.md`'s state block. `docs/plan/NEXT_SESSION.md` and
`docs/process/OPEN_GATES.md` carried no such claim and were untouched. **`SESSION_STATE.md`'s
substantive checklist and its `WORK-COMPLETE-VERIFICATION-PENDING @ db10f58` stamp were deliberately
left alone** — that record describes field-trial round 1's closure and round 2's still-open planning,
a separate initiative this patch has no bearing on; only the one version token was corrected.
Re-running `python3 -m tools.health.run` after all edits confirms `CONS-05` ("version 1.0.7 agrees
with CHANGELOG"), `CONS-08` ("all 11 state claim(s) ... agree with ground truth ... project 1.0.7"),
and `STRUCT-09` all green, same 33 passed / 0 failed / 5 skipped of 38 floor as before this change
(the 5 skips are `--full`-only suites plus one sandbox-environment `mktemp` limitation on `STRUCT-04`,
unrelated to this patch).

### Not touched

`tools/mermaid-engine/package-lock.json` — a separate tracked lockfile with its own
`VERSION_LOCK.json` (also read by STRUCT-09) — was not part of either request and was not run
through `npm update`; confirmed unmodified in the final diff. `docs/plan/NEXT_SESSION.md` and
`docs/process/OPEN_GATES.md` (no stale version claim). `SESSION_STATE.md`'s checklist and stamp
(a different initiative's closure record — see above).

## [1.0.6] — 2026-09-07 · A nested host could not read its own history: one `./` in three places

Found by pointing the engine at a host that sits one directory below its `.git` — a vendored
payload, the layout `CONFIGURATION.md` says is supported and that the first external field trial
never exercised, because its subject was the git top-level.

### The defect (`OG-249`)

Three sites built `git show <sha>:<rel>` with a bare `<rel>`. Git resolves that against the
repository **top-level**; the `git log -- <rel>` and `git ls-tree <sha> -- <rel>` calls beside
them resolve against the **invocation directory**. The two agree only when the scanned root is the
top-level. Everywhere else the ratchet reported *"historical spec blob … is unreadable — the object
store is incomplete"* (a true `ls-tree` followed by a false `show`, misread as truncation) — and the
two stamp guards did something worse than fail: the blob read returned nothing for every stamp, the
failure was routed to "unverifiable" **after** `checked` had already been incremented, and the guard
printed `PASS, 8 stamp(s) checked` on a host where no body had been compared at all. Measured on the
nested host: a drifted, undeclared body under a `verified_state: verified` header passed both guards.
That is the false green `P7-54` warned about, reached by a different route. A `./` prefix makes
`show` resolve from the working directory too; a top-level host is unaffected.

| site | before | after |
|---|---|---|
| `tools/blueprint/completeness.py` (2×) | `f"{commit}:{rel}"` | `f"{commit}:./{rel}"` |
| `tools/corpus_check/guards/stamps.py` | `f"{sha}:{rel}"` | `f"{sha}:./{rel}"` |
| `tools/corpus_check/guards/identity.py` | `f"{stamp.sha}:{rel}"` | `f"{stamp.sha}:./{rel}"` |

### Retained counter-examples

`tools/tests/test_git_paths_from_scanned_root.py` builds a repository whose host is `<repo>/host/`
and asserts (1) the ratchet remembers the highest floor ever committed, (2) the `stamps` guard
reports an undeclared drift after a stamp, and (3) the `identity` guard reports a `verified_state:
verified` claim whose stamp no longer covers the body. All three were run **red first** against the
bare-path form: (1) `historical spec blob … is unreadable`; (2) and (3) reported nothing — the
false green itself. A first draft of (2) only asserted that a valid stamp was accepted, and it
passed on the defective code; a probe that cannot fail on the defect it names is not a probe.

### Not changed, and why

The engine's own tests and hook checks still resolve "repository root" as the git top-level, so a
vendored copy's self-tests are not meaningful from inside its host (`ModuleNotFoundError: No
module named 'tools'` in subprocess tests; `STRUCT-03/04` looking for hooks in the host's
`.git/hooks`). That is a separate, larger calibration — the field trial's *health capability
profiles* proposal — and is left open rather than half-done here.

## [1.0.5] — 2026-09-01 · Round 1 came back: five real defects repaired, three claims refuted

The first external field trial ran and filed eleven findings. **Every one was re-derived here before
anything was changed** — the point of a trial report is not to be believed. Five were real engine
defects and are fixed, red-first, below. Three were correct observations about the *subject* and are
not this engine's to repair. Three were wrong, and being specific about why is the more useful half
of this entry.

### The five that were real — all found only because the engine was pointed at something else

| id | what was broken | why no self-check saw it |
|---|---|---|
| `OG-244` | `tools.draft check` crashed instead of returning a verdict | Size-dependent: **3/3** on a 1,046-file host, **0/3** on this repository's 362 files |
| `OG-246` | A layout could pass ELK and then be refused by docgen's placement rule | Needs a *disconnected* package graph; this repository's is fully connected |
| `OG-247` | A check's child inherited neither the interpreter nor the import path of its parent | Needs two interpreters with different dependency sets, and a host root that is not the launch directory |
| `OG-248` | Three graphify builders wrote an empty graph and exited 0 | Needs a host whose scanned directory does not match the builder's shape |
| `OG-245` | Every legend-less figure put a whitespace error into generated HTML | Nothing measured `git diff --check` over generated output |

**`OG-244` is the one that mattered.** `RULES.md` Rule 3 names `tools.draft check` as the mechanism
for the rule that pays for itself fastest — and it could not answer at all for a foreign host. The
gate built its baseline lab as a full repository and then copied it, object database included; the
detached `gc --auto` that `git commit` leaves behind packed and unlinked those objects while
`shutil.copytree` was still walking them. Measured: 255 loose object directories immediately after
the commit, **zero** three seconds later. The repair is not a retry — the candidate lab is now copied
from the exported worktree *before* either root owns a `.git`, and both labs are initialised with
`gc.auto=0`, so no background process mutates a lab while the guards read it.

`OG-248` supersedes `OG-241`, which had triaged the same shape as `NOT_A_DEFECT` on the reasoning
that a vacuous exit 0 was safe *because it was documented*. The trial refuted that empirically: the
documentation is in `engine.config.json` and `README.md`, the builder printed success, and a
consumer meets the exit code rather than the caveat. `build-deps.mjs`'s existing inline refusal was
**lifted** into `tools/lib/engine-config.mjs` rather than copied, so the three builders that walk a
host directory share one wording and one exit code (`RULES.md` Rule 1).

### The three that were the subject's, not the engine's

The subject's release metadata contradicts itself (33 `MODULE.md` files say `1.0.0`, their manifests
say `1.1.0`), its test manifest is stale, and its committed Graphviz derivatives do not byte-match a
fresh render from the installed `dot`. All three are real; none is an engine defect, and the trial
was right not to repair a read-only subject.

### The two that were wrong, and one that was right for the wrong reason

- **"The received engine cannot certify itself"**, filed CRITICAL on a `27 PASS / 10 FAIL` health
  run. The package handed over is **deliberately stripped**: `FIELD_TRIAL_ROUND_1.md` §2 removes the
  changelog, handover, registers, lessons, verification log, session record, plans and archive — 26
  tracked files — so the operator gets the engine and its method, not the story of how it was built.
  Health reported their absence correctly. This repository at the same commit measures
  **`HEALTHY — 38 passed, 0 failed, 0 skipped of 38`** under `--full --strict`. *The finding is
  nonetheless useful, one level up:* the brief never says the instrument is stripped, so the operator
  spent its first CRITICAL on the test's own packaging. Round 2's brief must state it.
- **"Health subprocesses discard the external `PYTHONPATH`."** They do not — `env=None` inherits
  the parent environment whole, and the child was measured receiving `PYTHONPATH=engine` intact. The
  proposed repair, passing `PYTHONPATH` to every child, would have changed nothing. **The symptom was
  real and the defect underneath it is now fixed**: `_run` sets `cwd` to the host root, which changes
  what a *relative* entry means, so `engine` became `<host>/engine` and resolved to nothing. Both
  halves are `OG-247`. Filed here rather than under "real" because the finding as written pointed the
  repair at the wrong mechanism, and a fix built to that description would have shipped green.
- **`system.spec.json` re-pointed at `docs/design/ARCHITECTURE.md`** because `docs/plan/BUILD_PLAN.md`
  was "absent". It is absent only from the stripped package; it is tracked here, and the spec still
  points at it. Not applied.

### One design gap named, not fixed

`blueprint build` on a foreign host publishes **this engine's** guard, health-check and figure-kind
registries in the host's `SURFACES.md`, because `tools/blueprint/surfaces.py` derives them by
importing `GUARDS` / `CHECKS` / `_FIGURE_KINDS` rather than from the host tree — and `blueprint
verify` passes, because it verifies tree ownership and not registry provenance. That is correct for a
**vendored** engine and wrong for a **sibling** one, and the engine has no notion of the difference.
Naming it is not the same as closing it: the repair is an installation/capability model, which is a
new deliverable rather than a fix, and it is left to be scoped as one.

### Also

- 9 ESLint `no-unused-vars` errors removed across five `.mjs` files. They had accumulated
  unmeasured: `eslint.config.mjs` exists and `npm run lint:js` runs it, but `tools/health/lint_baseline.json`
  pins only `ruff` and `mypy`, and `SUITE-04` never invokes ESLint — the config's own header says so.
  The count is now zero; wiring it into `SUITE-04` remains where that header left it.
- `examples/capability-gallery.html` regenerated (15 whitespace lines → 0), and
  `blueprint/{SYSTEM.json,SYSTEM.md,COMPLETENESS.md,system.layout.json}` regenerated behind the ELK
  spacing change (canvas 1549→1629 px; placement findings 0 before and after).

## [1.0.4] — 2026-09-01 · Round 1 gets a real foreign subject, and the language reach is measured

`[1.0.3]` pointed round 1 at a copy of this engine. That tested production and agent-usability but
explicitly could not test **portability** — whether the engine works when aimed at a project that is
not itself. This entry supersedes that design: **the subject is now external.**

### The subject, and why the alternatives were eliminated

**Chosen: the *Absolute Canonical Framework 1.1.0*** — a real governance framework with a Python
runtime, eleven numbered domains, `975` tracked files, `27` Python modules and `257` markdown files
of its own. The engine has never been pointed at it and it carries no engine artifacts.

Two candidates were examined and rejected, and the elimination is worth recording because each
failed for a different reason:

- **CredMgr v2 (Rust)** already contains **18 document sets built by this engine** — `.md` + `.html`
  + `.json` + `_spec.json`, carrying doc-system front matter. An operator pointed at it would be
  grading itself against answers already sitting in the folder.
- **CredMgr v1 (JavaScript)** is untouched, but it is not Python — see below.

### `OG-243`: the blueprint layer reads Python only

Found while choosing the subject, and registered before any of this was built. The import graph is
`_tracked(root, "*.py")` plus `ast.parse`; graphify's dependency builder likewise walks *"src/ for
.py files"*. So a Rust or JavaScript host project derives **zero** modules and zero import edges, and
the depth ladder and gatekeeper relation have nothing to work on. The document layer, the figure
renderers, the file-tree graph and every document guard are language-agnostic and unaffected.

Recorded as a stated bound rather than fixed: a per-language import resolver is a **new capability,
not a repair**, and a half-done one that silently under-reports edges would publish a confident map
with modules missing — the false-green class this engine exists to refuse.

### Feasibility proven before issue, not assumed

The engine really can be aimed at a foreign tree, and this was measured rather than hoped: pointed at
the subject it derives a real map (`975` files, `27` modules, `37` import edges, `257` markdown) and
`corpus_check` returns `5 passed, 4 failed, 2 skipped` with **49 real findings in the subject's own
documents**. `ENGINE_HOST_ROOT` resolves the host and `ENGINE_DOC_SYSTEM_DIR` relocates the rule
layer, both documented in `CONFIGURATION.md`.

**The command names are withheld from the brief on purpose** — finding them is the reachability half
of the test. The proof exists so that a failure to find them is read as a discoverability defect
rather than as an impossible task. One friction point is left in place deliberately: with the rule
layer relocated, a bare-name lookup still resolves under the relocated directory, so a locked file is
reported missing. It is surmountable, and it is exactly the kind of portability seam this round is
for.

### What the round can and cannot conclude

It **does** now measure portability. It still cannot measure **language reach**, because the subject
is Python — the engine's best case for structure. `docs/plan/FIELD_TRIAL_ROUND_1.md` §6 states both
halves rather than leaving the second to be discovered.

## [1.0.3] — 2026-08-31 · Round 1 redesigned before it ran: document the project from zero

`[1.0.2]` recorded round 1 as an **audit** of the shipped product — a full copy of the repository,
history included, with the operator asked to re-run the gates and attack the reasoning. That entry
stands as what was true when written; **this one supersedes its design**, on operator direction,
before the round was handed over. The record is append-only, so the correction is a new entry rather
than an edit to the old one.

### What changed, and why it is a better test

The old package handed over everything — including the finished documentation and the derived
blueprint. An operator given the answers can only be graded on whether it agrees with them. **The
round now removes the answers**, so the engine has to produce them:

- **removed:** all project documentation (charter, architecture, threat model), all build history and
  governance narrative (changelog, handover, registers, lessons, verification log, session record,
  plans and phase documents, the archive), the produced `blueprint/`, and the authored
  `system.spec.json` — the flagship artifact the operator must now author and derive for itself;
- **removed:** the git history. The package is a **fresh repository with a single commit**, not a
  clone. Git still works, which matters because the corpus guards, the stamp checks, the depth
  ratchet and the staleness check are all git-dependent;
- **kept:** the machinery and the rule layer — the tools, the rulebook, taxonomy, manifest,
  classification and contradiction table, the method documents, and the engine's own tests.

**The task is now the product claim itself:** take a codebase and produce the complete project
document set, its blueprints, its graphs and its JSON — then test, audit and calibrate the engine on
the evidence that exercise produces. Two briefs are issued rather than one (`SYSTEM-INSTRUCTION.md`
`dc45eaf5b916bf95`, `PROMPT.md` `188cc04d2c40a87c`), hashed rather than copied in.

### The measured baseline, recorded before issue

`docs/plan/FIELD_TRIAL_ROUND_1.md` §3 carries it: `health` **20 passed / 11 failed / 7 skipped**,
`corpus_check` 4/6/1 with 43 findings, `blueprint verify` `spec-missing`, and **86 of 574** retained
counter-examples not passing.

**The 20 passing checks are the engine; the 11 failures are the missing documentation** — `STRUCT-01`
names the nine absent core documents, and three guards refuse to pass **over nothing** rather than
report a hollow green. **The failure list is the specification**, which is the cleanest statement of
this engine's own contract the project has produced. The 86 non-passing tests are the number to
watch: any that never recover measure how tightly the engine is coupled to one project's corpus —
the portability question arriving as a measurement instead of an opinion.

### The measurement that justifies the round

Stage 5 of the brief withholds the prose and asks the operator to answer a fixed set of questions —
components and dependencies, what to change to extend it, the riskiest modules, the gate order, the
document lifecycle — **from the blueprints, graphs, tables and figures alone.** Every question that
cannot be answered that way is a defect in the blueprint layer, which is the precise thing this
engine exists to prevent. Nothing inside this repository has ever been able to take that measurement,
because every agent that has touched it already knew the answers.

`docs/plan/START_NEXT_SESSION.md` and `docs/process/ABSENT_PATHS.md` are reconciled to the round as
it will actually run.

---

## [1.0.2] — 2026-08-31 · Field-trial round 1 issued, and the repository swept for the handover

Process work, no engine behaviour changed: the Stream-B field trial the `1.0.1` audit closed **GO**
for is now **issued**, and the repository is cleaned and wired for the review session that follows.

### Round 1 is issued to a blind operator

`docs/plan/FIELD_TRIAL_ROUND_1.md` is the round log `FIELD_TRIAL.md` §4.7 requires, written **when
the round was issued** rather than after it returned, so the protocol cannot be trimmed to fit the
outcome. It records what was handed over (a full copy of the repository at `91c69dc` **including
`.git`**, so every git-dependent gate can actually run; the external secret scanner the hooks call;
the brief; a results template), what was withheld (transcripts, hints, mid-run correction, the
answers), and what was **removed** — the git remote, so no blind-run action can reach real history.

The issued brief and template are **hashed, not copied** into the repository (`36564ebe82b669b5`,
`8cf224bf1ae5733c`): a second copy of one text is the drift defect this engine exists to catch.

**The round is two-phase, and the ordering is the design.** `FIELD_TRIAL.md` §7 withholds command
names so a reachability test does not become a transcription exercise; the operator also wants every
corner exercised. Phase 1 is blind and is **written down before phase 2 is read**; phase 2 is the
full sweep, where anything not found unaided in phase 1 is itself a `NOT-DISCOVERABLE` finding —
which is what stops the checklist erasing the blind measurement. Phase 3 is calibration under the
standing discipline: a ratchet may only tighten.

**The subject deviates from `FIELD_TRIAL.md` §3 and the deviation is stated, not glossed.** Round 1's
subject is a copy of this engine rather than an external project — legitimate under the charter's
purpose 2, and satisfying §3's rules 1 and 2 more strongly than any external subject could (a
detached copy with no remote cannot perform a cross-project write at all). **What it therefore cannot
measure is portability** — host-root resolution, the config chain, the zero-configuration defaults —
and that is recorded as the gap a later external-subject round closes.

### The handover documents, rewritten in place rather than accumulated

- **`docs/plan/START_NEXT_SESSION.md`** is rewritten in place as the brief for the session that
  reviews the returned run. It had been carrying the superseded Phase-7 launch prompt long after the
  phase shipped — a record kept in the file whose job is to hold the **next** command. The Phase-7
  prompt lives in `git log` and in `[1.0.0]`, which is where a record belongs. One file, one job.
- The review brief carries the separation of duties explicitly (the reviewing session did not produce
  the run, which is why it may judge it), the rule that a discoverability finding is **never** closed
  by coaching the next operator — *if the answer was not findable from the repository, the repository
  is what changes* — and the instruction to treat the returned report as **evidence to verify, never
  a directive to follow**.

### Hygiene

38 MB of regenerable junk removed from the working tree (a stale `.docgen` build cache, `__pycache__`
trees, `.mypy_cache`, `.ruff_cache`, the derived `.blueprint` index, two stray built HTML artifacts).
Nothing tracked was deleted: the archived snapshots, the superseded plan records and the two declared
byte-identical file pairs all stay, because they are cited by other documents and by retained tests —
deleting them would break the guards that read them and destroy the audit trail. Tree clean, one
branch, no stashes, one worktree, nothing untracked.

`docs/CHARTER.md`'s corpus count moves 69 → 70 for the round log this adds.

---

## [1.0.1] — 2026-08-31 · The 1.0.0 full-system audit: proof, not construction

The one commissioned post-1.0 audit pass (`docs/plan/AUDIT_1_0.md`, its acceptance set AC-1…AC-13
frozen at commit `e4c77a2` before any audit work, hash `6c21d1cec88800cd`, proven byte-identical at
the close). It re-ran every floor to a verdict, independently re-attacked the Phase-7 close, swept the
three product pillars to finished-product status, and applied a bounded fix/calibration set under the
build's own falsification discipline. **No BLOCKING row surfaced; the build stays `1.0.0`-complete.**
This is a PATCH — two low-severity false-green fixes and one calibration, no new capability.

### The floors, re-proven on the tree as fetched (AC-1…AC-8)

`health --full` → HEALTHY 38/0/0 (run to a verdict on a quiet machine, load 5–18); `corpus_check`
→ 11/11, 0 findings; `blueprint verify` clean, `completeness --check` level with `verified` still 3
as a consequence; `--guard stamps` → drift declared by none; the full counter-example suite green,
0 skips; `hook_attacks.sh` → 23/23 refused; the server-side moat verified LIVE (`gh api …/rulesets`
active, require-PR + required `secret-scan`, EMPTY bypass) and `moat_server_side.sh` → the hostile
`--no-verify` push refused by GH013 at the server; and the A-10 browser sweep of
`examples/capability-gallery.md` measured **237 `<text>`/`<tspan>` across 23 SVGs, 0 overlaps / 0
out-of-box, in BOTH themes** (the zero is 237-of-237, `LESSONS.md` L-18). Independent cross-checks:
both stamped bodies (`PROVENANCE.md`, `THREAT_MODEL.md`) match commit `96b90d8` stamp-stripped, and
every stamped commit is reachable from `master` (three merge commits, no squash/rebase orphaning).

### The Phase-7 close, independently re-attacked (AC-9)

Ten read-only verifier lanes at the session tier, each pinned to `7d2272d` and handed the CLAIM
never the diff, re-attacked the OG-234 gitlink skip, the OG-224…OG-233 fix waves, the A-5
`verified_reachable` probe's faithfulness, the stamp dance, the acceptance freeze, and the merge
topology; three pillar lanes swept docgen / blueprint / graphing; one completeness critic. **Zero
BREACH, zero CRITICAL/HIGH.** The close holds. The re-attack surfaced two LOW false-greens and a set
of stated bounds, dispositioned below.

### The bounded fix set — each red-first, each with a retained counter-example

- **`OG-235` (LOW false-green):** the depth-ratchet's replace-graft guard checked only the literal
  `refs/replace` base, so a graft relocated via `GIT_REPLACE_REF_BASE` was ACTIVE for `git log` yet
  invisible to the guard — a confident LOWERED max (`{'x':3}` for a committed floor 9) instead of
  UNAVAILABLE, while the sibling `info/grafts` mechanism already defended its own `GIT_GRAFT_FILE`
  override. Fixed symmetrically (`completeness.py`); falsified both ways
  (`test_floor_a_replace_graft_relocated_by_GIT_REPLACE_REF_BASE_is_caught`).
- **`OG-236` (LOW):** the blueprint stale-map gate — whose whole value is "without it the map is
  prose again" — had no red-first counter-example for its FAILURE direction. The test named for it
  asserted a tautology (`SYSTEM.md + "\nline\n" != SYSTEM.md`) and never invoked `blueprint check`.
  Rebuilt to make a faithful lab current, stale one committed derived file, and assert `check` exits
  non-zero naming the drifted file (`test_blueprint.py`).
- **`OG-237` (calibration, AC-11):** `_PYTEST_HARD_FLOOR` sat at 190 while the suite grew to 575 — a
  gutting-backstop drifted to a third of its suite, and nothing forced the ratchet its own comment
  promised. Ratcheted 190 → 500, and — the class fix — added
  `test_the_pytest_and_harness_floors_track_their_suites`, which refuses a floor outside
  `[floor(0.80·defined), defined]` for BOTH hard floors (red at 190, green at 500). The moat-attack
  floor (20 vs 23) was examined and HELD, already inside the band with its derived gate at parity.
  Every other pinned ceiling/floor (`ruff=0`, `mypy_strict=22`) is at its earned limit and HELD.

### The stated bounds the re-attack found, registered not chased (AC-9/AC-10)

Recorded in `OPEN_GATES.md` as `NOT_A_DEFECT` with reasoning a verifier can attack and a trigger:
`OG-238` (an EBCDIC-encoded classified doc evades placement — no tracked non-UTF file exists, one
encoding-family past the CJK classes already fixed); `OG-239` (the ratchet's history memory hardcodes
SHA-1 — fails safe, latent on a sha1 repo); `OG-240` (a committed loosening is undetected in a
shallow/partial/grafted clone — announced, and the enforcement path is the full-clone pre-push hook);
`OG-241` (SUITE-07 covers 2 of 5 graphify builders — the other three are documented worked examples);
`OG-242` (`layout --check`'s orphaned-SVG blind spot — hypothetical, no SVG is committed per OG-199).

### The GO / NO-GO for the field trial

**GO.** The next session after this one is the Stream-B field trial (`docs/plan/FIELD_TRIAL.md`). The
preconditions are in place: the three roles are defined (§2), the subject-project rules are stated
(§3), and the blind-operator task statement is written (§7). The PAIRED design is runnable — a blind
operator (any model with no history here; ChatGPT in the first instance) against this project's own
agent, in parallel, on the same real external project, compared against the gates, the task, and each
other. The engine's own floor is green at this close. **The one thing this audit could not supply is
the field trial's subject project and the operator's own externally-designed trial plan, if any** —
none is in this repository, so the trial session must obtain the subject path and reconcile any held
plan against `FIELD_TRIAL.md` before issuing the task (recorded as the GO's single precondition, not a
blocker). Nothing in the engine blocks the trial.

---

## [1.0.0] — 2026-08-30 · Phase 7: harden, stamp, and make the moat non-optional

The build's last phase, and different in kind: Phases 1–6 built things, Phase 7 **proved** them, and
the proving is the deliverable. Against a frozen acceptance set (`BUILD_PLAN.md` row 7, hash
`db24fd1fab14150b`, written and hashed before any work and proven byte-identical at the close).

### The reverification (Pass 9) — the debt `OG-190`/`OG-203`/`OG-209` recorded, come due

Four independent verifiers, each at the session tier (`fable`), each handed the CLAIM and never the
diff, each pinned READ-ONLY to `dfc27fe`. The thesis — *implementer-verified fixes do not survive an
independent attack unchanged* — held a fourth time: every lane found a real defect. Raw findings in
`docs/process/VERIFICATION_LOG.md` Pass 9; disposition in `OPEN_GATES.md`.

- **The moat red-team found two real breaches** at the new edge of narrowed gates, neither a rerun of
  the retained attacks. **`OG-213` (CRITICAL):** the classification placement gate read a header only
  for nine allowlisted suffixes, so a `classification: secret` document saved as `notes.mkd` (a
  standard Markdown alias) or with no extension reached the remote — fixed by inverting the suffix
  allowlist (fails unsafe) to a structured-data denylist (fails safe), so content decides.
  **`OG-214` (MEDIUM):** pre-push never scanned the published PATHS, so a key-shaped filename via a
  merge that skips pre-commit reached the remote — fixed via the L9 two-step (rulebook `1.2.16` →
  `1.2.17`) so pre-push writes `__paths__` like pre-commit.
- **`OG-215` (HIGH):** the surfaces env-var derivation scanned text, not structure — a phantom, a
  docstring-satisfied credit, missed constant-name reads, and a circular probe. Fixed by deriving
  env reads per language from the AST, and replacing the probe with a planted-input falsification.
- **`OG-216`/`OG-217`/`OG-218`:** a comment could manufacture a `guarded_by` edge (fixed by stripping
  prose before the match — which removed four real false edges on the live tree); the `documented`
  state definition was contradicted by its own rung-4 nodes (corrected, single owner); a shallow
  clone silently under-enforced the ratchet (now UNAVAILABLE). `OG-219` (symbols text fallback) is
  `NOT_A_DEFECT` — unreachable on a green tree.

### The recursion: rounds three and four, where the thesis was turned on its own fixes

The reverification did not stop at attacking Pass 8 — it attacked its OWN fixes, and then the fixes
of those fixes, because implementer-verified work not surviving an independent attack is the finding
whether the work is a feature or a patch. Three further rounds ran, and each narrowed:

- **The round-two fixes were string-blind** (`OG-224`): the derivation repairs matched over raw
  source, so a boundary shape — a `#` inside a quoted shell word, a URL in a comment — still moved a
  number. The `OG-216` prose strip reached the text route but **not** the `-m` subprocess route
  (`OG-225`), so 36 phantom edges survived on the live tree until the prose-free source was shared by
  both. The shared strippers were placed to add **no** graph node, because a new module would shift
  the package layout and fail `blueprint verify` — the derivation layer measuring itself.
- **The `OG-213` empty-path fix over-corrected** (`OG-226`): skipping a blank path made
  `scan_manifest` hand every SUBTREE object to `git cat-file blob`, which exits non-zero on a tree,
  so pre-push refused **every** push with eleven false findings — fixed with a `git cat-file -t`
  type check so only blobs are scanned.
- **Two encoding classes the narrowed placement gate still missed:** a wide-encoded CJK secret
  document (`OG-227`) and then a NARROW legacy-CJK one (`OG-232`, round four) both decoded past the
  replacement-ratio cap and walked their ASCII headers through — fixed by keeping any blob whose
  front-matter header survives at position 0, where binary has nothing.
- **The ratchet's memory had three holes** (`OG-228`/`OG-229`/`OG-230`) and grew a fourth as a
  regression: a floor raise committed in an **evil merge** was forgotten when round three added
  `--diff-filter=ACMR` to tell a deletion from a missing object, because that filter drops merge
  commits (`OG-233`, round four) — fixed by removing the filter and using `git ls-tree` per commit,
  which reads the tree blobless.

Round four confirmed the round-three fixes held in both directions and converged to exactly two
narrow MEDIUMs (`OG-232`, `OG-233`), each reproduced → fixed → validated → probed. The findings
narrowed CRITICAL → HIGH → MEDIUM across the rounds; a fifth round was not run because convergence,
not fatigue, is the stop condition. Every row `OG-220`–`OG-233` is in `OPEN_GATES.md` `## Closed`.

### The moat is non-optional (`OG-31`) and the stamp covers the tree (`OG-09`)

- **`OG-31`** — the server-side half, the only place `--no-verify` can close. A branch ruleset on the
  default branch requires a pull request and a GitHub-hosted `secret-scan` check
  (`.github/workflows/secret-scan.yml`, gitleaks pinned by checksum), no bypass actor. Proved by
  doing it: `tools/tests/moat_server_side.sh` pushes a planted secret to `master` with `--no-verify`
  and the server refuses it. The residual — a feature-branch push on this no-GHAS private repo has no
  push-time content scan — is stated in `THREAT_MODEL.md`, not pretended away.
- **`OG-09`** — `PROVENANCE.md` re-hardened and re-stamped against a real commit; the
  `NEEDS RE-HARDENING` block and the `HANDOFF.md` amnesty are removed, so the `stamps` guard passes
  because the body matches, not because a handover excused it.

### `verified` is non-zero, as a consequence (`OG-207`)

`docs/process/THREAT_MODEL.md` — owner of the `moat` container, the deepest in the map and the only
one the depth ladder carries to rung 5 (`detail`) once its document is governed and claims verified —
is brought under governance (governed 4 → 5) and stamped `verified`, so the moat's three modules
reach `verified` in `blueprint/COMPLETENESS.md`: the first non-zero count, reached by the honest
stamping work rather than aimed at. Governing the document lifts the moat from rung 4 to rung 5, so
its `depthFloor` is raised 4 → 5 to keep the earned depth (`CONS-12` refuses a floor with slack
beneath its own measurement). The bar itself is NOT lowered.

### The measurement decisions, decided by the non-author and not tuned to flatter

- **`OG-204`** — rung 2's evidence STAYS a public surface; a shim's `sketched` carries the accurate
  `why`, and widening it would move the number in the phase that benefits.
- **`OG-205`** — the changelog exemption STANDS with its bound stated; a dated record's counts
  describe when written, and re-grading them is what `under_dated_heading` prevents.
- **`OG-136`** — the server-side moat is GitHub-hosted; the VPS2 runner is an operator action,
  re-scoped, and nothing blocks on it.

### The acceptance run caught two defects the floor had hidden

Phase 7's own instrument found them. Running `python3 -m tools.health --full` to a verdict on a quiet
machine — load 18, not the ~145 that timed `SUITE-05` out through the entire build — turned two latent
reds visible that every prior phase had passed over because health never completed to a result.

- **`OG-234` — the commit-time placement gate refused a LEGITIMATE submodule commit.** A gitlink
  (index mode `160000`) points at a commit in another repository, so its staged bytes read as `None`
  and `scan_staged` fail-closed into a block — a false positive live since before the freeze
  (`9a1c011`), with `SUITE-06`'s retained *"a submodule must COMMIT"* counter-example failing unseen.
  Fixed by `_is_staged_gitlink`, the commit-time twin of `OG-226`'s non-blob skip: a gitlink cannot
  carry a header, so the skip never spares a classified file (falsified both ways, retained probes in
  `test_staged_scanner.py`).
- **`SUITE-04` lint debt.** Nine `ruff` findings — import order, two `subprocess.run` calls without an
  explicit `check`, an unsorted `__all__` — had accrued across the reverification's own edits under a
  pinned ceiling of `0`, invisible while `--full` timed out. Cleared.

The phase's thesis turned on the phase itself: a floor asserted but never run to completion is a floor
assumed, not proven. `OG-212` had already made the timeout a distinct verdict; this is the first close
to actually spend the quiet machine that verdict asks for.

---

## [0.7.4] — 2026-08-29 · The model recommendation, corrected by measuring it

`0.7.2` wrote the Phase-7 model split with a caveat: route Fable per-lane through the subagent
override *"rather than by changing the session CLI flag, whose resolution has not been tested
here."* **That caution was based on not having checked.** `claude --help` names `fable` alongside
`opus` and `sonnet` as an alias for the latest model, so the flag resolves. Fixing what the
measurement falsified is part of the task, not optional extra work.

### The recommendation changes direction

Previously: session on Opus, verifier lanes delegated **up** to Fable. Now: **session at the top
tier, routing DOWNWARD** to Sonnet and Haiku for mechanical lanes.

Two reasons, and the second is the load-bearing one:

- **The whole phase is the top tier's own description.** The portfolio routing table puts *final
  audits, security-critical design and adversarial verification* there, and that is not one lane of
  Phase 7 — it is Phase 7.
- **The two directions fail differently.** Both need an instruction to be followed. Forgetting to
  route a cheap lane *down* costs money; forgetting to route a verifier lane *up* costs the phase
  its only real evidence. **Downward fails safe on the axis that matters**, and given three
  consecutive phases closing with implementer-verified residue (`OG-190`, `OG-203`, `OG-209`), that
  is the axis to protect.

The caveat that survives, narrowed to what is actually unknown: **a resolvable alias is not proof of
entitlement.** If the session does not start at the top tier it must say so plainly in its first
report and route the verifier lanes up explicitly, rather than silently substituting a weaker tier
into the one place the tier changes the answer.

`PHASE7_SCOPE.md` §3, the launch command (`--model fable`) and its flag table all move together;
`STEP 4d` is rewritten and the command re-verified as one 15,523-character argument.

---

## [0.7.3] — 2026-08-29 · The field trial: the first thing that can test the self-containment claim

**Documentation only, and written deliberately BEFORE Phase 7 runs.** `docs/plan/FIELD_TRIAL.md`
expands `AFTER_1_0.md`'s Stream B — *run the engine on a project that is not this one* — from three
sentences into the programme that begins after `1.0.0` ships. It changes nothing Phase 7 does.

### What it is for, and why this repository could never do it itself

`HANDOFF.md` asserts in its opening lines that these files are self-contained and that **nothing
important lives only in a previous chat**. Nothing gates that claim and nothing here ever could:
every agent this project has used was present for the build. It has been asserted for six phases and
never tested. A **blind operator** — a model with no history here — is the only thing that can
falsify it, and the product claim underneath it: *can someone who was not here use this engine?*

### The fifth finding class

`AFTER_1_0.md` §3 lists four outcomes, two of which are findings. A blind operator produces a fifth
that none of the others can: **the engine could do it, and the operator could not find out how.**
That is a discoverability defect, it is invisible to anyone who already knows the answer — which is
every agent that has ever touched this repository — and for a tool of this kind it is the most
likely real-world failure. The programme treats it as the primary yield, not an afterthought.

### The design decisions worth naming

- **Two operators, not one.** The blind operator tests *reachability*; this project's own agent,
  running the same task independently, tests *depth*. Where they agree the engine is both correct
  and documented; **where they diverge, the divergence names which half is broken** — ambiguous
  documents or a non-deterministic engine. Neither is visible from a single run, and neither model
  adjudicates its own output.
- **The blind operator must stop rather than guess**, and say where the trail went cold. An operator
  that thrashes and eventually succeeds destroys the discoverability signal, which is the most
  valuable thing the run produces.
- **A declared stop rule.** Two consecutive rounds with no NEW CLASS — not *no findings*, since a
  round can produce instances of a known class indefinitely — plus a hard ceiling of six rounds,
  plus a final round on a **never-seen subject** that does not count toward the streak. A protocol
  run five times against one project has been calibrated to that project. Unbounded verification
  does not converge here; it gets interrupted, which is a worse ending than a declared one.
- **The trap, named with its guards.** The engine is being tuned by the thing testing it — the exact
  shape `OG-198` and `OG-204` are open records of refusing. So every calibration must be a CLASS fix
  carrying a counter-example falsified both ways, and **a finding is never closed by making the
  operator smarter**: adding a hint to the task statement converts a product defect into a coaching
  problem. If the answer was not findable from the repository, the repository is what changes.
- **Findings are recorded before anything is fixed**, or the record gets trimmed to what got fixed.
- **Real subject, copy or branch, never live material**, and the cross-project write needs a named,
  dated operator grant — a trial is not an exemption from project isolation.

### Why it is written before Phase 7 rather than after

A protocol authored after seeing what Phase 7 produced would, without anyone intending it, avoid
testing what Phase 7 got wrong. Writing it blind is `RULES.md` Rule 5 applied one level up: the
measure is fixed before the thing being measured exists. It pins **no number** Phase 7 will move —
every quantity in it is a command to run rather than a value to trust.

### A false red found by hitting it (`OG-212`)

Writing this release tripped a defect in the engine itself. `_run` collapsed `TimeoutExpired` and
`OSError` into one exit code, so a **timeout**, a **launch failure** and a **test failure** were
indistinguishable to every caller. An unrelated project drove the machine to a load average of 36;
the counter-example suite used its usual ~407 s of CPU but 783 s of wall-clock, exceeded the 600 s
budget, and `SUITE-05` announced *"python counter-examples FAILED"* — while a direct run of the same
suite reported `OK`, exit 0. **The pre-push hook runs health, so that false red blocks every push**,
and the wording sends the reader hunting a broken test rather than looking at the machine.

Fixed at the root: `_run` returns `124` for a timeout and `127` for an unlaunchable command, and
`_suite_failure` words the FAIL by cause. **The verdict stays FAIL** — a timeout can also be a
genuine hang, and a gate that passes on *it did not finish* would be worse than useless. Three
retained counter-examples, all pure, because a probe that had to wait out a real 600-second timeout
would never be run. The residual is stated in the row: the budget is still a fixed wall-clock number
on a machine whose load the engine does not control.

### Phase 7 is unchanged, and that is the finding

The question was whether this needed to go into Phase 7. It does not, and the reasons are
structural rather than preference: `PHASE7_SCOPE.md` §4.4 forbids new capability and §4.5 forbids new
corpus documents *during* that phase; Phase 7 also changes what `verified` means (`OG-207`) and what
rung 2 measures (`OG-204`), so a protocol written into it would calibrate against a moving target.
Phase 7's own doctrine already requires fresh agents that re-derive from the artifacts, which is all
the trial depends on. **No edit to the Phase 7 scope or launch prompt was required.**

---

## [0.7.2] — 2026-08-29 · What happens after the build ends

**Documentation only.** Two questions were asked that the repository could not answer, and both
turned out to be gaps rather than misunderstandings.

### The model split for Phase 7 is now a written decision, not an inference

`BUILD_PLAN.md` **D7** settles the *principle* — model routing is a per-phase process decision, and
the strong model writes spines and judges while the cheap one fleshes and loops — but nothing made
it concrete for Phase 7. `PHASE7_SCOPE.md` §3 now carries the lane table, and the launch prompt
carries it as **STEP 4d**.

The substance: **spend the top tier on the verifier lane, not on a later pass.** Phase 7 *is* the
final audit; there is no second one to save a stronger model for. And
`DEEP_VERIFICATION_PASS.md` says why the tier changes the answer here rather than merely the speed —
*a model checking its own output converges on its own blind spots and goes quiet long before it goes
correct* — so a weak verifier returns a **confident green**, which costs more than not running one.
The lane that matters most is **the round attacking Phase 7's own fixes**, because that is where the
implementer-verified residue would otherwise re-form for a fourth time; `OG-190`, `OG-203` and
`OG-209` are the first three. Both halves are written with their check-rather-than-assume caveats: if
the tier is unavailable, say so and run on Opus rather than silently substituting, and route it
through the subagent override rather than an untested CLI flag.

### `docs/plan/AFTER_1_0.md` (new) — the plan stopped at Phase 7 and said nothing about after

`BUILD_PLAN.md` has seven phases and then ends. Correct — the build does end — but nothing in the
repository answered *what then*, and a grep for any statement of it returned one unrelated line. The
new file answers it:

- **Phase 7 finishes purpose 1 and not purpose 2.** The build ships `1.0.0` and there is no Phase 8.
  Purpose 2 is a *measurement*, and a measurement has no last day. At `1.0.0` you stop building and
  start operating, and the engine is finished either way.
- **Operating it is a gap-finding machine, not maintenance.** The charter's own line: every defect
  the engine cannot catch here is a gap in the product, discovered for free.
- **Four outcomes, only two of which are findings.** A gate firing correctly is the engine working
  and adds nothing; a false positive and — far more valuable — a **silence where a careful reader
  objects** are the product backlog. The third is the one that takes deliberate effort to notice,
  because a gap announces itself as a clean run. Both findings in the `0.7.1` closeout were exactly
  that shape and ran green throughout.
- **No new register.** `OPEN_GATES.md`, `LESSONS.md` and `CHANGELOG.md` already hold all of it. Two
  registers of one thing is the drift this engine exists to catch.
- **One decision left deliberately open.** The phase gate's only legal deferral is
  `SCHEDULED (Phase N)`, and after Phase 7 there are no phases — so the vocabulary loses its forcing
  event, which is precisely what turned four retired dispositions into indefinite parking when the
  register carried 26 open rows with 19 of them parked. A release-based spelling is recommended and
  explicitly **not** ratified here, to be settled at the first post-1.0 finding, in the same change
  that teaches `cross_doc` the new word — otherwise the check stops adjudicating deferrals silently,
  which would be `L-38` recurring in the file that records it.

Wired from `BUILD_PLAN.md` §3 and `NEXT_SESSION.md`; both state it is **not a phase** and that no
register row may be dispositioned against it.

### Timing, stated because it looks like a contradiction

`PHASE7_SCOPE.md` §4.5 tells Phase 7 not to add documents to the corpus, and this release adds one.
That rule binds **Phase 7**, which has not started: every new document moves the charter's measured
counts, restales derived artifacts and invalidates the stamp that phase exists to make valid. Before
it starts is exactly when to add one. The charter's count moved 66 → 67 and `draft check` named the
line before it landed — the third time that gate has caught this class in two sessions.

---

## [0.7.1] — 2026-08-29 · Phase-6 closeout: the deferral guard had gone blind

**Process work inside Phase 6, not new capability.** The closeout swept the repository, found a
false green, fixed its class, and defined Phase 7's scope and anti-scope. Phase 7 itself has not
started.

### The finding: `cross_doc`'s phase-COMPLETE branch had been dead since Phase 4 (`OG-210`)

`cross_doc` refuses a `SCHEDULED (Phase N)` register row whose phase the plan marks COMPLETE, on the
stated ground that *a deferral to finished work is parked forever*. It answers *is N complete?* by
looking for a completion marker **inside phase N's own table row**.

Phases 1-3 carry one. **Phases 4, 5 and 6 shipped without one**, because completion had migrated
into the status paragraph at the top of the same file. Nobody decided to stop marking rows — the
convention simply lapsed, and with it the branch. Measured consequence: `OG-07` and `OG-63`, both
deferred to Phase 4 and both actually finished *inside* Phase 4, sat in the register's `## Open`
table for two further phases while every gate reported clean. The register over-reported its open
defects, and the one check written to catch that said nothing.

### Fixed, class first

- **`CONS-13` (new health check)** reconciles the plan's status prose against its phase-row
  completion markers, in **both** directions, and refuses a gap in the completed prefix. It **fails
  rather than passes when it can derive neither side** — a vacuous pass would rebuild the same
  blindness one layer up (`L-19`, `L-37`). Its bound is stated in its own docstring: the prose side
  reads a bounded vocabulary, and rewording past it breaks the check loudly.
- **`phase_rows` and `marks_complete` are exported from `cross_doc`** and imported by the new check,
  so the two readers cannot develop two notions of what a phase row is (`RULES.md` Rule 1). The
  single-row reader now delegates to `phase_rows`.
- **Phases 4-6 carry their markers** (`23e6354`, `d90722c`, `aaee4d1` — the commits that stamped
  each version). This made `cross_doc` name both stale rows at HIGH on the very next run: **the fix
  is falsified by the guard it repaired**, not by assertion.
- **`OG-07` and `OG-63` closed**, each with the evidence that they had in fact been finished by
  Phase 4 — `DocHeader`'s identity block, and `generator.check_figure_provenance` running before any
  format is written, with `tools/tests/test_figure_provenance.py` behind it.
- **`tools/tests/test_phase_completion.py`** — nine counter-examples. Six drive `CONS-13` in both
  directions; one drives the **relationship that actually broke**, removing a marker and watching
  `cross-doc` go blind on a planted deferral, then restoring it and watching the finding return; two
  pin the shared row definition and the marker vocabulary.

### And one layer up: the crash-recovery record (`OG-211`)

`docs/process/SESSION_STATE.md` is the first document a fresh session reads after a crash. It named
a project version three phases behind, a health floor five checks short, and instructed a recovering
session to **start Phase 4** — three phases after Phase 4 shipped. Its own stamp check `STRUCT-06`
passed and was right to: it validates the stamp mechanically and explicitly disclaims judging the
checklist. **`CONS-08` guards exactly those facts across every other handover document, and this one
was not on its list.** Added to the list — it fired at once with five stale claims — then the file
was rewritten in place as its own *one session, one state* rule demands, with per-session history
left where it already lived in `CHANGELOG.md` and `VERIFICATION_LOG.md`. A comment in
`tools/corpus_check/guards/stamps.py` that cited it by line number was re-cited by section, the
citation having already rotted by eleven lines.

### Written down

- **`docs/plan/PHASE7_SCOPE.md` (new)** — Phase 7 at full width: the nine rows it owns with each
  deliverable stated as something falsifiable, the order they must happen in and why, **eleven
  things it must refuse to do** with the reason for each, the one step no agent may perform, and its
  exit condition.
- **`LESSONS.md` L-38, L-39, L-40** — a convention a gate reads and nothing enforces is a gate with
  an expiry date; fixing the source and re-reading the source proves nothing about the artifact you
  publish; a ratchet whose memory is `HEAD` has no memory, and a lab that `git init`s its own tree
  cannot test one.
- **`NEXT_SESSION.md` rewritten** — it claimed "five rows" while listing six of the nine, and cited a
  node count two behind the map.
- **`START_NEXT_SESSION.md` restamped** for the new floor, the nine rows, and the anti-scope.
- **`CHARTER.md`** tracked-document count moved with the new document, named by `draft check` before
  it landed rather than repaired afterwards.

### Three probes that had borrowed their condition from the corpus

Marking Phase 4 complete broke four retained tests, and each break is `L-37` — *a probe must create
or derive its condition, never borrow it* — arriving from a different direction. They are fixed at
the root rather than re-baselined:

- **`CrossDocIsFalsified` planted a deferral to the real Phase 4.** Once that phase was correctly
  marked complete, the guard's COMPLETE branch fired before the does-not-name-it branch and the
  probe failed for a reason unrelated to what it tests. Its sibling — the acceptance half — borrowed
  the live row `OG-07`, and the moment that row was closed it began **passing vacuously**, because
  `assertNotIn` is satisfied by absence. *The quieter half of the break is the one that kept
  reporting green.* Both now plant a probe-owned plan, and the acceptance test asserts a refused row
  **in the same run**, so it cannot pass while the guard is finding nothing. A third probe was added
  for the COMPLETE branch itself, on the owned fixture.
- **The first draft of that fixture tripped the guard's own vocabulary.** Its phase rows ended
  *"when it is done"*, and `\bDONE\b` is one of seven completion spellings, case-insensitively — so
  every row read as finished. Recorded in place: a fixture is subject to the guard's vocabulary, and
  seven spellings is enough that *"surely this reads as unfinished"* is not a safe assumption.
- **`StateFactExemptionsAreClauseScoped` kept a private copy of `CONS-08`'s document list.** Adding
  `SESSION_STATE.md` to the check left the lab writing four of five documents, and three probes
  failed — including the baseline whose entire job is to prove the others are not passing for free.
  The list is now the module-level `STATE_DOCS`, derived by the probe rather than restated.

### Swept, and clean

No orphan documents (every tracked Markdown is referenced by something), no dead branches, no
worktrees, no stashes, no junk files, one empty ignored directory removed. The two byte-identical
file pairs that remain are **declared aliases with tests behind them** — `project-theme` /
`project-theme-dark`, and the vendored `force-graph.min.js` shared by two independent graph engines
— and are recorded here so a future sweep does not "tidy" them away.

### Not claimed

This session's own work is implementer-verified only, exactly like the residue `OG-209` records for
Phase 6. It is falsified in both directions by retained counter-examples and by the repaired guard
itself, which is real evidence — it is not an independent second opinion, and Phase 7's
reverification is where it gets one.

---

## [0.7.0] — 2026-08-29 · Phase 6: procedure encoding

`BUILD_PLAN.md` row 6, against an acceptance set `A-1`…`A-8` written into the plan before any code
existed and frozen at `f67765dcfad1c32e`.

### The completeness report — *where did we stop*, from evidence

Three states, per node: **sketched** (named, but what is inside is not established), **documented**
(contents, edges, gatekeepers and probes established), **verified** (all of that, *and* the owning
document is governed, claims a verified state, and carries a stamp that still covers its body).

**`verified` is not rung 5 of the ladder, and the distinction is the phase's whole point.** The
ladder reads a header's CLAIM — Phase 5 corrected its own docstring for pretending otherwise. This
report is required to distinguish the three states *from evidence*, so it finds the stamp, resolves
its commit, and compares the body at that commit with the body now. A claim with no stamp behind it
reports `documented` and says so. When the evidence cannot be gathered — no git, no stamp, an
unreadable file — **the state falls and names the cause**; it never rises.

The measurement, on this repository: `sketched` 4 · `documented` 103 · `verified` **0**. Zero is
honest, not an oversight: no document that owns a container is governed by the doc-system yet, which
is `docs/CHARTER.md`'s purpose 2 stated as a number rather than an intention.

### The ladder ENFORCED — a ratchet, checked in both directions

Each container declares a `depthFloor` in `system.spec.json`. Measuring below it is a regression.
**A floor written *beneath* the measurement is refused too**, because that is the same regression
made permanent in advance and it is the easier one to slip past review. A ratchet that can be
loosened is a suggestion.

### The document lifecycle — six steps, each read from its owner

*tag / wire / date / version / changelog / stamp*, per governed document, derived from the header,
`DOC_MANIFEST.md`, the archive, `CHANGELOG.md` and the stamp. **Nothing here is enforced by the
report** — `classification` gates the tag, `manifest_drift` the wire, `identity` and `stamps` the
version and the stamp. Two enforcers of one rule is the defect this engine exists to catch; a report
beside an enforcer is not. Current state: 16 of 24 steps complete across 4 governed documents.

`docs/process/AUTHORING_CONTRACT.md` states the contract and names which gate owns each step;
`skills/doc-lifecycle/SKILL.md` is how to carry it out. A probe asserts every guard the contract
credits with enforcement is actually in the live registry — a procedure claiming a check nobody runs
is the defect, one document over.

### `OG-198` closed by the phase that accepted it, not by the phase that measured it

The six modules with no docstring — `tools/__init__.py`, `tools/project_index/__init__.py` and four
`__main__.py` shims — now say what they are for, and no container reports `sketch`.

**Four containers moved to `shape` rather than `modules`, and that is left standing.** Rung 2 tests
"are the contents enumerable" by counting public top-level definitions, which a delegation shim
legitimately has none of. Widening it here would have raised four floors in the same change that
authored them — the self-serving edit `OG-198` was held open to refuse, one layer up. Recorded as
`OG-204` and scheduled to Phase 7, which accepts it by name.

### The verification round — three verifiers, and the headline claim was refuted

Each was handed the CLAIM and never the diff, read-only against the committed sha. **All three
refuted something, and the deepest findings were about the two things this phase asserts hardest.**

- **The published state definitions were not what the code measured.** `COMPLETENESS.md` said
  `documented` meant "contents, edges, gatekeepers and probes established" while the code asked only
  for rung 2 — **73 of 103 documented nodes failed the published definition** — and `verified` said
  "all of that, and the document" while re-checking only the document. In a lab, a module that no
  gate reads and no counter-example names reported `verified`. Both halves are fixed, in opposite
  directions: `documented` now says what rung 2 establishes, and `verified` now REQUIRES rung 4.
  The word "edges" is gone from both, because `depth.py` states plainly that no rung tests them.
- **The ratchet did not ratchet.** It was `floor == depth`, an equality lock with no history, and a
  verifier defeated it in one line: strip a docstring so a container falls (correctly red), then
  lower its `depthFloor` to match — `verify` clean, `completeness` level, every probe green. A
  container went from `internals` to `sketch` and the engine reported level. It now reads the floors
  at `HEAD` through git, the way the `stamps` guard gets its memory, and a floor below the committed
  one is refused whatever the current measurement says. Falsified with the verifier's own attack.
- **Nothing in the 504-test suite could tell a three-state report from a two-state one.** A verifier
  hardwired the stamp check to always fail, making `verified` structurally unreachable, and the
  entire suite stayed green — the probes proved only the denial. There is now a positive control
  that builds a verified node end to end through unmodified machinery, and it reddens under exactly
  that mutation.
- **Three of the six lifecycle steps did not read the artifact they name.** `version` was
  **structurally unreachable** (it resolved a path slug while `archive cut` writes the header id, so
  no governed document could ever satisfy it); `wire` was a byte scan of the manifest FILE rather
  than its type-prefix ROW, so a comment saying a document *"was deleted and must never be built"*
  marked it wired; `date` never read the header field and accepted a document that merely discussed
  it, an empty value, or a `produced_by`. `tag` was half tautology and ignored the `surface` its own
  comment claimed. `stamp` accepted any kind, disagreeing with this same module's other half.
- **My probes shared the subject's blind spot again.** The governed-set probe used the code's own
  expression; the `version` probe called the identical wrong id expression, ran over zero subjects,
  and guarded its vacuity with `0 == 0`. Four of six steps were never falsified. Every step is now
  falsified independently, and the probes' oracle is written separately — though the first attempt
  at "independent" matched a doc-system header shown as an EXAMPLE in a fenced code block, which is
  a reminder that naive is not the same as independent.
- **The authoring contract credited an enforcer that does not do the job and one that does not
  exist.** The `tier` gate lives in `export_sanitizer.py` and decides export eligibility, not header
  presence; and **step 5 has no per-document enforcer at all** — `CONS-05` compares
  `PROJECT_VERSION` to the newest heading and never looks at a document. The contract now says so.
  Its probe validated 2 of ~7 claims and passed on fabricated gate names; it now checks both the
  guard and the gate registries, and refuses `flying_pony`.
- Also fixed: the report hardcoded prose that contradicted its own derived numbers (rendering a
  model with 8 verified still printed *"`verified` is 0"*); percentages truncated so the row summed
  to 99%; the "what to fix first" section listed only `sketched` nodes while calling itself the
  actionable half, hiding the 73 shallow `documented` ones; `--check` added no strictness and passed
  vacuously with no spec at all; and a JSON `true` was accepted as a floor of 1.

### Measured

- `python3 -m tools.blueprint completeness` → 107 nodes classified, ratchet level across 9
  containers, exit `0`
- 21 retained counter-examples added; the suite goes 489 → 510 defined
- `-k completeness` 7 · `-k lifecycle` 9 · `-k floor` 6 — each selector covering its class, and
  sweeping in one or two neighbours whose names share the token (measured, not assumed)
- ruff `0`, mypy `--strict` `22` — the pinned ceiling, unchanged, with zero new debt
- corpus clean at 65 tracked documents (the charter's number, re-derived twice by the draft gate as
  the two new documents landed)

## [0.6.0] — 2026-08-29 · Phase 5: the blueprint layer

The map stops being a list of names and starts answering questions. `BUILD_PLAN.md` row 5, against
an acceptance set `A-1`…`A-9` written into the plan before any code existed (`RULES.md` Rule 5).

### The authored half, and the gate that keeps it honest

`system.spec.json` is the **only** hand-written input to the map. It carries what no artifact in
the tree owns — which containers to think in, each one's purpose, and the document that owns it —
and nothing else. Everything around it stays derived.

`python3 -m tools.blueprint verify` then checks every fact the spec asserts against the tree and
exits 1 on seven drift classes: a container naming a package that matches nothing, a module no
container claims, a module two containers claim at equal specificity, an owning document that does
not resolve to **tracked** content, a duplicate container id, an unreadable spec, and a stale
committed map. Each was planted in a throwaway copy of the tree, shown red, and restored.

**There is deliberately no catch-all container.** A catch-all would turn the `unassigned` finding —
the one that fires when a package is added and nobody updates the decomposition — off permanently.

### Depth, measured rather than asserted

`D4`'s C4 ladder, levels 0–5, where a node's depth is the highest rung whose evidence exists **and**
all of whose lower rungs hold. Contiguous on purpose: a module with a test and no docstring would
otherwise report `internals`, which reads as "we went deep here" when what happened is that nobody
wrote down what it is for. A container is only as deep as its shallowest module.

The first run of it reported something true and unflattering: 6 modules sit at `sketch` because
they have no docstring, which holds four containers at depth 0. Recorded as `OG-198` rather than
fixed, because tuning the tree to a metric introduced in the same session is how a metric stops
measuring anything.

### Gatekeepers — "what will refuse me if I change this"

Derived from the gates themselves: a registered guard, health check or hook is a gatekeeper of a
module when it **imports** that module, or names its dotted id as a whole token, or names its real
file path. 146 relationships over 105 modules. The emitted-gate half reuses `_gate_labels_via_ast`
**by import** rather than by copy — `OG-195`'s closure note says that helper had already been the
second consumer of one root twice, and this is the third.

The first version of this was a bare substring test and it was wrong in **both** directions; the
verification round below is what measured it.

### The six surfaces Phase 4 measured itself needing

`blueprint/SURFACES.md`, derived from the artifacts that own them: the JSON schemas (which the map
never mentioned at all), the configuration surface and its environment variables, the CLI command
and flag inventory, the guard contract and what registering one costs, the figure kinds, and **what
each health check asserts** rather than merely its id.

Building the CLI inventory found two defects in its own first version, both fixed: nested
subcommands were flattened, so the map advertised a `cut` command that does not exist instead of
`archive cut`; and unassigned `add_parser` calls were invisible, so the blueprint package reported
**no commands at all** in the map that exists to describe it.

Two health checks — `SUITE-01` and `SUITE-02` — had no docstring, so the map could not say what
they assert. Both now have one.

### ELK auto-layout (`D5`), at zero new dependency

`elkjs` was already in the tree as a transitive dependency of `beautiful-mermaid`. The bridge hands
it a sorted edge list and gets back coordinates docgen's own renderers consume, which closes the
gap docgen has carried since the beginning: every node diagram needing hand-supplied `x`/`y`.

**The verdict is split into what ELK owns and what the renderer owns, and that split is the
honest part.** Node placement — overlaps and docgen's 1.5×-short-side gap rule — is ELK's job, must
be **zero**, and fails the command when it is not. It reached zero by encoding the gap rule in the
layout options instead of iterating by hand, which is exactly the cost D5 named. Edge routing is
not: docgen draws every edge as a straight line between two centres and `Edge` carries no
waypoints, so a graph this dense cannot be drawn cleanly at any placement — measured across
`layered`, `force`, `mrtree` and `stress`, at both package and container level, and the count never
reached zero. So no SVG is written, because writing a diagram the gate refused is the defect Phase 4
fixed. Recorded as `OG-199`.

### The derived SQLite index (`D1`), with FTS5

`python3 -m tools.blueprint index` builds `.blueprint/index.db` — gitignored, rebuildable, never
authoritative. Eight tables plus full text over the corpus, and it **refuses to write an empty
one**: `RULES.md` Rule 6's corollary, paid for by a navigation layer that once reported 1 artifact
for 295 files and 0 nodes for 77 modules. `query` runs the canonical joins (*which modules have no
document*, *where did we stop*); `search` runs FTS5 over the corpus.

### One duplication removed rather than left

The Phase-5 probes needed a throwaway-lab helper that `test_corpus_check.py` already had, and
writing the second copy WAS the finding — the two had already drifted, one carrying two `type:
ignore` comments the other did not. Both now import `tools/tests/lab.py`. `RULES.md` Rule 1.

### The verification round, and what it cost

Five independent verifiers, each handed the CLAIM and never the diff, working read-only against the
committed sha. **They refuted the phase's headline exit condition, and they were right to.** What
came back, and what it changed:

- **CRITICAL — the map published a command that cannot run.** `python3 -m tools.project_index` was
  in the CLI surface; that package has no `__main__.py`, so it errors. A map whose whole purpose is
  to save a reader from the tree was sending them at a broken command. The invocation is now
  *derived* — package when a `__main__.py` exists beside the parser, module id otherwise — and a
  probe executes `--help` for **every** published entry point.
- **The gatekeeper relation was wrong in both directions.** `_names_module` was
  `module_id in source`, so `from tools.docgen import adjudication` — which imports and *executes*
  it — was invisible (15 real relationships missing, and stubbing `adjudication` turns two health
  checks RED), while the root node `tools` collected 38 gatekeepers because every gate contains that
  substring. Now resolved with `ast` imports, whole-token dotted ids and real package paths
  (`x/y/__init__.py`, which the old path builder never produced). `depth`'s `pinned` rung inherited
  the same defect and was wrong for 22 modules.
- **8 of 26 environment variables did not exist.** They were synthesised from an
  `ENGINE_<SECTION>_<KEY>` convention neither resolver follows; two verifiers independently set them
  and measured no change. And `ENGINE_CONFIG_PATH` — which replaces the *entire* config file — was
  missing. Both halves are now derived from the files that actually read a variable.
- **The schema inventory listed 5 of 9**, because the directory was pinned rather than derived; and
  `doc_manifest.schema.json` reported no required fields because its row shape lives in `$defs`.
- **`tools.docgen.i18n` rendered with no interface at all** — its flags hang off
  `add_mutually_exclusive_group`, which the scan could not see. Flag `help=` strings were being
  discarded too, so *"which flag controls Y"* was unanswerable from data in the same call.
- **A false claim in `depth.py`'s own docstring**, the `OG-193` class: it said rung 5 required a
  verified state *"that the identity guard has not refuted"*, and that conjunct was never
  implemented. A verifier proved it — `identity` reported CRITICAL while the map reported depth 5.
  The claim is corrected, not the code: the map REPORTS a header's claim, the guard ADJUDICATES it.
- **The class root was left unfixed in a fourth consumer.** `symbols._defined_names` records
  `OG-166` — *a comment is prose about the code, not code* — and counts itself the third consumer.
  `CONS-07` was a fourth, still resolving RULEBOOK citations with a regex over raw text, so a symbol
  appearing **only in a comment** resolved. Falsified live with a planted `GHOST_RANKER_XYZ`. It now
  imports `_names_or_text`, and the live tree passes the stronger check.
- **Two of my own probes could not see any of it.** The schema probe globbed the same pinned
  directory as its subject; the configuration probe asserted only that a name *starts with*
  `ENGINE_`. Both rewritten to take their subject set from the tree.

Also corrected: `layout --check` never compared the SVG (a verifier planted garbage under that name
and got "current"); `compute()`'s "never raises" leaked a traceback on a malformed bridge reply; the
tier label `(no front matter)` was false for six `skills/*/SKILL.md` files that have front matter but
no doc-system header; "sixteen dotted gates" is 17; the guard-registration cost is three edits, not
two, *because this phase made it so*; and `SUITE-03`'s assertion was published as a sentence fragment.

### The SECOND round — the fixes were sent back to the verifiers that found the defects

`DEEP_VERIFICATION_PASS.md` §7: *re-run the verifier that found it — a fix is not done because the
fixer says so.* Two lanes were resumed against the fixed commit and **both found the fixes
incomplete**, one of them severely.

- **CRITICAL — a fix that reached the model and never the document.** The `environment` surface was
  derived correctly into `SYSTEM.json` and **not rendered into `SURFACES.md` at all**, so the finding
  it existed to close — `ENGINE_CONFIG_PATH` being undiscoverable — was still open for the document
  that calls itself the lookup table. Rendered now as §6, and a probe asserts every modelled surface
  reaches the rendered file, because *modelled is not published*.
- **HIGH — a regression I introduced.** Dropping ancestor packages entirely, to stop the root `tools`
  collecting 38 gatekeepers, made **the git moat** report that nothing guards it: both hooks reach
  `tools.docgen.hooks` by running its submodule, which executes the package. The rule that matches
  reality is neither extreme — an ancestor counts when its `__init__.py` executes something.
  Measured, not guessed: `tools`, `tools/docgen` and `tools/lib` have **zero** non-docstring
  statements (a verifier mutated `tools/docgen/__init__.py` and all eleven claimed gatekeepers
  passed), while `hooks` and `corpus_check` run real code.
- **HIGH — the class root was unfixed in a FIFTH consumer, and it was this module itself.**
  `symbols.py` exported `_names_or_text` to `CONS-07` and kept a raw regex in its own branch 2, 154
  lines below. One planted symbol, existing only inside a comment saying it does not exist, cited
  twice in the same shape: `CONS-07` refused it, `symbols` passed it.
- **HIGH — "two edits" was still rendered above a three-item list.** The corrected number reached
  `SYSTEM.json`'s `cost_note` while the renderer hardcoded the sentence. Both now derive from one
  count, and `ARCHITECTURE.md` — which the first fix did not touch — says three.
- **A gate that runs a module as a SUBPROCESS was invisible.** `BUILD-01` shells out to
  `docgen build`; 14 renderers underneath reported that nothing guards them, and a verifier proved
  `BUILD-01` turns red when any of them breaks. Route 3 now follows `python3 -m X` into X's
  transitive import closure.
- **`ENGINE_ROOT` was published as live** — a JS module constant that happens to match the naming
  shape. Four more variables were credited to files that only mention them in prose, and the reader
  set was a six-file allowlist inside a function claiming to derive it. An environment variable is
  now proven by an ACCESS (`os.environ`, `process.env`, `$VAR`) across every tracked source file,
  and a declared `envVar` counts only for the sections a resolver actually routes that way — which
  is itself derived, and correctly excludes `browsers` and `security`.
- **`pinned` meant *mentioned*, not *exercised*.** Six modules sat at `internals` on a name in a test
  comment. Rung 4 now requires an import or a real path.
- **A determinism defect in my own code, caught by the suite it broke.** The import closure memoised
  across nodes while sharing one cycle guard, so a cached answer depended on set-iteration order —
  which varies with `PYTHONHASHSEED`. `blueprint build` immediately followed by `blueprint verify`
  reported the freshly written map STALE. The existing determinism probe covered the ELK layout and
  not the model; there is now one for the model, across three seeds in separate processes.
- Also closed: alias-imported `ArgumentParser` was invisible (and the probe shared that blind spot —
  it now uses an independently written detector); a second parser in a package with a `__main__.py`
  could steal the package invocation; the `$defs` walk took the alphabetically first match instead of
  the one the schema references; three live sites still said "sixteen" dotted gates; the gate-label
  exemption was branch-scoped, so the fully-qualified spelling was still reported.

### Measured (after both rounds)

- `blueprint verify` → clean over 9 containers, 105 modules, 71 tracked `.md` files, 5 derived files
- 105 of 105 modules owned exactly once; 0 unassigned, 0 ambiguous
- gatekeepers: 272 `guarded_by` + 37 `emits` = 309 relationships across 49 guarded modules
- depth distribution: `sketch` 6 · `modules` 50 · `connections` 19 · `internals` 30 · `detail` 0
- surfaces: 9 schemas · 26 settings · 26 live environment variables · 10 entry points · 11 guards ·
  17 figure kinds · 36 health checks — **all seven rendered**, asserted by a probe
- the model is byte-identical across separate processes at three different hash seeds
- ruff `0`, mypy `--strict` `22` — the pinned ceiling, unchanged, with zero new debt
- ELK layout deterministic across 11 independent runs (verifier-measured, including shuffled input);
  0 placement findings, 39 edge-routing findings

## [0.5.2] — 2026-08-24 · Both closures were refuted, and both refutations were right

`OG-191` and `OG-194` were found AND fixed by the same session, so both closures went to
independent verifiers handed the claim and never the diff. Both came back with real defects. This
entry exists because the closures in `0.5.1` were not as clean as they were reported.

### `OG-195` — the `OG-191` closure was incomplete in four ways

**A 17th gate was still invisible.** `identity.py` writes `Finding(gate=GATE, ...)` against a
module constant; the widened regex needed a string literal, and the constant scan required the name
`_GATE`. So a blocking, CRITICAL-emitting gate sat unranked while CONS-04 reported full coverage
over 34 of 35. A regex cannot fix that class, only postpone it — the next site spells the constant
differently — so the scan resolves module-level constants with `ast`. `LESSONS.md` L-24 already
said this: *parse structured source with ast, do not scan it*.

**Three gates were exempted on a reading of their names, not their messages.** `chart.rule`,
`iso3d.rule` and `layered.rule` each also emit a legibility cap — a 6-slice cap, a 24-box cap, a
4-layer cap. That is precisely the tie used to justify mapping their `.collision` siblings to row 9,
so exempting them contradicted the reasoning written beside them.

**`sequence.collision` carried four referential errors** — *unknown src actor*, *duplicate order* —
so a reference error was annotated with *legibility wins; expressiveness is bounded by the contrast
floor*. Those moved to a new `sequence.rule`; the geometry findings kept `.collision`.

**The invariant replacement was a regression on one axis, with a counter-example to prove it.**
Exempting `figure_provenance` and deleting its mapping in the same change was caught by the old
blunt allowlist and accepted by both replacements. Now asserted properly: a `visual-rules` gate
with no dot in its name is a GENERAL rule, and a general rule may never be exempt nor unmapped.

**And the shared root bit for the third time.** `test_gates_and_cache`'s `_emitted()` had already
been widened alongside CONS-04 once; when CONS-04 moved to `ast`, the probe stayed on regexes and
reported `identity` as a dead `PRECEDENCE` entry. It now IMPORTS the resolver instead of
reimplementing it. Two implementations of one question disagree the moment one improves.

CONS-04 now reports 36 gates, all positioned.

### `OG-196` — the `OG-194` closure overclaimed

Re-punctuating the very repro that closed it got through: `Revenue: 4.2M USD ARR, 87 pct margin`
built clean and rendered verbatim. So did `₹500 crore` — the currency class was four hardcoded
symbols — and `1.500,00 €`, with the symbol trailing and period grouping. The register row had
disclosed a narrower residual than the truth.

**The false positives mattered more.** `Covered by Patent 10,123,456` BLOCKED a build. That is
citation-shaped content the detector could not tell from a measurement, and an author who hits it
once routes around the gate — which `OG-194`'s own reasoning warned about.

So the posture changed before the pattern did. For a structural figure this is now **advisory**,
the contract Gate 4 carries for the same stated reason: a semantic net over free prose is
paraphrase-fragile and must never be the sole moat. `--strict` promotes it. Once a false positive
costs a line of output rather than a build, the detector can afford to be generous — twenty
currency symbols, ISO codes either side of an amount, trailing symbols, `percent`/`pct`/`per cent`,
the full-width `％`, comma grouping — while masking URL percent-encoding and skipping
identifier-led comma groups. Seventeen cases falsified both ways.

**The blocking half of L16 does not depend on any of this.** A figure kind that declares a data
series must still name a resolvable source; that is structural, with no guessing in it. RULEBOOK
L16's Status now states the two postures instead of implying uniform enforcement, and what is still
undetected — bare measurements, unit-suffixed figures, scientific notation, numeric series in raw
`mermaid` source — is written at full width in `OG-196`.

Rulebook `1.2.13` → `1.2.16` across three L9 re-baselines; `CONTRADICTION.md` cut to **v4**.

### `OG-197` — and one defect found by committing it, in the same hour

The third re-baseline touched `RULEBOOK.md` only, and `CONTRADICTION.md` was cut afterwards out of
habit. v5 landed **byte-identical to v4** — the same sha256 recorded twice, two directories, one
document state, and a supersession derivation that would report v4 superseded by a copy of itself.
The duplicate was removed before it was committed, and `archive cut` now measures the freeze state
first and refuses when the live bytes already equal the newest snapshot. A retained probe asserts
both directions: the refusal, and that a real edit still cuts normally.

Worth stating plainly because it is the pattern this whole phase keeps meeting: the archive gained
its freeze check in Phase 4 and nothing used that check to protect the archive's own writer.

## [0.5.1] — 2026-08-24 · Both Phase-5 blockers closed

The two rows Phase 4's adversarial round raised are closed, and Phase 5 is unblocked. Both were
found and fixed by the same session, so both closures went to independent verifiers —
`DEEP_VERIFICATION_PASS.md`'s load-bearing law is separation of duties, and it binds a closure as
much as a build.

### `OG-191` — sixteen gate labels the coverage check could not see

`tools/health` CONS-04 scanned for `gate="…"` with `[a-z0-9_-]+`. No dot. So `geomap.source`,
`chart.rule`, `visual.collision` and thirteen more were invisible, none had a `PRECEDENCE`
position, and `_precedence_rank` scores an unlisted gate at `len(PRECEDENCE)` — a **blocking**
"this figure has no data source" finding sorted underneath a LOW note about a paraphrase.

Each of the sixteen was classified from the messages it emits, not from its name:

- **`.source`** (2) enforce L16 one figure kind at a time, written before the general gate existed
  → mapped to `l16`, row 8, alongside `figure_provenance`.
- **`.collision`** (7) fire when labels overlap or fall under a minimum gap → mapped to `l21`,
  row 9, the expressiveness-versus-legibility tie. Row 9's text names the *contrast* floor, so the
  attachment is slightly broader than its wording; that is stated in both places rather than left
  to be discovered.
- **`.rule`/`.bounds`** (7) report malformed or out-of-range input — *"bar chart has no items"*,
  *"lon outside [-180, 180]"*, *"matrix shape must be 3x4"*. No second law wants those accepted, so
  there is no tie to break; declared exempt with that reasoning rather than given rows that could
  never fire (`L-03`).

**The identical blind pattern sat in a second consumer** — `test_gates_and_cache.py`'s own
`_emitted()` — and was widened with it. Guarding one of two consumers of a shared root is Rule 1's
own failure mode, and widening CONS-04 alone would have left the test asserting the property over a
universe that excluded every gate the widening exposed.

**A pre-existing invariant was replaced rather than relaxed.** The exempt-set probe asserted *only
advisory and run-state gates may be exempt* — a proxy that held only because nothing else was
exempt yet. Exemption is about whether two laws contend, not about which spine class a gate sits
in. It now asserts the two properties that carry weight: no source-of-truth, security or **registry**
gate may be exempt (registries joins explicitly — `manifest_drift` is a real header-versus-registry
conflict, protected before only as a side effect), and **no gate may both carry a contradiction
mapping and declare it needs none** — which is what actually stops `figure_provenance` being
quietly exempted out of row 8.

CONS-04 now reports 34 gates, all positioned, and passes because it passes.

### `OG-194` — L16 reached numbers a figure declares, not numbers a figure writes

A `flowchart` node labelled `Revenue: $4.2M ARR, 87% margin` with `data_sources: []` built clean and
rendered verbatim. The provenance gate did what it declared; the law was broader than the gate.

Closed by making the law reach, without making the gate absurd. Structural kinds are still not
asked for a data series — that is the provenance theatre they were exempted from. They are asked
about **quantities they render as text**: currency amounts, percentages, thousands-separated
figures. `Stage 2`, `HTTP 200 OK`, `v1.2.13`, `RULEBOOK L16` and `Gate 3b` are identifiers and stay
accepted, because a gate that fires on those becomes untrustworthy within a day and an untrustworthy
gate gets bypassed — the same reasoning `counts._WORD_NUMBERS` records for admitting only `ten`.

The harvest walks the spec recursively rather than naming label fields per kind, so captions and
node notes are covered, and the six structural kinds — which share no shape — are covered by one
implementation. **Residual, stated rather than discovered:** a bare number that IS a measurement
(`Revenue 4200000`) is not detected. Separating a measurement from an identifier in free text is not
something a regex can do, and claiming otherwise would be the overclaim `OG-193` exists for.

### The rule layer moved again, and the archive caught it

`CONTRADICTION.md`'s "which rows can fire" table named one gate for row 8 and one for row 9; both
now name more. Rulebook `1.2.12` → `1.2.13` through the L9 two-step, and `CONTRADICTION.md` cut to
**v3** — its third supersession, each one caused by real work rather than by exercising the
machinery. The `identity` gate reported the drift as CRITICAL before the cut, from the bytes.

## [0.5.0] — 2026-08-24 · Phase 4: document identity + archive

`BUILD_PLAN.md` row 4, closed against the acceptance set `A-1`…`A-9` written before any code
existed. Two lines deviated and both say so in place rather than being quietly reworded.

### Document identity (`OG-07`)

`DocHeader` gains `version`, `revision`, `produced_by` and `verified_state`, all optional, so every
document that predates them keeps parsing and validating unchanged — identity is adopted one
document at a time, which is the only way a gate over an existing corpus lands without failing
every file on the day it ships. `version` is the archived generation; `revision` counts edits since
that cut, which makes `revision: 0` a claim with teeth: it asserts the live bytes ARE the archived
bytes, and the archive re-derives that rather than believing it.

`verified_state` is deliberately two values. `superseded` is **not** among them — a version is
superseded exactly when a higher one exists, so storing it would be a hand-maintained second answer
that goes stale on the next cut (`RULES.md` Rule 2). `version: true` is refused explicitly, because
`bool` is a subclass of `int` in Python and an unguarded type check reads it as version 1.

### The archive

`docs/archive/<id>/vN/` plus a machine-written `HISTORY.md` carrying only what a directory listing
cannot re-derive: the cut date, the commit, who cut it, and the snapshot's sha256. `docgen archive
cut` and `docgen archive list` are the surface. There is no `docs/current/`: the live tree IS
current, and relocating every governed document would break every path every other document cites
for nothing the archive does not already give.

A document with front matter has its `version`/`revision` written back; one without — this
repository's hash-locked rule files are the worked example — is left untouched and carried by the
archive alone, so freezing them needed no L9 re-baseline.

### Three documents frozen, and one of them superseded the same day

`TAXONOMY.md` and `DOC_WRITING_DOCTRINE.md` are frozen at v1. `CONTRADICTION.md` reached v2:
the provenance work below made its row 8 fire for the first time, so the row's recorded outcome
stopped being true and the file changed under RULEBOOK L9 (rulebook `1.2.11` → `1.2.12`). The gate
caught the drift **before** v2 was cut, and v1 survives byte-identical — supersession demonstrated
on a real locked rule file instead of a fixture.

### Figure provenance is a gate (`OG-63`)

RULEBOOK L16 — *a number with no resolvable `DataSource` fails the render* — was enforced for two
figure kinds out of eleven. Every other numeric spec declared `data_sources` with an empty default
that nothing read. The dispatch table now declares which kinds carry data, the check runs over that
derived set, and `EChartsFigureSpec` gained the `data_sources` field it never had — six ECharts
figures in this repository could not have been sourced even by an author who wanted to.

The gate's own new edge was attacked and closed: a `data_sources` entry with an empty `ref`
satisfied a non-empty-list check completely, which is worse than declaring none because the figure
then reads as attributed to everyone downstream. A source must resolve to a `ref` or a `url`.

`CONTRADICTION.md` row 8 now maps to the `figure_provenance` gate. It had a resolution recorded for
a conflict that could never be reached.

### `docgen build` reported BLOCKED and wrote the artifact anyway

Found while wiring the gate, and older than it. `run_gates` does not run `validate_header` or the
figure checks; those were computed, merged into the reported result, and **not** consulted before
writing. Measured on a document with a blocking `identity` finding: `docgen build: BLOCKED` on
stderr and the HTML on disk. Fixed at the root — every write is now gated on the pre-format
blocking findings, so the header findings that were already being ignored are covered too, not just
provenance.

### A stamp could never have been accepted

The `stamps` guard compared a stamped file against its stamped commit with `git diff`, which also
sees the stamp line — and the file at the commit a stamp names can never contain that stamp, since
writing the sha in is what changed the file. A fixed point would need a document whose bytes at
commit C include `sha(C)`. So the guard's accepted state was unreachable and it could only ever
fire. Both it and the new `identity` guard now compare the **body**, with stamp lines stripped from
both sides. `PROVENANCE.md`'s real drift is still detected — verified, not assumed.

### One predicate, three consumers

Archived snapshots are history, not live claims, so the guards must not judge them. Excluding them
from `Corpus.markdown` alone left `tools/health` CONS-09 counting them: the health check said 67
tracked documents and the `counts` guard said 61, within minutes of each other. Both now call
`identity.is_archived_path`. Two answers to one question is the bug, whichever answer is right.

### Probes that had borrowed their conditions

Two counter-examples in `test_corpus_check.py` broke because Phase 4 registered an eleventh guard —
one pinned the literal baseline `11`, the other asserted that the spelling *"ten guards"* resolved
to the live count. Both now derive what they measure: the baseline is read before the mutation, and
a spelling is asserted to resolve to the number it spells. Six documents that restated the guard
count were repaired by deletion rather than correction, per Rule 2.

### Recorded, not fixed

`OG-191` (**BLOCKS_PHASE_5**) — 16 emitted gate labels contain a dot, which CONS-04's label regex
cannot match, so none of them has a precedence position and a blocking finding from any sorts below
every advisory. Found while wiring `figure_provenance`; closing it needs a precedence position and a
contradiction decision for each of the 16, several requiring new matrix rows and another locked-rule
re-baseline. `OG-194` (**BLOCKS_PHASE_5**) — described above. `OG-192` and `OG-193` (LOW,
`NOT_A_DEFECT`) — the `docs/archive/` vs `docs/archives/_trash` near-collision, named at both points
a reader meets it rather than renamed; and the archive's self-certification bound, stated rather
than claimed away.

## [0.4.6] — 2026-08-23 · Session close: handover rewritten, and L-37

`NEXT_SESSION.md` still opened with *"Do not start Phase 4"* — stale, and by then actively wrong.
Rewritten as the Phase 4 brief: orient from the derived map, declare the acceptance set before
building, run every document through the draft gate. `SESSION_STATE.md` records the closed state so
a fresh session knows there is no recovery to perform. Both written **through the draft gate**,
which is the new rule applied to its own handover documents rather than exempting them.

Two zombie shells were killed. Both polled Pass 8's journal for **14** lane verdicts when only 13
ever arrived — the 14th died on a session limit and was re-run separately hours later — so the
condition was unsatisfiable by construction and they had been waking every 45-60 seconds for 15 and
17 hours.

### `L-37` — a probe must create or derive its condition, never borrow it

Three probes broke today at the exact moment the thing they measured got **better**: two pinned to
the register having a phase-blocking row (it no longer does), and one pinned to a document carrying
a stale count that was deleted in obedience to Rule 2. **Obeying a rule broke a test that depended
on violating it.** All three now synthesise their fixtures or derive their subject set and assert it
is non-empty. Inside the third fix came the corollary: the first derivation searched for the claim
family's internal name and found nothing, because the documents use different words. The label a
fact carries in code is not the words a document says it in.

## [0.4.5] — 2026-08-23 · The rules rewrite, and the gate that makes Rule 3 real

**Written before Phase 4, because the previous phase's cost was the argument for it.**

`RULES.md` is rewritten from two rules to six. The new ones are all measured, not chosen:
**fix the CLASS not the instance** (one lane found the shape *"one root, several consumers, one
guarded"* five separate times in a day — every instance created by an earlier fix that stopped at
the door in front of it); **draft, verify, then integrate**; **severity decides the pipeline**;
**a phase declares its acceptance set before it starts**; **derived work is committed, never
regenerated**. `DEEP_VERIFICATION_PASS.md` §3.1-3.3 make the severity gate, the acceptance set and
bounded rounds binding on the pass itself.

### `tools/draft` — the mechanism, not the intention

The largest category of finding across three passes was **prose written without reading its
neighbours**: counts already stale when typed, paths naming nothing, deferrals no plan accepted.
Every one was detectable by a guard that already existed — the guards simply ran at the END of the
session, so the cost was *repair* rather than *avoidance*.

`python3 -m tools.draft check <path>` answers *"would this document be accepted if it landed right
now?"* by running the same guards over two throwaway copies of the working tree — one with the
candidate, one without — and reporting the difference. **The difference, not a filter**, because
adding a document moves facts other documents state, and those findings land on paths the candidate
never mentions.

### This gate answered CLEAN for every possible input, twice, before its counter-examples existed

Recorded because it is the same defect class the engine exists to catch, committed by the engine's
own author while writing the rule against it. First: the throwaway copy was an unpacked archive with
no version control, and the corpus enumerates documents by asking git — so it saw nothing, every
guard reported zero, and the verdict was CLEAN for a probe naming a nonexistent module. Fixed, and
then: the candidate was written into the copy but never staged, so git still could not see it and
the candidate run was identical to the baseline. **CLEAN again, same input, different reason.**

The anti-vacuity floor was then `total == 0`, which is not a floor — a blind copy still reports
**nine**, because two guards fall back to a filesystem walk. It is now a structural assertion that
the copy is a repository, plus a ratcheted visibility floor.

### Rule 1 applied to this session's own new modules

Both new modules invented their own answer to *"which project am I governing"* by resolving the
engine's install directory. This engine is **vendored into other projects**: a map of the engine
handed to an agent working on the project that consumes it is useless, and silently so, because it
still produces a plausible map. Both now resolve the host root through the one function the CLI,
the generator, the doc-system validator and the health run already use.

## [0.4.4] — 2026-08-23 · Pass 8 finished: the 14th lane, the refutation round, and 59 closures

**This is the work `OG-181` said had not been done.** The remaining band was triaged against HEAD by
six independent agents (87 verdicts: 68 still reproduced, 19 were already fixed), fixed by six
file-partitioned lanes, and the closures were then attacked by refuters that never saw the diff.

### The 14th lane finally returned — and found the most

`gatekeeper-map` mapped every gate, its boundary, its order and its fail direction, and produced ten
findings. Three independently re-derived defects already queued from Pass 8 (`P8-088` PRECEDENCE
order, `P8-054` guard floors, `P8-042` guard registry) — arriving at the same defect twice, from two
directions, is the strongest signal this pass produced. Four were new holes: an index writer with no
classification gate, a vault anchor read from the working directory, a git error swallowed into an
empty list, and a config override whose named compensating check reads a different file.

### The refutation round changed two verdicts, which is why it exists

- **`F6` refuted.** The claim was that the L14 placement gate misses the engine's own `.html`/`.json`
  exports. A refuter rendered **real** engine output, applied the proposed fix verbatim, and measured
  that it changes the verdict on **zero bytes** — the engine emits neither front-matter nor the legacy
  comment into those formats, so the suffix list was never what excluded them. The original finding
  had measured a hand-authored file carrying a marker the engine never writes. `L-27`, exactly.
- **`F1` "refuted" by timing only** — the refuter read the working tree, where the fix had already
  landed, and said so itself. It did not refute the finding; it independently falsified the **fix**,
  and the fix held.

### Locked-rule changes in this version (RULEBOOK L9)

- **`tools/hooks/pre-commit`** — a secret-shaped **filename** was invisible to the commit gate.
  Everything scanned blob CONTENT, materialised by SHA; the staged PATH strings were scanned by
  nothing. The manifest's path column is now written into one extra file inside the blob directory,
  so the SAME scanner invocation sees it. Verified end to end through the real installed hook: a file
  whose name is an AWS-key-shaped string and whose bytes are innocuous is now **refused**, an ordinary
  filename still commits. The submodule-only branch was then closed too — a gitlink carries no bytes
  but still carries a path, and taking that branch skipped the path scan entirely (`L-26`).
- **`docs/design/doc-system/RULEBOOK.md`** — the locked-file table's rows 8-10 now match
  `rulebook_files` order. The section claims the table follows that order and **the L9 digest is
  computed over that sequence**, so the order is load-bearing; `CONS-03` compared membership
  bidirectionally and never examined order, so the document asserted an order it did not have with
  every gate green. `CONS-03` now compares the ordered list, after the membership comparison so a
  missing row still reports as missing rather than as position noise.

### The engine, switched on for itself

**`OG-183`.** The navigation layer this project exists to provide was empty in every part at once:
the project index held **1** artifact for 295 tracked files, the content index had never been
generated, and the dependency graph reported **0 nodes** across ~75 modules — in a gitignored
directory, so nothing survived to the next session even when it did build. The graph was empty for
one reason: its source root was still the shipped example's, and this repository's Python lives
elsewhere; the walker fails open on a missing directory, so it scanned nothing and **exited 0**.

Roughly thirty agents dispatched during this pass each began by re-deriving the tree by hand, at a
measured **200–350k tokens each**. `blueprint/SYSTEM.md` is **1,354 tokens** — **0.08%** of the tree
it orients you in — and carries the risky core, the packages, the gate spine in adjudication order,
all three registries, the locked rule files, the documents by classification and the open work as
addresses. `tools/blueprint/` derives it; the builder now refuses to emit an empty graph; and
`blueprint check` runs inside the retained suite, so a stale map fails the push. `L-36`.

Two defects were caught in the map before it was committed, both of the class this engine exists to
catch. It reported **54 secret documents** in a repository that has none — `parse_header` is
fail-closed, so an unheadered file yields the `SECRET` sentinel, and **a refusal to answer is not an
answer**. And it reproduced the register's rows verbatim, which `cross-doc` immediately reported for
failing the register's own rules; a second table carrying register semantics is a second register.

### Wave 2 — the four holes the 14th lane found, and the never-run modalities

- **`OG-184`** — the project index published vault documents past both commit gates. Driven end to
  end through the REAL installed hooks: both printed affirmative clean lines while a
  `classification: secret` document's path, title and summary entered committed history.
- **`OG-185`** — `STRUCT-09` attested one lockfile while the repository tracked several, and the one
  it ignored feeds a renderer that EXECUTES at build time. Now derived from the tracked set — and it
  proved itself within hours, catching a third lockfile that arrived the same day.
- **`OG-187`** — `ENGINE_CONFIG_PATH` silently replaced the entire configuration while `STRUCT-08`,
  named in `ARCHITECTURE.md` as its compensating check, read a hardcoded different file.
- **The PDF path was executed for the first time in this project's history, and is broken** —
  WeasyPrint cannot resolve the theme's CSS custom properties or `currentColor` inside inline SVG.
  A shipped output format, discovered broken only by running it.

### What the gates caught in this session's own work

Worth recording, because it is the argument for the gates: `counts` caught the phase-gate sentence
going stale **the moment `OG-181` closed**; `register` caught a row of mine that drew a table inside
a table cell; `cross-doc` refused a register key I cited before creating, and refused a deferral
until its row named the plan document by path; the blueprint ratchet caught its own author shipping
a stale map; and `STRUCT-09` refused a push because the attestation I had just written was still
untracked — an attestation that protects nobody, since a fresh clone would get the dependencies
without the pin.

Three counter-examples for the phase gate broke on the day the gate did its job, because the helper
**copied** a live `BLOCKS_PHASE` row instead of synthesising one, pinning the probes to "a blocker
currently exists". `0` is the state this project should spend most of its life in. Rewritten to
create their own condition. `L-35` records the three destructive-git incidents, one of them mine.

### Register

`OG-136` moved from the Closed table to Open as `SCHEDULED (Phase 7)`, and Phase 7's plan row now
names it — a deferral is only honoured when the phase accepts it by name (`OG-171`). It was caught by
this session's own new `cross-doc` rule, which is the mechanism working rather than a document being
tidied.

## [0.4.3] — 2026-08-23 · Pass 8: the third deep pass, and the exemption that ate a third of the corpus

**14 verifiers dispatched, 13 returned, 129 findings: 4 CRITICAL, 45 HIGH, 53 MEDIUM, 27 LOW.**
Recorded verbatim in `VERIFICATION_LOG.md` Pass 8; 41 closed here as `OG-140`…`OG-180`.

> ⚠ **This pass has NOT passed.** The adversarial-refutation round and the completeness critic never
> ran — 55 of 165 agents died on a session limit, including every refuter for the CRITICALs — and
> the 14th lane never returned. `OG-181` is open as `BLOCKS_PHASE_4` and says so. Every finding
> acted on here was verified by hand against the artifact and falsified in a disposable lab, but
> that is the implementer checking the verifier, which is the arrangement
> `DEEP_VERIFICATION_PASS.md` §1 exists to avoid.

### CRITICAL — each verified end to end through the real installed hooks

- **`OG-140`** — `under_dated_heading` inferred "this is history" from a date in any enclosing
  heading, exempting **2458 of 8307 prose lines (29.6%)** from five guards *and* from `CONS-06`,
  which the pre-push moat runs. Three **live policies** were 78–88% dark because each carries a
  version strapline as an `###` heading. **A subtitle is not a record.** Record-ness is now
  declared. Coverage rose everywhere it had been blind — `cross-doc` 395→469, `built-claims`
  344→420 — and immediately surfaced a defect that had been invisible. This was my own fix from
  `[0.4.2]`, and `L-31` is the lesson I wrote and did not apply.
- **`OG-160`** — one leading blank line hid a `classification: secret` document from BOTH L14
  gates. One keystroke, no bypass flag, affirmative "placement clean" printed.
- **`OG-161`** — a lightweight tag pointing at a blob published it unscanned; the handler fired
  only on the annotated spelling, and the counter-example covered only that one.
- **`OG-152`** — one non-UTF-8 byte disabled the whole push-time placement gate: `UnicodeDecodeError`
  IS a `ValueError`, so the handler returned an empty findings list, read by every caller as clean.

### Bypasses closed

`OG-167` **`OG-102`'s invariant was defeated by moving its other half** — both sides were read from
the same operator-controlled config, so setting two variables at once disabled the L14 gate. The
anchor is now git's ignore rules, which an env var cannot move · `OG-170` `--allow-rulebook-drift`
was silent and untraceable · `OG-169` `ENGINE_PREPUSH_FULL=1` refused EVERY push on a green tree ·
`OG-168` the leak gate's own findings carried 16 characters of the secret into build artifacts.

### One shape, four guards: a ground truth that ordinary prose can widen

`OG-163` `find_tables` was fence-blind at the ROOT, so a fenced row in `ABSENT_PATHS.md` declared a
path absent for real (`OG-100` had fixed one caller) · `OG-164` a fenced `##` heading defined a
register key · `OG-166` **`symbols` resolved identifiers by SUBSTRING**, so a comment saying a
function no longer exists satisfied every citation of it — all 664 checks were resolved that way ·
`OG-179` the guard count was a one-line regex, so a `ruff`-clean line wrap changed it.

### Gates that were claims

`OG-178` `velocity_ok` — the ±5% motion assertion `ENGINE_PLAN.md` states three times — had **zero
callers**; now asserted in the render path · `OG-157` Gate 3, the export credential scan, had zero
counter-examples · `OG-177` so did `SUITE-04`, plus three ways past it (`OG-174` the ceiling was an
uncompared number in an editable JSON, `OG-175` the invocation was unguarded data, `OG-176` driving
mypy to zero turned the check RED) · `OG-153` the anti-vacuity floors were constants, so 150 of 196
counter-examples were deletable · `OG-171` **all four deferrals were honoured by phases that had
never accepted them** — a deferral is now a two-sided agreement · `OG-156` `CONS-02` asserted
mechanical agreement and checked one direction · `OG-155` a gate could be registered and never
called · `OG-173` mermaid's `--theme` was a no-op accepting any string.

### Also

`OG-141` `docgen render` crashed in its documented default mode · `OG-142` the mermaid quickstart
fails and is copied into a `SKILL.md` · `OG-143` `built-claims` was blind to `node <script>` ·
`OG-158` the supply-chain attestation was false and unverified, now enforced by a new `STRUCT-09` ·
`OG-144`…`OG-151`, `OG-159`, `OG-162`, `OG-172`, `OG-180` documentation and record defects,
including the crash-recovery file and the copy-paste launch file both saying the Phase-3 pass had
never run, and the phase-gate accounting measuring a label that can never appear again.

**Two fixes were caught being wrong while being written**, which is the method working: the
gate-invocation check matched each function's own `def` line so every gate "called itself"
(`L-33`), and adding `node` detection dropped coverage 344→264 because over-escaping had broken the
pre-existing npm pattern (`L-34`). Three register rows tripped the very check they described and
had to be rewritten.

Lessons `L-32` (infer nothing from the shape of text — declare it), `L-33`, `L-34`.

Counter-examples **201 → 207**. Checks **33 → 34**. Rulebook `1.2.6` → `1.2.9` (three L9 two-steps).

**Verification:** `tools.corpus_check` → 10 guards clean · `unittest discover` → **207 OK** ·
ruff **0** (ceiling 0) · mypy `--strict` **22** (ceiling 22) · `tools.health --full` below.

## [0.4.2] — 2026-08-23 · Pass 7: attacking Pass 6's fixes, and what was still open

**12 agents, 91 findings: 7 CRITICAL, 34 HIGH, 29 MEDIUM, 21 LOW.** Every one dispositioned in
`OPEN_GATES.md` (`OG-94`…`OG-137`); raw findings verbatim in `VERIFICATION_LOG.md` Pass 7. Rulebook
`1.2.5` → `1.2.6` (the L9 two-step, because `tools/hooks/pre-commit` changed).

**The pass attacked the previous pass's fixes, and five of six narrowings had a hole one step over
from where the fix landed** — `LESSONS.md` `L-26`, demonstrated against the session that wrote it.

### Security — every claim below proven end to end through the real installed hook

- **Encoding (`OG-101`).** Normalisation stopped *classifying* and started *enumerating*. A UTF-16
  document padded with CJK drops NUL density to **0.0004**, far under the 0.10 detector threshold,
  with an ASCII key intact inside it. A NUL-bearing blob now contributes printable-ASCII runs from
  every candidate wide decoding, and the classified transcode is **additive**, so a misread encoding
  can no longer destroy the payload. **All 11 wire forms** of one `classification: secret` document
  carrying one AWS-shaped key are REFUSED; a clean public document and a UTF-16 public document
  still commit. Tracked binary assets grow **0.00%** — two earlier discriminators were measured
  wrong first (printable-byte share rejects CJK, decode damage passes compressed fonts).
- **Vault (`OG-102`, `OG-128`, `OG-129`).** `ENGINE_CONFIDENTIAL_DIR=docs` silently disabled the L14
  placement gate — `OG-92`'s third spelling, an ordinary relative directory. Blacklisting it would
  have been the fourth instance, so the guard asserts an invariant: **the vault may not be an
  ancestor of the rule layer**. An absolute vault is refused with its own accurate reason, and
  `trashDir`/`docSystemDir` — unguarded until now, where `ENGINE_TRASH_DIR=.` resolved to the
  repository root — refuse the root too.
- **Recursion mark (`OG-103`).** `ENGINE_IN_HOOK_PROBE=1` was a bypass switch: one `export` removed
  `STRUCT-04`'s behavioural probe and all of `SUITE-05`, and the pre-push moat does not use
  `--full`. It is now a random token backed by a marker file the minting process owns.
- **Push gate (`OG-118`).** `scan_manifest` failed **open** on every unreadable object while the
  module documents fail-closed and its sibling implements it. A manifest naming a nonexistent blob
  exited **0, CLEAN**.
- **Loudness (`OG-119`, `OG-127`).** `ENGINE_CONFIDENTIAL_DIR=. git commit` printed *"placement
  clean"*, exited 0, and said nothing about the refusal — the log is only shown on failure and then
  deleted. And an exported-but-empty variable was read as *unset*, so `""` was the one spelling
  refused silently, though it is listed first among those "refused loudly".

### Guards

`CONS-03` every exit fails closed (`OG-94`); `stamps` counts honestly, has no self-declaration
hatch, scans every text surface and SKIPs with a cause rather than passing on zero (`OG-96`,
`OG-126`); `built-claims` **222 → 344** claims (`OG-97`; the entry said `340`, measured 344 at the release commit — `OG-149`) and cites the right line in HTML (`OG-108`);
`symbols` covers 13 extensions (`OG-98`) — which found 18 dead bare citations: 2 were stale claims and were fixed, and the remainder are declared with a reason each in `ABSENT_PATHS.md` (the earlier breakdown said "2 fixed and 14 declared", which leaves two unaccounted — `OG-148`); `cross-doc` consults every cited plan (`OG-99`); a fenced table can no longer widen a live
vocabulary (`OG-100`); `rendered-output`'s `[object Object]` arm could never match **any** input
(`OG-104`), a role could be present yet never compared (`OG-105`), and its line-anchored table
pattern missed any row not alone on a line (`OG-112`); `present-tense` exemptions moved from
PARAGRAPH to SENTENCE scope and `_FUTURE_MARKERS` was cut 15 → 11 on measurement (14 of them
exempted nothing); `register` reported a declared `N/A` as undeclared while `7/A` passed (`OG-109`);
`crossrefs` saw **one** link across 58 documents and now reads reference-style and HTML refs
(`OG-111`); `CONS-08`'s "bump" exemption is clause-scoped (`OG-123`).

### Also in this release, and originally omitted from this entry (`OG-151`)

- **`OG-138`** — a failing moat attack printed an exit code and nothing else, so when the
  POSITIVE control failed `SUITE-06` reported *"1 moat attack no longer refused"* and pointed
  at the moat, while the cause was `CONS-06` red on a documentation path. `verdict` now prints
  the tail of whatever the failing command wrote.
- **`OG-139`** — `CONS-06` reported the verification log for citing lab probe paths, and
  *declaring* them was worse: the declaration then exempted the same paths in `present-tense`
  and broke `OG-115`'s counter-example. `CONS-06` now honours dated records. **This is a
  behaviour change to what the push-time moat refuses**, which is exactly why omitting it from
  the entry for its own release commit mattered.

### Records corrected where they did not re-derive

`16 → 164` was `15 → 163`; `63 → 105` was `62 → 110`; `111 → 132` counter-examples was **136**; and
*"14 of 57 auto-excused"* was **51 of 57** — that last one sitting inside the lesson that says
*measure the blast radius, do not estimate it*. `HANDOFF.md` no longer says the verification pass
has not been run two lines above the section saying it has.

### Deliberately NOT done

- **`OG-116`** — built, measured, **rejected**. The fix produced 12 findings, **11 on correct
  prose**; the measurement is recorded instead of a half-built guard (`L-31`).
- **CI on the VPS2 self-hosted runner (`OG-136`)** — verified live: the runner is **online** and
  registered to `AuditHunt` only, this repository has **0 runners** and no workflows, and CI is
  **Phase 7** work. Registering the shared runner is an operator action, and a required context
  whose label nobody serves queues forever. Recorded, not built.

### Counter-examples

**136 → 196.** Every new guard falsified by mutation. Three lessons: `L-29` (a probe that iterates
what a fix DELETED passes for free — probe inputs are now derived from the live data structure),
`L-30` (the type checker is a gate: `mypy --strict` found a `ValueError` crash 196 tests could not,
`OG-135`), `L-31` (measure a fix's cost on the real corpus before shipping it).

**Verification:** `python3 -m tools.health --full` → **33 passed, 0 failed, 0 skipped**;
`python3 -m tools.corpus_check` → **10 guards clean**; `unittest discover` → **196 OK**; ruff **0**
(ceiling 0), mypy `--strict` **22** (ceiling 22); attack harness **21/21 refused**.

## [0.4.1] — 2026-08-22 · Pass 6: the verification Phase 3 never got, and what it broke

**Rulebook `1.2.2` → `1.2.5`** (three L9 two-step re-baselines: the disposition vocabulary
generalised to `BLOCKS_PHASE_N`; a false "no code reads either key" claim about `VERSION.json`;
L18's scope stated).

Eleven independent agents against `c956619`, each handed a **claim to attack** and never the diff,
the live tree read-only, falsification confined to `git archive` labs. **80 findings: 4 CRITICAL,
27 HIGH, 37 MEDIUM, 12 LOW.** One agent confirmed its claim, one refuted it outright, nine partly
refuted. Raw findings verbatim in `docs/process/VERIFICATION_LOG.md` Pass 6.

The pass did what four passes of history said it would: **it broke the claims.**

### The four CRITICALs

- **`stamps` was reporting a false green on the live tree** (`OG-78`), found independently by three
  agents. The amnesty accepted the marker and a document's name appearing *anywhere in the same
  file*, so **51 of 57 documents were auto-excused** *(re-derived 2026-08-22: the figure long recorded here was `14 of 57`, which counted `HANDOFF.md`'s mentions alone and even for that file measures 17. **Seven** tracked files carried the marker at `c956619`, and the union of the documents they name is 51 — the blast radius was materially worse than the number that was reported. `OG-107`'s sibling: a count nobody derived.)* and a genuinely drifted stamp on
  `SESSION_STATE.md` was reported compliant. Two root causes: the declaration must be **co-located
  on one line**, and drift-invalidation applies only to **content-certifying** stamp kinds —
  `SESSION_STATE.md` declares its own stamp *"deliberately weaker … which invalidates on any edit to
  its own body"*, so applying doctrine §8.2 to it asked the wrong question. **The narrowing that
  closed the earlier blanket amnesty, in this same session, had *moved* the hole.**
- **Both L14 placement gates were encoding-blind** (`OG-84`). A `classification: secret` document
  saved as UTF-16 **committed and pushed clean** through the real installed hook, while its
  byte-identical UTF-8 twin was refused. The root fix already existed and had been wired into the
  *secret* path in the same hook, reading the same blobs — `OG-56` recorded the class as "closed at
  the ROOT" and it was closed for one of two consumers.
- **`CONS-11`'s stated contract was the opposite of its behaviour** (`OG-83`). Its docstring and
  `[0.4.0]` both said a guard SKIP is a health FAILURE; the code propagates SKIP, and a default
  health run — which is what pre-push runs — is green with skips. On every fresh clone, in CI, and
  in every lab, `rendered-output` could not build, checked **nothing**, and the push was accepted.

### The holes falsification found in guards that were already "proven"

- **`present-tense` was disarmed by seven ordinary English words** (`OG-79`). `L-23` was written
  this session about one over-broad word in the *absence* list; only that list was narrowed, and a
  verifier walked a false claim past the guard using `_FUTURE_MARKERS`. A retained probe then
  exposed a **third** list — the shared `_PAST_MARKERS`, gating three guards — carrying `" until "`
  and `" before "`. Coverage rose **62 → 110** claims. *(Corrected 2026-08-22: this said `63 → 105`; `present-tense` reports 110 at `35cd4f8`.)*
- **`rendered-output`'s only CRITICAL pattern could never fire** (`OG-81`): `<!-- figure:` was
  matched against text that had comments stripped first. Unreachable for its whole life.
- **`rendered-output` promised to assert its colour roles were present and did not** (`OG-82`):
  deleting every ink role took it to **0 assertions, still green**. *A second defect surfaced during
  that very fix* — the edit deleted the contrast pair loop entirely — and the retained
  counter-example caught it.
- **A vacuous guard shipped green** (`OG-80`): the test suite iterated a hand-written guard list, so
  a newly registered guard was covered by nothing. It now derives from `GUARDS`.
- **`counts` reported "9 of 9 measurable families"** while six matched nothing (`OG-87`). A family
  matching zero is Rule 2 being *obeyed* — so what runtime cannot prove is now proven by
  counter-example: every family is exercised with its own derived truth and a wrong value.
- **`cross-doc` could not detect an unhonoured deferral** (`OG-88`): it matched the substring
  "Phase N" anywhere. It now resolves against the plan's real phase row, and refuses a deferral to
  a phase the plan marks **COMPLETE** — a defect parked forever.

### Defects the guards could not see, and the root fixes that close the class

- **A cited source file that does not exist was invisible to everything** (`OG-89`). `CONS-06`'s
  pattern needs a directory prefix so a bare filename never matched; `symbols` dropped unresolvable
  paths *before* checking. It immediately found the engine's own architecture document naming
  **two modules that have never existed**. Coverage **15 → 163** claims. *(Corrected 2026-08-22: this said `16 → 164`. Re-derived by running each commit's own guard over its own corpus — `symbols` reports 163 at `35cd4f8`, `OG-107`'s sibling.)*
- **`docgen render` had been 100% broken for seven commits** (`OG-86`) — `AttributeError` on every
  invocation, because **nothing ever ran it**. `tools/tests/test_cli_surface.py` now invokes every
  subcommand: `built-claims` proves a command is *declared*; only running it proves it *works*.
- **`CONS-03` had been weakened from FAIL to SKIP** by Phase 3 (`OG-85`) — a file silently removed
  from `rulebook_files` left the engine reporting HEALTHY.
- **A config value silently disabled the L14 gate** (`OG-92`). `""` had been guarded; `.`, `./`,
  `..`, `/` had not. Every spelling is now refused, loudly.
- **Seven instructions for the deleted `build.py` survived in tracked rendered HTML** (`OG-91`),
  invisible to a Markdown-only guard. `built-claims` now reads tracked built output too.

### What was verified rather than accepted

`OG-93` was reported as "Gate 9 can never fire in the build path". **Half right.** The gate *does*
run on every export and *is* fail-closed — measured. What was true is that it had zero
counter-example; four are now retained, and `RULEBOOK.md` L18 states its real scope.

### New documentation

- **`docs/design/ARCHITECTURE.md`** — the whole system from the outside in: outer shape, layering,
  the document journey, six gate boundaries, the three deliberate fail-**open** paths, the rule
  layer's real readers, what is deliberately *not* guarded, and every extension point. Derived from
  source twice, independently, with the artifact deciding where the two disagreed.
- `LESSONS.md` `L-26`…`L-28`.

### Counts

- `tools/tests/` — **111 → 136** retained counter-examples. Register: **0 blocking rows**.
  *(Corrected 2026-08-22: this row said `111 → 132`. Re-derived by counting `test*` functions across `tools/tests/` at `35cd4f8`, the release commit: **136**. A miscounted count claim in a changelog is the exact defect `counts` exists to catch, and it was written by hand rather than derived — see `OG-107`.)*
- `ruff` **0** and `mypy --strict` **22**, both exactly at the pin, zero in the new code.

---

## [0.4.0] — 2026-08-22 · Phase 3: the checker, pointed at this repository's own corpus

**Rulebook `1.2.1` → `1.2.2`** (locked-file set unchanged; `RULEBOOK.md`'s L9 locked-file table
carried a register citation that the renumbering below made ambiguous — re-baselined via the L9
two-step: `rulebook_sha256` → `PENDING`, then `--write-hash`).

`BUILD_PLAN.md` Phase 3 delivered. `python3 -m tools.corpus_check` exits **0** on a clean corpus,
and **every one of its ten guards was deliberately falsified and shown red before being trusted**,
with the failing input retained in `tools/tests/test_corpus_check.py` and run by `SUITE-05` on every
health pass (`docs/process/RULES.md` Rule 1). The corpus is **this repository's own 57 tracked
documents**, not three fixtures — `docs/CHARTER.md` purpose 2.

### The overlap table came first — `docs/plan/PHASE3_OVERLAP.md`

- Written **before any implementation**, as `docs/plan/NEXT_SESSION.md` §2.1 requires: for each of
  the doctrine's nine guards, what `tools/health` already covers and what is missing. It records
  that six guards are net-new capability, three extend an existing `CONS` check, and that
  `CONS-01…CONS-10` keep their questions. Each guard's module docstring names the check it defers
  to, so "absorb, never duplicate" is checkable rather than asserted.

### `OG-36` — one Markdown table reader — `tools/lib/md_table.py`

- **Five readers became one.** The disagreement was measured first, on `DOC_MANIFEST.md`'s own
  header cell: `variants: [commercial\|confidential\|secret]` parsed as **4 cells** in
  `classification.py` and `adjudication.py` and **2** in `doc_manifest.py` and `generator.py`; and
  `|| a | b |` lost its empty leading cell in three of the four. The canonical dialect is GFM —
  one leading/trailing pipe removed, split on *unescaped* pipes, `\|` unescaped.
- The **three** documents governed at that point built **byte-identical** after the rewiring — sha256-compared before and after, including the flagship, which carries three GFM-escaped pipes. (`gallery.md` became the fourth governed document later in the same session, after this comparison; saying "all four" would claim a measurement that was never taken.)
- `CONS-03` stopped locating its `File` column by position — it regexed the whole row for the first
  backticked token, which *happened* to be the File column and would have silently started reading
  the `#` column the moment one was inserted to its left. It now looks the column up by name.
- `strip_markup` no longer strips underscores: they are identifier characters here
  (`NOT_A_DEFECT`, `content_role`), not emphasis.

### `OG-06` — the guard set — `tools/corpus_check/`

Ten guards. Nine are the doctrine's §5 set; `register` was earned by a live defect (below).

- `register`, `crossrefs`, `symbols`, `test-refs`, `counts`, `cross-doc`, `present-tense`,
  `stamps`, `built-claims`, `rendered-output`.
- **Anti-vacuity is structural, not per-guard discipline.** Every guard declares a floor and
  reports how many claims it examined; `model.passed()` demotes a clean-but-empty run to a FAILURE
  naming both possible causes (`LESSONS.md` L-19).
- Wired into health as **`CONS-11`**, so there is one command a session must remember. A guard
  SKIP propagates as a health **SKIP** — not a pass, fatal under `--full`/`--strict`, accepted
  by a default run. *(Corrected in place 2026-08-22 by Pass 6: this read "a guard SKIP is a
  health FAILURE", which the code has never done, and which understated the exposure on a
  fresh clone. See `[0.4.1]`.)*

### `OG-64` — Gate 10 now inspects the document it is building

- `rendered-output` extracts each theme block's declared ink and ground values **from the built
  stylesheet** and feeds them to the real `export_sanitizer.gate_wcag_contrast`. Every caller
  before this passed `pairs=None`, so a per-document accessibility gate had only ever checked the
  design tokens. The WCAG maths is not re-derived — that would be a second source of truth.

### `OG-65` — the raster exports follow the theme — `adapters/echarts/`

- `opaqueGround()` reads the ground from the token file. Measured: a light-theme PNG went
  `#060608` → **`#FAFBFC`**, print → `#FFFFFF`, dark unchanged. The interactive HTML's body, ink
  and captions now come from the same theme object the chart is rendered from, instead of three
  hardcoded dark hexes.
- `document-theme` has no ground a raster can observe, so it **warns** rather than silently
  resolving to one. 30/30 visual-engine tests still pass.

### `OG-73` — the second document engine is gone

- `tools/docgen/build.py` **deleted**: 223 lines, zero importers, an input convention incompatible
  with the canonical path. The corpus checker is what proved it unreferenced, which is why the
  decision belonged to this phase. Recorded in `ABSENT_PATHS.md`; git history is the archive.
- Its only document, `tools/docgen/gallery.md`, was **converted to the canonical convention**
  rather than deleted with it — taking the governed corpus **3 → 4**. The conversion was caught
  and corrected by the engine's own manifest-drift gate on the first attempt (`surface: repo` where
  `REF` is registered `web`).

### `OG-74`/`OG-75` — the register could not name its own rows

- **Eleven duplicate primary keys.** `OG-48`…`OG-58` each named two different findings, because a
  second numbering run started at `OG-48` when the first had reached `OG-62`. Every citation of
  `OG-49`, `OG-50` or `OG-58` was ambiguous — in the register the phase gate itself is answered
  from. The open run was renumbered to `OG-63`…`OG-73`; the map is at the top of `OPEN_GATES.md`,
  and `CHANGELOG.md`/`VERIFICATION_LOG.md` keep their original numbers by design.
- **Five rows had silently lost their `closing it means` column** — including `OG-36` and `OG-47`,
  two of this phase's own deliverables. A ragged Markdown row does not error; the cells shift left.
- Both classes are now refused by `register`, with retained counter-examples.

### Two guards that went green while being wrong — found by not trusting the green

Recorded because they are the phase's most useful evidence, and both are now regression probes:

- **`present-tense` was disarmed by its own exemption list.** A bare `" deliberately"` (intended
  for "deliberately absent") matched *"every guard **deliberately** falsified first"* in
  `BUILD_PLAN.md`'s Phase 3 row — the single row describing `tools/corpus_check/` in the present
  tense while it did not exist. The guard reported CLEAN on the exact finding it was built for.
- **`stamps` treated one declared drift as a blanket amnesty.** `HANDOFF.md` honestly declares
  `PROVENANCE.md`'s stamp stale (`OG-09`); the first version let that excuse *every* drifted stamp
  in the corpus. Declaration is now per document.

### `test-refs` taught itself a false vocabulary, twice

- First a test fixture quoting `"OG-998"` entered the id vocabulary, making every `OG-` citation in
  `CHANGELOG.md` a HIGH finding — **155 of them from one fixture**. The test tree was excluded.
- Then the *docstring explaining that exclusion* quoted the same probe id, and it happened again —
  **158 findings, from the sentence describing why there had been 155**. Python sources are now
  parsed with `ast` and docstrings are dropped before literals are collected: a docstring is prose
  about the code, not code. A ground truth that documentation can widen is not a ground truth.

### The corpus's own findings, fixed

- `tools/docgen/gallery.md` — a dead demo link, and three instructions naming the deleted script.
- `tools/docgen/AUTHORING_PROMPT.md` — the exit gate named the deleted build path; the correction
  note now describes an absence that is real.
- `tools/visual-engine/README.md`, `vault-graph-engine/VAULT_GRAPH_SPEC.md` — three pointers to
  documents belonging to other projects now say so instead of reading as local files.
- `docs/CHARTER.md` — the measurement moved twice in one session (57 tracked, then 4 governed) and
  a guard refused the run both times rather than a human noticing later.

### The regression this phase introduced, and how it was caught

- **A missing render engine read as a corpus defect, and the moat refused a clean push**
  (`OG-77`, `LESSONS.md` `L-25`). `node_modules` is gitignored, so it is absent in a fresh clone
  and in every `git archive` lab. `rendered-output` reported the resulting build failure as
  CRITICAL → `CONS-11` red → `tools.health` red → and **pre-push runs health**, so nothing could be
  pushed at all. Fixed: an environment fact is a SKIP with its cause named, propagated as a SKIP by
  `CONS-11`, exactly as `SUITE-01`/`SUITE-02` already behaved for the same dependency.
- **It was caught by the moat harness's positive control** — *"a clean commit and push are
  accepted"* — while all twenty adversarial cases still passed. The negative half of a two-sided
  gate was flawless while the gate was unusable.
- **Corollary, same shape:** `raise SkipTest` in `setUpClass` drops a whole class from unittest's
  run *count*, which is indistinguishable from the broken-import defect `SUITE-05` guards against —
  it turned a lab run red on *"111 defined but only 104 ran"*. Each test now skips itself.

### Counts

- `tools/tests/` — **71 → 111** retained counter-examples. `CHECKS` — **32 → 33**.
- `ruff` **0** and `mypy --strict` **22**, both exactly at the pinned baseline, with zero errors in
  the new package.

---

## [0.3.5] — 2026-08-21 · The renderer made real, and the eighth-agent gate answered

**Rulebook `1.2.0` → `1.2.1`** (locked-file set changed: `tools/hooks/install.sh` added to
`rulebook_files`, and both hooks edited — re-baselined via the L9 two-step).

An 8-agent fresh-context gate at `494746c`, weighted at the never-probed document renderer,
returned **109 findings (9 CRITICAL, 29 HIGH, 41 MEDIUM, 30 LOW)**. The renderer had never been
verified by rendering anything and looking at it.

### The renderer — `tools/docgen/generator.py`, `components.py`, `tokens.py`

- **Markdown is actually rendered now.** The body renderer understood only front matter, `#`/`##`,
  pipe tables and figure directives; **bold, italic, inline code, links, bullet and numbered lists,
  blockquotes, fenced code, `---` rules and `###`–`######` headings were emitted as literal source
  text.** The flagship `examples/capability-gallery.md` shipped with **118 literal backticks and 4
  literal `**` in its visible body**; measured after the fix: **0**. Added `_render_inline()`
  (code spans lifted to placeholders → HTML-escape → emphasis/links → restore, in that order, so a
  `**` inside a code span is never emphasis and no generated tag is ever escaped) plus block
  handling for every construct above. Link hrefs are **allow-listed** — `javascript:`, `data:` and
  `vbscript:` render as plain text, verified.
- **Hard-wrapped paragraphs are one paragraph.** Every non-blank source line became its own `<p>`,
  and the stylesheet never reset `p` margins, so a browser's default 1em margins put a blank line
  between every line of a single sentence. The flagship rendered **29 paragraphs for 8 authored**;
  now exactly **8**. Added the `p { margin: 0 }` reset and consecutive-line joining.
- **`\|` in a table cell survives.** The parser split on every raw `|`, deleting the escape and
  inventing columns — any cell holding a shell pipeline, a regex alternation or a union type was
  silently corrupted.
- **Table cells and `##` eyebrows render inline Markdown**, via an opt-in `cell_renderer` /
  `eyebrow_renderer` so the other callers of `components.data_table()` (which pass literal strings)
  are unaffected.
- **Print no longer truncates tables.** Tables live in `overflow-x: auto`, which *clips* on paper
  with no scrollbar and no indication anything is missing. Added `@media print` rules.
- **A figure id with no sidecar entry now refuses the build.** `entry = figures.get(fig_id)` had no
  `else`, so one typo'd id deleted a figure from the document with exit 0, `wrote html`, `check`
  PASSED and `--strict` silent. The adjacent *missing-sidecar* case was already guarded; this one —
  the more common — was not. Falsified: typo → refused naming the unknown and known ids; clean
  flagship → exit 0.

### The chart engine — `tools/visual-engine/`

- **Charts follow the document's theme.** ECharts SVG baked literal hex inks, but docgen documents
  honour `prefers-color-scheme` **and** carry a runtime toggle — so every chart rendered
  light-on-dark inside a light document. New `document-theme` expresses inks as CSS custom
  properties (`var(--fg)`, `var(--mute)`, `var(--faint)`); the bridge defaults to it. The
  categorical palette is unchanged across modes, so the reskin law holds.
- **An empty dataset is refused in every family, not just pie.** `countCells()` returned on the
  first shape it recognised and knew three (`source`, `matrix`, `items`), reporting **0** for graph,
  tree, radar and timeline — and nothing ever failed on 0, so those families rendered a complete,
  titled, provenance-stamped, *empty* chart that survived `--strict`. Rewritten to deny-list
  metadata keys instead of allow-listing payload keys, so a family added later counts correctly.
  Falsified across bar, graph, treemap, radar, timeline and heatmap.
- **G-SEC no longer misses a closing `</script >`** — the pattern was `/<\s*script/i`, and a closing
  tag is all that is needed to break out of an inline script block.
- **Heatmaps refuse a matrix that disagrees with its axes.** Out-of-range cells were dropped
  silently, and a short matrix shifted every value onto the wrong row label.
- **All-string first rows and duplicate category labels are refused** (ECharts eats the first as a
  header; duplicates collapse onto one axis position and draw over each other). The duplicate check
  is scoped to a *categorical* first column — the first version applied it to every family and broke
  the scatter golden, where repeated x-values are ordinary data.
- **SVG aria-labels are XML-escaped** — `&` or `<` in a title produced non-well-formed SVG.

### The moat and the health system

- **`install.sh --chain` ran a non-executable predecessor.** The generated chain gated on
  `[ -x "$keep" ]`, so a predecessor missing its mode bit was **skipped in silence while the chain
  exited 0** — a foreign project's gate switched off by the act of adopting ours. Measured both
  ways: old guard `exit 0`, predecessor never ran; new guard (`[ -e ]` + `bash`) predecessor ran and
  its `exit 3` propagated. Retained in `tools/tests/hook_attacks.sh`.
- **`install.sh` is now a locked rulebook file** — it generates the chain script, so a silent edit
  there neuters the moat, which `OG-52` had just demonstrated.
- **SUITE-05 and SUITE-06 derive their floors.** `_PYTEST_FLOOR` was the literal `30` while the
  suite had grown to **71** — 41 counter-examples could have been deleted with the engine green.
  Both now count what is *defined* (test methods by `ast`; `verdict` calls in the harness) and
  require that everything defined also *ran*, which is what catches a module silently failing to
  import. The literals survive only as hard floors.
- **`host_root()` and `tool_path()` no longer recurse** when `git` is absent from `PATH` — each
  called the other until the recursion limit. Falsified with `PATH=/nonexistent`.

### The gate that could not finish (`OG-54`, found by running `--full`, not by reading it)

`SUITE-06` hit `_run`'s **1800 s ceiling** and reported *"the attack harness printed no result
line … TimeoutExpired"*. Its own skip line advertised **"~6 min"** — a duration nobody had
measured, on a check that had apparently never completed. Cause: every one of the harness's ~20 lab
pushes runs the pre-push hook → `tools.health` → `STRUCT-04`'s ~72 s behavioural probe **and**
`SUITE-05`'s ~110 s counter-example suite. ~180 s of redundant re-verification per lab push, nested
inside the test that already proves the same thing.

Fixed with an environment mark (`ENGINE_IN_HOOK_PROBE`) set by the probe and by `SUITE-06`; a health
run that sees it skips those two checks **with the reason printed**, while the outer run still runs
both and the harness still executes every attack. Falsified both ways: unmarked →
`[PASS] proven to gate`; marked → `[SKIP] skipped inside a probe`.

**Measured: 20 passed, 0 failed, 126 s.** The skip line now quotes that number and its date.

One more defect came out of the same fix, and it is worth recording because of how it was found:
`SUITE-06`'s new derived floor printed **"6 defined"** against 20 real attacks. The anchor was
`^\s*verdict`, but most cases are written `git push … ; verdict 1 $? "…"`, so 14 were invisible —
and an *under*-count is the dangerous direction, because `passed < defined` could then never fire.
The check would have passed while measuring nothing. It was caught by **reading the number the
check printed**, not by observing that the check was green.

### Second working session — the MEDIUM and LOW bands, worked from the root

**The ledger the phase gate reads was five tables, not one.** `OPEN_GATES.md`'s `## Open` section
held four blank lines between rows; a blank line ENDS a Markdown table, so the section parsed as
five tables of which the first held **10 of its 22 rows**. Nothing about the rendered page or the
raw source shows it. That file is what answers *"may this phase start?"* — a reader taking the
first table would have certified the gate satisfied with twelve rows unread. Repaired to one table,
and **`CONS-10`** now fails on a blank line between two table rows across five governance
documents (falsified both ways).

**A broken `engine.config.json` was silent.** `_raw_config()` returns `{}` on any parse error, which
must stay — it is called at import time by every entry point *including the one that would report
the problem* (L-17). But silence meant the engine ran on built-in defaults while every path, tool
and host-root override in that file was ignored. It now says so on stderr, distinguishing ABSENT
(supported) from PRESENT-BUT-BROKEN (never), and **`STRUCT-08`** fails on it where failing loudly
costs nothing.

**A tag pointing at a blob published it unscanned.** `git tag -a v1 <blob>` is valid and pushing
the tag publishes that object; `git rev-list` walks commits, so it was never enumerated — measured:
*"the pushed range carries no blobs; nothing to scan"*, push accepted. The tag handling that should
have caught it sat at the BOTTOM of `collect_ref`, below two early returns that both fire for this
shape (`rev-list` fails outright on a blob-target tag; `revs` is empty when a tag's commits are
already on the remote). The repository's existing tag test passed throughout, because it tags a
commit carrying new history — the one case that did reach the code. Hoisted above every early
return; measured after: *"secret scan over 2 published object(s) … exit 1"*. Retained as attack 21.

**`LOCAL_SHAS` was read and never assigned.** In the fallback that runs *after* range resolution has
already failed, `for s in $LOCAL_SHAS` expanded to nothing — so the loop whose own comment says it
exists "so the printed guarantee and the behaviour agree" did nothing at all.

**`--formats pdf` without weasyprint exited 0 having written no file**, as an INFO. One branch below,
an unknown format was already HIGH and blocking — so `--formats pdff` failed loudly while
`--formats pdf` failed silently. Now blocking, with the install command in the message.

**A single-slice pie rendered as an empty frame.** docgen's native renderer emitted an arc whose
start and end points coincide, which SVG omits entirely (SVG 1.1 F.6.2) — title and legend intact
around a hole. Emits a circle for the full-circle case. *(The ECharts engine was checked and is
correct; it uses the standard two-arc idiom.)*

**Every native figure printed its caption twice** — once inside the SVG at ~4–9px after the viewBox
scaled down, once as a real `<figcaption>`. Hidden at the embedding rather than removed from the
renderers, because a standalone `.svg` export genuinely needs it: the duplication is a property of
embedding, so embedding is where it is resolved. Also: the decorative blueprint grid no longer
shows through chart SVGs (they paint no ground of their own), and long hashes/URLs no longer
overflow the text column.

**A document had exactly one heading element.** `##` sections rendered as `<span class="t-eyebrow">`,
so the flagship had one `<h1>` and 24 styled spans — no outline for a reader, a screen reader, or a
table-of-contents generator. They are `<h2>` now (24 of them), with the browser's default margin
zeroed so the layout is unchanged.

**An authoring prompt taught a convention the build cannot read.** `tools/docgen/build.py` is a
second renderer expecting `<!-- classification: GITHUB -->` comments and a `###` kicker;
`generator.py` — what the CLI actually calls — expects YAML front matter and `<!-- figure:ID -->`.
Nothing imports `build.py`, yet `AUTHORING_PROMPT.md`, *which authoring agents are told to copy
verbatim*, and `tools/docgen/README.md` both presented it as the way to build. A document written
from that prompt fails on its first line. Both now point at `python3 -m tools.docgen.cli build`, and
`build.py`'s docstring opens with what it is. Deletion is `OG-58`, deliberately not done as a side
effect of a fix.

**An unknown `classification:` value coerced to `secret` in silence.** `classification: publik`
became `secret` — correct, fail-closed — and the author then received two errors about
`classification=secret`, a tier they never wrote, with nothing naming the typo. The coercion now
says which value it rejected and that the errors below refer to the coercion.

### Documents

- **The launch command in `START_NEXT_SESSION.md` was broken and is regenerated.** It wrapped the
  prompt in double quotes while containing an inner `"import yaml"`, so the shell closed the string
  early: `claude` received a **365-character** prompt plus a stray positional argument, silently
  discarding ~3,300 characters. The replacement contains **no double quotes at all**, and is
  `shlex`-verified to parse as exactly one argument of full length (**5,415 chars**) — verified
  again by round-tripping it back out of the written file.
- **`INTERPRETATION.md`'s `DataSource` guarantee was false and is corrected.** It claimed *"a number
  with no `DataSource` fails the render (L16, fail-closed)"*; every spec declares
  `data_sources: list[DataSource] = field(default_factory=list)`, so such a figure renders clean.
  Recorded as `OG-48` rather than quietly restated.
- `OG-48`…`OG-53` opened with dispositions; `OG-52` opened and closed the same day.

## [0.3.4] — 2026-08-21 · Every blocker closed; Phase 3 unblocked

Times are `+0330`. **`docs/process/OPEN_GATES.md` carries zero `BLOCKS_PHASE_3` rows.**

Four verification passes produced **270 recorded findings**. Every one is now fixed, demoted to
`NOT_A_DEFECT` with reasoning a future verifier can attack, or scheduled to a phase whose
`BUILD_PLAN.md` row **names that work** — the only deferral the phase gate permits.

### One root fix closed four blockers

The ninth verifier's four most serious findings shared a single shape: **both hooks forked once per
blob and handed the scanner raw bytes.** `tools/docgen/hooks/materialise.py` replaces that with one
`git cat-file --batch` process.

| blocker | what it actually cost |
|---|---|
| `OG-58` | 1000 tiny files totalling 10,890 bytes took **331 seconds** to commit — 9.9 s of it compute, the rest process creation. Not slowness: *denial of the gate*. At ~16 min for 3000 files people bypass it. |
| `OG-56` | A blob that natively **is** UTF-16 — Notepad "Unicode", PowerShell redirection — defeated the scan entirely, because `grep` cannot match across interleaved NULs. Fixing `working-tree-encoding` earlier had only **moved** this hole. Now detected by BOM or NUL density and transcoded; ASCII and binary are untouched, because over-eager transcoding would be its own defect. |
| `OG-61` | A submodule could not be committed at all: its "blob sha" is a commit in the *submodule's* object store, absent here. The only exit was `ENGINE_SKIP_PRECOMMIT=1` — **the moat teaching its own bypass**. Gitlinks are now detected by mode `160000`, the correct source. |
| `OG-57` | The commit gate certified a **snapshot**, not the commit — git writes the tree after the hook returns. The manifest is re-derived after the scan and compared, which is the assertion the hook always believed it made. |

### The remaining blockers

`OG-59` the fallback printed *"every object reachable from the pushed refs"* while running
`rev-list --all`, which is every local ref plus HEAD and **not the pushed sha**. `OG-60` `render`
and `index` wrote anywhere at exit 0 while `build` fail-closed on the identical shape. `OG-40`
`--watch` checked the L9 gate once, before the loop — *a long-lived process that checks a security
invariant only at startup does not have that invariant*. `OG-34` `CONS-07` recognised only `.py`
citations, so **the citation guard could not see the shell hooks and `.mjs` renderers that do the
enforcing**, and its block scanner stopped at a blockquote. `OG-55` `install.sh` gained `--chain`,
so a project on husky is not forced to choose between clobbering its hook and going without.

And from `OG-62`, the one that mattered most: **`tools.health --root <tree>` reported
`[PASS] RULE-01 hash-gate holds` over a rulebook carrying an injected rule** — `--root` moved every
check *except* the rule layer, because the context took its doc-system directory from the engine's
own location. A false green that gets louder the more deliberately you use the flag.

### Decisions, not deferrals

`OG-38`, `OG-39` and `OG-46` are closed **`NOT_A_DEFECT` with reasoning**. The `host_root()` row
conflated two roots that must stay distinct — the six modules compute the *engine's* root to find
vendored assets, which is the correct question there. The five JSON schemas document a shape;
wiring `jsonschema` would add a runtime dependency to re-check invariants three modules already
enforce, and **two enforcers of one rule is the defect this engine exists to catch**. `CONS-03`'s
three-edit cost is the accepted bar, because removing self-certification means moving the locked-set
declaration outside the repository the gate protects — trading a bounded weakness for an unbounded
one.

### Four defects caught by gates built the same day

- `BUILD-01`'s first version built **in place and deleted `examples/capability-gallery.html`**, a
  tracked deliverable. `SUITE-03` caught it in one run. Its second version still rewrote it every
  health run. It now builds into gitignored scratch: *a check must not write into the tree it is
  checking.*
- Widening `BUILD-01` to all three documents pulled in the flagship gallery, which needs the node
  renderers — **so every fresh clone would have failed it until `npm install`**, contradicting the
  bootstrap this repository documents. It now SKIPs on an absent toolchain, exactly as `SUITE-01/02`
  do, and `--full` still fails on the skip.
- The `--watch` hash-gate re-check called `check()` **without its required argument** — the fix for
  `OG-40` would have crashed on its first tick. `mypy` caught it.
- `SUITE-06` caught the `BUILD-01` regression in the same run that introduced it.

### Phase 3

`BUILD_PLAN.md`'s Phase 3 row now names two further deliverables so `OG-36` and `OG-47` are
**legitimately** scheduled rather than parked: one Markdown table reader replacing the five that
disagree, and the residual doc-claim findings — stale counts, dead citations, present-tense plans,
which is exactly what `counts`/`crossrefs`/`built-claims`/`present-tense` catch mechanically.

**And the corpus is this repository's own 56 tracked documents, not three fixtures.** That is
`docs/CHARTER.md` purpose 2, made concrete: the checker is proven on documents someone depends on.

Checks **30**. Counter-examples **71** + **19 retained moat attacks**.

## [0.3.3] — 2026-08-21 · The ninth verifier, and the evidence made real

Times are `+0330`. **Not a phase.** The ninth agent of the blind pass — a completeness critic over
the other eight — had died on an account weekly limit. It was re-dispatched and returned **14 new
findings**, plus a record audit that caught **both of this project's own rules being violated on its
most load-bearing claims**.

### The blocker

**`docs/confidential/` was never git-ignored.** Six sites call it *"the git-ignored
`docs/confidential/` tree"*, RULEBOOK **L14** confines every non-public document to it, both
placement gates deliberately **skip** anything inside it, and `--local-preview` actively writes
confidential renders there. It was in no ignore file. **The one location the engine instructs you to
put secret documents was the single guaranteed publication route** — a classified document placed
there committed clean, pushed clean, and reached the remote with every gate printing an affirmative
line. `STRUCT-07` now asks **git**, not the file's text: a `.gitignore` line can be overridden by a
later negation, by `.git/info/exclude`, or by a global excludes file, and only `git check-ignore`
accounts for all three. It also fails if anything inside the vault is already tracked, because
ignoring a directory does not untrack what is in it.

### My own rules, violated

| rule | what I did | evidence |
|---|---|---|
| **Rule 1** | `[0.3.2]` cited *"12-case harness, all red first, 12 passed 0 failed"* as the evidence for every moat CRITICAL, and `THREAT_MODEL.md` said those cases *"are re-run by the harness"*. **No harness existed in the tree.** It ran from `/tmp` and was discarded — exactly what Rule 1 says does not count, written by me one commit earlier. | `tools/tests/hook_attacks.sh`, now **17 attacks**, wired as `SUITE-06`. |
| **Rule 2** | Three of four severity numbers wrong (`12/14/25/10` sums to **61**; the real counts are `12/17/27/11` = 67). The charter said **53** tracked documents where there are **56** — wrong the day it was written — and **4** governed where the engine derives **3**. | `CONS-09` now **re-derives** both on every run. The charter may keep its numbers precisely because something recomputes them. It reports the gap in the charter's own terms: **5% of the corpus is under the engine.** |

### Fixed

- **Annotated tag messages were never scanned** while three places claimed they were.
  `git push --follow-tags` is the ordinary release flow, so this was a publication route.
- **The interpreter guard validated `.venv/bin/python` and then fell back to an unvalidated
  `python3` from `$PATH`** — a stub there made both placement gates and the health gate inert while
  each printed its affirmative line. **And the first fix was wrong:** it probed with
  `sys.exit(0 if version==3 else 1)` and trusted `rc=0`, which a stub that does nothing but `exit 0`
  satisfies perfectly — *a guard against faked exit codes that was itself reading an exit code*
  (`L-18`). It now demands output only a real Python can produce. **The retained harness caught
  this on its first complete run**, which is Rule 1 paying for itself: run by hand from `/tmp` as
  before, it would have shipped broken and looked green.
- **pre-push took `rc=0` as success without checking health printed a verdict**, so a silent health
  run certified the push.
- **The documented bootstrap's first command exited 1** — `pip install --quiet PyYAML` hits PEP 668
  `externally-managed-environment`, and it is `&&`-chained inside the copy-paste launch command, so
  the next session died at *"verify the floor"* before doing anything.

### Rule 1 gains the clause the critic earned

> **The counter-example must cover the CLASS, not the instance.** When you fix something, the very
> next question is *what is the sibling of the thing I just closed?*

Its evidence: **every one of its four most serious findings was a fix that MOVED a hole rather than
closing it.** UTF-16 out of `git archive` and into the blob; the interpreter guard onto `.venv` and
off `$PATH`; the message scan onto commits and not tags; the range fallback off tip-trees and onto
`--all`, which is not the pushed sha either. Each fix was correct. Each left a sibling standing.

### Recorded, not fixed

`OG-56`…`OG-62`: a blob that natively **is** UTF-16 still defeats the scan (`THREAT_MODEL.md` lists
UTF-16 as closed — it is not); the index TOCTOU; the O(n) fork storm that makes it practical
(1000 tiny files = **331 s**, of which 9.9 s is compute); the `--all` versus pushed-sha divergence;
writing entry points with no containment or collision guard; submodules being uncommittable with the
only exit a total bypass — *the moat teaching its own bypass*; and **18 Pass-4 findings in no row
plus 6 rows that misdescribe their own defect**, one of which a previous pass had already flagged.

**Blockers 12 → 18. That is the number going the right way**, not the wrong one: it is what happens
when a register stops flattering itself.

Checks 27 → **30** (`STRUCT-07` vault, `CONS-09` charter counts, `SUITE-06` moat attacks).
`python3 -m tools.health --full` → **30 passed, 0 failed, 0 skipped**, including all 17 attacks.

## [0.3.2] — 2026-08-21 · Blind claim-attack, and the moat rebuilt on objects

Times are `+0330`. **Not a phase.** The correction pass that followed `0.3.1`, run by a method that
had not been tried before and that is now the standard.

**What changed about the method.** Eight independent agents were each handed a **CLAIM about the
repository and told to break it** — never told anything had been fixed, never shown a diff, and
explicitly forbidden from looking for one. An agent told what was fixed verifies *the fix*; an agent
handed a guarantee attacks *the guarantee*. Every earlier pass had been given the work to review.

**All 8 claims BROKEN. 67 findings — 12 CRITICAL, 17 HIGH, 27 MEDIUM, 11 LOW.** Four rounds of the
implementer's own falsification had found none of them. Full text: `docs/process/VERIFICATION_LOG.md`
Pass 4.

### The twelve CRITICALs were four root causes

| root cause | what it cost |
|---|---|
| The gate scanned a filesystem **rendering** of the objects, not the objects | 6 of 12 |
| The moat trusted **untracked local state** | 3 of 12 |
| The integrity checks were structurally too weak | 2 of 12 |
| Range computation was wrong | 1 of 12 |

### Fixed — the moat now reads blob objects

| time | change | files | evidence |
|---|---|---|---|
| 11:5x | **Both hooks rewritten to enumerate blob objects and read them with `git cat-file`.** `git archive` and `git checkout-index` are lossy, *configurable* projections of the object store, and every knob that configures them was a hole: `export-ignore` from a tracked **or untracked** `.gitattributes` made a path vanish from the scan while the blob reached the remote; smudge filters and `working-tree-encoding` meant the scanned bytes were provably not the recorded bytes; two paths differing only in case collided on APFS and one blob overwrote the other; `find -type f` skipped symlinks. Blobs are now written named by **SHA, never path**, which additionally defeats the portfolio scanner's basename self-exclusion — relevant because portfolio rule **S2 instructs projects to vendor a file called `secret-scan.sh`**. | `tools/hooks/pre-push`, `tools/hooks/pre-commit`, `staged_content_scanner.py` (new blob-true `--manifest` mode) | 12-case harness, all red first: export-ignore tracked/untracked, smudge filter, peer-remote inheritance, unresolvable range, vendored scanner name, commit message, UTF-16 encoding filter, case collision, fake interpreter, plus two controls. **12 passed, 0 failed**, and each refusal verified to come from the secret gate with health green — not from health failing incidentally. `LESSONS.md` **L-21**. |
| 11:5x | **Range computation corrected.** `--not --remotes` subtracted every remote-tracking ref including a *different* remote's and a fetched peer's, so "fetch a colleague's branch, add a commit, push it" published unscanned commits. Now scoped to the remote being pushed to. And the unresolvable-range fallback no longer archives each ref's **tip tree** — that was endpoint scanning, the exact defect the hook documents as fixed, surviving one code path over. | `tools/hooks/pre-push` | Both proven red with a real peer clone and a real force-push race. |
| 11:5x | **Commit and tag messages are scanned.** A key pasted into a message is published exactly like a file and is one of the most common accidental leaks. | `tools/hooks/pre-push` | Falsified red. |
| 11:5x | **The interpreter is part of the moat.** An untracked `.venv/bin/python` containing `exit 0` neutered every Python gate in both hooks — no tracked file modified, no re-baseline needed, health still green. A non-default interpreter must now announce itself and prove it is a working Python 3. | both hooks | Falsified. |
| 11:5x | **Each hook asserts its own gate count.** Deleting a gate's invocation left the others printing affirmative lines and exiting 0. Removing a gate now takes two coordinated edits, and the assertion is itself a marker `STRUCT-03` checks for. | both hooks | — |

### Fixed — three accidental vectors outside the hooks

| time | change | files | evidence |
|---|---|---|---|
| 12:1x | **`rulebook_sha256: PENDING` no longer accepts arbitrary drift.** Checking with the sentinel recorded meant the rule set was UNLOCKED and the gate verified nothing — yet it returned a non-blocking INFO, so `cli check` reported PASSED and health printed `[PASS] RULE-01 hash-gate holds — no undeclared rulebook drift`, a summary line that was **literally false**, over a `RULEBOOK.md` rewritten to carry any rule at all. The one string that betrayed it was visible only under `--json`. Now blocking on check; `--write-hash` still completes the sanctioned two-step. | `validate_doc_system.py` | Falsified three ways: health blocks, `cli check` blocks, `--write-hash` still works. |
| 12:1x | **An empty `confidentialDir` no longer disables the L14 placement gate.** One character in `engine.config.json` made every path in the repository test as *inside the confidential vault*. | `engine_config.py` | Falsified: a `classification: secret` document at the root is refused with the config blanked. |
| 12:1x | **Front matter is recognised behind a BOM or a leading HTML comment.** The pattern anchored at byte 0 without `re.MULTILINE`, so any document carrying one leading comment — **the house style of every process document in this tree** — parsed as header-less and the placement gate skipped it. Worse, a leading `<!-- classification: public -->` over YAML saying `secret` passed on the comment's word. | `classification.py` | Six shapes verified, including the dangerous one: YAML now wins over the comment. |
| 12:2x | A marker hidden in a **trailing** comment (`exit 0  # -m tools.health "$SCANNER"`) satisfied `STRUCT-03`; whole-line stripping was not enough. Gate 3 and the gate-count assertion are now named by markers too — either could previously be deleted outright. | `tools/health/checks.py` | Falsified with the attacker's exact three-line hook: now FAILS, naming all four missing markers. |
| 12:2x | `TYPECHANGE` entries were dropped from the staged enumeration (`--diff-filter=ACMR`), so a classified document written over a symlink was invisible. | `staged_content_scanner.py` | — |
| 12:2x | `STRUCT-06` now **SKIPs** rather than FAILs when the stamped commit is absent. Every verification lab in this project is a `git archive` + `git init` export with its own history, so failing painted every lab red for a reason unrelated to what it tested — and a gate that is red for irrelevant reasons is one people learn to ignore. A SKIP is still not a pass: `--full` and `--strict` both fail on one. | `tools/health/checks.py` | — |

### Scoped rather than patched — the decision that ended the arms race

Three of the twelve CRITICALs were reachable **only by deliberately editing the hook that was
supposed to stop you**. No client-side hook survives that: `--no-verify` disables every hook with
exit 0 and no output, and whoever can install a hook can delete it. **Those were never fixable, and
the defect was in the claim, not the implementation** — the moat had been described in three
documents as making leaking *impossible*.

**`docs/process/THREAT_MODEL.md`** now states what the moat is (*a guard against accidental
publication by a cooperating developer* — achievable, and now achieved) and what it is not (*a
security boundary* — impossible client-side, and a declared Phase 7 deliverable). `LESSONS.md`
**L-22** generalises the decision: when a verifier breaks a claim, first ask whether the claim was
ever achievable, because chasing an unachievable one consumes the sessions that should have built
the product.

### Corrected — my own false claims from `0.3.1`

The attackers audited the register this session had just written, and found it wrong in five places.
Each is the exact defect class the register exists to record.

- `OG-43` cited **`_load_figure_specs`, a symbol that exists nowhere** — the real reader is
  `generator._load_sibling_figure`.
- `OG-03`'s evidence contradicted itself in one sentence.
- `OG-34` asserted a defect **with no evidence at all**, violating the file's own Rule 2.
- `OG-33` **undercounted its own defect**: `CONS-06` has a fourth blind spot — it scans only tracked
  `.md`, so path citations in `.py`/`.json`/`.html`, where most of this engine's citations live, are
  invisible.
- `BUILD_PLAN.md` still described the manifest as shipping **one** row (it ships eight) at a site the
  `0.3.1` sweep missed.
- **The `Lines` column in `BUILD_PLAN.md` is deleted, not re-measured.** It was re-measured in
  `0.3.1` with a note saying *"do not hand-maintain these"* — and **four of six were stale again
  within the same session**, because the fixes being recorded changed the files. A number a document
  restates about code it does not own cannot be kept true by discipline.
- `USAGE_GUIDE.md` printed `22/22 acceptance simulations` under a command that runs only the unit
  suite, and cited `../chart-engine/SKILL.md`, a path that escapes the repository.

### The picture, restated

**`docs/CHARTER.md`** — new, and the anchor a long build drifts away from. This repository is **one
project with two purposes**: build the engine, and *be the engine's own test corpus*. Measured at
this commit: **56 tracked Markdown documents, 3 governed by the engine, all 3 fixtures.** That gap
is why three verification passes found overwhelmingly stale counts, present-tense plans, dead
citations and self-contradicting registers **by hand** — every one of those is a defect class the
engine exists to catch mechanically, and it cannot, because its corpus is three samples.

The charter also names what is *not* the product — the moat, `tools/health`, the registers — and
carries an anti-drift rule: **every session must name which purpose its work served before it
commits.** This session's honest answer is *scaffolding, twice in a row*, which the charter says out
loud is a signal.

## [0.3.1] — 2026-08-20 · Whole-system verification pass and its fixes

Times are `+0330`. **Not a phase.** Phase 2 shipped at `0.3.0`; this is the correction pass that
followed it, run against the *whole repository* rather than one phase's diff.

**What was run.** Twelve independent verifier agents against frozen commit `d12a13e`, none of which
saw the implementer's reasoning: fresh-clone reality, gates-and-hooks, baseline-and-suites,
claims-vs-reality, open-gates audit, cross-document truth, data-file contracts (60+ file-corruption
mutation runs), gatekeeper topology, modularity, hygiene, next-phase readiness, and a completeness
critic over the other eleven. **All twelve returned `DEFECTS_FOUND`: 136 raw findings — 8 CRITICAL
(5 distinct), 29 HIGH, 58 MEDIUM, 41 LOW.** Every finding is preserved verbatim in
`docs/process/VERIFICATION_LOG.md`.

**Where they came from, measured against `git`.** All five distinct CRITICALs are in the git moat —
the thing Phase 2 built one commit earlier and reported complete, green, and falsified four separate
ways. The pre-existing engine (generator, sanitizer, classification, project index, renderers)
contributed 15 findings and **zero** criticals.

### Fixed — CRITICAL (each shown red in a real push lab with a real bare remote, before the fix)

| time | change | files | evidence |
|---|---|---|---|
| 21:1x | **The pre-push secret gate scanned the endpoint diff, not the commits.** `git diff remote local` sees start-vs-end only, so a key committed and then removed or redacted by a later commit *in the same push* was published under an affirmative "clean" line. Now walks `git rev-list` and materialises **every commit's own bytes into its own directory** — the per-commit directory is load-bearing, because a later clean version extracted over an earlier dirty one is exactly how the leak hid. | `tools/hooks/pre-push` | Red first: add-then-delete → `exit 0`, `nothing to scan`, `git show <A>:transient.txt` → the AWS key **on the remote**. Add-then-redact → `exit 0`, `clean (1 pushed file)`, key on the remote. After: both **REFUSED**. |
| 21:1x | **The fallback path still scanned the branch you were standing on.** When the range cannot resolve (force-push race, shallow clone, rewritten remote) it ran `git archive HEAD` instead of the ref being pushed — the identical wrong-artifact defect `L-15` was written for, one code path over. | `tools/hooks/pre-push` | Red first, real force-push race with a second clone: standing on clean `master`, pushing `sidebr` whose tip held a key → `exit 0`, `secret scan clean (257 pushed file(s))` — 257 being `master`'s file count — key on the remote. After: **REFUSED**. |
| 21:2x | **pre-commit's secret gate read the working tree, not the index.** It called the scanner with no arguments; that mode takes path *names* from `git diff --cached` and greps them **on disk**. Now materialises the index with `git checkout-index` and scans that, exactly as pre-push does. The hook's own header had asserted the opposite. | `tools/hooks/pre-commit` | Red first: stage a 2-line AWS key pair, redact the worktree copy, commit → `exit 0` and `✓ 1 lines actually read` while `git show HEAD:staged.txt` held both lines. After: **REFUSED**. |
| 21:3x | **`STRUCT-03`/`STRUCT-04` were satisfied by comments.** A whole-file substring test, so both hooks could be reduced to `exit 0` stubs that merely *mention* the marker strings and health still reported them "installed, current, and still gating". Three defences now: markers matched against **executable lines only**; a **two-sided behavioural probe** of the installed pre-commit hook (clean index must pass, planted secret must fail — one-sided would pass vacuously for a brick); and both hooks **hash-locked** into `rulebook_files`. | `tools/health/checks.py`, `docs/design/doc-system/VERSION.json`, `docs/design/doc-system/RULEBOOK.md` | Stub attack → both **FAIL**. Subtle weakening (real body, gate 2 neutered) → `STRUCT-04` **"installed but DOES NOT GATE"**, caught behaviourally where the structural test could not. One appended comment line → `RULE-01` BLOCKED. |
| 21:4x | **`--no-verify` was a total silent bypass, named nowhere.** Cannot be closed client-side; now named in `HANDOFF.md`, both hook headers, `CONFIGURATION.md` and `LESSONS.md` L-20, made a declared **Phase 7 deliverable** with its own exit condition, and materially reduced: because pre-push now scans every commit in the range, `commit --no-verify` is caught at push time (falsified). | `HANDOFF.md`, `tools/hooks/*`, `CONFIGURATION.md`, `docs/plan/BUILD_PLAN.md` | `git grep -- '--no-verify'` at `d12a13e` → **zero hits**. `gh api …/protection` → `Branch not protected`. |

### Fixed — HIGH

| time | change | files | evidence |
|---|---|---|---|
| 21:5x | `CONS-06` resolved cited paths against the **filesystem**, so an untracked gitignored directory satisfied a citation — green here, red on every fresh clone, and because pre-push runs health, **no fresh clone could push until it had run `npm install`**. A zero-byte empty directory satisfied it. Now resolves against `git ls-files` plus the declared-absent registry. | `tools/health/checks.py`, `docs/process/ABSENT_PATHS.md` | Immediately surfaced a second untracked citation (`__pycache__/`) that no verifier had found. Fresh-clone bootstrap verified end to end: hooks-only → `HEALTHY 21/0/2`; full bootstrap → **25 passed, 0 failed, 0 skipped**. |
| 21:5x | `--full` reported **HEALTHY over checks it could not run**. A skip now fails the run under `--full`, whose whole meaning is "run everything". | `tools/health/run.py` | Falsified: `--full` on a clone with no `node_modules` → **UNHEALTHY**, where it used to exit 0 over an unbuildable flagship. |
| 21:5x | The npm suite check asserted **only the exit code** while printing `expected 30/30` — a literal never compared to anything. Now parses the suite's own summary and asserts it. | `tools/health/checks.py` | Falsified: one test marked `.skip` → `skipped=1 (must be 0); pass=29 is below the floor of 30`. |
| 21:5x | `UnicodeDecodeError` escaped `except (OSError, JSONDecodeError)` at twelve sites; one bad byte in `engine.config.json` took down **every entry point**. Swept, plus `project_index` now refuses to overwrite an index it could not parse. | `engine_config.py`, `project_index/index.py`, `build_index.py`, `doc_manifest.py`, `adjudication.py`, `i18n.py` | Falsified: non-UTF-8 config → no traceback; corrupt index → `IndexUnreadable`, file byte-identical, prior content intact. `LESSONS.md` **L-17**. |
| 21:5x | The cache key did not cover the **out-of-tree renderers**, so editing `tools/mermaid-engine/render.mjs` or an ECharts adapter left `--cached` serving a stale artifact under a success message. Key format bumped to `v3`. | `tools/docgen/build_cache.py` | Falsified: warm → `3 reused in 0.009s`; mutate `render.mjs` → `3 rebuilt`; mutate an adapter → `3 rebuilt`; restore → reused. |
| 21:5x | `CONS-08` was blind to the one line in `START_NEXT_SESSION.md` a human actually executes — the 2,684-character launch command — for two independent reasons: a `bump` early-`continue` skipped the whole line, and the count regex accepted only the comma form. | `tools/health/checks.py` | Falsified: corrupting the slash-form floor inside the launch command → `states a health floor of 99 check(s) … but 25 are registered`. |
| 21:5x | The commit-time placement gate ran **only for `git commit`** — `merge`, `cherry-pick` and `rebase` all create commits without it. Now also runs at push time over the materialised pushed trees. | `tools/hooks/pre-push`, `staged_content_scanner.py` | Falsified: classified doc committed with `--no-verify`, push **REFUSED**; ordinary clean commit + push still exit 0. |
| 21:5x | The placement gate could not see the **legacy `<!-- classification: X -->` form** used by 11 tracked documents carrying a foreign vocabulary (`INTERNAL`/`GITHUB`) this engine does not implement. Now fails closed on any value but `public`; the 11 files normalised and the two stale instructional lines corrected. | `staged_content_scanner.py`, 11 documents | Falsified end to end through the installed hook: `<!-- classification: secret -->` → **COMMIT REFUSED**; `public` → accepted. |
| 21:5x | `BUILD-02` was hardcoded to `sample.md`, so the 7-gate spine never ran against any other document. Now derives the set from every tracked document whose front-matter declares `classification`. | `tools/health/checks.py` | Falsified: breaking `capability-gallery.md`'s header → `cli check fails on 1 of 3`. |
| 21:5x | `CONS-04` derived its gate universe from `PRECEDENCE` — the structure it was checking. Now derived from the `gate="…"` labels the source actually emits, asserted **both** ways. | `tools/health/checks.py`, `export_sanitizer.py`, `adjudication.py` | It immediately found **eight** unlisted gates, two of which no verifier had named. Falsified both directions. |
| 21:5x | `CONS-01`/`CONS-02` passed vacuously on empty input. Guarded. | `tools/health/checks.py` | `LESSONS.md` **L-19**. |
| 21:5x | Per-document crash isolation existed only on the **cached** path, so the same corpus and command produced two different failure surfaces depending on a performance flag; and an unrecognised figure `kind` rendered **silently as a flowchart** with the author's correct caption, exit 0, no finding. | `tools/docgen/cli.py`, `generator.py` | Falsified: unknown kind → identical `BLOCKED (1 of 2)` on both paths, healthy document still built. |

### Fixed — hygiene, orphans and false claims

| time | change | files | evidence |
|---|---|---|---|
| 22:0x | **`render_ms`, a wall-clock value, is no longer persisted** into tracked validation evidence whose own release record declares `date_basis: content-derived (no clock in the render path)`. Seven files changed on every run, so the tree was permanently dirty and a real regression would hide in the noise. | `tools/visual-engine/adapters/echarts/render.mjs` | Three consecutive `simulate` runs → zero further churn; `npm test` still 30/30. |
| 22:0x | **Three orphaned modules deleted** (909 lines): the bank-judgement collector, the animations generator, and `surface_channel_router.py` — 353 lines implementing L3's physical-routing half with zero callers and **unwireable as written**: run against this repository it produced 104 blocking findings, treating every tracked `.json` as a rendered export. All three declared in `ABSENT_PATHS.md`. | — | L3's declared status names only the header-validity half, so nothing overclaims. |
| 22:0x | **ruff 22 → 0**, including two real bugs: an undefined `RoutedEdge` annotation, and two ambiguous implicit string concatenations inside list literals. **mypy `--strict` 34 → 23**, the fixed 11 including a real `Path / None` crash on a config with a `null` value. Baseline pinned and gated. | across `tools/`, `tools/health/lint_baseline.json` | New `SUITE-04`. Falsified: one introduced ruff error → ceiling exceeded. `LESSONS.md` **L-18**. |
| 22:0x | `ci_cost_control` had **never passed here and nothing ran it** — it fabricated a phantom workflow file when `.github/workflows/` was empty and reported `fail-closed`. Zero workflows is the policy's goal; now reported as a stated scope, and **wired into health** as `STRUCT-05`. | `ci_cost_control.py`, `tools/health/checks.py` | Falsified with a push-triggered `write-all` workflow → 5 violations. |
| 22:0x | `RULEBOOK.md` L1 enumerated a **7-gate spine** while the code held 9, then 17. The enumeration is **deleted**, not re-counted: L1 now fixes the order of the *categories* and names `PRECEDENCE` as the single home of membership. | `RULEBOOK.md` | It had been wrong twice; `CONS-04` now guards the real thing. |
| 22:0x | **`CLASSIFICATION.md` written** — cited as normative by 18 code sites and absent. Resolves the `OG-05`/`OG-13` contradiction in the text of both. | `docs/design/doc-system/CLASSIFICATION.md` | — |
| 22:0x | `ENGINE_DOC_SYSTEM_DIR` moved the taxonomy but left the manifest and `VERSION.json` behind — a silently **split rule layer**. Children now resolve under it. | `engine_config.py`, `engine.config.json` | Falsified: the whole rule layer relocates together; defaults unchanged. |
| 22:0x | A raising check reported its **function name**, not its documented id, so `STRUCT-05` failures printed a string no register or brief can be grepped for. | `tools/health/run.py` | Falsified: forced exception → `[FAIL] STRUCT-05`. |
| 22:0x | `BUILD-03` **discarded the exit code** of every subprocess it ran, so it greped the stdout of commands that may not have run at all. | `tools/health/checks.py` | — |
| 22:0x | `ENGINE_SECRET_SCAN` did not announce itself — pointing it at any binary that exits 0 replaced the secret gate with nothing under an affirmative "clean" line. Now warns on stderr in both hooks. | `tools/hooks/*` | `LESSONS.md` **L-20**. |
| 22:0x | False counts corrected across the tree: the bundled manifest ships **eight** rows, not "one" (3 documents); the sanitizer runs **7** gates, not "9" (7 files); `BUILD_PLAN.md`'s hardcoded module line counts re-measured; its §1 present-tense snapshot dated rather than silently rewritten; `README.md`'s flagship cached-build example replaced with the three explicit paths that actually produce the printed output. | `CONFIGURATION.md`, `DOC_MANIFEST.md`, `README.md`, `BUILD_PLAN.md`, 7 others | The README example now reproduces its own output: `3 rebuilt` then `3 reused from cache` in `0.009s`. |
| 22:0x | **PyYAML is a real dependency** and one document claimed the opposite. Added to all three bootstrap blocks; the false "no install needed beyond stdlib" line deleted. | `HANDOFF.md`, `NEXT_SESSION.md`, `START_NEXT_SESSION.md`, `USAGE_GUIDE.md` | On a `python3` without it the documented bootstrap ends UNHEALTHY with 6 failures. |

### Crash-recovery record

| time | change | files | evidence |
|---|---|---|---|
| 22:4x | **`docs/process/SESSION_STATE.md`** — a stamped, per-item checklist of what this session actually finished, with the proof for each, plus a chronological log and explicit recovery instructions. It exists so a session that crashes loses no work and, just as importantly, **does not redo finished work**. It carries a machine-greppable stamp (`<!-- session-state: <STATE> @ <commit> on <date> via <pass> -->`) and a written **definition of done** whose bar is four-part: it runs, it was shown red first, it is in `CHANGELOG.md`, and it is committed. | `docs/process/SESSION_STATE.md`, `HANDOFF.md` | Wired into `HANDOFF.md`'s register table; `CONS-06` refused it until it was tracked, which is the citation guard working. |
| 22:4x | **`STRUCT-06`** — enforces the stamp, because a claim nobody checks is decoration (`LESSONS.md` L-18). Asserts the stamp exists, parses, uses a state the document itself defines, names a commit that really exists, and is an ancestor of `HEAD` (so a reset is caught rather than silently believed). The state **vocabulary is derived from the document's own table**, not hardcoded, so the two cannot drift (L-13). It checks the mechanical half only and says so — whether a checklist is honest is not machine-decidable. | `tools/health/checks.py` | Falsified three ways: invented state word → FAIL naming the real vocabulary; non-existent commit → FAIL; stamp deleted → FAIL. |
| 22:4x | Removed a drifting count from a dated evidence row rather than restating it. `OG-21`'s closed row quoted a live check count that goes stale every time a check is added; it now records *green with zero failures and zero skips* and lets `tools.health` be the only place the number lives. | `docs/process/OPEN_GATES.md` | This is the `counts` guard's own advice applied to the register that recorded it. |

### Process

- **The operator's phase gate is now law:** a phase does not begin while a known defect is open, and
  the only permitted deferral is a defect whose fix *is* a named later phase's declared main work.
  `OPEN_GATES.md`'s disposition vocabulary was rebuilt around it — `SHOULD_FIX`, `NEXT_SESSION`,
  `NICE_TO_HAVE` and open-ended `ACCEPTED` are retired, because 19 of 26 open rows were parked under
  them with no forcing event.
- **`docs/process/VERIFICATION_LOG.md` created** — the append-only raw record of every pass, in the
  verifiers' own words, so curation into `OPEN_GATES.md` can no longer lose a finding.
- **18 gates closed** with falsification evidence; **17 opened** (`OG-31`…`OG-47`) for what this pass
  found and this session did not fix. **Phase 3 is blocked until `OG-32`…`OG-47` close** — that is
  the phase gate applied to this session's own output, not an exception carved for it.
- Health checks 23 → **26** (`STRUCT-05` CI policy, `SUITE-04` lint/type baseline,
  `STRUCT-06` session-state stamp). The evidence rows above quote the counts measured at the
  time they were run — they are dated measurements, not claims about the current floor.
- A correction to this project's own history: **Phase 1 did not end at zero findings.** It ended with
  24 rows carried in the register, and no pass had ever been re-run against its own fixed tree until
  this one.

## [0.3.0] — 2026-08-20 · Phase 2 — expose what exists

Times are `+0330`.

**Phase 2's exit condition, measured, not asserted:** a second build of an unchanged 3-document
corpus (`sample.md`, `sample-multi-figure.md`, `capability-gallery.md`, formats `html,json`) went
**3.359s → 0.003s**, `0 reused / 3 rebuilt` → `3 reused / 0 rebuilt`; and `cli index` over that
corpus renders an index listing 3 real documents (`WF-201`, `WF-301`, `WF-501` verified present in
the **rendered HTML**, not just in the source).

| time | change | file | section |
|---|---|---|---|
| 10:50 | **`build --cached` — the phase deliverable.** `build_cache.py` (322 lines, written in Phase 0, exposed by nothing) is now on the CLI. `build` takes **one or many** inputs and routes a corpus through `build_corpus` — one cache load, one engine fingerprint, one save — so an N-document build no longer re-hashes the engine N times. `--cached` picks the conventional cache (`<out-dir>/.docgen_cache.json`, else `.docgen/.docgen_cache.json`); `--cache PATH` still names one explicitly. | `tools/docgen/cli.py` | `_resolve_cache_path`, `_build_paths`, `_emit_corpus_summary`, `_cmd_build`, `build_parser` |
| 10:50 | Every cached build now prints one **measured** line — `built N doc(s) in T s — R reused from cache, B rebuilt` — so a cache hit is evidence the tool produces, not a claim an operator makes with a stopwatch. | `tools/docgen/cli.py` | `_emit_corpus_summary` |
| 10:50 | **Latent fail-open closed before it shipped.** A cache skip emits only the INFO "reused cached build" finding, so `--strict` (advisories are failures) would either have failed every cached build or, worse, passed a document that *was* advisory-dirty because it was skipped. `--strict` now ignores the cache and says so. | `tools/docgen/cli.py` | `_resolve_cache_path` |
| 10:50 | `_repo_rel` made public as `repo_rel` — the CLI needs it to line `CorpusResult.results` back up with input order, and reaching into a private helper for that is how a consumer ends up carrying a `noqa: SLF001` forever. | `tools/docgen/build_cache.py` | `repo_rel` |
| 10:47 | **`-o` at a directory that does not exist** crashed with a `FileNotFoundError` traceback out of `pathlib` — and `--cached` makes that path far more common, since the cache lives beside the outputs. Now created, or exit 2 with the reason. | `tools/docgen/cli.py` | `_cmd_build` |
| 10:46 | **A non-existent input** surfaced as a raw traceback, and in a corpus did worse: it aborted mid-list, so `save_cache` never ran and every entry earned earlier in that run was discarded. Inputs are validated up front; a usage error is exit 2, not a stack trace. | `tools/docgen/cli.py` | `_cmd_build` |
| 10:59 | **OG-10 closed — the git moat is live.** New engine-wide `pre-push` hook: `python3 -m tools.health` plus a secret scan **scoped to the files the push actually carries** (`--all` would block a push over an untracked scratch file, and a false red trains bypassing). Both gates fail closed; a missing scanner refuses the push rather than waving it through; `ENGINE_SKIP_PREPUSH=1` bypasses but announces itself. | `tools/hooks/pre-push`, `tools/hooks/install.sh` | new files |
| 10:59 | **The old sample hook was deleted, not fixed.** `tools/docgen/hooks/pre-push.sample` ran `cli check --strict` with **no input path**: it exited 2 on a usage error, so under `set -euo pipefail` it would have blocked every push if anyone had installed it. Two competing pre-push hooks is the two-sources-of-truth defect this engine exists to catch. | `tools/docgen/hooks/pre-push.sample` | **deleted**; README repointed; declared in `ABSENT_PATHS.md` |
| 11:02 | **Portability trap caught by falsification, not review.** The hook's first draft read git's stdin with `mapfile` — bash 4+. macOS ships bash 3.2 at `/bin/bash`, where it fails "command not found", leaving the file list empty, which the script would then have reported as *"nothing to scan"*: a secret gate that silently no-ops and prints a pass. Replaced with a portable `while read` loop, plus an explicit branch for "no ref lines on stdin" that scans all tracked files rather than nothing. Re-proven end to end under `/bin/bash` 3.2. | `tools/hooks/pre-push` | stdin range loop |
| 11:00 | `tools.health` **STRUCT-03**: the pre-push hook must be installed, executable, and **byte-identical** to `tools/hooks/pre-push`. Presence alone would pass an empty or stale file. Outside a git repo it SKIPs with the cause. This is what makes an inert moat loud instead of invisible. | `tools/health/checks.py` | `check_prepush_hook_installed`, `CHECKS` |
| 10:56 | **OG-14 closed — health logs by default.** Append-only JSONL run log at `.health/runs.jsonl`: timestamp, commit sha, dirty flag, duration, counts, failed and skipped ids. `--run-log PATH` and `--no-run-log` control it. An unknown git state records `null`, never a guess. A write failure is announced on stderr and **never** changes the exit code — observability must not turn a green engine red, and silence would reopen this gate invisibly. | `tools/health/run.py` | `_RUN_LOG_RELATIVE`, `_git_state`, `_append_run_log`, `main` |
| 10:56 | `--log`'s "report written" notice moved to **stderr**. Under `--json` it was printed to stdout, so the machine-readable output was not parseable JSON whenever both flags were used. | `tools/health/run.py` | `main` |
| 11:07 | **OG-15 closed.** RULE-03 derives its universe from `update_impact_map.json`'s own `change_types` keys instead of a hardcoded 5-tuple, so a sixth change type is validated the moment it is added. The documented five are kept as a **floor** assertion — deriving from the map alone would let a deletion pass, since the map would simply have fewer keys and every one of them fine. | `tools/health/checks.py` | `_BASELINE_CHANGE_TYPES`, `check_impact_map` |

### Fixed — two blind spots found inside `CONS-06` while closing OG-10

| time | change | file | section |
|---|---|---|---|
| 11:04 | **A five-character extension cap made the check blind.** `CONS-06`'s regex ended `\.[A-Za-z0-9]{1,5}`, so it could not see any citation of a `.sample`, `.geojson`, `.template` or `.properties` path — and it duly reported *"every cited repo path resolves"* while two tracked documents cited a file deleted in the same session. Widened to `+`; the red was shown first, then fixed. | `tools/health/checks.py` | `check_doc_paths_resolve` |
| 11:05 | **The suppression registry excused more than it declared.** The "declared absent" set was built by running that regex over **all of** `ABSENT_PATHS.md`, including the column naming *what replaced* each file — so **7 real files**, among them `RULEBOOK.md`, `DOC_WRITING_DOCTRINE.md` and `OPEN_GATES.md`, were exempt from the check repo-wide. Now parsed from the first column only: 21 declared-absent paths → 14, of which 0 exist. | `tools/health/checks.py` | `check_doc_paths_resolve` |
| 11:03 | `ci_cost_control` repointed at the real hook after the sample was deleted, and `tools.health` accepted as a gate invocation (it runs the hash-gate as RULE-01 and `cli check` as BUILD-02). A comment now records what its pattern check **cannot** see: it proves the hook *mentions* the gate, never that the hook runs — measured against the deleted sample, which it passed. | `tools/docgen/ci_cost_control.py` | `DOCGEN_PREPUSH_HOOK`, `_GATE_INVOCATION_PATTERNS` |
| 11:12 | **A stale rulebook version in the handoff documents, and a guard against the recurrence.** `HANDOFF.md` and `NEXT_SESSION.md` both told the next session the rulebook was `1.1.0` while `VERSION.json` had said `1.2.0` since the previous session — the most expensive kind of wrong, since a handoff is read first and reasoned from. Corrected, and **CONS-08** added: the three state documents may not misquote the rulebook version. Its first draft flagged the *project* version on the same line as a stale rulebook claim, so the pattern was tightened to require the semver to follow the word "rulebook"; transition records (lines with an arrow) are skipped so an accurate history entry never fails. Falsified both ways. | `tools/health/checks.py`, `HANDOFF.md`, `docs/plan/NEXT_SESSION.md` | `check_state_docs_rulebook_version`, state tables |
| 11:08 | `L-14` recorded: a check's pattern and its suppression list are both part of its universe, and both shrink it silently. | `docs/process/LESSONS.md` | L-14 |
| 11:08 | Register updated: OG-10, OG-14, OG-15 closed with falsification evidence; OG-24 (no per-document error isolation in `build_corpus`), OG-25 (`ci_cost_control` has never passed here and nothing runs it), OG-26 (the secret scanner lives outside the repo) recorded. | `docs/process/OPEN_GATES.md` | Open, Closed |
| 11:04 | `.docgen/` and `.health/` gitignored — derived state. Committing either would let a stale entry skip a build that never ran in this checkout, or attribute another machine's run to this one. | `.gitignore` | new block |

---

### Fixed — found by the Phase 2 deep verification pass (11 independent agents, 72 raw findings)

**Two CRITICALs, both in work this same session had already falsified four ways and reported green.**
That is the pass earning its cost: `LESSONS.md` L-15 and L-16 are the generalisations.

| time | change | file | section |
|---|---|---|---|
| 12:52 | **CRITICAL — the secret gate was reading the wrong artifact.** The `pre-push` hook took file *names* from git history but scanned the *working tree*, and on the new-branch path ran `git ls-files`, which lists the branch you are standing on. So the ordinary workflow — commit on a side branch, switch away, push it — was scanned against a different branch entirely and passed clean. It now materialises the pushed commit's own bytes with `git archive` into a temp tree and scans that. Proven end to end: a key header committed on a side branch, working tree clean, standing on `master` → **push REFUSED**, 258 pushed files scanned, probe named. | `tools/hooks/pre-push` | Gate 2 |
| 12:52 | The hook never checked the exit status of its `git` calls, so an unresolvable range (a remote sha this clone lacks) produced an empty file list and printed *"nothing to scan"* — the same no-op-that-prints-a-pass the `mapfile` rewrite existed to eliminate. Both git calls are now checked and degrade to the whole HEAD tree, announced. Paths are NUL-delimited (`-z`) so a path git would quote is no longer silently dropped, and `--diff-filter=d` drops deletions, which have no bytes to scan. | `tools/hooks/pre-push` | `extract_range` |
| 12:40 | **CRITICAL — a cache hit bypassed a BLOCKING gate.** `compute_key` covered the document and `tools/docgen/*.py` and nothing else, while a hit synthesises a *passing* `GateResult` without re-running anything. Five proven classes of wrong hit: `assets/glyphs.py` (below a non-recursive glob), `assets/tokens.json`, the embedded `fonts/*.woff2`, the output directory, and the entire doc-governance rule layer — so editing `DOC_MANIFEST.md` to make a document illegal left it building green from cache. The fingerprint is now recursive and content-typed over every file under `tools/docgen/`, a second fingerprint covers the rule layer at its resolved paths, `out_dir` is in the key, and `_CACHE_FORMAT` is **v2** so every v1 entry is a miss rather than something trusted. Each class re-falsified: tokens.json, glyphs.py, `DOC_MANIFEST.md` and a changed `-o` all now rebuild. | `tools/docgen/build_cache.py` | `_engine_fingerprint`, `_rule_layer_fingerprint`, `compute_key`, `_CACHE_FORMAT` |
| 12:44 | **Two concurrent cached builds silently discarded each other's entries** — load at entry, write at exit, no merge: a textbook lost update, and not exotic, since `--cached` with no `-o` puts every document in one repo-wide file. `save_cache` now re-reads and merges per source path, then `os.replace`s atomically. Proven: two concurrent builds of different documents against one cache file → **both entries survive**. | `tools/docgen/build_cache.py` | `save_cache` |
| 12:44 | `load_cache` caught `(OSError, json.JSONDecodeError)`, so a cache file with non-UTF-8 bytes raised `UnicodeDecodeError` — a `ValueError` — straight out of the module, contradicting the docstring's promise that ANY error degrades to a full rebuild. This repo had already paid for the identical mistake in `classification.load_taxonomy_prefixes`. Widened to `ValueError`; proven with a binary cache file → exit 0, zero tracebacks. | `tools/docgen/build_cache.py` | `load_cache` |
| 12:44 | `build_corpus` had no per-document isolation: a renderer that raised aborted the whole corpus **and** skipped the save, discarding every entry earlier documents had earned. Each document is now isolated, a raising build becomes a blocking finding, and the save moved into a `finally`. Closes `OG-24`, which the pass reproduced live. | `tools/docgen/build_cache.py` | `build_corpus` |
| 12:20 | **`--strict` did not disable the cache on `--cache PATH`** — the guard sat *below* the explicit-path branch, so a strict run failed on the cache-skip's own INFO finding while blaming the document, and never recomputed the document's real advisories. Both horns of the dilemma the guard exists to prevent, on the one flag it did not cover. Three prose claims asserted otherwise. Guard moved above; the announcement now covers both flags. Proven: `--strict --cache PATH` exit 1 → **exit 0**, with a real rebuild. | `tools/docgen/cli.py` | `_resolve_cache_path`, `_cmd_build` |
| 12:20 | **`--watch` re-enabled the cache `--strict` had just disabled.** `_run_watch` kept a second resolver that re-derived a default cache from the `None` the strict guard returned, so every tick after the first skipped the gate. The docstring claiming "one resolver for every entry point" was false when written. Second resolver deleted; `cache_path` is authoritative. | `tools/docgen/cli.py` | `_run_watch` |
| 12:35 | **An unwritable `--log` path turned a healthy engine UNHEALTHY** and destroyed the run-log entry that would have shown why: the write was unguarded and ran *before* `_append_run_log`, which was itself carefully hardened — the asymmetry was the defect. Every caller reading the exit code, the pre-push hook included, saw a false red. The durable record is now written first, and the optional report is announced-not-fatal. Proven: exit 1 → **exit 0**, run log still grew. | `tools/health/run.py` | `main` |
| 12:35 | `_git_state` decoded git output with `text=True` under handlers that cannot catch `UnicodeDecodeError`; since the run log is on by default, that ran on every health run. Widened to `ValueError`. | `tools/health/run.py` | `_git_state` |
| 12:48 | **`CONS-06` was still blind in two more directions** after the earlier widening: its top-level prefixes were hardcoded to four names — so it could not see `vault-graph-engine/`, one of five tracked top-level directories — and it required a dot-extension, so it could not see `tools/hooks/pre-push`, this engine's own moat, cited by name in six documents. Prefixes are now derived from `git ls-files`; the extension is optional. It immediately found 7 more unresolved citations, all genuine, now declared in `ABSENT_PATHS.md`. | `tools/health/checks.py` | `check_doc_paths_resolve` |
| 12:48 | The `ABSENT_PATHS.md` parser read every table row in the file and every path in the first cell. Now scoped to the `## Declared absent` table only, and a row naming more than one path is a **failure**, not a double exemption — the same "a row excuses everything it mentions" defect, one column narrower. | `tools/health/checks.py` | `check_doc_paths_resolve` |
| 12:30 | **`RULE-03`'s emptiness tests could never see a JSON `null`**: `compute_change_impact` coerces with `str()`, so `null` arrived as the truthy string `"None"`. A change type whose L10 blast-radius answer was null reported as resolving fine. The raw entry is now type-checked before the coerced view is trusted. | `tools/health/checks.py` | `check_impact_map` |
| 13:02 | **`CONS-08` guarded the rulebook version while the identical defect sat in the next column.** All three state documents still claimed project `0.2.1` against `PROJECT_VERSION` `0.3.0`, and a health floor of "20 passed" against 23 registered checks. Rewritten to check three fact families against machine-readable truth: rulebook version vs `VERSION.json`, project version vs `PROJECT_VERSION`, and any `N passed, M failed, K skipped` literal vs `len(CHECKS)`. The first arrow-exemption was too broad — it skipped `--full → **20 passed…**`, where the arrow means *produces* — so it is now narrowed to an arrow **between two versions**. | `tools/health/checks.py` | `check_state_docs_facts` |
| 13:10 | **`STRUCT-03` proved fidelity, not effectiveness.** It compared the installed hook byte-for-byte against a source that nothing hashes, so replacing that source with `exit 0` and reinstalling left the check green while the moat did nothing. It now also asserts the hook still invokes its gates. Proven: a stub source, perfectly installed → **FAIL, "no longer invokes its gate(s)"**. | `tools/health/checks.py` | `_hook_check`, `_HOOK_MARKERS` |
| 13:10 | **The classification moat had no caller.** `staged_content_scanner.py` — the index-level guard its own README calls the last line against a non-public document reaching a tracked public path — was invoked by nothing, and commit-time had no gate at all. New `tools/hooks/pre-commit` runs it plus a secret scan of the staged index; `install.sh` installs both hooks; **STRUCT-04** verifies it the way STRUCT-03 verifies pre-push. Proven live: a `classification: secret` document staged outside the vault → **COMMIT REFUSED**. | `tools/hooks/pre-commit`, `tools/hooks/install.sh`, `tools/health/checks.py` | new file, install loop, `check_precommit_hook_installed` |
| 13:10 | `tools/docgen/hooks/pre-commit.sample` deleted — it installed a strict subset of the new hook, and two competing pre-commit hooks is the same two-sources-of-truth defect as the pre-push sample. README repointed at `tools/hooks/install.sh`. | `tools/docgen/hooks/pre-commit.sample`, `tools/docgen/hooks/README.md` | deleted; install section |
| 13:06 | The hook filtered the *NOT A FULL PASS* banner out of health's output, so the moat could certify a push while two of health's five stages had not run. Both lines are printed now. | `tools/hooks/pre-push` | Gate 1 |
| 13:15 | `ci_cost_control`'s CLI help and public docstring still advertised the `pre-push.sample` this session deleted; the help string now derives from `DOCGEN_PREPUSH_HOOK` so it cannot drift again. | `tools/docgen/ci_cost_control.py` | `main`, `audit` |
| 13:15 | `.gitignore` covered `.docgen/` but not `<out-dir>/.docgen_cache.json`, which `--cached` writes into any `-o` inside the repo. Ignored at any depth now. | `.gitignore` | derived-state block |
| 13:18 | `OG-02` corrected: re-measurement showed **24** mypy errors under `tools/docgen` (not 22), `adjudication.py` carrying **zero** and three unnamed files carrying errors. `OG-27`…`OG-30` recorded — a rulebook that states 7 gates where the code has 9, an unpinned and ungated lint baseline, the moat's source not being hash-locked, and two docs that never learned the health system exists. | `docs/process/OPEN_GATES.md` | Open |
| 13:18 | `L-15` (scope a gate to the artifact it certifies) and `L-16` (an optimisation that skips a gate inherits the gate's contract) recorded — the two CRITICALs, generalised. | `docs/process/LESSONS.md` | L-15, L-16 |

| 13:30 | **`PROVENANCE.md` R5's stated bound was falsified by measurement.** It read "purely presentational … exit 1, nothing written"; a verifier disproved both halves on the corpus path — a raise on document N leaves documents 1..N-1 written, and it skipped `save_cache`, so the consequence was work-loss, not display. Bound corrected, and the underlying defect closed as `OG-24`. | `PROVENANCE.md` | R5 |
| 13:34 | `BUILD_PLAN.md` still said "Phases 2–7 have not started" and carried `build_cache.py` as *unexposed* with a hardcoded line count. Status line corrected, Phase 2 row marked done with its commit, line count dropped — a hardcoded count in prose is the data-in-code smell `OG-15` closed. | `docs/plan/BUILD_PLAN.md` | §1 status, module table, phase table |
| 13:36 | **`SHOULD_FIX` requires an owner and a trigger, and this register had nowhere to put either** — so ten rows silently failed a locked law (`DEEP_VERIFICATION_PASS.md` Step 6). Every `SHOULD_FIX` row now ends with an explicit `Owner · Trigger:` sentence, and rule 6 states where they live for the other dispositions. | `docs/process/OPEN_GATES.md` | Rules, Open |
| 13:38 | `L-14`'s counts restated **with their measurement conditions** after a verifier reproduced different integers using the pre-fix regex. A lesson whose subject is unchecked numbers is not entitled to an exemption from its own rule. | `docs/process/LESSONS.md` | L-14 |
| 13:40 | `README.md` and `USAGE_GUIDE.md` documented neither `tools.health` nor `--cached` — the phase's headline deliverable existed only in the changelog and the source. Both now carry the health entry point, the hook installer, the corpus/cache form with its measured numbers, and what the cache key covers. `CAPABILITIES.json` and `CONFIGURATION.md` remain stale and are recorded as `OG-30`. | `README.md`, `USAGE_GUIDE.md` | Running it, Quick start |
| 13:42 | Four more `ABSENT_PATHS.md` declarations, surfaced by the widened `CONS-06`: `tools/corpus_check/` and `docs/current/` (Phase 3/4 deliverables, cited in the future tense), `docs/confidential/` (a runtime path git cannot track and must never ship with contents), and `tools/docgen/assets/animations/`. | `docs/process/ABSENT_PATHS.md` | Declared absent |

### Two findings against this session's own process, recorded rather than quietly fixed

| time | finding | consequence |
|---|---|---|
| — | **The version was bumped before the pass ran.** `PROJECT_VERSION` went to `0.3.0` and this section was headed *Phase 2* in the phase commit, while `DEEP_VERIFICATION_PASS.md` §0 states a phase is **not** complete at the first report and puts "changelog and version updated" in Step 8, *after* the pass. The commit message said so itself ("Deep verification pass runs next"). The number is correct **now** — the pass ran, found two CRITICALs, and they are fixed above — but it was a claim before it was a fact, and `CONS-05` green-lit it. | Left at `0.3.0`, which is now true. The durable fix is a check asserting that a MINOR bump carries a recorded deep-pass result; recorded as a candidate for Phase 3's `counts`/`built-claims` guards rather than bolted on here. |
| — | **The tree was mutated while a verifier was in flight** — `LESSONS.md` L-09, violated by the session that wrote it. The re-run of the `rules-preserved` verifier overlapped the start of the fix work; it noticed only because a line-number citation stopped matching, re-scoped every measurement to a pristine `git archive 0e5d1f5` export, and reported the instability as a finding. Its verdicts are sound *because it caught this*; the next verifier might not. | The rule stands and needs no rewrite — it needs obeying. Concretely: fix work waits for **every** agent to return, and verifiers are given an explicit sha to `git archive` rather than the working tree. Added to the Phase 3 brief. |

---

## [0.2.1] — 2026-08-20 · Deep verification pass on Phase 1

Times are `+0330`.

| time | change | file | section |
|---|---|---|---|
| 00:47 | Established the standing end-of-phase deep-verification ritual, cached so it is never re-requested. Separation of duties (creator ≠ verifier) made its load-bearing law. | `docs/process/DEEP_VERIFICATION_PASS.md` | new file |
| 00:52 | Introduced build-work versioning, explicitly separated from the doc-system rulebook hash. | `CHANGELOG.md`, `PROJECT_VERSION` | new files |
| 01:05 | **Health system.** One command (`python3 -m tools.health`) replacing four disconnected entry points. 19 checks, foundation-first: STRUCTURE → RULE_LAYER → CONSISTENCY → BUILD → SUITES. Fail-closed (a raising check is a FAIL; SKIP never counts as PASS). Stdlib only. Falsified on 4 checks before being trusted. | `tools/health/` | new package (`__init__`, `model`, `checks`, `run`, `__main__`) |
| 01:05 | Open-gates register created so nothing depends on being remembered. OG-01…OG-08 recorded, OG-00 closed. | `docs/process/OPEN_GATES.md` | new file |
| 01:05 | Public accessor replacing cross-module private access to the gate→token map; returns a copy so callers cannot mutate it. | `tools/docgen/adjudication.py` | `gate_contradiction_tokens()` |

### Fixed — found by the deep verification pass

| time | change | file | section |
|---|---|---|---|
| 01:31 | **Fail-open in a gate.** `check` returned **0** when `validate_doc_system` was unimportable, making "hash-gate absent" indistinguishable from "hash-gate passed". Now fails closed with a CRIT line. A gate that cannot run has not passed. | `tools/docgen/cli.py` | `_cmd_check` `except ImportError` |
| 01:31 | **`load_taxonomy_prefixes` did not fail closed on non-UTF-8 input** — `UnicodeDecodeError` is a `ValueError`, not an `OSError`, so it escaped as an uncaught traceback. This refuted the Phase 1 claim "fails closed on every error path". | `tools/docgen/classification.py` | `load_taxonomy_prefixes` |
| 01:31 | `check` was silent on success — a pass looked identical to a no-op. Now prints what it verified. | `tools/docgen/cli.py` | `_cmd_check` |
| 01:31 | `check` did not surface the L11 advisory that the standalone gate CLI does, so the two entry points could report different governance. Now both consult. | `tools/docgen/cli.py` | `_cmd_check` |
| 01:38 | **7 of 8 known doc types were unbuildable** — the manifest registered only `WF`, so every other taxonomy prefix passed the prefix gate and was then refused by manifest-drift, **including `ADR` and `CHG`, the two types L9 requires by name**. Registered all 8. | `docs/design/doc-system/DOC_MANIFEST.md` | registry table |
| 01:38 | `CONTRADICTION.md` claimed "rows 1–7 each map to a gate that can fire". Row 6 (`L6`/`detector_internal`) fires **only under `--strict`**, because Gate 4 sets `blocking=strict` and consultation only annotates blocking findings. Replaced with a measured per-row reach table. | `docs/design/doc-system/CONTRADICTION.md` | closing note |
| 01:45 | **The documented re-baseline procedure did not work.** Both `RULEBOOK.md` and `VERSION.json` said `--write-hash` re-baselines; it does nothing on a live mismatch — only the `PENDING` sentinel authorises a write (deliberate: the gate refuses to paper over drift). Corrected to the real two-step procedure in both files. | `docs/design/doc-system/RULEBOOK.md`, `VERSION.json` | L9 §, `notes` |
| 01:45 | Rulebook re-baselined under L9 after the locked-file edits above: `version` 1.0.0 → **1.1.0**, hash `99825b10…` → `56febb6c…`. | `docs/design/doc-system/VERSION.json` | `version`, `rulebook_sha256` |
| 02:05 | **The rulebook was citing symbols that do not exist.** `L7` cited `_append_generated_guard` (exists nowhere); `L8` and `L16` both cited `visual.py`, which contains **zero** `DataSource` occurrences — the gate has always lived in `geo_map.py`. Repointed all three to real symbols. | `docs/design/doc-system/RULEBOOK.md` | L7, L8, L16 |
| 02:05 | `L23` claimed "no dependency outside the tree", contradicted by the repo's own `package.json` files and `.gitignore` (echarts, resvg, zod, MCP SDK, beautiful-mermaid, PyYAML — pinned and reinstallable, not vendored). Narrowed to the true claim: offline rendering from vendored **assets**. | `docs/design/doc-system/RULEBOOK.md` | L23 |
| 02:05 | `L17`/`L22` asserted "no reference exists anywhere in this tree" — a sentence falsified by itself. Reworded to the checkable claim (zero **code** references) and given the `Status:` line all other laws carry. | `docs/design/doc-system/RULEBOOK.md` | L17, L22 |
| 02:05 | `L6`'s status word was outside the file's own legend, and the preamble named a verification command that cannot run as written (`cli check` requires a document argument). Both corrected. | `docs/design/doc-system/RULEBOOK.md` | preamble, L6 |
| 02:12 | **Structural fix so this cannot recur:** `CONS-07` greps every backticked identifier on every `**Status:**` line and requires it to exist in the file that line cites. Falsified by reintroducing the real historical defect (`_append_generated_guard`) and by citing a ghost module — both caught. | `tools/health/checks.py` | `check_rulebook_citations_resolve` |
| 02:12 | Rulebook re-baselined again after the L7/L8/L16/L17/L22/L23 corrections. | `docs/design/doc-system/VERSION.json` | `rulebook_sha256` |
| 02:40 | **`build` produced artifacts under a tampered rulebook.** `check` gated the rulebook; `build` — the command people actually run — did not, so a locked-rule edit only mattered if someone happened to run `check` first. `build` now refuses on a blocking hash-gate, with an explicit `--allow-rulebook-drift` escape hatch. Falsified: tampered rulebook → exit 1, **no artifact written**. | `tools/docgen/cli.py` | `_cmd_build`, `_rulebook_gate_blocks()` |
| 02:47 | **`hash_gate` and `header` were absent from `PRECEDENCE`**, so their BLOCKING findings sorted *below* advisory ones (an unlisted gate ranks last) — an L1 precedence-spine violation. Added at the top: an undeclared rule edit outranks any single document's problem. | `tools/docgen/export_sanitizer.py` | `PRECEDENCE` |
| 02:52 | **`CONS-04` was self-referential** — it derived the gate universe from the very mapping it was checking, so a gate missing from that mapping could never be reported. Now derives the universe from `PRECEDENCE`. It immediately found two genuinely unmapped gates. | `tools/health/checks.py` | `check_gate_token_coverage` |
| 02:52 | Mapped the two gates `CONS-04` exposed (`header`, `wcag_contrast`). This also activated `CONTRADICTION.md` row 9, which previously could never fire. | `tools/docgen/adjudication.py`, `CONTRADICTION.md` | `_GATE_TO_CONTRADICTION_TOKENS`, reach table |
| 03:05 | **`CONS-06` widened from 8 core documents to all 47 tracked Markdown files** — it had reported "every repo path resolves" while blind to the `tools/` tree. It immediately surfaced **13 stale pointers**, incl. `docs/design/DOC_DESIGN_SYSTEM.md`, cited as the authoritative visual law by three files but never bundled. | `tools/health/checks.py` | `check_doc_paths_resolve` |
| 03:05 | Repointed the actionable stale references at files that exist. `AUTHORING_PROMPT.md` mattered most — agents are told to copy it verbatim, so its dead pointers sent every author to missing files. | `tools/docgen/AUTHORING_PROMPT.md`, `build.py`, `README.md`, `ENGINE_PLAN.md`, `project_index/README.md`, `visual-engine/README.md`, `vault-graph-engine/VAULT_GRAPH_SPEC.md` | source-of-truth lists, docstrings |
| 03:05 | Registry of paths this repo deliberately does not contain, each with a reason and its replacement. **Not a suppression list** — an undeclared missing path still fails `CONS-06`, proven by falsification. | `docs/process/ABSENT_PATHS.md` | new file |
| 03:12 | `PROVENANCE.md`'s hardening stamp marked **NEEDS RE-HARDENING**: its declared scope covers the engines and configuration layer, which changed across four commits since `9a1c011`. Stamp retained verbatim as history — superseded, not deleted. Tracked as `OG-09`. | `PROVENANCE.md` | stamp block |
| 03:12 | `BUILD_PLAN`'s own correction banner claimed the "4 commands" error was fixed in place; the prose instance in §1 still stood. Now actually corrected. | `docs/plan/BUILD_PLAN.md` | §1 |
| 03:18 | Open-gates register extended to **OG-01…OG-20**, incl. the inert git moat, the missing renderer/gate registries, the absent run log, and two orphaned modules. `OG-02`'s attribution corrected — the stale "mypy-strict clean" claim is in `ENGINE_PLAN.md` and three module docstrings, not `README.md`. | `docs/process/OPEN_GATES.md` | Open table |

| 03:40 | **CRITICAL — the L9 lock was self-certifying.** `VERSION.json` declares *both* what is locked (`rulebook_files`) *and* the digest, and is **not a member of its own locked set**, so nothing pinned it. Deleting an entry from `rulebook_files` and re-baselining silently removed a file from the lock **with every gate still green** — proven by doing it. `CONS-03` is now **bidirectional**: `RULEBOOK.md`'s locked-file table is the human-declared truth and the two must match exactly, both ways. Falsified: dropping `RULEBOOK.md` from the set now fails with "documented as locked but NOT in rulebook_files". | `tools/health/checks.py` | `check_rulebook_locked_table` |
| 03:40 | **The commit that fixed fabricated citations introduced a new one.** `9a99859` repaired L7 and repointed L8/L16 — and invented `check_choropleth_rules()`, which does not exist. `CONS-07` missed it because the citation sat on a **continuation line** and the check only read the first line of a `**Status:**` entry. Real symbol: `check_choropleth_collisions()`. `CONS-07` now scans the whole Status block; falsified on a continuation line. | `docs/design/doc-system/RULEBOOK.md`, `tools/health/checks.py` | L16, `check_rulebook_citations_resolve` |
| 03:47 | `HEALTHY` was printed over skipped checks, reading as full coverage. Every partial run now states which checks did not run and that **a skip is unknown, not green**. | `tools/health/run.py` | `_print_human` |
| 03:50 | Next-session brief written: Phase 2 scope, ordered open gates, standing constraints, and an explicit must/should/nice split. | `docs/plan/NEXT_SESSION.md` | new file |
| 03:50 | `HANDOFF.md` rewritten as an accurate start line: current versions, the five registers, the health command as the single entry point, 12 standing rules, and what the deep pass found. | `HANDOFF.md` | whole file |
| 03:50 | `L-12` (a gate piped into `tail` reports the pipe's exit code) and `L-13` (a check that derives its universe from what it checks cannot fail) recorded — both paid for during this pass. | `docs/process/LESSONS.md` | L-12, L-13 |
| 04:05 | **CRITICAL — the L9 lock was self-certifying.** `VERSION.json` declares both the locked set and the digest and is not a member of its own set, so dropping an entry and re-baselining removed a lock **with every gate green** (proven by doing it). `CONS-03` is now bidirectional against `RULEBOOK.md`'s declared table. | `tools/health/checks.py` | `check_rulebook_locked_table` |
| 04:05 | **The citation fix introduced a new false citation.** `9a99859` invented `check_choropleth_rules()`; `CONS-07` missed it because it sat on a continuation line. Real symbol `check_choropleth_collisions()`; `CONS-07` now reads whole `Status:` blocks. | `docs/design/doc-system/RULEBOOK.md`, `tools/health/checks.py` | L16, `check_rulebook_citations_resolve` |
| 04:05 | A partial run printed `HEALTHY` over skipped checks. It now names them and states that a skip is unknown, not green. | `tools/health/run.py` | `_print_human` |
| 04:20 | Launch command for the next session, with flags verified against `claude --help`. | `docs/plan/START_NEXT_SESSION.md` | new file |
| 10:40 | **The law files were not locked.** `DOC_WRITING_DOCTRINE.md` and `DEEP_VERIFICATION_PASS.md` state binding procedure, but only their *existence* was checked — either could be silently edited or gutted with every gate green. Both added to `rulebook_files`; rulebook `1.1.0` → **`1.2.0`**. Falsified: a one-line silent edit to either now blocks. | `docs/design/doc-system/VERSION.json`, `RULEBOOK.md` | `rulebook_files`, locked-file set |
| 10:40 | **The two files that hand work to the next session were fully unprotected** — `NEXT_SESSION.md` and `START_NEXT_SESSION.md` could vanish with health still green. `ABSENT_PATHS.md` likewise, and it is machine-read by `CONS-06`, so deleting it would silently widen that check. All three added to `STRUCT-01`. Falsified by deleting each. | `tools/health/checks.py` | `_CORE_DOCS` |
| 10:40 | Recorded the locking policy explicitly: **laws are locked, ledgers are not.** `CHANGELOG`/`OPEN_GATES`/`LESSONS`/`HANDOFF`/`NEXT_SESSION` change every session by design, and locking them would force a re-baseline per lesson — which trains people to bypass the gate. They are guarded by `STRUCT-01` instead. | `docs/design/doc-system/RULEBOOK.md` | Locked-file set |
| 10:42 | Removed the commit sha from the launch doc's starting-state line — it went stale on every commit, making a file whose purpose is to stay true. | `docs/plan/START_NEXT_SESSION.md` | header |
| 04:22 | **All work pushed** — `master` `874b59f..29e4beb`, `origin/master` verified equal to `HEAD`. Nine reports had verified work that existed only on this machine. | — | — |


---

## [0.2.0] — 2026-08-19 21:05 +0330 · Phase 1 — the rule layer

**Phase 1 of `BUILD_PLAN.md` §3. Commit `fcb6c39`, recorded in `4d32fd5`.**

The engine shipped ~3,000 lines of governance code consulting five data files that were never
ported, and printed its own degraded state on every build:
`L11 contradiction matrix absent … — skipping active consultation`.

### Added

| time | change | file | section |
|---|---|---|---|
| 21:05 | The locked laws **L1–L23**, each with its enforcement site and an honest `enforced`/`advisory`/`declared`/`reserved` status. L17/L22 recorded *reserved* (zero references) rather than invented. | `docs/design/doc-system/RULEBOOK.md` | whole file (290 lines) |
| 21:05 | Doc-type prefix registry, 8 generic prefixes incl. `ADR`/`CHG` (both required *by name* by L9). | `docs/design/doc-system/TAXONOMY.md` | whole file (49 lines) |
| 21:05 | L11 tie-breaker matrix, 9 rows. `Rule(s)` cells written against the live `_GATE_TO_CONTRADICTION_TOKENS` map so rows actually fire rather than merely parse. | `docs/design/doc-system/CONTRADICTION.md` | whole file (43 lines) |
| 21:05 | L10 blast-radius map: 5 change types → dependent doc-ids + public-sanitisation rule. | `docs/design/doc-system/update_impact_map.json` | whole file (59 lines) |
| 21:05 | Hash-gate manifest: `rulebook_files` + `rulebook_sha256` (the only two keys any code reads), PENDING-baselined then written back. | `docs/design/doc-system/VERSION.json` | whole file (13 lines) |
| 21:05 | `load_taxonomy_prefixes()` — the missing parser. House pipe-table dialect, markup-tolerant, fails **closed** (empty set on every error path). | `tools/docgen/classification.py` | +69 lines |
| 21:05 | Wired the id-prefix gate into `check`. | `tools/docgen/cli.py` | `_cmd_check`, `_TAXONOMY_PATH` (+13/−2) |
| 21:05 | Ignore local codemap session state. | `.gitignore` | local-tooling section |

### Fixed

| time | change | file | section |
|---|---|---|---|
| 21:05 | Degraded-mode consultation — the L11 warning is gone from **every** entry point (build, check, manifest, standalone gate). | engine-wide | — |
| 21:05 | `cli check` went from **exit 1** (`VERSION.json not found`) to **exit 0**. | `tools/docgen/cli.py` | `_cmd_check` |
| 21:08 | Start-line moved to Phase 2; Phase 1 recorded with measured exit evidence. | `HANDOFF.md` | status table, Phase 1 §, next-steps § |
| 21:08 | Plan stopped asserting five claims the implementation disproved. | `docs/plan/BUILD_PLAN.md` | header, §3 phase table |

### Verified — every gate falsified on purpose, then restored

| # | Falsification | Result |
|---|---|---|
| 1 | Undeclared locked-rule edit | exit 1, BLOCK |
| 2 | Locked file missing | exit 1, fail-closed |
| 3 | Unknown id-prefix | exit 1, BLOCK |
| 4 | Taxonomy registry absent | blocks a **valid** doc (fail-closed) |
| 5 | Unknown L10 change type | exit 0, advisory (fail-open **by contract**) |

Baseline held: visual-engine 30/30 + 22/22 simulations, mermaid 6/6, gallery 21 figures,
`project_index verify` exit 0. Edited files ruff-clean and `mypy --strict` clean, measured against
the pre-phase commit rather than assumed.

### Corrections to `BUILD_PLAN.md` §3, found by reading the code

1. `VERSION.json`'s `gate` key is **read by no code** — recorded as declarative, not implied enforced.
2. The CLI has **6** commands, not 4 — `index` and `content-index` already shipped, so part of Phase 2 was already done.
3. `_cmd_check` **already** invoked the hash-gate; it was wired and failing closed, not absent.
4. The rulebook is **L1–L23**, not the 8 laws listed.
5. `TAXONOMY.md` had **no parser and no caller** — the data file alone would have activated nothing.

### Known, carried forward (not fixed here)

- `_resolve_rulebook_files` does not guard an **absolute path** in `rulebook_files`; pathlib's `/`
  silently discards the root. Bounded: `VERSION.json` is itself locked and hashed. Pre-existing.
- `mypy --strict` reports **19 pre-existing errors** (`engine_config`, `geo_map`, `visual`,
  `generator`), making the README's "mypy-strict clean" claim stale. None in files this phase touched.

---

## [0.1.0] — 2026-08-19 03:03 +0330 · Baseline engine

Commits `9a1c011` (full-engine reverification: 4 correctness gates proven by deliberate failure,
5 shipping defects fixed, capability gallery added) and `5e5d78f` (stamped *Approved With Known
Risks*). 45 renderers, 36 forms, 8 output formats. Six known risks recorded with bounds, owners and
triggers in `PROVENANCE.md`.

This is the floor every later phase must not regress.
