"""Tests for language evidence domain models and identifiers."""

from __future__ import annotations

import pytest

from codestrata.domain.evidence.language.capabilities import (
    DependencySemantics,
    ProviderApplicabilityStatus,
)
from codestrata.domain.evidence.language.contracts import (
    LanguageEvidenceProviderMetadata,
    ProviderApplicability,
)
from codestrata.domain.evidence.language.identifiers import (
    LanguageEvidenceProviderId,
    stable_evidence_id,
    validate_capability_id,
    validate_provider_id,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance


def test_provider_id_validation() -> None:
    assert validate_provider_id("language.python.core") == "language.python.core"
    with pytest.raises(ValueError):
        validate_provider_id("python")


def test_capability_id_validation() -> None:
    assert validate_capability_id("dependencies.imports") == "dependencies.imports"
    with pytest.raises(ValueError):
        validate_capability_id("imports")


def test_stable_evidence_id_deterministic() -> None:
    left = stable_evidence_id("dependency", "language.python.core", "a", "b", "runtime")
    right = stable_evidence_id("dependency", "language.python.core", "a", "b", "runtime")
    assert left == right
    assert left.startswith("ev:")


def test_provider_metadata_round_trip() -> None:
    meta = LanguageEvidenceProviderMetadata(
        provider_id=LanguageEvidenceProviderId("language.python.core"),
        provider_version="1.0.0",
        title="Python",
        description="Python evidence",
        supported_languages=("python",),
        supported_file_extensions=(".py",),
    )
    assert str(meta.provider_id) == "language.python.core"
    dumped = meta.model_dump(mode="json")
    assert dumped["provider_id"] == "language.python.core"


def test_applicability_states() -> None:
    assert ProviderApplicability.applicable().status is ProviderApplicabilityStatus.APPLICABLE
    assert (
        ProviderApplicability.not_applicable("x").status
        is ProviderApplicabilityStatus.NOT_APPLICABLE
    )
    assert (
        ProviderApplicability.insufficient_input("y").status
        is ProviderApplicabilityStatus.INSUFFICIENT_INPUT
    )


def test_provenance_frozen() -> None:
    provenance = EvidenceProvenance(
        provider_id="language.python.core",
        provider_version="1.0.0",
        transformation_chain=("a", "b"),
    )
    assert provenance.origin.value == "source_parse"
    assert DependencySemantics.TYPE_ONLY.value == "type_only"
