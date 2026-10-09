"""Engine artifact publishing policy and fail-soft publisher tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.config import (
    PlatformArtifactPublishingSettings,
    PlatformIntegrationSettings,
)
from codestrata.integration.commercial.artifacts.policy import ArtifactPublishingPolicy
from codestrata.integration.commercial.artifacts.publisher import publish_artifacts_to_platform
from codestrata.integration.commercial.client import MockPlatformClient
from codestrata.integration.community_runtime import HOSTED_SUBMISSION_REMOVED


def test_policy_disabled_by_default() -> None:
    policy = ArtifactPublishingPolicy.from_settings(
        type("S", (), {"platform": PlatformIntegrationSettings()})()
    )
    assert policy.platform_enabled is False
    assert policy.enabled is False
    assert policy.publishing_active() is False
    assert policy.intelligence_processing_active() is False
    assert policy.allows("assessment_summary") is False


def test_policy_requires_explicit_per_type_consent() -> None:
    settings = PlatformIntegrationSettings(
        enabled=True,
        artifacts=PlatformArtifactPublishingSettings(
            enabled=True,
            publish_summary=True,
            publish_report_json=True,
            publish_report_html=False,
        ),
    )
    policy = ArtifactPublishingPolicy.from_settings(type("S", (), {"platform": settings})())
    assert policy.allows("assessment_summary") is True
    assert policy.allows("report_json") is True
    assert policy.allows("report_html") is False
    assert policy.allows("findings") is False


def test_policy_rejects_source_code_and_archives(tmp_path: Path) -> None:
    policy = ArtifactPublishingPolicy(
        platform_enabled=True,
        enabled=True,
        publish_summary=True,
        publish_report_json=True,
    )
    source = tmp_path / "main.py"
    source.write_text("print('hi')", encoding="utf-8")
    archive = tmp_path / "repo.zip"
    archive.write_bytes(b"PK")
    assert policy.reject_reason(
        artifact_type="report_json",
        path=source,
        size_bytes=source.stat().st_size,
    )
    assert policy.reject_reason(
        artifact_type="report_json",
        path=archive,
        size_bytes=archive.stat().st_size,
    )


def test_publish_artifacts_removed_even_when_enabled(tmp_path: Path) -> None:
    client = MockPlatformClient()
    policy = ArtifactPublishingPolicy(
        platform_enabled=True,
        enabled=True,
        publish_summary=True,
        publish_report_json=True,
    )
    report = tmp_path / "report.json"
    report.write_text('{"ok":true}', encoding="utf-8")
    result = publish_artifacts_to_platform(
        client=client,
        policy=policy,
        engine_assessment_id="engine-assessment:1",
        platform_assessment_id="assessment:1",
        repository_name="app",
        html_report_path=None,
        json_report_path=report,
    )
    assert result.status == "removed"
    assert result.message == HOSTED_SUBMISSION_REMOVED
    assert result.published == ()
    assert client.artifacts == {}


def test_publish_artifacts_removed_when_policy_disabled(tmp_path: Path) -> None:
    client = MockPlatformClient()
    policy = ArtifactPublishingPolicy(platform_enabled=True, enabled=False)
    result = publish_artifacts_to_platform(
        client=client,
        policy=policy,
        engine_assessment_id="engine-assessment:1",
        platform_assessment_id="assessment:1",
        repository_name="app",
        html_report_path=None,
        json_report_path=tmp_path / "report.json",
    )
    assert result.status == "removed"
    assert result.message == HOSTED_SUBMISSION_REMOVED
    assert client.artifacts == {}
