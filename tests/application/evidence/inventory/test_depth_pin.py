"""Pinned extractor depth matches live providers and collectors."""

from __future__ import annotations

from codestrata.application.evidence.inventory.catalog import build_extractor_depth_pin
from codestrata.application.evidence.inventory.models import SupportKind
from codestrata.application.evidence.language.factory import create_language_evidence_service
from codestrata.application.evidence.language.providers import (
    CsharpLanguageEvidenceProvider,
    JavaLanguageEvidenceProvider,
    JavaScriptLanguageEvidenceProvider,
    PhpLanguageEvidenceProvider,
    PythonLanguageEvidenceProvider,
)
from codestrata.domain.evidence.language.capabilities import CapabilityMaturity
from codestrata.domain.evidence.language.capability_catalog import (
    CAP_FRAMEWORK_USAGE,
    CAP_SOURCE_SYMBOLS,
)


def test_depth_pin_matches_live_language_providers() -> None:
    pin = build_extractor_depth_pin()
    assert pin.languages == ("csharp", "java", "javascript", "php", "python")
    service = create_language_evidence_service()
    ids = {row["provider_id"] for row in service.list_providers()}
    assert ids == {
        "language.csharp.core",
        "language.java.core",
        "language.javascript.core",
        "language.php.core",
        "language.python.core",
    }


def test_javascript_complexity_and_framework_usage_are_structural_scans() -> None:
    pin = build_extractor_depth_pin()
    js = next(
        item for item in pin.fact_mappings if item.extractor_id == "language.javascript.complexity"
    )
    assert js.support is SupportKind.STRUCTURAL
    framework = next(
        item
        for item in pin.fact_mappings
        if item.extractor_id == "language.javascript.core" and item.fact_kind == "framework.usage"
    )
    assert framework.support is SupportKind.STRUCTURAL
    provider = JavaScriptLanguageEvidenceProvider()
    assert provider.SUPPORTED_DEPTH.complexity_provider_id == "language.javascript.complexity"
    assert provider.SUPPORTED_DEPTH.framework_structural is True
    assert "next" in provider.SUPPORTED_DEPTH.supported_frameworks
    assert "nestjs" in provider.SUPPORTED_DEPTH.supported_frameworks
    assert "svelte" in provider.SUPPORTED_DEPTH.supported_frameworks
    assert any(
        d.capability_id == CAP_FRAMEWORK_USAGE and d.maturity is CapabilityMaturity.PARTIAL
        for d in provider.metadata.capabilities.supported
    )
    assert CAP_FRAMEWORK_USAGE not in provider.metadata.capabilities.unsupported
    assert CAP_SOURCE_SYMBOLS in provider.metadata.capabilities.unsupported


def test_provider_pins_are_attached_to_the_five_providers() -> None:
    mapping = {
        JavaLanguageEvidenceProvider: "java",
        JavaScriptLanguageEvidenceProvider: "javascript",
        PythonLanguageEvidenceProvider: "python",
        PhpLanguageEvidenceProvider: "php",
        CsharpLanguageEvidenceProvider: "csharp",
    }
    for cls, language in mapping.items():
        provider = cls()
        assert provider.SUPPORTED_DEPTH.language == language
        assert str(provider.metadata.provider_id) == provider.SUPPORTED_DEPTH.provider_id


def test_npm_inventory_collector_is_structural_outside_dependency_ecosystem() -> None:
    pin = build_extractor_depth_pin()
    by_eco = {item.ecosystem: item for item in pin.manifests}
    assert by_eco["npm"].support is SupportKind.STRUCTURAL
    assert by_eco["npm"].structural_collector is not None
    from codestrata.application.evidence.dependency.paths import classify_manifest_basename

    assert classify_manifest_basename("package.json") is None
    assert by_eco["composer"].limitations
    assert by_eco["nuget"].limitations
    assert "lock" in by_eco["composer"].limitations.lower()
    github = next(item for item in pin.ci if item.provider == "github-actions")
    gitlab = next(item for item in pin.ci if item.provider == "gitlab-ci")
    assert github.support is SupportKind.STRUCTURAL
    assert gitlab.support is SupportKind.DETECTION_ONLY
