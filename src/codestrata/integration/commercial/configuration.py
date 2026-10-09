"""Configuration helpers for PlatformClient construction."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.integration.commercial.client import (
    OfflinePlatformClient,
    PlatformClient,
)


@dataclass(frozen=True, slots=True)
class PlatformClientConfig:
    enabled: bool = False
    base_url: str = "http://127.0.0.1:8000"
    organization_id: str = ""
    workspace_id: str = ""
    auth_token: str | None = None
    timeout_seconds: float = 10.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    max_artifact_bytes: int = 10_485_760


def platform_client_from_settings(settings: object) -> PlatformClient:
    """Community composition always returns the offline client.

    ``RestPlatformClient`` remains importable as a compatibility projection for
    outside-Engine hosts. Canonical Community runtime never constructs it, even
    when ``[platform].enabled`` is true in settings.
    """

    _ = settings
    return OfflinePlatformClient()


def platform_config_from_settings(settings: object) -> PlatformClientConfig:
    platform = getattr(settings, "platform", None)
    if platform is None:
        return PlatformClientConfig()
    artifacts = getattr(platform, "artifacts", None)
    return PlatformClientConfig(
        enabled=bool(getattr(platform, "enabled", False)),
        base_url=str(getattr(platform, "base_url", "http://127.0.0.1:8000")),
        organization_id=str(getattr(platform, "organization_id", "") or ""),
        workspace_id=str(getattr(platform, "workspace_id", "") or ""),
        auth_token=getattr(platform, "auth_token", None),
        timeout_seconds=float(getattr(platform, "timeout_seconds", 10.0)),
        max_retries=int(getattr(platform, "max_retries", 2)),
        retry_backoff_seconds=float(getattr(platform, "retry_backoff_seconds", 0.5)),
        max_artifact_bytes=int(getattr(artifacts, "max_artifact_bytes", 10_485_760)),
    )
