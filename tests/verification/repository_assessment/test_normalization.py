"""SV.4 normalization tests."""

from __future__ import annotations

from verification.repository_assessment.normalization import (
    compare_normalized,
    extract_id_sets,
    normalize_report,
)


def test_strips_volatile_fields() -> None:
    doc = {
        "schema_version": "1.2",
        "assessment": {
            "schema_version": "1.2",
            "generated_at": "2026-01-01T00:00:00Z",
            "findings": [{"id": "F-1", "timestamp": "x"}],
            "evidence": [{"id": "E-1"}],
            "deterministic_recommendations": [{"id": "R-1"}],
            "priority_actions": [{"id": "PA-1"}],
            "activation": {"packs": [{"pack_id": "security", "enabled": True}]},
        },
    }
    normalized = normalize_report(doc)
    assert "generated_at" not in normalized["assessment"]
    assert "timestamp" not in normalized["assessment"]["findings"][0]
    ids = extract_id_sets(doc)
    assert ids["finding_ids"] == ["F-1"]


def test_compare_detects_id_drift() -> None:
    left = {
        "assessment": {
            "findings": [{"id": "F-1"}],
            "evidence": [],
            "deterministic_recommendations": [],
            "priority_actions": [],
            "activation": {"packs": []},
        }
    }
    right = {
        "assessment": {
            "findings": [{"id": "F-2"}],
            "evidence": [],
            "deterministic_recommendations": [],
            "priority_actions": [],
            "activation": {"packs": []},
        }
    }
    ok, diffs = compare_normalized(left, right)
    assert not ok
    assert any("finding_ids" in d for d in diffs)
