"""Conservative inherent-confidence assignments for production Shared Rules."""

from __future__ import annotations

from codestrata.domain.rules.rule_confidence import (
    RuleConfidence,
    RuleConfidenceBasis,
    RuleConfidenceCalibrationStatus,
    RuleConfidenceLevel,
    RuleValidationSupport,
)


def _confidence(
    level: RuleConfidenceLevel,
    *basis: RuleConfidenceBasis,
    calibration: RuleConfidenceCalibrationStatus = RuleConfidenceCalibrationStatus.DEFINED,
    limitations: tuple[str, ...] = (),
    validation_set_id: str | None = None,
    validation_limitation: str | None = None,
) -> RuleConfidence:
    support = None
    if validation_set_id is not None:
        support = RuleValidationSupport(
            validation_set_id=validation_set_id,
            limitations=(validation_limitation or "Controlled-fixture scope; not universal.",),
        )
    return RuleConfidence(
        level=level,
        basis=basis,
        limitations=limitations,
        calibration_status=calibration,
        validation_support=support,
    )


def _fixture_defined(
    level: RuleConfidenceLevel,
    basis: RuleConfidenceBasis,
    scope: str,
    *,
    limitations: tuple[str, ...] = (),
) -> RuleConfidence:
    """Epic 4 fixtures exercise the rule, but counts are not attached here.

    Calibration stays ``defined`` until rule-level true-positive counts exist.
    Fixture scope remains an explicit limitation only.
    """

    fixture_limitation = (
        f"Epic 4 {scope} controlled-fixture regression exercises this rule; "
        "rule-level validation_support counts are not attached; not universal."
    )
    return _confidence(
        level,
        basis,
        limitations=(*limitations, fixture_limitation),
    )


_ARCHITECTURE = {
    "architecture.dependency-cycle": _fixture_defined(
        RuleConfidenceLevel.HIGH,
        RuleConfidenceBasis.STRUCTURAL_GRAPH_RELATIONSHIP,
        "architecture-signals",
    ),
    "architecture.layer-boundary-violation": _fixture_defined(
        RuleConfidenceLevel.HIGH,
        RuleConfidenceBasis.STRUCTURAL_GRAPH_RELATIONSHIP,
        "architecture-signals",
        limitations=("Depends on extracted layer classifications.",),
    ),
    "architecture.invalid-dependency-direction": _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.INFERRED_CLASSIFICATION,
        RuleConfidenceBasis.STRUCTURAL_GRAPH_RELATIONSHIP,
        limitations=("Depends on inferred architectural classifications.",),
    ),
    "architecture.excessive-cross-module-coupling": _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.STRUCTURAL_GRAPH_RELATIONSHIP,
        limitations=("Static graph coupling does not capture runtime coupling.",),
    ),
    "architecture.component-concentration": _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.STATIC_PATTERN,
        limitations=("Repository structure is a proxy for component ownership.",),
    ),
    "architecture.framework-leakage": _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.INFERRED_CLASSIFICATION,
        limitations=("Framework and boundary classifications are inferred.",),
    ),
    "architecture.enterprise-standard-mismatch": _confidence(
        RuleConfidenceLevel.LIMITED,
        RuleConfidenceBasis.INFERRED_CLASSIFICATION,
        limitations=("Requires complete and current enterprise standards context.",),
    ),
}

_TECHNICAL_DEBT = {
    rule_id: _fixture_defined(
        RuleConfidenceLevel.HIGH,
        RuleConfidenceBasis.DETERMINISTIC_THRESHOLD,
        "complexity-signals",
        limitations=("Threshold meaning varies by language and repository context.",),
    )
    for rule_id in (
        "technical_debt.large-callable",
        "technical_debt.excessive-branching",
        "technical_debt.deep-nesting",
        "technical_debt.excessive-parameters",
        "technical_debt.oversized-type",
    )
}

_DEPENDENCY = {
    rule_id: _fixture_defined(
        RuleConfidenceLevel.HIGH,
        RuleConfidenceBasis.MANIFEST_DECLARATION,
        "dependency-signals",
        limitations=("Assessment is limited to statically extracted manifest declarations.",),
    )
    for rule_id in (
        "dependency.unresolved-version",
        "dependency.mutable-version",
        "dependency.unbounded-requirement",
        "dependency.conflicting-exact-versions",
        "dependency.duplicate-declaration",
    )
}

_SECURITY = {
    "security.private-key-material": _confidence(
        RuleConfidenceLevel.HIGH,
        RuleConfidenceBasis.EXACT_SIGNATURE,
        limitations=("Detection is limited to inspected repository content.",),
    ),
    "security.credential-literal": _confidence(
        RuleConfidenceLevel.HIGH,
        RuleConfidenceBasis.EXPLICIT_CONFIGURATION,
        limitations=("Literal classification cannot determine whether a credential is active.",),
    ),
    "security.placeholder-credential": _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.EXPLICIT_CONFIGURATION,
        limitations=("Placeholder classification is a hygiene signal, not a secret finding.",),
    ),
    **{
        rule_id: _confidence(
            RuleConfidenceLevel.HIGH,
            RuleConfidenceBasis.EXPLICIT_CONFIGURATION,
            limitations=("Configuration scope and deployment environment are not inferred.",),
        )
        for rule_id in (
            "security.tls-verification-disabled",
            "security.hostname-verification-disabled",
            "security.authentication-disabled",
            "security.permissive-cors-origin",
            "security.debug-enabled",
        )
    },
}

_CLOUD_IDS = (
    "cloud.cloud-001",
    "cloud.cloud-002",
    "cloud.cloud-010",
    "cloud.cloud-011",
    "cloud.cloud-020",
    "cloud.cloud-021",
    "cloud.cloud-030",
    "cloud.cloud-040",
    "cloud.cloud-050",
)
_CLOUD = {
    rule_id: _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.STATIC_PATTERN,
        RuleConfidenceBasis.MANIFEST_DECLARATION,
        limitations=("Static repository signals do not prove deployed cloud topology.",),
    )
    for rule_id in _CLOUD_IDS
}
_CLOUD.update(
    {
        "cloud.cloud-060": _confidence(
            RuleConfidenceLevel.LIMITED,
            RuleConfidenceBasis.PARTIAL_EXTRACTION,
            RuleConfidenceBasis.INFERRED_CLASSIFICATION,
            calibration=RuleConfidenceCalibrationStatus.PROVISIONAL,
            limitations=("Broad cloud-native foundations are inferred from partial static signals.",),
        ),
        "cloud.cloud-061": _confidence(
            RuleConfidenceLevel.LIMITED,
            RuleConfidenceBasis.PARTIAL_EXTRACTION,
            limitations=("Absence of a detected platform may reflect incomplete extraction.",),
        ),
    }
)

_AI_MODERATE_IDS = (
    "ai_readiness.ai-001",
    "ai_readiness.ai-002",
    "ai_readiness.ai-010",
    "ai_readiness.ai-020",
    "ai_readiness.ai-021",
    "ai_readiness.ai-022",
    "ai_readiness.ai-030",
    "ai_readiness.ai-031",
    "ai_readiness.ai-032",
    "ai_readiness.ai-040",
    "ai_readiness.ai-041",
    "ai_readiness.ai-050",
)
_AI_READINESS = {
    rule_id: _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.STATIC_PATTERN,
        RuleConfidenceBasis.INFERRED_CLASSIFICATION,
        limitations=("Static signals indicate capability presence, not operational maturity.",),
    )
    for rule_id in _AI_MODERATE_IDS
}
_AI_READINESS.update(
    {
        rule_id: _confidence(
            RuleConfidenceLevel.LIMITED,
            RuleConfidenceBasis.PARTIAL_EXTRACTION,
            RuleConfidenceBasis.INFERRED_CLASSIFICATION,
            calibration=RuleConfidenceCalibrationStatus.PROVISIONAL,
            limitations=("Absence or breadth is inferred from partial repository extraction.",),
        )
        for rule_id in (
            "ai_readiness.ai-003",
            "ai_readiness.ai-011",
            "ai_readiness.ai-051",
            "ai_readiness.ai-060",
            "ai_readiness.ai-061",
        )
    }
)

_PERFORMANCE_MODERATE_IDS = (
    "performance.perf-001",
    "performance.perf-002",
    "performance.perf-010",
    "performance.perf-011",
    "performance.perf-020",
    "performance.perf-030",
    "performance.perf-031",
    "performance.perf-040",
    "performance.perf-050",
    "performance.perf-051",
    "performance.perf-060",
    "performance.perf-070",
)
_PERFORMANCE = {
    rule_id: _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.STATIC_PATTERN,
        limitations=("Static patterns do not establish runtime performance impact.",),
    )
    for rule_id in _PERFORMANCE_MODERATE_IDS
}
_PERFORMANCE.update(
    {
        rule_id: _confidence(
            RuleConfidenceLevel.LIMITED,
            RuleConfidenceBasis.PARTIAL_EXTRACTION,
            RuleConfidenceBasis.INFERRED_CLASSIFICATION,
            calibration=RuleConfidenceCalibrationStatus.PROVISIONAL,
            limitations=("Negative or broad performance inference depends on partial static signals.",),
        )
        for rule_id in (
            "performance.perf-003",
            "performance.perf-021",
            "performance.perf-032",
            "performance.perf-041",
            "performance.perf-052",
            "performance.perf-061",
            "performance.perf-071",
            "performance.perf-072",
        )
    }
)

_TESTING = {
    rule_id: _confidence(
        RuleConfidenceLevel.MODERATE,
        RuleConfidenceBasis.STATIC_PATTERN,
        limitations=("Repository-local test signals do not prove test execution quality.",),
    )
    for rule_id in (
        "testing.test-001",
        "testing.test-002",
        "testing.test-003",
        "testing.test-005",
    )
}

RULE_CONFIDENCE_CATALOG: dict[str, RuleConfidence] = {
    **_ARCHITECTURE,
    **_TECHNICAL_DEBT,
    **_DEPENDENCY,
    **_SECURITY,
    **_CLOUD,
    **_AI_READINESS,
    **_PERFORMANCE,
    **_TESTING,
}


def confidence_for_rule(rule_id: str) -> RuleConfidence:
    """Return inherent confidence for a production Shared Rule ID."""

    key = rule_id.strip().lower()
    try:
        return RULE_CONFIDENCE_CATALOG[key]
    except KeyError as exc:
        raise KeyError(f"No Rule Confidence catalog entry for {rule_id}") from exc
