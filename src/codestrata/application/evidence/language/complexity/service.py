"""Complexity evidence service and settings bridge (Phase 4.3.2).

Owned by the Language Evidence Platform. Not wired into Architecture
Intelligence assessment. Technical Debt may consume projections later.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.language.complexity.collector import (
    aggregate_complexity_bundles,
    collect_csharp_complexity_bundle,
    collect_java_complexity_bundle,
    collect_php_complexity_bundle,
    collect_python_complexity_bundle,
)
from codestrata.application.evidence.language.complexity.paths import (
    DEFAULT_COMPLEXITY_IGNORE_MARKERS,
)
from codestrata.config.settings import CodestrataSettings, ComplexityEvidenceSettings
from codestrata.domain.evidence.language.complexity.models import AggregatedComplexityEvidence


class ComplexityEvidenceService:
    """Collect deterministic complexity facts for supported languages."""

    def __init__(self, settings: ComplexityEvidenceSettings | None = None) -> None:
        self._settings = settings or ComplexityEvidenceSettings()

    @property
    def settings(self) -> ComplexityEvidenceSettings:
        return self._settings

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        configuration_fingerprint: str = "",
    ) -> AggregatedComplexityEvidence:
        if not self._settings.enabled:
            return AggregatedComplexityEvidence(
                repository_id=repository_id,
                diagnostics=("complexity_evidence_disabled",),
            )

        ignore = tuple(self._settings.ignore_path_markers) or DEFAULT_COMPLEXITY_IGNORE_MARKERS
        bundles = []
        if self._settings.python.enabled:
            bundles.append(
                collect_python_complexity_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        if self._settings.java.enabled:
            bundles.append(
                collect_java_complexity_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        if self._settings.php.enabled:
            bundles.append(
                collect_php_complexity_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        if self._settings.csharp.enabled:
            bundles.append(
                collect_csharp_complexity_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        # Drop empty language bundles that considered nothing and produced nothing.
        active = tuple(
            bundle
            for bundle in bundles
            if bundle.files_considered > 0 or bundle.files or bundle.diagnostics
        )
        return aggregate_complexity_bundles(repository_id=repository_id, bundles=active)


def create_complexity_evidence_service(
    settings: CodestrataSettings | None = None,
) -> ComplexityEvidenceService:
    if settings is None:
        return ComplexityEvidenceService()
    return ComplexityEvidenceService(settings.evidence.complexity)
