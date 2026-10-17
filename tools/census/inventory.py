"""How many different charts, graphs and figures the engine can draw — counted from its own registries, never from memory.

Three engines draw figures, and each keeps its own list:

* the document engine's figure kinds (``tools.docgen.generator._FIGURE_KINDS``): native pictures, two bridges (to the chart engine
  and to Mermaid) and the explorer block;
* the chart engine's supported visuals (``SUPPORTED_VISUALS`` in its validator);
* Mermaid's text-diagram types (the table in the Mermaid engine's README, which states its scope as exactly the rows it lists).

``inventory`` reads those three and returns the counts together with the names, plus how many names are offered by more than one
engine (a bar chart exists as a native figure and as a chart-engine visual: two implementations, one idea). The headline number is
the sum of implementations; the second number merges the names the engines share, through an explicit alias table.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

# The same idea under two names, merged only when the two engines really draw the same thing.
_ALIASES: Final = {"stateDiagram-v2": "state", "sequenceDiagram": "sequence", "flowchart": "flowchart", "graph": "flowchart", "erDiagram": "er", "classDiagram": "class",
                   "xychart-beta": "xychart", "donut": "pie", "matrix": "heatmap", "bar_grouped": "bar", "bar_stacked": "bar", "bar_horizontal": "bar",
                   "line_step": "line", "area_stacked": "area"}


def _supported_visuals(root: Path) -> list[str]:
    text = (root / "tools/visual-engine/adapters/echarts/validate.mjs").read_text(encoding="utf-8")
    block = re.search(r"SUPPORTED_VISUALS\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not block:
        raise ValueError("the chart engine's SUPPORTED_VISUALS list was not found")
    return [v for v in re.findall(r'"([a-z_0-9]+)"', block.group(1)) if v != "none"]


def _mermaid_types(root: Path) -> list[str]:
    text = (root / "tools/mermaid-engine/README.md").read_text(encoding="utf-8")
    section = text.split("## Supported diagram types", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\|\s*`([^|`]+)`[^|]*\|\s*([^|]+?)\s*\|", section, re.MULTILINE)
    return [syntax.split("/")[0].strip(" `") for syntax, _ in rows]


def inventory(root: Path) -> dict[str, Any]:
    """Counts and names of everything the engine at ``root`` can draw (``root`` is the engine's own repository root)."""
    from tools.docgen import (
        generator,  # imported late: the census measures without drawing
    )

    kinds = sorted(generator._FIGURE_KINDS)
    bridges = [k for k in kinds if k in {"echarts", "mermaid"}]
    blocks = [k for k in kinds if k in {"explorer"}]
    native = [k for k in kinds if k not in bridges and k not in blocks]
    charts = _supported_visuals(root)
    mermaid = _mermaid_types(root)
    merged = {_ALIASES.get(n, n) for n in native + charts + mermaid}
    # Names two engines both offer (after aliasing): the overlap the merged count removes.
    seen: dict[str, int] = {}
    for n in native + charts + mermaid:
        seen[_ALIASES.get(n, n)] = seen.get(_ALIASES.get(n, n), 0) + 1
    return {
        "document_engine": {"native": native, "bridges": bridges, "blocks": blocks, "count": len(kinds)},
        "chart_engine": {"visuals": charts, "count": len(charts)},
        "mermaid_engine": {"types": mermaid, "count": len(mermaid)},
        "implementations": len(native) + len(blocks) + len(charts) + len(mermaid),
        "distinct_after_merging_names": len(merged),
        "offered_by_more_than_one_engine": sorted(k for k, n in seen.items() if n > 1),
        "how_counted": "native figures + explorer block + chart-engine visuals + Mermaid types; the two bridges are doors to the other engines and are not counted twice",
    }
