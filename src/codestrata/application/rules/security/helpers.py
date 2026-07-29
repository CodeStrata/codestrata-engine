"""Shared helpers for Security hygiene SharedRules (Phase 4.5.3)."""

from __future__ import annotations

from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationKeyFamily,
    ContentClassification,
    InspectionStatus,
    PlaceholderStatus,
    RepositorySensitiveParseStatus,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
    ConfigurationFactEvidence,
    SensitiveArtifactEvidence,
)
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import RuleMatch
from codestrata.domain.security.ids import PACK_ID, PACK_VERSION, RULE_VERSION
from codestrata.domain.security.taxonomy import SecurityCategory

_CREDENTIAL_FAMILIES = frozenset(
    {
        ConfigurationKeyFamily.CREDENTIAL,
        ConfigurationKeyFamily.SECRET,
    }
)

_RECOMMENDATIONS: dict[str, str] = {
    "security.private-key-material": (
        "Remove private-key material from the repository. Prefer a secrets "
        "manager or environment injection, and rotate any exposed keys."
    ),
    "security.credential-literal": (
        "Replace committed credential literals with environment references or "
        "a secrets manager. Rotate any exposed credentials."
    ),
    "security.placeholder-credential": (
        "Replace placeholder credential values with environment references "
        "before deployment. Placeholders are hygiene signals, not proven secrets."
    ),
    "security.tls-verification-disabled": (
        "Enable TLS certificate verification for production connections."
    ),
    "security.hostname-verification-disabled": (
        "Enable TLS hostname verification for production connections."
    ),
    "security.authentication-disabled": (
        "Enable the configured authentication control unless this is an "
        "intentional non-production local profile."
    ),
    "security.permissive-cors-origin": (
        "Replace wildcard CORS origins with an explicit allow-list."
    ),
    "security.debug-enabled": (
        "Disable debug mode for production-facing configuration."
    ),
}


def repository_sensitive_evidence(
    context: RuleExecutionContext,
) -> AggregatedRepositorySensitiveEvidence | None:
    raw = context.repository_sensitive_evidence
    if isinstance(raw, AggregatedRepositorySensitiveEvidence):
        return raw
    return None


def evidence_is_usable(
    evidence: AggregatedRepositorySensitiveEvidence | None,
) -> bool:
    if evidence is None:
        return False
    if evidence.status in {
        RepositorySensitiveParseStatus.NOT_APPLICABLE,
        RepositorySensitiveParseStatus.SKIPPED,
        RepositorySensitiveParseStatus.FAILED,
    }:
        return False
    return bool(evidence.artifacts or evidence.configuration_facts)


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    remediation: str,
    severity: RuleSeverity = RuleSeverity.HIGH,
) -> RuleMetadata:
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse(RULE_VERSION),
        title=title,
        description=description,
        category=RuleCategory.SECURITY,
        default_severity=severity,
        supported_languages=("java", "python", "javascript", "typescript", "php", "csharp"),
        tags=("security", PACK_ID, "hygiene", "dimension:security"),
        remediation_summary=remediation,
        documentation_reference=(
            "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        enabled_by_default=True,
        experimental=False,
        requires_enterprise_context=False,
        incremental_behaviors=(
            RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
            RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
        ),
    )


def recommendation_for(rule_id: str) -> str:
    return _RECOMMENDATIONS.get(
        rule_id,
        "Review the repository-sensitive evidence fact and remediate the "
        "hygiene condition.",
    )


def match(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: RuleSeverity,
    confidence: RuleConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
    remediation: str | None = None,
) -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse(RULE_VERSION),
        severity=severity,
        confidence=confidence,
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=remediation or recommendation_for(rule_id),
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
    )


def evidence_artifact(
    *,
    item: SensitiveArtifactEvidence,
    message: str,
    security_category: SecurityCategory,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.path,
        attributes={
            "evidence_id": item.evidence_id,
            "path": item.path,
            "kind": item.kind.value,
            "inspection_status": item.inspection_status.value,
            "content_classifications": ",".join(
                classification.value for classification in item.content_classifications
            ),
            "classification": item.classification.value,
            "security_category": security_category.value,
        },
        provenance="aggregated_repository_sensitive_evidence",
    )


def evidence_configuration(
    *,
    item: ConfigurationFactEvidence,
    message: str,
    security_category: SecurityCategory,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.CONFIGURATION_KEY,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.path,
        line_start=item.line_start,
        attributes={
            "evidence_id": item.evidence_id,
            "path": item.path,
            "normalized_key": item.normalized_key,
            "key_family": item.key_family.value,
            "value_kind": item.value_kind.value,
            "placeholder_status": item.placeholder_status.value,
            "redacted_preview": item.redacted_preview,
            "value_fingerprint": item.value_fingerprint or "",
            "classification": item.classification.value,
            "section": item.section or "",
            "literal_boolean": (
                "" if item.literal_boolean is None else str(item.literal_boolean).lower()
            ),
            "is_wildcard_origin": str(item.is_wildcard_origin).lower(),
            "security_category": security_category.value,
        },
        provenance="aggregated_repository_sensitive_evidence",
    )


def has_private_key_material(item: SensitiveArtifactEvidence) -> bool:
    if item.inspection_status is not InspectionStatus.INSPECTED:
        return False
    return (
        ContentClassification.PRIVATE_KEY_MATERIAL in item.content_classifications
    )


def is_credential_sensitive_fact(item: ConfigurationFactEvidence) -> bool:
    return item.key_family in _CREDENTIAL_FAMILIES


def is_literal_credential(item: ConfigurationFactEvidence) -> bool:
    if not is_credential_sensitive_fact(item):
        return False
    if item.is_empty or item.value_kind is ValueKind.EMPTY:
        return False
    if item.value_kind is ValueKind.ENVIRONMENT_REFERENCE:
        return False
    if item.placeholder_status in {
        PlaceholderStatus.EMPTY,
        PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
        PlaceholderStatus.PLACEHOLDER_LITERAL,
    }:
        return False
    return item.value_kind is ValueKind.LITERAL


def is_placeholder_credential(item: ConfigurationFactEvidence) -> bool:
    if not is_credential_sensitive_fact(item):
        return False
    if item.value_kind is ValueKind.ENVIRONMENT_REFERENCE:
        return False
    if item.placeholder_status is PlaceholderStatus.ENVIRONMENT_INTERPOLATION:
        return False
    return item.placeholder_status is PlaceholderStatus.PLACEHOLDER_LITERAL


def tls_verification_disabled(item: ConfigurationFactEvidence) -> bool:
    if item.key_family is not ConfigurationKeyFamily.TLS_VERIFICATION:
        return False
    if item.literal_boolean is None:
        return False
    key = item.normalized_key
    if any(token in key for token in ("trust_all", "trustall", "insecure")):
        return item.literal_boolean is True
    return item.literal_boolean is False


def hostname_verification_disabled(item: ConfigurationFactEvidence) -> bool:
    if item.key_family is not ConfigurationKeyFamily.HOSTNAME_VERIFICATION:
        return False
    return item.literal_boolean is False


def authentication_disabled(item: ConfigurationFactEvidence) -> bool:
    if item.key_family is not ConfigurationKeyFamily.AUTHENTICATION:
        return False
    return item.literal_boolean is False


def permissive_cors_origin(item: ConfigurationFactEvidence) -> bool:
    if item.key_family is not ConfigurationKeyFamily.CORS_ORIGIN:
        return False
    return item.is_wildcard_origin is True


def debug_enabled(item: ConfigurationFactEvidence) -> bool:
    """True when a typed debug control is explicitly enabled.

    Emits for all source roles; assessment inventory may separate roles later.
    """

    if item.key_family is not ConfigurationKeyFamily.DEBUG:
        return False
    return item.literal_boolean is True


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    category = category_for_rule(rule_id)
    return {
        "taxonomy_id": category.value,
        "security_category": category.value,
        "assessment_dimensions": "security",
        "business_impact": "unknown",
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "recommendation_effort_band": "unknown",
        "recommendation_validation": "static_evidence_only",
        "recommendation_rationale": recommendation_for(rule_id),
        "recommendation_expected_outcome": (
            "Improve repository-local security hygiene using typed evidence facts"
        ),
    }


def category_for_rule(rule_id: str) -> SecurityCategory:
    mapping = {
        "security.private-key-material": SecurityCategory.PRIVATE_KEY,
        "security.credential-literal": SecurityCategory.CREDENTIAL,
        "security.placeholder-credential": SecurityCategory.CREDENTIAL,
        "security.tls-verification-disabled": SecurityCategory.TRANSPORT_SECURITY,
        "security.hostname-verification-disabled": SecurityCategory.TRANSPORT_SECURITY,
        "security.authentication-disabled": SecurityCategory.AUTHENTICATION,
        "security.permissive-cors-origin": SecurityCategory.CONFIGURATION,
        "security.debug-enabled": SecurityCategory.CONFIGURATION,
    }
    return mapping.get(rule_id, SecurityCategory.UNKNOWN)
