"""Unit tests for provider_contracts.compatibility and relationship."""

from __future__ import annotations

from codestrata.ai.provider_contracts.compatibility import (
    ContractCompatibilityStatement,
    build_contract_compatibility_statements,
)
from codestrata.ai.provider_contracts.policy import REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
from codestrata.ai.provider_contracts.relationship import (
    AbstractionClassification,
    build_abstraction_classifications,
)


def test_compatibility_statements_cover_all_six_crs() -> None:
    statements = build_contract_compatibility_statements()
    assert {s.requirement_id for s in statements} == set(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS)
    assert len(statements) == 6


def test_all_compatibility_statements_hold() -> None:
    for statement in build_contract_compatibility_statements():
        assert isinstance(statement, ContractCompatibilityStatement)
        assert statement.holds is True
        assert statement.explanation.strip()


def test_relationship_classifies_legacy_and_new_abstractions() -> None:
    classifications = build_abstraction_classifications()
    by_path = {c.dotted_path: c for c in classifications}
    assert isinstance(classifications[0], AbstractionClassification)

    legacy_provider = by_path["codestrata.ai.providers.base.AIModelProvider"]
    assert legacy_provider.classification == "legacy_capability_specific_invoke_abc"
    assert legacy_provider.status == "retained_unchanged"

    legacy_registry = by_path["codestrata.extensions.assess_ai.AssessAIProviderRegistry"]
    assert legacy_registry.classification == "legacy_runtime_selection_registry"
    assert legacy_registry.status == "retained_unchanged"

    new_provider = by_path["codestrata.ai.provider_contracts.provider.AIProvider"]
    assert new_provider.classification == "future_foundation_unwired"
    assert new_provider.status == "new_unwired"

    new_registry = by_path["codestrata.ai.provider_contracts.registry.AIProviderRegistry"]
    assert new_registry.classification == "future_foundation_unwired"
    assert new_registry.status == "new_unwired"


def test_relationship_does_not_import_the_classes_it_describes() -> None:
    # A purely-documentation module: dotted paths are strings only.
    import codestrata.ai.provider_contracts.relationship as relationship_module

    source = relationship_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import codestrata.ai.providers" not in text
    assert "from codestrata.ai.providers" not in text
    assert "from codestrata.extensions" not in text
