# Pin one version inside a project or a build server

A project that builds its documents in its own repository or in continuous integration needs the same engine on every
machine, and must not change underneath a build. Pinning gives it exactly one signed release, extracted into a folder
your version control ignores, with **no automatic update**: a newer version arrives only when you pin it.

## What you keep in the project

| File | What it is |
|---|---|
| `SIGNING_KEY.pub` | FreeXStudio's release key, copied once from [this repository](../SIGNING_KEY.pub). It decides which releases you trust. |
| `.engine/ENGINE_PIN.json` | written by the pin: the version, the archive's SHA-256, the terms you accepted, and the checksum of the file list. Commit it. |
| `.engine/ultimate-engine-<version>/` | the extracted release. **Do not commit it**: add it to `.gitignore`. Rebuild it from the pin. |

## Pin with an installed engine

```sh
ultimate-engine pin ./downloaded-assets --into .engine --accept-license
```

`./downloaded-assets` holds the four files of one release: `ultimate-engine-<version>.tar.gz`, `manifest.json`,
`manifest.json.sig` and `SHA256SUMS`. The installed engine checks the signature with the key it trusts, checks the
archive against the signed manifest, extracts only the listed files and checks each one.

## Pin on a build server, without an installed engine

```sh
v=2.1.0
gh release download "v$v" -R FreeXStudio-Platform/ultimate-engine -D assets   # or download the four files by hand
ssh-keygen -Y verify -f SIGNING_KEY.pub -I release@freexstudio.com -n ultimate-engine-release \
  -s assets/manifest.json.sig < assets/manifest.json
(cd assets && shasum -a 256 -c SHA256SUMS)
mkdir -p .engine/bootstrap && tar -xzf "assets/ultimate-engine-$v.tar.gz" -C .engine/bootstrap
python3 -P -m tools.product.host pin --assets assets --signers SIGNING_KEY.pub --into .engine --accept-license --with-python
```

Run the last line from `.engine/bootstrap/ultimate-engine-$v` (or set `PYTHONPATH` to it). It verifies everything again
and writes the pin. `--with-python` also prepares the release's own Python environment, installing its two libraries only
from files that match pinned checksums.

## Use it

```sh
python3 -P -m tools.product.host check --into .engine          # before each use: every file is the pinned one
python3 -P -m tools.product.host run --into .engine -- build docs/BRF-001-project-brief.md -o out --formats html,blueprint
python3 -P -m tools.product.host run --into .engine -- doc-map --check
```

`run` checks the pinned copy, then runs the document command with it, in your project. Any document command works:
`build`, `check`, `new`, `types`, `doc-map`, `render`.

## Rules that come with pinning

- Accepting the license with `--accept-license` is your acceptance of the [license](../LICENSE.md) and the [privacy notice](../PRIVACY.md).
- The pinned copy must stay **unchanged**; `check` refuses a changed file. To fix something, [tell us](https://github.com/FreeXStudio-Platform/ultimate-engine/issues/new?template=bug_report.yml).
- Do not commit or re-host the extracted release. Commit `ENGINE_PIN.json` and `SIGNING_KEY.pub`.
- To move to a newer version, pin it again and rebuild your documents.
