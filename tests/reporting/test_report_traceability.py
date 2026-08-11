"""Epic 2 Slice 2.6 — canonical report.json traceability tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    RuleEvaluationResult,
)
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResult,
)
from codestrata.domain.traceability import (
    EvidenceCompleteness,
    EvidenceKind,
    EvidenceLocation,
    EvidenceRef,
    dedupe_evidence_refs,
)
from codestrata.domain.traceability.enums import EvidenceProductionMode
from codestrata.models import (
    AnalysisResult,
    Repository,
    RepositoryFacts,
    StructureFacts,
)
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.customer_universe import (
    CustomerFinding,
    CustomerRecommendation,
    customer_finding_json,
    write_customer_finding_artifacts,
)
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.traceability import (
    AssessmentTraceabilityError,
    build_assessment_priority_actions,
    collect_assessment_evidence,
    serialize_evidence_index,
    validate_assessment_traceability,
)


def _evidence_ref(evidence_id: str, *, path: str = "src/App.py") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        location=EvidenceLocation(path=path),
    )


def _analysis(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["src/App.py"],
            total_files=1,
        ),
        technologies=[],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=1,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[],
        recommendations=[],
    )


def _report_with_traceability(tmp_path: Path) -> ModernizationReportInput:
    ref = _evidence_ref("ev:secret-1")
    finding = Finding.create(
        rule_id="security.credential-literal",
        title="Literal credential",
        description="Found credential",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("path:src/App.py",),
        evidence=(
            FindingEvidence(
                evidence_type="file",
                source_id="src",
                path="src/App.py",
                excerpt="***",
            ),
        ),
        evidence_refs=(ref,),
        primary_evidence_id="ev:secret-1",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )
    recommendation = Recommendation.create(
        provider_id="codestrata-rec-secret",
        title="Remediate credentials",
        summary="Rotate exposed credentials",
        rationale="Security risk",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.GOVERNANCE,
        related_finding_ids=(finding.id,),
        supporting_finding_ids=(finding.id,),
        primary_finding_id=finding.id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        actions=(
            RecommendationAction(order=1, title="Rotate", description="Rotate secret"),
        ),
        subject_keys=("repo",),
    )
    return ModernizationReportInput(
        analysis_result=_analysis(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=RuleEvaluationResult.from_findings(
            findings=(finding,),
            rules_evaluated=("security.credential-literal",),
        ),
        assessment_recommendation_result=RecommendationResult.from_recommendations(
            recommendations=(recommendation,),
            providers_evaluated=("codestrata-rec-secret",),
        ),
    )


def test_evidence_collected_from_findings_deduped_ordered() -> None:
    f1 = CustomerFinding(
        id="f1",
        rule_id="R1",
        title="t",
        description="d",
        severity="high",
        category="security",
        source="deterministic",
        evidence=(),
        affected_technologies=(),
        metadata={},
        evidence_refs=(
            _evidence_ref("ev-b", path="b.py"),
            _evidence_ref("ev-a", path="a.py"),
            _evidence_ref("ev-a", path="a.py"),
        ),
        primary_evidence_id="ev-a",
        evidence_completeness="complete",
    )
    refs = collect_assessment_evidence([f1])
    assert [item.evidence_id for item in refs] == ["ev-a", "ev-b"]
    payload = serialize_evidence_index(refs)
    assert all("evidence_id" in item for item in payload)
    assert all(
        not str((item.get("location") or {}).get("path", "")).startswith("/")
        for item in payload
    )


def test_contradictory_duplicate_evidence_rejected() -> None:
    a = _evidence_ref("ev-1", path="a.py")
    b = EvidenceRef(
        evidence_id="ev-1",
        kind=EvidenceKind.MEASUREMENT,
        production_mode=EvidenceProductionMode.DIRECT,
        location=EvidenceLocation(path="a.py"),
    )
    with pytest.raises(Exception):
        dedupe_evidence_refs((a, b))


def test_no_unreferenced_fabricated_evidence() -> None:
    finding = CustomerFinding(
        id="f1",
        rule_id="R1",
        title="t",
        description="d",
        severity="high",
        category="security",
        source="deterministic",
        evidence=(),
        affected_technologies=(),
        metadata={},
        evidence_refs=(_evidence_ref("ev-1"),),
        primary_evidence_id="ev-1",
        evidence_completeness="complete",
    )
    refs = collect_assessment_evidence([finding])
    assert len(refs) == 1
    assert refs[0].evidence_id == "ev-1"


def test_finding_serialization_keeps_inline_and_refs() -> None:
    finding = CustomerFinding(
        id="f1",
        rule_id="R1",
        title="t",
        description="d",
        severity="high",
        category="security",
        source="deterministic",
        evidence=({"path": "src/App.py", "excerpt": "x"},),
        affected_technologies=(),
        metadata={},
        evidence_refs=(_evidence_ref("ev-1"),),
        primary_evidence_id="ev-1",
        synthesized_from_evidence_ids=(),
        evidence_completeness="complete",
        limitations=(),
    )
    payload = customer_finding_json(finding)
    assert payload["id"] == "f1"
    assert payload["evidence"]
    assert payload["evidence_refs"] == [{"evidence_id": "ev-1"}]
    assert payload["primary_evidence_id"] == "ev-1"


def test_full_chain_in_report_json(tmp_path: Path) -> None:
    document = build_assessment_json_document(_report_with_traceability(tmp_path))
    assert document["schema_version"] == "1.2"
    assert document["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    assessment = document["assessment"]
    assert assessment["evidence"]
    assert assessment["priority_actions"]
    assert assessment["roadmap"]
    assert assessment["summary"]["evidence_count"] == len(assessment["evidence"])
    assert assessment["summary"]["priority_action_count"] == len(
        assessment["priority_actions"]
    )
    assert assessment["summary"]["finding_count"] == len(assessment["findings"])
    assert assessment["summary"]["recommendation_count"] == len(
        assessment["deterministic_recommendations"]
    )

    initiative = assessment["roadmap"]["initiatives"][0]
    assert initiative["initiative_type"] == "priority_action_backed"
    pa_id = initiative["supporting_priority_action_ids"][0]
    action = next(a for a in assessment["priority_actions"] if a["action_id"] == pa_id)
    assert not action["action_id"].startswith("presentation:finding:")
    rec_id = action["supporting_recommendation_ids"][0]
    rec = next(r for r in assessment["deterministic_recommendations"] if r["id"] == rec_id)
    finding_id = rec["supporting_finding_ids"][0]
    finding = next(f for f in assessment["findings"] if f["id"] == finding_id)
    evidence_id = finding["evidence_refs"][0]["evidence_id"]
    evidence = next(e for e in assessment["evidence"] if e["evidence_id"] == evidence_id)
    assert (evidence.get("location") or {}).get("path") == "src/App.py"
    assert finding["evidence"]  # inline retained for compatibility
    assert rec["related_finding_ids"] == rec["supporting_finding_ids"]

    validate_assessment_traceability(assessment)


def test_repeat_run_stable_ids(tmp_path: Path) -> None:
    first = build_assessment_json_document(_report_with_traceability(tmp_path))
    second = build_assessment_json_document(_report_with_traceability(tmp_path))
    assert [e["evidence_id"] for e in first["assessment"]["evidence"]] == [
        e["evidence_id"] for e in second["assessment"]["evidence"]
    ]
    assert [f["id"] for f in first["assessment"]["findings"]] == [
        f["id"] for f in second["assessment"]["findings"]
    ]
    assert [a["action_id"] for a in first["assessment"]["priority_actions"]] == [
        a["action_id"] for a in second["assessment"]["priority_actions"]
    ]
    assert [
        i["initiative_id"] for i in first["assessment"]["roadmap"]["initiatives"]
    ] == [i["initiative_id"] for i in second["assessment"]["roadmap"]["initiatives"]]


def test_companion_artifacts_align(tmp_path: Path) -> None:
    report_input = _report_with_traceability(tmp_path)
    document = build_assessment_json_document(report_input)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_customer_finding_artifacts(report_input, run_dir)
    import json

    findings_doc = json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))
    recs_doc = json.loads((run_dir / "recommendations.json").read_text(encoding="utf-8"))
    assert findings_doc["finding_count"] == document["assessment"]["summary"]["finding_count"]
    assert [f["id"] for f in findings_doc["findings"]] == [
        f["id"] for f in document["assessment"]["findings"]
    ]
    assert recs_doc["recommendation_count"] == document["assessment"]["summary"][
        "recommendation_count"
    ]
    assert [r["id"] for r in recs_doc["recommendations"]] == [
        r["id"] for r in document["assessment"]["deterministic_recommendations"]
    ]


def test_validator_unknown_evidence_fails() -> None:
    assessment = {
        "evidence": [],
        "findings": [
            {
                "id": "f1",
                "evidence_refs": [{"evidence_id": "missing"}],
                "primary_evidence_id": "missing",
            }
        ],
        "deterministic_recommendations": [],
        "priority_actions": [],
    }
    with pytest.raises(AssessmentTraceabilityError, match="unknown evidence"):
        validate_assessment_traceability(assessment)


def test_validator_unknown_finding_fails() -> None:
    assessment = {
        "evidence": [],
        "findings": [],
        "deterministic_recommendations": [
            {
                "id": "r1",
                "supporting_finding_ids": ["missing"],
                "related_finding_ids": ["missing"],
                "primary_finding_id": "missing",
            }
        ],
        "priority_actions": [],
    }
    with pytest.raises(AssessmentTraceabilityError, match="unknown finding"):
        validate_assessment_traceability(assessment)


def test_validator_unknown_recommendation_fails() -> None:
    assessment = {
        "evidence": [],
        "findings": [{"id": "f1", "evidence_refs": []}],
        "deterministic_recommendations": [
            {
                "id": "r1",
                "supporting_finding_ids": ["f1"],
                "related_finding_ids": ["f1"],
                "primary_finding_id": "f1",
            }
        ],
        "priority_actions": [
            {
                "action_id": "r1",
                "supporting_recommendation_ids": ["missing"],
                "primary_recommendation_id": "missing",
                "supporting_finding_ids": ["f1"],
            }
        ],
    }
    with pytest.raises(AssessmentTraceabilityError, match="unknown recommendation"):
        validate_assessment_traceability(assessment)


def test_validator_unknown_priority_action_fails() -> None:
    assessment = {
        "evidence": [],
        "findings": [{"id": "f1", "evidence_refs": []}],
        "deterministic_recommendations": [
            {
                "id": "r1",
                "supporting_finding_ids": ["f1"],
                "related_finding_ids": ["f1"],
                "primary_finding_id": "f1",
            }
        ],
        "priority_actions": [
            {
                "action_id": "r1",
                "supporting_recommendation_ids": ["r1"],
                "primary_recommendation_id": "r1",
                "supporting_finding_ids": ["f1"],
            }
        ],
        "roadmap": {
            "initiatives": [
                {
                    "initiative_id": "i1",
                    "initiative_type": "priority_action_backed",
                    "supporting_priority_action_ids": ["missing"],
                    "primary_priority_action_id": "missing",
                    "supporting_recommendation_ids": ["r1"],
                    "supporting_finding_ids": ["f1"],
                    "depends_on_initiative_ids": [],
                }
            ]
        },
    }
    with pytest.raises(AssessmentTraceabilityError, match="unknown priority_action"):
        validate_assessment_traceability(assessment)


def test_validator_mismatched_derived_union_fails() -> None:
    assessment = {
        "evidence": [],
        "findings": [{"id": "f1", "evidence_refs": []}, {"id": "f2", "evidence_refs": []}],
        "deterministic_recommendations": [
            {
                "id": "r1",
                "supporting_finding_ids": ["f1"],
                "related_finding_ids": ["f1"],
                "primary_finding_id": "f1",
            }
        ],
        "priority_actions": [
            {
                "action_id": "r1",
                "supporting_recommendation_ids": ["r1"],
                "primary_recommendation_id": "r1",
                "supporting_finding_ids": ["f1", "f2"],
            }
        ],
    }
    with pytest.raises(AssessmentTraceabilityError, match="mismatch derived union"):
        validate_assessment_traceability(assessment)


def test_validator_unresolved_roadmap_dependency_fails() -> None:
    assessment = {
        "evidence": [],
        "findings": [{"id": "f1", "evidence_refs": []}],
        "deterministic_recommendations": [
            {
                "id": "r1",
                "supporting_finding_ids": ["f1"],
                "related_finding_ids": ["f1"],
                "primary_finding_id": "f1",
            }
        ],
        "priority_actions": [
            {
                "action_id": "r1",
                "supporting_recommendation_ids": ["r1"],
                "primary_recommendation_id": "r1",
                "supporting_finding_ids": ["f1"],
            }
        ],
        "roadmap": {
            "initiatives": [
                {
                    "initiative_id": "i1",
                    "initiative_type": "priority_action_backed",
                    "supporting_priority_action_ids": ["r1"],
                    "primary_priority_action_id": "r1",
                    "supporting_recommendation_ids": ["r1"],
                    "supporting_finding_ids": ["f1"],
                    "depends_on_initiative_ids": ["missing-init"],
                }
            ]
        },
    }
    with pytest.raises(AssessmentTraceabilityError, match="depends_on unresolved"):
        validate_assessment_traceability(assessment)


def test_priority_actions_built_from_recommendations_only() -> None:
    rec = CustomerRecommendation(
        id="rec-1",
        rule_id="R",
        title="t",
        description="d",
        rationale="r",
        priority="high",
        category="security",
        effort="m",
        risk="high",
        related_finding_ids=("f1",),
        supporting_finding_ids=("f1",),
        primary_finding_id="f1",
        actions=(),
        dependencies=(),
        evidence=(),
        priority_score=10.0,
        presentation_bucket="immediate",
        recommendation_type="deterministic",
        evidence_completeness="complete",
    )
    actions = build_assessment_priority_actions([rec])
    assert len(actions) == 1
    assert actions[0].action_id == "rec-1"
    assert actions[0].supporting_finding_ids == ("f1",)


def test_empty_universe_still_valid(tmp_path: Path) -> None:
    report_input = ModernizationReportInput(
        analysis_result=_analysis(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
    )
    document = build_assessment_json_document(report_input)
    assert document["assessment"]["evidence"] == []
    assert document["assessment"]["priority_actions"] == []
    assert "roadmap" not in document["assessment"]
    assert document["schema_version"] == "1.2"
