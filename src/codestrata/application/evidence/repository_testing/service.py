"""Repository-testing evidence service (Phase 4.6.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_testing.collector import (
    collect_repository_testing_evidence,
)
from codestrata.application.evidence.repository_testing.discovery import (
    DEFAULT_IGNORE_MARKERS,
)
from codestrata.config.settings import CodestrataSettings, RepositoryTestingEvidenceSettings
from codestrata.domain.evidence.repository_testing.enums import (
    RepositoryTestingParseStatus,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
)


class RepositoryTestingEvidenceService:
    """Collect deterministic repository-observable testing evidence."""

    def __init__(
        self, settings: RepositoryTestingEvidenceSettings | None = None
    ) -> None:
        self._settings = settings or RepositoryTestingEvidenceSettings()

    @property
    def settings(self) -> RepositoryTestingEvidenceSettings:
        return self._settings

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        load_errors: Mapping[str, str] | None = None,
        configuration_fingerprint: str = "",
    ) -> AggregatedRepositoryTestingEvidence:
        if not self._settings.enabled:
            return AggregatedRepositoryTestingEvidence(
                repository_id=repository_id,
                status=RepositoryTestingParseStatus.NOT_APPLICABLE,
                diagnostics=(),
                limitations=(),
                evidence_fingerprint="",
            )

        ignore = (
            tuple(self._settings.ignore_path_markers) or DEFAULT_IGNORE_MARKERS
        )
        return collect_repository_testing_evidence(
            repository_id=repository_id,
            relative_paths=relative_paths,
            file_texts=file_texts,
            load_errors=load_errors,
            ignore_path_markers=ignore,
            max_files=self._settings.max_files,
            configuration_fingerprint=configuration_fingerprint
            or f"evidence.repository_testing.enabled={self._settings.enabled}",
        )


def create_repository_testing_evidence_service(
    settings: CodestrataSettings | None = None,
) -> RepositoryTestingEvidenceService:
    if settings is None:
        return RepositoryTestingEvidenceService()
    return RepositoryTestingEvidenceService(settings.evidence.repository_testing)


def repository_testing_evidence_collection_enabled(
    settings: CodestrataSettings | None,
) -> bool:
    if settings is None:
        return False
    return bool(settings.evidence.repository_testing.enabled)
