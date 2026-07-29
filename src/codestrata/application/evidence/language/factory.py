"""Composition root for language evidence providers."""

from __future__ import annotations

from codestrata.application.evidence.language.planner import LanguageEvidenceProviderPlanner
from codestrata.application.evidence.language.providers import (
    CsharpLanguageEvidenceProvider,
    JavaLanguageEvidenceProvider,
    JavaScriptLanguageEvidenceProvider,
    PhpLanguageEvidenceProvider,
    PythonLanguageEvidenceProvider,
)
from codestrata.application.evidence.language.raw_facts import PROVIDER_PRECEDENCE
from codestrata.application.evidence.language.registry import LanguageEvidenceProviderRegistry
from codestrata.application.evidence.language.service import LanguageEvidenceService
from codestrata.config.settings import CodestrataSettings, LanguageEvidenceSettings


def create_language_evidence_registry(
    settings: LanguageEvidenceSettings | None = None,
) -> LanguageEvidenceProviderRegistry:
    registry = LanguageEvidenceProviderRegistry()
    cfg = settings or LanguageEvidenceSettings()
    if cfg.python.enabled:
        registry.register(PythonLanguageEvidenceProvider())
    if cfg.java.enabled:
        registry.register(JavaLanguageEvidenceProvider())
    if cfg.javascript.enabled:
        registry.register(JavaScriptLanguageEvidenceProvider())
    if cfg.php.enabled:
        registry.register(PhpLanguageEvidenceProvider())
    if cfg.csharp.enabled:
        registry.register(CsharpLanguageEvidenceProvider())
    return registry


def create_language_evidence_service(
    settings: CodestrataSettings | None = None,
) -> LanguageEvidenceService:
    evidence_settings = (
        settings.evidence.language if settings is not None else LanguageEvidenceSettings()
    )
    registry = create_language_evidence_registry(evidence_settings)
    enabled_ids: frozenset[str] | None = None
    if not evidence_settings.providers.auto_detect:
        enabled_ids = frozenset(
            provider_id
            for provider_id, enabled in (
                ("language.python.core", evidence_settings.python.enabled),
                ("language.java.core", evidence_settings.java.enabled),
                ("language.javascript.core", evidence_settings.javascript.enabled),
                ("language.php.core", evidence_settings.php.enabled),
                ("language.csharp.core", evidence_settings.csharp.enabled),
            )
            if enabled
        )
    else:
        # Still respect per-provider enable toggles.
        enabled_ids = frozenset(
            provider_id
            for provider_id, enabled in (
                ("language.python.core", evidence_settings.python.enabled),
                ("language.java.core", evidence_settings.java.enabled),
                ("language.javascript.core", evidence_settings.javascript.enabled),
                ("language.php.core", evidence_settings.php.enabled),
                ("language.csharp.core", evidence_settings.csharp.enabled),
            )
            if enabled
        )
    precedence = tuple(evidence_settings.providers.precedence) or PROVIDER_PRECEDENCE
    planner = LanguageEvidenceProviderPlanner(
        registry,
        enabled_provider_ids=enabled_ids,
        auto_detect=evidence_settings.providers.auto_detect,
        precedence=precedence,
    )
    return LanguageEvidenceService(
        registry,
        planner=planner,
        fail_fast=evidence_settings.providers.fail_fast,
    )


def language_evidence_pipeline_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.evidence.language.enabled)
