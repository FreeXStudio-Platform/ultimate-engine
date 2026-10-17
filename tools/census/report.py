"""The census as a document: Markdown plus a figure sidecar for ``tools.docgen``, with a different kind of figure for each question.

``compose`` turns a measurement (and, when asked, the engine inventory) into ``(markdown, figure specs)``; every number in the prose
and in every figure is computed from the measurement, none is typed here. ``build`` writes the two files and asks the document engine
to build them. The figure for each question is chosen once and kept: a flow of documents between states is a Sankey, how fresh each
area is a stacked bar and a heat map, the shape of completeness a radar, the stamps a donut, months of activity a timeline and an
XY chart, how the system's parts relate an ER diagram, the layers of the documentation a layered diagram, and the two hierarchies
are explorers.

The document is built inside the host repository (docgen refuses paths outside its root), under the document id the profile names.
That id's prefix must be registered in the host's document manifest; if it is not, the document engine says so and nothing is written
to the host's manifest from here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from tools.census import explorer_specs
from tools.census.profile import Profile

_AREAS: Final = 12
_SHORT: Final = {"titled": "Titled", "links": "Links resolve", "updated": "Recently updated", "indexed": "Indexed", "stamps": "Stamps hold", "wired": "Authority cited",
                 "cross_out": "Crossed out kept out", "modules": "Packages named"}


def _n(value: int) -> str:
    return f"{value:,}"


def _src(census: dict[str, Any], ref: str = "git history and the tracked tree") -> list[dict[str, str]]:
    return [{"kind": "metric", "ref": ref, "retrieved": census["today"]}]


def _top_areas(census: dict[str, Any], k: int = _AREAS) -> list[dict[str, Any]]:
    areas: list[dict[str, Any]] = census["documents"]["areas"]
    return areas[:k]


def _age_bucket_matrix(census: dict[str, Any], areas: list[str]) -> tuple[list[str], list[list[int]]]:
    labels = [b["label"] for b in census["freshness"]["histogram"]]
    edges = []
    for lab in labels[:-1]:
        edges.append(int(lab.split("-")[1].split(" ")[0]))
    matrix = [[0] * len(labels) for _ in areas]
    index = {a: i for i, a in enumerate(areas)}
    for r in census["records"]:
        if r["state"] not in ("fresh", "recent", "outdated") or r["area"] not in index or r["age"] is None:
            continue
        j = 0
        while j < len(edges) and r["age"] > edges[j]:
            j += 1
        matrix[index[r["area"]]][j] += 1
    return labels, matrix


def figures(census: dict[str, Any], profile: Profile) -> list[dict[str, Any]]:
    """The sidecar specs, in the order the report places them."""
    d, fr, lc, tr, cm, hi = (census[k] for k in ("documents", "freshness", "lifecycle", "truth", "completeness", "history"))
    out: list[dict[str, Any]] = []

    # 1 — a flow: where every document ever written ended up (Sankey, native)
    ever = d["total"] + lc["removed"]
    nodes = [{"id": "ever", "label": "Ever written", "col": 0}, {"id": "tree", "label": "In the tree", "col": 1}]
    flows = [{"src": "ever", "dst": "tree", "value": d["total"]}]
    steps: list[tuple[str, str, str, int, int]] = [  # (id, label, parent, col, value): a zero is left out, never drawn as one
        ("gone", "Deleted", "ever", 1, lc["removed"]),
        ("live", "Live", "tree", 2, d["live"]),
        ("arch", "Archived", "tree", 2, d["archived"]),
        ("fresh", f"Touched in the last {profile.fresh_days} days", "live", 3, fr["fresh"]),
        ("recent", f"Touched {profile.fresh_days + 1}–{profile.outdated_days} days ago", "live", 3, fr["recent"]),
        ("out", "Outdated", "live", 3, fr["outdated"]),
        ("mark", "Marked superseded or retired", "live", 3, lc["marked_but_live"]),
    ]
    for key, label, parent, col, value in steps:
        if value > 0:
            nodes.append({"id": key, "label": label, "col": col})
            flows.append({"src": parent, "dst": key, "value": value, **({"emphasis": True} if key == "out" else {})})
    out.append({"id": "census-flow", "kind": "sankey", "title": "Where the documents are", "width": 900, "height": 480, "unit": " documents", "nodes": nodes, "flows": flows,
                "reader_question": "Of everything ever written, how much is still alive, how much is archived, how much is gone?",
                "insight": f"Of {_n(ever)} documents ever written, {_n(d['live'])} are live and {_n(fr['updated'])} of the {_n(fr['population'])} unmarked live ones were touched within {profile.outdated_days} days.",
                "caption": f"Flow of every document ever written in {census['project']} (deleted ones are counted from git history) into the states this report measures.",
                "data_sources": _src(census)})

    # 2 — areas by state (stacked bar, chart engine)
    ar = _top_areas(census)
    rows = [[a["area"], a["fresh"], a["recent"], a["outdated"], a["marked"], a["archived"]] for a in ar]
    out.append({"id": "census-areas", "kind": "echarts", "caption": f"The {len(ar)} largest areas of the documentation, stacked by state. Source: git history and the tracked tree.",
                "data_sources": _src(census),
                "job": {"visual_id": "CENSUS-AREAS", "reader_question": "In which areas does the documentation live, and in what state is each?", "classification": profile.report.get("classification", "internal"),
                        "selected_visual": "bar_stacked", "title": "Documents per area, by state", "stack": True, "theme": "document-theme", "width": 620, "height": 560,
                        "text_summary": f"{_n(ar[0]['total'])} of {_n(d['total'])} documents sit in {ar[0]['area']}; {sum(a['outdated'] for a in ar):,} outdated documents sit in these {len(ar)} areas.",
                        "data": {"dimensions": ["Area", f"Touched 0–{profile.fresh_days} d ago", f"Touched {profile.fresh_days + 1}–{profile.outdated_days} d ago", f"Not touched in {profile.outdated_days}+ d", "Marked", "Archived"], "source": rows},
                        "units": ["documents"]}})

    # 3 — how fresh each area is by age band (heat map, native)
    labels, full = _age_bucket_matrix(census, [a["area"] for a in ar])
    kept = [(a["area"], row) for a, row in zip(ar, full, strict=True) if sum(row)][:10]
    names = [n for n, _ in kept]
    matrix = [row for _, row in kept]
    if names:
        peak = max((v for row in matrix for v in row), default=1)
        out.append({"id": "census-age-heat", "kind": "heatmap", "title": "Age of the live documents, by area", "width": 760, "height": 440, "min_value": 0, "max_value": max(1, peak),
                    "row_labels": names, "col_labels": labels, "matrix": matrix,
                    "reader_question": "How old are the live documents of each area?", "insight": f"Median age of a live document: {fr['median_age_days']} days.",
                    "caption": f"Live, unmarked documents by area and days since last touched (reference date {census['today']}).", "data_sources": _src(census)})

    # 4 — what is crossed out (native bar)
    cross_items = [{"label": "Archived by path", "value": lc["archived"]}, {"label": "Marked in the header", "value": lc["marked"]},
                   {"label": "Marked but still live", "value": lc["marked_but_live"]}, {"label": "Deleted from the tree", "value": lc["removed"]}]
    out.append({"id": "census-crossed", "kind": "bar", "title": "Crossed out of the project", "width": 900, "height": 360, "unit": " documents", "items": cross_items,
                "reader_question": "How many documents have been taken out of the live project, and how?", "insight": f"{_n(lc['crossed_out_total'])} documents are crossed out: {_n(lc['crossed_out_in_tree'])} still in the tree and {_n(lc['removed'])} deleted.",
                "caption": "Four ways a document leaves the live set. The first two overlap: a marked document may also sit in an archive path.", "data_sources": _src(census)})

    # 5 — stamps (donut, native)
    states = tr["stamp_states"]
    slices = [{"label": k.title(), "value": v} for k, v in sorted(states.items(), key=lambda kv: -kv[1]) if v]
    if slices:
        out.append({"id": "census-stamps", "kind": "pie", "title": "Source-of-truth stamps and what became of them", "width": 520, "height": 520, "donut": True, "slices": slices, "legend": [],
                    "reader_question": "Of the documents stamped as a source of truth, how many stamps still hold?",
                    "insight": f"{_n(states.get('VALID', 0))} of {_n(tr['stamped'])} stamps still hold; {_n(states.get('INVALIDATED', 0))} say so themselves and {_n(states.get('DRIFTED', 0))} were edited after being stamped.",
                    "caption": "Each stamp is VALID (its commit exists and the document's text, stamp lines aside, is unchanged since), DRIFTED (the text changed after the stamp), INVALIDATED (its own text says it no longer holds), UNVERIFIABLE (the document did not exist at that path then) or UNRESOLVED (the commit cannot be found).",
                    "data_sources": _src(census)})

    # 6 — completeness shape (radar, native); counts, never a composite
    dims = [x for x in cm["dimensions"] if x["of"] > 0]
    if len(dims) >= 3:
        out.append({"id": "census-completeness", "kind": "radar", "title": "Completeness, one axis per dimension", "width": 560, "height": 560, "max_value": 100,
                    "axes": [f"{_SHORT.get(x['id'], x['label'])} ({_n(x['covered'])} of {_n(x['of'])})" for x in dims],
                    "series": [{"label": "Covered", "values": [round(100 * x["covered"] / x["of"], 1) if x["of"] else 0 for x in dims]}],
                    "legend": [{"kind": "swatch", "key": "Covered", "label": "Share covered, per dimension"}],
                    "reader_question": "Where are the gaps in the documentation system, dimension by dimension?",
                    "insight": "Each axis is its own dimension with its own rule; there is deliberately no single completeness number.",
                    "caption": "Share covered on each dimension (the axis label gives the counts). No composite is computed: a hole on one axis must not be averaged away.",
                    "data_sources": _src(census)})

    # 7 — months of activity (timeline, native) and added vs removed (XY chart, Mermaid)
    months = hi["months"][-12:]
    if len(months) >= 2:
        touched = hi["touched"][-12:]
        peak_t = max(touched) or 1
        events = [{"label": f"{t:,} document" + ("" if t == 1 else "s"), "date_label": m, "t": round(i / (len(months) - 1), 3)} for i, (m, t) in enumerate(zip(months, touched, strict=True))]
        out.append({"id": "census-activity", "kind": "timeline", "title": "Documents last touched, by month", "width": 900, "height": 280, "events": events,
                    "reader_question": "In which months was the documentation last worked on?", "insight": f"The busiest month last touched {_n(peak_t)} documents.",
                    "caption": "For each month, how many documents have that month as their last touch (documents touched again later count in the later month).", "data_sources": _src(census)})
        added = hi["added"][-12:]
        removed = hi["removed"][-12:]
        top = max(added + removed + [1])
        code = "xychart-beta\n    title \"Documents added and removed per month\"\n    x-axis [" + ", ".join(m for m in months) + "]\n    y-axis \"Documents\" 0 --> " + str(top) + "\n    bar [" + ", ".join(str(v) for v in added) + "]\n    line [" + ", ".join(str(v) for v in removed) + "]"
        out.append({"id": "census-growth", "kind": "mermaid", "code": code, "caption": "Documents first added (bars, \"Bar 1\") and documents deleted (line, \"Line 1\"), per month. A document moved to a new path counts once: renames are followed. The Mermaid renderer names its series itself and draws the line as a smoothed curve that can dip below zero between months; read the dots, not the dips.",
                    "reader_question": "Is the documentation growing, and is anything being removed?", "insight": f"{_n(sum(hi['added']))} documents were added over the history and {_n(sum(hi['removed']))} deleted.",
                    "data_sources": _src(census)})

    # 8 — how the parts relate (ER diagram, Mermaid)
    er = ("erDiagram\n    DOCUMENT ||--o{ LINK : contains\n    AREA ||--o{ DOCUMENT : holds\n    DOCUMENT ||--o| STAMP : \"may carry\"\n"
          "    DOCUMENT ||--o| LIFECYCLE_MARK : \"may declare\"\n    DOCUMENT {\n        int total \"" + str(d["total"]) + "\"\n        int live \"" + str(d["live"]) + "\"\n"
          "        int archived \"" + str(d["archived"]) + "\"\n    }\n    STAMP {\n        int stamped \"" + str(tr["stamped"]) + "\"\n        int valid \"" + str(states.get("VALID", 0)) + "\"\n    }\n"
          "    LINK {\n        int relative \"" + str(census["links"]["relative"]) + "\"\n        int dangling \"" + str(census["links"]["dangling"]) + "\"\n    }\n"
          "    LIFECYCLE_MARK {\n        int marked \"" + str(lc["marked"]) + "\"\n    }")
    out.append({"id": "census-model", "kind": "mermaid", "code": er, "caption": "The things this census measures and how they relate, with each thing's count.",
                "reader_question": "What does the census treat as a document, a stamp, a link and a mark, and how do they relate?",
                "insight": "An area holds many documents; a document contains links and may carry one stamp and one lifecycle mark.", "data_sources": _src(census)})

    # 9 — layers of the documentation (layered workflow, native) when the profile names layers
    if profile.layers:
        node_list: list[dict[str, Any]] = []
        layer_labels: list[str] = []
        ids: dict[str, str] = {}
        by_area = {a["area"]: a for a in d["areas"]}
        for li, layer in enumerate(profile.layers):
            members = [a for a in by_area if any(a == x or a.startswith(x + "/") for x in layer.areas)]
            members = sorted(members, key=lambda a: -by_area[a]["total"])[:4]
            layer_labels.append(f"{layer.label} · {_n(sum(by_area[a]['total'] for a in members))} documents")
            for ci, a in enumerate(members):
                nid = f"l{li}c{ci}"
                ids[a] = nid
                node_list.append({"id": nid, "label": f"{a} · {_n(by_area[a]['total'])}", "layer": li, "col": ci})
        conns: list[dict[str, str]] = []
        for a, b, n in census["folder_refs"]:
            ka = next((k for k in ids if a == k or a.startswith(k + "/")), None)
            kb = next((k for k in ids if b == k or b.startswith(k + "/")), None)
            if ka and kb and ka != kb and (ka, kb) not in {(c["a"], c["b"]) for c in conns} and len(conns) < 14:
                conns.append({"a": ka, "b": kb, "src": ids[ka], "dst": ids[kb]})
        if node_list:
            out.append({"id": "census-layers", "kind": "layered_workflow", "title": "The layers of the documentation", "width": 900, "height": 520, "layer_labels": layer_labels,
                        "nodes": node_list, "connectors": [{"src": c["src"], "dst": c["dst"]} for c in conns],
                        "reader_question": "How is the documentation layered, and which layers cite which?", "insight": "Each row is a layer named by the project's profile; lines are citations between areas.",
                        "caption": "The profile's layers with their largest areas; a line means documents in one area cite documents in the other.", "data_sources": _src(census)})

    # 10, 11 — the two hierarchies (explorers)
    out.append(explorer_specs.docs_explorer(census, profile))
    code_ex = explorer_specs.modules_explorer(census)
    if code_ex:
        out.append(code_ex)
    return out


def _table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def compose(census: dict[str, Any], profile: Profile, inventory: dict[str, Any] | None = None) -> tuple[str, list[dict[str, Any]]]:
    """``(markdown, figure specs)``. The markdown names each figure with ``<!-- figure:ID -->`` in the order below."""
    d, fr, lc, tr, cm, hi = (census[k] for k in ("documents", "freshness", "lifecycle", "truth", "completeness", "history"))
    figs = figures(census, profile)
    have = {f["id"] for f in figs}
    rep = {"id": "CEN-901", "classification": "internal", "surface": "none", "audience": "technical", "owner": "doc-system", "status": "draft", "export_allowed": False}
    rep.update(profile.report)
    front = "---\n" + "\n".join(f"{k}: {str(v).lower() if isinstance(v, bool) else v}" for k, v in {**rep, "title": f"{census['project']} — Documentation Census", "last_reviewed": census["today"]}.items()) + "\n---\n"
    states = tr["stamp_states"]
    win = tr["window"]
    p: list[str] = [front, f"# {census['project']} — Documentation Census\n"]
    p.append(f"*Measured from the git tree at commit `{census['head']['sha'][:8]}` (committed {census['head']['date']}); ages are counted from {census['today']}. "
             f"Every number below is computed by the engine's census tool, with its rule printed beside it.*\n")
    p.append("## 1. The answers\n")
    p.append(_table(["Question", "Answer", "Rule"], [
        ["How many documents?", f"**{_n(d['total'])}** ({_n(d['live'])} live, {_n(d['archived'])} archived)", census["rules"]["document"]],
        ["How many are updated?", f"**{_n(fr['updated'])}** of {_n(fr['population'])} live documents ({_n(fr['fresh'])} within {profile.fresh_days} days)", census["rules"]["updated"]],
        ["How many are outdated?", f"**{_n(fr['outdated'])}** of {_n(fr['population'])} live documents; median age {fr['median_age_days']} days", "live, unmarked, not touched within the window"],
        ["How many are crossed out?", f"**{_n(lc['crossed_out_total'])}**: {_n(lc['archived'])} archived by path, {_n(lc['marked'])} marked in the header ({_n(lc['marked_but_live'])} of those still among the live), {_n(lc['removed'])} deleted", census["rules"]["crossed_out"]],
        ["How many are stamped as a source of truth?", f"**{_n(tr['stamped'])}** carry a stamp; **{_n(tr['authoritative'])}** are treated as authoritative in all", census["rules"]["authoritative"]],
        ["Do the stamps still hold?", f"**{_n(states.get('VALID', 0))}** of {_n(tr['stamped'])}: {_n(states.get('INVALIDATED', 0))} declare themselves invalidated, {_n(states.get('DRIFTED', 0))} were edited after being stamped", census["rules"]["stamp"]],
        ["Are we working from them?", f"{_n(tr['wired'])} of {_n(tr['authoritative'])} authoritative documents are cited by another live document; {_n(win['authoritative_commits'])} of the {_n(win['doc_commits'])} commits that touched a document since {win['since']} touched an authoritative one", "see section 5"],
        ["How complete is the system?", "per dimension, never one number: " + "; ".join(f"{x['id']} {_n(x['covered'])} of {_n(x['of'])}" for x in cm["dimensions"]), census["rules"]["completeness"]],
    ]))
    p.append("## 2. How the documents divide\n")
    p.append(f"Of {_n(d['total'] + lc['removed'])} documents ever written, {_n(lc['removed'])} have been deleted, {_n(d['archived'])} sit in archive paths and {_n(d['live'])} are live. "
             f"The largest area is `{d['areas'][0]['area']}` with {_n(d['areas'][0]['total'])} documents.\n")
    p.append("<!-- figure:census-flow -->\n\n<!-- figure:census-areas -->\n")
    p.append("## 3. How fresh they are\n")
    p.append(f"Counting only live documents that are not marked superseded or retired, {_n(fr['updated'])} of {_n(fr['population'])} were touched within {profile.outdated_days} days and {_n(fr['outdated'])} were not. "
             f"The oldest untouched live document is `{fr['oldest'][0]['p']}` at {fr['oldest'][0]['age']} days." if fr["oldest"] else "No live documents.")
    p.append("\n")
    if "census-age-heat" in have:  # a repository whose documents are all archived or marked has no live document to age
        p.append("<!-- figure:census-age-heat -->\n")
    if "census-activity" in have:
        p.append("<!-- figure:census-activity -->\n")
    p.append("## 4. What has been crossed out\n")
    p.append(f"{_n(lc['crossed_out_total'])} documents are crossed out of the project. {_n(lc['marked_but_live'])} documents are marked superseded, retired or deprecated in their own header yet still sit outside an archive path; "
             "a reader opening the live folders can still meet them.\n")
    p.append("<!-- figure:census-crossed -->\n")
    if "census-growth" in have:
        p.append("<!-- figure:census-growth -->\n")
    p.append("## 5. Source of truth: stamps, and whether the work follows them\n")
    p.append(f"{_n(tr['stamped'])} documents carry a hardening stamp, {_n(tr['labelled'])} call themselves a source of truth in their header and {_n(tr['declared'])} are named by an authority document; "
             f"together {_n(tr['authoritative'])} documents are treated as authoritative. A stamp holds only while its document is unchanged: "
             f"{_n(states.get('VALID', 0))} hold, {_n(states.get('DRIFTED', 0))} have drifted and {_n(states.get('INVALIDATED', 0))} say they no longer hold. "
             f"The documents are nonetheless in use: {_n(tr['cited_by_updated'])} of the {_n(tr['authoritative'])} are cited by a live document that was itself touched within the window, and "
             f"{_n(win['authoritative_commits'])} of {_n(win['doc_commits'])} documentation commits since {win['since']} touched one.\n")
    if "census-stamps" in have:
        p.append("<!-- figure:census-stamps -->\n")
    p.append("## 6. How complete the documentation system is\n")
    p.append("The census reports each dimension as covered of total and does not combine them. The gaps:\n\n" + _table(["Dimension", "Covered", "Of", "Rule"], [[x["label"], _n(x["covered"]), _n(x["of"]), x["rule"]] for x in cm["dimensions"]]))
    if "census-completeness" in have:
        p.append("<!-- figure:census-completeness -->\n")
    p.append("## 7. How the parts of the system relate\n")
    p.append("<!-- figure:census-model -->\n")
    if "census-layers" in have:
        p.append("<!-- figure:census-layers -->\n")
    p.append("## 8. Explore it\n")
    p.append("Click a folder or a package to go inside it; the panel names what it connects to and opens its dossier.\n")
    p.append("<!-- figure:census-docs-explorer -->\n")
    if "census-code-explorer" in have:
        p.append("<!-- figure:census-code-explorer -->\n")
    if inventory:
        p.append("## 9. What the engine can draw\n")
        ie = inventory
        p.append(f"This report was drawn by the engine's own figure kinds. The engine offers **{ie['implementations']}** named figure models: {len(ie['document_engine']['native'])} native document figures, "
                 f"the module explorer, {ie['chart_engine']['count']} chart-engine visuals and {ie['mermaid_engine']['count']} Mermaid text-diagram types. "
                 f"Counting a name once when two engines share it, and a variant (stacked bar, donut, step line, matrix) with its parent, that is **{ie['distinct_after_merging_names']}** distinct kinds. "
                 f"{ie['how_counted']}.\n")
        p.append(_table(["Engine", "Models", "Names"], [
            ["Document engine (native)", str(len(ie["document_engine"]["native"]) + len(ie["document_engine"]["blocks"])), ", ".join(ie["document_engine"]["native"] + ie["document_engine"]["blocks"])],
            ["Chart engine", str(ie["chart_engine"]["count"]), ", ".join(ie["chart_engine"]["visuals"])],
            ["Mermaid engine", str(ie["mermaid_engine"]["count"]), ", ".join(ie["mermaid_engine"]["types"])]]))
    p.append("## 10. What this census could not verify\n")
    p.append("\n".join([
        f"- **Documents are Markdown** (`{', '.join(profile.doc_exts)}`) under `{', '.join(profile.doc_globs)}`; other files are not counted as documents.",
        "- **\"Outdated\" is age, not falsehood.** A document untouched for a long time may be perfectly true; a document touched yesterday may be wrong. The census cannot read meaning.",
        "- **A stamp's state is git's, plus the stamp's own words.** It does not re-read the document to see whether its claims still hold.",
        "- **\"Cited\" means a link or a path appears in another live document**; a document used without being named is not counted.",
        "- **Marks are read from the first lines of a document only**; a retired document that says so deep in its body is not marked.",
        f"- **History starts where git's does** ({_n(hi['commits'])} commits); a document moved with heavy edits can read as deleted and added.",
        "- **No composite completeness number is given, by design.**",
    ]) + "\n")
    return "\n".join(p), figs


def build(census: dict[str, Any], profile: Profile, out_dir: Path, inventory: dict[str, Any] | None = None, formats: tuple[str, ...] = ("html", "blueprint"),
          *, local_preview: bool = False) -> dict[str, Path]:
    """Write ``<id>.md`` and its sidecar into ``out_dir`` (inside the host repository) and build them with the document engine.

    ``local_preview`` is the document engine's own switch for a document that is not export-eligible (confidential, internal): it is built for
    reading here and never exported. A report whose profile classifies it above ``public`` needs it.
    """
    from tools.docgen import generator

    md, figs = compose(census, profile, inventory)
    rep_id = "CEN-901"
    for line in md.split("\n", 12)[:12]:
        if line.startswith("id:"):
            rep_id = line.split(":", 1)[1].strip()
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{rep_id}.md"
    md_path.write_text(md, encoding="utf-8")
    (out_dir / f"{rep_id}_spec.json").write_text(json.dumps(figs, ensure_ascii=False, indent=1), encoding="utf-8")
    result = generator.build(md_path, formats=formats, out_dir=out_dir, local_preview=local_preview)
    if not result.ok:
        raise RuntimeError("the document engine refused the census report: " + "; ".join(f.message for f in result.gate.findings)[:600])
    return {k: Path(v) for k, v in result.outputs.items()}
