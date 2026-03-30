"""
SentinelStream AI — FastAPI Application
Webhook endpoint for GitLab MR events.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager

from config import settings
from models.schemas import MergeRequestEvent
from agents.orchestrator import Orchestrator


# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sentinelstream")

# ── Orchestrator singleton ───────────────────────────────────

orchestrator: Orchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global orchestrator
    orchestrator = Orchestrator()
    logger.info(
        "🛡️  %s v%s is online. Monitoring for MR events...",
        settings.app_name,
        settings.app_version,
    )
    yield
    if orchestrator:
        await orchestrator.shutdown()
    logger.info("SentinelStream shutting down.")


# ── FastAPI App ──────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Autonomous DevOps Governance Agent for GitLab",
    lifespan=lifespan,
)


# ── Endpoints ────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    """Health check for Cloud Run / load balancers."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Receive GitLab MR webhook events.

    GitLab sends a POST with:
        - X-Gitlab-Token header (shared secret)
        - JSON body with merge_request event data
    """
    # ── Verify webhook secret ──
    token = request.headers.get("X-Gitlab-Token", "")
    if settings.gitlab_webhook_secret and token != settings.gitlab_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    body = await request.json()

    # ── Filter: only process merge_request events ──
    object_kind = body.get("object_kind", "")
    if object_kind != "merge_request":
        return {"status": "ignored", "reason": f"Event type '{object_kind}' not handled"}

    # ── Parse event ──
    mr_attrs = body.get("object_attributes", {})
    project = body.get("project", {})

    # Check if dependency files were changed
    changes = body.get("changes", {})

    event = MergeRequestEvent(
        object_kind="merge_request",
        project_id=project.get("id", 0),
        project_url=project.get("web_url", ""),
        merge_request_iid=mr_attrs.get("iid", 0),
        source_branch=mr_attrs.get("source_branch", ""),
        target_branch=mr_attrs.get("target_branch", "main"),
        action=mr_attrs.get("action", "open"),
        author_username=mr_attrs.get("last_commit", {}).get("author", {}).get("name", ""),
    )

    # Only process on open or update
    if event.action not in ("open", "update", "reopen"):
        return {
            "status": "ignored",
            "reason": f"MR action '{event.action}' does not trigger audit",
        }

    logger.info(
        "Received MR event: !%d (%s) by %s on %s",
        event.mr_iid,
        event.action,
        event.author_username,
        event.source_branch,
    )

    # ── Run the orchestrator pipeline ──
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    report = await orchestrator.process_merge_request(event)

    return {
        "status": "processed",
        "mr_iid": report.mr_iid,
        "total_scanned": report.total_scanned,
        "blockers": report.blockers,
        "warnings": report.warnings,
        "remediations_created": report.remediations_created,
    }


@app.post("/webhook/pipeline")
async def handle_pipeline_webhook(request: Request):
    """
    Pipeline-Aware Auto-Merge.

    Listens to GitLab CI/CD pipeline events. When a SentinelStream-generated
    remediation MR's pipeline passes, the agent automatically merges the MR
    and deletes the source branch — zero manual clicks for patch-level fixes.
    """
    token = request.headers.get("X-Gitlab-Token", "")
    if settings.gitlab_webhook_secret and token != settings.gitlab_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    body = await request.json()
    object_kind = body.get("object_kind", "")
    if object_kind != "pipeline":
        return {"status": "ignored", "reason": f"Event '{object_kind}' not a pipeline event"}

    pipeline_status = body.get("object_attributes", {}).get("status", "")
    if pipeline_status != "success":
        return {"status": "ignored", "reason": f"Pipeline status is '{pipeline_status}', not 'success'"}

    # Check if the MR that triggered this pipeline is a SentinelStream fix
    mr_attrs = body.get("merge_request", {})
    source_branch: str = mr_attrs.get("source_branch", "")
    if not source_branch.startswith("sentinelstream/fix/"):
        return {"status": "ignored", "reason": "Pipeline is not for a SentinelStream fix branch"}

    project_id = body.get("project", {}).get("id", 0)
    mr_iid = mr_attrs.get("iid", 0)

    logger.info(
        "🟢 Pipeline passed for SentinelStream fix MR !%d on branch '%s'. Initiating auto-merge...",
        mr_iid,
        source_branch,
    )

    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    merge_result = await orchestrator.auto_merge(
        project_id=project_id,
        mr_iid=mr_iid,
        source_branch=source_branch,
    )

    return {
        "status": "auto_merged" if merge_result else "merge_skipped",
        "project_id": project_id,
        "mr_iid": mr_iid,
        "branch": source_branch,
    }


@app.get("/")
async def root():
    """Landing page / API docs redirect."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "message": "SentinelStream is online. I have ingested the PRD. "
                   "I am now monitoring the current Merge Request for compliance gaps.",
    }
