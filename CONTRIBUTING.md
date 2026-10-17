# Contributing to Ultimate Engine

Thank you for helping. Ultimate Engine is a FreeXStudio product, released under the
[Apache License 2.0](LICENSE); by contributing you agree your contribution is licensed under the same
terms (Apache-2.0 §5). Be kind: see the [Code of Conduct](CODE_OF_CONDUCT.md).

## Set up

You need Python 3.11+ (with **PyYAML** — the tests spawn `python3`, so it must be the first `python3`
on your `PATH`), Node 20+, and git.

```bash
git clone <this repository> && cd ultimate-engine
python3 -m pip install PyYAML                  # or use a venv first on PATH
npm ci && (cd tools/visual-engine && npm ci) && (cd tools/mermaid-engine && npm ci)
bash tools/hooks/install.sh                    # once per clone: the pre-commit / pre-push gates
python3 -m tools.health                        # one command: is everything green?
```

`python3 -m tools.health --full` also runs both npm suites, lint (`ruff`, `mypy --strict`) and the
moat attack harness; it takes several minutes. The three real-browser tests run when
`PLAYWRIGHT_MODULE_DIR` names a directory that resolves `playwright`; otherwise they skip, and say so.

## The rules that keep this engine honest

Read [`docs/process/RULES.md`](docs/process/RULES.md) first; the short version:

1. **Fix the class, not the instance** — find every consumer of a defect's root before you fix one.
2. **No assertion without a retained counter-example** — a new check ships with a test that was seen
   to fail first, and the failing input stays in the suite.
3. **A document never restates a fact the code owns** — counts and versions are derived, not typed.
4. Every change that fixes a defect gets a row in [`docs/process/OPEN_GATES.md`](docs/process/OPEN_GATES.md)
   and an entry in [`CHANGELOG.md`](CHANGELOG.md) (append-only: never edit an old entry).
5. Generated files (`blueprint/`, `PROJECT_INDEX.json`) are never hand-edited: rebuild them
   (`python3 -m tools.blueprint build`) as the **last** step.

## Pull requests

- Branch from `master`; open the PR as a **draft** while it is in progress.
- Run `python3 -m tools.health` before pushing; `master` only accepts pull requests whose
  `secret-scan` check is green.
- A lockfile change needs its `VERSION_LOCK.json` attestation re-derived (health tells you how).
- Maintainers merge with a **merge commit** (never squash or rebase): stamped commits are read by the
  stamp guards.
- Never commit secrets, personal data, absolute home-directory paths or machine-specific settings.

## Reporting bugs and ideas

Use the issue templates. For security problems follow [SECURITY.md](SECURITY.md) instead.
