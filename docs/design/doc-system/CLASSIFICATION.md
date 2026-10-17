<!-- classification: public -->
<!-- title: CLASSIFICATION -->
# Classification — the metadata header this engine parses and enforces

**Status:** PUBLIC · normative · written 2026-08-20 to close `OG-13`.

**Why this file exists.** Eighteen code sites across six modules cite `CLASSIFICATION.md` as the
normative description of the document header — `classification.py`'s own module docstring opens with
it — and the file did not exist. That is a citation pointing at nothing, in the modules that decide
whether a document may be rendered or committed. This is the short, true version of what the code
already enforces; it invents nothing.

`OG-05` recorded the *source project's* `CLASSIFICATION.md` as deliberately not bundled, and it
still is not: that document governed a different tier vocabulary (`INTERNAL`, `GITHUB`,
`COMMERCIAL`) which this engine does not implement. This file is the engine's own, and the two rows
are no longer in contradiction.

## The metadata header

A doc-system document begins with a YAML front-matter fence — `---`, fields, `---` — parsed by
`tools/docgen/classification.py` `parse_header()`. The fence is matched by `_FRONT_MATTER_RE`.

**Required fields:** `id`, `title`, `classification`, `surface`, `audience`, `owner`, `status`,
`last_reviewed`. A missing or empty required field is a blocking `header` finding.
**Optional:** `variants` (defaults to an empty list).

`id` must carry an extractable `<PREFIX>-<NNN>` prefix, and that prefix must be registered in
`TAXONOMY.md` (RULEBOOK **L2**/**L5**). An unregistered prefix cannot satisfy the manifest gate.

## Tiers

Exactly three, and no others: **`public`**, **`confidential`**, **`secret`** (`models.py` `Tier`).

**A tier that cannot be parsed degrades to `secret`** — the most restrictive reading, never the most
permissive (`_coerce_tier()`). A document with no header at all therefore parses as `secret`, which
is correct for the render gate and deliberately *not* treated as a placement violation: an ordinary
header-less `README.md` is legitimate outside the vault.

**The legacy single-line form `<!-- classification: X -->` is not this header.** It is inherited
from the project this engine was extracted from. `staged_content_scanner` accepts it only with the
literal value `public` and blocks every other value rather than guessing, because an author who
writes `<!-- classification: secret -->` believing it protects them would otherwise be unprotected.

## Surface

`web`, `repo`, `both`, or `none` (RULEBOOK **L3**). **Non-public tiers are always `none`.** A public
document may not declare `none`, and a non-public document may not declare anything else — both
directions are checked by `validate_header()`; an unparseable surface degrades to `none`.

## Placement (RULEBOOK L14)

**A `confidential` or `secret` document may exist only under `docs/confidential/`.** Enforced at two
points, both on the bytes being recorded rather than on the working tree:

- `tools/hooks/pre-commit` → `staged_content_scanner` over the **git index**;
- `tools/hooks/pre-push` → `staged_content_scanner --tree` over **every commit in the pushed range**,
  because `git merge`, `git cherry-pick` and `git rebase` all create commits without `pre-commit`.

`docs/confidential/` is gitignored. `local_preview` for a non-public document refuses to write
outside it.

## What consults this file

`classification.py`, `adjudication.py`, `export_sanitizer.py`, `cli.py`, `doc_manifest.py`,
`hooks/staged_content_scanner.py`. It is **not** in `VERSION.json`'s `rulebook_files`: the hash gate
fails closed on a listed file that is missing, and a host project may legitimately override this
document. If a host project does lock it, it adds the path there and re-baselines under **L9**.
