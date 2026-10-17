"""The guard registry — **add a guard with TWO edits in this file: the import, and ``GUARDS``.**

It said "one line to ``GUARDS``" (`OG-147`). That is the optimistic half of a two-part edit, and
`docs/design/ARCHITECTURE.md` §8 states the honest cost — the same shape as `OG-132`, a summary
contradicting the accurate table below it, here contradicting another artifact instead.

Order is deliberate and is not alphabetical:

* the **textual** guards run first because they are milliseconds and their findings are the ones a
  reader can act on immediately;
* ``rendered-output`` runs **last** because it builds documents into a temporary directory, which
  costs seconds. Eight guards' findings should already be on the screen before that starts.

Every name here matches a guard in `docs/framework/DOC_WRITING_DOCTRINE.md` §5 except ``register``,
which was earned by a live defect and says so in its own module docstring.
"""

from __future__ import annotations

from collections.abc import Callable

from tools.corpus_check.corpus import Corpus
from tools.corpus_check.guards import (
    built_claims,
    counts,
    cross_doc,
    crossrefs,
    identity,
    present_tense,
    register,
    rendered_output,
    stamps,
    symbols,
    test_refs,
)
from tools.corpus_check.model import GuardResult

GuardFn = Callable[[Corpus], GuardResult]

GUARDS: tuple[tuple[str, GuardFn], ...] = (
    # --- textual: fast, no subprocess ------------------------------------------------
    (register.GUARD, register.run),
    (crossrefs.GUARD, crossrefs.run),
    (symbols.GUARD, symbols.run),
    (test_refs.GUARD, test_refs.run),
    (counts.GUARD, counts.run),
    (identity.GUARD, identity.run),
    (cross_doc.GUARD, cross_doc.run),
    (present_tense.GUARD, present_tense.run),
    # --- git: one subprocess per stamped document -------------------------------------
    (stamps.GUARD, stamps.run),
    (built_claims.GUARD, built_claims.run),
    # --- builds documents: seconds ----------------------------------------------------
    (rendered_output.GUARD, rendered_output.run),
)


def guard_names() -> tuple[str, ...]:
    """Every registered guard name, in run order."""
    return tuple(name for name, _ in GUARDS)
