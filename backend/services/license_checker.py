"""
SentinelStream AI — License Checker Service
Checks package license metadata from PyPI, npm, and Go module proxy.
Falls back to web search for obscure packages.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings
from models.schemas import LicenseResult, Ecosystem

logger = logging.getLogger("sentinelstream.license")


class LicenseChecker:
    """Queries package registries for license SPDX identifiers."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._allowed_licenses = set(settings.default_allowed_licenses)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def set_allowed_licenses(self, licenses: list[str]) -> None:
        """Override the allowed-license list (e.g., from POLICY.md)."""
        self._allowed_licenses = set(licenses)

    # ── Registry Lookups ─────────────────────────────────────

    async def _check_pypi(self, package_name: str, version: str) -> str:
        """Fetch license from PyPI JSON API."""
        client = await self._get_client()
        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                # Try without version
                resp = await client.get(
                    f"https://pypi.org/pypi/{package_name}/json"
                )
            resp.raise_for_status()
            data = resp.json()
            info = data.get("info", {})

            # Try classifiers first (more reliable)
            for classifier in info.get("classifiers", []):
                if "License :: OSI Approved ::" in classifier:
                    parts = classifier.split(" :: ")
                    return _normalize_license(parts[-1])

            # Fall back to license field
            raw_license = info.get("license", "")
            if raw_license and len(raw_license) < 50:
                return _normalize_license(raw_license)

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("PyPI lookup failed for %s: %s", package_name, exc)
        return "UNKNOWN"

    async def _check_npm(self, package_name: str, version: str) -> str:
        """Fetch license from npm registry."""
        client = await self._get_client()
        url = f"https://registry.npmjs.org/{package_name}/{version}"
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                resp = await client.get(
                    f"https://registry.npmjs.org/{package_name}/latest"
                )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("license", "")
            if isinstance(raw, dict):
                raw = raw.get("type", "")
            if raw:
                return _normalize_license(raw)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("npm lookup failed for %s: %s", package_name, exc)
        return "UNKNOWN"

    async def _check_go(self, package_name: str, version: str) -> str:
        """Fetch license from Go module proxy (pkg.go.dev fallback)."""
        client = await self._get_client()
        url = f"https://pkg.go.dev/{package_name}@v{version}?tab=licenses"
        try:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                text = resp.text
                # Simple heuristic: look for SPDX in the page
                for spdx in [
                    "MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause",
                    "ISC", "MPL-2.0", "LGPL-3.0", "GPL-3.0", "AGPL-3.0",
                ]:
                    if spdx in text:
                        return spdx
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Go license check failed for %s: %s", package_name, exc)
        return "UNKNOWN"

    # ── Unified Check ────────────────────────────────────────

    async def check_license(
        self,
        package_name: str,
        version: str,
        ecosystem: Ecosystem = Ecosystem.UNKNOWN,
    ) -> LicenseResult:
        """
        Look up the license for a package and determine compliance.

        Returns a LicenseResult with is_allowed set based on the current policy.
        """
        spdx = "UNKNOWN"

        if ecosystem == Ecosystem.PYPI:
            spdx = await self._check_pypi(package_name, version)
        elif ecosystem == Ecosystem.NPM:
            spdx = await self._check_npm(package_name, version)
        elif ecosystem == Ecosystem.GO:
            spdx = await self._check_go(package_name, version)
        else:
            # Try all registries
            spdx = await self._check_pypi(package_name, version)
            if spdx == "UNKNOWN":
                spdx = await self._check_npm(package_name, version)
            if spdx == "UNKNOWN":
                spdx = await self._check_go(package_name, version)

        is_allowed = spdx in self._allowed_licenses

        logger.info(
            "License check: %s@%s → %s (%s)",
            package_name,
            version,
            spdx,
            "✅ allowed" if is_allowed else "❌ blocked",
        )

        return LicenseResult(
            package_name=package_name,
            version=version,
            license_spdx=spdx,
            is_allowed=is_allowed,
            policy_source="POLICY.md",
        )


# ── Helpers ──────────────────────────────────────────────────

_LICENSE_ALIASES = {
    "MIT License": "MIT",
    "Apache Software License": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache 2.0": "Apache-2.0",
    "BSD License": "BSD-3-Clause",
    "BSD 3-Clause": "BSD-3-Clause",
    "BSD 2-Clause": "BSD-2-Clause",
    "ISC License": "ISC",
    "GNU General Public License v3": "GPL-3.0-only",
    "GPLv3": "GPL-3.0-only",
    "GNU General Public License v2": "GPL-2.0-only",
    "GPLv2": "GPL-2.0-only",
    "GNU Affero General Public License v3": "AGPL-3.0-only",
    "AGPLv3": "AGPL-3.0-only",
    "Mozilla Public License 2.0": "MPL-2.0",
    "LGPL-2.1": "LGPL-2.1-only",
    "Unlicense": "Unlicense",
    "Public Domain": "Unlicense",
}


def _normalize_license(raw: str) -> str:
    """Normalize a raw license string to an SPDX identifier."""
    raw = raw.strip()
    if raw in _LICENSE_ALIASES:
        return _LICENSE_ALIASES[raw]
    # If it's already a short SPDX-like string, return as-is
    if len(raw) < 30 and raw.replace("-", "").replace(".", "").isalnum():
        return raw
    # Try partial matching
    upper = raw.upper()
    for alias, spdx in _LICENSE_ALIASES.items():
        if alias.upper() in upper:
            return spdx
    return "UNKNOWN"
