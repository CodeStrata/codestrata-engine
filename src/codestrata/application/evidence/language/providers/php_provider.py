"""PHP language evidence provider."""

from __future__ import annotations

import time
from typing import Any

from codestrata.application.evidence.language.adapters import bundle_from_raw_facts
from codestrata.application.rules.architecture.view_builder import collect_raw_package_facts
from codestrata.domain.evidence.language.capabilities import CapabilityMaturity
from codestrata.domain.evidence.language.capability_catalog import (
    CAP_ARCHITECTURE_LAYERS,
    CAP_ARCHITECTURE_UNITS,
    CAP_BUILD_DEPENDENCIES,
    CAP_BUILD_MODULES,
    CAP_DEPENDENCIES_IMPORTS,
    CAP_DEPENDENCIES_RUNTIME,
    CAP_DEPENDENCIES_TYPE_ONLY,
    CAP_FRAMEWORK_USAGE,
    CAP_SOURCE_FILES,
    CAP_SOURCE_SYMBOLS,
    CAP_TESTS_PRESENCE,
    EvidenceCapabilityDeclaration,
    ProviderCapabilitySet,
)
from codestrata.domain.evidence.language.contracts import (
    LanguageEvidenceCollectionResult,
    LanguageEvidenceContext,
    LanguageEvidenceProviderMetadata,
    ProviderApplicability,
)
from codestrata.domain.evidence.language.identifiers import LanguageEvidenceProviderId


class PhpLanguageEvidenceProvider:
    PROVIDER_ID = "language.php.core"
    PROVIDER_VERSION = "1.0.0"

    def __init__(self) -> None:
        self._metadata = LanguageEvidenceProviderMetadata(
            provider_id=LanguageEvidenceProviderId(self.PROVIDER_ID),
            provider_version=self.PROVIDER_VERSION,
            title="PHP Core Language Evidence",
            description=(
                "Collects PHP use/require edges and path- or namespace-based units "
                "using existing architecture extractors. Composer package graphs "
                "are collected separately by Dependency Evidence."
            ),
            supported_languages=("php",),
            supported_file_extensions=(".php",),
            supported_frameworks=("laravel", "symfony", "codeigniter", "laminas"),
            capabilities=ProviderCapabilitySet(
                supported=(
                    EvidenceCapabilityDeclaration(
                        capability_id=CAP_SOURCE_FILES,
                        maturity=CapabilityMaturity.PARTIAL,
                    ),
                    EvidenceCapabilityDeclaration(
                        capability_id=CAP_DEPENDENCIES_IMPORTS,
                        maturity=CapabilityMaturity.PARTIAL,
                        limitations="use / require / include only; no full AST.",
                    ),
                    EvidenceCapabilityDeclaration(
                        capability_id=CAP_DEPENDENCIES_RUNTIME,
                        maturity=CapabilityMaturity.PARTIAL,
                    ),
                    EvidenceCapabilityDeclaration(
                        capability_id=CAP_ARCHITECTURE_UNITS,
                        maturity=CapabilityMaturity.EXPERIMENTAL,
                        limitations="Namespace or directory path units.",
                    ),
                    EvidenceCapabilityDeclaration(
                        capability_id=CAP_ARCHITECTURE_LAYERS,
                        maturity=CapabilityMaturity.EXPERIMENTAL,
                    ),
                    EvidenceCapabilityDeclaration(
                        capability_id=CAP_FRAMEWORK_USAGE,
                        maturity=CapabilityMaturity.PARTIAL,
                        limitations="Illuminate/Symfony/Doctrine/CodeIgniter/Laminas markers.",
                    ),
                    EvidenceCapabilityDeclaration(
                        capability_id=CAP_TESTS_PRESENCE,
                        maturity=CapabilityMaturity.PARTIAL,
                    ),
                ),
                unsupported=(
                    CAP_SOURCE_SYMBOLS,
                    CAP_DEPENDENCIES_TYPE_ONLY,
                    CAP_BUILD_MODULES,
                    CAP_BUILD_DEPENDENCIES,
                ),
            ),
            documentation_reference=("docs/rule-engine.md"),
        )

    @property
    def metadata(self) -> LanguageEvidenceProviderMetadata:
        return self._metadata

    def evaluate_applicability(self, context: LanguageEvidenceContext) -> ProviderApplicability:
        php_paths = [
            path
            for path in context.relative_paths
            if path.replace("\\", "/").lower().endswith(".php")
        ]
        if not php_paths:
            return ProviderApplicability.not_applicable("no_php_source_files")
        return ProviderApplicability.applicable(detected_languages=("php",))

    def collect(self, context: LanguageEvidenceContext) -> LanguageEvidenceCollectionResult:
        started = time.perf_counter()
        applicability = self.evaluate_applicability(context)
        if applicability.status.value == "not_applicable":
            return LanguageEvidenceCollectionResult.not_applicable(
                applicability.message or "not_applicable"
            )
        php_paths = [
            path
            for path in context.relative_paths
            if path.replace("\\", "/").lower().endswith(".php")
        ]
        if not any(path in context.file_texts for path in php_paths):
            return LanguageEvidenceCollectionResult.insufficient_input(
                "php_files_present_but_source_text_unavailable"
            )
        try:
            facts = collect_raw_package_facts(
                relative_paths=context.relative_paths,
                file_texts=context.file_texts,
                language_filter="php",
                ignore_path_markers=_ignore_markers(context),
            )
            bundle = bundle_from_raw_facts(
                facts=facts,
                provider_id=self.PROVIDER_ID,
                provider_version=self.PROVIDER_VERSION,
                language="php",
                configuration_fingerprint=context.configuration.get("fingerprint", ""),
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            if facts.files_parsed == 0 and facts.files_considered > 0:
                return LanguageEvidenceCollectionResult.partially_succeeded(
                    bundle,
                    message="no_php_texts_parsed",
                    duration_ms=duration_ms,
                )
            return LanguageEvidenceCollectionResult.succeeded(bundle, duration_ms=duration_ms)
        except Exception as error:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started) * 1000)
            return LanguageEvidenceCollectionResult.failed(
                f"{type(error).__name__}: provider collection failed",
                duration_ms=duration_ms,
            )

    def explain_applicability(self, context: LanguageEvidenceContext) -> dict[str, Any]:
        applicability = self.evaluate_applicability(context)
        return {
            "provider_id": self.PROVIDER_ID,
            "provider_version": self.PROVIDER_VERSION,
            "status": str(applicability.status),
            "message": applicability.message,
            "supported_languages": list(self.metadata.supported_languages),
            "detected_languages": list(applicability.detected_languages),
        }


def _ignore_markers(context: LanguageEvidenceContext) -> tuple[str, ...]:
    raw = context.configuration.get("ignore_path_markers", "")
    if not raw.strip():
        return ("/generated/", "/.generated/", "/vendor/")
    return tuple(item.strip() for item in raw.split(",") if item.strip())
