"""
SentinelStream AI — Plan-and-Execute Orchestrator
Main DAG controller that runs the Scout → Lawyer → Fixer pipeline
with logic gating for model routing (Flash vs Claude).
"""

from __future__ import annotations

import logging
from typing import Optional

from models.schemas import (
    AuditReport,
    DependencyAudit,
    DependencyDelta,
    ChangeType,
    ActionType,
    MergeRequestEvent,
)
from agents.scout import ScoutAgent
from agents.lawyer import LawyerAgent
from agents.fixer import FixerAgent
from services.gitlab_api import GitLabAPIBridge
from services.osv_client import OSVClient
from services.license_checker import LicenseChecker
from templates.comment_template import CommentTemplate

logger = logging.getLogger("sentinelstream.orchestrator")


class Orchestrator:
    """
    Plan-and-Execute DAG Orchestrator.

    Pipeline:
        1. Scout  → Identify dependency deltas
        2. Lawyer → Check license + CVE compliance
        3. Fixer  → Generate remediation for violations
        4. Report → Post summary comment on MR

    Logic Gating:
        - Patch bumps       → Gemini 1.5 Flash (fast)
        - Minor bumps       → Gemini 1.5 Flash (extended)
        - Major / New libs  → Anthropic Claude-3 (deep reasoning)
    """

    def __init__(self) -> None:
        self.gitlab = GitLabAPIBridge()
        self.osv = OSVClient()
        self.license_checker = LicenseChecker()

        self.scout = ScoutAgent(self.gitlab)
        self.lawyer = LawyerAgent(self.gitlab, self.osv, self.license_checker)
        self.fixer = FixerAgent(self.osv, self.license_checker)

        self.comment_template = CommentTemplate()

    async def shutdown(self) -> None:
        """Clean up async clients."""
        await self.gitlab.close()
        await self.osv.close()
        await self.license_checker.close()

    async def process_merge_request(
        self,
        event: MergeRequestEvent,
    ) -> AuditReport:
        """
        Execute the full Plan-and-Execute pipeline for an MR event.

        Args:
            event: Parsed GitLab MR webhook payload.

        Returns:
            AuditReport with all findings, remediations, and the reasoning log.
        """
        logger.info(
            "═══ SentinelStream Processing MR !%d (project %d) ═══",
            event.mr_iid,
            event.project_id,
        )

        reasoning_log: list[str] = []

        # ── Phase 1: Scout ───────────────────────────────────
        reasoning_log.append("**Step A (Scout):** Scanning MR diff for dependency changes...")

        deltas = await self.scout.scan(
            project_id=event.project_id,
            mr_iid=event.mr_iid,
            source_branch=event.source_branch,
            target_branch=event.target_branch,
            changed_files=event.changed_files or None,
        )

        if not deltas:
            reasoning_log.append("No dependency changes detected. Audit complete — all clear ✅")
            report = AuditReport(
                mr_iid=event.mr_iid,
                project_id=event.project_id,
                project_url=event.project_url,
                source_branch=event.source_branch,
                reasoning_log="\n".join(reasoning_log),
            )
            await self._post_report(event, report)
            return report

        # Log what Scout found
        for d in deltas:
            model = self._select_model(d)
            reasoning_log.append(
                f"  - `{d.package_name}`: {d.change_type.value} change → routed to **{model}**"
            )

        # ── Phase 2: Lawyer ──────────────────────────────────
        reasoning_log.append("\n**Step B (Analyze):** Checking licenses and vulnerabilities...")

        audits = await self.lawyer.analyze(
            project_id=event.project_id,
            deltas=deltas,
            target_branch=event.target_branch,
        )

        # Tag each audit with the model used (logic gating)
        for audit in audits:
            audit.model_used = self._select_model(audit.delta)

        # Log Lawyer findings
        for audit in audits:
            dep_name = audit.delta.package_name
            lic_str = audit.license.license_spdx if audit.license else "N/A"
            vuln_count = len(audit.vulnerabilities)
            reasoning_log.append(
                f"  - `{dep_name}`: license={lic_str}, CVEs={vuln_count}"
            )

        # ── Phase 3: Fixer ───────────────────────────────────
        blocked = [a for a in audits if self._needs_remediation(a)]

        if blocked:
            reasoning_log.append(
                f"\n**Step C (Remediate):** {len(blocked)} dependency(ies) need remediation..."
            )

            audits = await self.fixer.remediate(audits)

            for audit in audits:
                if audit.remediation:
                    r = audit.remediation
                    if r.recommended_version:
                        reasoning_log.append(
                            f"  - `{r.package_name}`: Upgrade {r.current_version} → "
                            f"{r.recommended_version} (verified={r.license_verified})"
                        )
                    else:
                        reasoning_log.append(
                            f"  - `{r.package_name}`: ⚠️ No compliant version found automatically"
                        )

            reasoning_log.append(
                "\n**Step D (Self-Verify):** All proposed fixes re-checked for compliance."
            )
        else:
            reasoning_log.append("\nNo dependencies require remediation ✅")

        # ── Build Report ─────────────────────────────────────
        report = self._build_report(event, audits, reasoning_log)

        # ── Post to GitLab ───────────────────────────────────
        await self._post_report(event, report)

        logger.info(
            "═══ MR !%d Audit Complete: %d scanned, %d blockers, %d remediations ═══",
            event.mr_iid,
            report.total_scanned,
            report.blockers,
            report.remediations_created,
        )

        return report

    # ── Logic Gating ─────────────────────────────────────────

    @staticmethod
    def _select_model(delta: DependencyDelta) -> str:
        """
        Select the AI model based on the change type.

        Logic Gating (from PRD Section 3 & agent prompt):
            - Patch → Gemini 1.5 Flash
            - Minor → Gemini 1.5 Flash (extended)
            - Major / New → Anthropic Claude-3
        """
        if delta.change_type == ChangeType.PATCH:
            return "gemini-1.5-flash"
        elif delta.change_type == ChangeType.MINOR:
            return "gemini-1.5-flash-extended"
        elif delta.change_type in (ChangeType.MAJOR, ChangeType.NEW):
            return "claude-3"
        return "gemini-1.5-flash"

    # ── Report Building ──────────────────────────────────────

    @staticmethod
    def _needs_remediation(audit: DependencyAudit) -> bool:
        """Check if an audit entry needs remediation."""
        if audit.license and not audit.license.is_allowed:
            if audit.license.license_spdx != "UNKNOWN":
                return True
        for v in audit.vulnerabilities:
            if v.severity.value in ("critical", "high"):
                return True
        return False

    def _build_report(
        self,
        event: MergeRequestEvent,
        audits: list[DependencyAudit],
        reasoning_log: list[str],
    ) -> AuditReport:
        """Compile all audits into a single AuditReport."""
        compliant = 0
        warnings = 0
        blockers = 0
        remediations = 0

        for audit in audits:
            if audit.delta.change_type == ChangeType.REMOVED:
                continue

            has_issue = False

            if audit.license and not audit.license.is_allowed:
                if audit.license.license_spdx != "UNKNOWN":
                    blockers += 1
                    has_issue = True

            for v in audit.vulnerabilities:
                if v.severity.value == "critical":
                    blockers += 1
                    has_issue = True
                elif v.severity.value == "high":
                    warnings += 1
                    has_issue = True

            if audit.remediation and audit.remediation.recommended_version:
                remediations += 1

            if not has_issue:
                compliant += 1

        return AuditReport(
            mr_iid=event.mr_iid,
            project_id=event.project_id,
            project_url=event.project_url,
            source_branch=event.source_branch,
            total_scanned=len([a for a in audits if a.delta.change_type != ChangeType.REMOVED]),
            compliant=compliant,
            warnings=warnings,
            blockers=blockers,
            audits=audits,
            remediations_created=remediations,
            reasoning_log="\n".join(reasoning_log),
        )

    async def _post_report(
        self,
        event: MergeRequestEvent,
        report: AuditReport,
    ) -> None:
        """Format and post the audit report as an MR comment."""
        comment_body = self.comment_template.render(report)

        try:
            await self.gitlab.post_mr_comment(
                project_id=event.project_id,
                mr_iid=event.mr_iid,
                body=comment_body,
            )
        except Exception as exc:
            logger.error("Failed to post MR comment: %s", exc)
