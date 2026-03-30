"""
SentinelStream AI — Agent-Scout
Identifies the "Delta": dependencies added, modified, or removed in an MR.
This is the first stage of the Plan-and-Execute DAG.
"""

from __future__ import annotations

import logging

from models.schemas import DependencyDelta, ChangeType
from parsers.dependency_parser import (
    detect_parser,
    parse_dependency_file,
    compute_deltas,
)
from services.gitlab_api import GitLabAPIBridge

logger = logging.getLogger("sentinelstream.scout")

# Files we care about
DEPENDENCY_FILES = {"requirements.txt", "package.json", "go.mod"}


class ScoutAgent:
    """
    Agent-Scout: Scans an MR diff to identify dependency changes.

    Responsibilities:
        1. Filter changed files to dependency manifests only.
        2. Fetch base (target branch) and head (source branch) versions.
        3. Parse both versions and compute the delta.
        4. Classify each change: patch / minor / major / new / removed.
    """

    def __init__(self, gitlab: GitLabAPIBridge) -> None:
        self.gitlab = gitlab

    async def scan(
        self,
        project_id: int,
        mr_iid: int,
        source_branch: str,
        target_branch: str,
        changed_files: list[str] | None = None,
    ) -> list[DependencyDelta]:
        """
        Scan the MR for dependency changes.

        Args:
            project_id: GitLab project ID.
            mr_iid: MR internal ID.
            source_branch: The MR's source branch.
            target_branch: The MR's target branch (usually 'main').
            changed_files: Optional pre-filtered list of changed file paths.

        Returns:
            List of DependencyDelta objects for each changed dependency.
        """
        # If changed_files not provided, fetch from GitLab
        if changed_files is None:
            mr_changes = await self.gitlab.get_mr_changes(project_id, mr_iid)
            changed_files = [
                change["new_path"]
                for change in mr_changes.get("changes", [])
            ]

        # Filter to only dependency files
        dep_files = [
            f for f in changed_files
            if any(f.endswith(df) for df in DEPENDENCY_FILES)
        ]

        if not dep_files:
            logger.info("MR !%d: No dependency files changed.", mr_iid)
            return []

        logger.info(
            "MR !%d: Found %d dependency file(s): %s",
            mr_iid,
            len(dep_files),
            dep_files,
        )

        all_deltas: list[DependencyDelta] = []

        for file_path in dep_files:
            if detect_parser(file_path) is None:
                continue

            # Fetch base version (target branch)
            try:
                base_content = await self.gitlab.get_file_content(
                    project_id, file_path, ref=target_branch
                )
            except Exception:
                base_content = ""  # File is new in this MR
                logger.info("File %s is new (not found on %s)", file_path, target_branch)

            # Fetch head version (source branch)
            try:
                head_content = await self.gitlab.get_file_content(
                    project_id, file_path, ref=source_branch
                )
            except Exception:
                head_content = ""  # File was deleted
                logger.info("File %s was deleted in %s", file_path, source_branch)

            # Parse both versions
            base_deps = parse_dependency_file(file_path, base_content)
            head_deps = parse_dependency_file(file_path, head_content)

            # Compute deltas
            deltas = compute_deltas(base_deps, head_deps)
            all_deltas.extend(deltas)

            logger.info(
                "File %s: %d base deps, %d head deps → %d deltas",
                file_path,
                len(base_deps),
                len(head_deps),
                len(deltas),
            )

        # Log summary
        summary = {ct.value: 0 for ct in ChangeType}
        for d in all_deltas:
            summary[d.change_type.value] += 1
        logger.info("Scout scan complete: %s", summary)

        return all_deltas
