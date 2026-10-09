"""Fail-soft publisher. Community Engine does not submit to Platform."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codestrata.integration.commercial.client import PlatformClient
from codestrata.integration.commercial.configuration import PlatformClientConfig
from codestrata.integration.community_runtime import HOSTED_SUBMISSION_REMOVED
from codestrata.models import Repository


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
    """Never performs Platform HTTP. Hosted submission is removed from Community."""

    _ = (
        client,
        config,
        repository,
        configured_repository_url,
        html_report_path,
        json_report_path,
    )
    return PlatformPublishResult(status="removed", message=HOSTED_SUBMISSION_REMOVED)
