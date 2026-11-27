# Install, use, remove

## Requirements
- macOS or Linux. On Windows, use WSL.
- Python 3.11 or newer, and OpenSSH 8.1 or newer (`ssh-keygen`). The installer tests that it can check a release signature, and stops if it cannot.
- git 2.26 or newer, only for the project census.
- For charts and Mermaid: Node.js 20 or newer, with npm.
- A network connection during installation (two Python libraries, plus npm packages for optional components).

## Install
1. Download the newest `ultimate-engine-<version>.tar.gz` from the [releases page](https://github.com/FreeXStudio-Platform/ultimate-engine/releases/latest). [Verify it](VERIFY.md) if you can.
2. ```sh
   tar -xzf ultimate-engine-<version>.tar.gz
   cd ultimate-engine-<version> && ./install.sh
   ```
3. Read the license summary. Type `I accept` to continue, then choose the optional components.

Everything goes into `~/.ultimate-engine`. The command is `~/.local/bin/ultimate-engine`; add that folder to your `PATH` if the installer says so.

## The menu
Run `ultimate-engine` with nothing after it:
1 Verify the installation · 2 Add the chart engine · 3 Add Mermaid diagrams · 4 Set up a project here · 5 Check for updates now ·
6 Return to the previous version · 7 Version, license and privacy · 8 Uninstall

## Commands
| Command | What it does |
|---|---|
| `ultimate-engine init [folder] --idea "…"` | adds the rule layer and the project brief, the first document, to a project |
| `ultimate-engine types [TYPE]` | the document types, in the order a project writes them |
| `ultimate-engine new TYPE "title"` | a new document with every required section, linked to what it builds on |
| `ultimate-engine doc-map` | writes `DOCUMENT_MAP.json`: every document, its links, what is missing, the order to read them |
| `ultimate-engine check doc.md [--strict]` | checks a document's header, type, links and sections |
| `ultimate-engine pin <assets> --into <folder>` | pins one release inside a project ([pinning](PINNING.md)) |
| `ultimate-engine build doc.md -o out --formats html,blueprint` | builds a page and its record |
| `ultimate-engine render spec.json --theme dark -o figure.svg` | draws one document figure |
| `ultimate-engine chart job.json [-o folder]` | draws a chart |
| `ultimate-engine mermaid a.mmd -o a.svg` | draws a Mermaid diagram |
| `ultimate-engine cvd check <file or folder>` | colour-vision check |
| `ultimate-engine catalog list` | every figure kind |
| `ultimate-engine add charts` / `add mermaid` | adds a component |
| `ultimate-engine update` / `rollback` / `verify` / `version` / `license` | maintenance |
| `ultimate-engine uninstall` | removes the engine; your projects stay |

## Use with an AI assistant
Point your assistant at `~/.ultimate-engine/current/skills/choose-a-chart/SKILL.md`. It routes a question to the right
figure kind and links to that kind's instructions.

## Automatic updates
Once a week the engine checks for a newer signed release (a macOS LaunchAgent or a cron entry, and also when you use it a
week after the last check). A release that changes the license or the privacy notice waits: run `ultimate-engine update`, which shows you the new
texts, and accept or not. After `ultimate-engine rollback`, the version you left is not installed again until a newer one
is released or you run `ultimate-engine update`. If `CI` is set while installing, automatic updates are off.
The log is `~/.ultimate-engine/update.log`.

## If something fails
Run `ultimate-engine verify` and read the log, then [report it](https://github.com/FreeXStudio-Platform/ultimate-engine/issues/new?template=bug_report.yml). Remove personal data from anything you paste.
