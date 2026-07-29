"""Map Engine assessment artifacts to Platform ingestion requests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from codestrata import RULESET_VERSION, __version__
from codestrata.integration.commercial.models import (
    CompleteAssessmentRequest,
    RegisterAssessmentRequest,
    RegisterRepositoryRequest,
    ReportPointer,
)
from codestrata.models import Repository


def new_engine_assessment_id() -> str:
    return f"engine-assessment:{uuid4().hex}"


def infer_provider(repository_url: str) -> str:
    compact = repository_url.strip().lower()
    if "github.com" in compact:
        return "github"
    if "gitlab.com" in compact or "gitlab." in compact:
        return "gitlab"
    if "bitbucket.org" in compact:
        return "bitbucket"
    if "dev.azure.com" in compact or "visualstudio.com" in compact:
        return "azure_devops"
    return "other"


def technology_summary(repository: Repository) -> str:
    names = sorted({tech.name.strip() for tech in repository.technologies if tech.name.strip()})
    return ", ".join(names)


def to_register_repository_request(
    *,
    organization_id: str,
    workspace_id: str,
    repository: Repository,
    repository_url: str,
) -> RegisterRepositoryRequest:
    return RegisterRepositoryRequest(
        organization_id=organization_id,
        workspace_id=workspace_id,
        display_name=repository.name,
        repository_url=repository_url,
        provider=infer_provider(repository_url),
        default_branch=repository.default_branch or "main",
        visibility="private",
        description=repository.description,
        engine_repository_id=str(repository.id),
        metadata={
            "engine_repository_name": repository.name,
            "technology_summary": technology_summary(repository),
        },
    )


def to_register_assessment_request(
    *,
    repository_id: str,
    workspace_id: str,
    engine_assessment_id: str,
    repository: Repository,
    engine_version: str | None = None,
    assessment_version: str | None = None,
    started_at: datetime | None = None,
) -> RegisterAssessmentRequest:
    return RegisterAssessmentRequest(
        repository_id=repository_id,
        workspace_id=workspace_id,
        engine_assessment_id=engine_assessment_id,
        engine_version=engine_version or __version__,
        assessment_version=assessment_version or RULESET_VERSION,
        started_at=started_at or datetime.now(UTC),
        technology_summary=technology_summary(repository) or None,
        metadata={"engine_repository_id": str(repository.id)},
    )


def to_complete_assessment_request(
    *,
    assessment_id: str,
    html_report_path: Path | None,
    json_report_path: Path | None,
    completed_at: datetime | None = None,
) -> CompleteAssessmentRequest:
    reports: list[ReportPointer] = []
    if html_report_path is not None:
        reports.append(ReportPointer(report_type="html", location=str(html_report_path)))
    if json_report_path is not None:
        reports.append(ReportPointer(report_type="json", location=str(json_report_path)))
    return CompleteAssessmentRequest(
        assessment_id=assessment_id,
        generated_reports=tuple(reports),
        completed_at=completed_at or datetime.now(UTC),
    )


def resolve_repository_url(repository: Repository, configured_url: str | None) -> str | None:
    """Prefer scanned source URL, then configured repository URL."""

    for candidate in (repository.source_url, configured_url):
        if candidate is None:
            continue
        compact = candidate.strip()
        if compact.startswith(("http://", "https://")):
            return compact.rstrip("/")
    return None
