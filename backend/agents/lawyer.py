"""
SentinelStream AI — Agent-Lawyer
Reads POLICY.md, checks each dependency's license, queries OSV for CVEs,
and produces a compliance verdict for each dependency delta.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from models.schemas import (
    DependencyDelta,
    DependencyAudit,
    ChangeType,
    Severity,
    ActionType,
)
from services.gitlab_api import GitLabAPIBridge
from services.osv_client import OSVClient
from services.license_checker import LicenseChecker

logger = logging.getLogger("sentinelstream.lawyer")

# Severity → Action mapping (from POLICY.md Section 3)
_SEVERITY_ACTION = {
    Severity.CRITICAL: ActionType.BLOCK,
    Severity.HIGH: ActionType.WARN,
    Severity.MEDIUM: ActionType.INFO,
    Severity.LOW: ActionType.PASS,
    Severity.NONE: ActionType.PASS,
}


class LawyerAgent:
    """
    Agent-Lawyer: Evaluates each dependency delta for compliance.

    Responsibilities:
        1. Load POLICY.md from the repository (Zero Trust fallback).
        2. For each delta: query license + query vulnerabilities.
        3. Determine action: BLOCK / WARN / INFO / PASS.
    """

    def __init__(
        self,
        gitlab: GitLabAPIBridge,
        osv: OSVClient,
        license_checker: LicenseChecker,
    ) -> None:
        self.gitlab = gitlab
        self.osv = osv
        self.license_checker = license_checker
        self._policy_loaded = False

    async def _load_policy(self, project_id: int, branch: str = "main") -> None:
        """
        Attempt to load POLICY.md from the repo.
        Falls back to Zero Trust if not found.
        """
        if self._policy_loaded:
            return

        try:
            policy_content = await self.gitlab.get_file_content(
                project_id,
                ".gitlab/agents/sentinelstream/POLICY.md",
                ref=branch,
            )
            # Parse allowed licenses from POLICY.md
            allowed = _parse_allowed_licenses(policy_content)
            if allowed:
                self.license_checker.set_allowed_licenses(allowed)
                logger.info("Loaded POLICY.md: %d allowed licenses", len(allowed))
            else:
                logger.warning("POLICY.md found but no licenses parsed; using defaults")
        except Exception:
            logger.warning(
                "POLICY.md not found in repo — using Zero Trust defaults"
            )

        self._policy_loaded = True

    async def analyze(
        self,
        project_id: int,
        deltas: list[DependencyDelta],
        target_branch: str = "main",
    ) -> list[DependencyAudit]:
        """
        Analyze each dependency delta for license and vulnerability compliance.

        Returns:
            List of DependencyAudit with populated license/vulnerability data.
        """
        await self._load_policy(project_id, target_branch)

        audits: list[DependencyAudit] = []

        for delta in deltas:
            # Skip removed dependencies — no action needed
            if delta.change_type == ChangeType.REMOVED:
                audits.append(DependencyAudit(
                    delta=delta,
                    model_used="none",
                ))
                continue

            dep = delta.new
            if dep is None:
                continue

            # ── Step B.1: License Check ──
            license_result = await self.license_checker.check_license(
                package_name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
            )

            # ── Step B.2: Vulnerability Check ──
            vulns = await self.osv.query_vulnerabilities(
                package_name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
            )

            # ── Determine worst-case action ──
            action = ActionType.PASS

            # License violation → BLOCK
            if not license_result.is_allowed and license_result.license_spdx != "UNKNOWN":
                action = ActionType.BLOCK

            # CVE severity escalation
            for v in vulns:
                vuln_action = _SEVERITY_ACTION.get(v.severity, ActionType.PASS)
                if _action_priority(vuln_action) > _action_priority(action):
                    action = vuln_action

            # Unknown license with vulns → escalate to WARN at minimum
            if license_result.license_spdx == "UNKNOWN" and vulns:
                if _action_priority(action) < _action_priority(ActionType.WARN):
                    action = ActionType.WARN

            audit = DependencyAudit(
                delta=delta,
                vulnerabilities=vulns,
                license=license_result,
            )

            logger.info(
                "Lawyer verdict: %s@%s → license=%s, vulns=%d, action=%s",
                dep.name,
                dep.version,
                license_result.license_spdx,
                len(vulns),
                action.value,
            )

            audits.append(audit)

        return audits


# ── Helpers ──────────────────────────────────────────────────

_ACTION_PRIORITY = {
    ActionType.PASS: 0,
    ActionType.INFO: 1,
    ActionType.WARN: 2,
    ActionType.BLOCK: 3,
}


def _action_priority(action: ActionType) -> int:
    return _ACTION_PRIORITY.get(action, 0)


def _parse_allowed_licenses(policy_content: str) -> list[str]:
    """Extract allowed SPDX license identifiers from POLICY.md."""
    licenses: list[str] = []
    in_allowed = False
    for line in policy_content.splitlines():
        if "Allowed Licenses" in line:
            in_allowed = True
            continue
        if "Blocked Licenses" in line:
            in_allowed = False
            continue
        if in_allowed:
            # Match lines like: | `MIT` | ✅ Allowed |
            match = re.search(r"`([A-Za-z0-9\-\.]+)`", line)
            if match:
                licenses.append(match.group(1))
    return licenses
