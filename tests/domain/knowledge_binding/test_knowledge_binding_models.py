"""Tests for Knowledge Binding domain contracts."""

from __future__ import annotations

import pytest

from codestrata.domain.graph import NodeId
from codestrata.domain.knowledge_binding import (
    KnowledgeBinding,
    KnowledgeBindingType,
    KnowledgeMatchingStrategy,
    KnowledgeObservationKind,
    build_knowledge_binding_id,
)


def test_binding_id_is_deterministic() -> None:
    first = build_knowledge_binding_id(
        repository_node_id="repo:demo:dependency:maven:_:spring-boot",
        knowledge_node_id="ekg:framework:spring-boot",
        matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
        matched_key="Spring Boot",
    )
    second = build_knowledge_binding_id(
        repository_node_id=NodeId("repo:demo:dependency:maven:_:spring-boot"),
        knowledge_node_id=NodeId("ekg:framework:spring-boot"),
        matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
        matched_key="spring-boot",
    )
    assert first == second
    assert first.startswith("kb:exact_canonical_key:")


def test_knowledge_binding_create_normalizes_key() -> None:
    binding = KnowledgeBinding.create(
        repository_node_id=NodeId("repo:demo:file:src/App.java"),
        knowledge_node_id=NodeId("ekg:language:java"),
        binding_type=KnowledgeBindingType.USES_CONCEPT,
        confidence=1.0,
        matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
        matched_key="Java",
        observation_kind=KnowledgeObservationKind.FILE_LANGUAGE,
        repository_node_type="file",
        knowledge_node_type="language",
    )
    assert binding.matched_key == "java"
    assert binding.binding_id.endswith(":java")
    dumped = binding.model_dump(mode="json")
    restored = KnowledgeBinding.model_validate(dumped)
    assert restored == binding


def test_knowledge_binding_rejects_blank_fields() -> None:
    with pytest.raises(ValueError, match="blank"):
        KnowledgeBinding.create(
            repository_node_id=NodeId("repo:demo:file:src/App.java"),
            knowledge_node_id=NodeId("ekg:language:java"),
            binding_type=KnowledgeBindingType.USES_CONCEPT,
            confidence=1.0,
            matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
            matched_key=" ",
            observation_kind=KnowledgeObservationKind.FILE_LANGUAGE,
            repository_node_type="file",
            knowledge_node_type="language",
        )
