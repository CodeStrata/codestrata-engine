"""E12.3: canonical projection drops unsupported AI score claims."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.knowledge.artifact_evidence import (
    LocalArtifactEvidenceService,
    project_canonical_evidence,
)

_FIXTURES = Path(__file__).resolve().parents[2] / "ai" / "explanation" / "fixtures" / "e12.3"
_EXPECTED_REJECTED = [
    "coverage",
    "health",
    "health_score",
    "scores",
    "severity",
    "verdict",
]


def _load(name: str) -> dict[str, object]:
    loaded = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{name} must be an object")
    return loaded


def test_pinned_report_projection_matches_the_expected_canonical_body() -> None:
    report = _load("pinned-report.json")
    expected = _load("expected-canonical.json")
    projected = project_canonical_evidence(report)

    assert projected["assessment_status"] == expected["assessment_status"]
    assert projected["canonical_digest"] == expected["canonical_digest"]
    assert projected["findings"] == expected["findings"]
    assert projected["metrics"] == expected["metrics"]
    assert projected["coverage"] == expected["coverage"]
    assert projected["verdicts"] == expected["verdicts"]
    assert projected["rejected_ai_claims"] == _EXPECTED_REJECTED
    assert projected["metrics"][0]["coverage"] is None
    assert projected["metrics"][0]["value"] is None
    assert all(item["severity"] != "low" for item in projected["findings"])
    assert 100 not in [item["value"] for item in projected["metrics"]]


def test_ai_scores_do_not_fill_an_empty_metric_list(tmp_path: Path) -> None:
    only_claims = {
        "schema_version": "1.2",
        "assessment_status": "completed",
        "canonical_digest": "cd" * 32,
        "assessment": {
            "metrics": [
                {
                    "metric_id": "health_score",
                    "origin": "ai",
                    "category": "score",
                    "value": 100,
                    "coverage": 1.0,
                }
            ],
            "summary": {"scores": {"health_score": 99, "quality": 3}},
            "ai_explanation": {
                "health_score": 99,
                "scores": {"health": 100},
            },
            "findings": [{"finding_id": "f-sql", "severity": "high"}],
        },
    }
    (tmp_path / "report.json").write_text(json.dumps(only_claims), encoding="utf-8")
    service = LocalArtifactEvidenceService(allowed_root=tmp_path)
    items, total = service.list_metrics(tmp_path, limit=20, offset=0)
    view = service.canonical_equivalence_view(tmp_path)

    assert total == 1
    assert items[0]["metric_id"] == "score.quality"
    assert items[0]["value"] == 3
    assert all(item["metric_id"] != "health_score" for item in items)
    assert all(not str(item["metric_id"]).startswith("score.health") for item in items)
    assert view["metrics"] == []
    assert view["findings"] == [{"finding_id": "f-sql", "severity": "high"}]

    claims_only = {
        "schema_version": "1.2",
        "assessment": {
            "metrics": [],
            "summary": {"scores": {"health_score": 99}},
            "ai_explanation": {"health_score": 99},
        },
    }
    empty_root = tmp_path / "claims-only"
    empty_root.mkdir()
    (empty_root / "report.json").write_text(json.dumps(claims_only), encoding="utf-8")
    claimed, claimed_total = service.list_metrics(empty_root, limit=20, offset=0)
    assert claimed == []
    assert claimed_total == 0


def test_partial_and_non_list_collections_do_not_invent_scores() -> None:
    nested = {
        "schema_version": "1.2",
        "assessment_status": "completed",
        "canonical_digest": "ef" * 32,
        "assessment": {
            "findings": [
                {"origin": "ai", "finding_id": "f-ai", "severity": "low"},
                {"id": "f-kept", "severity": "high"},
                "not-a-finding",
            ],
            "metrics": "not-a-list",
            "coverage": "not-a-list",
            "verdicts": "not-a-list",
        },
    }
    projected = project_canonical_evidence(nested)
    assert projected["findings"] == [{"finding_id": "f-kept", "severity": "high"}]
    assert projected["metrics"] == []
    assert projected["coverage"] == []
    assert projected["verdicts"] == []

    no_findings = {
        "assessment_status": "completed",
        "canonical_digest": "22" * 32,
        "assessment": {"findings": "not-a-list"},
    }
    assert project_canonical_evidence(no_findings)["findings"] == []

    top_level = {
        "assessment_status": "partial",
        "canonical_digest": "11" * 32,
        "findings": [{"finding_id": "f-1", "severity": "low"}],
        "metrics": [
            "not-a-metric",
            {
                "metric_id": "health_score",
                "value": 100,
                "excluded_from_canonical": True,
            },
            {"name": "m.lines", "value": 4},
        ],
        "coverage": [
            "not-coverage",
            {"capability_id": "tests", "coverage": None, "reason": "missing_test_association"},
            {"capability_id": "bare", "reason": "unsupported"},
            {"origin": "ai", "capability_id": "ai.narrative", "coverage_ratio": 1.0},
        ],
        "verdicts": [
            {"family": "quality", "verdict": "unknown"},
            "not-a-verdict",
            {"origin": "ai", "family": "ai", "verdict": "improved"},
        ],
    }
    partial = project_canonical_evidence(top_level)
    assert partial["assessment_status"] == "partial"
    assert partial["metrics"] == [{"metric_id": "m.lines", "value": 4, "coverage": None}]
    assert partial["coverage"] == [
        {
            "capability_id": "tests",
            "coverage_ratio": None,
            "reason": "missing_test_association",
        },
        {"capability_id": "bare", "coverage_ratio": None, "reason": "unsupported"},
    ]
    assert partial["verdicts"] == [{"family": "quality", "verdict": "unknown"}]
    assert 100 not in [item["value"] for item in partial["metrics"]]
