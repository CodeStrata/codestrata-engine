"""Reusable Engineering Knowledge Graph domain schema.

Models curated engineering knowledge (technologies, patterns, practices, rules)
independently of any repository. Peer to ``codestrata.domain.repository_graph`` on the
shared graph kernel; does not depend on repository inventory or extractors.
"""

from codestrata.domain.engineering_knowledge.enums import (
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeRelationshipType,
    KnowledgeMaturityLevel,
    KnowledgeRuleKind,
    KnowledgeSeverity,
    ModernizationStrategyKind,
    TechnologyLifecycleStatus,
)
from codestrata.domain.engineering_knowledge.factories import (
    ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
    EngineeringKnowledgeNodeFactory,
    EngineeringKnowledgeRelationshipFactory,
    build_engineering_knowledge_metadata,
)
from codestrata.domain.engineering_knowledge.ids import (
    EngineeringKnowledgeNodeIdFactory,
    EngineeringKnowledgeRelationshipIdFactory,
    normalize_canonical_key,
)
from codestrata.domain.engineering_knowledge.models import EngineeringKnowledgeGraph
from codestrata.domain.engineering_knowledge.properties import (
    ArchitectureStyleProperties,
    ConstraintProperties,
    EngineeringKnowledgeCatalogMetadata,
    EngineeringKnowledgeProperties,
    EngineeringPracticeProperties,
    FrameworkProperties,
    LanguageProperties,
    ModernizationStrategyProperties,
    PatternProperties,
    PlatformCapabilityProperties,
    QualityAttributeProperties,
    RiskTypeProperties,
    RuleProperties,
    TechnologyProperties,
)
from codestrata.domain.engineering_knowledge.schema import (
    EngineeringKnowledgeGraphSchema,
    EngineeringKnowledgeGraphSchemaError,
)

__all__ = [
    "ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION",
    "ArchitectureStyleProperties",
    "ConstraintProperties",
    "EngineeringKnowledgeCatalogMetadata",
    "EngineeringKnowledgeGraph",
    "EngineeringKnowledgeGraphSchema",
    "EngineeringKnowledgeGraphSchemaError",
    "EngineeringKnowledgeNodeFactory",
    "EngineeringKnowledgeNodeIdFactory",
    "EngineeringKnowledgeNodeType",
    "EngineeringKnowledgeProperties",
    "EngineeringKnowledgeRelationshipFactory",
    "EngineeringKnowledgeRelationshipIdFactory",
    "EngineeringKnowledgeRelationshipType",
    "EngineeringPracticeProperties",
    "FrameworkProperties",
    "KnowledgeMaturityLevel",
    "KnowledgeRuleKind",
    "KnowledgeSeverity",
    "LanguageProperties",
    "ModernizationStrategyKind",
    "ModernizationStrategyProperties",
    "PatternProperties",
    "PlatformCapabilityProperties",
    "QualityAttributeProperties",
    "RiskTypeProperties",
    "RuleProperties",
    "TechnologyLifecycleStatus",
    "TechnologyProperties",
    "build_engineering_knowledge_metadata",
    "normalize_canonical_key",
]
