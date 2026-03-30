"""
SentinelStream AI — Configuration
Environment-driven settings for the governance agent backend.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── GitLab ──────────────────────────────────────────────
    gitlab_url: str = Field(
        default="https://gitlab.com",
        description="GitLab instance base URL",
    )
    gitlab_token: str = Field(
        default="",
        description="GitLab Personal/Project Access Token with 'api' scope",
    )
    gitlab_webhook_secret: str = Field(
        default="",
        description="Shared secret for validating incoming webhook payloads",
    )

    # ── Google Cloud OSV ────────────────────────────────────
    osv_api_url: str = Field(
        default="https://api.osv.dev/v1",
        description="Google Cloud OSV API base URL",
    )

    # ── Model Routing (Logic Gating) ───────────────────────
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google AI / Vertex API key for Gemini 1.5 Flash",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Fast model for patch-level verification",
    )
    claude_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude-3 deep reasoning",
    )
    claude_model: str = Field(
        default="claude-3-sonnet-20240229",
        description="Reasoning model for major/new-library analysis",
    )

    # ── Application ────────────────────────────────────────
    app_name: str = "SentinelStream AI"
    app_version: str = "1.0.0"
    log_level: str = Field(default="INFO", description="Logging level")
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8080, description="Server bind port")

    # ── Policy Defaults ────────────────────────────────────
    default_allowed_licenses: list[str] = Field(
        default=[
            "MIT",
            "Apache-2.0",
            "BSD-2-Clause",
            "BSD-3-Clause",
            "ISC",
            "0BSD",
        ],
        description="Zero Trust fallback: allowed licenses when POLICY.md is missing",
    )

    model_config = {"env_prefix": "SENTINEL_", "env_file": ".env"}


settings = Settings()
