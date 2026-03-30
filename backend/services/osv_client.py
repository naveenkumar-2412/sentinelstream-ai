"""
SentinelStream AI — Google Cloud OSV Client
Queries the OSV.dev API for known vulnerabilities by package/version.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings
from models.schemas import VulnerabilityResult, Severity, Ecosystem

logger = logging.getLogger("sentinelstream.osv")

# Map our Ecosystem enum to OSV ecosystem strings
_ECOSYSTEM_MAP = {
    Ecosystem.PYPI: "PyPI",
    Ecosystem.NPM: "npm",
    Ecosystem.GO: "Go",
}


def _cvss_to_severity(score: float) -> Severity:
    """Map a CVSS score to our severity enum (aligned with POLICY.md)."""
    if score >= 9.0:
        return Severity.CRITICAL
    if score >= 7.0:
        return Severity.HIGH
    if score >= 4.0:
        return Severity.MEDIUM
    if score > 0:
        return Severity.LOW
    return Severity.NONE


class OSVClient:
    """Async client for the Google Cloud OSV API (https://osv.dev)."""

    def __init__(self) -> None:
        self.base_url = settings.osv_api_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def query_vulnerabilities(
        self,
        package_name: str,
        version: str,
        ecosystem: Ecosystem = Ecosystem.UNKNOWN,
    ) -> list[VulnerabilityResult]:
        """
        Query OSV for vulnerabilities affecting a specific package version.

        Uses the /v1/query endpoint:
        https://osv.dev/docs/#tag/api/operation/OSV_QueryAffected
        """
        client = await self._get_client()
        osv_ecosystem = _ECOSYSTEM_MAP.get(ecosystem, "")

        payload: dict = {"version": version}
        if osv_ecosystem:
            payload["package"] = {
                "name": package_name,
                "ecosystem": osv_ecosystem,
            }
        else:
            payload["package"] = {"name": package_name}

        try:
            resp = await client.post(
                f"{self.base_url}/query",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OSV query failed for %s@%s: %s", package_name, version, exc
            )
            return []
        except httpx.RequestError as exc:
            logger.error("OSV request error: %s", exc)
            return []

        results: list[VulnerabilityResult] = []
        for vuln in data.get("vulns", []):
            # Extract CVSS score from severity array
            cvss_score = 0.0
            for sev_entry in vuln.get("severity", []):
                if sev_entry.get("type") == "CVSS_V3":
                    try:
                        # The score is embedded in the CVSS vector string
                        # or in the 'score' field depending on the entry
                        score_str = sev_entry.get("score", "")
                        if score_str:
                            cvss_score = float(score_str)
                    except (ValueError, TypeError):
                        pass

            # Extract CVE alias
            cve_id = ""
            for alias in vuln.get("aliases", []):
                if alias.startswith("CVE-"):
                    cve_id = alias
                    break
            if not cve_id:
                cve_id = vuln.get("id", "UNKNOWN")

            # Find fixed version
            fixed_version: Optional[str] = None
            affected_versions: list[str] = []
            for affected in vuln.get("affected", []):
                for rng in affected.get("ranges", []):
                    for event in rng.get("events", []):
                        if "fixed" in event:
                            fixed_version = event["fixed"]
                        if "introduced" in event:
                            affected_versions.append(
                                f">={event['introduced']}"
                            )

            results.append(VulnerabilityResult(
                cve_id=cve_id,
                summary=vuln.get("summary", vuln.get("details", ""))[:300],
                cvss_score=cvss_score,
                severity=_cvss_to_severity(cvss_score),
                affected_versions=affected_versions,
                fixed_version=fixed_version,
                reference_url=f"https://osv.dev/vulnerability/{vuln.get('id', '')}",
            ))

        logger.info(
            "OSV returned %d vulns for %s@%s", len(results), package_name, version
        )
        return results

    async def batch_query(
        self,
        packages: list[dict],
    ) -> dict[str, list[VulnerabilityResult]]:
        """
        Query vulnerabilities for multiple packages at once.

        Args:
            packages: List of dicts with keys: name, version, ecosystem.

        Returns:
            Mapping of "name@version" → list of VulnerabilityResult.
        """
        results: dict[str, list[VulnerabilityResult]] = {}
        for pkg in packages:
            key = f"{pkg['name']}@{pkg['version']}"
            results[key] = await self.query_vulnerabilities(
                package_name=pkg["name"],
                version=pkg["version"],
                ecosystem=pkg.get("ecosystem", Ecosystem.UNKNOWN),
            )
        return results
