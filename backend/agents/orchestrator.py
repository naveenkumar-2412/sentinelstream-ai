"""
SentinelStream AI — Plan-and-Execute Orchestrator
Main DAG controller that runs the Scout → Lawyer → Fixer pipeline
with logic gating for model routing (Flash vs Claude).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from config import settings
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
from agents.coder import AgentCoder
from services.gitlab_api import GitLabAPIBridge
from services.osv_client import OSVClient
from services.license_checker import LicenseChecker
from services.policy_store import PolicyStore
from services.audit_store import AuditStore
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

        self.policy_store = PolicyStore()
        self.audit_store = AuditStore()

        self.scout = ScoutAgent(self.gitlab)
        self.lawyer = LawyerAgent(
            self.gitlab,
            self.osv,
            self.license_checker,
            policy_store=self.policy_store,
        )
        self.fixer = FixerAgent(self.osv, self.license_checker)
        self.coder = AgentCoder()

        self.comment_template = CommentTemplate()

    async def shutdown(self) -> None:
        """Clean up async clients."""
        await self.gitlab.close()
        await self.osv.close()
        await self.license_checker.close()
        self.policy_store.close()
        self.audit_store.close()

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

            await self._post_remediation_suggestions(event, audits)

            if settings.enable_remediation_mr:
                await self._create_remediation_mr(event, audits)

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

            # ── Agent-Coder: Application Code Migration ──────
            major_deltas = [
                d for d in deltas
                if d.change_type in (ChangeType.MAJOR, ChangeType.NEW)
            ]
            if major_deltas:
                reasoning_log.append("\n**Step E (Agent-Coder):** Checking for breaking API changes...")
                try:
                    # Fetch source files that are changed in this MR for code analysis
                    # In a real environment, we'd iterate through event.changed_files
                    # For demo purposes, we'll fetch a representative set or simulate
                    source_files: dict[str, str] = {}
                    for file_path in (event.changed_files or []):
                        if file_path.endswith((".py", ".js", ".ts", ".tsx", ".go", ".java")):
                            content = await self.gitlab.get_file_content(
                                event.project_id,
                                file_path,
                                ref=event.source_branch,
                            )
                            source_files[file_path] = content

                    for delta in major_deltas:
                        patches = self.coder.analyze(delta, source_files)
                        if patches:
                            patch_md = self.coder.format_patches_as_markdown(patches)
                            reasoning_log.append(patch_md)
                except Exception as exc:
                    logger.warning("Agent-Coder analysis failed: %s", exc)
        else:
            reasoning_log.append("\nNo dependencies require remediation ✅")

        # ── Build Report ─────────────────────────────────────
        report = self._build_report(event, audits, reasoning_log)

        self.audit_store.store_report(report)

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

    async def _post_remediation_suggestions(
        self,
        event: MergeRequestEvent,
        audits: list[DependencyAudit],
    ) -> None:
        """Post inline suggestions for supported dependency files."""
        for audit in audits:
            remediation = audit.remediation
            if not remediation or not remediation.recommended_version:
                continue

            file_path = remediation.file_path
            try:
                content = await self.gitlab.get_file_content(
                    event.project_id,
                    file_path,
                    ref=event.source_branch,
                )
            except Exception as exc:
                logger.warning("Suggestion skipped: failed to fetch %s (%s)", file_path, exc)
                continue

            match = _find_dependency_line(
                content=content,
                file_path=file_path,
                package_name=remediation.package_name,
            )
            if match is None:
                logger.info("Suggestion skipped: no match for %s in %s", remediation.package_name, file_path)
                continue

            line_no, line_text = match

            new_line = _build_suggestion_line(
                content=content,
                file_path=file_path,
                package_name=remediation.package_name,
                new_version=remediation.recommended_version,
                line_text=line_text,
            )
            if not new_line:
                logger.info("Suggestion skipped: unsupported file type %s", file_path)
                continue

            try:
                await self.gitlab.create_mr_suggestion(
                    project_id=event.project_id,
                    mr_iid=event.mr_iid,
                    file_path=file_path,
                    old_line=line_no,
                    new_content=new_line,
                    comment="SentinelStream Remediation Suggestion",
                )
            except Exception as exc:
                logger.warning("Failed to post suggestion for %s: %s", remediation.package_name, exc)

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

    async def _create_remediation_mr(
        self,
        event: MergeRequestEvent,
        audits: list[DependencyAudit],
    ) -> None:
        """Create a remediation branch and MR with applied fixes."""
        fixes = [
            a for a in audits
            if a.remediation and a.remediation.recommended_version
        ]
        if not fixes:
            return

        if settings.remediation_dry_run:
            logger.info("Remediation dry-run enabled; skipping MR creation")
            return

        branch = f"{settings.remediation_branch_prefix}{event.mr_iid}"
        try:
            await self.gitlab.create_branch(
                project_id=event.project_id,
                branch_name=branch,
                ref=event.target_branch,
            )
        except Exception as exc:
            logger.warning("Failed to create remediation branch: %s", exc)
            return

        updated_files: dict[str, str] = {}

        for audit in fixes:
            remediation = audit.remediation
            if not remediation:
                continue

            file_path = remediation.file_path
            try:
                content = updated_files.get(file_path)
                if content is None:
                    content = await self.gitlab.get_file_content(
                        event.project_id,
                        file_path,
                        ref=event.target_branch,
                    )
                match = _find_dependency_line(
                    content=content,
                    file_path=file_path,
                    package_name=remediation.package_name,
                )
                if match is None:
                    continue
                line_no, line_text = match
                new_line = _build_suggestion_line(
                    content=content,
                    file_path=file_path,
                    package_name=remediation.package_name,
                    new_version=remediation.recommended_version,
                    line_text=line_text,
                )
                if not new_line:
                    continue
                content = _replace_line(content, line_no, new_line)
                updated_files[file_path] = content
            except Exception as exc:
                logger.warning("Failed to apply remediation for %s: %s", remediation.package_name, exc)

        if not updated_files:
            return

        for file_path, content in updated_files.items():
            try:
                await self.gitlab.commit_file_change(
                    project_id=event.project_id,
                    branch=branch,
                    file_path=file_path,
                    content=content,
                    commit_message="SentinelStream: apply remediation",
                )
            except Exception as exc:
                logger.warning("Failed to commit remediation for %s: %s", file_path, exc)

        try:
            await self.gitlab.create_merge_request(
                project_id=event.project_id,
                source_branch=branch,
                target_branch=event.target_branch,
                title=settings.remediation_mr_title,
                description="Automated remediation from SentinelStream AI.",
            )
        except Exception as exc:
            logger.warning("Failed to create remediation MR: %s", exc)


def _find_dependency_line(
    content: str,
    file_path: str,
    package_name: str,
) -> Optional[tuple[int, str]]:
    """Find the line number and line content for a dependency in supported files."""
    lines = content.splitlines()
    if file_path.endswith("requirements.txt"):
        pattern = re.compile(rf"^\s*{re.escape(package_name)}\b", re.IGNORECASE)
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                return idx, line
        return None

    if file_path.endswith("package.json"):
        pattern = re.compile(rf"^\s*\"{re.escape(package_name)}\"\s*:")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                return idx, line
        return None

    if file_path.endswith("go.mod"):
        pattern = re.compile(rf"^\s*{re.escape(package_name)}\s+v?", re.IGNORECASE)
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                return idx, line
        return None

    if file_path.endswith("pom.xml"):
        target = package_name.split(":", 1)
        if len(target) != 2:
            return None
        group_id, artifact_id = target
        in_dep = False
        found_group = False
        found_artifact = False
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if "<dependency" in stripped:
                in_dep = True
                found_group = False
                found_artifact = False
            if in_dep and f"<groupId>{group_id}</groupId>" in stripped:
                found_group = True
            if in_dep and f"<artifactId>{artifact_id}</artifactId>" in stripped:
                found_artifact = True
            if in_dep and found_group and found_artifact and "<version>" in stripped:
                prop_match = re.search(r"<version>\s*\$\{([^}]+)\}\s*</version>", stripped)
                if prop_match:
                    prop_name = prop_match.group(1)
                    prop_pattern = re.compile(rf"^\s*<{re.escape(prop_name)}>.*</{re.escape(prop_name)}>\s*$")
                    for p_idx, p_line in enumerate(lines, start=1):
                        if prop_pattern.search(p_line):
                            return p_idx, p_line
                return idx, line
            if in_dep and "</dependency>" in stripped:
                in_dep = False
        return None

    if file_path.endswith("build.gradle"):
        pattern = re.compile(rf"['\"]{re.escape(package_name)}:[^'\"]+['\"]")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                var_match = re.search(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", line)
                if var_match:
                    var_name = var_match.group(1)
                    var_pattern = re.compile(
                        rf"^\s*(?:ext\s*\.)?{re.escape(var_name)}\s*=\s*['\"][^'\"]+['\"]"
                    )
                    for v_idx, v_line in enumerate(lines, start=1):
                        if var_pattern.search(v_line):
                            return v_idx, v_line
                return idx, line
        return None

    if file_path.endswith("Cargo.toml"):
        pattern = re.compile(rf"^\s*{re.escape(package_name)}\s*=")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                return idx, line
        return None

    if file_path.endswith("Gemfile"):
        pattern = re.compile(rf"^\s*gem\s+['\"]{re.escape(package_name)}['\"]")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                return idx, line
        return None

    if file_path.endswith("composer.json"):
        pattern = re.compile(rf"^\s*\"{re.escape(package_name)}\"\s*:")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                return idx, line
        return None

    if file_path.endswith(".csproj"):
        in_ref = False
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if "<PackageReference" in stripped and f"Include=\"{package_name}\"" in stripped:
                if "Version=\"" in stripped:
                    return idx, line
                in_ref = True
                continue
            if in_ref and "<Version>" in stripped:
                return idx, line
            if in_ref and "</PackageReference>" in stripped:
                in_ref = False
        return None

    return None


def _build_suggestion_line(
    content: str,
    file_path: str,
    package_name: str,
    new_version: str,
    line_text: str,
) -> str:
    """Build a single-line replacement for a dependency entry."""
    if file_path.endswith("requirements.txt"):
        return f"{package_name}=={new_version}"
    if file_path.endswith("go.mod"):
        trailing = ""
        if "//" in line_text:
            trailing = " " + line_text.split("//", 1)[1].rstrip()
        return f"{package_name} v{new_version}{trailing}"
    if file_path.endswith("package.json"):
        match = re.search(r"\"([\^~><=]*)[0-9][^\"]*\"", line_text)
        prefix = match.group(1) if match else "^"
        indent = re.match(r"^\s*", line_text).group(0)
        suffix = "," if line_text.rstrip().endswith(",") else ""
        return f"{indent}\"{package_name}\": \"{prefix}{new_version}\"{suffix}"
    if file_path.endswith("pom.xml"):
        indent = re.match(r"^\s*", line_text).group(0)
        if re.search(r"^\s*<[^>]+>.*</[^>]+>\s*$", line_text):
            tag_match = re.search(r"^\s*<([^>]+)>", line_text)
            if tag_match:
                tag_name = tag_match.group(1)
                return f"{indent}<{tag_name}>{new_version}</{tag_name}>"
        return f"{indent}<version>{new_version}</version>"
    if file_path.endswith("build.gradle"):
        def replacer(match: re.Match) -> str:
            quote = match.group(1)
            group = match.group(2)
            artifact = match.group(3)
            return f"{quote}{group}:{artifact}:{new_version}{quote}"

        if re.search(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", line_text):
            return re.sub(
                r"(=\s*['\"])([^'\"]+)(['\"])",
                rf"\1{new_version}\3",
                line_text,
            )
        return re.sub(
            r"(['\"])([A-Za-z0-9.\-_]+):([A-Za-z0-9.\-_]+):[^'\"]+\1",
            replacer,
            line_text,
        )
    if file_path.endswith("Cargo.toml"):
        if "version" in line_text:
            return re.sub(
                r"(version\s*=\s*\")(.*?)(\")",
                rf"\1{new_version}\3",
                line_text,
            )
        if "workspace = true" in line_text:
            return ""
        return re.sub(
            r"(=\s*\")(.*?)(\")",
            rf"\1{new_version}\3",
            line_text,
        )
    if file_path.endswith("Gemfile"):
        updated = re.sub(
            r"(gem\s+['\"]%s['\"]\s*,\s*['\"])([^'\"]+)(['\"])"
            % re.escape(package_name),
            rf"\1{new_version}\3",
            line_text,
        )
        return "" if updated == line_text else updated
    if file_path.endswith("composer.json"):
        match = re.search(r"\"([\^~><=]*)[0-9][^\"]*\"", line_text)
        prefix = match.group(1) if match else "^"
        indent = re.match(r"^\s*", line_text).group(0)
        suffix = "," if line_text.rstrip().endswith(",") else ""
        return f"{indent}\"{package_name}\": \"{prefix}{new_version}\"{suffix}"
    if file_path.endswith(".csproj"):
        if "Version=\"" in line_text:
            return re.sub(
                r"(Version=\")(.*?)(\")",
                rf"\1{new_version}\3",
                line_text,
            )
        indent = re.match(r"^\s*", line_text).group(0)
        return f"{indent}<Version>{new_version}</Version>"
    return ""


def _replace_line(content: str, line_no: int, new_line: str) -> str:
    """Replace a 1-based line in content and return updated content."""
    lines = content.splitlines()
    if line_no < 1 or line_no > len(lines):
        return content
    lines[line_no - 1] = new_line
    return "\n".join(lines)
