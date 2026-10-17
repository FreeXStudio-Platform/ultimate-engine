<!-- title: PROJECT CENSUS -->
# Project census — measuring a project's documentation system and drawing it

**Status:** DESIGN + IMPLEMENTED (`tools/census/`, engine `1.0.13`). Raised by the operator after reading a report that said *"1,290 documents"* without
saying how many were alive, how many had been crossed out, how many were stamped as a source of truth, whether the stamps still held, or whether
anyone worked from them. The census answers those from the project's own git tree, with the rule beside every number, and draws the answer with a
different kind of figure for each question.

## 1. What it answers

| Question | The number | The rule that makes it |
|---|---|---|
| How many documents? | `documents.total` (live, archived) | tracked, matches `doc_globs`, has one of `doc_exts` |
| How many are updated? How many outdated? | `freshness.updated` / `outdated` of `population` | live, **unmarked**, touched within `outdated_days` of the reference date (archives are expected to be old and are not counted) |
| How many are crossed out? | `lifecycle.crossed_out_total` | archived by path, **marked in the header** (superseded / retired / deprecated / archived), or **deleted** (git history shows it removed; a rename is not a removal) |
| How many are stamped as a source of truth? | `truth.stamped`, `labelled`, `declared`, `authoritative` | a stamp line (`stamp_patterns`), a header that says "source of truth", or a document named by an `authority_docs` document |
| Do the stamps still hold? | `truth.stamp_states` | **VALID** = the commit exists and the body is unchanged since it, *with the stamp lines removed from both sides* (a stamp cannot be present at the commit it names); **DRIFTED** = the body changed; **INVALIDATED** = the stamp's own status text says it no longer holds; **UNVERIFIABLE** = the document did not exist at that path then; **UNRESOLVED** = the commit is not in this clone |
| Are we working from them? | `truth.wired`, `cited_by_updated`, `window` | *wired* = another live document links to or names it (the index document is excluded: an index cites everything and proves nothing); *cited by an updated document* = one of those was itself touched within the window; `window` counts the commits since `today − outdated_days` that touched any document and the ones that touched an authoritative one |
| How complete is the system? | `completeness.dimensions[]` | one **covered of total** per dimension, each with its rule. **There is deliberately no composite number**: one figure lets a hole in one dimension hide behind the rest |

Ages count from the commit date of `HEAD` (or the profile's `today`), never from the wall clock, so the same tree measures the same on every machine and on
every day. The measurement is one dictionary (`census/1`) and is deterministic for a commit, a profile and a date.

## 2. The profile

`examples/census.profile.example.json` shows every key; every key is optional; **unknown keys are refused** and so is a regular expression that does not
compile, so a misspelt key never silently measures something else. A missing profile file is an error, never the defaults.

## 3. The figures

Each question gets the kind of figure that suits it, and the report keeps that choice:

| Question | Figure | Engine |
|---|---|---|
| Where did every document ever written end up? | Sankey (flow) | document engine, native |
| In which areas, in what state? | stacked bar | chart engine |
| How old is each area's live set? | heat map | document engine, native |
| What has been crossed out, and how? | bar | document engine, native |
| What became of the stamps? | donut | document engine, native |
| Where are the gaps, dimension by dimension? | radar | document engine, native |
| When was the documentation worked on? | timeline | document engine, native |
| Is it growing, is anything removed? | XY chart (bars and a line) | Mermaid |
| What does the census treat as a document, stamp, link, mark? | ER diagram | Mermaid |
| How is the documentation layered? | layered diagram (only when the profile names `layers`) | document engine, native |
| What is inside each folder, and which folders cite which? | **explorer** (documents) | document engine |
| What is inside each package, what does it import? | **explorer** (code; only with `code_roots`) | document engine |

The two explorers are the same figure kind the module section of a report uses: zoom into a folder or a package, read its panel, open its dossier. Folder-to-folder
citations and package-to-package imports are drawn as hover arrows (worded "cites" and "imports" through the spec's `arrows`) and listed in the panel. When one folder holds 85% or more of all lines, the first map opens it up (its children become the top level, its loose files stay as one part) so the map is not a single rectangle.

## 4. Running it

```bash
python3 -m tools.census measure PROFILE.json --root . --out census.json          # the measurement as JSON
python3 -m tools.census report  PROFILE.json --root . --out docs/census/         # measure, then build the document with docgen
python3 -m tools.census inventory --engine-root .                                # how many figure models the engine can draw
```

`report` writes `<id>.md`, its sidecar and the built outputs under `--out`, which must be **inside the host repository** (docgen refuses paths outside its root).
The report's document id comes from the profile's `report.id`; **its prefix must be registered in the host's document manifest** — if it is not, the document
engine says so and the census writes nothing to the manifest.

## 5. What it cannot know (printed in every report)

* **"Outdated" is age, not falsehood.** An old document can be true and a new one wrong.
* **Cited means named**: a link or a path in another live document. A document used without being named is not counted.
* **Marks are read from the first lines**; a retired document that says so deep in its body is not marked.
* **A stamp's state is git's plus the stamp's own words**; the census does not re-read the document to check its claims.
* **History is git's**: a document moved with heavy edits can read as deleted and added.
* **Documents are what `doc_globs` and `doc_exts` select**; other files are not counted.

## 6. What building it found

Drawing a real census was the first time several figure kinds were used in a report. Each defect below passed every test and was found by looking at the picture, and
each is fixed at the source with a test that fails against the previous code (`OG-292`):

* the **stacked bar** drew three category names under twelve bars (ECharts hides labels that overlap) — every name is now shown, tilted when it must be;
* the native **radar** cut long axis names off at the canvas edge — they now wrap and the ring shrinks to make room, and a radar whose names already fit is
  byte-identical to before;
* the native **layered diagram** drew every plane as wide as the whole figure's node count, ran a long node label through its box and let connectors strike through
  labels — planes span their own columns, labels wrap inside the node, nodes are opaque;
* the **Mermaid ER diagram** silently dropped a self-relationship and any relationship whose left cardinality is `}o` or `}|` (six declared, three drawn) — the bridge
  now refuses a diagram that drew fewer relationships than it declares, and names the way out.

## 7. Where it sits

`tools/census` reads git and the source tree and writes only where it is told. It does not change the document engine, the chart engine or the Mermaid engine; it
composes them. It is independent of the project index (which records what was built) and of the blueprint (which maps the engine's own modules): the census
measures a *project's* documents and code, whichever project that is.
