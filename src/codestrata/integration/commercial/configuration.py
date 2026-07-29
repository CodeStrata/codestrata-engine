"""Configuration helpers for PlatformClient construction."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.integration.commercial.client import (
    OfflinePlatformClient,
    PlatformClient,
    RestPlatformClient,
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
    """Build a PlatformClient from ``CodestrataSettings.platform`` (duck-typed)."""

    platform = getattr(settings, "platform", None)
    if platform is None or not bool(getattr(platform, "enabled", False)):
        return OfflinePlatformClient()

    token = getattr(platform, "auth_token", None)
    token_env = getattr(platform, "auth_token_env", None)
    if not token and token_env:
        import os

        token = os.environ.get(str(token_env)) or None

    artifacts = getattr(platform, "artifacts", None)
    max_artifact_bytes = int(getattr(artifacts, "max_artifact_bytes", 10_485_760))

    return RestPlatformClient(
        base_url=str(getattr(platform, "base_url", "http://127.0.0.1:8000")),
        timeout_seconds=float(getattr(platform, "timeout_seconds", 10.0)),
        max_retries=int(getattr(platform, "max_retries", 2)),
        retry_backoff_seconds=float(getattr(platform, "retry_backoff_seconds", 0.5)),
        auth_token=token,
        max_artifact_bytes=max_artifact_bytes,
    )


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
