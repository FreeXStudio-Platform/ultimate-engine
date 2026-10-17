"""Bridge from docgen to the visual-engine ECharts adapter (tools/visual-engine).

Docgen remains the authority for document diagrams; this bridge adds the data-chart
families the generator's own docstring left unwired ("extend ``_FIGURE_RENDERERS``-style
dispatch") by delegating to the project's canonical chart engine instead of growing a
second chart implementation here. One engine per family (ENGINE_ROUTING_POLICY.json):
docgen renders diagrams natively; quantitative charts render through the engine's
deterministic SSR path and are embedded as inline SVG exactly like every other figure.

Invariants preserved:
- **Determinism** — the engine guarantees build-twice byte-identical SVG for a fixed
  job + pinned engine version (its own regression suite locks this), so docgen's
  hash-gate discipline is unchanged.
- **Fail-closed** — a validation-gate failure, a missing Node runtime, or missing
  engine dependencies raises ``EChartsRenderError``; the build fails honestly rather
  than emitting a document with a silently absent figure (T-R9).
- **Leak-gate coverage** — the returned SVG is embedded into the document body BEFORE
  the export sanitizer runs, so rendered chart bytes pass the same 7-gate scan as
  every other output channel.

stdlib only (subprocess/tempfile/json/pathlib). ``mypy --strict`` clean.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.docgen import engine_config
from tools.docgen.models import DataSource, LegendEntry, Tier

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENGINE_ROOT = _REPO_ROOT / "tools" / "visual-engine"
_ENGINE_CLI = _ENGINE_ROOT / "adapters" / "echarts" / "cli.mjs"
_RENDER_TIMEOUT_S = 60

# --- Classification reconciliation (F9) --------------------------------------------------
#
# docgen has its own document-tier vocabulary (``models.Tier``: public/confidential/secret,
# RULEBOOK L2) and the visual-engine has its own, independently-evolved job-classification
# vocabulary (``adapters/echarts/validate.mjs`` ``CLASSIFICATIONS``:
# public/internal/confidential/restricted). Nothing reconciled the two before this: a job
# whose ``classification`` was literally the docgen-only token ``"secret"`` was refused by
# the engine's G-STRUCT gate as an *unknown token* — fail-closed today, but for a reason
# that evaporates the moment someone adds ``"secret"`` to ``CLASSIFICATIONS`` without also
# deciding how restrictive it is. Separately, nothing compared a job's declared
# classification against the tier of the document it was about to be inlined into at all,
# so a ``confidential`` chart could be embedded in a ``public`` document with no gate ever
# looking at the pair (the SVG bytes still pass the export sanitizer's leak gates — this is
# specifically about the undeclared *relationship* between the two labels, not content).
#
# ONE named, ordinal mapping settles both: every token from both vocabularies gets a rank,
# and a job may render into a document only if the job's rank is no more restrictive than
# the document's. docgen's ``secret`` reconciles onto the engine's most restrictive rank
# (``restricted``) — the two names differ but both mean "the ceiling of this vocabulary".
CLASSIFICATION_RANK: dict[str, int] = {
    # visual-engine vocabulary (adapters/echarts/validate.mjs CLASSIFICATIONS)
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    # docgen vocabulary (models.Tier) — the engine never sees this as a job classification,
    # but a document's tier is expressed in it, so it has to sit on the same scale to be
    # compared at all.
    "secret": 3,
}

_TIER_RANK: dict[Tier, int] = {
    Tier.PUBLIC: CLASSIFICATION_RANK["public"],
    Tier.CONFIDENTIAL: CLASSIFICATION_RANK["confidential"],
    Tier.SECRET: CLASSIFICATION_RANK["secret"],
}


class EChartsRenderError(RuntimeError):
    """Raised when the visual-engine render fails or cannot run (fail-closed)."""


def _classification_rank(token: str) -> int:
    """Look up ``token``'s rank on the reconciled scale, failing closed on the unknown."""
    try:
        return CLASSIFICATION_RANK[token]
    except KeyError:
        # A job that already passed the engine's own G-STRUCT gate cannot carry an
        # unrecognized classification — this is a belt-and-suspenders path for direct
        # callers of this module that skip the engine's own validation. Fail closed rather
        # than silently treating an unknown token as harmless.
        raise EChartsRenderError(
            f'classification "{token}" is not in the reconciled vocabulary '
            f"({', '.join(sorted(CLASSIFICATION_RANK))})"
        ) from None


def assert_embeddable(job_classification: str, doc_tier: Tier, *, figure_id: str) -> None:
    """Refuse when ``job_classification`` outranks ``doc_tier`` on the reconciled scale.

    This is the one place that compares a figure's declared classification against the
    tier of the document embedding it — previously nothing did, so a ``confidential`` chart
    could be inlined into a ``public`` document with no finding at all.
    """
    if _classification_rank(job_classification) > _TIER_RANK[doc_tier]:
        raise EChartsRenderError(
            f'figure "{figure_id}": declared classification "{job_classification}" is more '
            f'restrictive than the building document\'s tier "{doc_tier.value}" — refusing '
            "to inline a more-classified chart into a less-classified document."
        )


@dataclass(frozen=True)
class EChartsFigureSpec:
    """A docgen figure whose SVG comes from the visual-engine ECharts adapter.

    ``job`` is a normalized visual job packet (tools/visual-engine/schemas/
    visual-job.schema.json); the engine's own gates validate it — this class carries
    only what the generator's figure component needs (``id``, ``caption``, ``legend``).
    """

    id: str
    caption: str
    job: dict[str, Any]
    legend: list[LegendEntry] = field(default_factory=list)
    # **The one data-carrying figure kind that had nowhere to put a source** (`OG-63`). Every other
    # numeric spec in this engine declares ``data_sources``; this one did not, so the six ECharts
    # figures in this repository could not have been sourced even by an author who wanted to. A
    # convention that some kinds cannot physically obey is not a convention.
    data_sources: list[DataSource] = field(default_factory=list)


def spec_from_dict(data: dict[str, Any]) -> EChartsFigureSpec:
    """Build an ``EChartsFigureSpec`` from a sidecar ``*_spec.json`` object."""
    job = data.get("job")
    if not isinstance(job, dict):
        raise EChartsRenderError(
            f'figure "{data.get("id", "?")}": kind "echarts" requires a "job" object '
            "(a visual-engine job packet)"
        )
    legend = [
        LegendEntry(
            kind=str(entry.get("kind", "swatch")),
            key=str(entry.get("key", "")),
            label=str(entry["label"]),
        )
        for entry in data.get("legend", [])
    ]
    return EChartsFigureSpec(
        id=str(data.get("id", str(job.get("visual_id", "echarts-figure")))),
        caption=str(data.get("caption", "")),
        job=job,
        legend=legend,
        data_sources=[
            DataSource(
                kind=str(src.get("kind", "cited")),
                ref=str(src.get("ref", "")),
                retrieved=str(src.get("retrieved", "")),
                url=str(src.get("url", "")),
            )
            for src in data.get("data_sources", [])
            if isinstance(src, dict)
        ],
    )


def engine_available() -> tuple[bool, str]:
    """Report whether the engine can run here (Node discoverable + installed deps)."""
    if not _ENGINE_CLI.is_file():
        return False, f"engine CLI missing: {_ENGINE_CLI}"
    if not (_ENGINE_ROOT / "node_modules" / "echarts").is_dir():
        return False, f"engine deps not installed — run `npm ci` in {_ENGINE_ROOT}"
    node_bin = engine_config.tool_path("node")
    if not node_bin:
        return False, "node not found (checked ENGINE_NODE_BIN, engine.config.json, PATH)"
    try:
        subprocess.run([node_bin, "--version"], capture_output=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False, f"node found at {node_bin} but failed to run"
    return True, "ok"


def render_with_figure(
    spec: EChartsFigureSpec, *, doc_tier: Tier = Tier.PUBLIC
) -> tuple[str, dict[str, Any]]:
    """Render the figure's job through the engine's direct (non-MCP) CLI → SVG string.

    ``doc_tier`` is the classification of the document this figure is about to be
    embedded into (RULEBOOK L2, ``models.Tier``). It defaults to ``Tier.PUBLIC`` — the
    least permissive tier — because the current call site (``generator.py``'s
    ``_FIGURE_KINDS`` dispatch) does not yet pass the building document's real header
    classification through; until it does, this default means only a ``public``-classified
    job can render at all, which is the fail-closed posture for an unestablished caller
    rather than the previous behavior of never checking the pair. A caller that DOES know
    the document's tier (or a future ``generator.py`` wired to pass ``header.classification``)
    should pass it explicitly so a same-or-more-permissive document can legitimately embed a
    same-or-more-classified chart.

    The engine writes ``<visual_id>.svg`` into a private temp dir; the bytes are read
    back and returned for inline embedding. Every engine gate failure surfaces with
    the gate id in the raised message.
    """
    assert_embeddable(str(spec.job.get("classification", "public")), doc_tier, figure_id=spec.id)
    available, why = engine_available()
    if not available:
        raise EChartsRenderError(
            f'figure "{spec.id}" cannot render: {why}. tools/visual-engine is the '
            "canonical chart renderer for this package (see ../../CAPABILITIES.json); "
            "install it (npm install in tools/visual-engine/) rather than hand-drawing the chart."
        )
    with tempfile.TemporaryDirectory(prefix="docgen-echarts-") as tmp:
        tmp_path = Path(tmp)
        job_path = tmp_path / "job.json"
        # Default this figure to the document theme unless the sidecar pinned one explicitly.
        # The SVG returned here is INLINED into the document, so it must inherit that document's
        # palette: docgen documents follow `prefers-color-scheme` and carry a runtime theme toggle,
        # and a chart with baked hex inks cannot follow either — every chart rendered light-on-dark
        # inside a light document. "document-theme" expresses its inks as CSS custom properties,
        # which is exactly how every native docgen figure already behaves.
        job = dict(spec.job)
        job.setdefault("theme", "document-theme")
        job_path.write_text(json.dumps(job), encoding="utf-8")
        result = subprocess.run(
            [
                engine_config.tool_path("node") or "node",
                str(_ENGINE_CLI),
                "render",
                str(job_path),
                "-o",
                str(tmp_path),
                "--formats",
                # json = the AI-only figure record (every mark, its value and connections, how to read it).
                "svg,json",
            ],
            capture_output=True,
            text=True,
            # Explicit: this bridge inspects returncode itself and turns a non-zero exit into an
            # EChartsRenderError with the engine's own stderr, which is far more useful than a bare
            # CalledProcessError. `check=False` states that on purpose (PLW1510).
            check=False,
            timeout=_RENDER_TIMEOUT_S,
            cwd=str(_ENGINE_ROOT),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[:500]
            raise EChartsRenderError(f'figure "{spec.id}": visual-engine render failed — {detail}')
        visual_id = str(spec.job.get("visual_id", "visual"))
        safe_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in visual_id)
        svg_path = tmp_path / f"{safe_id}.svg"
        if not svg_path.is_file():
            raise EChartsRenderError(
                f'figure "{spec.id}": engine reported success but wrote no SVG '
                f"(expected {svg_path.name}; NO_CHART jobs cannot be embedded as figures)"
            )
        figure_path = tmp_path / f"{safe_id}.figure.json"
        figure: dict[str, Any] = {}
        if figure_path.is_file():
            loaded = json.loads(figure_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                figure = loaded
        return svg_path.read_text(encoding="utf-8"), figure


def render(spec: EChartsFigureSpec, *, doc_tier: Tier = Tier.PUBLIC) -> str:
    """Render the figure's job and return just the SVG (the original entry point; see ``render_with_figure``)."""
    return render_with_figure(spec, doc_tier=doc_tier)[0]
