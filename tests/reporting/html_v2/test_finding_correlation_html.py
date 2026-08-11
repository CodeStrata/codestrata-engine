"""Slice 5.12 — HTML related-finding labels are customer-safe."""

from __future__ import annotations

from types import SimpleNamespace

from codestrata.reporting.html_v2.builder import _correlation_relationship_labels


def test_correlation_labels_are_customer_safe() -> None:
    report_input = SimpleNamespace(
        finding_correlations=(
            {
                "correlation_id": "correlation:aaaaaaaaaaaaaaaaaaaaaaaa",
                "correlation_type": "configuration_cluster",
                "finding_ids": ["finding:a", "finding:b"],
                "primary_finding_id": "finding:a",
                "confidence": {"level": "high"},
                "basis": ["same_configuration_key"],
            },
        ),
        assessment_rule_evaluation=None,
    )
    labels = _correlation_relationship_labels(report_input)  # type: ignore[arg-type]
    assert labels["finding:a"]["finding:b"] == "Same configuration subject"
    assert "FindingCorrelationPolicy" not in str(labels)
    assert "explicit_rule_relationship" not in str(labels)
