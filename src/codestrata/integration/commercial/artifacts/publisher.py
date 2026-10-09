"""Fail-soft publisher. Community Engine does not upload artifacts to Platform."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codestrata.integration.commercial.artifacts.models import (
    ArtifactFailure,
    PublishArtifactResult,
)
from codestrata.integration.commercial.artifacts.policy import ArtifactPublishingPolicy
from codestrata.integration.commercial.client import PlatformClient
from codestrata.integration.community_runtime import HOSTED_SUBMISSION_REMOVED


@dataclass(frozen=True, slots=True)
class ArtifactPublishBatchResult:
    status: str
    published: tuple[PublishArtifactResult, ...] = ()
    failures: tuple[ArtifactFailure, ...] = ()
    message: str | None = None


def publish_artifacts_to_platform(
    *,
    client: PlatformClient,
    policy: ArtifactPublishingPolicy,
    engine_assessment_id: str,
    platform_assessment_id: str,
    repository_name: str,
    html_report_path: Path | None,
    json_report_path: Path | None,
) -> ArtifactPublishBatchResult:
    """Never performs Platform HTTP. Hosted artifact submission is removed."""

    _ = (
        client,
        policy,
        engine_assessment_id,
        platform_assessment_id,
        repository_name,
        html_report_path,
        json_report_path,
    )
    return ArtifactPublishBatchResult(
        status="removed",
        message=HOSTED_SUBMISSION_REMOVED,
    )
