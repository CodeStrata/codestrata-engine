"""Slice 5.13 — Finding severity expectation helpers."""

from __future__ import annotations

from validation.finding_severity.expectations import (
    FindingSeverityExpectation,
    ForbiddenSeverityPrefix,
    compare_finding_severity_expectations,
)


def test_forbidden_high_cloud_severity() -> None:
    expectation = FindingSeverityExpectation(
        forbidden_severity_prefixes=(
            ForbiddenSeverityPrefix(
                prefix="cloud.",
                severities=("high", "critical"),
            ),
        )
    )
    assert (
        compare_finding_severity_expectations(
            expectation=expectation,
            findings=[
                {"rule_id": "cloud.cloud-010", "severity": "informational"},
                {"rule_id": "cloud.cloud-061", "severity": "low"},
            ],
        )
        == []
    )
    mismatches = compare_finding_severity_expectations(
        expectation=expectation,
        findings=[{"rule_id": "cloud.cloud-061", "severity": "high"}],
    )
    assert mismatches and "forbidden severity" in mismatches[0]
