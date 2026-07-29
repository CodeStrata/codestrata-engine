"""Fail-soft publisher for authorized assessment artifacts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from codestrata.integration.commercial.artifacts.checksum import sha256_hex
from codestrata.integration.commercial.artifacts.mapper import (
    descriptors_for_assessment,
    to_publish_request,
)
from codestrata.integration.commercial.artifacts.models import (
    ArtifactFailure,
    PublishArtifactResult,
)
from codestrata.integration.commercial.artifacts.policy import ArtifactPublishingPolicy
from codestrata.integration.commercial.client import PlatformClient
from codestrata.integration.commercial.errors import PlatformIntegrationError

logger = logging.getLogger(__name__)


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
    """Publish explicitly enabled artifacts after local report generation.

    Never raises. Platform and policy failures become soft failures.
    """

    if not policy.publishing_active():
        return ArtifactPublishBatchResult(
            status="disabled",
            message="Artifact publishing disabled",
        )

    published: list[PublishArtifactResult] = []
    failures: list[ArtifactFailure] = []

    try:
        items = descriptors_for_assessment(
            policy=policy,
            engine_assessment_id=engine_assessment_id,
            platform_assessment_id=platform_assessment_id,
            repository_name=repository_name,
            html_report_path=html_report_path,
            json_report_path=json_report_path,
        )
    except Exception as error:  # noqa: BLE001 - fail-soft boundary
        logger.warning("Artifact descriptor creation failed: %s", error)
        return ArtifactPublishBatchResult(
            status="failed",
            message=str(error),
            failures=(
                ArtifactFailure(
                    artifact_type="*",
                    reason=str(error),
                    reason_code="descriptor_failed",
                ),
            ),
        )

    if not items:
        return ArtifactPublishBatchResult(
            status="skipped",
            message="No enabled artifacts available to publish",
        )

    for descriptor, payload in items:
        registration: PublishArtifactResult | None = None
        try:
            digest = sha256_hex(payload.content)
            if digest != descriptor.checksum:
                raise PlatformIntegrationError(
                    "Local artifact checksum verification failed",
                    reason_code="checksum_mismatch",
                )
            if len(payload.content) != descriptor.size_bytes:
                raise PlatformIntegrationError(
                    "Local artifact size mismatch",
                    reason_code="content_length_mismatch",
                )
            request = to_publish_request(
                engine_assessment_id=engine_assessment_id,
                platform_assessment_id=platform_assessment_id,
                descriptor=descriptor,
                payload=payload,
            )
            registration = client.register_artifact(request)
            client.upload_artifact(
                assessment_id=platform_assessment_id,
                artifact_id=registration.artifact_id,
                content=payload.content,
                checksum=descriptor.checksum,
                content_type=payload.content_type,
            )
            completed = client.complete_artifact(
                assessment_id=platform_assessment_id,
                artifact_id=registration.artifact_id,
            )
            published.append(
                PublishArtifactResult(
                    artifact_id=completed.artifact_id,
                    assessment_id=completed.assessment_id or platform_assessment_id,
                    artifact_type=completed.artifact_type or descriptor.artifact_type,
                    checksum=completed.checksum or descriptor.checksum,
                    status=completed.status,
                    version=completed.version,
                    created=registration.created,
                )
            )
        except PlatformIntegrationError as error:
            logger.warning(
                "Artifact publish failed for %s: %s",
                descriptor.artifact_type,
                error,
            )
            if registration is not None:
                try:
                    client.fail_artifact(
                        assessment_id=platform_assessment_id,
                        artifact_id=registration.artifact_id,
                        reason=str(error),
                    )
                except Exception:  # noqa: BLE001 - fail-soft
                    pass
            failures.append(
                ArtifactFailure(
                    artifact_type=descriptor.artifact_type,
                    reason=str(error),
                    reason_code=getattr(error, "reason_code", None) or "publish_failed",
                )
            )
        except Exception as error:  # noqa: BLE001 - fail-soft boundary
            logger.warning(
                "Artifact publish failed for %s: %s",
                descriptor.artifact_type,
                error,
            )
            failures.append(
                ArtifactFailure(
                    artifact_type=descriptor.artifact_type,
                    reason=str(error),
                )
            )

    if failures and not published:
        status = "failed"
    elif failures:
        status = "partial"
    else:
        status = "succeeded"

    return ArtifactPublishBatchResult(
        status=status,
        published=tuple(published),
        failures=tuple(failures),
        message=None if not failures else f"{len(failures)} artifact(s) failed",
    )
