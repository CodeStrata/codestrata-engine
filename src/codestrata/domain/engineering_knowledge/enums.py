"""Engineering Knowledge Graph vocabulary and supporting classifications.

The Engineering Knowledge Graph models reusable engineering concepts
(technologies, patterns, practices, rules). It is peer to the Repository Graph
and must not encode repository-specific facts such as ``this repo uses Spring``.
"""

from __future__ import annotations

from enum import StrEnum


class EngineeringKnowledgeNodeType(StrEnum):
    """Canonical node kinds for reusable engineering knowledge."""

    TECHNOLOGY = "technology"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    LANGUAGE = "language"
    RUNTIME = "runtime"
    BUILD_TOOL = "build_tool"
    PLATFORM = "platform"
    PLATFORM_CAPABILITY = "platform_capability"
    ARCHITECTURE_STYLE = "architecture_style"
    DESIGN_PATTERN = "design_pattern"
    ANTI_PATTERN = "anti_pattern"
    QUALITY_ATTRIBUTE = "quality_attribute"
    ENGINEERING_PRACTICE = "engineering_practice"
    RISK_TYPE = "risk_type"
    MODERNIZATION_STRATEGY = "modernization_strategy"
    RULE = "rule"
    CONSTRAINT = "constraint"


class EngineeringKnowledgeRelationshipType(StrEnum):
    """Canonical relationship kinds between knowledge concepts."""

    IS_A = "is_a"
    PART_OF = "part_of"
    DEPENDS_ON = "depends_on"
    COMPATIBLE_WITH = "compatible_with"
    CONFLICTS_WITH = "conflicts_with"
    SUPERSEDES = "supersedes"
    SUPPORTS = "supports"
    IMPACTS = "impacts"
    MITIGATES = "mitigates"
    INCREASES_RISK = "increases_risk"
    ADDRESSES = "addresses"
    RECOMMENDS = "recommends"
    REQUIRES = "requires"
    GOVERNED_BY = "governed_by"
    RELATED_TO = "related_to"


class TechnologyLifecycleStatus(StrEnum):
    """Lifecycle posture for technologies and frameworks."""

    CURRENT = "current"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"
    END_OF_SUPPORT = "end_of_support"
    OBSOLETE = "obsolete"
    UNKNOWN = "unknown"


class KnowledgeMaturityLevel(StrEnum):
    """Maturity classification for engineering practices."""

    EMERGING = "emerging"
    DEVELOPING = "developing"
    ESTABLISHED = "established"
    OPTIMIZED = "optimized"
    UNKNOWN = "unknown"


class KnowledgeSeverity(StrEnum):
    """Severity scale for knowledge risks and rules."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ModernizationStrategyKind(StrEnum):
    """High-level modernization strategy categories."""

    RETAIN = "retain"
    RETIRE = "retire"
    REPURCHASE = "repurchase"
    REHOST = "rehost"
    RELOCATE = "relocate"
    REPLATFORM = "replatform"
    REFACTOR = "refactor"
    REARCHITECT = "rearchitect"
    REBUILD = "rebuild"
    REPLACE = "replace"
    UNKNOWN = "unknown"


class KnowledgeRuleKind(StrEnum):
    """Classification for reusable engineering rules."""

    COMPATIBILITY = "compatibility"
    LIFECYCLE = "lifecycle"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    SCALABILITY = "scalability"
    OPERABILITY = "operability"
    MODERNIZATION = "modernization"
    GOVERNANCE = "governance"
    UNKNOWN = "unknown"
