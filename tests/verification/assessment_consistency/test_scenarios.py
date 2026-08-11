"""Scenario mutation detection tests (fixtures only)."""

from __future__ import annotations

from verification.assessment_consistency.findings import check_correlations, check_findings
from verification.assessment_consistency.limitations import check_limitations
from verification.assessment_consistency.models import RepositoryBundle
from verification.assessment_consistency.priority import check_priority
from verification.assessment_consistency.recommendations import check_recommendations
from verification.assessment_consistency.coverage import check_coverage
from verification.assessment_consistency.schemas import check_schemas
from verification.assessment_consistency.scenarios import (
    minimal_record,
    mutate_correlation_self_ref,
    mutate_duplicate_finding_id,
    mutate_dangling_recommendation_support,
    mutate_priority_band_mismatch,
    mutate_schema_version,
    mutate_wrong_limitation_repo,
    mutate_zero_denominator_ratio,
)


def _fixture_bundle() -> RepositoryBundle:
    finding = {
        "id": "f1",
        "rule_id": "R1",
        "severity": "medium",
        "title": "t",
        "category": "security",
        "finding_confidence": {"level": "high"},
        "correlated_finding_ids": [],
    }
    rec = {
        "id": "r1",
        "recommendation_type": "finding_backed",
        "supporting_finding_ids": ["f1"],
        "primary_finding_id": "f1",
        "priority": "medium",
        "priority_score": 55,
        "priority_assessment": {
            "priority": "medium",
            "score": 55,
            "policy_id": "priority.test",
            "calibration_status": "provisional",
        },
        "recommendation_confidence": {"level": "moderate"},
        "title": "rec",
    }
    report = {
        "schema_version": "1.2",
        "report_version": "1.2",
        "assessment": {
            "findings": [finding, dict(finding, id="f2", rule_id="R2")],
            "deterministic_recommendations": [rec],
            "finding_correlations": [],
            "priority_actions": [],
            "assessment_coverage": {
                "security_intelligence": {
                    "status": "complete",
                    "areas": [],
                }
            },
            "assessment_head_confidence": {
                "security_intelligence": {"level": "moderate"}
            },
            "activation": {"mode": "default", "packs": []},
        },
    }
    return RepositoryBundle(
        repository_id="flask",
        record=minimal_record(repository_id="flask"),
        report=report,
        findings_doc={"findings": report["assessment"]["findings"], "finding_count": 2},
        recommendations_doc={"recommendations": [rec]},
        artifact_dir_name="deadbeefdead",
        html_present=True,
        html_has_csp=True,
    )


def test_schema_mismatch_detected() -> None:
    b = mutate_schema_version(_fixture_bundle(), "1.1")
    _checks, defects = check_schemas([b])
    assert any(d.classification == "schema_contract" for d in defects)


def test_duplicate_finding_id_detected() -> None:
    b = mutate_duplicate_finding_id(_fixture_bundle())
    _c, defects = check_findings([b])
    assert any("duplicates=" in d.actual for d in defects)


def test_dangling_recommendation_support_detected() -> None:
    b = mutate_dangling_recommendation_support(_fixture_bundle())
    _c, defects = check_recommendations([b])
    assert any("dangling=" in d.actual for d in defects)


def test_priority_band_mismatch_detected() -> None:
    b = mutate_priority_band_mismatch(_fixture_bundle())
    _c, defects, _o = check_priority([b])
    assert any(d.classification == "priority_policy" for d in defects)


def test_correlation_self_ref_detected() -> None:
    b = mutate_correlation_self_ref(_fixture_bundle())
    _c, defects = check_correlations([b])
    assert any("itself" in d.actual for d in defects)


def test_wrong_limitation_placement_detected() -> None:
    b = mutate_wrong_limitation_repo(_fixture_bundle())
    # attach to unrelated repo id
    b.repository_id = "express"
    b.record["repository_id"] = "express"
    _c, defects = check_limitations([b])
    assert any(d.entity_id == "submodule_limitation" for d in defects)


def test_zero_denominator_ratio_detected() -> None:
    b = mutate_zero_denominator_ratio(_fixture_bundle())
    _c, defects = check_coverage([b])
    assert any(d.entity_id == "sv11_zero_denom" for d in defects)
