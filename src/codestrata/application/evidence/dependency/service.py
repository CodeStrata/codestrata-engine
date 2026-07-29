"""Dependency Evidence service (Phase 4.4.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.dependency.collector import aggregate_dependency_bundles
from codestrata.application.evidence.dependency.composer_collector import (
    collect_composer_dependency_bundle,
)
from codestrata.application.evidence.dependency.gradle_collector import (
    collect_gradle_dependency_bundle,
)
from codestrata.application.evidence.dependency.maven_collector import (
    collect_maven_dependency_bundle,
)
from codestrata.application.evidence.dependency.nuget_collector import (
    collect_nuget_dependency_bundle,
)
from codestrata.application.evidence.dependency.paths import DEFAULT_DEPENDENCY_IGNORE_MARKERS
from codestrata.application.evidence.dependency.python_collector import (
    collect_python_dependency_bundle,
)
from codestrata.config.settings import CodestrataSettings, DependencyEvidenceSettings
from codestrata.domain.evidence.dependency.enums import DependencyParseStatus
from codestrata.domain.evidence.dependency.models import AggregatedDependencyEvidence


class DependencyEvidenceService:
    """Collect deterministic declared-dependency facts from supported manifests."""

    def __init__(self, settings: DependencyEvidenceSettings | None = None) -> None:
        self._settings = settings or DependencyEvidenceSettings()

    @property
    def settings(self) -> DependencyEvidenceSettings:
        return self._settings

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        configuration_fingerprint: str = "",
    ) -> AggregatedDependencyEvidence:
        if not self._settings.enabled:
            return AggregatedDependencyEvidence(
                repository_id=repository_id,
                status=DependencyParseStatus.NOT_APPLICABLE,
                diagnostics=("dependency_evidence_disabled",),
            )

        ignore = (
            tuple(self._settings.ignore_path_markers)
            or DEFAULT_DEPENDENCY_IGNORE_MARKERS
        )
        bundles = []
        if self._settings.maven.enabled:
            bundles.append(
                collect_maven_dependency_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        if self._settings.gradle.enabled:
            bundles.append(
                collect_gradle_dependency_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        if self._settings.python.enabled:
            bundles.append(
                collect_python_dependency_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        if self._settings.composer.enabled:
            bundles.append(
                collect_composer_dependency_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        if self._settings.nuget.enabled:
            bundles.append(
                collect_nuget_dependency_bundle(
                    relative_paths=relative_paths,
                    file_texts=file_texts,
                    ignore_path_markers=ignore,
                    max_files=self._settings.max_files,
                    max_file_chars=self._settings.max_file_chars,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
        active = tuple(
            bundle
            for bundle in bundles
            if bundle.coverage.manifests_supported > 0
            or bundle.manifests
            or bundle.declarations
            or bundle.diagnostics
        )
        return aggregate_dependency_bundles(
            repository_id=repository_id, bundles=active
        )


def create_dependency_evidence_service(
    settings: CodestrataSettings | None = None,
) -> DependencyEvidenceService:
    if settings is None:
        return DependencyEvidenceService()
    return DependencyEvidenceService(settings.evidence.dependency)
