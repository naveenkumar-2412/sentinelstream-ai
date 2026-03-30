"""
SentinelStream AI — GitLab API Bridge
Wraps the GitLab REST API for MR operations: fetching diffs, posting comments,
creating branches, and suggesting changes.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger("sentinelstream.gitlab")


class GitLabAPIBridge:
    """Async client for GitLab REST API v4."""

    def __init__(self) -> None:
        self.base_url = f"{settings.gitlab_url}/api/v4"
        self.headers = {"PRIVATE-TOKEN": settings.gitlab_token}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── MR Diff ──────────────────────────────────────────────

    async def get_mr_changes(self, project_id: int, mr_iid: int) -> dict:
        """Fetch the list of changed files in an MR."""
        client = await self._get_client()
        resp = await client.get(
            f"/projects/{project_id}/merge_requests/{mr_iid}/changes"
        )
        resp.raise_for_status()
        return resp.json()

    async def get_file_content(
        self,
        project_id: int,
        file_path: str,
        ref: str = "main",
    ) -> str:
        """Fetch raw file content from a specific branch."""
        client = await self._get_client()
        import urllib.parse

        encoded_path = urllib.parse.quote(file_path, safe="")
        resp = await client.get(
            f"/projects/{project_id}/repository/files/{encoded_path}/raw",
            params={"ref": ref},
        )
        resp.raise_for_status()
        return resp.text

    # ── Comments ─────────────────────────────────────────────

    async def post_mr_comment(
        self,
        project_id: int,
        mr_iid: int,
        body: str,
    ) -> dict:
        """Post a note (comment) on an MR."""
        client = await self._get_client()
        resp = await client.post(
            f"/projects/{project_id}/merge_requests/{mr_iid}/notes",
            json={"body": body},
        )
        resp.raise_for_status()
        logger.info("Posted comment on MR !%d (project %d)", mr_iid, project_id)
        return resp.json()

    # ── Suggestions ──────────────────────────────────────────

    async def create_mr_suggestion(
        self,
        project_id: int,
        mr_iid: int,
        file_path: str,
        old_line: int,
        new_content: str,
        comment: str = "SentinelStream Remediation",
    ) -> dict:
        """
        Create an inline suggestion on a specific line of the MR diff.
        Uses the GitLab Suggestions API (markdown ```suggestion blocks).
        """
        suggestion_body = (
            f"{comment}\n\n"
            f"```suggestion:-0+0\n"
            f"{new_content}\n"
            f"```"
        )

        # Get the diff refs for positioning
        client = await self._get_client()
        mr_data = await client.get(
            f"/projects/{project_id}/merge_requests/{mr_iid}"
        )
        mr_data.raise_for_status()
        mr_json = mr_data.json()
        diff_refs = mr_json.get("diff_refs", {})

        resp = await client.post(
            f"/projects/{project_id}/merge_requests/{mr_iid}/discussions",
            json={
                "body": suggestion_body,
                "position": {
                    "base_sha": diff_refs.get("base_sha", ""),
                    "head_sha": diff_refs.get("head_sha", ""),
                    "start_sha": diff_refs.get("start_sha", ""),
                    "position_type": "text",
                    "new_path": file_path,
                    "new_line": old_line,
                },
            },
        )
        resp.raise_for_status()
        logger.info("Created suggestion on %s:%d", file_path, old_line)
        return resp.json()

    # ── Branches & Commits ───────────────────────────────────

    async def create_branch(
        self,
        project_id: int,
        branch_name: str,
        ref: str = "main",
    ) -> dict:
        """Create a new branch from a ref."""
        client = await self._get_client()
        resp = await client.post(
            f"/projects/{project_id}/repository/branches",
            json={"branch": branch_name, "ref": ref},
        )
        resp.raise_for_status()
        logger.info("Created branch '%s' from '%s'", branch_name, ref)
        return resp.json()

    async def commit_file_change(
        self,
        project_id: int,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> dict:
        """Update a file on a branch via the Commits API."""
        client = await self._get_client()
        resp = await client.post(
            f"/projects/{project_id}/repository/commits",
            json={
                "branch": branch,
                "commit_message": commit_message,
                "actions": [
                    {
                        "action": "update",
                        "file_path": file_path,
                        "content": content,
                    }
                ],
            },
        )
        resp.raise_for_status()
        logger.info("Committed change to %s on branch '%s'", file_path, branch)
        return resp.json()

    async def create_merge_request(
        self,
        project_id: int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> dict:
        """Create a remediation Merge Request."""
        client = await self._get_client()
        resp = await client.post(
            f"/projects/{project_id}/merge_requests",
            json={
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "description": description,
                "remove_source_branch": True,
                "labels": "sentinelstream,remediation,security",
            },
        )
        resp.raise_for_status()
        logger.info(
            "Created remediation MR: %s → %s", source_branch, target_branch
        )
        return resp.json()
