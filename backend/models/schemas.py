"""
SentinelStream AI — Pydantic Models / Schemas
Data structures used across all agent sub-modules.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────


class Ecosystem(str, Enum):
    """Package ecosystem identifiers."""
    PYPI = "PyPI"
    NPM = "npm"
    GO = "Go"
    UNKNOWN = "unknown"


class ChangeType(str, Enum):
    """Semantic version change classification."""
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"
    NEW = "new"
    REMOVED = "removed"


class Severity(str, Enum):
    """CVE severity levels aligned with POLICY.md thresholds."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ActionType(str, Enum):
    """Remediation action types."""
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"
    PASS = "pass"


# ── Core Models ──────────────────────────────────────────────


class Dependency(BaseModel):
    """A single dependency extracted from a manifest file."""
    name: str
    version: str
    ecosystem: Ecosystem = Ecosystem.UNKNOWN
    file_path: str = Field(default="", description="Source manifest file")


class DependencyDelta(BaseModel):
    """Change detected between base and head of an MR."""
    old: Optional[Dependency] = None
    new: Optional[Dependency] = None
    change_type: ChangeType = ChangeType.NEW

    @property
    def package_name(self) -> str:
        if self.new:
            return self.new.name
        if self.old:
            return self.old.name
        return "unknown"


class VulnerabilityResult(BaseModel):
    """Result from OSV or similar vulnerability database."""
    cve_id: str = Field(default="", description="e.g. CVE-2026-1234")
    summary: str = ""
    cvss_score: float = Field(default=0.0, ge=0.0, le=10.0)
    severity: Severity = Severity.NONE
    affected_versions: list[str] = Field(default_factory=list)
    fixed_version: Optional[str] = None
    reference_url: str = ""


class LicenseResult(BaseModel):
    """License metadata for a package."""
    package_name: str
    version: str
    license_spdx: str = Field(default="UNKNOWN", description="SPDX identifier")
    is_allowed: bool = False
    policy_source: str = Field(
        default="POLICY.md",
        description="Where the allow/block decision came from",
    )


class RemediationAction(BaseModel):
    """A single remediation step proposed by Agent-Fixer."""
    package_name: str
    current_version: str
    recommended_version: Optional[str] = None
    alternative_package: Optional[str] = None
    action: ActionType = ActionType.BLOCK
    reason: str = ""
    file_path: str = ""
    diff_snippet: str = Field(
        default="",
        description="Suggested file change as a unified diff fragment",
    )
    license_verified: bool = Field(
        default=False,
        description="Whether the fix itself was verified for license compliance",
    )


class DependencyAudit(BaseModel):
    """Full audit result for one dependency."""
    delta: DependencyDelta
    vulnerabilities: list[VulnerabilityResult] = Field(default_factory=list)
    license: Optional[LicenseResult] = None
    remediation: Optional[RemediationAction] = None
    model_used: str = Field(
        default="",
        description="Which model handled this dependency (flash / claude)",
    )


class AuditReport(BaseModel):
    """Top-level report aggregating all dependency audits for an MR."""
    mr_iid: int
    project_id: int
    project_url: str = ""
    source_branch: str = ""
    total_scanned: int = 0
    compliant: int = 0
    warnings: int = 0
    blockers: int = 0
    audits: list[DependencyAudit] = Field(default_factory=list)
    remediations_created: int = 0
    reasoning_log: str = Field(
        default="",
        description="Full chain-of-thought reasoning for the Logic Disclosure",
    )


# ── Webhook Payloads ─────────────────────────────────────────


class MergeRequestEvent(BaseModel):
    """Simplified GitLab MR webhook payload."""
    object_kind: str = "merge_request"
    project_id: int = 0
    project_url: str = ""
    mr_iid: int = Field(default=0, alias="merge_request_iid")
    source_branch: str = ""
    target_branch: str = ""
    action: str = Field(
        default="open",
        description="open | update | merge | close",
    )
    author_username: str = ""
    changed_files: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
