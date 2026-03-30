"""
SentinelStream AI — Agent-Coder
Performs safe application code refactoring in response to major version dependency upgrades.

When a major CVE fix requires a breaking API upgrade (e.g., express 3.x → 4.x, django 3 → 4),
Agent-Coder uses LLM reasoning to identify deprecated API calls in the codebase and
generate a multi-file diff that updates the application code to match the new library API.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.schemas import DependencyDelta, ChangeType, Ecosystem, RemediationAction

logger = logging.getLogger(__name__)

# ── Major Upgrade Migration Guides ──────────────────────────────────────────
# Pre-baked migration hints for common libraries to reduce LLM hallucinations.

MIGRATION_HINTS: dict[str, dict] = {
    "express": {
        "3_to_4": {
            "breaking_patterns": [
                ("app.configure", "// app.configure() removed - just call app.use() or set env directly"),
                ("req.param(", "req.params."),   # req.param() → req.params.x
                ("res.redirect('back')", "res.redirect('back')  // Use req.get('Referer') explicitly"),
            ],
            "guide": "https://expressjs.com/en/guide/migrating-4.html",
        },
    },
    "django": {
        "2_to_3": {
            "breaking_patterns": [
                ("from django.utils.encoding import force_text", "from django.utils.encoding import force_str"),
                ("from django.utils.translation import ugettext_lazy", "from django.utils.translation import gettext_lazy"),
            ],
            "guide": "https://docs.djangoproject.com/en/3.0/releases/3.0/",
        },
        "3_to_4": {
            "breaking_patterns": [
                ("from django.utils.translation import ugettext", "from django.utils.translation import gettext"),
                ("DEFAULT_AUTO_FIELD", "# Set DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField' in settings.py"),
            ],
            "guide": "https://docs.djangoproject.com/en/4.0/releases/4.0/",
        },
    },
    "react": {
        "16_to_17": {
            "breaking_patterns": [
                ("import React from 'react'", "// Automatic JSX transform — React import optional"),
            ],
            "guide": "https://reactjs.org/blog/2020/10/20/react-v17.html#changes-to-event-delegation",
        },
        "17_to_18": {
            "breaking_patterns": [
                ("ReactDOM.render(", "createRoot("),
            ],
            "guide": "https://reactjs.org/blog/2022/03/08/react-18-upgrade-guide.html",
        },
    },
    "sqlalchemy": {
        "1_to_2": {
            "breaking_patterns": [
                ("session.execute(query)", "session.execute(sa.select(...))"),
                ("Model.query.", "session.execute(sa.select(Model)).scalars()."),
            ],
            "guide": "https://docs.sqlalchemy.org/en/20/changelog/migration_20.html",
        },
    },
}


# ── Agent-Coder ──────────────────────────────────────────────────────────────

class AgentCoder:
    """
    Suggests multi-file application code patches to accompany major version upgrades.

    Pipeline position: AFTER Agent-Fixer determines a major-version upgrade is needed.
                       BEFORE the MR comment is posted.
    
    Decision flow:
        1. Receive a DependencyDelta for a MAJOR version bump.
        2. Look up known migration hints for that library.
        3. Search the MR diff for usage of deprecated API patterns.
        4. Generate replacement patches for each affected file.
        5. Append code patches to the RemediationAction returned by Agent-Fixer.
    """

    def __init__(self):
        self.migration_hints = MIGRATION_HINTS

    def _get_migration_key(self, old_version: str, new_version: str) -> str | None:
        """Derive a migration key like '3_to_4' from version strings."""
        try:
            old_major = old_version.split(".")[0]
            new_major = new_version.split(".")[0]
            return f"{old_major}_to_{new_major}"
        except (IndexError, AttributeError):
            return None

    def analyze(
        self,
        delta: DependencyDelta,
        source_code_files: dict[str, str],
    ) -> list[dict]:
        """
        Analyze source code files for deprecated API patterns caused by the major version upgrade.

        Args:
            delta: The DependencyDelta requiring a major upgrade.
            source_code_files: Dict of { file_path: file_content } for the MR's changed source files.

        Returns:
            List of code-patch suggestions: [{ file, line, old, new, hint_url }]
        """
        if delta.change_type not in (ChangeType.MAJOR, ChangeType.NEW):
            logger.debug("AgentCoder: Skipping non-major delta for %s", delta.package_name)
            return []

        package = delta.package_name.lower()
        hints_for_lib = self.migration_hints.get(package)
        if not hints_for_lib:
            logger.info("AgentCoder: No migration hints for '%s'. Skipping code analysis.", package)
            return []

        old_version = delta.old.version if delta.old else "0"
        new_version = delta.new.version if delta.new else "0"
        migration_key = self._get_migration_key(old_version, new_version)
        if not migration_key or migration_key not in hints_for_lib:
            logger.info("AgentCoder: No hints for migration key '%s' of '%s'.", migration_key, package)
            return []

        hints = hints_for_lib[migration_key]
        breaking_patterns = hints.get("breaking_patterns", [])
        guide_url = hints.get("guide", "")

        patches = []
        for file_path, content in source_code_files.items():
            for old_pattern, new_pattern in breaking_patterns:
                if old_pattern in content:
                    for line_no, line in enumerate(content.splitlines(), start=1):
                        if old_pattern in line:
                            patches.append({
                                "file": file_path,
                                "line": line_no,
                                "old_code": line.rstrip(),
                                "new_code": line.replace(old_pattern, new_pattern).rstrip(),
                                "reason": f"API change in {package} {old_version}→{new_version}",
                                "migration_guide": guide_url,
                            })

        if patches:
            logger.info(
                "AgentCoder: Found %d code location(s) requiring migration in %s (%s→%s)",
                len(patches),
                package,
                old_version,
                new_version,
            )
        return patches

    def format_patches_as_markdown(self, patches: list[dict]) -> str:
        """Render patches as a collapsible GitLab Markdown section for the MR comment."""
        if not patches:
            return ""

        lines = [
            "\n<details>",
            "<summary>🔧 <strong>Agent-Coder: Application Code Migration Required</strong></summary>",
            "",
            "The following application code changes are required to remain compatible with the new library version:",
            "",
        ]
        for patch in patches:
            lines += [
                f"**`{patch['file']}`** — Line {patch['line']}",
                "```diff",
                f"- {patch['old_code']}",
                f"+ {patch['new_code']}",
                "```",
                f"> *Reason: {patch['reason']}*  ",
                f"> 📖 [Migration Guide]({patch['migration_guide']})",
                "",
            ]
        lines.append("</details>")
        return "\n".join(lines)
