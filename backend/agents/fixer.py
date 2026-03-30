"""
SentinelStream AI — Agent-Fixer
Generates remediation actions for non-compliant dependencies.
Self-validates that fixes are themselves compliant (Step D).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from models.schemas import (
    DependencyAudit,
    RemediationAction,
    ActionType,
    Severity,
    ChangeType,
)
from services.osv_client import OSVClient
from services.license_checker import LicenseChecker

logger = logging.getLogger("sentinelstream.fixer")

MAX_REMEDIATION_ATTEMPTS = 3


class FixerAgent:
    """
    Agent-Fixer: Proposes remediation for blocked/warned dependencies.

    Responsibilities:
        1. For each BLOCK/WARN audit, find the nearest compliant version.
        2. Verify the proposed fix's license (Step D: Self-Verify).
        3. Generate diff snippets for the dependency file.
        4. If the fix is non-compliant, retry with the next candidate.
    """

    def __init__(
        self,
        osv: OSVClient,
        license_checker: LicenseChecker,
    ) -> None:
        self.osv = osv
        self.license_checker = license_checker

    async def remediate(
        self,
        audits: list[DependencyAudit],
    ) -> list[DependencyAudit]:
        """
        Process audits and attach RemediationAction to those needing fixes.

        Modifies and returns the same list with remediation data populated.
        """
        for audit in audits:
            # Only fix BLOCK or WARN verdicts with new/modified deps
            if audit.delta.change_type == ChangeType.REMOVED:
                continue
            if audit.delta.new is None:
                continue

            needs_fix = False
            reasons: list[str] = []

            # Check license violation
            if audit.license and not audit.license.is_allowed:
                if audit.license.license_spdx != "UNKNOWN":
                    needs_fix = True
                    reasons.append(
                        f"License `{audit.license.license_spdx}` is not in allowed list"
                    )

            # Check CVE severity
            for vuln in audit.vulnerabilities:
                if vuln.severity in (Severity.CRITICAL, Severity.HIGH):
                    needs_fix = True
                    reasons.append(
                        f"{vuln.cve_id} (CVSS {vuln.cvss_score}, {vuln.severity.value})"
                    )

            if not needs_fix:
                continue

            dep = audit.delta.new
            reason_str = "; ".join(reasons)

            # ── Try to find a compliant version ──
            remediation = await self._find_compliant_version(
                package_name=dep.name,
                current_version=dep.version,
                ecosystem=dep.ecosystem,
                file_path=dep.file_path,
                reason=reason_str,
                audit=audit,
            )

            audit.remediation = remediation
            logger.info(
                "Fixer: %s@%s → %s (verified=%s)",
                dep.name,
                dep.version,
                remediation.action.value,
                remediation.license_verified,
            )

        return audits

    async def _find_compliant_version(
        self,
        package_name: str,
        current_version: str,
        ecosystem,
        file_path: str,
        reason: str,
        audit: DependencyAudit,
    ) -> RemediationAction:
        """
        Search for the nearest compliant version (upgrade path).

        Step D (Self-Verify): After finding a candidate, verify its license
        and vulnerability status. Retry up to MAX_REMEDIATION_ATTEMPTS times.
        """
        # Collect candidate versions from OSV "fixed" fields
        candidates: list[str] = []
        for vuln in audit.vulnerabilities:
            if vuln.fixed_version:
                candidates.append(vuln.fixed_version)

        # Also try incrementing the patch version
        candidates.extend(_generate_upgrade_candidates(current_version))

        # Deduplicate and sort
        candidates = list(dict.fromkeys(candidates))

        for attempt, candidate_version in enumerate(candidates):
            if attempt >= MAX_REMEDIATION_ATTEMPTS:
                break

            logger.info(
                "Fixer: trying %s@%s (attempt %d/%d)",
                package_name,
                candidate_version,
                attempt + 1,
                MAX_REMEDIATION_ATTEMPTS,
            )

            # ── Step D: Self-Verify license ──
            lic = await self.license_checker.check_license(
                package_name=package_name,
                version=candidate_version,
                ecosystem=ecosystem,
            )

            if not lic.is_allowed and lic.license_spdx != "UNKNOWN":
                logger.warning(
                    "Fixer: %s@%s has blocked license %s — retrying",
                    package_name,
                    candidate_version,
                    lic.license_spdx,
                )
                continue

            # ── Step D: Self-Verify vulnerabilities ──
            new_vulns = await self.osv.query_vulnerabilities(
                package_name=package_name,
                version=candidate_version,
                ecosystem=ecosystem,
            )
            critical_vulns = [
                v for v in new_vulns
                if v.severity in (Severity.CRITICAL, Severity.HIGH)
            ]
            if critical_vulns:
                logger.warning(
                    "Fixer: %s@%s still has %d critical/high CVEs — retrying",
                    package_name,
                    candidate_version,
                    len(critical_vulns),
                )
                continue

            # ✅ This version passes all checks
            diff_snippet = _generate_diff(
                file_path=file_path,
                package_name=package_name,
                old_version=current_version,
                new_version=candidate_version,
            )

            return RemediationAction(
                package_name=package_name,
                current_version=current_version,
                recommended_version=candidate_version,
                action=ActionType.BLOCK,
                reason=reason,
                file_path=file_path,
                diff_snippet=diff_snippet,
                license_verified=True,
            )

        # No compliant version found
        return RemediationAction(
            package_name=package_name,
            current_version=current_version,
            recommended_version=None,
            action=ActionType.BLOCK,
            reason=f"{reason}. No compliant upgrade found automatically.",
            file_path=file_path,
            diff_snippet="",
            license_verified=False,
        )


# ── Helpers ──────────────────────────────────────────────────


def _generate_upgrade_candidates(version: str) -> list[str]:
    """Generate candidate upgrade versions from the current version."""
    try:
        parts = version.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return []

    candidates = [
        f"{major}.{minor}.{patch + 1}",  # Patch bump
        f"{major}.{minor}.{patch + 2}",  # Patch +2
        f"{major}.{minor + 1}.0",        # Minor bump
    ]
    return candidates


def _generate_diff(
    file_path: str,
    package_name: str,
    old_version: str,
    new_version: str,
) -> str:
    """Generate a suggested diff snippet based on the file type."""
    if file_path.endswith("requirements.txt"):
        return f"-{package_name}=={old_version}\n+{package_name}=={new_version}"
    elif file_path.endswith("package.json"):
        return (
            f'-    "{package_name}": "^{old_version}"\n'
            f'+    "{package_name}": "^{new_version}"'
        )
    elif file_path.endswith("go.mod"):
        return (
            f"-    {package_name} v{old_version}\n"
            f"+    {package_name} v{new_version}"
        )
    return f"Upgrade {package_name} from {old_version} to {new_version}"
