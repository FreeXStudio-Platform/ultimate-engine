"""A project's census profile: where its documents live and what its own conventions look like.

Every field has a default that works on an ordinary repository; a project overrides only what differs. The profile is JSON so a
host can keep it next to its other governance data. Unknown keys are REFUSED (a misspelt key must not silently fall back to a
default that measures something else), regular expressions are compiled at load so a bad one fails here and not halfway through
a scan, and nothing in this module reads git.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

SCHEMA: Final = "census-profile/1"

DEFAULT_LIFECYCLE: Final[dict[str, tuple[str, ...]]] = {
    # Matched against the first ``header_lines`` lines of a document, line by line, case-insensitively. A word in the BODY
    # ("this supersedes ...") is prose; only a header declaration crosses a document out.
    "superseded": (r"^\s*[>#*_\s-]*status\W{0,4}\s*[:—-]\s*\W*superseded", r"^\s*[>*_\s]*\W{0,3}superseded\b.{0,20}(?:by|with|see)\b"),
    "retired": (r"^\s*[>#*_\s-]*status\W{0,4}\s*[:—-]\s*\W*(?:retired|obsolete|withdrawn)", r"^\s*[>*_\s]*\W{0,3}retired\b"),
    "deprecated": (r"^\s*[>#*_\s-]*status\W{0,4}\s*[:—-]\s*\W*deprecated", r"^\s*[>*_\s]*\W{0,3}deprecated\b"),
    "archived": (r"^\s*[>#*_\s-]*status\W{0,4}\s*[:—-]\s*\W*archived", r"^\s*[>*_\s]*\W{0,3}archived\b"),
}
# A hardening stamp: ``<!-- artifact-hardened: Approved @ 1a2b3c4 on 2026-06-02 via three-pass-v1 -->``.
DEFAULT_STAMPS: Final = (
    r"^<!--\s*artifact-hardened:\s*(?P<status>[^@]+?)\s*@\s*(?P<sha>[0-9a-f]{7,40})(?:\s+on\s+(?P<date>\d{4}-\d{2}-\d{2}))?",
)
DEFAULT_TRUTH_LABELS: Final = (r"source[ _-]of[ _-]truth",)
# A stamp whose own text says it no longer holds (the status field of the stamp, not git).
DEFAULT_INVALIDATED: Final = (r"invalidat", r"revoked", r"withdrawn", r"needs[ _-]re-?hard")

_KEYS: Final = frozenset({
    "schema", "project", "doc_globs", "doc_exts", "archive_globs", "lifecycle_markers", "header_lines", "stamp_patterns",
    "truth_label_patterns", "invalidated_patterns", "authority_docs", "fresh_days", "outdated_days", "index_doc", "code_roots", "area_depth",
    "explorer_depth", "layers", "today", "notes", "report",
})


class ProfileError(ValueError):
    """A profile the census refuses, naming the key and the reason."""


@dataclass(frozen=True)
class Layer:
    """A named band of the documentation system (``layers``): the areas it holds, drawn as one row of a layered diagram."""

    label: str
    areas: tuple[str, ...]


@dataclass(frozen=True)
class Profile:
    project: str = "Project"
    doc_globs: tuple[str, ...] = ("docs/**", "*.md")
    doc_exts: tuple[str, ...] = (".md",)
    archive_globs: tuple[str, ...] = ()
    lifecycle_markers: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(DEFAULT_LIFECYCLE))
    header_lines: int = 30
    stamp_patterns: tuple[str, ...] = DEFAULT_STAMPS
    truth_label_patterns: tuple[str, ...] = DEFAULT_TRUTH_LABELS
    invalidated_patterns: tuple[str, ...] = DEFAULT_INVALIDATED
    authority_docs: tuple[str, ...] = ()
    fresh_days: int = 7
    outdated_days: int = 35
    index_doc: str | None = None
    code_roots: tuple[str, ...] = ()
    area_depth: int = 2
    explorer_depth: int = 3
    layers: tuple[Layer, ...] = ()
    today: str | None = None
    notes: str = ""
    report: dict[str, Any] = field(default_factory=dict)


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ProfileError(f"{where}: expected a list of non-empty strings")
    return tuple(value)


def _regexes(value: Any, where: str) -> tuple[str, ...]:
    out = _strings(value, where)
    for r in out:
        try:
            re.compile(r, re.IGNORECASE | re.MULTILINE)
        except re.error as exc:
            raise ProfileError(f"{where}: {r!r} is not a regular expression ({exc})") from exc
    return out


def _int(value: Any, where: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ProfileError(f"{where}: expected an integer from {low} to {high}")
    return value


def from_dict(data: dict[str, Any]) -> Profile:
    """Validate a decoded profile and fill its defaults."""
    unknown = sorted(set(data) - _KEYS)
    if unknown:
        raise ProfileError(f"unknown profile key(s): {', '.join(unknown)}")
    if data.get("schema", SCHEMA) != SCHEMA:
        raise ProfileError(f"schema: expected {SCHEMA!r}")
    base = Profile()
    kw: dict[str, Any] = {}
    if "project" in data:
        if not isinstance(data["project"], str) or not data["project"].strip():
            raise ProfileError("project: expected a non-empty string")
        kw["project"] = data["project"].strip()
    for key in ("doc_globs", "archive_globs", "authority_docs", "code_roots"):
        if key in data:
            kw[key] = _strings(data[key], key)
    if "doc_exts" in data:
        exts = _strings(data["doc_exts"], "doc_exts")
        if not all(e.startswith(".") for e in exts):
            raise ProfileError("doc_exts: every extension starts with a dot")
        kw["doc_exts"] = tuple(e.lower() for e in exts)
    for key in ("stamp_patterns", "truth_label_patterns", "invalidated_patterns"):
        if key in data:
            kw[key] = _regexes(data[key], key)
    if "lifecycle_markers" in data:
        raw = data["lifecycle_markers"]
        if not isinstance(raw, dict) or not raw:
            raise ProfileError("lifecycle_markers: expected an object of name -> list of regular expressions")
        kw["lifecycle_markers"] = {str(k): _regexes(v, f"lifecycle_markers.{k}") for k, v in raw.items()}
    if "header_lines" in data:
        kw["header_lines"] = _int(data["header_lines"], "header_lines", 1, 400)
    if "fresh_days" in data:
        kw["fresh_days"] = _int(data["fresh_days"], "fresh_days", 1, 3650)
    if "outdated_days" in data:
        kw["outdated_days"] = _int(data["outdated_days"], "outdated_days", 1, 3650)
    if "area_depth" in data:
        kw["area_depth"] = _int(data["area_depth"], "area_depth", 1, 4)
    if "explorer_depth" in data:
        kw["explorer_depth"] = _int(data["explorer_depth"], "explorer_depth", 1, 5)
    if "index_doc" in data:
        if data["index_doc"] is not None and not isinstance(data["index_doc"], str):
            raise ProfileError("index_doc: expected a path or null")
        kw["index_doc"] = data["index_doc"]
    if "today" in data:
        today = data["today"]
        if today is not None and (not isinstance(today, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", today)):
            raise ProfileError("today: expected YYYY-MM-DD or null")
        kw["today"] = today
    if "notes" in data:
        kw["notes"] = str(data["notes"])
    if "report" in data:
        raw_rep = data["report"]
        allowed = {"id", "classification", "surface", "audience", "owner", "status", "export_allowed"}
        if not isinstance(raw_rep, dict) or set(raw_rep) - allowed:
            raise ProfileError(f"report: expected an object with keys from {sorted(allowed)}")
        kw["report"] = dict(raw_rep)
    if "layers" in data:
        raw_layers = data["layers"]
        if not isinstance(raw_layers, list):
            raise ProfileError("layers: expected a list of {label, areas}")
        layers = []
        for i, layer in enumerate(raw_layers):
            if not isinstance(layer, dict) or set(layer) - {"label", "areas"} or not isinstance(layer.get("label"), str):
                raise ProfileError(f"layers[{i}]: expected {{label, areas}}")
            layers.append(Layer(label=layer["label"], areas=_strings(layer.get("areas"), f"layers[{i}].areas")))
        kw["layers"] = tuple(layers)
    prof = Profile(**{**base.__dict__, **kw})
    if prof.fresh_days >= prof.outdated_days:
        raise ProfileError("fresh_days must be smaller than outdated_days")
    return prof


def load(path: Path) -> Profile:
    """Read a profile file; a missing file is an error, never the defaults (a typo in the path must not measure the wrong thing)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"{path}: expected a JSON object")
    return from_dict(data)


def glob_regex(pattern: str) -> re.Pattern[str]:
    """``**`` crosses directories, ``*`` and ``?`` do not; the pattern must match the whole path."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        out.append("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c))
        i += 1
    return re.compile("".join(out) + r"\Z")


def matcher(patterns: tuple[str, ...]) -> Callable[[str], bool]:
    """A predicate over repository-relative paths for a list of globs (an empty list matches nothing)."""
    compiled = [glob_regex(p) for p in patterns]

    def match(path: str) -> bool:
        return any(c.match(path) for c in compiled)

    return match
