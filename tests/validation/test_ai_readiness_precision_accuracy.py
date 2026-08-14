"""Slice 4.9 — AI Readiness precision expectation model, metrics, and fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.evidence.repository_ai_readiness.discovery import (
    classify_ai_readiness_candidate,
)
from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessEvidenceFamily,
)
from validation.actual import load_emitted_assessment, run_real_assessment
from validation.ai_readiness import (
    AiReadinessExpectation,
    AiReadinessFamilyExpectation,
    AiReadinessFindingActual,
    AiReadinessFindingExpectation,
    AiReadinessRecommendationActual,
    AiReadinessRecommendationExpectation,
    AiReadinessSignalActual,
    AiReadinessSignalExpectation,
    aggregate_ai_readiness_results,
    extract_ai_readiness_findings,
    extract_ai_readiness_signals,
    validate_ai_readiness_precision,
)
from validation.inventory import FactClassification, compute_precision_recall
from validation.models import ExpectedResults, ValidationVerdict
from validation.paths import VALIDATION_ROOT
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.summary import build_validation_summary


def test_contradictory_ai_readiness_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        AiReadinessExpectation(
            expected_rule_ids=("ai_readiness.ai-030",),
            forbidden_rule_ids=("ai_readiness.ai-030",),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        AiReadinessExpectation(
            required_signal_families=(
                AiReadinessFamilyExpectation(family_id="ai_integration"),
            ),
            forbidden_signal_families=(
                AiReadinessFamilyExpectation(family_id="ai_integration"),
            ),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            ai_readiness=AiReadinessExpectation(
                required_findings=(
                    AiReadinessFindingExpectation(rule_id="ai_readiness.ai-040"),
                ),
                forbidden_rule_ids=("ai_readiness.ai-040",),
            )
        )


def test_classify_tp_fp_fn_and_metrics() -> None:
    expectation = AiReadinessExpectation(
        required_signal_families=(
            AiReadinessFamilyExpectation(family_id="ai_integration"),
        ),
        required_findings=(
            AiReadinessFindingExpectation(rule_id="ai_readiness.ai-030"),
        ),
        forbidden_rule_ids=("ai_readiness.ai-032",),
        forbidden_conclusions=("ai ready",),
    )
    actual_findings = (
        AiReadinessFindingActual(
            rule_id="ai_readiness.ai-030",
            path="src/openai_agent.py",
            evidence_ids=("e1",),
        ),
        AiReadinessFindingActual(
            rule_id="ai_readiness.ai-032",
            path="notes/prose.md",
            evidence_ids=("e2",),
        ),
    )
    signals = (
        AiReadinessSignalActual(
            family_id="ai_integration",
            signal_kind="llm_sdk",
            path="src/openai_agent.py",
            confirmation_level="structurally_confirmed",
        ),
    )
    result = validate_ai_readiness_precision(
        repository_id="fixture",
        expectation=expectation,
        actual_findings=actual_findings,
        actual_signals=signals,
        artifact_texts={
            "report.json": (
                "Repository-observable AI-enablement signals were detected. "
                "Runtime model behavior and organizational readiness were not assessed. "
                "Absence of findings does not establish AI readiness."
            )
        },
    )
    by_name = {item.name: item.classification for item in result.classifications}
    assert by_name["family:ai_integration"] is FactClassification.TRUE_POSITIVE
    assert by_name["ai_readiness.ai-030"] is FactClassification.TRUE_POSITIVE
    assert by_name["ai_readiness.ai-032"] is FactClassification.FALSE_POSITIVE
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == pytest.approx(1.0)


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0, false_positives=0, false_negatives=0
    )
    assert precision is None and recall is None and reason is not None


def test_aggregate_deterministic_order() -> None:
    expectation = AiReadinessExpectation(
        required_signal_families=(
            AiReadinessFamilyExpectation(family_id="tool_mcp"),
        )
    )
    signals = (
        AiReadinessSignalActual(
            family_id="tool_mcp",
            signal_kind="mcp_server",
            path="mcp.json",
            confirmation_level="structurally_confirmed",
        ),
    )
    a = validate_ai_readiness_precision(
        repository_id="repo-a",
        expectation=expectation,
        actual_findings=(),
        actual_signals=signals,
    )
    b = validate_ai_readiness_precision(
        repository_id="repo-b",
        expectation=expectation,
        actual_findings=(),
        actual_signals=signals,
    )
    aggregate = aggregate_ai_readiness_results((b, a))
    assert [item.repository_id for item in aggregate.per_repository] == [
        "repo-b",
        "repo-a",
    ]
    assert aggregate.precision == 1.0


def test_all_repositories_have_ai_readiness_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.ai_readiness is not None, definition.repository_id
        assert expected.ai_readiness.evidence_notes, definition.repository_id


def test_generic_negative_controls_not_discovered() -> None:
    """Package name / prose / helpers must not invent AI families."""

    cases = (
        ("notes/fake-agent-package-name.txt", None),
        ("notes/assistant-shaped-prose.md", None),
        ("notes/ordinary-build-pipeline.md", None),
        ("src/helpers/utility_helpers.py", None),
        ("docs/mentions-ai-only.md", AiReadinessEvidenceFamily.DOCUMENTATION),
        ("src/openai_agent.py", AiReadinessEvidenceFamily.AI_INTEGRATION),
        ("mcp.json", AiReadinessEvidenceFamily.TOOL_MCP),
        ("openapi.yaml", AiReadinessEvidenceFamily.API_BOUNDARY),
        ("README.md", AiReadinessEvidenceFamily.DOCUMENTATION),
    )
    for path, expected_family in cases:
        classified = classify_ai_readiness_candidate(path)
        if expected_family is None:
            assert classified is None or classified.family is AiReadinessEvidenceFamily.UNKNOWN, path
            if classified is not None:
                assert classified.family not in {
                    AiReadinessEvidenceFamily.AI_INTEGRATION,
                    AiReadinessEvidenceFamily.TOOL_MCP,
                    AiReadinessEvidenceFamily.WORKFLOW_AGENT,
                    AiReadinessEvidenceFamily.DATA_RETRIEVAL,
                }, path
        else:
            assert classified is not None, path
            assert classified.family is expected_family, path


def test_recommendation_and_count_range_expectations() -> None:
    expectation = AiReadinessExpectation(
        required_recommendations=(
            AiReadinessRecommendationExpectation(
                title_pattern="(?i)AI integration",
                rationale="signal review",
            ),
        ),
        forbidden_recommendations=(
            AiReadinessRecommendationExpectation(
                title_pattern="(?i)deploy rag",
                rationale="no RAG deploy",
            ),
        ),
        expected_count_ranges=(),
    )
    result = validate_ai_readiness_precision(
        repository_id="recs",
        expectation=expectation,
        actual_findings=(),
        actual_recommendations=(
            AiReadinessRecommendationActual(
                title="Review AI integration signals",
                category="AI readiness signals",
            ),
            AiReadinessRecommendationActual(
                title="Deploy RAG to production",
                category="AI readiness signals",
            ),
        ),
    )
    assert result.false_positives >= 1
    assert any(
        item.classification is FactClassification.TRUE_POSITIVE
        and "recommendation" in item.rule_id
        for item in result.classifications
    )


def test_controlled_ai_readiness_fixture_precision(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "ai-readiness").resolve()
    config = VALIDATION_ROOT / "configs" / "local-ai-readiness.toml"
    actual, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "out",
        config_path=config,
    )
    rule_ids = {item.rule_id for item in actual.ai_readiness_findings}
    for rule_id in (
        "ai_readiness.ai-002",
        "ai_readiness.ai-030",
        "ai_readiness.ai-040",
        "ai_readiness.ai-051",
        "ai_readiness.ai-060",
    ):
        assert rule_id in rule_ids, rule_id
    assert "ai_readiness.ai-003" not in rule_ids
    assert "ai_readiness.ai-031" not in rule_ids
    assert "ai_readiness.ai-032" not in rule_ids
    assert "ai_readiness.ai-041" not in rule_ids

    families = {item.family_id for item in actual.ai_readiness_signals}
    assert {
        "api_boundary",
        "documentation",
        "ai_integration",
        "tool_mcp",
    }.issubset(families)
    assert "workflow_agent" not in families
    assert "data_retrieval" not in families
    assert "observability_governance" not in families

    assert any(
        item.family_id == "ai_integration"
        and item.signal_kind == "llm_sdk"
        and item.path == "src/openai_agent.py"
        for item in actual.ai_readiness_signals
    )
    assert any(
        item.family_id == "tool_mcp"
        and item.signal_kind == "mcp_server"
        and item.path == "mcp.json"
        for item in actual.ai_readiness_signals
    )
    assert not any(
        item.path and "assistant-shaped-prose" in item.path and item.family_id == "ai_integration"
        for item in actual.ai_readiness_signals
    )
    assert not any(
        item.path and "utility_helpers" in item.path and item.family_id == "tool_mcp"
        for item in actual.ai_readiness_signals
    )

    expected = resolve_expected_results(
        next(
            item
            for item in load_all_repositories()
            if item.repository_id == "local-ai-readiness"
        )
    )
    assert expected.ai_readiness is not None
    result = validate_ai_readiness_precision(
        repository_id="local-ai-readiness",
        expectation=expected.ai_readiness,
        actual_findings=actual.ai_readiness_findings,
        actual_signals=actual.ai_readiness_signals,
        actual_recommendations=actual.ai_readiness_recommendations,
        artifact_texts={"report.json": json.dumps(actual.report_document)},
        limitation_texts=actual.limitations,
    )
    assert result.false_positives == 0, result.diagnostics
    assert result.false_negatives == 0, result.diagnostics
    assert result.passed, result.diagnostics

    for item in actual.ai_readiness_findings:
        assert item.finding_id
        assert item.path is None or not item.path.startswith("/")
        assert item.evidence_ids


def test_ai_readiness_repeat_run_determinism(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "ai-readiness").resolve()
    config = VALIDATION_ROOT / "configs" / "local-ai-readiness.toml"
    first, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "a",
        config_path=config,
    )
    second, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "b",
        config_path=config,
    )
    assert sorted(item.finding_id or "" for item in first.ai_readiness_findings) == sorted(
        item.finding_id or "" for item in second.ai_readiness_findings
    )


def test_negative_control_repositories_ai_readiness(tmp_path_factory) -> None:
    definitions = [
        item
        for item in load_all_repositories()
        if item.repository_id
        in {
            "local-sample-js",
            "local-sample-python",
            "local-cloud-signals",
            "local-security-hygiene",
        }
    ]
    output_root = tmp_path_factory.mktemp("ai-neg")
    results = run_validation_suite(
        definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        local_only=True,
        include_remote=False,
    )
    summary = build_validation_summary(results)
    assert summary.failed == 0, [
        (r.repository_id, r.mismatches) for r in results if r.verdict != ValidationVerdict.PASS
    ]
    assert summary.errors == 0

    ai_results = []
    for definition, run in zip(definitions, results, strict=True):
        assert run.verdict == ValidationVerdict.PASS, (
            definition.repository_id,
            run.mismatches,
        )
        expected = resolve_expected_results(definition)
        assert expected.ai_readiness is not None
        report, document = load_emitted_assessment(run.artifact_dir)
        artifact_paths = {report.name: str(report)}
        evidence = report.parent / "repository-ai-readiness-evidence.json"
        if evidence.is_file():
            artifact_paths["repository-ai-readiness-evidence.json"] = str(evidence)
        findings_list = (document.get("assessment") or {}).get("findings") or []
        findings = extract_ai_readiness_findings(findings_list)
        signals = extract_ai_readiness_signals(document, artifact_paths=artifact_paths)
        for forbidden in expected.ai_readiness.forbidden_rule_ids:
            assert forbidden not in {item.rule_id for item in findings}
        result = validate_ai_readiness_precision(
            repository_id=definition.repository_id,
            expectation=expected.ai_readiness,
            actual_findings=findings,
            actual_signals=signals,
            artifact_texts={report.name: json.dumps(document)},
            limitation_texts=(),
        )
        assert result.false_positives == 0, result.diagnostics
        assert result.passed, result.diagnostics
        ai_results.append(result)
    aggregate = aggregate_ai_readiness_results(ai_results)
    assert aggregate.false_positives == 0


def test_schema_remains_1_2() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.schema_version == "1.2"
