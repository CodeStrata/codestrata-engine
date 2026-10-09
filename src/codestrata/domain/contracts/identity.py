"""Existing identifier, confidence and severity mapping for E01.1."""

from __future__ import annotations

from codestrata.domain.contracts.enums import ConfidenceContractLevel
from codestrata.domain.contracts.models import (
    ConfidenceMapping,
    RuleIdGrammar,
    SeverityPolicy,
)
from codestrata.domain.dependency.ids import HYGIENE_RULE_IDS as DEPENDENCY_RULES
from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)
from codestrata.domain.security.ids import HYGIENE_RULE_IDS as SECURITY_RULES
from codestrata.domain.technical_debt.ids import COMPLEXITY_RULE_IDS
from codestrata.domain.testing.ids import HYGIENE_RULE_IDS as TESTING_RULES

LAUNCH_RULE_IDS: tuple[str, ...] = tuple(
    sorted(
        {
            RULE_DEPENDENCY_CYCLE,
            RULE_INVALID_DEPENDENCY_DIRECTION,
            RULE_LAYER_BOUNDARY_VIOLATION,
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            RULE_COMPONENT_CONCENTRATION,
            RULE_FRAMEWORK_LEAKAGE,
            *DEPENDENCY_RULES,
            *SECURITY_RULES,
            *COMPLEXITY_RULE_IDS,
            *TESTING_RULES,
        }
    )
)

# Cloud, performance and AI-readiness packs are not launch outcome drivers.
# Their IDs remain valid under the existing grammar and must not be rewritten.
DEFERRED_VALID_RULE_ID_FAMILIES: tuple[str, ...] = (
    "ai_readiness.",
    "cloud.",
    "performance.",
    "architecture.enterprise-standard-mismatch",
)

RULE_ID_GRAMMAR = RuleIdGrammar(
    shared_pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_-]*)+$",
    legacy_pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$",
    incompatible_restriction_invented=False,
    notes=(
        "Keep namespace.kebab-name and legacy codestrata-rule-* identities. "
        "Do not invent a new ID restriction that would reject current valid IDs. "
        "testing.test-00N and security.* kebab names stay as published."
    ),
)

CONFIDENCE_MAP: tuple[ConfidenceMapping, ...] = (
    ConfidenceMapping(
        existing_token="high",
        existing_enum="RuleConfidenceLevel.HIGH | MatchEvidenceConfidence.HIGH",
        contract_level=ConfidenceContractLevel.HIGH,
        notes="Exact syntax/manifest/lock/Git evidence and fully resolved witness.",
    ),
    ConfidenceMapping(
        existing_token="certain",
        existing_enum="MatchEvidenceConfidence.CERTAIN",
        contract_level=ConfidenceContractLevel.HIGH,
        notes="CERTAIN is high with an exact witness; not a calibrated probability.",
    ),
    ConfidenceMapping(
        existing_token="moderate",
        existing_enum="RuleConfidenceLevel.MODERATE",
        contract_level=ConfidenceContractLevel.MEDIUM,
        notes="Documented static convention or association.",
    ),
    ConfidenceMapping(
        existing_token="medium",
        existing_enum="MatchEvidenceConfidence.MEDIUM",
        contract_level=ConfidenceContractLevel.MEDIUM,
        notes="Evidence-certainty medium maps to contract medium.",
    ),
    ConfidenceMapping(
        existing_token="limited",
        existing_enum="RuleConfidenceLevel.LIMITED",
        contract_level=ConfidenceContractLevel.LOW,
        notes="Labeled non-authoritative indicator only.",
    ),
    ConfidenceMapping(
        existing_token="low",
        existing_enum="MatchEvidenceConfidence.LOW",
        contract_level=ConfidenceContractLevel.LOW,
        notes="Evidence-certainty low maps to contract low.",
    ),
    ConfidenceMapping(
        existing_token="unavailable",
        existing_enum="RuleConfidenceLevel.UNAVAILABLE",
        contract_level=ConfidenceContractLevel.UNSUPPORTED,
        notes="No fabricated confidence for unsupported evidence.",
    ),
)

SEVERITY_POLICY = SeverityPolicy(
    default_and_effective_preserved=True,
    hidden_rewrite_after_override_forbidden=True,
    context_derived_default_must_be_versioned=True,
    existing_calibrator="codestrata.application.findings.severity_calibration",
    launch_rule=(
        "Context caps may contribute only to versioned default severity on the "
        "rule/config contract before an approved override. After an approved "
        "effective-severity override, later context classification must not "
        "rewrite that effective value. E01.2 binds this into the descriptor; "
        "E03/E04 must not retain a hidden post-processing override."
    ),
)
