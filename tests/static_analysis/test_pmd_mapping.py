"""Tests for PMD mapping helpers."""

from codestrata.models.enums import FindingCategory, Severity
from codestrata.static_analysis.providers.pmd_mapping import (
    build_pmd_rule_id,
    humanize_rule_name,
    map_pmd_category,
    map_pmd_priority,
)


def test_priority_to_severity_mapping() -> None:
    assert map_pmd_priority(1) == Severity.CRITICAL
    assert map_pmd_priority(2) == Severity.HIGH
    assert map_pmd_priority(3) == Severity.MEDIUM
    assert map_pmd_priority(4) == Severity.LOW
    assert map_pmd_priority(5) == Severity.INFO
    assert map_pmd_priority(None) == Severity.INFO


def test_stable_rule_id_generation() -> None:
    assert (
        build_pmd_rule_id("Best Practices", "UnusedPrivateField")
        == "PMD.JAVA.BESTPRACTICES.UNUSEDPRIVATEFIELD"
    )
    assert (
        build_pmd_rule_id("category/java/errorprone.xml", "EmptyCatchBlock")
        == "PMD.JAVA.ERRORPRONE.EMPTYCATCHBLOCK"
    )


def test_human_readable_rule_title() -> None:
    assert humanize_rule_name("UnusedPrivateField") == "Unused private field"


def test_unknown_ruleset_maps_to_maintainability() -> None:
    assert map_pmd_category("unknown-ruleset") == FindingCategory.MAINTAINABILITY
    assert map_pmd_category("Error Prone") == FindingCategory.RELIABILITY
