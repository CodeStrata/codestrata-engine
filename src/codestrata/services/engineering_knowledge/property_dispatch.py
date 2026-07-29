"""Static mapping from knowledge node types to typed property models.

Keeps property validation out of the loader's control flow so dispatch stays
deterministic and easy to audit.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from codestrata.domain.engineering_knowledge.enums import EngineeringKnowledgeNodeType
from codestrata.domain.engineering_knowledge.ids import normalize_canonical_key
from codestrata.domain.engineering_knowledge.properties import (
    ArchitectureStyleProperties,
    ConstraintProperties,
    EngineeringKnowledgeProperties,
    EngineeringPracticeProperties,
    FrameworkProperties,
    KnowledgePropertyModel,
    LanguageProperties,
    ModernizationStrategyProperties,
    PatternProperties,
    PlatformCapabilityProperties,
    QualityAttributeProperties,
    RiskTypeProperties,
    RuleProperties,
    TechnologyProperties,
)
from codestrata.services.engineering_knowledge.exceptions import (
    EngineeringKnowledgeCatalogValidationError,
)

_PROPERTY_MODEL_BY_NODE_TYPE: Mapping[
    EngineeringKnowledgeNodeType,
    type[KnowledgePropertyModel],
] = {
    EngineeringKnowledgeNodeType.TECHNOLOGY: TechnologyProperties,
    EngineeringKnowledgeNodeType.FRAMEWORK: FrameworkProperties,
    EngineeringKnowledgeNodeType.LANGUAGE: LanguageProperties,
    EngineeringKnowledgeNodeType.ARCHITECTURE_STYLE: ArchitectureStyleProperties,
    EngineeringKnowledgeNodeType.DESIGN_PATTERN: PatternProperties,
    EngineeringKnowledgeNodeType.ANTI_PATTERN: PatternProperties,
    EngineeringKnowledgeNodeType.QUALITY_ATTRIBUTE: QualityAttributeProperties,
    EngineeringKnowledgeNodeType.ENGINEERING_PRACTICE: EngineeringPracticeProperties,
    EngineeringKnowledgeNodeType.RISK_TYPE: RiskTypeProperties,
    EngineeringKnowledgeNodeType.MODERNIZATION_STRATEGY: ModernizationStrategyProperties,
    EngineeringKnowledgeNodeType.RULE: RuleProperties,
    EngineeringKnowledgeNodeType.CONSTRAINT: ConstraintProperties,
    EngineeringKnowledgeNodeType.PLATFORM_CAPABILITY: PlatformCapabilityProperties,
    # Remaining vocabulary uses the shared metadata model.
    EngineeringKnowledgeNodeType.LIBRARY: EngineeringKnowledgeProperties,
    EngineeringKnowledgeNodeType.RUNTIME: EngineeringKnowledgeProperties,
    EngineeringKnowledgeNodeType.BUILD_TOOL: EngineeringKnowledgeProperties,
    EngineeringKnowledgeNodeType.PLATFORM: EngineeringKnowledgeProperties,
}


def property_model_for(
    node_type: EngineeringKnowledgeNodeType,
) -> type[KnowledgePropertyModel]:
    """Return the property model class for a knowledge node type."""

    try:
        return _PROPERTY_MODEL_BY_NODE_TYPE[node_type]
    except KeyError as exc:  # pragma: no cover - enum exhaustiveness guard
        raise EngineeringKnowledgeCatalogValidationError(
            f"unsupported engineering knowledge node type '{node_type}'"
        ) from exc


def validate_node_properties(
    *,
    node_type: EngineeringKnowledgeNodeType,
    canonical_key: str,
    properties: Mapping[str, Any],
) -> KnowledgePropertyModel:
    """Validate catalog node properties with the typed model for ``node_type``.

    ``canonical_key`` from the catalog entry is authoritative and injected into
    the property payload when missing or conflicting.
    """

    model_cls = property_model_for(node_type)
    key = normalize_canonical_key(canonical_key)
    payload = dict(properties)
    existing = payload.get("canonical_key")
    if existing is not None and normalize_canonical_key(str(existing)) != key:
        raise EngineeringKnowledgeCatalogValidationError(
            f"properties.canonical_key '{existing}' does not match "
            f"entry canonical_key '{key}' for {node_type.value}"
        )
    payload["canonical_key"] = key
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise EngineeringKnowledgeCatalogValidationError(
            f"invalid properties for {node_type.value}:{key}: {exc}"
        ) from exc
