"""Repository-cloud evidence service (Phase 4.7.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_cloud.collector import (
    collect_repository_cloud_evidence,
)
from codestrata.application.evidence.repository_cloud.discovery import DEFAULT_IGNORE_MARKERS
from codestrata.config.settings import CodestrataSettings, RepositoryCloudEvidenceSettings
from codestrata.domain.evidence.repository_cloud.enums import RepositoryCloudParseStatus
from codestrata.domain.evidence.repository_cloud.models import (
    AggregatedRepositoryCloudEvidence,
)


class RepositoryCloudEvidenceService:
    """Collect deterministic repository-observable cloud evidence."""

    def __init__(self, settings: RepositoryCloudEvidenceSettings | None = None) -> None:
        self._settings = settings or RepositoryCloudEvidenceSettings()

    @property
    def settings(self) -> RepositoryCloudEvidenceSettings:
        return self._settings

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        load_errors: Mapping[str, str] | None = None,
        configuration_fingerprint: str = "",
    ) -> AggregatedRepositoryCloudEvidence:
        if not self._settings.enabled:
            return AggregatedRepositoryCloudEvidence(
                repository_id=repository_id,
                status=RepositoryCloudParseStatus.NOT_APPLICABLE,
                diagnostics=(),
                limitations=(),
                evidence_fingerprint="",
            )

        ignore = tuple(self._settings.ignore_path_markers) or DEFAULT_IGNORE_MARKERS
        return collect_repository_cloud_evidence(
            repository_id=repository_id,
            relative_paths=relative_paths,
            file_texts=file_texts,
            load_errors=load_errors,
            ignore_path_markers=ignore,
            max_files=self._settings.max_files,
            configuration_fingerprint=configuration_fingerprint
            or f"evidence.repository_cloud.enabled={self._settings.enabled}",
        )


def create_repository_cloud_evidence_service(
    settings: CodestrataSettings | None = None,
) -> RepositoryCloudEvidenceService:
    if settings is None:
        return RepositoryCloudEvidenceService()
    return RepositoryCloudEvidenceService(settings.evidence.repository_cloud)


def repository_cloud_evidence_collection_enabled(
    settings: CodestrataSettings | None,
) -> bool:
    if settings is None:
        return False
    return bool(settings.evidence.repository_cloud.enabled)
