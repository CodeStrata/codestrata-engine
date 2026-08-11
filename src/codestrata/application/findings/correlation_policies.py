"""Explicit reviewed Finding correlation policies (Slice 5.12).

Policies are deterministic, conservative, and testable. Title similarity never
implies a policy.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.dependency.ids import (
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNRESOLVED_VERSION,
)
from codestrata.domain.findings.correlation import (
    CorrelationDirection,
    CorrelationConfidenceLevel,
    FindingCorrelationBasis,
    FindingCorrelationType,
)
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)
from codestrata.domain.security.ids import (
    RULE_CREDENTIAL_LITERAL,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)
from codestrata.domain.technical_debt.ids import (
    RULE_DEEP_NESTING,
    RULE_EXCESSIVE_BRANCHING,
    RULE_LARGE_CALLABLE,
)
from codestrata.domain.traceability.validators import normalize_limitations


class FindingCorrelationPolicy(BaseModel):
    """One reviewed rule-to-rule correlation policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    rule_ids: tuple[str, ...]
    correlation_type: FindingCorrelationType
    required_bases: tuple[FindingCorrelationBasis, ...]
    direction: CorrelationDirection = CorrelationDirection.UNDIRECTED
    minimum_confidence: CorrelationConfidenceLevel = CorrelationConfidenceLevel.MODERATE
    cross_head_allowed: bool = False
    limitations: tuple[str, ...] = ()

    @field_validator("policy_id", mode="before")
    @classmethod
    def require_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="policy_id")

    @field_validator("rule_ids", mode="before")
    @classmethod
    def normalize_rules(cls, value: object) -> tuple[str, ...]:
        items = tuple(
            sorted(
                {
                    require_nonblank(str(item), label="rule_id").strip()
                    for item in as_tuple(value)
                }
            )
        )
        if len(items) < 2:
            raise ValueError("policy requires at least two rule_ids")
        return items

    @field_validator("required_bases", mode="before")
    @classmethod
    def normalize_bases(cls, value: object) -> tuple[Any, ...]:
        items = tuple(as_tuple(value))
        if not items:
            raise ValueError("policy requires required_bases")
        return items

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)


CORRELATION_POLICIES: tuple[FindingCorrelationPolicy, ...] = (
    FindingCorrelationPolicy(
        policy_id="security.config.credential-placeholder",
        rule_ids=(RULE_CREDENTIAL_LITERAL, RULE_PLACEHOLDER_CREDENTIAL),
        correlation_type=FindingCorrelationType.CONFIGURATION_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_CONFIGURATION_KEY,
            FindingCorrelationBasis.SAME_PATH,
        ),
        minimum_confidence=CorrelationConfidenceLevel.HIGH,
        limitations=(
            "Correlates only when the same configuration key and path are shared.",
        ),
    ),
    FindingCorrelationPolicy(
        policy_id="security.config.tls-hostname",
        rule_ids=(
            RULE_TLS_VERIFICATION_DISABLED,
            RULE_HOSTNAME_VERIFICATION_DISABLED,
        ),
        correlation_type=FindingCorrelationType.CONFIGURATION_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_PATH,
            FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        ),
        minimum_confidence=CorrelationConfidenceLevel.HIGH,
        limitations=("Same configuration boundary; transport verification family.",),
    ),
    FindingCorrelationPolicy(
        policy_id="dependency.declaration.duplicate-conflict",
        rule_ids=(RULE_DUPLICATE_DECLARATION, RULE_CONFLICTING_EXACT_VERSIONS),
        correlation_type=FindingCorrelationType.DEPENDENCY_CLUSTER,
        required_bases=(FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY,),
        minimum_confidence=CorrelationConfidenceLevel.HIGH,
        limitations=("Same dependency identity and comparison scope required.",),
    ),
    FindingCorrelationPolicy(
        policy_id="dependency.declaration.mutable-duplicate",
        rule_ids=(RULE_MUTABLE_VERSION, RULE_DUPLICATE_DECLARATION),
        correlation_type=FindingCorrelationType.DEPENDENCY_CLUSTER,
        required_bases=(FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY,),
        minimum_confidence=CorrelationConfidenceLevel.HIGH,
    ),
    FindingCorrelationPolicy(
        policy_id="dependency.declaration.unresolved-mutable",
        rule_ids=(RULE_UNRESOLVED_VERSION, RULE_MUTABLE_VERSION),
        correlation_type=FindingCorrelationType.DEPENDENCY_CLUSTER,
        required_bases=(FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY,),
        minimum_confidence=CorrelationConfidenceLevel.MODERATE,
    ),
    FindingCorrelationPolicy(
        policy_id="technical_debt.callable.branching-nesting",
        rule_ids=(RULE_EXCESSIVE_BRANCHING, RULE_DEEP_NESTING),
        correlation_type=FindingCorrelationType.COMPLEXITY_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_PATH,
            FindingCorrelationBasis.SAME_SYMBOLIC_REFERENCE,
        ),
        minimum_confidence=CorrelationConfidenceLevel.HIGH,
    ),
    FindingCorrelationPolicy(
        policy_id="technical_debt.callable.large-branching",
        rule_ids=(RULE_LARGE_CALLABLE, RULE_EXCESSIVE_BRANCHING),
        correlation_type=FindingCorrelationType.COMPLEXITY_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_PATH,
            FindingCorrelationBasis.SAME_SYMBOLIC_REFERENCE,
        ),
        minimum_confidence=CorrelationConfidenceLevel.HIGH,
    ),
    FindingCorrelationPolicy(
        policy_id="architecture.edge.direction-boundary",
        rule_ids=(RULE_INVALID_DEPENDENCY_DIRECTION, RULE_LAYER_BOUNDARY_VIOLATION),
        correlation_type=FindingCorrelationType.ARCHITECTURE_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_GRAPH_EDGE,
            FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        ),
        minimum_confidence=CorrelationConfidenceLevel.HIGH,
        limitations=("Same directed graph edge identity required.",),
    ),
    FindingCorrelationPolicy(
        policy_id="architecture.edge.cycle-direction",
        rule_ids=(RULE_DEPENDENCY_CYCLE, RULE_INVALID_DEPENDENCY_DIRECTION),
        correlation_type=FindingCorrelationType.ARCHITECTURE_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_GRAPH_NODE,
            FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        ),
        minimum_confidence=CorrelationConfidenceLevel.MODERATE,
    ),
    FindingCorrelationPolicy(
        policy_id="architecture.unit.framework-boundary",
        rule_ids=(RULE_FRAMEWORK_LEAKAGE, RULE_LAYER_BOUNDARY_VIOLATION),
        correlation_type=FindingCorrelationType.ARCHITECTURE_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_GRAPH_NODE,
            FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        ),
        minimum_confidence=CorrelationConfidenceLevel.MODERATE,
    ),
    FindingCorrelationPolicy(
        policy_id="architecture.unit.concentration-coupling",
        rule_ids=(RULE_COMPONENT_CONCENTRATION, RULE_EXCESSIVE_CROSS_MODULE_COUPLING),
        correlation_type=FindingCorrelationType.ARCHITECTURE_CLUSTER,
        required_bases=(
            FindingCorrelationBasis.SAME_GRAPH_NODE,
            FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        ),
        minimum_confidence=CorrelationConfidenceLevel.MODERATE,
        limitations=("Coupling remains separate from boundary clusters (Option A).",),
    ),
)


def policies_for_rules(rule_a: str, rule_b: str) -> tuple[FindingCorrelationPolicy, ...]:
    pair = frozenset({rule_a, rule_b})
    return tuple(
        policy for policy in CORRELATION_POLICIES if pair.issubset(set(policy.rule_ids))
    )


def all_correlation_policies() -> tuple[FindingCorrelationPolicy, ...]:
    return CORRELATION_POLICIES
