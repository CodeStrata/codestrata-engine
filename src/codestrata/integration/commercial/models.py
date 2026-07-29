"""Transport-neutral Platform integration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PlatformRepositoryRef:
    repository_id: str
    workspace_id: str
    organization_id: str
    display_name: str
    repository_url: str
    status: str
    created: bool = False


@dataclass(frozen=True, slots=True)
class PlatformAssessmentRef:
    assessment_id: str
    repository_id: str
    workspace_id: str
    engine_assessment_id: str
    engine_version: str
    assessment_version: str
    status: str


@dataclass(frozen=True, slots=True)
class RegisterRepositoryRequest:
    organization_id: str
    workspace_id: str
    display_name: str
    repository_url: str
    provider: str = "other"
    default_branch: str = "main"
    visibility: str = "private"
    description: str | None = None
    engine_repository_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegisterAssessmentRequest:
    repository_id: str
    workspace_id: str
    engine_assessment_id: str
    engine_version: str
    assessment_version: str
    started_at: datetime | None = None
    technology_summary: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportPointer:
    report_type: str
    location: str


@dataclass(frozen=True, slots=True)
class ReferencePointer:
    artifact_uri: str
    label: str | None = None


@dataclass(frozen=True, slots=True)
class CompleteAssessmentRequest:
    assessment_id: str
    generated_reports: tuple[ReportPointer, ...] = ()
    references: tuple[ReferencePointer, ...] = ()
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FailAssessmentRequest:
    assessment_id: str
    reason: str
