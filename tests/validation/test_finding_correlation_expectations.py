"""Slice 5.12 — correlation expectation helpers."""

from __future__ import annotations

from validation.finding_correlations.expectations import (
    FindingCorrelationExpectation,
    FindingCorrelationPairExpectation,
    compare_correlation_expectations,
    extract_correlation_pair_keys,
    pair_key,
)


def test_extract_and_compare_required_forbidden() -> None:
    findings = [
        {"id": "finding:a", "rule_id": "security.credential-literal"},
        {"id": "finding:b", "rule_id": "security.placeholder-credential"},
        {"id": "finding:c", "rule_id": "security.debug-enabled"},
    ]
    correlations = [
        {
            "correlation_id": "correlation:aaaaaaaaaaaaaaaaaaaaaaaa",
            "finding_ids": ["finding:a", "finding:b"],
            "correlation_type": "configuration_cluster",
        }
    ]
    keys = extract_correlation_pair_keys(findings=findings, correlations=correlations)
    assert pair_key(
        "security.credential-literal", "security.placeholder-credential"
    ) in keys

    expectation = FindingCorrelationExpectation(
        required_correlations=(
            FindingCorrelationPairExpectation(
                rule_ids=(
                    "security.credential-literal",
                    "security.placeholder-credential",
                )
            ),
        ),
        forbidden_correlations=(
            FindingCorrelationPairExpectation(
                rule_ids=("security.credential-literal", "security.debug-enabled")
            ),
        ),
    )
    assert compare_correlation_expectations(
        expectation=expectation, actual_pair_keys=keys
    ) == []

    missing = compare_correlation_expectations(
        expectation=FindingCorrelationExpectation(
            required_correlations=(
                FindingCorrelationPairExpectation(
                    rule_ids=(
                        "architecture.invalid-dependency-direction",
                        "architecture.layer-boundary-violation",
                    )
                ),
            )
        ),
        actual_pair_keys=keys,
    )
    assert missing and "missing required" in missing[0]
