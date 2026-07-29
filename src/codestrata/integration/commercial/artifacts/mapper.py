"""Map local assessment outputs to publishable artifact descriptors."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.integration.commercial.artifacts.checksum import sha256_file, sha256_hex
from codestrata.integration.commercial.artifacts.models import (
    ArtifactDescriptor,
    ArtifactPayload,
    PublishArtifactRequest,
)
from codestrata.integration.commercial.artifacts.policy import ArtifactPublishingPolicy

SCHEMA_VERSION = "1.0"


def build_summary_payload(
    *,
    engine_assessment_id: str,
    platform_assessment_id: str,
    repository_name: str,
    html_report_path: Path | None,
    json_report_path: Path | None,
) -> bytes:
    payload = {
        "engine_assessment_id": engine_assessment_id,
        "platform_assessment_id": platform_assessment_id,
        "repository_name": repository_name,
        "reports": {
            "html": str(html_report_path) if html_report_path else None,
            "json": str(json_report_path) if json_report_path else None,
        },
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def descriptors_for_assessment(
    *,
    policy: ArtifactPublishingPolicy,
    engine_assessment_id: str,
    platform_assessment_id: str,
    repository_name: str,
    html_report_path: Path | None,
    json_report_path: Path | None,
) -> tuple[tuple[ArtifactDescriptor, ArtifactPayload], ...]:
    """Create policy-filtered descriptors. Never includes source code."""

    items: list[tuple[ArtifactDescriptor, ArtifactPayload]] = []

    if policy.allows("assessment_summary"):
        content = build_summary_payload(
            engine_assessment_id=engine_assessment_id,
            platform_assessment_id=platform_assessment_id,
            repository_name=repository_name,
            html_report_path=html_report_path,
            json_report_path=json_report_path,
        )
        reason = policy.reject_reason(
            artifact_type="assessment_summary",
            path=None,
            size_bytes=len(content),
        )
        if reason is None:
            checksum = sha256_hex(content)
            items.append(
                (
                    ArtifactDescriptor(
                        artifact_type="assessment_summary",
                        format="json",
                        schema_version=SCHEMA_VERSION,
                        checksum=checksum,
                        size_bytes=len(content),
                        metadata={"kind": "assessment_summary"},
                    ),
                    ArtifactPayload(content=content, content_type="application/json"),
                )
            )

    if policy.allows("report_json") and json_report_path is not None and json_report_path.is_file():
        reason = policy.reject_reason(
            artifact_type="report_json",
            path=json_report_path,
            size_bytes=json_report_path.stat().st_size,
        )
        if reason is None:
            checksum, size_bytes, content = sha256_file(json_report_path)
            items.append(
                (
                    ArtifactDescriptor(
                        artifact_type="report_json",
                        format="json",
                        schema_version=SCHEMA_VERSION,
                        checksum=checksum,
                        size_bytes=size_bytes,
                        metadata={"kind": "report_json"},
                        local_path=str(json_report_path),
                    ),
                    ArtifactPayload(content=content, content_type="application/json"),
                )
            )

    if policy.allows("report_html") and html_report_path is not None and html_report_path.is_file():
        reason = policy.reject_reason(
            artifact_type="report_html",
            path=html_report_path,
            size_bytes=html_report_path.stat().st_size,
        )
        if reason is None:
            checksum, size_bytes, content = sha256_file(html_report_path)
            items.append(
                (
                    ArtifactDescriptor(
                        artifact_type="report_html",
                        format="html",
                        schema_version=SCHEMA_VERSION,
                        checksum=checksum,
                        size_bytes=size_bytes,
                        metadata={"kind": "report_html"},
                        local_path=str(html_report_path),
                    ),
                    ArtifactPayload(content=content, content_type="text/html"),
                )
            )

    return tuple(items)


def to_publish_request(
    *,
    engine_assessment_id: str,
    platform_assessment_id: str,
    descriptor: ArtifactDescriptor,
    payload: ArtifactPayload,
) -> PublishArtifactRequest:
    return PublishArtifactRequest(
        engine_assessment_id=engine_assessment_id,
        platform_assessment_id=platform_assessment_id,
        artifact_type=descriptor.artifact_type,
        format=descriptor.format,
        schema_version=descriptor.schema_version,
        checksum=descriptor.checksum,
        size_bytes=descriptor.size_bytes,
        metadata=dict(descriptor.metadata),
        content=payload.content,
    )
