"""Normalize PMD violations into CodeStrata severities, categories, and visibility."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.models.enums import FindingCategory, Severity
from codestrata.static_analysis.providers.pmd_mapping import (
    build_pmd_rule_id,
    map_pmd_category,
    map_pmd_priority,
    normalize_ruleset_token,
)
from codestrata.static_analysis.visibility import CustomerVisibility, ModernizationRelevance


@dataclass(frozen=True)
class PmdRuleNormalization:
    """Normalized classification for one PMD rule family."""

    severity: Severity
    category: FindingCategory
    visibility: CustomerVisibility
    modernization_relevance: ModernizationRelevance
    rationale: str


# Explicit mappings for high-frequency / high-value PMD rule families.
# Keys are PMD external rule names (CamelCase).
_EXPLICIT_RULE_POLICIES: dict[str, PmdRuleNormalization] = {
    # Correctness / reliability — elevate for modernization.
    "AvoidThrowingRawExceptionTypes": PmdRuleNormalization(
        Severity.HIGH,
        FindingCategory.RELIABILITY,
        CustomerVisibility.PRIMARY,
        ModernizationRelevance.HIGH,
        "Raw exception types obscure failure modes during modernization.",
    ),
    "CloseResource": PmdRuleNormalization(
        Severity.HIGH,
        FindingCategory.RELIABILITY,
        CustomerVisibility.PRIMARY,
        ModernizationRelevance.HIGH,
        "Resource leaks are correctness and operational risks.",
    ),
    "AvoidCatchingGenericException": PmdRuleNormalization(
        Severity.HIGH,
        FindingCategory.RELIABILITY,
        CustomerVisibility.PRIMARY,
        ModernizationRelevance.HIGH,
        "Broad catch blocks hide defects and complicate migration.",
    ),
    "MutableStaticState": PmdRuleNormalization(
        Severity.HIGH,
        FindingCategory.RELIABILITY,
        CustomerVisibility.PRIMARY,
        ModernizationRelevance.HIGH,
        "Mutable static state is hazardous for cloud concurrency.",
    ),
    "AvoidDuplicateLiterals": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Duplicate literals are common style noise with limited modernization signal.",
    ),
    "AvoidLiteralsInIfCondition": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Literal conditions are mostly convention-oriented.",
    ),
    "AvoidFieldNameMatchingTypeName": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.SUPPRESSED_FROM_HTML,
        ModernizationRelevance.NONE,
        "Naming convention only; preserve in JSON, omit from HTML cards.",
    ),
    "MissingSerialVersionUID": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Serialization boilerplate with limited modernization impact.",
    ),
    "ProperLogger": PmdRuleNormalization(
        Severity.MEDIUM,
        FindingCategory.OPERATIONAL_READINESS,
        CustomerVisibility.SUPPORTING,
        ModernizationRelevance.MEDIUM,
        "Logger usage affects operability after modernization.",
    ),
    "GuardLogStatement": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.PERFORMANCE,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Log guarding is micro-optimization noise for most assessments.",
    ),
    "SystemPrintln": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.OPERATIONAL_READINESS,
        CustomerVisibility.SUPPORTING,
        ModernizationRelevance.MEDIUM,
        "Console logging should be replaced before production modernization.",
    ),
    "DoubleBraceInitialization": PmdRuleNormalization(
        Severity.MEDIUM,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.SUPPORTING,
        ModernizationRelevance.MEDIUM,
        "Double-brace init creates anonymous classes and migration friction.",
    ),
    "AvoidReassigningParameters": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Parameter reassignment is a readability convention.",
    ),
    "ImplicitFunctionalInterface": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.SUPPRESSED_FROM_HTML,
        ModernizationRelevance.NONE,
        "Annotation convention only.",
    ),
    "AbstractClassWithoutAbstractMethod": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.ARCHITECTURE,
        CustomerVisibility.SUPPORTING,
        ModernizationRelevance.MEDIUM,
        "Abstract type design may indicate structural debt.",
    ),
    # Design / complexity — modernization-relevant.
    "CyclomaticComplexity": PmdRuleNormalization(
        Severity.MEDIUM,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.SUPPORTING,
        ModernizationRelevance.HIGH,
        "High complexity increases modernization and testing cost.",
    ),
    "CognitiveComplexity": PmdRuleNormalization(
        Severity.MEDIUM,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.SUPPORTING,
        ModernizationRelevance.HIGH,
        "Cognitive complexity signals hard-to-migrate logic.",
    ),
    "TooManyMethods": PmdRuleNormalization(
        Severity.MEDIUM,
        FindingCategory.ARCHITECTURE,
        CustomerVisibility.SUPPORTING,
        ModernizationRelevance.HIGH,
        "Oversized types hinder modularization.",
    ),
    "DataClass": PmdRuleNormalization(
        Severity.LOW,
        FindingCategory.ARCHITECTURE,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.MEDIUM,
        "Anemic data classes may inform domain redesign, but are often expected.",
    ),
    "ExcessiveImports": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.SUPPRESSED_FROM_HTML,
        ModernizationRelevance.NONE,
        "Import volume is stylistic noise.",
    ),
    "CollapsibleIfStatements": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.SUPPRESSED_FROM_HTML,
        ModernizationRelevance.NONE,
        "Style-only nesting suggestion.",
    ),
    "PublicMemberInNonPublicType": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.MAINTAINABILITY,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Access-modifier convention; frequent and low modernization value.",
    ),
    # Test conventions — high volume noise in Petclinic-like repos.
    "UnitTestShouldIncludeAssert": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.TESTING,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Test-assert conventions are high-volume and often Spring-test noise.",
    ),
    "UnitTestContainsTooManyAsserts": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.TESTING,
        CustomerVisibility.INFORMATIONAL,
        ModernizationRelevance.LOW,
        "Assert-count conventions rarely block modernization.",
    ),
    "JUnitJupiterTestShouldBePackagePrivate": PmdRuleNormalization(
        Severity.INFO,
        FindingCategory.TESTING,
        CustomerVisibility.SUPPRESSED_FROM_HTML,
        ModernizationRelevance.NONE,
        "JUnit visibility convention only.",
    ),
}


_SECURITY_RULE_TOKENS = frozenset(
    {
        "hardcodedcryptokey",
        "hardcodedsecret",
        "insecurecryptoclass",
        "weakcryptography",
        "cryptographykey",
    }
)


def normalize_pmd_rule(
    *,
    external_rule_id: str | None,
    ruleset: str | None,
    provider_priority: int | None,
) -> PmdRuleNormalization:
    """Normalize one PMD rule using explicit maps, then category/priority fallback."""

    rule_name = (external_rule_id or "").strip()
    if rule_name in _EXPLICIT_RULE_POLICIES:
        return _EXPLICIT_RULE_POLICIES[rule_name]

    category = map_pmd_category(ruleset)
    severity = map_pmd_priority(provider_priority)
    ruleset_token = normalize_ruleset_token(ruleset).lower()
    rule_token = "".join(character.lower() for character in rule_name if character.isalnum())

    if ruleset_token == "security" or any(token in rule_token for token in _SECURITY_RULE_TOKENS):
        escalated = _escalate(severity, floor=Severity.HIGH)
        return PmdRuleNormalization(
            severity=escalated,
            category=FindingCategory.SECURITY,
            visibility=_visibility_for_severity(escalated, default=CustomerVisibility.PRIMARY),
            modernization_relevance=ModernizationRelevance.HIGH,
            rationale="Security ruleset/family escalated for customer visibility.",
        )

    if ruleset_token == "errorprone":
        escalated = _escalate(severity, floor=Severity.MEDIUM)
        return PmdRuleNormalization(
            severity=escalated,
            category=FindingCategory.RELIABILITY,
            visibility=_visibility_for_severity(escalated, default=CustomerVisibility.PRIMARY),
            modernization_relevance=ModernizationRelevance.HIGH,
            rationale="Error-prone rules indicate likely defects and modernization risk.",
        )

    if ruleset_token == "codestyle" or ruleset_token == "documentation":
        return PmdRuleNormalization(
            severity=Severity.INFO,
            category=FindingCategory.MAINTAINABILITY,
            visibility=CustomerVisibility.SUPPRESSED_FROM_HTML,
            modernization_relevance=ModernizationRelevance.NONE,
            rationale="Style/documentation conventions are omitted from HTML cards.",
        )

    if ruleset_token == "design":
        return PmdRuleNormalization(
            severity=severity if severity != Severity.CRITICAL else Severity.HIGH,
            category=FindingCategory.ARCHITECTURE
            if severity in {Severity.HIGH, Severity.CRITICAL}
            else FindingCategory.MAINTAINABILITY,
            visibility=_visibility_for_severity(severity, default=CustomerVisibility.SUPPORTING),
            modernization_relevance=ModernizationRelevance.MEDIUM,
            rationale="Design findings support architecture modernization planning.",
        )

    if ruleset_token == "bestpractices":
        # Avoid elevating generic best-practice noise.
        demoted = severity if severity in {Severity.INFO, Severity.LOW} else Severity.LOW
        return PmdRuleNormalization(
            severity=demoted,
            category=category,
            visibility=CustomerVisibility.INFORMATIONAL,
            modernization_relevance=ModernizationRelevance.LOW,
            rationale="Generic best-practice findings are informational unless explicitly mapped.",
        )

    return PmdRuleNormalization(
        severity=severity,
        category=category,
        visibility=_visibility_for_severity(severity, default=CustomerVisibility.SUPPORTING),
        modernization_relevance=ModernizationRelevance.MEDIUM,
        rationale="Fallback mapping from PMD ruleset and priority.",
    )


def ensure_critical_high_not_suppressed(
    normalization: PmdRuleNormalization,
) -> PmdRuleNormalization:
    """Critical and high findings must remain customer-visible."""

    if normalization.severity not in {Severity.CRITICAL, Severity.HIGH}:
        return normalization
    if normalization.visibility != CustomerVisibility.SUPPRESSED_FROM_HTML:
        return normalization
    return PmdRuleNormalization(
        severity=normalization.severity,
        category=normalization.category,
        visibility=CustomerVisibility.PRIMARY,
        modernization_relevance=(
            ModernizationRelevance.HIGH
            if normalization.modernization_relevance == ModernizationRelevance.NONE
            else normalization.modernization_relevance
        ),
        rationale=f"{normalization.rationale} Critical/high findings cannot be suppressed.",
    )


def stable_pmd_rule_id(ruleset: str | None, rule: str | None) -> str:
    """Public helper preserving the stable PMD rule identifier format."""

    return build_pmd_rule_id(ruleset, rule)


def _escalate(severity: Severity, *, floor: Severity) -> Severity:
    order = [
        Severity.INFO,
        Severity.LOW,
        Severity.MEDIUM,
        Severity.HIGH,
        Severity.CRITICAL,
    ]
    return order[max(order.index(severity), order.index(floor))]


def _visibility_for_severity(
    severity: Severity,
    *,
    default: CustomerVisibility,
) -> CustomerVisibility:
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        return CustomerVisibility.PRIMARY
    if severity == Severity.MEDIUM:
        return (
            default
            if default != CustomerVisibility.SUPPRESSED_FROM_HTML
            else (CustomerVisibility.SUPPORTING)
        )
    if severity == Severity.LOW:
        return CustomerVisibility.INFORMATIONAL
    return CustomerVisibility.INFORMATIONAL
