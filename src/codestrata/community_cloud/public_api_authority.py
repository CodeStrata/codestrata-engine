"""Engine-side public Community API base URL authority (Slice 17.14).

Product transmission remains off by default. When operators explicitly configure
Community Cloud transport, production authority is api.codestrata.ai — never the
raw execute-api hostname.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

PUBLIC_COMMUNITY_API_HOSTNAME = "api.codestrata.ai"
PUBLIC_COMMUNITY_API_BASE_URL = "https://api.codestrata.ai"
PUBLIC_COMMUNITY_API_REGION = "us-west-2"

# Optional override for local/dev/testing only. Production operators should leave
# unset so the branded authority is used.
COMMUNITY_API_BASE_ENV = "CODESTRATA_COMMUNITY_CLOUD_API_BASE"

# Default production telemetry ingest path when endpoint is explicitly enabled.
PUBLIC_TELEMETRY_INGEST_URL = f"{PUBLIC_COMMUNITY_API_BASE_URL}/api/v1/telemetry"
PUBLIC_CLI_EVENTS_URL = f"{PUBLIC_COMMUNITY_API_BASE_URL}/api/v1/cli-events"
PUBLIC_EXTENSION_EVENTS_URL = f"{PUBLIC_COMMUNITY_API_BASE_URL}/api/v1/extension-events"
PUBLIC_ASSESSMENT_METADATA_URL = (
    f"{PUBLIC_COMMUNITY_API_BASE_URL}/api/v1/assessment-metadata"
)
PUBLIC_AI_USAGE_URL = f"{PUBLIC_COMMUNITY_API_BASE_URL}/api/v1/ai-usage"
PUBLIC_HEALTH_URL = f"{PUBLIC_COMMUNITY_API_BASE_URL}/api/v1/health"

EXECUTE_API_HOST_CLASSIFICATION = "IMPLEMENTATION_DETAIL"


def is_public_community_api_host(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return host == PUBLIC_COMMUNITY_API_HOSTNAME


def rejects_execute_api_as_public_authority(hostname: str | None) -> bool:
    """True when hostname is an AWS execute-api implementation host."""

    host = (hostname or "").strip().lower()
    return "execute-api." in host and ".amazonaws.com" in host


def resolve_public_community_api_base() -> str:
    """Return production Community API base URL authority.

    Local/dev may override via CODESTRATA_COMMUNITY_CLOUD_API_BASE. An execute-api
    override is rejected as public authority (fallback remains available only as
    an explicit legacy CODESTRATA_TELEMETRY_ENDPOINT for operators who still need
    the implementation endpoint during migration).
    """

    override = os.environ.get(COMMUNITY_API_BASE_ENV, "").strip().rstrip("/")
    if not override:
        return PUBLIC_COMMUNITY_API_BASE_URL
    host = urlparse(override).hostname
    if rejects_execute_api_as_public_authority(host):
        raise ValueError(
            "CODESTRATA_COMMUNITY_CLOUD_API_BASE must not use execute-api hostname; "
            f"use {PUBLIC_COMMUNITY_API_BASE_URL}"
        )
    return override


def production_telemetry_ingest_url() -> str:
    return f"{resolve_public_community_api_base()}/api/v1/telemetry"


def production_assessment_metadata_url() -> str:
    """Public Community assessment_metadata ingest URL (override-aware)."""

    return f"{resolve_public_community_api_base()}/api/v1/assessment-metadata"


__all__ = [
    "COMMUNITY_API_BASE_ENV",
    "EXECUTE_API_HOST_CLASSIFICATION",
    "PUBLIC_AI_USAGE_URL",
    "PUBLIC_ASSESSMENT_METADATA_URL",
    "PUBLIC_CLI_EVENTS_URL",
    "PUBLIC_COMMUNITY_API_BASE_URL",
    "PUBLIC_COMMUNITY_API_HOSTNAME",
    "PUBLIC_COMMUNITY_API_REGION",
    "PUBLIC_EXTENSION_EVENTS_URL",
    "PUBLIC_HEALTH_URL",
    "PUBLIC_TELEMETRY_INGEST_URL",
    "is_public_community_api_host",
    "production_assessment_metadata_url",
    "production_telemetry_ingest_url",
    "rejects_execute_api_as_public_authority",
    "resolve_public_community_api_base",
]
