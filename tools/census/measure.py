"""The measurement: every number the census reports, with the rule that made it.

``measure`` reads a repository and a profile and returns one plain dictionary (``census/1``). It is deterministic for a given
commit, profile and reference date: ages are counted from the commit date of ``HEAD`` (or the profile's ``today``), never from the
wall clock, so the same tree measures the same on every machine and on every day.

Definitions (also written into the result under ``rules`` so a reader of the numbers can read the definitions):

* a DOCUMENT is a tracked file that matches ``doc_globs`` and has one of ``doc_exts``;
* it is ARCHIVED when it matches ``archive_globs``, MARKED when its header declares a lifecycle state (superseded, retired,
  deprecated, archived), and REMOVED when git history shows it deleted and it is not in the tree. A body that merely
  mentions "superseded" is not marked;
* the UPDATED / OUTDATED split counts live, unmarked documents only (an archive is expected to be old): updated = touched
  within ``outdated_days``, outdated = not;
* a STAMP is a header line matching ``stamp_patterns``; it is VALID when its commit exists and the document's body (stamp lines removed
  from both sides, as a stamp cannot be present at the commit it names) is unchanged since, DRIFTED when the body changed, INVALIDATED
  when its own status text says it no longer holds, UNVERIFIABLE when the document did not exist at that path then, UNRESOLVED when the
  commit cannot be found in this clone;
* AUTHORITATIVE = stamped, or labelled "source of truth" in the header, or named by an ``authority_docs`` document;
* a document is WIRED when another live document links to or names its path; CITED BY AN UPDATED DOCUMENT when one of those
  was itself touched within ``outdated_days``.

There is deliberately no composite "completeness percentage": each dimension is reported as ``covered of total`` with its rule,
because one number lets a hole in one dimension hide behind the rest.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from tools.census import gitscan, modules
from tools.census.profile import Profile, matcher

SCHEMA: Final = "census/1"
_LINK_RE: Final = re.compile(r"\]\(\s*<?([^)\s>#]+)(?:#[^)\s>]*)?(?:\s+\"[^\"]*\")?\s*>?\)")
_H1_RE: Final = re.compile(r"^\s{0,3}#\s+\S", re.MULTILINE)
_STAMP_CHECK_CAP: Final = 400


def _without_stamps(text: str, patterns: list[re.Pattern[str]]) -> str:
    """The body of a stamped document: the stamp lines removed, because a stamp cannot be present at the commit it names (writing its
    sha in is what changed the file). Compared with the stamps stripped on both sides, an edit to the body still shows and the act of
    stamping does not."""
    return "\n".join(line for line in text.splitlines() if not any(rx.search(line) for rx in patterns))


def _day(value: str) -> date:
    return date.fromisoformat(value)


def area_of(path: str, depth: int) -> str:
    """The first ``depth`` directories of ``path`` (``(root)`` for a file at the top)."""
    parts = path.split("/")[:-1]
    return "/".join(parts[:depth]) if parts else "(root)"


def _tokens(text: str, exts: tuple[str, ...]) -> set[str]:
    """Path-like words in ``text`` ending in one of ``exts``."""
    pattern = r"(?<![\w/.-])([A-Za-z0-9_.][A-Za-z0-9_./-]*(?:" + "|".join(re.escape(e) for e in exts) + r"))(?![\w-])"
    return set(re.findall(pattern, text))


def _resolve(source: str, target: str) -> str:
    """A link target as a repository-relative path (``/x`` is from the root, anything else from the source's directory)."""
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def _buckets(ages: list[int], edges: list[int]) -> list[dict[str, Any]]:
    labels = [f"0-{edges[0]} d"] + [f"{a + 1}-{b} d" for a, b in pairwise(edges)] + [f">{edges[-1]} d"]
    counts = [0] * len(labels)
    for age in ages:
        i = 0
        while i < len(edges) and age > edges[i]:
            i += 1
        counts[i] += 1
    return [{"label": lab, "n": n} for lab, n in zip(labels, counts, strict=True)]


def _months(start: str, end: str) -> list[str]:
    y, m = int(start[:4]), int(start[5:7])
    ye, me = int(end[:4]), int(end[5:7])
    out = []
    while (y, m) <= (ye, me):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def measure(root: Path, profile: Profile, today: str | None = None) -> dict[str, Any]:
    """Measure the repository at ``root`` under ``profile``; see the module docstring for every definition."""
    sha, head_date = gitscan.head(root)
    ref = today or profile.today or head_date
    ref_day = _day(ref)
    files = gitscan.tracked(root)
    fileset = set(files)
    is_doc_glob = matcher(profile.doc_globs)
    is_archive = matcher(profile.archive_globs)

    def is_doc(path: str) -> bool:
        return is_doc_glob(path) and path.lower().endswith(profile.doc_exts)

    docs = [p for p in files if is_doc(p)]
    docset = set(docs)
    window_start = reference_window(ref, profile.outdated_days)
    hist = gitscan.history(root, fileset, window_start)

    texts = {p: gitscan.read(root, p) for p in docs}
    headers = {p: "\n".join(t.split("\n", profile.header_lines)[: profile.header_lines]) for p, t in texts.items()}

    def age(path: str) -> int:
        last = hist.last_touch.get(path)
        return max(0, (ref_day - _day(last)).days) if last else 10**6

    archived = {p for p in docs if is_archive(p)}
    live = [p for p in docs if p not in archived]
    marked: dict[str, list[str]] = {}
    for p in docs:
        hits = [name for name, pats in profile.lifecycle_markers.items() if any(re.search(r, headers[p], re.IGNORECASE | re.MULTILINE) for r in pats)]
        if hits:
            marked[p] = sorted(hits)
    crossed = archived | set(marked)

    population = [p for p in live if p not in marked]
    updated = [p for p in population if age(p) <= profile.outdated_days]
    fresh = [p for p in population if age(p) <= profile.fresh_days]
    recent = [p for p in updated if p not in set(fresh)]
    outdated = [p for p in population if age(p) > profile.outdated_days]
    edges_days = sorted({profile.fresh_days, profile.outdated_days, 90, 180, 365})
    ages = [age(p) for p in population]

    def state(p: str) -> str:
        if p in archived:
            return "archived"
        if p in marked:
            return "marked"
        a = age(p)
        return "fresh" if a <= profile.fresh_days else "recent" if a <= profile.outdated_days else "outdated"

    # ---- by area
    by_area: dict[str, Counter[str]] = defaultdict(Counter)
    for p in docs:
        by_area[area_of(p, profile.area_depth)][state(p)] += 1
    areas = [
        {"area": a, "total": sum(c.values()), **{k: c.get(k, 0) for k in ("fresh", "recent", "outdated", "marked", "archived")}}
        for a, c in sorted(by_area.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    ]

    # ---- links, references
    refs: dict[str, set[str]] = defaultdict(set)
    rel_total = rel_dangling = 0
    dirs: set[str] = {"."}
    for f in files:
        d = posixpath.dirname(f)
        while d and d not in dirs:
            dirs.add(d)
            d = posixpath.dirname(d)
    for p in docs:
        text = texts[p]
        if p.lower().endswith(".md"):
            for target in _LINK_RE.findall(text):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                rel_total += 1
                resolved = _resolve(p, target)
                if resolved in fileset or resolved in dirs:
                    if resolved in docset and resolved != p and p != profile.index_doc:
                        refs[resolved].add(p)
                else:
                    rel_dangling += 1
        for tok in _tokens(text, profile.doc_exts):
            for cand in (tok, _resolve(p, tok)):
                if cand in docset and cand != p and p != profile.index_doc:
                    refs[cand].add(p)
                    break

    # ---- stamps and authority
    stamps: list[dict[str, Any]] = []
    stamped: set[str] = set()
    compiled = [re.compile(r, re.IGNORECASE | re.MULTILINE) for r in profile.stamp_patterns]
    for p in docs:
        for rx in compiled:
            m = rx.search(headers[p])
            if m:
                g = m.groupdict()
                stamps.append({"path": p, "status": (g.get("status") or "").strip(), "sha": g.get("sha") or "", "date": g.get("date") or ""})
                stamped.add(p)
                break
    for i, s in enumerate(stamps):
        if any(re.search(r, s["status"], re.IGNORECASE) for r in profile.invalidated_patterns):
            s["state"], s["since"] = "INVALIDATED", 0
        elif i >= _STAMP_CHECK_CAP:
            s["state"], s["since"] = "NOT_CHECKED", 0
        elif not s["sha"] or not gitscan.commit_exists(root, s["sha"]):
            s["state"], s["since"] = "UNRESOLVED", 0
        else:
            s["since"] = gitscan.commits_since(root, s["sha"], s["path"])
            blob = gitscan.show(root, s["sha"], s["path"])
            if blob is None:
                s["state"] = "UNVERIFIABLE"  # the document did not exist at that path then (moved or renamed): nothing to compare
            else:
                s["state"] = "VALID" if _without_stamps(blob, compiled) == _without_stamps(texts[s["path"]], compiled) else "DRIFTED"
    labelled = {p for p in docs if any(re.search(r, headers[p], re.IGNORECASE | re.MULTILINE) for r in profile.truth_label_patterns)}
    declared: set[str] = set()
    for a in profile.authority_docs:
        if a in docset:
            for tok in _tokens(texts[a], profile.doc_exts) | {_resolve(a, t) for t in _LINK_RE.findall(texts[a])}:
                for cand in (tok, _resolve(a, tok)):
                    if cand in docset and cand != a:
                        declared.add(cand)
                        break
    authoritative = sorted(stamped | labelled | declared)
    live_set = set(live)
    wired = [p for p in authoritative if refs.get(p, set()) & live_set]
    cited_updated = [p for p in authoritative if any(age(r) <= profile.outdated_days for r in refs.get(p, set()) & live_set)]
    stamp_states = Counter(s["state"] for s in stamps)
    auth_set = set(authoritative)
    live_stamped_valid = [s["path"] for s in stamps if s["state"] == "VALID" and s["path"] in live_set]
    window_commits = [paths for _d, paths in hist.recent]
    window_doc = [pp for pp in ([x for x in paths if x in docset] for paths in window_commits) if pp]
    window_auth = [pp for pp in window_doc if any(x in auth_set for x in pp)]

    # ---- completeness dimensions (counts, never a composite)
    dims: list[dict[str, Any]] = []
    md_docs = [p for p in docs if p.lower().endswith(".md")]
    titled = [p for p in md_docs if _H1_RE.search(texts[p])]
    dims.append({"id": "titled", "label": "Markdown documents with a title", "covered": len(titled), "of": len(md_docs), "rule": "a level-1 heading exists"})
    dims.append({"id": "links", "label": "Relative links that resolve", "covered": rel_total - rel_dangling, "of": rel_total, "rule": "the target is a tracked file"})
    dims.append({"id": "updated", "label": "Live documents updated recently", "covered": len(updated), "of": len(population),
                 "rule": f"touched within {profile.outdated_days} days of {ref}; archived and marked documents are not counted"})
    if profile.index_doc and profile.index_doc in docset:
        indexed = _tokens(texts[profile.index_doc], profile.doc_exts) | {_resolve(profile.index_doc, t) for t in _LINK_RE.findall(texts[profile.index_doc])}
        listed = [p for p in docs if p in indexed or p == profile.index_doc]
        dims.append({"id": "indexed", "label": "Documents listed in the index", "covered": len(listed), "of": len(docs), "rule": f"named in {profile.index_doc}"})
    if stamps:
        dims.append({"id": "stamps", "label": "Source-of-truth stamps that still hold", "covered": stamp_states.get("VALID", 0), "of": len(stamps),
                     "rule": "the stamped commit exists and the body is unchanged since it (stamp lines removed from both sides)"})
    if authoritative:
        dims.append({"id": "wired", "label": "Authoritative documents other live documents cite", "covered": len(wired), "of": len(authoritative),
                     "rule": "a live document links to or names the path"})
    if marked:
        misplaced = [p for p in marked if p not in archived]
        dims.append({"id": "cross_out", "label": "Crossed-out documents kept out of the live set", "covered": len(marked) - len(misplaced), "of": len(marked),
                     "rule": "a document marked superseded/retired/deprecated sits in an archive path"})
    mods: dict[str, Any] | None = None
    if profile.code_roots:
        mods = modules.read_modules(root, profile.code_roots, files)
        if mods["packages"]:
            live_text = "\n".join(texts[p] for p in live)
            doc_cov = modules.documented(mods, live_text)
            mods["documented"] = doc_cov
            dims.append({"id": "modules", "label": "Code packages named by a live document", "covered": len(doc_cov), "of": len(mods["packages"]),
                         "rule": "a live document names '<root>/<package>'"})

    # ---- history
    first_months = Counter(hist.first_seen[p][:7] for p in docs if p in hist.first_seen)
    removed_docs = {p: d for p, d in hist.removed.items() if is_doc(p)}
    removed_months = Counter(d[:7] for d in removed_docs.values())
    touched_months = Counter(hist.last_touch[p][:7] for p in docs if p in hist.last_touch)
    all_months = sorted(set(first_months) | set(removed_months) | set(touched_months))
    months = _months(all_months[0], all_months[-1]) if all_months else []

    stamp_of = {s["path"]: s["state"] for s in stamps}
    folder_refs: Counter[tuple[str, str]] = Counter()
    for dst, srcs in refs.items():
        for src in srcs:
            fa, fb = area_of(src, profile.explorer_depth), area_of(dst, profile.explorer_depth)
            if fa != fb:
                folder_refs[(fa, fb)] += 1
    records = [
        {"p": p, "area": area_of(p, profile.area_depth), "state": state(p), "age": age(p) if p in hist.last_touch else None, "last": hist.last_touch.get(p, ""),
         "first": hist.first_seen.get(p, ""), "commits": hist.commits.get(p, 0), "lines": texts[p].count("\n") + (1 if texts[p] else 0),
         "marks": marked.get(p, []), "stamp": stamp_of.get(p, ""), "auth": p in auth_set,
         "refs_in": len(refs.get(p, set()))}
        for p in docs
    ]
    return {
        "schema": SCHEMA,
        "project": profile.project,
        "head": {"sha": sha, "date": head_date},
        "today": ref,
        "dirty": gitscan.is_dirty(root),
        "profile": {"doc_globs": list(profile.doc_globs), "doc_exts": list(profile.doc_exts), "archive_globs": list(profile.archive_globs),
                    "fresh_days": profile.fresh_days, "outdated_days": profile.outdated_days, "area_depth": profile.area_depth, "header_lines": profile.header_lines},
        "rules": {"document": "tracked, matches doc_globs, has a doc extension", "updated": f"live, unmarked, touched within {profile.outdated_days} days of the reference date",
                  "crossed_out": "archived by path, marked in the header, or deleted from the tree", "stamp": "VALID = the commit exists and the body is unchanged since it, stamp lines removed from both sides",
                  "authoritative": "stamped, labelled source-of-truth in the header, or named by an authority document",
                  "completeness": "per-dimension counts; no composite number by design"},
        "documents": {"total": len(docs), "live": len(live), "archived": len(archived), "by_ext": dict(sorted(Counter(Path(p).suffix.lower() for p in docs).items())),
                      "areas": areas, "tracked_files": len(files)},
        "freshness": {"population": len(population), "fresh": len(fresh), "recent": len(recent), "updated": len(updated), "outdated": len(outdated),
                      "median_age_days": sorted(ages)[len(ages) // 2] if ages else 0, "histogram": _buckets(ages, edges_days),
                      "oldest": [{"p": p, "age": age(p)} for p in sorted(population, key=lambda q: -age(q))[:15]],
                      "newest": [{"p": p, "age": age(p)} for p in sorted(population, key=age)[:15]]},
        "lifecycle": {"archived": len(archived), "marked": len(marked), "marked_by": dict(Counter(m for v in marked.values() for m in v)),
                      "marked_but_live": len([p for p in marked if p not in archived]), "removed": len(removed_docs),
                      "crossed_out_in_tree": len(crossed), "crossed_out_total": len(crossed) + len(removed_docs), "renamed_paths": hist.renamed},
        "truth": {"stamped": len(stamped), "labelled": len(labelled), "declared": len(declared), "authoritative": len(authoritative),
                  "stamp_states": dict(stamp_states), "stamps": stamps, "wired": len(wired), "cited_by_updated": len(cited_updated),
                  "not_wired": [p for p in authoritative if p not in set(wired)][:40],
                  "live_valid_stamps": len(live_stamped_valid),
                  "window": {"since": window_start, "commits": len(window_commits), "doc_commits": len(window_doc), "authoritative_commits": len(window_auth)},
                  "stamps_by_status": dict(Counter(s["status"] for s in stamps))},
        "completeness": {"dimensions": dims},
        "history": {"months": months, "added": [first_months.get(m, 0) for m in months], "removed": [removed_months.get(m, 0) for m in months],
                    "touched": [touched_months.get(m, 0) for m in months], "commits": hist.commit_count},
        "links": {"relative": rel_total, "dangling": rel_dangling},
        "modules": mods,
        "folder_refs": [[a, b, n] for (a, b), n in sorted(folder_refs.items(), key=lambda kv: (-kv[1], kv[0]))],
        "records": records,
    }


def reference_window(today: str, days: int) -> str:
    """The date ``days`` before ``today`` (used by reports that print the window's start)."""
    return (_day(today) - timedelta(days=days)).isoformat()
