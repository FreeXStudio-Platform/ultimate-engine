"""Universal path/tool configuration loader.

Single source of truth: ../../engine.config.json (relative to this file). Every
value has a hardcoded fallback matching this engine's original, tested behavior,
so a missing or corrupted config file degrades to "works exactly like before"
rather than failing. Precedence for every setting: environment variable >
engine.config.json value > hardcoded fallback below.

See ../../CONFIGURATION.md for the full field reference and override examples.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Final

_ENGINE_ROOT = Path(__file__).resolve().parents[2]  # .../Ultimate Engine/

# Set only while host_root() is resolving; read by tool_path() to refuse the one branch that
# would call back into host_root(). See the guard in host_root() for why.
_RESOLVING_HOST_ROOT = False
_LOG = logging.getLogger("tools.docgen.engine_config")

_DEFAULT_VAULT_DIR = "docs/confidential"
_CONFIG_PATH_ENV = "ENGINE_CONFIG_PATH"


def config_path() -> Path:
    """The configuration file actually in force — resolved, never assumed.

    Exported because two other places need the SAME answer and were each computing their own:
    ``build_cache._rule_layer_fingerprint`` hashed the literal ``engine.config.json`` while the
    loader might be reading somewhere else entirely, and ``tools.health`` STRUCT-08 parsed the
    literal path and reported *"engine.config.json parses (9 keys)"* while the engine ran on an
    EMPTY configuration (measured 2026-08-23). One resolved answer, one function.
    """
    return Path(os.environ.get(_CONFIG_PATH_ENV, "") or (_ENGINE_ROOT / "engine.config.json"))


@lru_cache(maxsize=1)
def _raw_config() -> dict[str, Any]:
    path = config_path()
    # AN OVERRIDE MUST BE AS LOUD AS A BYPASS (`THREAT_MODEL.md`). This one silently replaced the
    # ENTIRE configuration — every gate-relevant path, the vault location included — and was the
    # only such override in the engine that said nothing, while `ENGINE_SECRET_SCAN` and
    # `ENGINE_SKIP_*` all announce. `_raw_config` is `lru_cache`d, so this prints once per process.
    if os.environ.get(_CONFIG_PATH_ENV):
        print(f"⚠️  engine configuration OVERRIDDEN via {_CONFIG_PATH_ENV}={path}", file=sys.stderr)
    try:
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return loaded
    # ValueError, not json.JSONDecodeError: a non-UTF-8 config raises UnicodeDecodeError, which is a
    # ValueError and NOT a JSONDecodeError, so the narrower tuple let it escape. host_root() is
    # called at import time by cli, generator, adjudication and validate_doc_system, and from
    # run.py's main() BEFORE run_all()'s fail-closed wrapper exists — so one bad byte in
    # engine.config.json took down every entry point, tools.health included (LESSONS.md L-17).
    except (OSError, ValueError) as exc:
        # Returning {} is deliberate and must stay (see above): raising here kills every entry
        # point, tools.health included, so nothing would be left to REPORT the problem. But
        # returning silently is its own defect — the engine then runs on built-in defaults while
        # the operator believes their configuration is in force, and every path, tool and host-root
        # override in that file is quietly ignored. So: distinguish ABSENT (normal — the engine is
        # designed to run with no config at all) from PRESENT-BUT-BROKEN (never normal), and say so
        # on stderr. `STRUCT-08` turns the same condition into a hard failure, which is where it
        # can fail loudly without taking the reporter down with it.
        if path.exists():
            print(
                f"engine.config.json at {path} could not be read "
                f"({type(exc).__name__}: {exc}) — running on BUILT-IN DEFAULTS; every setting in "
                "that file is being ignored. Run `python3 -m tools.health` (STRUCT-08).",
                file=sys.stderr,
            )
        return {}


def _field(section: str, key: str, default: str | None) -> str | None:
    """Env var (ENGINE_<SECTION>_<KEY> pattern declared in the config itself) > config file > default."""
    cfg = _raw_config().get(section, {}).get(key)
    if isinstance(cfg, dict):
        env_name = cfg.get("envVar")
        # **PRESENCE, not truthiness** (`OG-127`). `os.environ.get(name)` is falsy for `""`, so an
        # exported-but-empty variable — `export ENGINE_CONFIDENTIAL_DIR=` — was silently read as
        # "not set" and the config-file value was used instead. That is why `""` was the one
        # spelling refused silently while `.`, `..` and `/` each announced themselves, even though
        # `OG-92`'s register row and the resolver's own docstring both list `""` FIRST among the
        # values "refused loudly". An empty export is a configuration the operator made; returning
        # it lets `_path_field` refuse it out loud, which is what was always documented.
        if env_name and env_name in os.environ:
            return os.environ[env_name]
        value = cfg.get("value", default)
        return value if value is not None else default
    return default


def _path_field(section: str, key: str, default: str) -> str:
    """``_field`` for values that are joined onto a Path — never returns ``None``.

    ``_field`` is typed ``str | None`` and genuinely can return ``None``: a config that sets the key
    to JSON ``null`` reaches ``value if value is not None else default`` with ``default`` itself
    ``None`` at some call sites, and the plain ``dict.get`` branch returns whatever is stored. Every
    caller below then evaluated ``host_root() / None``, which raises ``TypeError`` at import time —
    taking down every entry point, `tools.health` included, on a config file that is valid JSON.
    Falling back to the documented default is the only safe reading of "the operator blanked this".
    """
    value = _field(section, key, default)
    if isinstance(value, str) and not value.strip() and value != default:
        # **An explicitly blank value is a configuration, not an absence** (`OG-127`).
        # This returned the default silently, so `ENGINE_CONFIDENTIAL_DIR=""` never reached the
        # `OG-92` refusal below and produced no log line at all — while `.`, `..` and `/` each
        # announced themselves. Both `OG-92`'s register row and `confidential_dir_relative`'s
        # docstring list `""` FIRST among the values "refused loudly"; measured, it was the one
        # spelling that was refused silently. The fallback is right; the silence was not.
        _LOG.error(
            "%s.%s is set to an empty value, which is not a path. REFUSED — falling back to %r.",
            section, key, default,
        )
        return default
    return value if isinstance(value, str) and value else default


def _safe_relative(section: str, key: str, default: str, consequence: str) -> str:
    """A host-root-relative path field that may not BE the root or escape above it (`OG-129`).

    `confidentialDir` was guarded (`OG-92`, `OG-102`, `OG-128`) and its siblings were not, though
    they are joined onto `host_root()` exactly the same way. Measured with `ENGINE_HOST_ROOT` set
    to a lab: `ENGINE_TRASH_DIR=.` resolved the trash directory to the repository ROOT, `'..'` to
    its parent and `'/'` to the filesystem root — all silently. A "move to trash" against the
    repository root is not a configuration mistake anyone should have to notice from behaviour.

    Absolute values are deliberately NOT refused here: `_doc_system_child` documents absolute
    support for a host whose rule layer lives outside its repository, and taking that away would
    break a supported layout to close a hole that is about relative escapes.
    """
    value = _path_field(section, key, default)
    normalised = PurePosixPath(value.strip()) if value.strip() else PurePosixPath("")
    if normalised.is_absolute():
        return value
    parts = [part for part in normalised.parts if part not in ("", ".")]
    if not parts or ".." in parts:
        _LOG.error(
            "%s.%s=%r names the host root or escapes above it. %s REFUSED — falling back to %r. "
            "(OG-129)",
            section, key, value, consequence, default,
        )
        return default
    return str(PurePosixPath(*parts))


@lru_cache(maxsize=1)
def host_root() -> Path:
    """The consuming host project's root — where docs/design/doc-system etc. live.

    Resolution order: ENGINE_HOST_ROOT env var > engine.config.json's docSystem.hostRoot >
    `git rev-parse --show-toplevel` from the current working directory > this engine's own
    parent directory (Ultimate Engine/ itself, so the engine is at least self-consistent
    when run standalone with no host project around it).
    """
    configured = _field("docSystem", "hostRoot", None)
    if configured:
        return Path(configured).expanduser().resolve()
    # Reentrancy guard. tool_path() resolves a relative candidate (".venv/bin/python") against
    # host_root(), and host_root() asks tool_path() for git — so with git absent from PATH the two
    # called each other until the interpreter hit its recursion limit. The flag lets tool_path()
    # know it is being called FROM host_root() and must skip the host-root-relative branch, which
    # is the only branch that closes the cycle.
    global _RESOLVING_HOST_ROOT
    if _RESOLVING_HOST_ROOT:
        return _ENGINE_ROOT
    _RESOLVING_HOST_ROOT = True
    try:
        git_bin = tool_path("git")
    finally:
        _RESOLVING_HOST_ROOT = False
    if git_bin:
        try:
            out = subprocess.run(
                [git_bin, "rev-parse", "--show-toplevel"],
                # Decode explicitly. `text=True` uses the PROCESS LOCALE, so a non-UTF-8 locale
                # corrupts a repository path containing non-ASCII — and this value becomes the root
                # every other path in the engine is resolved against.
                capture_output=True, text=True, timeout=5, check=False,
                encoding="utf-8", errors="surrogateescape",
            )
            if out.returncode == 0 and out.stdout.strip():
                return Path(out.stdout.strip()).resolve()
        except (OSError, subprocess.SubprocessError) as exc:
            # `git` was on PATH (the `if git_bin:` guard above) but the invocation itself failed —
            # a race where it vanished, a timeout, or a spawn error. Falling back to _ENGINE_ROOT is
            # the documented behaviour outside a git checkout; log at debug so the fallback is
            # traceable without adding noise to every non-git invocation (N22).
            _LOG.debug("host_root: git rev-parse failed, falling back to %s: %s", _ENGINE_ROOT, exc)
    return _ENGINE_ROOT


def doc_system_dir() -> Path:
    return host_root() / _safe_relative(
        "docSystem", "docSystemDir", "docs/design/doc-system",
        "The rule layer would resolve to the repository root, so the hash gate, the manifest and "
        "the taxonomy would all be looked up in the wrong place.",
    )


def project_name() -> str:
    """The host project's display name, used wherever a rendered document names its publisher.

    The engine ships an EMPTY default, and that emptiness was visible in the output rather than
    inert: the trust footer rendered ``Verified by `` with nothing after it, and the content-index
    schema id came out as ``.doc-system.content-index/v1`` with a leading dot where the project
    namespace belongs. Both had a project-name slot; neither had a way to fill it.

    Empty stays the default so an unconfigured engine renders exactly as before — this is
    additive, and a host that sets nothing sees no change.
    """
    return (_field("branding", "projectName", "") or "").strip()


_ENGINE_ASSETS_DIR: Final[Path] = Path(__file__).resolve().parent / "assets"


def mark_path() -> Path:
    """Resolve the project mark SVG that :func:`components.logo_svg` inlines.

    The engine ships a NEUTRAL placeholder so it renders out of the box. A host project supplies
    its own brand mark here rather than by editing engine code — this is the "profile-aware engine
    hook" a host profile's identity block anticipates. Before it existed, ``components._MARK_PATH``
    was a module-level constant pinned to the placeholder, so a host that vendored its real mark
    right next to it still shipped the generic one in EVERY rendered document, silently and
    forever (measured on a downstream host: ``assets/<host>-mark.svg`` was present, protected
    from the sync, named in the profile — and read by nothing).

    Three shapes, matching :func:`_doc_system_child` so the vocabulary is the same everywhere:

    * absolute        -> used as-is;
    * contains a `/`  -> HOST-root-relative (the host keeps its mark in its own tree);
    * a bare filename -> resolved under the ENGINE's own ``assets/`` directory (where a vendored
                         mark sits next to the placeholder it replaces).

    **Fail-closed:** a configured mark that does not exist raises. Falling back to the placeholder
    would reproduce the exact defect this hook was added to fix — an operator who asked for a
    specific mark and silently got the generic one. The default placeholder always exists, so an
    unconfigured engine never reaches that path.
    """
    value = _path_field("branding", "markPath", "engine-mark-placeholder.svg")
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate
    elif len(candidate.parts) > 1:
        resolved = host_root() / candidate
    else:
        resolved = _ENGINE_ASSETS_DIR / candidate
    if not resolved.is_file():
        raise FileNotFoundError(
            f"branding.markPath (ENGINE_MARK_PATH) resolves to {resolved}, which does not exist. "
            "Refusing to fall back to the placeholder mark: a configured brand mark that silently "
            "degrades to the engine's generic one is the defect this setting exists to prevent."
        )
    return resolved


def _doc_system_child(key: str, default: str) -> Path:
    """Resolve a rule-layer file that belongs *inside* the doc-system directory.

    Three shapes, in order, so `ENGINE_DOC_SYSTEM_DIR` alone relocates the whole rule layer:

    * absolute            -> used as-is;
    * contains a `/`      -> host-root-relative (back-compatible with configs that spell out the
                             full `docs/design/doc-system/DOC_MANIFEST.md`);
    * a bare filename     -> resolved under :func:`doc_system_dir`.

    Before this (``OG-22``) each of these was independently host-root-relative, so pointing
    `ENGINE_DOC_SYSTEM_DIR` at a host project's own layout moved the TAXONOMY but left
    `DOC_MANIFEST.md` and `VERSION.json` behind — a silently split rule layer, in which the hash
    gate and the manifest gate consult different directories. Five env vars existed; setting the
    one an operator would obviously reach for produced the broken state.
    """
    value = _path_field("docSystem", key, default)
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if len(candidate.parts) > 1:
        return host_root() / candidate
    return doc_system_dir() / candidate


def doc_manifest_path() -> Path:
    return _doc_system_child("docManifestPath", "DOC_MANIFEST.md")


def version_json_path() -> Path:
    return _doc_system_child("versionJsonPath", "VERSION.json")


def confidential_dir() -> Path:
    # Routed through the relative resolver so the root-escape refusal applies to BOTH callers —
    # guarding one of two consumers of a shared value is how `OG-84` happened.
    return host_root() / confidential_dir_relative()


def confidential_dir_relative() -> str:
    """The confidential-docs path as a host-root-relative string (for comparing against
    git-relative staged-file paths, which are never absolute).

    **Any value naming the repository root or an ancestor is refused, not just the empty string.**

    The empty case was closed first: `""` became `PurePosixPath('')`, which equals
    `PurePosixPath('.')`, so the placement gate's containment test was true for EVERY path in the
    repository — one character silently disabling the L14 security gate while the hook printed its
    ordinary affirmative line.

    That fix guarded `""` alone, and a verifier walked straight past it with
    `ENGINE_CONFIDENTIAL_DIR=.` — same effect, different spelling, gate off, exit 0 (`OG-92`).
    `docs/process/RULES.md` Rule 1: *the counter-example must cover the CLASS, not the instance*.
    The class is "a vault that contains everything is not a vault", so every spelling of the root
    and of an escape upward is refused here, and the refusal is **announced** rather than silent —
    a security control that degrades quietly is the fail-open defect this engine exists to catch.
    """
    value = _path_field("docSystem", "confidentialDir", _DEFAULT_VAULT_DIR)
    normalised = PurePosixPath(value.strip()) if value.strip() else PurePosixPath("")
    parts = [p for p in normalised.parts if p not in ("", ".")]
    if normalised.is_absolute():
        # **Refused, but for its own reason** (`OG-128`). This shared `OG-92`'s message, which says
        # the value "names the repository root or escapes it" — untrue of `/abs/vault`, and a
        # refusal that misdescribes what it refused sends the operator looking for the wrong
        # mistake. The refusal itself is right: this value is compared against git-relative staged
        # paths, which are never absolute, so an absolute vault matches NOTHING and every governed
        # document reads as outside it. That fails closed, which is safe, but silently reclassifies
        # the whole corpus — so it is refused here with an accurate explanation instead.
        _LOG.error(
            "confidentialDir=%r is an absolute path. The placement gate compares this against "
            "git-relative staged paths, which are never absolute, so no document could ever be "
            "inside the vault. REFUSED — falling back to %r. (OG-128)",
            value,
            _DEFAULT_VAULT_DIR,
        )
        return _DEFAULT_VAULT_DIR
    if not parts or ".." in parts:
        _LOG.error(
            "confidentialDir=%r names the repository root or escapes it, which would put every "
            "path 'inside the vault' and disable the RULEBOOK L14 placement gate. REFUSED — "
            "falling back to %r. (OG-92)",
            value,
            _DEFAULT_VAULT_DIR,
        )
        return _DEFAULT_VAULT_DIR

    # **A vault that swallows the rule layer is not a vault either** (`OG-102`).
    #
    # The check above refuses `""`, `.`, `/` and `..` — every spelling of the ROOT. Pass 7 walked
    # past it with `ENGINE_CONFIDENTIAL_DIR=docs`: a perfectly ordinary relative directory, no
    # dots, no escape — and because `docs/` contains this project's entire governed corpus, every
    # document was suddenly "inside the vault" and the L14 placement gate passed everything while
    # the hook printed its ordinary affirmative line. Identical effect to `OG-92`, third spelling.
    # `LESSONS.md` L-26: after narrowing, attack the NEW edge.
    #
    # The invariant that actually holds, rather than another blacklisted string: **the vault may
    # not be an ancestor of the rule layer.** If `confidentialDir` contains `docSystemDir`, then
    # the documents that DEFINE the classification rules are themselves classified, which is
    # incoherent on its own terms — and mechanically it is the exact condition under which the
    # containment test starts returning true for the whole corpus. Derived from configuration, so
    # it holds for any host layout instead of only for this one.
    rule_layer = PurePosixPath(_path_field("docSystem", "docSystemDir", "docs/design/doc-system"))
    rule_parts = [p for p in rule_layer.parts if p not in ("", ".")]
    if rule_parts[: len(parts)] == parts:
        _LOG.error(
            "confidentialDir=%r contains the rule layer docSystemDir=%r, so every governed "
            "document would count as already inside the vault and the RULEBOOK L14 placement "
            "gate would pass everything. REFUSED — falling back to %r. (OG-102)",
            value,
            str(rule_layer),
            _DEFAULT_VAULT_DIR,
        )
        return _DEFAULT_VAULT_DIR
    return str(PurePosixPath(*parts))


def trash_dir() -> Path:
    return host_root() / _safe_relative(
        "docSystem", "trashDir", "docs/archives/_trash",
        "A trash directory that IS the repository root makes every archive operation target the "
        "whole repository.",
    )


_DEFAULT_ARCHIVE_DIR = "docs/archive"


def archive_dir() -> Path:
    """Where superseded document versions are kept (Phase 4 document identity).

    ⚠ **Not to be confused with ``trash_dir``, whose default is ``docs/archives/_trash``** — one
    letter apart, and the two hold opposite things. This directory is a *version history*: every
    snapshot in it is a document the project deliberately kept and can still be read. The trash
    directory holds content on its way OUT. The near-collision is named here, and in
    ``engine.config.json``, because a reader who meets only one of the two names has no way to
    know the other exists.
    """
    return host_root() / archive_dir_relative()


def archive_dir_relative() -> str:
    """The archive path as a host-root-relative string, for comparing against git-relative paths.

    Routed through ``_safe_relative`` for the same reason every other relative field is: an
    archive directory resolving to the repository root would make "snapshot this document" copy
    into, and a future prune walk over, the whole tree (`OG-129`).
    """
    return _safe_relative(
        "docSystem", "archiveDir", _DEFAULT_ARCHIVE_DIR,
        "An archive directory that IS the repository root would make every snapshot and every "
        "archive walk target the whole repository.",
    )


_DEFAULT_SYSTEM_SPEC = "system.spec.json"
_DEFAULT_BLUEPRINT_DIR = "blueprint"
_DEFAULT_BLUEPRINT_INDEX_DIR = ".blueprint"


def system_spec_path() -> Path:
    """The authored system spec the blueprint layer resolves against (Phase 5).

    Host-root-relative like every other document-layer path, and routed through
    ``_safe_relative`` for the reason every sibling is (`OG-129`): a spec path that resolved to
    the repository root would make ``blueprint verify`` try to parse a directory.

    **Why this file is authored and everything around it is derived.** The spec carries only the
    facts no artifact in the tree owns — the containers a reader should think in, their purpose,
    and the document that owns each. Every other value in ``blueprint/`` is re-derived on each
    build, so it cannot rot (`docs/process/RULES.md` Rule 2). ``verify`` then checks the authored
    half against the tree, which is the only thing that keeps a judgement file honest.
    """
    return host_root() / _safe_relative(
        "docSystem", "systemSpec", _DEFAULT_SYSTEM_SPEC,
        "The system spec would resolve to the repository root, so `blueprint verify` would have "
        "no spec to check the container decomposition against.",
    )


def blueprint_dir() -> Path:
    """Where the DERIVED, committed map is written. Contents are described by ``blueprint_files``."""
    return host_root() / _safe_relative(
        "docSystem", "blueprintDir", _DEFAULT_BLUEPRINT_DIR,
        "The blueprint directory would resolve to the repository root, so a build would write "
        "SYSTEM.md and its siblings over the top of the project.",
    )


def blueprint_index_dir() -> Path:
    """Where the derived SQLite index is written — **gitignored, rebuildable, never authoritative**.

    `docs/plan/BUILD_PLAN.md` D1: the corpus lives as Markdown in git, and the database is built
    *from* it so that joins and full-text search are cheap. Committing it would create a second
    source of truth that a stale row could silently win.
    """
    return host_root() / _safe_relative(
        "docSystem", "blueprintIndexDir", _DEFAULT_BLUEPRINT_INDEX_DIR,
        "The derived-index directory would resolve to the repository root, so `blueprint index` "
        "would write its database into the top of the project.",
    )


def content_index_path() -> Path:
    return _doc_system_child("contentIndexPath", "CONTENT_INDEX.json")


def authored_docs_root() -> Path:
    return _doc_system_child("authoredDocsRoot", "authored")


def project_index_path() -> Path:
    """Where PROJECT_INDEX.json lives — env var > config value > default (``PROJECT_INDEX.json``
    at ``host_root()``).

    A relative ``configured`` value is resolved against ``host_root()``, matching every other
    accessor in this module (``doc_manifest_path``, ``confidential_dir``, ...); an absolute value
    is used as-is. **Fixed 2026-09-24:** this used to return a bare ``Path(configured)``
    unresolved, so a relative override (e.g. a host pointing its index at a doc-system subdirectory
    rather than its repo root) silently resolved against the process's CWD instead of the host
    project root — correct only by accident, whenever a caller's CWD happened to already be
    ``host_root()``. Every other relative override in this module is host-root-anchored; this one
    now is too.
    """
    configured = _field("projectIndex", "path", None)
    if configured:
        p = Path(configured).expanduser()
        return p if p.is_absolute() else host_root() / p
    return host_root() / "PROJECT_INDEX.json"


@lru_cache(maxsize=8)
def tool_path(name: str) -> str | None:
    """Discover an external binary: env var override > config 'path' field > PATH-searched fallback list."""
    cfg = _raw_config().get("tools", {}).get(name, {})
    env_name = cfg.get("envVar")
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    explicit = cfg.get("path")
    if explicit:
        return str(explicit)
    for candidate in cfg.get("pathFallback", [name]):
        found = shutil.which(str(candidate))
        if found:
            return found
        # allow a relative venv-style path (e.g. ".venv/bin/python") resolved against host_root()
        if _RESOLVING_HOST_ROOT:
            # We are inside host_root() itself; resolving a host-root-relative candidate here
            # would recurse. Skipping it only loses the ".venv/bin/x" convenience for the tool
            # host_root() happens to be looking up (git), which is never a venv-relative binary.
            continue
        rel = host_root() / candidate
        if rel.exists():
            return str(rel)
    return None


def require_tool(name: str) -> str:
    """Like tool_path(), but raises a clear, actionable error instead of returning None."""
    found = tool_path(name)
    if found:
        return found
    cfg = _raw_config().get("tools", {}).get(name, {})
    hint = cfg.get("installHint", f"install '{name}' and ensure it is on PATH")
    env_name = cfg.get("envVar", f"ENGINE_{name.upper()}_BIN")
    raise RuntimeError(
        f"required tool '{name}' not found. {hint}. "
        f"Or point at it explicitly: export {env_name}=/path/to/{name}"
    )
