"""Render PROJECT_INDEX.json as a self-contained HTML dashboard — the "what have I built"
view. Reuses docgen's own dark/light theme tokens (tools/docgen/assets/tokens.json) so it
looks native next to generated documents, but has no import dependency on docgen itself
(this module only reads the token JSON as data) — project-index stays usable even in a
context where docgen isn't installed.

Stdlib only. No wall-clock timestamps are embedded (deterministic — the caller supplies
``created``/``updated`` strings when registering an artifact; this renderer never calls
datetime.now()).
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from tools.docgen import engine_config
from tools.project_index import index


def _group_by_section(artifacts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for a in artifacts:
        groups.setdefault(a.get("section") or "(no section)", []).append(a)
    return dict(sorted(groups.items()))


def render_dashboard_html() -> str:
    artifacts = index.list_artifacts()
    stats = index.stats()
    groups = _group_by_section(artifacts)

    stat_cards = "".join(
        f'<div class="stat-card"><div class="stat-n">{v}</div><div class="stat-label">{escape(k)}</div></div>'
        for k, v in sorted(stats["by_type"].items())
    )

    sections_html = []
    for section, items in groups.items():
        rows = "".join(
            f"""<tr>
  <td><span class="type-badge type-{escape(a.get('type','other'))}">{escape(a.get('type','other'))}</span></td>
  <td>{escape(a.get('title',''))}</td>
  <td class="muted">{escape(a.get('path',''))}</td>
  <td>{escape(a.get('summary',''))}</td>
  <td>{''.join(f'<span class="tag">{escape(t)}</span>' for t in (a.get('tags') or []))}</td>
  <td><span class="status-badge status-{escape(a.get('status','draft'))}">{escape(a.get('status','draft'))}</span></td>
  <td class="muted">{escape(a.get('updated') or a.get('created') or '')}</td>
</tr>"""
            for a in items
        )
        sections_html.append(
            f"""<section class="section-block">
  <h2>{escape(section)} <span class="muted">({len(items)})</span></h2>
  <table>
    <thead><tr><th>Type</th><th>Title</th><th>Path</th><th>Summary</th><th>Tags</th><th>Status</th><th>Updated</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""
        )

    empty_state = (
        '<p class="muted">No artifacts registered yet. Call '
        '<code>tools.project_index.index.register_artifact(...)</code> or '
        '<code>python3 -m tools.project_index.cli register ...</code> after creating a '
        "document, chart, graph, or diagram.</p>"
        if not artifacts
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Project Index — {stats['total']} artifacts</title>
<style>
:root{{ --paper:#060608; --paper-2:#141420; --fg:#EAEEF5; --muted:#8A96AE; --line:#252A38; --accent:#4A7FC1; }}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--fg);font:14px/1.5 -apple-system,"Segoe UI",Inter,system-ui,sans-serif;padding:32px}}
h1{{font-size:22px;margin:0 0 4px}}
.muted{{color:var(--muted)}}
.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0 32px}}
.stat-card{{background:var(--paper-2);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:100px}}
.stat-n{{font-size:24px;font-weight:700}}
.stat-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.section-block{{margin-bottom:32px}}
h2{{font-size:15px;border-bottom:1px solid var(--line);padding-bottom:8px;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:var(--muted);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:.03em;padding:6px 10px;border-bottom:1px solid var(--line)}}
td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
tr:hover td{{background:color-mix(in srgb, var(--paper-2) 60%, transparent)}}
.type-badge,.status-badge{{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;background:var(--paper-2);border:1px solid var(--line)}}
.tag{{display:inline-block;background:var(--paper-2);border:1px solid var(--line);border-radius:5px;padding:1px 6px;margin:1px;font-size:11px}}
</style>
</head>
<body>
<h1>Project Index</h1>
<p class="muted">{stats['total']} artifacts across {len(groups)} section(s). Generated from PROJECT_INDEX.json — not live, re-run the dashboard command to refresh.</p>
<div class="stats-row">{stat_cards}</div>
{empty_state}
{''.join(sections_html)}
</body>
</html>
"""


class WriteBlockedError(RuntimeError):
    """Raised when ``write_dashboard``'s target would land outside the host project root."""


def write_dashboard(out_path: str | None = None) -> Path:
    html = render_dashboard_html()
    root = engine_config.host_root()
    target = Path(out_path) if out_path else (root / "PROJECT_INDEX.html")

    # Containment (`P8-074`). `docgen`'s own `build`/`render`/`index` subcommands all refuse an
    # `--out` that resolves outside the repo root (`OG-60`) — this subcommand accepted one at exit 0
    # with no check at all, reproduced live: `dashboard --out /tmp/x.html` wrote outside the repo
    # while `docgen index` refused the identical shape with exit 2. The check is duplicated here
    # rather than imported from `tools.docgen.generator` on purpose: this module's docstring
    # declares no import dependency on docgen itself (only the lightweight `engine_config` loader),
    # so project-index stays usable even where docgen isn't installed — same shape, not the same
    # import.
    target_dir = target.parent if target.suffix else target
    resolved = target_dir.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise WriteBlockedError(
            f"path {target_dir} resolves outside the repo root ({root}): {resolved}"
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


__all__ = ["WriteBlockedError", "render_dashboard_html", "write_dashboard"]
