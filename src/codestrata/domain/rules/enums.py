"""Shared Rule Platform enumerations.

Severity reuses :class:`~codestrata.domain.findings.enums.FindingSeverity` to avoid a
second severity system. Confidence is platform-specific (evidence certainty).
"""

from __future__ import annotations

from enum import StrEnum

from codestrata.domain.findings.enums import FindingSeverity

# Re-export for rule authors — do not invent a parallel severity scale.
RuleSeverity = FindingSeverity


class RuleCategory(StrEnum):
    """High-level rule pack category."""

    ARCHITECTURE = "architecture"
    TECHNICAL_DEBT = "technical_debt"
    DEPENDENCY = "dependency"
    SECURITY = "security"
    TESTING = "testing"
    CLOUD = "cloud"
    AI_READINESS = "ai_readiness"
    PERFORMANCE = "performance"
    PLATFORM = "platform"
    EXPERIMENTAL = "experimental"


class RuleConfidence(StrEnum):
    """Deterministic evidence certainty (not business severity)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CERTAIN = "certain"


class RuleResultStatus(StrEnum):
    """Outcome of evaluating one shared rule."""

    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    NOT_APPLICABLE = "not_applicable"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


class RuleEvidenceKind(StrEnum):
    """Typed evidence subjects."""

    FILE_LOCATION = "file_location"
    SYMBOL = "symbol"
    PACKAGE = "package"
    MODULE = "module"
    DEPENDENCY = "dependency"
    GRAPH_NODE = "graph_node"
    GRAPH_EDGE = "graph_edge"
    CONFIGURATION_KEY = "configuration_key"
    REPOSITORY_FACT = "repository_fact"
    ENTERPRISE_RELATIONSHIP = "enterprise_relationship"
    ASSESSMENT_ARTIFACT = "assessment_artifact"


class RuleApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


class RuleSkipReason(StrEnum):
    DISABLED = "disabled"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    UNSUPPORTED_REPOSITORY_TYPE = "unsupported_repository_type"
    EXPLICITLY_EXCLUDED = "explicitly_excluded"
    CATEGORY_DISABLED = "category_disabled"
    MISSING_ENTERPRISE_CONTEXT = "missing_enterprise_context"
    STATIC_METADATA = "static_metadata"
    INCREMENTAL_REUSE = "incremental_reuse"
    NOT_SELECTED = "not_selected"
    OTHER = "other"


class RuleIncrementalBehavior(StrEnum):
    ALWAYS_RUN = "always_run"
    AFFECTED_BY_SOURCE_CHANGES = "affected_by_source_changes"
    AFFECTED_BY_DEPENDENCY_CHANGES = "affected_by_dependency_changes"
    AFFECTED_BY_BUILD_CHANGES = "affected_by_build_changes"
    AFFECTED_BY_GRAPH_CHANGES = "affected_by_graph_changes"
    AFFECTED_BY_ENTERPRISE_CONTEXT_CHANGES = "affected_by_enterprise_context_changes"
    SUPPORTS_SELECTIVE_EXECUTION = "supports_selective_execution"
    REQUIRES_FULL_CONTEXT = "requires_full_context"


class RuleSuppressionSource(StrEnum):
    CONFIGURATION = "configuration"
    MANUAL = "manual"
    ACCEPTED_RISK = "accepted_risk"
    SYSTEM = "system"
