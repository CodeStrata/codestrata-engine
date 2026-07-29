"""Repository performance evidence service (Phase 4.9.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_performance.collector import (
    collect_repository_performance_evidence,
)
from codestrata.application.evidence.repository_performance.discovery import (
    DEFAULT_IGNORE_MARKERS,
)
from codestrata.config.settings import CodestrataSettings, RepositoryPerformanceEvidenceSettings
from codestrata.domain.evidence.repository_performance.enums import (
    RepositoryPerformanceParseStatus,
)
from codestrata.domain.evidence.repository_performance.models import (
    AggregatedRepositoryPerformanceEvidence,
)


class RepositoryPerformanceEvidenceService:
    """Collect deterministic repository-observable performance evidence."""

    def __init__(self, settings: RepositoryPerformanceEvidenceSettings | None = None) -> None:
        self._settings = settings or RepositoryPerformanceEvidenceSettings()

    @property
    def settings(self) -> RepositoryPerformanceEvidenceSettings:
        return self._settings

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        load_errors: Mapping[str, str] | None = None,
        configuration_fingerprint: str = "",
    ) -> AggregatedRepositoryPerformanceEvidence:
        if not self._settings.enabled:
            return AggregatedRepositoryPerformanceEvidence(
                repository_id=repository_id,
                status=RepositoryPerformanceParseStatus.NOT_APPLICABLE,
                diagnostics=(),
                limitations=(),
                evidence_fingerprint="",
            )

        ignore = tuple(self._settings.ignore_path_markers) or DEFAULT_IGNORE_MARKERS
        return collect_repository_performance_evidence(
            repository_id=repository_id,
            relative_paths=relative_paths,
            file_texts=file_texts,
            load_errors=load_errors,
            ignore_path_markers=ignore,
            max_files=self._settings.max_files,
            configuration_fingerprint=configuration_fingerprint
            or f"evidence.repository_performance.enabled={self._settings.enabled}",
        )


def create_repository_performance_evidence_service(
    settings: CodestrataSettings | None = None,
) -> RepositoryPerformanceEvidenceService:
    if settings is None:
        return RepositoryPerformanceEvidenceService()
    return RepositoryPerformanceEvidenceService(settings.evidence.repository_performance)


def repository_performance_evidence_collection_enabled(
    settings: CodestrataSettings | None,
) -> bool:
    if settings is None:
        return False
    return bool(settings.evidence.repository_performance.enabled)
