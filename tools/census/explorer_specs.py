"""The census as explorer figures: the documentation tree, and the code hierarchy.

Both return a plain ``explorer`` spec (``tools.docgen.explorer``): a hierarchy sized by lines, coloured by a state a reader can act on,
with a dossier for every part that has something to say. They add no new drawing code: the zoom, the panel and the reader are the
explorer's. Folder-level connections are counted from the measurement (documents citing documents in another folder; packages
importing packages) and are exact at the level they are drawn.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Final

from tools.census import measure as _m
from tools.census.profile import Profile

_MAX_CHILDREN: Final = 58
_FLATTEN_SHARE: Final = 0.85  # a folder holding this share of all lines is opened up on the first map
_MAX_DOSSIERS: Final = 380
_ID_BAD: Final = re.compile(r"[^A-Za-z0-9_.:-]")


def _short(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _nid(prefix: str, key: str, used: set[str]) -> str:
    base = prefix + _ID_BAD.sub(":", key.replace("/", ":"))[: 60 - len(prefix)]
    out, k = base, 2
    while out in used:
        out = f"{base[:56]}~{k}".replace("~", "_")
        k += 1
    used.add(out)
    return out


def _state_of(c: Counter[str]) -> str:
    live = c.get("fresh", 0) + c.get("recent", 0) + c.get("outdated", 0)
    if live == 0:
        return "ARCHIVE"
    share = c.get("outdated", 0) / live
    return "OUTDATED" if share > 0.6 else "MIXED" if share > 0.25 else "CURRENT"


def docs_explorer(census: dict[str, Any], profile: Profile) -> dict[str, Any]:
    """The documentation tree: folder -> subfolder, sized by lines, coloured by how many documents are still being updated."""
    records: list[dict[str, Any]] = census["records"]
    depth = profile.explorer_depth
    by_folder: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_folder[_m.area_of(r["p"], depth)].append(r)
    used: set[str] = {"system"}
    ids: dict[str, str] = {}
    documents: list[dict[str, Any]] = []

    def stats(rs: list[dict[str, Any]]) -> Counter[str]:
        return Counter(r["state"] for r in rs)

    def facts(rs: list[dict[str, Any]]) -> list[list[str]]:
        c = stats(rs)
        return [["Documents", f"{len(rs):,}"], ["Lines", f"{sum(r['lines'] for r in rs):,}"],
                ["Updated within the window", f"{c.get('fresh', 0) + c.get('recent', 0):,}"], ["Outdated", f"{c.get('outdated', 0):,}"],
                ["Archived", f"{c.get('archived', 0):,}"], ["Marked superseded or retired", f"{c.get('marked', 0):,}"],
                ["Source-of-truth documents", f"{sum(1 for r in rs if r['auth']):,}"]]

    def dossier(key: str, title: str, rs: list[dict[str, Any]]) -> str | None:
        if len(documents) >= _MAX_DOSSIERS or not rs:
            return None
        live = sorted((r for r in rs if r["state"] in ("fresh", "recent", "outdated")), key=lambda r: (-(r["age"] or 0), r["p"]))
        newest = sorted((r for r in rs if r["state"] in ("fresh", "recent")), key=lambda r: (r["age"] or 0, r["p"]))
        blocks: list[dict[str, Any]] = [{"t": "kv", "rows": facts(rs)}]
        if live:
            blocks += [{"t": "h", "text": "The longest untouched live documents"},
                       {"t": "table", "head": ["Document", "Days since touched", "Commits", "Lines"],
                        "rows": [[r["p"], str(r["age"]), str(r["commits"]), str(r["lines"])] for r in live[:25]]}]
        if newest:
            blocks += [{"t": "h", "text": "Most recently touched"}, {"t": "ul", "items": [f"{r['p']} ({r['age']} d)" for r in newest[:10]]}]
        auth = [r for r in rs if r["auth"]]
        if auth:
            blocks += [{"t": "h", "text": "Documents this project treats as a source of truth"},
                       {"t": "ul", "items": [f"{r['p']}" + (f" — stamp {r['stamp'].lower()}" if r["stamp"] else "") for r in auth[:25]]}]
        marked = [r for r in rs if r["state"] == "marked"]
        if marked:
            blocks += [{"t": "h", "text": "Marked superseded, retired or deprecated"}, {"t": "ul", "items": [f"{r['p']} ({', '.join(r['marks'])})" for r in marked[:20]]}]
        did = f"d-{len(documents)}"
        documents.append({"id": did, "title": f"{title} — documents", "sources": ["git history and the tracked tree"], "blocks": blocks})
        return did

    # ---- tree of folders
    root_children: dict[str, dict[str, Any]] = {}

    def node_for(path: str) -> dict[str, Any]:
        parts = path.split("/") if path != "(root)" else ["(root)"]
        level = root_children
        node: dict[str, Any] = {}
        for i, part in enumerate(parts):
            key = "/".join(parts[: i + 1])
            if part not in level:
                level[part] = {"key": key, "name": part, "children": {}, "own": []}
            node = level[part]
            level = node["children"]
        return node

    for folder, rs in by_folder.items():
        node_for(folder)["own"] = rs

    def collect(n: dict[str, Any]) -> list[dict[str, Any]]:
        out = list(n["own"])
        for ch in n["children"].values():
            out += collect(ch)
        return out

    def build(n: dict[str, Any]) -> dict[str, Any]:
        rs = collect(n)
        c = stats(rs)
        nid = _nid("f:", n["key"], used)
        ids[n["key"]] = nid
        spec: dict[str, Any] = {"id": nid, "name": _short(n["name"], 80), "kicker": f"{len(rs):,} documents", "status": _state_of(c),
                                "summary": _short(f"{n['key']}: {c.get('fresh', 0) + c.get('recent', 0)} updated within the window, {c.get('outdated', 0)} outdated, "
                                                  f"{c.get('archived', 0)} archived, {c.get('marked', 0)} marked.", 300),
                                "facts": facts(rs)[:8]}
        d = dossier(n["key"], n["key"], rs)
        if d:
            spec["docs"] = [d]
        kids = sorted(n["children"].values(), key=lambda ch: (-sum(r["lines"] for r in collect(ch)), ch["name"]))
        if len(kids) > _MAX_CHILDREN:
            keep, rest = kids[: _MAX_CHILDREN - 1], kids[_MAX_CHILDREN - 1 :]
            other = [r for ch in rest for r in collect(ch)]
            spec["children"] = [build(ch) for ch in keep]
            oid = _nid("f:", n["key"] + ":others", used)
            spec["children"].append({"id": oid, "name": f"{len(rest)} smaller folders", "kicker": "Folders grouped to keep the map readable", "status": _state_of(stats(other)),
                                     "value": max(1, sum(r["lines"] for r in other)), "facts": facts(other)[:8]})
        else:
            spec["children"] = [build(ch) for ch in kids]
        own_lines = sum(r["lines"] for r in n["own"])
        if spec["children"] and n["own"]:
            hid = _nid("f:", n["key"] + ":here", used)
            spec["children"].append({"id": hid, "name": "(documents here)", "kicker": "Directly in this folder", "status": _state_of(stats(n["own"])),
                                     "value": max(1, own_lines), "facts": facts(n["own"])[:8]})
        if not spec["children"]:
            spec["value"] = max(1, own_lines)
            del spec["children"]
        return spec

    def by_size(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(nodes, key=lambda ch: (-sum(r["lines"] for r in collect(ch)), ch["name"]))

    top = by_size(list(root_children.values()))
    # One folder that holds almost everything makes the first map a single rectangle: lift its children to the top level (its own
    # loose files stay as a part under the folder's own key, so citations to and from the folder still land somewhere).
    for _ in range(2):
        total_lines = sum(sum(r["lines"] for r in collect(ch)) for ch in top) or 1
        lead = top[0] if top else None
        if not lead or not lead["children"] or sum(r["lines"] for r in collect(lead)) / total_lines < _FLATTEN_SHARE:
            break
        lifted = list(lead["children"].values())
        if lead["own"]:
            lifted.append({"key": lead["key"], "name": f"{lead['name']} (loose files)", "children": {}, "own": lead["own"]})
        top = by_size(lifted + top[1:])
    children = [build(ch) for ch in top[:_MAX_CHILDREN]]
    if not children:
        raise ValueError("the census found no documents to draw")

    # ---- folder -> folder citations (exact at the drawn level)
    leaf_for: dict[str, str] = {}
    for folder in by_folder:
        parts = folder.split("/")
        for i in range(len(parts), 0, -1):
            k = "/".join(parts[:i])
            if k in ids:
                leaf_for[folder] = ids[k]
                break
    edges = []
    seen: Counter[tuple[str, str]] = Counter()
    for a, b, n in census["folder_refs"]:
        sa, sb = leaf_for.get(a), leaf_for.get(b)
        if sa and sb and sa != sb:
            seen[(sa, sb)] += n
    for (sa, sb), n in sorted(seen.items(), key=lambda kv: -kv[1])[:900]:
        edges.append({"src": sa, "dst": sb, "weight": n, "kind": "cites"})
    c = census
    total = c["documents"]["total"]
    return {
        "id": "census-docs-explorer", "kind": "explorer", "unit": "lines",
        "arrows": {"out": "cites", "in": "cited by", "out_detail": "the folders whose documents it cites", "in_detail": "the folders whose documents cite it"},
        "title": "Explore the documentation tree",
        "caption": f"Fig. - Every folder of {c['project']}'s documentation as one map you can walk into. Area is lines; colour says how many of a folder's live documents were touched "
                   f"within {c['profile']['outdated_days']} days of {c['today']}. Click a folder for its subfolders and its longest-untouched documents.",
        "reader_question": "Which parts of the documentation are alive, which have gone quiet, and which are archives?",
        "insight": f"{total:,} documents in {len(by_folder)} folders; {c['freshness']['updated']:,} of {c['freshness']['population']:,} live documents were touched within the window.",
        "data_sources": [{"kind": "metric", "ref": "git history and the tracked tree", "retrieved": c["today"]}],
        "statuses": [
            {"key": "CURRENT", "label": "mostly updated", "tone": "green", "detail": "at most a quarter of the live documents are outdated"},
            {"key": "MIXED", "label": "mixed", "tone": "gold", "detail": "a quarter to three-fifths are outdated"},
            {"key": "OUTDATED", "label": "mostly outdated", "tone": "red", "detail": "more than three-fifths are outdated"},
            {"key": "ARCHIVE", "label": "archive or crossed out", "tone": "steel", "detail": "no live document: an archive path or marked superseded"},
        ],
        "kinds": [{"key": "cites", "label": "cites", "tone": "blue", "detail": "documents in one folder link to or name documents in the other"}],
        "root": {"id": "system", "name": c["project"] + " documents", "kicker": "The whole documentation", "summary": f"{total:,} documents.", "children": children},
        "edges": edges,
        "documents": documents,
    }


def modules_explorer(census: dict[str, Any]) -> dict[str, Any] | None:
    """The code hierarchy (package -> submodule), coloured by whether a live document names the package; ``None`` without code roots."""
    mods = census.get("modules")
    if not mods or not mods["packages"]:
        return None
    documented = set(mods.get("documented", []))
    used: set[str] = {"system"}
    ids: dict[str, str] = {}
    documents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    out_by: dict[str, list[tuple[str, int]]] = defaultdict(list)
    in_by: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for a, b, n in mods["edges"]:
        out_by[a].append((b, n))
        in_by[b].append((a, n))
    sub_by: dict[str, dict[str, list[tuple[str, int]]]] = defaultdict(lambda: defaultdict(list))
    for p, s, d, n in mods["sub_edges"]:
        sub_by[p][s].append((d, n))
    for pkg in mods["packages"][:_MAX_CHILDREN]:
        pid = _nid("p:", pkg["name"], used)
        ids[pkg["name"]] = pid
        subs = pkg["subs"]
        kids = []
        for s in subs[: _MAX_CHILDREN - 1]:
            node: dict[str, Any] = {"id": _nid("s:", f"{pkg['name']}.{s['name']}", used), "name": _short(s["name"], 80), "value": max(1, s["loc"]),
                                    "kicker": f"Submodule of {pkg['name']}", "facts": [["Files", str(s["files"])], ["Lines", f"{s['loc']:,}"]]}
            ext = sorted(sub_by[pkg["name"]].get(s["name"], []), key=lambda t: -t[1])
            if ext:
                node["lists"] = [{"title": "Imports from other packages", "items": [f"{d}: {n}" for d, n in ext[:30]]}]
            kids.append(node)
        if len(subs) > _MAX_CHILDREN - 1:
            rest = subs[_MAX_CHILDREN - 1 :]
            kids.append({"id": _nid("s:", pkg["name"] + ":others", used), "name": f"{len(rest)} smaller parts", "value": max(1, sum(s["loc"] for s in rest)),
                         "kicker": "Grouped to keep the map readable"})
        node = {"id": pid, "name": pkg["name"], "kicker": f"Package in {pkg['root']}", "status": "DOCUMENTED" if pkg["name"] in documented else "UNDOCUMENTED",
                "summary": f"{pkg['files']} files, {pkg['loc']:,} lines; imports {pkg['fan_out']} times, imported {pkg['fan_in']} times.",
                "facts": [["Files", str(pkg["files"])], ["Lines", f"{pkg['loc']:,}"], ["Imports it makes", str(pkg["fan_out"])], ["Imports it receives", str(pkg["fan_in"])],
                          ["Named by a live document", "yes" if pkg["name"] in documented else "no"]],
                "children": kids}
        if len(documents) < _MAX_DOSSIERS:
            did = f"m-{len(documents)}"
            blocks: list[dict[str, Any]] = [{"t": "kv", "rows": node["facts"]}]
            if out_by.get(pkg["name"]):
                blocks += [{"t": "h", "text": "Packages it imports"}, {"t": "table", "head": ["Package", "Imports"], "rows": [[b, str(n)] for b, n in sorted(out_by[pkg["name"]], key=lambda t: -t[1])[:30]]}]
            if in_by.get(pkg["name"]):
                blocks += [{"t": "h", "text": "Packages that import it"}, {"t": "table", "head": ["Package", "Imports"], "rows": [[a, str(n)] for a, n in sorted(in_by[pkg["name"]], key=lambda t: -t[1])[:30]]}]
            blocks += [{"t": "h", "text": "Largest parts"}, {"t": "table", "head": ["Part", "Lines", "Files"], "rows": [[s["name"], f"{s['loc']:,}", str(s["files"])] for s in subs[:15]]}]
            documents.append({"id": did, "title": f"{pkg['name']} — dossier", "sources": ["the source tree, read with ast"], "blocks": blocks})
            node["docs"] = [did]
        children.append(node)
    edges = [{"src": ids[a], "dst": ids[b], "weight": n, "kind": "imports"} for a, b, n in mods["edges"] if a in ids and b in ids]
    n_pk = len(mods["packages"])
    return {
        "id": "census-code-explorer", "kind": "explorer", "unit": "lines",
        "arrows": {"out": "imports", "in": "imported by", "out_detail": "the packages it imports", "in_detail": "the packages that import it"},
        "title": "Explore the code: packages and submodules",
        "caption": f"Fig. - The source tree as one map you can walk into. Area is lines ({mods['loc']:,} in {mods['files']:,} files); colour says whether a live document names the package. "
                   f"Connections are import statements read with ast, between packages under {', '.join(mods['roots'])}.",
        "reader_question": "What is inside each package, what does it import, and is it written down anywhere?",
        "insight": f"{len(documented)} of {n_pk} packages are named by a live document.",
        "data_sources": [{"kind": "metric", "ref": "the source tree, read with ast", "retrieved": census["today"]}],
        "statuses": [{"key": "DOCUMENTED", "label": "named by a document", "tone": "green", "detail": "a live document names this package by path"},
                     {"key": "UNDOCUMENTED", "label": "not named", "tone": "red", "detail": "no live document names this package by path"}],
        "kinds": [{"key": "imports", "label": "imports", "tone": "blue", "detail": "the package imports the other"}],
        "root": {"id": "system", "name": census["project"] + " code", "kicker": "The whole source tree", "summary": f"{n_pk} packages, {mods['loc']:,} lines.", "children": children},
        "edges": edges,
        "documents": documents,
    }
