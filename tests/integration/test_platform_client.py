"""Engine PlatformClient and publisher tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from codestrata.config import PlatformIntegrationSettings
from codestrata.integration.commercial.client import MockPlatformClient, OfflinePlatformClient
from codestrata.integration.commercial.configuration import (
    PlatformClientConfig,
    platform_client_from_settings,
)
from codestrata.integration.commercial.mapper import (
    infer_provider,
    new_engine_assessment_id,
    resolve_repository_url,
    technology_summary,
)
from codestrata.integration.commercial.publisher import publish_assessment_to_platform
from codestrata.integration.community_runtime import HOSTED_SUBMISSION_REMOVED
from codestrata.models import Repository, Technology
from codestrata.models.enums import TechnologyCategory


def _repo(*, url: str = "https://github.com/acme/app") -> Repository:
    return Repository(
        id=uuid4(),
        name="app",
        path=Path("/tmp/app"),
        source_url=url,
        default_branch="main",
        technologies=[
            Technology(name="Python", category=TechnologyCategory.LANGUAGE, confidence=0.9),
        ],
    )


def test_offline_client_when_disabled() -> None:
    class Settings:
        platform = PlatformIntegrationSettings(enabled=False)

    client = platform_client_from_settings(Settings())
    assert isinstance(client, OfflinePlatformClient)


def test_correlation_ids_are_stable_prefix() -> None:
    first = new_engine_assessment_id()
    second = new_engine_assessment_id()
    assert first.startswith("engine-assessment:")
    assert second.startswith("engine-assessment:")
    assert first != second


def test_mapper_provider_and_technology_summary() -> None:
    assert infer_provider("https://github.com/acme/app") == "github"
    repo = _repo()
    assert "Python" in technology_summary(repo)
    assert resolve_repository_url(repo, None) == "https://github.com/acme/app"


def test_mock_client_register_lookup_and_lifecycle() -> None:
    client = MockPlatformClient()
    repo = client.register_repository(
        __import__(
            "codestrata.integration.commercial.models",
            fromlist=["RegisterRepositoryRequest"],
        ).RegisterRepositoryRequest(
            organization_id="org:1",
            workspace_id="workspace:1",
            display_name="App",
            repository_url="https://github.com/acme/app",
        )
    )
    assert repo.created is True
    looked = client.lookup_repository(
        workspace_id="workspace:1",
        repository_url="https://github.com/acme/app/",
    )
    assert looked is not None
    assert looked.repository_id == repo.repository_id

    from codestrata.integration.commercial.models import (
        CompleteAssessmentRequest,
        RegisterAssessmentRequest,
    )

    assessment = client.register_assessment(
        RegisterAssessmentRequest(
            repository_id=repo.repository_id,
            workspace_id="workspace:1",
            engine_assessment_id="engine-assessment:abc",
            engine_version="0.1.0",
            assessment_version="1.2.0",
        )
    )
    started = client.start_assessment(assessment.assessment_id)
    assert started.status == "running"
    completed = client.complete_assessment(
        CompleteAssessmentRequest(assessment_id=assessment.assessment_id)
    )
    assert completed.status == "succeeded"


def test_publisher_removed_when_disabled() -> None:
    result = publish_assessment_to_platform(
        client=MockPlatformClient(),
        config=PlatformClientConfig(enabled=False),
        repository=_repo(),
        configured_repository_url=None,
        html_report_path=None,
        json_report_path=None,
    )
    assert result.status == "removed"
    assert result.message == HOSTED_SUBMISSION_REMOVED


def test_publisher_removed_even_when_enabled() -> None:
    client = MockPlatformClient()
    result = publish_assessment_to_platform(
        client=client,
        config=PlatformClientConfig(
            enabled=True,
            organization_id="org:1",
            workspace_id="workspace:1",
        ),
        repository=_repo(),
        configured_repository_url=None,
        html_report_path=Path("/tmp/report.html"),
        json_report_path=Path("/tmp/report.json"),
    )
    assert result.status == "removed"
    assert result.message == HOSTED_SUBMISSION_REMOVED
    assert result.assessment_id is None


def test_enabled_settings_still_compose_offline_client() -> None:
    class Settings:
        platform = PlatformIntegrationSettings(enabled=True, auth_token="secret")

    client = platform_client_from_settings(Settings())
    assert isinstance(client, OfflinePlatformClient)
