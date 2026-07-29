"""Tests for PMD profiles, normalization, grouping, and visibility."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.models.enums import FindingCategory, FindingSource, Severity
from codestrata.models.evidence import Evidence
from codestrata.models.finding import Finding
from codestrata.static_analysis.grouping import (
    group_observations,
    observations_from_pmd_findings,
    visibility_counts,
)
from codestrata.static_analysis.providers.pmd_normalization import (
    ensure_critical_high_not_suppressed,
    normalize_pmd_rule,
)
from codestrata.static_analysis.providers.pmd_profiles import (
    DEFAULT_PMD_PROFILE,
    PmdProfile,
    parse_pmd_profile,
    resolve_pmd_profile_definition,
)
from codestrata.static_analysis.visibility import CustomerVisibility, ModernizationRelevance


def test_default_profile_is_standard() -> None:
    assert DEFAULT_PMD_PROFILE == PmdProfile.STANDARD
    assert parse_pmd_profile(None) == PmdProfile.STANDARD


def test_invalid_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid PMD profile"):
        parse_pmd_profile("aggressive")


def test_focused_profile_uses_narrower_rulesets() -> None:
    focused = resolve_pmd_profile_definition(PmdProfile.FOCUSED)
    standard = resolve_pmd_profile_definition(PmdProfile.STANDARD)
    comprehensive = resolve_pmd_profile_definition(PmdProfile.COMPREHENSIVE)

    assert "category/java/security.xml" in focused.rulesets
    assert "category/java/bestpractices.xml" not in focused.rulesets
    assert focused.minimum_priority == 3
    assert standard.minimum_priority == 3
    assert "category/java/bestpractices.xml" in standard.rulesets
    assert comprehensive.minimum_priority == 5


def test_comprehensive_honors_configured_rulesets() -> None:
    definition = resolve_pmd_profile_definition(
        PmdProfile.COMPREHENSIVE,
        configured_rulesets=["category/java/errorprone.xml"],
    )
    assert definition.rulesets == ("category/java/errorprone.xml",)


def test_petclinic_rule_distribution_fixture_present() -> None:
    path = Path(__file__).parent / "fixtures" / "petclinic_pmd_rule_distribution.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["pmd_count"] >= 150
    assert payload["by_rule"]["PMD.JAVA.BESTPRACTICES.UNITTESTSHOULDINCLUDEASSERT"] >= 30
    assert payload["by_severity"]["medium"] >= 100


def test_style_rules_do_not_become_high_severity() -> None:
    normalization = normalize_pmd_rule(
        external_rule_id="JUnitJupiterTestShouldBePackagePrivate",
        ruleset="Best Practices",
        provider_priority=3,
    )
    assert normalization.severity == Severity.INFO
    assert normalization.visibility == CustomerVisibility.SUPPRESSED_FROM_HTML


def test_security_and_correctness_rules_escalate() -> None:
    raw_exception = normalize_pmd_rule(
        external_rule_id="AvoidThrowingRawExceptionTypes",
        ruleset="Design",
        provider_priority=3,
    )
    assert raw_exception.severity == Severity.HIGH
    assert raw_exception.visibility == CustomerVisibility.PRIMARY

    close_resource = normalize_pmd_rule(
        external_rule_id="CloseResource",
        ruleset="Error Prone",
        provider_priority=3,
    )
    assert close_resource.severity == Severity.HIGH
    assert close_resource.category == FindingCategory.RELIABILITY


def test_critical_high_cannot_be_suppressed() -> None:
    forced = ensure_critical_high_not_suppressed(
        normalize_pmd_rule(
            external_rule_id="AvoidFieldNameMatchingTypeName",
            ruleset="Error Prone",
            provider_priority=1,
        )
    )
    # priority 1 maps critical via fallback before explicit style map...
    # AvoidFieldNameMatchingTypeName is explicit INFO/SUPPRESSED; ensure guard
    # only upgrades when severity is critical/high.
    assert forced.severity == Severity.INFO

    escalated = ensure_critical_high_not_suppressed(
        type(forced)(
            severity=Severity.HIGH,
            category=FindingCategory.MAINTAINABILITY,
            visibility=CustomerVisibility.SUPPRESSED_FROM_HTML,
            modernization_relevance=ModernizationRelevance.NONE,
            rationale="test",
        )
    )
    assert escalated.visibility == CustomerVisibility.PRIMARY


def _pmd_finding(
    *,
    rule: str,
    ruleset: str,
    priority: int,
    path: str,
    line: int,
    message: str,
) -> Finding:
    from codestrata.static_analysis.providers.pmd_mapping import (
        build_pmd_rule_id,
        humanize_rule_name,
    )

    return Finding(
        rule_id=build_pmd_rule_id(ruleset, rule),
        title=humanize_rule_name(rule),
        description=message,
        category=FindingCategory.MAINTAINABILITY,
        severity=Severity.MEDIUM,
        source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
        evidence=[Evidence(file_path=path, line_number=line, column_number=1, description=message)],
        metadata={
            "provider_id": "pmd",
            "provider_name": "PMD",
            "external_rule_id": rule,
            "ruleset": ruleset,
            "original_priority": priority,
        },
    )


def test_repeated_same_rule_findings_group() -> None:
    findings = [
        _pmd_finding(
            rule="UnitTestShouldIncludeAssert",
            ruleset="Best Practices",
            priority=3,
            path=f"src/test/java/A{index}.java",
            line=10 + index,
            message="Add an assert",
        )
        for index in range(5)
    ]
    observations = observations_from_pmd_findings(findings)
    groups, customer = group_observations(observations)
    assert len(observations) == 5
    assert len(groups) == 1
    assert groups[0].occurrence_count == 5
    assert groups[0].affected_file_count == 5
    assert len(customer) == 1
    assert customer[0].metadata["occurrence_count"] == 5
    assert all(item.group_id == groups[0].group_id for item in observations)


def test_unrelated_rules_do_not_group() -> None:
    findings = [
        _pmd_finding(
            rule="CloseResource",
            ruleset="Error Prone",
            priority=2,
            path="src/main/java/A.java",
            line=1,
            message="close it",
        ),
        _pmd_finding(
            rule="CyclomaticComplexity",
            ruleset="Design",
            priority=3,
            path="src/main/java/B.java",
            line=2,
            message="too complex",
        ),
    ]
    groups, customer = group_observations(observations_from_pmd_findings(findings))
    assert len(groups) == 2
    assert len(customer) == 2


def test_visibility_counts_and_suppression() -> None:
    findings = [
        _pmd_finding(
            rule="JUnitJupiterTestShouldBePackagePrivate",
            ruleset="Best Practices",
            priority=3,
            path="src/test/java/A.java",
            line=1,
            message="package private",
        ),
        _pmd_finding(
            rule="AvoidThrowingRawExceptionTypes",
            ruleset="Design",
            priority=3,
            path="src/main/java/B.java",
            line=2,
            message="raw exception",
        ),
    ]
    observations = observations_from_pmd_findings(findings)
    groups, customer = group_observations(observations)
    counts = visibility_counts(observations, groups)
    assert counts["raw_observation_count"] == 2
    assert counts["suppressed_from_html_count"] >= 1
    assert counts["primary_count"] >= 1
    assert all(
        item.metadata.get("customer_visibility") != "suppressed_from_html" for item in customer
    )
    assert not any("/Users/" in item.file_path for item in observations)
