"""The authored half of the map — and the gate that keeps it honest.

WHY A SPEC EXISTS AT ALL, when `RULES.md` Rule 2 says a document never restates a fact code owns
=================================================================================================
Because three facts in a system map are **judgements**, not derivations, and no artifact in the
tree owns them:

* which **containers** a reader should think in — the tree says ``tools.docgen`` has 31 modules; it
  does not say that ``tools.docgen.hooks`` is a different thing from the renderer beside it;
* what each container is **for**, in one sentence;
* which **document owns** it.

Everything else — the modules, the edges, the depth, the gatekeepers, the registries, the surfaces
— is derived on every build from the artifact that owns it. So this file is deliberately small, and
the rule it lives under is the inverse of Rule 2's: **a judgement may be authored, but every fact it
touches is checked against the tree.** That check is :func:`verify`, and it is what stops the spec
becoming the hand-kept overview this whole layer exists to replace.

THE DRIFT CLASSES, AND WHY EACH ONE IS A REAL FAILURE
=====================================================
``blueprint verify`` exits 1 on any of these. None is cosmetic:

``spec-missing`` / ``spec-unparseable``
    The map claims a decomposition it cannot read. Fail loudly rather than fall back to "no
    containers", which would render a map that looks complete and asserts nothing.
``empty-package`` / ``empty-module``
    A container names something that no longer exists — a package renamed, a module deleted. The
    map would keep printing a container that maps to nothing.
``unassigned``
    A module the tree contains and no container claims. **This is the one that matters most**: it
    is what happens when a package is added and nobody updates the decomposition, and without it
    the map silently under-reports the system. There is deliberately **no catch-all container**,
    because a catch-all turns this finding off permanently.
``ambiguous``
    Two containers claim one module at the same specificity. Ownership that is not single is not
    ownership, and the exit condition of this phase is that an agent can name *the* owning document.
``document-missing``
    An owning document that does not resolve to **tracked** content. Untracked is as good as absent
    for a reader who just cloned the repository.
``duplicate-container-id``
    Two containers with one id. The register guard refuses exactly this shape in the corpus
    (`OG-74`, eleven duplicate primary keys); a spec is no different.

WHY LONGEST-PREFIX WINS
=======================
``tools.docgen.hooks`` is inside ``tools.docgen`` and is a different container. Resolving by
longest matching package prefix is what lets a container carve a sub-tree out of its parent without
either declaring the parent's whole module list or triggering ``ambiguous``. Ambiguity is then a
genuine tie at the same prefix length — two containers making the same claim — rather than the
ordinary nesting the decomposition is made of.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.blueprint.model import tracked_paths


class SpecError(Exception):
    """The spec could not be read at all. Never swallowed into an empty decomposition."""


@dataclass(frozen=True)
class Container:
    """One container: a judgement about how to think about a slice of the tree."""

    id: str
    name: str
    purpose: str
    document: str
    packages: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    # The RATCHET (`BUILD_PLAN.md` row 6). A commitment that this container will not get shallower,
    # authored because "how well must this be understood" is a judgement no artifact owns. It is
    # checked in both directions: below it is a regression, above it is slack that should be taken.
    depth_floor: int | None = None

    def claim_length(self, module_id: str) -> int:
        """How specifically this container claims ``module_id``; ``0`` means it does not.

        An exact ``modules`` entry outranks any package prefix, so a single module can always be
        pulled out of a package without restructuring the package that holds it.
        """
        if module_id in self.modules:
            return len(module_id) + 1_000  # exact beats every prefix, however long
        best = 0
        for pkg in self.packages:
            if module_id == pkg or module_id.startswith(pkg + "."):
                best = max(best, len(pkg))
        return best


@dataclass(frozen=True)
class Spec:
    """The whole authored decomposition."""

    name: str
    purpose: str
    document: str
    containers: tuple[Container, ...]
    path: str = ""


@dataclass(frozen=True)
class Drift:
    """One thing the spec asserts that the tree does not agree with."""

    kind: str
    subject: str
    detail: str

    def render(self) -> str:
        return f"{self.kind:<22} {self.subject}\n{'':<23}{self.detail}"


@dataclass(frozen=True)
class Assignment:
    """Who owns what, plus everything that could not be resolved."""

    owner: dict[str, str] = field(default_factory=dict)          # module id -> container id
    unassigned: tuple[str, ...] = ()
    ambiguous: dict[str, tuple[str, ...]] = field(default_factory=dict)
    empty_packages: tuple[tuple[str, str], ...] = ()             # (container id, package)
    empty_modules: tuple[tuple[str, str], ...] = ()              # (container id, module)


def spec_path(root: Path) -> Path:
    """Where the spec lives, honouring the same env-var > config > default chain as every path."""
    from tools.docgen import engine_config

    configured = engine_config.system_spec_path()
    # `engine_config` resolves against `host_root()`, which is the right answer for a normal run
    # and the wrong one inside a throwaway lab whose root is passed explicitly. Prefer the caller's
    # root when the two disagree and the caller's copy exists — a verifier working in a `git
    # archive` lab must be measuring the lab, not the checkout it was cut from.
    local = root / configured.name
    if configured != local and local.is_file():
        return local
    return configured


def load_spec(root: Path) -> Spec:
    """Read and shape-check the spec. Raises :class:`SpecError` rather than returning a hollow one."""
    path = spec_path(root)
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SpecError(f"spec-missing: {path} could not be read ({type(exc).__name__})") from exc
    except ValueError as exc:
        raise SpecError(f"spec-unparseable: {path} is not valid JSON ({exc})") from exc

    if not isinstance(raw, dict):
        raise SpecError(f"spec-unparseable: {path} is not a JSON object")
    system = raw.get("system")
    if not isinstance(system, dict):
        raise SpecError(f"spec-unparseable: {path} has no `system` object")
    rows = raw.get("containers")
    if not isinstance(rows, list) or not rows:
        raise SpecError(f"spec-unparseable: {path} declares no containers")

    containers: list[Container] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SpecError(f"spec-unparseable: containers[{i}] is not an object")
        missing = [k for k in ("id", "name", "purpose", "document") if not str(row.get(k, "")).strip()]
        if missing:
            raise SpecError(
                f"spec-unparseable: containers[{i}] "
                f"({row.get('id', '?')}) is missing {', '.join(missing)}"
            )
        containers.append(
            Container(
                id=str(row["id"]),
                name=str(row["name"]),
                purpose=str(row["purpose"]),
                document=str(row["document"]),
                packages=tuple(str(p) for p in row.get("packages", ())),
                modules=tuple(str(m) for m in row.get("modules", ())),
                # `isinstance(True, int)` is True in Python. The history reader excluded bools and
                # this did not, so `"depthFloor": true` was a live floor of 1 that the ratchet's
                # memory silently discarded — a two-step loosening on any floor-1 container, using
                # a value one reader honours and the other forgets. Both readers exclude it now.
                depth_floor=(
                    int(row["depthFloor"])
                    if isinstance(row.get("depthFloor"), int)
                    and not isinstance(row.get("depthFloor"), bool)
                    else None
                ),
            )
        )
    return Spec(
        name=str(system.get("name", "")),
        purpose=str(system.get("purpose", "")),
        document=str(system.get("document", "")),
        containers=tuple(containers),
        path=str(path),
    )


def assign(spec: Spec, module_ids: list[str]) -> Assignment:
    """Resolve every module to exactly one container, and name everything that did not resolve."""
    owner: dict[str, str] = {}
    unassigned: list[str] = []
    ambiguous: dict[str, tuple[str, ...]] = {}

    for module_id in module_ids:
        scored = [(c.claim_length(module_id), c.id) for c in spec.containers]
        scored = [(n, cid) for n, cid in scored if n > 0]
        if not scored:
            unassigned.append(module_id)
            continue
        best = max(n for n, _ in scored)
        winners = sorted(cid for n, cid in scored if n == best)
        if len(winners) > 1:
            ambiguous[module_id] = tuple(winners)
            continue
        owner[module_id] = winners[0]

    known = set(module_ids)
    empty_packages = tuple(
        (c.id, pkg)
        for c in spec.containers
        for pkg in c.packages
        if not any(m == pkg or m.startswith(pkg + ".") for m in known)
    )
    empty_modules = tuple(
        (c.id, m) for c in spec.containers for m in c.modules if m not in known
    )
    return Assignment(
        owner=owner,
        unassigned=tuple(sorted(unassigned)),
        ambiguous=ambiguous,
        empty_packages=empty_packages,
        empty_modules=empty_modules,
    )


def spec_drift(root: Path, spec: Spec, assignment: Assignment) -> list[Drift]:
    """Every disagreement between the authored spec and the tree, as a flat, printable list."""
    drift: list[Drift] = []

    seen: dict[str, int] = {}
    for c in spec.containers:
        seen[c.id] = seen.get(c.id, 0) + 1
    for cid, n in sorted(seen.items()):
        if n > 1:
            drift.append(Drift("duplicate-container-id", cid, f"declared {n} times"))

    for cid, pkg in assignment.empty_packages:
        drift.append(Drift("empty-package", f"{cid}: {pkg}", "no module in the tree matches this package prefix"))
    for cid, mod in assignment.empty_modules:
        drift.append(Drift("empty-module", f"{cid}: {mod}", "no such module in the tree"))
    for mod in assignment.unassigned:
        drift.append(
            Drift(
                "unassigned",
                mod,
                "no container claims this module — add it to the decomposition, and note that "
                "there is deliberately no catch-all container to absorb it",
            )
        )
    for mod, winners in sorted(assignment.ambiguous.items()):
        drift.append(
            Drift("ambiguous", mod, f"claimed at equal specificity by {', '.join(winners)}")
        )

    # Owning documents must resolve to TRACKED content. `git ls-files <path>` answers exactly the
    # question a fresh clone asks, which `Path.is_file()` does not: an untracked file is present
    # for the author and absent for everybody else.
    for subject, doc in [("system", spec.document)] + [(c.id, c.document) for c in spec.containers]:
        if not doc:
            drift.append(Drift("document-missing", subject, "no owning document declared"))
        elif not tracked_paths(root, doc):
            drift.append(
                Drift("document-missing", f"{subject}: {doc}", "does not resolve to tracked content")
            )
    return drift
