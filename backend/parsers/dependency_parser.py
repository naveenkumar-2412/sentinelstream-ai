"""
SentinelStream AI — Dependency File Parser
Parses package.json, requirements.txt, and go.mod to extract dependency lists.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from models.schemas import Dependency, DependencyDelta, ChangeType, Ecosystem


# ── Individual Parsers ───────────────────────────────────────


def parse_requirements_txt(content: str, file_path: str = "requirements.txt") -> list[Dependency]:
    """Parse a Python requirements.txt file."""
    deps: list[Dependency] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle: package==1.0.0, package>=1.0.0, package~=1.0.0, etc.
        match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([><=~!]+)\s*([^\s,;#]+)", line)
        if match:
            deps.append(Dependency(
                name=match.group(1).lower(),
                version=match.group(3),
                ecosystem=Ecosystem.PYPI,
                file_path=file_path,
            ))
        else:
            # Bare package name without version pin
            name_match = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
            if name_match:
                deps.append(Dependency(
                    name=name_match.group(1).lower(),
                    version="*",
                    ecosystem=Ecosystem.PYPI,
                    file_path=file_path,
                ))
    return deps


def parse_package_json(content: str, file_path: str = "package.json") -> list[Dependency]:
    """Parse an npm package.json file."""
    deps: list[Dependency] = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return deps

    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, version in data.get(section, {}).items():
            # Strip semver range prefixes: ^, ~, >=, etc.
            clean_version = re.sub(r"^[\^~>=<|*x ]+", "", version) or version
            deps.append(Dependency(
                name=name,
                version=clean_version,
                ecosystem=Ecosystem.NPM,
                file_path=file_path,
            ))
    return deps


def parse_go_mod(content: str, file_path: str = "go.mod") -> list[Dependency]:
    """Parse a Go go.mod file."""
    deps: list[Dependency] = []
    in_require = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if in_require and line == ")":
            in_require = False
            continue
        if in_require or line.startswith("require "):
            clean = line.replace("require ", "").strip()
            parts = clean.split()
            if len(parts) >= 2:
                deps.append(Dependency(
                    name=parts[0],
                    version=parts[1].lstrip("v"),
                    ecosystem=Ecosystem.GO,
                    file_path=file_path,
                ))
    return deps


# ── Unified Parser ───────────────────────────────────────────


PARSER_MAP = {
    "requirements.txt": parse_requirements_txt,
    "package.json": parse_package_json,
    "go.mod": parse_go_mod,
}

# Also match paths like `backend/requirements.txt`
FILENAME_MAP = {
    "requirements.txt": parse_requirements_txt,
    "package.json": parse_package_json,
    "go.mod": parse_go_mod,
}


def detect_parser(file_path: str):
    """Return the appropriate parser function for a file path."""
    for filename, parser in FILENAME_MAP.items():
        if file_path.endswith(filename):
            return parser
    return None


def parse_dependency_file(file_path: str, content: str) -> list[Dependency]:
    """Parse a dependency file and return the list of dependencies."""
    parser = detect_parser(file_path)
    if parser is None:
        return []
    return parser(content, file_path)


# ── Delta Computation ────────────────────────────────────────


def _classify_change(old_version: str, new_version: str) -> ChangeType:
    """Classify a version change as patch, minor, or major."""
    try:
        old_parts = [int(x) for x in old_version.split(".")[:3]]
        new_parts = [int(x) for x in new_version.split(".")[:3]]
    except (ValueError, AttributeError):
        return ChangeType.MAJOR  # Can't parse → treat as major

    # Pad to 3 elements
    while len(old_parts) < 3:
        old_parts.append(0)
    while len(new_parts) < 3:
        new_parts.append(0)

    if old_parts[0] != new_parts[0]:
        return ChangeType.MAJOR
    if old_parts[1] != new_parts[1]:
        return ChangeType.MINOR
    return ChangeType.PATCH


def compute_deltas(
    old_deps: list[Dependency],
    new_deps: list[Dependency],
) -> list[DependencyDelta]:
    """Compare two dependency lists and produce a list of deltas."""
    old_map = {d.name: d for d in old_deps}
    new_map = {d.name: d for d in new_deps}

    deltas: list[DependencyDelta] = []

    # Added or modified
    for name, new_dep in new_map.items():
        old_dep = old_map.get(name)
        if old_dep is None:
            deltas.append(DependencyDelta(
                old=None,
                new=new_dep,
                change_type=ChangeType.NEW,
            ))
        elif old_dep.version != new_dep.version:
            deltas.append(DependencyDelta(
                old=old_dep,
                new=new_dep,
                change_type=_classify_change(old_dep.version, new_dep.version),
            ))

    # Removed
    for name, old_dep in old_map.items():
        if name not in new_map:
            deltas.append(DependencyDelta(
                old=old_dep,
                new=None,
                change_type=ChangeType.REMOVED,
            ))

    return deltas
