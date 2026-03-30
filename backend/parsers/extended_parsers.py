"""
SentinelStream AI — Multi-Language Dependency Parsers (V2)
Adds Java (pom.xml/Gradle), Rust (Cargo.toml), Ruby (Gemfile), PHP (composer.json), C# (.csproj)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional

from models.schemas import Dependency, Ecosystem


# ── Java: pom.xml (Maven) ───────────────────────────────────────────────────

def parse_pom_xml(content: str, file_path: str = "pom.xml") -> list[Dependency]:
    """Parse a Maven pom.xml file."""
    deps: list[Dependency] = []
    try:
        # Strip namespace for simpler parsing
        content_stripped = re.sub(r'\sxmlns="[^"]+"', '', content, count=1)
        root = ET.fromstring(content_stripped)
        ns = ""
        for dep in root.findall(f".//dependency"):
            group_id = dep.findtext("groupId", "").strip()
            artifact_id = dep.findtext("artifactId", "").strip()
            version = dep.findtext("version", "*").strip()
            if group_id and artifact_id:
                # Skip if version is a Maven property placeholder
                if version.startswith("${"):
                    version = "*"
                deps.append(Dependency(
                    name=f"{group_id}:{artifact_id}",
                    version=version,
                    ecosystem=Ecosystem.MAVEN,
                    file_path=file_path,
                ))
    except ET.ParseError:
        pass
    return deps


# ── Java: build.gradle ──────────────────────────────────────────────────────

_GRADLE_DEP_RE = re.compile(
    r"""(?:implementation|api|compile|testImplementation|runtimeOnly)\s+
        ['"]
        ([A-Za-z0-9.\-_]+)     # groupId
        :
        ([A-Za-z0-9.\-_]+)     # artifactId
        (?::([0-9][^\s'"]+))?  # optional version
        ['"]""",
    re.VERBOSE,
)


def parse_build_gradle(content: str, file_path: str = "build.gradle") -> list[Dependency]:
    """Parse a Gradle build.gradle file (Groovy DSL)."""
    deps: list[Dependency] = []
    for match in _GRADLE_DEP_RE.finditer(content):
        group_id, artifact_id, version = match.groups()
        deps.append(Dependency(
            name=f"{group_id}:{artifact_id}",
            version=version or "*",
            ecosystem=Ecosystem.MAVEN,
            file_path=file_path,
        ))
    return deps


# ── Rust: Cargo.toml ────────────────────────────────────────────────────────

_CARGO_DEP_RE = re.compile(
    r'^([a-zA-Z0-9_\-]+)\s*=\s*(?:"([^"]+)"|.*?version\s*=\s*"([^"]+)")',
    re.MULTILINE,
)


def parse_cargo_toml(content: str, file_path: str = "Cargo.toml") -> list[Dependency]:
    """Parse a Rust Cargo.toml file."""
    deps: list[Dependency] = []
    in_deps_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]"):
            in_deps_section = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_deps_section = False
            continue
        if in_deps_section and "=" in line:
            match = re.match(r'^([a-zA-Z0-9_\-]+)\s*=\s*"([^"]+)"', stripped)
            if match:
                name, version = match.groups()
                # Strip semver range prefix
                version = re.sub(r"^[^0-9]*", "", version) or version
                deps.append(Dependency(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.CARGO,
                    file_path=file_path,
                ))
            else:
                # Inline table: name = { version = "1.0", features = [...] }
                table_match = re.match(r'^([a-zA-Z0-9_\-]+)\s*=\s*\{.*version\s*=\s*"([^"]+)"', stripped)
                if table_match:
                    name, version = table_match.groups()
                    version = re.sub(r"^[^0-9]*", "", version) or version
                    deps.append(Dependency(
                        name=name,
                        version=version,
                        ecosystem=Ecosystem.CARGO,
                        file_path=file_path,
                    ))
    return deps


# ── Ruby: Gemfile ────────────────────────────────────────────────────────────

_GEMFILE_GEM_RE = re.compile(
    r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""",
    re.MULTILINE,
)


def parse_gemfile(content: str, file_path: str = "Gemfile") -> list[Dependency]:
    """Parse a Ruby Gemfile."""
    deps: list[Dependency] = []
    for match in _GEMFILE_GEM_RE.finditer(content):
        name = match.group(1)
        version = match.group(2) or "*"
        # Strip constraint prefix: ~>, >=, <=, =
        version = re.sub(r"^[~><=\s]+", "", version) or version
        deps.append(Dependency(
            name=name,
            version=version,
            ecosystem=Ecosystem.RUBYGEMS,
            file_path=file_path,
        ))
    return deps


# ── PHP: composer.json ───────────────────────────────────────────────────────

def parse_composer_json(content: str, file_path: str = "composer.json") -> list[Dependency]:
    """Parse a PHP composer.json file."""
    import json
    deps: list[Dependency] = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return deps
    for section in ("require", "require-dev"):
        for name, version in data.get(section, {}).items():
            if name == "php":  # Skip PHP engine constraint
                continue
            clean = re.sub(r"^[^0-9]*", "", version) or version
            deps.append(Dependency(
                name=name,
                version=clean,
                ecosystem=Ecosystem.COMPOSER,
                file_path=file_path,
            ))
    return deps


# ── C#/.NET: .csproj ─────────────────────────────────────────────────────────

def parse_csproj(content: str, file_path: str = "project.csproj") -> list[Dependency]:
    """Parse a C# .csproj file."""
    deps: list[Dependency] = []
    try:
        root = ET.fromstring(content)
        for ref in root.findall(".//PackageReference"):
            name = ref.get("Include", "")
            version = ref.get("Version", "") or ref.findtext("Version", "*")
            if name:
                deps.append(Dependency(
                    name=name,
                    version=version or "*",
                    ecosystem=Ecosystem.NUGET,
                    file_path=file_path,
                ))
    except ET.ParseError:
        pass
    return deps


# ── Extended Parser Map ───────────────────────────────────────────────────────

EXTENDED_PARSER_MAP: dict[str, callable] = {
    "pom.xml": parse_pom_xml,
    "build.gradle": parse_build_gradle,
    "Cargo.toml": parse_cargo_toml,
    "Gemfile": parse_gemfile,
    "composer.json": parse_composer_json,
    ".csproj": parse_csproj,
}


def detect_extended_parser(file_path: str):
    """Return extended parser for a file path, or None."""
    for pattern, parser in EXTENDED_PARSER_MAP.items():
        if file_path.endswith(pattern):
            return parser
    return None


def parse_extended_dependency_file(file_path: str, content: str) -> list[Dependency]:
    """Parse a dependency file using the extended parser map."""
    parser = detect_extended_parser(file_path)
    if parser is None:
        return []
    return parser(content, file_path)
