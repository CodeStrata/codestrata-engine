"""Repository-sensitive evidence service (Phase 4.5.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_sensitive.collector import (
    collect_repository_sensitive_evidence,
)
from codestrata.application.evidence.repository_sensitive.discovery import (
    DEFAULT_IGNORE_MARKERS,
)
from codestrata.config.settings import CodestrataSettings, RepositorySensitiveEvidenceSettings
from codestrata.domain.evidence.repository_sensitive.enums import (
    RepositorySensitiveParseStatus,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
)


class RepositorySensitiveEvidenceService:
    """Collect deterministic repository-visible security-relevant evidence."""

    def __init__(
        self, settings: RepositorySensitiveEvidenceSettings | None = None
    ) -> None:
        self._settings = settings or RepositorySensitiveEvidenceSettings()

    @property
    def settings(self) -> RepositorySensitiveEvidenceSettings:
        return self._settings

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        file_binaries: Mapping[str, bytes] | None = None,
        load_errors: Mapping[str, str] | None = None,
        configuration_fingerprint: str = "",
    ) -> AggregatedRepositorySensitiveEvidence:
        if not self._settings.enabled:
            return AggregatedRepositorySensitiveEvidence(
                repository_id=repository_id,
                status=RepositorySensitiveParseStatus.NOT_APPLICABLE,
                diagnostics=(),
                limitations=(),
                evidence_fingerprint="",
            )

        ignore = (
            tuple(self._settings.ignore_path_markers) or DEFAULT_IGNORE_MARKERS
        )
        return collect_repository_sensitive_evidence(
            repository_id=repository_id,
            relative_paths=relative_paths,
            file_texts=file_texts,
            file_binaries=file_binaries,
            load_errors=load_errors,
            ignore_path_markers=ignore,
            max_files=self._settings.max_files,
            configuration_fingerprint=configuration_fingerprint
            or f"evidence.repository_sensitive.enabled={self._settings.enabled}",
        )


def create_repository_sensitive_evidence_service(
    settings: CodestrataSettings | None = None,
) -> RepositorySensitiveEvidenceService:
    if settings is None:
        return RepositorySensitiveEvidenceService()
    return RepositorySensitiveEvidenceService(settings.evidence.repository_sensitive)


def repository_sensitive_evidence_collection_enabled(
    settings: CodestrataSettings | None,
) -> bool:
    if settings is None:
        return False
    return bool(settings.evidence.repository_sensitive.enabled)
