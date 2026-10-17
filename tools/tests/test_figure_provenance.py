"""Counter-examples for the figure-provenance gate (`OG-63`, RULEBOOK L16).

L16 has always said a number with no resolvable ``DataSource`` fails the render. Until Phase 4 it
was enforced for two figure kinds out of eleven, and every other numeric spec declared
``data_sources`` with an empty default that nothing read — so the law was a convention everywhere
it was not a gate.

**The subject set is derived from the engine's own dispatch table and asserted non-empty**
(`LESSONS.md` L-37). A list of kinds copied into this file would stop covering a kind the moment
one was added, and would say nothing when it happened.
"""

from __future__ import annotations

import json
import unittest
from collections.abc import Mapping
from pathlib import Path

from tools.docgen import generator
from tools.docgen.models import BarItem, BarSpec, DataSource, Node, NodeType, VisualSpec

_ROOT = Path(__file__).resolve().parents[2]


def _bar(sources: list[DataSource]) -> Mapping[str, tuple[str, BarSpec]]:
    """A minimal data-carrying figure, built here rather than borrowed from the corpus.

    Returns a ``Mapping``, not a ``dict``: ``dict`` is invariant in its value type, so a
    ``dict[str, tuple[str, BarSpec]]`` cannot be passed where the figure-spec union is expected.
    ``check_figure_provenance`` takes a ``Mapping`` for the same reason — it only reads — and a
    cast here instead would be a way of not testing the signature.
    """
    return {
        "probe": (
            "bar",
            BarSpec(
                id="probe",
                title="t",
                caption="c",
                items=[BarItem(label="a", value=1.0)],
                data_sources=sources,
            ),
        )
    }


class DataSourcesIsAGateNotAConvention(unittest.TestCase):
    def test_data_sources_missing_on_a_numeric_figure_is_refused(self) -> None:
        findings = generator.check_figure_provenance(_bar([]))
        self.assertEqual(len(findings), 1, "an unsourced numeric figure was accepted")
        self.assertTrue(findings[0].blocking)
        self.assertIn("L16", findings[0].message)

    def test_data_sources_present_and_resolvable_is_accepted(self) -> None:
        """The accepted direction, so this proves a gate rather than a refusal."""
        self.assertEqual(generator.check_figure_provenance(_bar([DataSource("metric", "fs-x")])), [])
        self.assertEqual(
            generator.check_figure_provenance(_bar([DataSource("cited", "", url="https://e/x")])), []
        )

    def test_data_sources_that_name_nothing_are_refused(self) -> None:
        """The gate's NEW edge: the widest input that still gets through a non-empty-list check.

        `RULES.md` Rule 1's corollary. The first version asked only whether the list was non-empty,
        and a source with an empty ref satisfied it completely — worse than declaring none, because
        the figure then reads as attributed to everyone downstream.
        """
        for empty in ("", "   ", "\t"):
            with self.subTest(ref=repr(empty)):
                findings = generator.check_figure_provenance(_bar([DataSource("metric", empty)]))
                self.assertEqual(len(findings), 1, f"ref={empty!r} was accepted as a source")
                self.assertIn("name nothing", findings[0].message)

    def test_data_sources_are_not_demanded_of_structural_figures(self) -> None:
        """A flowchart's boxes are named, not measured. Demanding provenance would be theatre.

        Derived from the dispatch table: every kind NOT declared as data-carrying must be exempt,
        so adding a structural kind is covered without editing this test.
        """
        carrying = generator.data_carrying_kinds()
        structural = sorted(set(generator._FIGURE_KINDS) - carrying)
        self.assertTrue(structural, "every kind carries data, so this probe measured nothing")
        for kind in structural:
            with self.subTest(kind=kind):
                figures = {"probe": (kind, BarSpec(id="probe", title="t", caption="c", items=[]))}
                self.assertEqual(generator.check_figure_provenance(figures), [])

    def test_data_sources_cover_every_data_carrying_kind(self) -> None:
        """The gate is over the DERIVED set, not a list someone remembered to extend."""
        carrying = sorted(generator.data_carrying_kinds())
        self.assertTrue(carrying, "no kind is declared as data-carrying — the gate covers nothing")
        for kind in carrying:
            with self.subTest(kind=kind):
                figures = {
                    "probe": (
                        kind,
                        BarSpec(id="probe", title="t", caption="c", items=[BarItem("a", 1.0)]),
                    )
                }
                self.assertEqual(
                    len(generator.check_figure_provenance(figures)), 1,
                    f"kind {kind} is declared data-carrying but its unsourced figure was accepted",
                )

    def test_data_sources_are_declared_by_every_numeric_figure_in_this_repository(self) -> None:
        """The live corpus, derived: every tracked sidecar figure of a data-carrying kind.

        Asserted non-empty, so a corpus that lost its sidecars cannot pass this by having nothing
        to check.
        """
        carrying = generator.data_carrying_kinds()
        checked = 0
        for sidecar in sorted(_ROOT.glob("**/*_spec.json")):
            if "node_modules" in sidecar.parts or "archive" in sidecar.parts:
                continue
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            for fig in data if isinstance(data, list) else [data]:
                if fig.get("kind", "flowchart") not in carrying:
                    continue
                checked += 1
                sources = [
                    s for s in fig.get("data_sources", [])
                    if str(s.get("ref", "")).strip() or str(s.get("url", "")).strip()
                ]
                self.assertTrue(
                    sources,
                    f"{sidecar.relative_to(_ROOT)}: figure {fig.get('id')!r} "
                    f"(kind={fig.get('kind')}) renders numbers with no resolvable source",
                )
        self.assertTrue(checked, "no data-carrying figure was found, so this probe measured nothing")


class L16AppliesToQuantitiesInStructuralFigureText(unittest.TestCase):
    """`OG-194` — a structural figure that writes a quantity into its own labels answers to L16.

    Found by an adversarial verifier at the close of Phase 4: `figure_provenance` ran only over
    kinds declared `carries_data`, so a `flowchart` node labelled `Revenue: $4.2M ARR, 87% margin`
    with `data_sources: []` built clean and rendered verbatim. The gate did what it declared; the
    law was broader than the gate.
    """

    @staticmethod
    def _flow(label: str, sources: list[DataSource] | None = None) -> Mapping[str, tuple[str, VisualSpec]]:
        return {
            "probe": (
                "flowchart",
                VisualSpec(
                    id="probe", title="t", caption="c",
                    nodes=[Node(id="a", type=NodeType.PROCESS, label=label, x=0.0, y=0.0)],
                    edges=[], data_sources=list(sources or []),
                ),
            )
        }

    def test_data_sources_demanded_for_a_quantity_in_a_structural_label(self) -> None:
        """The exact reproduction the verifier used, and the two other quantity shapes."""
        for label in (
            "Revenue: $4.2M ARR, 87% margin",       # the original repro
            "Revenue: 4.2M USD ARR, 87 pct margin",  # the same facts, re-punctuated (`OG-196`)
            "Budget ₹500 crore allocated",           # a currency symbol outside the ASCII four
            "total 1.500,00 EUR collected",          # code trailing, European grouping
            "Margin 87 percent this year",           # the word form
            "Margin 87％ this year",                  # the full-width sign
            "Churn: 12.5% monthly",
            "Processed 4,200,000 rows",
        ):
            with self.subTest(label=label):
                findings = generator.check_figure_provenance(self._flow(label))
                self.assertEqual(len(findings), 1, f"{label!r} rendered unsourced")
                self.assertIn("L16", findings[0].message)
                # **Advisory, not blocking, and asserted so deliberately** (`OG-196`). The first
                # version blocked; an adversarial verifier then refused a build on
                # `Covered by Patent 10,123,456`. A heuristic over free prose that can refuse
                # legitimate work teaches authors to route around it. `cli.py` promotes advisories
                # to failures under `--strict`, so the strict posture is still reachable.
                self.assertFalse(
                    findings[0].blocking,
                    "the free-text quantity heuristic must not block a build on its own",
                )

    def test_data_sources_quantity_residual_is_what_the_register_says_it_is(self) -> None:
        """The stated residual, pinned. If one of these starts being detected, say so.

        `OG-196` records exactly what this heuristic does not see. A residual that is written down
        but never asserted drifts silently in both directions — it stops being true when the
        detector improves, and nobody notices when it gets worse.
        """
        for undetected in (
            "Revenue 4200000",              # a bare number that IS a measurement
            "latency 250ms at p99",         # unit-suffixed
            "throughput 4.2e6 events",      # scientific notation
            "Budget 500 crore INR",         # a scale WORD between the amount and its code
        ):
            with self.subTest(label=undetected):
                self.assertEqual(
                    generator.quantities_in(undetected), [],
                    f"{undetected!r} is now detected — update OG-196 and RULEBOOK L16's residual",
                )

    def test_data_sources_satisfy_a_structural_quantity_too(self) -> None:
        """The accepted direction — otherwise this is a refusal, not a gate."""
        self.assertEqual(
            generator.check_figure_provenance(
                self._flow("Revenue: $4.2M ARR", [DataSource("metric", "fin-2026-08")])
            ),
            [],
        )

    def test_data_sources_are_not_demanded_for_an_identifier_that_merely_contains_digits(self) -> None:
        """The gate's boundary, pinned. A figure's labels are full of integers that are NAMES.

        If any of these ever start firing the gate becomes untrustworthy, and an untrustworthy
        gate gets bypassed — which is worse than the hole this closed.
        """
        for label in (
            "Stage 2", "HTTP 200 OK", "engine v1.2.13", "RULEBOOK L16 gate", "Gate 3b",
            # Refused by the first version and reported as false positives (`OG-196`). A patent
            # number is citation-shaped, not a measurement, and blocking a build on one is how a
            # gate loses its authority.
            "Covered by Patent 10,123,456", "Ticket #12,345 resolved",
            "Path /items/42%2Fchild fetched", "host 192.168.1.1", "render at 16:9",
            "position in $AAPL", "shipped 2026-08-24",
        ):
            with self.subTest(label=label):
                self.assertEqual(
                    generator.check_figure_provenance(self._flow(label)), [],
                    f"{label!r} is an identifier, not a measurement, and was refused",
                )

    def test_data_sources_check_reaches_nested_and_non_label_prose(self) -> None:
        """The harvest walks the spec rather than naming label fields per kind.

        A caption or a node note is text a reader sees, so a quantity there is as unsourced as one
        in a label. Naming fields per kind would be a list that stops covering a kind the day one
        is added — and the six structural kinds do not share a shape.
        """
        nested = {
            "probe": (
                "flowchart",
                VisualSpec(
                    id="probe", title="t", caption="Throughput rose 41% this quarter",
                    nodes=[Node(id="a", type=NodeType.PROCESS, label="Ingest", x=0.0, y=0.0)],
                    edges=[],
                ),
            )
        }
        self.assertEqual(len(generator.check_figure_provenance(nested)), 1)

        note = {
            "probe": (
                "flowchart",
                VisualSpec(
                    id="probe", title="t", caption="c",
                    nodes=[Node(id="a", type=NodeType.PROCESS, label="Ingest", x=0.0, y=0.0,
                                note="sustained 4,000,000 events")],
                    edges=[],
                ),
            )
        }
        self.assertEqual(len(generator.check_figure_provenance(note)), 1)

    def test_data_sources_harvest_ignores_identifier_fields(self) -> None:
        """`id`/`kind`/`style` are machinery. A node id of `n1,000` must not read as a quantity."""
        self.assertEqual(generator._prose_of("x", field_name="id"), [])
        self.assertEqual(generator._prose_of("solid", field_name="style"), [])
        self.assertEqual(generator._prose_of("real prose"), ["real prose"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
