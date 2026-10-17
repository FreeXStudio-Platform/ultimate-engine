"""The derived SQLite index — `BUILD_PLAN.md` D1, in stdlib, gitignored, never authoritative.

THE DECISION THIS IMPLEMENTS, RESTATED ONLY AS ITS CONSEQUENCE
=============================================================
D1: **documents are the source of truth; SQLite is a derived index.** The corpus stays as Markdown
and JSON in git — diffable, reviewable, greppable, and the thing a stamp can be computed over — and
a database is built *from* it so that the questions that are joins stop being full-tree greps.

Three properties follow, and all three are enforced here rather than promised:

**Gitignored.** ``.blueprint/`` is in ``.gitignore``. A committed database is a second source of
truth that a stale row can silently win, which is the exact failure D1 exists to prevent.

**Rebuildable in seconds.** Nothing is stored here that is not re-derivable from the tree, so
deleting it costs a rebuild and never costs information.

**Never authoritative.** Every table is written from the model in one transaction, after a full
``DROP``. There is no update path, no migration and no partial write, because an index that can
drift from its source is worse than no index — it answers confidently.

WHY IT REFUSES TO BE EMPTY
==========================
``RULES.md`` Rule 6's mechanical corollary, paid for on this repository: *a builder that produces
an empty result must exit non-zero.* This project's previous navigation layer reported **1**
artifact for 295 tracked files and **0** nodes across ~77 modules, and every downstream reader
believed it. An empty index is not a result; it is a confident lie. :func:`build` raises rather
than write one.

FTS5
====
Verified available in this machine's stdlib ``sqlite3`` before D1 was taken, and re-asserted at
build time rather than assumed: a full-text table that silently does not exist would turn every
search into a zero-row answer, which reads exactly like "nothing matches".
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE containers (
    id TEXT PRIMARY KEY, name TEXT, purpose TEXT, document TEXT,
    depth INTEGER, level TEXT, modules INTEGER
);
CREATE TABLE modules (
    id TEXT PRIMARY KEY, package TEXT, container TEXT, document TEXT,
    in_degree INTEGER, out_degree INTEGER,
    depth INTEGER, level TEXT, stopped_because TEXT
);
CREATE TABLE edges (src TEXT, dst TEXT);
CREATE TABLE gatekeepers (module TEXT, gate TEXT, direction TEXT);
CREATE TABLE documents (
    path TEXT PRIMARY KEY, id TEXT, tier TEXT, status TEXT, title TEXT,
    version TEXT, revision TEXT, verified_state TEXT
);
CREATE TABLE surfaces (surface TEXT, key TEXT, detail TEXT);
CREATE TABLE open_work (id TEXT PRIMARY KEY, severity TEXT, disposition TEXT, title TEXT);
CREATE VIRTUAL TABLE doc_fts USING fts5(path UNINDEXED, body);
CREATE INDEX idx_modules_container ON modules(container);
CREATE INDEX idx_edges_src ON edges(src);
CREATE INDEX idx_gatekeepers_module ON gatekeepers(module);
"""


class EmptyIndexError(RuntimeError):
    """The index would have been empty. Never written — see the module docstring."""


def index_path(root: Path) -> Path:
    from tools.docgen import engine_config

    configured = engine_config.blueprint_index_dir()
    # Prefer the caller's root when it differs and exists, so a verifier working in a throwaway
    # `git archive` lab indexes the lab rather than the checkout it was cut from.
    local = root / configured.name
    directory = local if configured != local and local.parent.is_dir() else configured
    return directory / "index.db"


def fts5_available() -> bool:
    """Asserted, not assumed — a missing FTS5 makes every search a silent zero-row answer."""
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
        con.close()
        return True
    except sqlite3.Error:
        return False


def build(root: Path, model: dict[str, Any]) -> dict[str, int]:
    """Write the whole index in one transaction. Returns the row count per table."""
    if not fts5_available():
        raise EmptyIndexError(
            "FTS5 is not available in this Python's sqlite3 — the full-text half of the index "
            "cannot be built, and a partial index that answers searches with zero rows is worse "
            "than none"
        )

    nodes = model["graph"]["nodes"]
    if not nodes:
        raise EmptyIndexError("the model contains no modules — an empty index is not a result")

    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        owner: dict[str, str] = model.get("ownership", {}).get("owner", {})
        depths: dict[str, Any] = model.get("depth", {}).get("modules", {})
        gates: dict[str, Any] = model.get("gatekeepers", {})
        container_doc = {c["id"]: c["document"] for c in model.get("containers", [])}

        con.executemany(
            "INSERT INTO containers VALUES (?,?,?,?,?,?,?)",
            [
                (
                    c["id"], c["name"], c["purpose"], c["document"],
                    c.get("depth", 0), c.get("level", ""), c.get("modules", 0),
                )
                for c in model.get("containers", [])
            ],
        )
        con.executemany(
            "INSERT INTO modules VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    n["id"], n["package"], owner.get(n["id"], ""),
                    container_doc.get(owner.get(n["id"], ""), ""),
                    n["in"], n["out"],
                    depths.get(n["id"], {}).get("depth", 0),
                    depths.get(n["id"], {}).get("level", ""),
                    depths.get(n["id"], {}).get("stopped_because", ""),
                )
                for n in nodes
            ],
        )
        con.executemany(
            "INSERT INTO edges VALUES (?,?)",
            [tuple(e.split(" -> ", 1)) for e in model["graph"]["edges"] if " -> " in e],
        )
        con.executemany(
            "INSERT INTO gatekeepers VALUES (?,?,?)",
            [
                (module, gate, direction)
                for module, rec in gates.items()
                for direction, names in (("guarded_by", rec.get("guarded_by", [])),
                                         ("emits", rec.get("emits", [])))
                for gate in names
            ],
        )
        con.executemany(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    d["path"], d.get("id", ""), d.get("tier", ""), d.get("status", ""),
                    d.get("title", ""), d.get("version", ""), d.get("revision", ""),
                    d.get("verified_state", ""),
                )
                for d in model["documents"]
            ],
        )
        con.executemany(
            "INSERT INTO open_work VALUES (?,?,?,?)",
            [(r["id"], r["severity"], r["disposition"], r["title"]) for r in model["open_work"]],
        )
        surfaces = model.get("surfaces", {})
        rows: list[tuple[str, str, str]] = []
        for name, payload in surfaces.items():
            if isinstance(payload, list):
                for item in payload:
                    key = str(
                        item.get("id") or item.get("guard") or item.get("kind")
                        or item.get("invocation") or item.get("path")
                        or f"{item.get('section', '')}.{item.get('key', '')}"
                    )
                    rows.append((name, key, json.dumps(item, sort_keys=True)))
            else:
                rows.append((name, name, json.dumps(payload, sort_keys=True)))
        con.executemany("INSERT INTO surfaces VALUES (?,?,?)", rows)

        # Full text over the corpus itself — the half that makes "which document says X" a query
        # rather than a grep of 70 files.
        fts: list[tuple[str, str]] = []
        for doc in model["documents"]:
            try:
                fts.append((doc["path"], (root / doc["path"]).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
        con.executemany("INSERT INTO doc_fts VALUES (?,?)", fts)
        con.commit()

        counts = {
            table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("containers", "modules", "edges", "gatekeepers", "documents",
                          "surfaces", "open_work", "doc_fts")
        }
    finally:
        con.close()

    empty = [t for t, n in counts.items() if n == 0 and t != "open_work"]
    if empty:
        path.unlink(missing_ok=True)
        raise EmptyIndexError(
            f"table(s) {', '.join(empty)} came out empty — refusing to write an index that would "
            f"answer confidently and wrongly (RULES.md Rule 6)"
        )
    return counts


# The canonical questions, kept HERE rather than in the CLI so the SQL is reviewable beside the
# schema it runs against, and so a probe can call them without going through argparse.
QUERIES: dict[str, tuple[str, str]] = {
    "which modules have no document": (
        (
            "Modules whose container declares no owning document — the completeness question D1 "
            "exists to make cheap."
        ),
        "SELECT id, package, container FROM modules WHERE document = '' ORDER BY id",
    ),
    "which modules have no gatekeeper": (
        (
            "Modules no registered guard, check or hook reads. Not necessarily a defect; always "
            "worth knowing before changing one."
        ),
        (
            "SELECT m.id, m.package FROM modules m "
            "LEFT JOIN gatekeepers g ON g.module = m.id WHERE g.module IS NULL ORDER BY m.id"
        ),
    ),
    "where did we stop": (
        "The depth distribution: how many modules reached each rung of the C4 ladder.",
        "SELECT level, COUNT(*) AS modules FROM modules GROUP BY level ORDER BY MIN(depth)",
    ),
    "shallowest modules": (
        "The modules holding their container's depth down.",
        "SELECT id, level, stopped_because FROM modules ORDER BY depth, id LIMIT 20",
    ),
    "risky core": (
        "Highest in-degree first — a wrong change here breaks the most.",
        (
            "SELECT id, in_degree, out_degree, container FROM modules "
            "ORDER BY in_degree DESC, id LIMIT 12"
        ),
    ),
}


def query(root: Path, question: str) -> tuple[str, list[tuple[Any, ...]], list[str]]:
    """Run a named question. Returns ``(sql, rows, column names)``."""
    if question not in QUERIES:
        raise KeyError(question)
    _, sql = QUERIES[question]
    path = index_path(root)
    if not path.is_file():
        raise FileNotFoundError(path)
    con = sqlite3.connect(path)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description or []]
        return sql, cur.fetchall(), cols
    finally:
        con.close()


def search(root: Path, text: str, limit: int = 20) -> list[tuple[str, str]]:
    """Full-text search across the corpus, with a snippet showing why each row matched."""
    path = index_path(root)
    if not path.is_file():
        raise FileNotFoundError(path)
    con = sqlite3.connect(path)
    try:
        cur = con.execute(
            "SELECT path, snippet(doc_fts, 1, '[', ']', ' … ', 12) FROM doc_fts "
            "WHERE doc_fts MATCH ? ORDER BY rank LIMIT ?",
            (text, limit),
        )
        return [(str(r[0]), str(r[1])) for r in cur.fetchall()]
    finally:
        con.close()
