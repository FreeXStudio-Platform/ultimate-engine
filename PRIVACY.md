# Ultimate Engine — Privacy Notice

Effective 27 November 2026 (with Ultimate Engine 2.1.0) · FreeXStudio · https://freexstudio.com · admin@freexstudio.com

## The short version

Ultimate Engine works on your files **on your computer**. It has no account, no telemetry, no analytics and no advertising,
and FreeXStudio does not receive your documents, figures, data or usage.

## When the software uses the network

| When | What happens | Who can see the request |
|---|---|---|
| **Weekly update check** (and when you run `ultimate-engine update`) | It downloads the newest release description and its signature from the official releases page on GitHub over HTTPS, and, if a newer signed release exists, the release archive. The request names the program and its version (`ultimate-engine-updater/<version>`). It contains no file, name, account or machine identifier. | GitHub receives your IP address and the usual request data, under GitHub's own privacy statement. |
| **Installing and updating** | A private Python environment is created and two Python libraries are installed (from the Python Package Index). If you add the chart or Mermaid components, their packages are installed with npm. | The package services you are configured to use, under their privacy policies. |
| **Fetching a public fact** (optional, only when you use it) | A tool can fetch a public web address that **you** give it, to cite a number. It refuses private and local addresses. | The website you name. |

Building documents and drawing figures needs no network, and neither do `init`, `new`, `types`, `check`, `doc-map`
or `pin`: `pin` verifies release files you have already downloaded, and never fetches anything itself. Pages the engine creates load nothing from the internet. The graph
viewer, if you use it, serves files from your own computer to your own browser.

## What is stored on your computer

In `~/.ultimate-engine` (or the folder you set): the installed versions; a small state file with the installed and previous
version, the components you chose, when you accepted the license and privacy notice and which texts, and when updates were last
checked; the public key updates are checked against; the new texts of a release that waits for your acceptance; and an
update log. It also records where `ssh-keygen`, `node` and `npm` were found, so a scheduled update can use them. In your
projects: the files you create; the ones `init` and `new` add; `DOCUMENT_MAP.json`, which `doc-map` writes and which
lists your documents' titles, paths relative to the project, links and states — never a home directory; and, if you pin
a release, the pinned copy and its record `ENGINE_PIN.json` (the version, checksums and which license and privacy texts
you accepted). Keep the pinned copy out of version control. `ultimate-engine uninstall` removes the engine folder, its
launcher and the weekly schedule. It does not touch your projects, or the download cache that pip and npm keep for your
user account.

## What you send us yourself

Issues, discussions and comments in the public GitHub repository are **public** and are handled by GitHub under its terms.
Do not post personal data, confidential material, passwords or keys; remove them from logs before you attach them. Report
security problems privately, as described in `SECURITY.md` on the releases page. If you e-mail admin@freexstudio.com, we
receive your address and message and use them to answer you and to improve the product; ask us at the same address to
delete them.

## Your rights

Depending on where you live, you may have rights to access, correct or delete personal data that we hold about you, or to
object to its use. Contact admin@freexstudio.com. You may also complain to your local data protection authority.

## Changes

We publish changes to this notice with a release and record them in the change log. A change that makes the software collect
or send more than this notice says will not be installed without your acceptance of the new terms.
