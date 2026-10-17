"""Counter-examples for the Phase-5 blueprint layer — the acceptance set, falsified both ways.

WHAT THESE PROBES ARE FOR
=========================
`BUILD_PLAN.md` row 5's acceptance set was written before any of this code existed, and every line
of it is a command with an expected result. These are the probes those lines select.

**Every one falsifies in both directions.** Showing that ``verify`` is green on a clean tree proves
nothing on its own — a command that always exits 0 would pass that. So each drift class is planted
in a throwaway copy of the tree, asserted RED with the offending subject named, then removed and
asserted green again. That discipline is `HANDOFF.md` standing rule 2, and it is the reason this
project trusts any gate at all.

**Every subject set is DERIVED, never listed** (`LESSONS.md` L-37). Where a probe needs modules,
containers, guards or figure kinds, it takes them from the live model and asserts the set is
non-empty first — so a probe can never pass by measuring nothing, which is the failure mode that
broke three probes in Phase 4 at the exact moment the thing they measured improved.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

from tools.blueprint import depth as depth_mod
from tools.blueprint import gatekeepers as gate_mod
from tools.blueprint import index_db
from tools.blueprint import spec as spec_mod
from tools.blueprint import surfaces as surfaces_mod
from tools.blueprint.model import build_model
from tools.tests.lab import ROOT as _ROOT
from tools.tests.lab import LabCase


class _LabCase(LabCase):
    """Phase-5 probes share the one lab implementation (`tools/tests/lab.py`)."""

    lab_prefix = "bp5-lab-"

    def spec_path(self) -> Path:
        return self.lab / "system.spec.json"

    def read_spec(self) -> dict[str, Any]:
        doc: dict[str, Any] = json.loads(self.spec_path().read_text(encoding="utf-8"))
        return doc

    def write_spec(self, doc: dict[str, Any]) -> None:
        self.spec_path().write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def drift_kinds(self) -> list[str]:
        """Run the real resolver over the lab and return the drift classes it reports."""
        return [d.kind for d in self._drift()]

    def drift_subjects(self, kind: str) -> list[str]:
        return [d.subject for d in self._drift() if d.kind == kind]

    def _drift(self) -> list[spec_mod.Drift]:
        spec = spec_mod.load_spec(self.lab)
        model = build_model(self.lab)
        module_ids = [n["id"] for n in model["graph"]["nodes"]]
        return spec_mod.spec_drift(self.lab, spec, spec_mod.assign(spec, module_ids))


class BlueprintDriftIsRefusedInEveryClass(_LabCase):
    """A-2. Each way the spec can stop describing the tree, shown RED then restored to green.

    The green half is not decoration. A ``verify`` that exited 1 unconditionally would satisfy every
    red assertion here and be worthless; the restore-and-pass step is what proves the command
    discriminates.
    """

    def setUp(self) -> None:
        self._original = self.spec_path().read_text(encoding="utf-8")
        self.addCleanup(lambda: self.spec_path().write_text(self._original, encoding="utf-8"))

    def test_blueprint_drift_the_unmodified_lab_is_clean(self) -> None:
        """The positive control. Without it every probe below could pass on a broken resolver."""
        self.assertEqual(self.drift_kinds(), [], "the lab must start clean or nothing below means anything")

    def test_blueprint_drift_a_container_naming_a_package_that_does_not_exist_is_refused(self) -> None:
        doc = self.read_spec()
        doc["containers"][0]["packages"] = ["tools.no_such_package"]
        self.write_spec(doc)
        self.assertIn("empty-package", self.drift_kinds())

    def test_blueprint_drift_a_container_naming_a_module_that_does_not_exist_is_refused(self) -> None:
        doc = self.read_spec()
        doc["containers"][0].setdefault("modules", []).append("tools.not_a_real_module")
        self.write_spec(doc)
        subjects = self.drift_subjects("empty-module")
        self.assertTrue(any("tools.not_a_real_module" in s for s in subjects), subjects)

    def test_blueprint_drift_a_module_no_container_claims_is_refused(self) -> None:
        """The one that matters most: a package added and never put in the decomposition.

        There is deliberately no catch-all container, because a catch-all turns this finding off
        permanently — and this is the finding that keeps the map from silently under-reporting the
        system it describes.
        """
        doc = self.read_spec()
        victim = next(c for c in doc["containers"] if "tools.docgen" in c.get("packages", []))
        victim["packages"] = [p for p in victim["packages"] if p != "tools.docgen"]
        self.write_spec(doc)
        subjects = self.drift_subjects("unassigned")
        self.assertTrue(subjects, "removing a package must orphan its modules")
        self.assertTrue(any(s.startswith("tools.docgen") for s in subjects), subjects[:5])

    def test_blueprint_drift_a_module_two_containers_claim_at_equal_specificity_is_refused(self) -> None:
        doc = self.read_spec()
        doc["containers"].append({
            "id": "rival", "name": "Rival", "purpose": "claims what is already claimed",
            "packages": ["tools.docgen"], "document": "docs/CHARTER.md",
        })
        self.write_spec(doc)
        self.assertIn("ambiguous", self.drift_kinds())

    def test_blueprint_drift_nesting_is_not_mistaken_for_ambiguity(self) -> None:
        """The other side of the same rule, and the reason longest-prefix wins.

        ``tools.docgen.hooks`` sits inside ``tools.docgen`` and is a different container. If nesting
        registered as ambiguity the decomposition could not express the moat at all, so this asserts
        the ordinary shape stays clean while the tie above stays refused.
        """
        self.assertNotIn("ambiguous", self.drift_kinds())

    def test_blueprint_drift_an_owning_document_that_is_not_tracked_is_refused(self) -> None:
        doc = self.read_spec()
        doc["containers"][0]["document"] = "docs/design/NO_SUCH_DOCUMENT.md"
        self.write_spec(doc)
        self.assertIn("document-missing", self.drift_kinds())

    def test_blueprint_drift_an_untracked_file_does_not_count_as_an_owning_document(self) -> None:
        """Tracked, not merely present: an untracked file exists for its author and nobody else."""
        (self.lab / "docs" / "UNTRACKED.md").write_text("# untracked\n", encoding="utf-8")
        self.addCleanup(lambda: (self.lab / "docs" / "UNTRACKED.md").unlink(missing_ok=True))
        doc = self.read_spec()
        doc["containers"][0]["document"] = "docs/UNTRACKED.md"
        self.write_spec(doc)
        self.assertIn("document-missing", self.drift_kinds())

    def test_blueprint_drift_two_containers_with_one_id_are_refused(self) -> None:
        doc = self.read_spec()
        doc["containers"].append(dict(doc["containers"][0]))
        self.write_spec(doc)
        self.assertIn("duplicate-container-id", self.drift_kinds())

    def test_blueprint_drift_an_unreadable_spec_fails_loudly_rather_than_rendering_an_empty_map(self) -> None:
        """A map that silently reports 'no containers' looks complete and asserts nothing."""
        self.spec_path().write_text("{ this is not json", encoding="utf-8")
        with self.assertRaises(spec_mod.SpecError):
            spec_mod.load_spec(self.lab)

    def test_blueprint_drift_verify_exits_1_on_drift_and_0_when_it_is_removed(self) -> None:
        """End to end through the real command, both directions, in one test."""
        def run() -> int:
            return subprocess.run(
                (sys.executable, "-m", "tools.blueprint", "verify"),
                cwd=self.lab, capture_output=True, text=True, timeout=300,
                env={**_env(), "ENGINE_HOST_ROOT": str(self.lab)}, check=False,
            ).returncode

        # The lab is a fresh copy that also contains untracked-but-not-ignored files, so its
        # inherited `blueprint/` is legitimately stale on arrival — `verify` says so, correctly.
        # Build once to establish the green baseline this probe then breaks and restores.
        subprocess.run(
            (sys.executable, "-m", "tools.blueprint", "build"),
            cwd=self.lab, capture_output=True, text=True, timeout=300,
            env={**_env(), "ENGINE_HOST_ROOT": str(self.lab)}, check=True,
        )
        self.assertEqual(run(), 0, "the lab must verify clean before it is broken")
        doc = self.read_spec()
        doc["containers"][0]["document"] = "docs/NOPE.md"
        self.write_spec(doc)
        self.assertEqual(run(), 1, "verify must exit 1 on a broken owning-document reference")
        self.spec_path().write_text(self._original, encoding="utf-8")
        self.assertEqual(run(), 0, "verify must return to 0 once the drift is removed")


def _env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(_ROOT)
    return env


class ModuleOwnershipIsTotalAndSingle(_LabCase):
    """A-3. Every module is owned exactly once — asserted over the whole set, not a sample."""

    def test_ownership_covers_every_module_with_no_orphans(self) -> None:
        model = build_model(self.lab)
        module_ids = [n["id"] for n in model["graph"]["nodes"]]
        self.assertGreater(len(module_ids), 50, "derived subject set must not be empty (L-37)")
        ownership = model["ownership"]
        self.assertEqual(ownership["unassigned"], [], "every module must be claimed by a container")
        self.assertEqual(ownership["ambiguous"], {}, "no module may be claimed twice")
        self.assertEqual(
            sorted(ownership["owner"]), sorted(module_ids),
            "the ownership map must cover exactly the modules the graph contains",
        )

    def test_every_ownership_target_is_a_declared_container(self) -> None:
        model = build_model(self.lab)
        declared = {c["id"] for c in model["containers"]}
        owner = model["ownership"]["owner"]
        # Guard the subject set FIRST. `set() <= declared` is true, so without this the probe
        # passed on an empty ownership map — a verifier planted exactly that, and only one of the
        # three ownership probes fired.
        self.assertTrue(declared, "no containers declared")
        self.assertGreater(len(owner), 50, "derived subject set is empty (L-37)")
        undeclared = set(owner.values()) - declared
        self.assertFalse(
            undeclared,
            f"ownership targets not in the declared container set: {sorted(undeclared)}",
        )

    def test_ownership_every_module_resolves_to_an_owning_document(self) -> None:
        """The exit condition's *owning document* half, over the whole module set."""
        model = build_model(self.lab)
        doc_of = {c["id"]: c["document"] for c in model["containers"]}
        owner = model["ownership"]["owner"]
        # A comprehension over an empty dict yields an empty list, so this asserted nothing at all
        # on an empty map until the subject set was guarded.
        self.assertGreater(len(owner), 50, "derived subject set is empty (L-37)")
        missing = [m for m, c in owner.items() if not doc_of.get(c)]
        self.assertEqual(missing, [])


class DepthIsMeasuredFromEvidenceNotAsserted(_LabCase):
    """A-4. The C4 ladder of `BUILD_PLAN.md` D4, and the proof that it responds to evidence."""

    def _derive(self, root: Path) -> dict[str, Any]:
        depths: dict[str, Any] = build_model(root)["depth"]["modules"]
        return depths

    def test_every_module_carries_a_depth_and_a_level_name(self) -> None:
        depths = self._derive(self.lab)
        self.assertGreater(len(depths), 50)
        for module_id, rec in depths.items():
            self.assertIn(rec["level"], depth_mod.LEVELS, module_id)
            self.assertEqual(depth_mod.LEVELS[rec["depth"]], rec["level"], module_id)

    def test_depth_is_contiguous_so_it_reports_where_we_stopped(self) -> None:
        """A ladder is climbed, not sampled: every rung below the reported one must hold."""
        ladder = ["exists", "purpose", "enumerable", "gated", "pinned", "verified"]
        for module_id, rec in self._derive(self.lab).items():
            for key in ladder[: rec["depth"] + 1]:
                self.assertTrue(rec["evidence"][key], f"{module_id}: {key} must hold below its depth")
            if rec["stopped_because"]:
                self.assertFalse(rec["evidence"][rec["stopped_because"]], module_id)

    def test_removing_evidence_lowers_the_derived_depth(self) -> None:
        """The measurement, falsified: take a docstring away and the rung must fall.

        This is what separates a derived ladder from a field somebody writes. A module is chosen
        from the live model by its evidence rather than named here, so the probe cannot rot when the
        tree changes around it (L-37).
        """
        before = self._derive(self.lab)
        victim = next(
            (m for m, r in sorted(before.items()) if r["evidence"]["purpose"] and r["depth"] >= 2
             and (self.lab / (m.replace(".", "/") + ".py")).is_file()),
            None,
        )
        self.assertIsNotNone(victim, "no module with a docstring — derived subject set is empty")
        assert victim is not None
        path = self.lab / (victim.replace(".", "/") + ".py")
        original = path.read_text(encoding="utf-8")
        self.addCleanup(lambda: path.write_text(original, encoding="utf-8"))

        import ast as _ast

        tree = _ast.parse(original)
        doc_node = tree.body[0]
        stripped = original.split("\n")
        # Replace the docstring with a bare expression that parses but carries no purpose.
        end = getattr(doc_node, "end_lineno", 1)
        path.write_text("\n".join(["_ = None"] + stripped[end:]), encoding="utf-8")

        after = self._derive(self.lab)
        self.assertLess(
            after[victim]["depth"], before[victim]["depth"],
            f"{victim}: removing its docstring must lower its measured depth",
        )
        self.assertEqual(after[victim]["stopped_because"], "purpose")

    def test_depth_a_container_is_only_as_deep_as_its_shallowest_module(self) -> None:
        model = build_model(self.lab)
        depths = model["depth"]["modules"]
        owner = model["ownership"]["owner"]
        self.assertTrue(model["containers"])
        for container in model["containers"]:
            mods = [m for m, c in owner.items() if c == container["id"]]
            if not mods:
                continue
            self.assertEqual(
                container["depth"], min(depths[m]["depth"] for m in mods), container["id"]
            )


class GatekeepersAreDerivedFromTheGatesThemselves(_LabCase):
    """A-5. What will refuse me if I change this — derived, and shown to respond to change."""

    def test_the_gatekeeper_map_covers_every_module_and_is_not_empty(self) -> None:
        model = build_model(self.lab)
        module_ids = [n["id"] for n in model["graph"]["nodes"]]
        gates = model["gatekeepers"]
        self.assertEqual(sorted(gates), sorted(module_ids))
        guarded = [m for m, rec in gates.items() if rec["guarded_by"]]
        self.assertTrue(guarded, "no module has a gatekeeper — the derivation has stopped working")

    def test_gatekeeper_a_module_a_guard_imports_reports_that_guard(self) -> None:
        """Anchored on an EXECUTED IMPORT, and the subject is derived from the tree.

        The first version named `tools.lib.md_table` literally and rested on a **comment** — while
        its own docstring claimed to be derived and this file's header claims every subject set is.
        A verifier reworded that one comment, left all five real imports intact, and the probe
        failed. Both halves are fixed: the subject comes from the guard registry's own imports, and
        the relationship asserted is one the guard actually executes.
        """
        from tools.corpus_check.guards import GUARDS

        wanted: tuple[str, str] | None = None
        for name, fn in GUARDS:
            rel = getattr(fn, "__module__", "").replace(".", "/") + ".py"
            source = (self.lab / rel).read_text(encoding="utf-8", errors="replace")
            for imported in sorted(gate_mod.imported_modules(source)):
                if imported.startswith("tools.") and (
                    self.lab / (imported.replace(".", "/") + ".py")
                ).is_file():
                    wanted = (imported, f"guard:{name}")
                    break
            if wanted:
                break
        self.assertIsNotNone(wanted, "no registered guard imports a module — subject set is empty")
        assert wanted is not None
        module_id, guard_name = wanted
        gates = gate_mod.build(self.lab, [module_id])
        self.assertIn(
            guard_name, gates[module_id]["guarded_by"],
            f"{guard_name} imports and executes {module_id} but is not reported as guarding it",
        )

    def test_gatekeeper_a_gate_that_stops_naming_a_module_stops_claiming_to_guard_it(self) -> None:
        """The falsification: change the gate's source, and the derived set must change with it."""
        model = build_model(self.lab)
        gates = model["gatekeepers"]
        # A SPECIFIC victim — at least three dotted segments. The first version took the
        # alphabetically first guarded module, which is `tools`: a substring of every path in the
        # tree, so the edit mangled the whole file, and the replacement text `tools.nothing_at_all`
        # still CONTAINED `tools`, so the derivation correctly kept reporting a match. The probe
        # was wrong, not the code — and a probe whose subject is a substring of its own replacement
        # can never go red.
        victim = next(
            (m for m, rec in sorted(gates.items())
             if m.count(".") >= 2
             and any(g.startswith("guard:") for g in rec["guarded_by"])
             and (self.lab / (m.replace(".", "/") + ".py")).is_file()),
            None,
        )
        self.assertIsNotNone(victim, "derived subject set is empty")
        assert victim is not None
        guard_name = next(g for g in gates[victim]["guarded_by"] if g.startswith("guard:"))
        module_file = self.lab / f"tools/corpus_check/guards/{guard_name.split(':', 1)[1].replace('-', '_')}.py"
        if not module_file.is_file():
            self.skipTest(f"{guard_name} does not map to a file by name; covered by the probe above")
        original = module_file.read_text(encoding="utf-8")
        self.addCleanup(lambda: module_file.write_text(original, encoding="utf-8"))
        replacement_id, replacement_path = "qqq.absent.module", "qqq/absent/module.py"
        self.assertNotIn(victim, replacement_id, "the replacement must not contain the original")
        module_file.write_text(
            original
            .replace(victim.replace(".", "/") + ".py", replacement_path)
            .replace(victim, replacement_id),
            encoding="utf-8",
        )
        after = gate_mod.build(self.lab, [victim])
        self.assertNotIn(
            guard_name, after[victim]["guarded_by"],
            f"{guard_name} stopped naming {victim} but still claims to guard it",
        )

    def test_gatekeeper_the_emitted_gate_vocabulary_is_resolved_through_module_constants(self) -> None:
        """`OG-195`: a gate written as ``gate=GATE`` against a constant must not be invisible."""
        gates = gate_mod.build(self.lab, ["tools.docgen.identity"])
        self.assertIn("identity", gates["tools.docgen.identity"]["emits"])

    def test_gatekeeper_a_module_named_only_in_prose_does_not_manufacture_an_edge(self) -> None:
        """`OG-216` — a Phase-7 verifier added one comment to a check and an unrelated module gained
        a published `guarded_by`. A comment or a docstring is not a read; a real code reference is."""
        target, path = "tools.draft.gate", "tools/draft/gate.py"
        comment = "def check_x():\n    # merely mentions tools.draft.gate in passing\n    return True\n"
        docstring = 'def check_x():\n    """mentions tools.draft.gate"""\n    return True\n'
        shell = "# mentions tools.draft.gate\necho hi\n"
        # A `;#` is a real shell comment the first fix's `\\s#` strip missed — planted so this probe
        # does not share the blind spot a second verifier found in the shell path (`OG-216` round 2).
        shell_semicolon = "true;# mentions tools.draft.gate\necho hi\n"
        real = 'def check_x():\n    run(["python3", "-m", "tools.draft.gate"])\n'
        self.assertFalse(gate_mod._names_module(gate_mod._prose_free(comment, python=True), target, path, set()))
        self.assertFalse(gate_mod._names_module(gate_mod._prose_free(docstring, python=True), target, path, set()))
        self.assertFalse(gate_mod._names_module(gate_mod._prose_free(shell, python=False), target, path, set()))
        self.assertFalse(gate_mod._names_module(gate_mod._prose_free(shell_semicolon, python=False), target, path, set()))
        # The positive control: a real dotted-id reference in actual code still counts.
        self.assertTrue(gate_mod._names_module(gate_mod._prose_free(real, python=True), target, path, set()))

    def test_gatekeeper_a_subprocess_m_flag_in_prose_does_not_reach(self) -> None:
        """`OG-225` — route 3 (`python3 -m X`) read the RAW gate source, so a `-m tools.X` merely
        RECOUNTED in a comment or a docstring credited that command's whole import closure with a
        guard that never runs it. A verifier measured 36 such phantom edges. Route 3 now reads the
        prose-free source, like the other text routes — this pins that composition directly."""
        prose = ('def check():\n'
                 '    # once ran `python3 -m tools.docgen.cli` here\n'
                 '    """historical: -m tools.health was the culprit"""\n'
                 '    return True\n')
        self.assertEqual(
            gate_mod._SUBPROCESS_RE.findall(gate_mod._prose_free(prose, python=True)), [],
            "a `-m module` living only in a comment or docstring must not be seen by route 3",
        )
        # Positive control: a real `-m` invocation in executed code IS still seen.
        real = 'def check():\n    run(["python3", "-m", "tools.docgen.cli"])\n'
        self.assertIn(
            "tools.docgen.cli", gate_mod._SUBPROCESS_RE.findall(gate_mod._prose_free(real, python=True)),
        )

    def test_gatekeeper_the_real_moat_modules_keep_their_enforcing_gates(self) -> None:
        """The prose-stripping must not drop a REAL edge: the moat modules are guarded by the hooks
        and SUITE-03 through imports and `-m` invocations, not comments, so they must survive."""
        gates = gate_mod.build(_ROOT, ["tools.docgen.hooks.materialise",
                                       "tools.docgen.hooks.staged_content_scanner"])
        for mod in ("tools.docgen.hooks.materialise", "tools.docgen.hooks.staged_content_scanner"):
            guarded = gates[mod]["guarded_by"]
            self.assertIn("hook:pre-push", guarded, f"{mod} lost its real pre-push gatekeeper")
            self.assertIn("hook:pre-commit", guarded, f"{mod} lost its real pre-commit gatekeeper")


class TheSixSurfacesAreDerivedFromTheirOwners(_LabCase):
    """A-6. Each surface cross-checked against the artifact that owns it, never against a copy."""

    def test_surfaces_all_of_them_report_rows(self) -> None:
        s = surfaces_mod.build(self.lab)
        # `environment` was absent from this list, which is part of why it could exist in the model
        # and never be rendered at all.
        for name in ("schemas", "configuration", "environment", "cli", "guards",
                     "figure_kinds", "health_checks"):
            self.assertTrue(s[name], f"surface {name!r} is empty — it would answer nothing")

    def test_surfaces_every_surface_is_rendered_not_just_modelled(self) -> None:
        """**The probe that would have caught the second CRITICAL.**

        The `environment` surface was derived correctly into `SYSTEM.json` and never rendered into
        `SURFACES.md` — so the finding it existed to close (`ENGINE_CONFIG_PATH` undiscoverable)
        was still open for the document that calls itself the lookup table. Modelled is not
        published.
        """
        from tools.blueprint.render import render_surfaces

        model = build_model(self.lab)
        rendered = render_surfaces(model)
        for name, payload in model["surfaces"].items():
            if not isinstance(payload, list) or not payload:
                continue
            first = payload[0]
            key = str(
                first.get("id") or first.get("guard") or first.get("kind")
                or first.get("invocation") or first.get("env_var") or first.get("path")
                or first.get("key") or ""
            )
            self.assertTrue(key, f"cannot key surface {name!r} for the render check")
            self.assertIn(
                key, rendered,
                f"surface {name!r} is in the model but nothing from it reaches SURFACES.md",
            )

    def test_surfaces_the_guard_cost_heading_agrees_with_its_own_list(self) -> None:
        """A heading that counts differently from the list beneath it is the `OG-132` shape."""
        from tools.blueprint.render import render_surfaces

        rendered = render_surfaces(build_model(self.lab))
        steps = len(surfaces_mod.guard_contract()["to_register"])
        words = ("zero", "one", "two", "three", "four", "five")
        self.assertIn(f"costs {words[steps]} edit", rendered)

    def test_surfaces_every_published_environment_variable_names_a_reader(self) -> None:
        """A documented control that does not exist is the defect this surface exists to remove.

        Every row must name a reader, and a config-section reader must be one a resolver actually
        routes through `envVar`. **Whether a code reader truly READS the variable rather than merely
        naming it is NOT checked here by re-running the derivation** — that was circular (`OG-215`),
        and the derivation's own probe cannot see the derivation's own blind spot. The method is
        proven instead by `SurfacesEnvDerivationIsStructuralNotTextual`, which plants a docstring
        mention, a JS template literal and a constant-name read and asserts each is handled; and the
        specific real-tree defects are pinned in `test_surfaces_env_derivation_real_tree_defects`.
        """
        rows = surfaces_mod.environment(self.lab)
        self.assertTrue(rows, "derived subject set is empty")
        honoured = surfaces_mod._envvar_sections(self.lab)
        for row in rows:
            readers = row.get("read_by", [])
            self.assertTrue(readers, f"{row['env_var']} names no reader")
            for reader in readers:
                if reader.startswith("engine.config.json"):
                    section = reader.split("(", 1)[1].split(".", 1)[0]
                    self.assertIn(
                        section, honoured,
                        f"{row['env_var']} is declared in {section}, which never consults an envVar",
                    )

    def test_surfaces_env_derivation_real_tree_defects(self) -> None:
        """The three defects a Phase-7 verifier measured on the REAL tree, pinned closed (`OG-215`)."""
        env = {r["env_var"]: r["read_by"] for r in surfaces_mod.environment(_ROOT)}
        # A JS module constant used in a template literal is not an env override — it changed
        # nothing when set, and was published because a shell pattern matched `v${ENGINE_VERSION}`.
        self.assertNotIn("ENGINE_VERSION", env)
        # The primary resolver reads this through a module CONSTANT; the literal-scanning version
        # missed it, so "the one to know" named neither resolver.
        self.assertIn("tools/docgen/engine_config.py", env.get("ENGINE_CONFIG_PATH", []))
        self.assertIn("tools/lib/engine-config.mjs", env.get("ENGINE_CONFIG_PATH", []))
        # A docstring quoting a past attack is not a read (L-24).
        self.assertNotIn(
            "tools/docgen/hooks/staged_content_scanner.py",
            env.get("ENGINE_CONFIDENTIAL_DIR", []),
        )

    def test_surfaces_schemas_cover_every_tracked_schema_in_the_tree(self) -> None:
        """Derived scope, not a pinned directory.

        The first version globbed the SAME hardcoded ``tools/docgen/schemas`` the surface read, so
        it could not see that four real schemas under ``tools/visual-engine/`` were missing. A probe
        that shares its subject's blind spot is not a probe. The subject set now comes from git.
        """
        rows = surfaces_mod.schemas(self.lab)
        tracked = subprocess.run(
            ("git", "-C", str(self.lab), "ls-files", "*.schema.json", "*/*.schema.json"),
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.split()
        self.assertTrue(tracked, "derived subject set is empty")
        self.assertEqual(sorted(r["path"] for r in rows), sorted(tracked))
        self.assertTrue(
            any(r["required"] and r["required_from"].startswith("$defs") for r in rows),
            "a schema whose row shape lives in $defs must still report its required fields",
        )

    def test_surfaces_health_checks_match_the_registry_exactly(self) -> None:
        from tools.health.checks import CHECKS

        rows = surfaces_mod.health_checks(self.lab)
        self.assertEqual(len(rows), len(CHECKS))
        self.assertTrue(all(r["asserts"] for r in rows), "every check must say what it asserts")

    def test_surfaces_guards_match_the_registry_in_run_order(self) -> None:
        from tools.corpus_check.guards import GUARDS

        rows = surfaces_mod.guards(self.lab)
        self.assertEqual([r["guard"] for r in rows], [name for name, _ in GUARDS])

    def test_surfaces_figure_kinds_match_the_dispatch_table(self) -> None:
        from tools.docgen.generator import _FIGURE_KINDS, data_carrying_kinds

        rows = surfaces_mod.figure_kinds()
        self.assertEqual(sorted(r["kind"] for r in rows), sorted(_FIGURE_KINDS))
        self.assertEqual(
            {r["kind"] for r in rows if r["carries_data"]}, set(data_carrying_kinds())
        )

    def test_surfaces_cli_reports_nested_subcommands_under_their_parent(self) -> None:
        """The defect the first version shipped: ``archive cut`` flattened to a ``cut`` that does
        not exist, and an unassigned ``add_parser`` producing no commands at all."""
        rows = surfaces_mod.cli(self.lab)
        docgen = next(r for r in rows if r["module"].endswith("docgen/cli.py"))
        names = {c["command"] for c in docgen["commands"]}
        self.assertIn("archive cut", names)
        self.assertNotIn("cut", names)
        blueprint = next(r for r in rows if r["module"].endswith("blueprint/cli.py"))
        self.assertTrue(
            {"build", "check", "verify"} <= {c["command"] for c in blueprint["commands"]},
            "unassigned add_parser() calls must still be reported",
        )

    def test_surfaces_configuration_names_only_env_vars_something_reads(self) -> None:
        """The claim is that the surface answers *which variable controls Y* — truthfully.

        The first version asserted only that each row's value ``startswith("ENGINE_")``, which a
        synthesised name satisfies perfectly. Two independent verifiers then measured 8 of 26 rows
        naming a variable that changes nothing when set. The probe now requires every published
        variable to be one some file actually reads.
        """
        live = {row["env_var"] for row in surfaces_mod.environment(self.lab)}
        self.assertTrue(live, "derived subject set is empty")
        for row in surfaces_mod.configuration(self.lab):
            if row.get("env_var"):
                self.assertIn(
                    row["env_var"], live,
                    f"{row['section']}.{row['key']} publishes {row['env_var']}, which nothing reads",
                )

    def test_surfaces_environment_includes_the_override_that_replaces_everything(self) -> None:
        """`ENGINE_CONFIG_PATH` replaces the entire configuration file and was absent entirely."""
        live = {row["env_var"] for row in surfaces_mod.environment(self.lab)}
        self.assertIn("ENGINE_CONFIG_PATH", live)
        for name in ("ENGINE_SKIP_PRECOMMIT", "ENGINE_SKIP_PREPUSH", "ENGINE_SECRET_SCAN"):
            self.assertIn(name, live, f"{name} gates the moat and must be discoverable")

    def test_surfaces_every_published_invocation_actually_runs(self) -> None:
        """**The probe that would have caught the CRITICAL.**

        The surface published ``python3 -m tools.project_index``, which cannot run — that package
        has no ``__main__.py``. Nothing asserted that a published command exists, so a map whose
        entire job is to save a reader from the tree sent them at a command that errors. Every
        invocation now has its ``--help`` executed.
        """
        rows = surfaces_mod.cli(self.lab)
        self.assertTrue(rows, "derived subject set is empty")
        for entry in rows:
            argv = entry["invocation"].split()[2:]  # drop "python3 -m"
            proc = subprocess.run(
                (sys.executable, "-m", *argv, "--help"),
                cwd=self.lab, capture_output=True, text=True, timeout=120,
                env={**_env(), "ENGINE_HOST_ROOT": str(self.lab)}, check=False,
            )
            self.assertEqual(
                proc.returncode, 0,
                f"{entry['invocation']} is published but does not run:\n{proc.stderr[-400:]}",
            )

    def test_surfaces_cli_covers_every_module_that_builds_a_parser(self) -> None:
        """The entry-point SET must be derived, not a list somebody maintains.

        A verifier added a real, runnable module with a parser and it never appeared in a fresh
        build, because the set was a literal dict. The subject set now comes from the tree.
        """
        published = {r["module"] for r in surfaces_mod.cli(self.lab)}
        tracked = subprocess.run(
            ("git", "-C", str(self.lab), "ls-files", "*.py", "*/*.py", "*/*/*.py", "*/*/*/*.py"),
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.split()
        # An INDEPENDENT detector, deliberately not `surfaces._constructs_parser`. The first
        # version called the subject's own function, so when that function could not see
        # `from argparse import ArgumentParser as AP` the probe could not see it either — which is
        # exactly the flaw its sibling schema probe's docstring names: a probe that shares its
        # subject's blind spot is not a probe. Written differently on purpose: this one asks
        # whether the module imports `argparse` AND calls something bound from it.
        def _builds_parser(source: str) -> bool:
            try:
                tree = ast.parse(source)
            except (SyntaxError, ValueError):
                return False
            names: set[str] = set()
            uses_module = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    uses_module |= any(a.name == "argparse" for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module == "argparse":
                    names.update(a.asname or a.name for a in node.names)
            if not names and not uses_module:
                return False
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in names:
                    return True
                if isinstance(fn, ast.Attribute) and fn.attr == "ArgumentParser" and uses_module:
                    return True
            return False

        builders = {
            rel for rel in tracked
            if not rel.startswith("tools/tests/")
            and _builds_parser((self.lab / rel).read_text(encoding="utf-8", errors="replace"))
        }
        self.assertTrue(builders, "derived subject set is empty")
        self.assertEqual(
            builders - published, set(),
            "these modules build an argparse parser and are absent from the CLI surface",
        )


class SurfacesEnvDerivationIsStructuralNotTextual(unittest.TestCase):
    """`OG-215` — the env-read derivation must see a READ in the file's own language, not a mention.

    A Phase-7 verifier refuted the previous derivation three ways, all one class (`OG-166`/L-24, the
    scan-text-not-structure defect): a JS constant published as a phantom because a shell pattern
    matched a template literal, a docstring mention counted as a read, and a real read through a
    module constant missed entirely. These plant each shape directly against the language helpers, so
    the test cannot share the derivation's blind spot the way the old circular liveness probe did.
    """

    def test_a_python_docstring_mention_is_not_a_read(self) -> None:
        src = '"""A past attack: ENGINE_DOCSTRING_ONLY=docs was refused."""\nx = 1\n'
        self.assertNotIn("ENGINE_DOCSTRING_ONLY", surfaces_mod._py_env_reads(src))

    def test_a_python_literal_read_is_seen(self) -> None:
        src = 'import os\nv = os.environ.get("ENGINE_REALPY")\n'
        self.assertIn("ENGINE_REALPY", surfaces_mod._py_env_reads(src))

    def test_a_python_constant_name_read_is_resolved(self) -> None:
        src = 'import os\n_V = "ENGINE_VIACONST"\nv = os.environ.get(_V)\n'
        self.assertIn("ENGINE_VIACONST", surfaces_mod._py_env_reads(src))

    def test_a_python_membership_read_is_seen(self) -> None:
        src = 'import os\nif "ENGINE_MEMBER" in os.environ:\n    pass\n'
        self.assertIn("ENGINE_MEMBER", surfaces_mod._py_env_reads(src))

    def test_a_js_template_literal_is_not_a_read(self) -> None:
        src = "export const ENGINE_VERSION = pkg.version;\nconst s = `v${ENGINE_VERSION}`;\n"
        self.assertNotIn("ENGINE_VERSION", surfaces_mod._js_env_reads(src))

    def test_a_js_process_env_read_is_seen(self) -> None:
        self.assertIn("ENGINE_REALJS", surfaces_mod._js_env_reads("const x = process.env.ENGINE_REALJS;\n"))

    def test_a_js_const_alias_read_is_resolved(self) -> None:
        src = "const CP = 'ENGINE_VIACONST_JS';\nconst x = process.env[CP];\n"
        self.assertIn("ENGINE_VIACONST_JS", surfaces_mod._js_env_reads(src))

    def test_a_shell_comment_mention_is_not_a_read(self) -> None:
        self.assertNotIn(
            "ENGINE_COMMENTED",
            surfaces_mod._sh_env_reads("# note: $ENGINE_COMMENTED is legacy\necho hi\n"),
        )

    def test_a_shell_read_is_seen(self) -> None:
        self.assertIn("ENGINE_REALSH", surfaces_mod._sh_env_reads('echo "${ENGINE_REALSH}"\n'))

    # --- OG-215 round 2: a second verifier found the first fix made only the PYTHON path structural
    # and left JS + shell scanning raw text, and that these probes shared that blind spot (they never
    # planted a JS comment/string or a shell `;#`). Each of the following plants one of those exact
    # shapes so the probe cannot be green while the class is open.

    def test_a_js_line_comment_mention_is_not_a_read(self) -> None:
        self.assertNotIn(
            "ENGINE_JSLINE",
            surfaces_mod._js_env_reads("const x = 1; // reads process.env.ENGINE_JSLINE one day\n"),
        )

    def test_a_js_block_comment_mention_is_not_a_read(self) -> None:
        self.assertNotIn(
            "ENGINE_JSBLOCK",
            surfaces_mod._js_env_reads("/* process.env.ENGINE_JSBLOCK is legacy */\nconst y = 2;\n"),
        )

    def test_a_js_string_literal_mention_is_not_a_read(self) -> None:
        self.assertNotIn(
            "ENGINE_JSSTRING",
            surfaces_mod._js_env_reads('const doc = "set process.env.ENGINE_JSSTRING to configure";\n'),
        )

    def test_a_js_bracket_string_read_is_seen(self) -> None:
        # The key literal IS the read, so comment/string stripping must capture it BEFORE blanking
        # strings — the fix's most fragile edge.
        self.assertIn(
            "ENGINE_BRACKETJS",
            surfaces_mod._js_env_reads('const v = process.env["ENGINE_BRACKETJS"];\n'),
        )

    def test_a_shell_semicolon_comment_mention_is_not_a_read(self) -> None:
        # `;#` is a real shell comment; the old strip only saw a whitespace-preceded ` #`.
        self.assertNotIn(
            "ENGINE_SEMICOLON",
            surfaces_mod._sh_env_reads("true;# legacy $ENGINE_SEMICOLON note\n"),
        )

    def test_a_python_environ_write_is_not_a_read(self) -> None:
        # `os.environ["X"] = v` is a Subscript in Store context — a WRITE, credited as a read before
        # the `ctx is ast.Load` fix, which put a test in §6 as a "reader" of variables it only sets.
        self.assertNotIn(
            "ENGINE_WRITTEN",
            surfaces_mod._py_env_reads('import os\nos.environ["ENGINE_WRITTEN"] = "x"\n'),
        )

    def test_a_python_getenv_read_is_seen(self) -> None:
        self.assertIn(
            "ENGINE_GETENV",
            surfaces_mod._py_env_reads('import os\nv = os.getenv("ENGINE_GETENV")\n'),
        )

    # --- OG-224 round 3: a verifier refuted the round-2 JS stripper in both directions because
    # comments were stripped BEFORE strings, so a `//` inside a URL string opened a phantom comment.
    # These plant the string-vs-comment shapes the round-2 probes never did (they only planted a bare
    # `//` comment, a bare string, and a bracket read — never a string CONTAINING a comment opener).

    def test_a_js_read_survives_a_url_string_on_the_same_line(self) -> None:
        # 1a: the `//` in the URL must not comment out the real read after it.
        self.assertIn(
            "ENGINE_TOKEN",
            surfaces_mod._js_env_reads(
                'const url = "https://api.example.com"; const key = process.env.ENGINE_TOKEN;\n'),
        )

    def test_a_js_name_only_inside_a_string_is_not_a_read(self) -> None:
        # 1c: `process.env.X` written as string CONTENT is not a read, even after another URL string.
        self.assertNotIn(
            "ENGINE_PHANTOM",
            surfaces_mod._js_env_reads('"see https://docs"; "process.env.ENGINE_PHANTOM x";\n'),
        )

    def test_a_js_read_survives_glob_strings_that_look_like_block_comments(self) -> None:
        # 1e: `"tools/*"` … `"*/x"` must not open a `/* */` comment across the real read between them.
        self.assertIn(
            "ENGINE_CACHE",
            surfaces_mod._js_env_reads(
                'const a = "tools/*"; const c = process.env.ENGINE_CACHE; const b = "*/node_modules";\n'),
        )

    def test_a_js_bracket_read_survives_a_url_string(self) -> None:
        # 1f: the bracket-key read must be captured even when a prior string contains `//`.
        self.assertIn(
            "ENGINE_BRK",
            surfaces_mod._js_env_reads(
                'const u = "https://x.example"; const v = process.env["ENGINE_BRK"];\n'),
        )


class TheSqliteIndexIsDerivedRebuildableAndRefusesToBeEmpty(_LabCase):
    """A-8. `BUILD_PLAN.md` D1, with the empty-result refusal that `RULES.md` Rule 6 demands."""

    def test_sqlite_index_builds_every_table_non_empty(self) -> None:
        model = build_model(self.lab)
        counts = index_db.build(self.lab, model)
        for table, n in counts.items():
            if table == "open_work":
                continue
            self.assertGreater(n, 0, f"{table} came out empty")

    def test_sqlite_index_refuses_a_model_with_no_modules(self) -> None:
        """A builder that produces an empty result must exit non-zero — an empty map is a lie."""
        model = build_model(self.lab)
        model["graph"]["nodes"] = []
        with self.assertRaises(index_db.EmptyIndexError):
            index_db.build(self.lab, model)

    def test_sqlite_index_answers_the_canonical_joins(self) -> None:
        index_db.build(self.lab, build_model(self.lab))
        for question in index_db.QUERIES:
            sql, _rows, cols = index_db.query(self.lab, question)
            self.assertTrue(sql)
            self.assertTrue(cols, question)

    def test_sqlite_index_full_text_search_finds_a_document_by_its_content(self) -> None:
        index_db.build(self.lab, build_model(self.lab))
        hits = index_db.search(self.lab, "charter")
        self.assertTrue(hits, "FTS5 returned nothing for a term the corpus certainly contains")

    def test_sqlite_index_is_gitignored_so_it_can_never_become_authoritative(self) -> None:
        proc = subprocess.run(
            ("git", "-C", str(self.lab), "check-ignore", "-q", ".blueprint"),
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 0, ".blueprint must be gitignored (BUILD_PLAN.md D1)")


class TheElkLayoutSatisfiesDocgensOwnPlacementRules(_LabCase):
    """A-7. What ELK is responsible for, asserted; what the renderer cannot do, named."""

    def test_layout_placement_is_clean_or_skipped_with_its_cause(self) -> None:
        from tools.blueprint import layout as layout_mod

        model = build_model(self.lab)
        outcome = layout_mod.compute(model)
        if outcome.skipped:
            self.assertTrue(outcome.reason, "a SKIP must name its cause, never be silent (L-25)")
            self.skipTest(f"layout unavailable: {outcome.reason}")
        self.assertTrue(outcome.ok, outcome.reason)
        assert outcome.layout is not None
        report = layout_mod.collision_report(outcome.layout)
        self.assertEqual(
            report["node_placement"], [],
            "ELK's job is placement: docgen must find no overlap and no gap violation",
        )

    def test_layout_is_deterministic_so_the_committed_copy_can_be_checked(self) -> None:
        from tools.blueprint import layout as layout_mod

        model = build_model(self.lab)
        first = layout_mod.compute(model)
        if first.skipped:
            self.skipTest(f"layout unavailable: {first.reason}")
        second = layout_mod.compute(model)
        self.assertEqual(first.layout, second.layout, "a layout that cannot be re-derived is not derived")

    def test_disconnected_packages_keep_the_gap_docgen_requires(self) -> None:
        """`OG-246`. ELK spaces DISCONNECTED subgraphs by a different option than adjacent nodes.

        ``elk.spacing.nodeNode`` governs neighbours inside one component; nodes with no edge
        between them are separate COMPONENTS, and ELK lays those out at ``componentComponent``,
        whose default is 20 px — below the 72 px docgen derives from the node box and refuses. So
        ``compute`` returned ``ok=True`` and ``collision_report`` then found four placement
        violations in the same layout: ELK said yes, the renderer said no, and nothing in between
        said why.

        This repository's own package graph is fully connected, which is why no self-check ever saw
        it. It surfaced on the first foreign host with a sparse import graph — the case the
        blueprint exists to serve.
        """
        from tools.blueprint import layout as layout_mod

        if not layout_mod.available()[0]:
            self.skipTest("node/elkjs unavailable")
        # Three packages, zero edges: three components, and nothing else to explain a gap.
        model = {"graph": {"nodes": [{"id": name, "package": name}
                                     for name in ("alpha", "beta", "gamma")],
                           "edges": []}}
        outcome = layout_mod.compute(model)
        self.assertTrue(outcome.ok, outcome.reason)
        assert outcome.layout is not None
        self.assertEqual(
            layout_mod.collision_report(outcome.layout)["node_placement"], [],
            "a layout may not pass ELK and then be refused by the renderer that consumes it",
        )

    def test_layout_refuses_an_empty_graph(self) -> None:
        from tools.blueprint import layout as layout_mod

        if not layout_mod.available()[0]:
            self.skipTest("node/elkjs unavailable")
        model = build_model(self.lab)
        model["graph"]["nodes"] = []
        outcome = layout_mod.compute(model)
        self.assertFalse(outcome.ok)
        self.assertFalse(outcome.skipped, "an empty graph is a real failure, not an environment fact")


class TheCommittedPhase5ArtifactsAreCurrent(unittest.TestCase):
    """A-1 and A-7's ratchet, against the REAL tree rather than a lab.

    `RULES.md` Rule 6: a derived artifact needs a staleness ratchet run by the retained suite, so a
    stale copy fails the push. **The ratchet — not the artifact — is what makes it trustworthy.**
    This lives beside the existing ``blueprint check`` ratchet rather than in a new health check,
    because two enforcers of one rule is the defect this engine exists to catch, not a fix for it.
    """

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, "-m", "tools.blueprint", *args),
            cwd=_ROOT, capture_output=True, text=True, timeout=600, env=_env(), check=False,
        )

    def test_the_model_is_identical_across_SEPARATE_PROCESSES(self) -> None:
        """In-process determinism is not enough, and this is not hypothetical.

        `build` and `verify` are separate processes. An import-closure that memoised across nodes
        while sharing one cycle-guard made a cached answer depend on the order a set was iterated,
        and set order varies with `PYTHONHASHSEED` — so `blueprint build` immediately followed by
        `blueprint verify` reported the freshly written map as STALE. The existing determinism probe
        covered the ELK layout and not the model, so nothing caught it.
        """
        # Hash the RENDERED BYTES, not a normalised dump of the model. `SYSTEM.json` is written
        # with `indent=2` and NO `sort_keys`, and the other five files go through text renderers —
        # so a probe hashing `json.dumps(model, sort_keys=True)` could not see key-order or
        # renderer-level nondeterminism in the very artifacts it exists to protect. These are the
        # bytes that get committed and compared.
        script = (
            "import hashlib;"
            "from pathlib import Path;"
            "from tools.blueprint.model import build_model;"
            "from tools.blueprint.render import blueprint_files;"
            "f = blueprint_files(build_model(Path('.').resolve()));"
            "print(hashlib.sha256(''.join(f[k] for k in sorted(f)).encode()).hexdigest())"
        )
        digests = set()
        for seed in ("0", "1", "12345"):
            proc = subprocess.run(
                (sys.executable, "-c", script), cwd=_ROOT, capture_output=True, text=True,
                timeout=600, env={**_env(), "PYTHONHASHSEED": seed}, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            digests.add(proc.stdout.strip())
        self.assertEqual(
            len(digests), 1,
            "the model differs between processes, so a committed map can never be verified",
        )

    def test_blueprint_verify_is_clean_on_the_committed_tree(self) -> None:
        proc = self._run("verify")
        self.assertEqual(
            proc.returncode, 0,
            "the system spec no longer describes the tree, or blueprint/ is stale:\n"
            + proc.stdout + proc.stderr,
        )

    def test_the_committed_elk_layout_is_current_or_honestly_skipped(self) -> None:
        proc = self._run("layout", "--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        if "SKIP:" in proc.stdout:
            # An environment fact, not a finding about the artifact (L-25). It must still SAY so.
            self.assertRegex(proc.stdout, r"SKIP: \S")


if __name__ == "__main__":
    unittest.main()
