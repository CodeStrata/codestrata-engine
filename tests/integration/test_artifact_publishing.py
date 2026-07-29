"""Engine artifact publishing policy and fail-soft publisher tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.config import (
    PlatformArtifactPublishingSettings,
    PlatformIntegrationSettings,
)
from codestrata.integration.commercial.artifacts.checksum import sha256_hex
from codestrata.integration.commercial.artifacts.policy import ArtifactPublishingPolicy
from codestrata.integration.commercial.artifacts.publisher import publish_artifacts_to_platform
from codestrata.integration.commercial.client import MockPlatformClient
from codestrata.integration.commercial.models import (
    RegisterAssessmentRequest,
    RegisterRepositoryRequest,
)


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


def test_publish_artifacts_fail_soft_when_platform_unavailable(tmp_path: Path) -> None:
    client = MockPlatformClient()
    client.register_repository(
        RegisterRepositoryRequest(
            organization_id="org:1",
            workspace_id="workspace:1",
            display_name="App",
            repository_url="https://github.com/acme/app",
        )
    )
    assessment = client.register_assessment(
        RegisterAssessmentRequest(
            repository_id="repo:mock-1",
            workspace_id="workspace:1",
            engine_assessment_id="engine-assessment:1",
            engine_version="1.0.0",
            assessment_version="0.1.0",
        )
    )
    report = tmp_path / "report.json"
    report.write_text('{"ok":true}', encoding="utf-8")
    client.fail_next = "upload_artifact"
    policy = ArtifactPublishingPolicy(
        platform_enabled=True,
        enabled=True,
        publish_summary=True,
        publish_report_json=True,
    )
    result = publish_artifacts_to_platform(
        client=client,
        policy=policy,
        engine_assessment_id="engine-assessment:1",
        platform_assessment_id=assessment.assessment_id,
        repository_name="app",
        html_report_path=None,
        json_report_path=report,
    )
    assert result.status in {"failed", "partial"}
    assert result.failures


def test_publish_artifacts_succeeds_for_enabled_types(tmp_path: Path) -> None:
    client = MockPlatformClient()
    client.register_repository(
        RegisterRepositoryRequest(
            organization_id="org:1",
            workspace_id="workspace:1",
            display_name="App",
            repository_url="https://github.com/acme/app",
        )
    )
    assessment = client.register_assessment(
        RegisterAssessmentRequest(
            repository_id="repo:mock-1",
            workspace_id="workspace:1",
            engine_assessment_id="engine-assessment:1",
            engine_version="1.0.0",
            assessment_version="0.1.0",
        )
    )
    report = tmp_path / "report.json"
    report.write_text('{"ok":true}', encoding="utf-8")
    policy = ArtifactPublishingPolicy(
        platform_enabled=True,
        enabled=True,
        publish_summary=True,
        publish_report_json=True,
        publish_report_html=False,
    )
    result = publish_artifacts_to_platform(
        client=client,
        policy=policy,
        engine_assessment_id="engine-assessment:1",
        platform_assessment_id=assessment.assessment_id,
        repository_name="app",
        html_report_path=tmp_path / "missing.html",
        json_report_path=report,
    )
    assert result.status == "succeeded"
    assert len(result.published) == 2
    types = {item.artifact_type for item in result.published}
    assert types == {"assessment_summary", "report_json"}
    listed = client.list_assessment_artifacts(assessment.assessment_id)
    assert len(listed) == 2
    assert all(item.status == "completed" for item in listed)
    assert sha256_hex(report.read_bytes()) in {item.checksum for item in listed}


def test_disabled_artifacts_publish_nothing(tmp_path: Path) -> None:
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
    assert result.status == "disabled"
    assert client.artifacts == {}
