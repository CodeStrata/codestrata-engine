"""Fail-soft publisher that synchronizes Engine assessment metadata to Platform."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from codestrata.integration.commercial.client import PlatformClient
from codestrata.integration.commercial.configuration import PlatformClientConfig
from codestrata.integration.commercial.errors import PlatformIntegrationError
from codestrata.integration.commercial.mapper import (
    new_engine_assessment_id,
    resolve_repository_url,
    to_complete_assessment_request,
    to_register_assessment_request,
    to_register_repository_request,
)
from codestrata.models import Repository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlatformPublishResult:
    status: str
    engine_assessment_id: str | None = None
    organization_id: str | None = None
    workspace_id: str | None = None
    repository_id: str | None = None
    assessment_id: str | None = None
    message: str | None = None


def publish_assessment_to_platform(
    *,
    client: PlatformClient,
    config: PlatformClientConfig,
    repository: Repository,
    configured_repository_url: str | None,
    html_report_path: Path | None,
    json_report_path: Path | None,
) -> PlatformPublishResult:
    """Register repository + assessment lifecycle with Platform.

    Never raises — Platform failures become a failed publish result.
    """

    if not config.enabled:
        return PlatformPublishResult(status="disabled", message="Platform integration disabled")

    if not config.organization_id.strip() or not config.workspace_id.strip():
        return PlatformPublishResult(
            status="failed",
            message="platform.organization_id and platform.workspace_id are required",
        )

    repository_url = resolve_repository_url(repository, configured_repository_url)
    if repository_url is None:
        return PlatformPublishResult(
            status="failed",
            message="No HTTP(S) repository URL available for Platform registration",
        )

    engine_assessment_id = new_engine_assessment_id()
    try:
        existing = client.lookup_repository(
            workspace_id=config.workspace_id,
            repository_url=repository_url,
        )
        if existing is None:
            repo_ref = client.register_repository(
                to_register_repository_request(
                    organization_id=config.organization_id,
                    workspace_id=config.workspace_id,
                    repository=repository,
                    repository_url=repository_url,
                )
            )
        else:
            repo_ref = existing

        assessment_ref = client.register_assessment(
            to_register_assessment_request(
                repository_id=repo_ref.repository_id,
                workspace_id=config.workspace_id,
                engine_assessment_id=engine_assessment_id,
                repository=repository,
            )
        )
        assessment_ref = client.start_assessment(assessment_ref.assessment_id)
        assessment_ref = client.complete_assessment(
            to_complete_assessment_request(
                assessment_id=assessment_ref.assessment_id,
                html_report_path=html_report_path,
                json_report_path=json_report_path,
            )
        )
        return PlatformPublishResult(
            status="succeeded",
            engine_assessment_id=engine_assessment_id,
            organization_id=repo_ref.organization_id,
            workspace_id=repo_ref.workspace_id,
            repository_id=repo_ref.repository_id,
            assessment_id=assessment_ref.assessment_id,
        )
    except PlatformIntegrationError as error:
        logger.warning("Platform ingestion failed: %s", error)
        return PlatformPublishResult(
            status="failed",
            engine_assessment_id=engine_assessment_id,
            message=str(error),
        )
    except Exception as error:  # noqa: BLE001 - never break Engine reporting
        logger.warning("Platform ingestion unexpected failure: %s", error)
        return PlatformPublishResult(
            status="failed",
            engine_assessment_id=engine_assessment_id,
            message=str(error),
        )
