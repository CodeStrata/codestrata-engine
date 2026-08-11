"""Slice 4.10 — Modernization recommendation authority-chain precision."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from validation.actual import run_real_assessment
from validation.inventory import FactClassification, compute_precision_recall
from validation.models import ExpectedResults, ValidationVerdict
from validation.modernization import (
    ModernizationExpectation,
    ModernizationPriorityActionActual,
    ModernizationPriorityActionExpectation,
    ModernizationRecommendationActual,
    ModernizationRecommendationExpectation,
    ModernizationRoadmapInitiativeActual,
    ModernizationRoadmapInitiativeExpectation,
    aggregate_modernization_results,
    extract_modernization_priority_actions,
    extract_modernization_recommendations,
    extract_modernization_roadmap_initiatives,
    validate_modernization_precision,
)
from validation.paths import VALIDATION_ROOT
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.summary import build_validation_summary


def test_contradictory_modernization_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        ModernizationExpectation(
            required_recommendations=(
                ModernizationRecommendationExpectation(title_pattern="(?i)LICENSE"),
            ),
            forbidden_recommendations=(
                ModernizationRecommendationExpectation(title_pattern="(?i)LICENSE"),
            ),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ModernizationExpectation(
            required_roadmap_phases=("stabilize",),
            forbidden_roadmap_phases=("stabilize",),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            modernization=ModernizationExpectation(
                required_priority_actions=(
                    ModernizationPriorityActionExpectation(title_pattern="(?i)LICENSE"),
                ),
                forbidden_priority_actions=(
                    ModernizationPriorityActionExpectation(title_pattern="(?i)LICENSE"),
                ),
            )
        )


def test_classify_tp_fp_fn_and_metrics() -> None:
    expectation = ModernizationExpectation(
        required_recommendations=(
            ModernizationRecommendationExpectation(
                title_pattern="(?i)LICENSE",
                supporting_rule_ids=("codestrata-rule-missing-license",),
            ),
        ),
        forbidden_recommendations=(
            ModernizationRecommendationExpectation(
                title_pattern="(?i)become cloud native",
            ),
        ),
        forbidden_conclusions=("modernization ready",),
    )
    recs = (
        ModernizationRecommendationActual(
            recommendation_id="recommendation:codestrata-rec-missing-license:abc",
            title="Add an explicit LICENSE",
            category="governance",
            priority="medium",
            recommendation_type="finding_backed",
            primary_finding_id="finding:codestrata-rule-missing-license:1",
            supporting_finding_ids=("finding:codestrata-rule-missing-license:1",),
            related_finding_ids=("finding:codestrata-rule-missing-license:1",),
            supporting_rule_ids=("codestrata-rule-missing-license",),
            evidence_completeness="complete",
        ),
        ModernizationRecommendationActual(
            recommendation_id="bad",
            title="Become cloud native now",
            category="cloud",
            priority="high",
            recommendation_type="finding_backed",
            primary_finding_id="finding:x:1",
            supporting_finding_ids=("finding:x:1",),
            related_finding_ids=("finding:x:1",),
            supporting_rule_ids=("cloud.cloud-010",),
            evidence_completeness="complete",
        ),
    )
    result = validate_modernization_precision(
        repository_id="fixture",
        expectation=expectation,
        actual_recommendations=recs,
        actual_priority_actions=(),
        actual_roadmap_initiatives=(),
        finding_ids={
            "finding:codestrata-rule-missing-license:1",
            "finding:x:1",
        },
        artifact_texts={
            "report.json": (
                "Absence of Priority Actions does not establish absence of "
                "modernization need. No delivery estimate was produced."
            )
        },
        ai_executed=False,
    )
    by_name = {item.name: item.classification for item in result.classifications}
    assert any(
        item.classification is FactClassification.TRUE_POSITIVE
        and "LICENSE" in item.name
        for item in result.classifications
    )
    assert any(
        item.classification is FactClassification.FALSE_POSITIVE
        and "cloud native" in item.name.lower()
        for item in result.classifications
    )
    assert result.precision is not None
    assert result.recall == pytest.approx(1.0)


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0, false_positives=0, false_negatives=0
    )
    assert precision is None and recall is None and reason is not None


def test_authority_chain_rejects_presentation_finding_ids() -> None:
    expectation = ModernizationExpectation(require_finding_backed_authority=True)
    actions = (
        ModernizationPriorityActionActual(
            action_id="presentation:finding:abc",
            title="Fabricated from finding",
            priority="high",
            presentation_bucket="immediate",
            category="security",
            primary_recommendation_id="presentation:finding:abc",
            supporting_recommendation_ids=("presentation:finding:abc",),
            supporting_finding_ids=("presentation:finding:abc",),
        ),
    )
    result = validate_modernization_precision(
        repository_id="bad",
        expectation=expectation,
        actual_recommendations=(),
        actual_priority_actions=actions,
        actual_roadmap_initiatives=(),
        finding_ids=set(),
        ai_executed=False,
    )
    assert result.false_positives >= 1
    assert any("presentation:finding" in d for d in result.diagnostics)


def test_legacy_roadmap_allowed_when_marked() -> None:
    expectation = ModernizationExpectation(
        require_priority_action_backed_roadmap=True,
        required_roadmap_initiatives=(
            ModernizationRoadmapInitiativeExpectation(
                title_pattern="(?i)Cloud",
                phase="modernize",
                initiative_type="legacy",
            ),
        ),
    )
    initiatives = (
        ModernizationRoadmapInitiativeActual(
            initiative_id="legacy:cloud",
            title="Modernize — Cloud",
            phase="modernize",
            initiative_type="legacy",
            primary_priority_action_id=None,
            supporting_priority_action_ids=(),
        ),
    )
    result = validate_modernization_precision(
        repository_id="petclinic",
        expectation=expectation,
        actual_recommendations=(),
        actual_priority_actions=(),
        actual_roadmap_initiatives=initiatives,
        finding_ids=set(),
        ai_executed=False,
    )
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.passed


def test_ai_executed_is_blocking() -> None:
    result = validate_modernization_precision(
        repository_id="ai-on",
        expectation=ModernizationExpectation(),
        actual_recommendations=(),
        actual_priority_actions=(),
        actual_roadmap_initiatives=(),
        finding_ids=set(),
        ai_executed=True,
    )
    assert result.false_positives >= 1
    assert any("ai" in d.lower() for d in result.diagnostics)


def test_aggregate_deterministic_order() -> None:
    expectation = ModernizationExpectation(
        required_recommendations=(
            ModernizationRecommendationExpectation(title_pattern="(?i)LICENSE"),
        )
    )
    rec = ModernizationRecommendationActual(
        recommendation_id="r1",
        title="Add an explicit LICENSE",
        category="governance",
        priority="medium",
        recommendation_type="finding_backed",
        primary_finding_id="f1",
        supporting_finding_ids=("f1",),
        related_finding_ids=("f1",),
        supporting_rule_ids=("codestrata-rule-missing-license",),
        evidence_completeness="complete",
    )
    a = validate_modernization_precision(
        repository_id="repo-a",
        expectation=expectation,
        actual_recommendations=(rec,),
        actual_priority_actions=(),
        actual_roadmap_initiatives=(),
        finding_ids={"f1"},
    )
    b = validate_modernization_precision(
        repository_id="repo-b",
        expectation=expectation,
        actual_recommendations=(rec,),
        actual_priority_actions=(),
        actual_roadmap_initiatives=(),
        finding_ids={"f1"},
    )
    aggregate = aggregate_modernization_results((b, a))
    # Deterministic ordering is by repository_id, not input order.
    assert [item.repository_id for item in aggregate.per_repository] == [
        "repo-a",
        "repo-b",
    ]


def test_all_repositories_have_modernization_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.modernization is not None, definition.repository_id
        assert expected.modernization.evidence_notes, definition.repository_id
        assert expected.schema_version == "1.2"


def test_controlled_security_fixture_modernization(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "security-hygiene").resolve()
    actual, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "out",
    )
    titles = {item.title for item in actual.modernization_recommendations}
    assert any("Rotate credentials" in title for title in titles)
    pas = actual.modernization_priority_actions
    assert any(
        "Rotate credentials" in item.title
        and item.priority in {"critical", "immediate", "high"}
        and item.presentation_bucket in {"immediate", "near_term"}
        and item.category == "security"
        for item in pas
    )
    assert not any(
        item.action_id.startswith("presentation:finding:") for item in pas
    )
    for item in actual.modernization_recommendations:
        blob = f"{item.title} {item.summary or ''}"
        assert "BEGIN " not in blob
        assert "AKIA" not in blob

    expected = resolve_expected_results(
        next(
            item
            for item in load_all_repositories()
            if item.repository_id == "local-security-hygiene"
        )
    )
    assert expected.modernization is not None
    result = validate_modernization_precision(
        repository_id="local-security-hygiene",
        expectation=expected.modernization,
        actual_recommendations=actual.modernization_recommendations,
        actual_priority_actions=actual.modernization_priority_actions,
        actual_roadmap_initiatives=actual.modernization_roadmap_initiatives,
        finding_ids=set(actual.finding_ids),
        artifact_texts={"report.json": json.dumps(actual.report_document)},
        limitation_texts=actual.limitations,
        ai_executed=bool(actual.ai_executed),
    )
    assert result.false_positives == 0, result.diagnostics
    assert result.false_negatives == 0, result.diagnostics
    assert result.passed, result.diagnostics


def test_controlled_ai_fixture_no_ai_priority_actions(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "ai-readiness").resolve()
    config = VALIDATION_ROOT / "configs" / "local-ai-readiness.toml"
    actual, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "out",
        config_path=config,
    )
    assert not any(
        "AI integration" in item.title or "MCP and tool" in item.title
        for item in actual.modernization_priority_actions
    )
    assert any("LICENSE" in item.title for item in actual.modernization_priority_actions)


def test_modernization_repeat_run_determinism(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "security-hygiene").resolve()
    first, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "a"
    )
    second, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "b"
    )
    assert sorted(
        item.recommendation_id or "" for item in first.modernization_recommendations
    ) == sorted(
        item.recommendation_id or "" for item in second.modernization_recommendations
    )
    assert sorted(
        item.action_id or "" for item in first.modernization_priority_actions
    ) == sorted(item.action_id or "" for item in second.modernization_priority_actions)


def test_six_repository_modernization_suite(tmp_path_factory) -> None:
    definitions = [item for item in load_all_repositories() if item.enabled]
    output_root = tmp_path_factory.mktemp("mod-suite")
    results = run_validation_suite(
        definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        local_only=False,
        include_remote=True,
    )
    summary = build_validation_summary(results)
    assert summary.failed == 0, [
        (r.repository_id, r.mismatches) for r in results if r.verdict != ValidationVerdict.PASS
    ]
    assert summary.errors == 0

    mod_results = []
    for definition, run in zip(definitions, results, strict=True):
        if run.verdict == ValidationVerdict.SKIPPED:
            # Remote clone can be environment-skipped; locals must still pass.
            assert definition.source_type.value == "remote", (
                definition.repository_id,
                run.skip_reason,
            )
            continue
        assert run.verdict == ValidationVerdict.PASS, (
            definition.repository_id,
            run.verdict,
            run.mismatches,
            run.error_message,
            run.skip_reason,
        )
        expected = resolve_expected_results(definition)
        assert expected.modernization is not None
        report = next(Path(run.artifact_dir).rglob("report.json"))
        document = json.loads(report.read_text(encoding="utf-8"))
        findings = (document.get("assessment") or {}).get("findings") or []
        finding_ids = {
            str(item.get("id"))
            for item in findings
            if isinstance(item, dict) and item.get("id")
        }
        recs = extract_modernization_recommendations(document)
        pas = extract_modernization_priority_actions(document)
        initiatives = extract_modernization_roadmap_initiatives(document)
        result = validate_modernization_precision(
            repository_id=definition.repository_id,
            expectation=expected.modernization,
            actual_recommendations=recs,
            actual_priority_actions=pas,
            actual_roadmap_initiatives=initiatives,
            finding_ids=finding_ids,
            artifact_texts={"report.json": report.read_text(encoding="utf-8")},
            ai_executed=False,
        )
        assert result.false_positives == 0, (
            definition.repository_id,
            result.diagnostics,
        )
        assert result.passed, (definition.repository_id, result.diagnostics)
        mod_results.append(result)
    assert mod_results, "expected at least local modernization precision results"
    aggregate = aggregate_modernization_results(mod_results)
    assert aggregate.false_positives == 0
    assert aggregate.precision == 1.0 or aggregate.precision is None
