"""
SentinelStream AI — GitLab Markdown Comment Template
Renders AuditReport into the PRD's Design & Visual Identity format:
summary table, per-dependency detail, Logic Disclosure, and Quick Actions.
"""

from __future__ import annotations

from models.schemas import (
    AuditReport,
    DependencyAudit,
    ActionType,
    ChangeType,
    Severity,
)


class CommentTemplate:
    """Renders audit results as GitLab-native Markdown comments."""

    def render(self, report: AuditReport) -> str:
        """Generate the full MR comment body."""
        sections = [
            self._sentinel_header(),
            self._summary_table(report),
            self._dependency_table(report),
            self._logic_disclosure(report),
            self._quick_actions(report),
        ]
        return "\n\n".join(s for s in sections if s)

    # ── Header ───────────────────────────────────────────────

    @staticmethod
    def _sentinel_header() -> str:
        return (
            "## 🛡️ SentinelStream AI — Governance Audit\n"
            "> Autonomous compliance check triggered by dependency changes."
        )

    # ── Summary Table ────────────────────────────────────────

    @staticmethod
    def _summary_table(report: AuditReport) -> str:
        return (
            "| 🛡️ SentinelStream Audit | Status |\n"
            "|--------------------------|--------|\n"
            f"| Dependencies Scanned     | {report.total_scanned} |\n"
            f"| Compliant                | {report.compliant} ✅ |\n"
            f"| Warnings                 | {report.warnings} ⚠️ |\n"
            f"| Blockers                 | {report.blockers} 🔴 |\n"
            f"| Remediation Suggestions  | {report.remediations_created} |"
        )

    # ── Per-Dependency Table ─────────────────────────────────

    @staticmethod
    def _dependency_table(report: AuditReport) -> str:
        if not report.audits:
            return ""

        rows = [
            "### Dependency Details\n",
            "| Package | Version | License | CVE Status | Action |",
            "|---------|---------|---------|------------|--------|",
        ]

        for audit in report.audits:
            if audit.delta.change_type == ChangeType.REMOVED:
                continue

            dep = audit.delta.new
            if dep is None:
                continue

            # License column
            if audit.license:
                lic = audit.license.license_spdx
                lic_icon = "✅" if audit.license.is_allowed else "🔴"
                lic_str = f"{lic} {lic_icon}"
            else:
                lic_str = "—"

            # CVE column
            if audit.vulnerabilities:
                worst = max(audit.vulnerabilities, key=lambda v: v.cvss_score)
                sev_icon = _severity_icon(worst.severity)
                cve_str = f"{worst.cve_id} ({sev_icon} {worst.severity.value.title()})"
            else:
                cve_str = "None ✅"

            # Action column
            if audit.remediation and audit.remediation.recommended_version:
                action_str = (
                    f"🔴 Blocked → Upgrade to `{audit.remediation.recommended_version}`"
                )
            elif audit.remediation:
                action_str = "🔴 Blocked — Manual review needed"
            else:
                action_str = "✅ Pass"

            rows.append(
                f"| `{dep.name}` | {dep.version} | {lic_str} | {cve_str} | {action_str} |"
            )

        return "\n".join(rows)

    # ── Logic Disclosure ─────────────────────────────────────

    @staticmethod
    def _logic_disclosure(report: AuditReport) -> str:
        if not report.reasoning_log:
            return ""

        return (
            "<details>\n"
            "<summary>🔍 Show SentinelStream's Reasoning</summary>\n\n"
            f"{report.reasoning_log}\n\n"
            "</details>"
        )

    # ── Quick Actions ────────────────────────────────────────

    @staticmethod
    def _quick_actions(report: AuditReport) -> str:
        actions: list[str] = []

        # Collect remediation diffs
        has_fixes = False
        for audit in report.audits:
            if audit.remediation and audit.remediation.recommended_version:
                has_fixes = True
                r = audit.remediation
                actions.append(
                    f"- **`{r.package_name}`**: "
                    f"`{r.current_version}` → `{r.recommended_version}` "
                    f"in `{r.file_path}`"
                )

        if not has_fixes:
            return (
                "---\n"
                "**🚀 All clear!** No remediation needed. "
                "Consider assigning a reviewer to finalize this MR.\n\n"
                "`/assign_reviewer @security-team`"
            )

        actions_list = "\n".join(actions)

        return (
            "---\n"
            "### 🚀 Suggested Fixes\n\n"
            f"{actions_list}\n\n"
            "**Apply these fixes:**\n"
            "1. Use the **Apply suggestion** button above for each inline suggestion, or\n"
            "2. Run the following command to request a review:\n\n"
            "```\n"
            "/assign_reviewer @security-team\n"
            "```\n\n"
            "*SentinelStream AI — Autonomous DevOps Governance*"
        )


# ── Helpers ──────────────────────────────────────────────────

def _severity_icon(severity: Severity) -> str:
    return {
        Severity.CRITICAL: "🔴",
        Severity.HIGH: "🟠",
        Severity.MEDIUM: "🟡",
        Severity.LOW: "⚪",
        Severity.NONE: "✅",
    }.get(severity, "❓")
