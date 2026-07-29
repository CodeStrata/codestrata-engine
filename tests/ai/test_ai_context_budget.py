"""Tests for AI context budgeting and normalized PMD input selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.ai.contracts import (
    AIContextBudgetError,
    LLMAnalysisContextBuilder,
    LLMContractLimits,
)
from codestrata.ai.contracts.budget import select_findings_for_ai_context
from codestrata.models import (
    AnalysisResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    Severity,
)
from codestrata.static_analysis.models import (
    StaticAnalysisObservation,
    StaticAnalysisResult,
    StaticAnalysisStatus,
)
from codestrata.static_analysis.visibility import CustomerVisibility, ModernizationRelevance


def _finding(
    *,
    rule_id: str,
    title: str,
    severity: Severity,
    source: FindingSource = FindingSource.DETERMINISTIC,
    visibility: str = CustomerVisibility.PRIMARY.value,
    metadata: dict[str, object] | None = None,
) -> Finding:
    payload = {
        "customer_visibility": visibility,
        **(metadata or {}),
    }
    return Finding(
        rule_id=rule_id,
        title=title,
        description=f"{title} description",
        category=FindingCategory.MAINTAINABILITY,
        severity=severity,
        source=source,
        evidence=[Evidence(file_path="src/Example.java", line_number=10)],
        metadata=payload,
    )


def test_suppressed_observations_excluded_from_candidates() -> None:
    findings = [
        _finding(rule_id="KEEP", title="Keep", severity=Severity.MEDIUM),
        _finding(
            rule_id="STYLE",
            title="Suppressed style",
            severity=Severity.LOW,
            source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
            visibility=CustomerVisibility.SUPPRESSED_FROM_HTML.value,
        ),
    ]
    selection = select_findings_for_ai_context(findings, max_findings=10)
    assert selection.candidate_count == 1
    assert [item.rule_id for item in selection.included] == ["KEEP"]


def test_critical_high_never_omitted() -> None:
    findings = [
        _finding(rule_id="CRIT", title="Critical", severity=Severity.CRITICAL),
        _finding(rule_id="HIGH", title="High", severity=Severity.HIGH),
        _finding(rule_id="MED", title="Medium", severity=Severity.MEDIUM),
        _finding(
            rule_id="INFO",
            title="Info",
            severity=Severity.INFO,
            visibility=CustomerVisibility.INFORMATIONAL.value,
        ),
    ]
    selection = select_findings_for_ai_context(findings, max_findings=2)
    assert {item.rule_id for item in selection.included} == {"CRIT", "HIGH"}
    assert selection.omitted_informational_count == 1


def test_budget_error_when_critical_cannot_fit() -> None:
    findings = [
        _finding(rule_id=f"C{i}", title=f"Critical {i}", severity=Severity.CRITICAL)
        for i in range(3)
    ]
    with pytest.raises(AIContextBudgetError, match="critical/high"):
        select_findings_for_ai_context(findings, max_findings=2)


def test_builder_prefers_grouped_pmd_over_raw_observations(tmp_path: Path) -> None:
    observation = StaticAnalysisObservation(
        observation_id="obs-1",
        provider_id="pmd",
        provider_name="pmd",
        provider_version="7.26.0",
        rule_id="BestPractices.UnusedLocalVariable",
        normalized_category=FindingCategory.MAINTAINABILITY,
        normalized_severity=Severity.LOW,
        customer_visibility=CustomerVisibility.SUPPRESSED_FROM_HTML,
        modernization_relevance=ModernizationRelevance.LOW,
        file_path="src/A.java",
        line_number=1,
        message="unused",
        title="Unused local",
    )
    grouped = _finding(
        rule_id="BestPractices.UnusedLocalVariable",
        title="Unused local variable",
        severity=Severity.MEDIUM,
        source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
        visibility=CustomerVisibility.PRIMARY.value,
        metadata={
            "group_id": "pmd:BestPractices.UnusedLocalVariable",
            "occurrence_count": 12,
            "affected_file_count": 4,
            "mapping_rationale": "Grouped unused locals",
            "modernization_relevance": "maintainability",
        },
    )
    result = AnalysisResult(
        repository=Repository(name="demo", path=tmp_path, files=["src/A.java"], total_files=1),
        findings=[grouped],
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="pmd",
                provider_version="7.26.0",
                status=StaticAnalysisStatus.COMPLETED,
                profile="standard",
                observations=[observation],
                raw_observation_count=1,
                grouped_finding_count=1,
                files_analyzed=1,
                eligible_file_count=1,
            )
        ],
    )
    context = LLMAnalysisContextBuilder().build(result)
    assert context.budget is not None
    assert context.budget.candidate_finding_count == 1
    assert context.budget.included_finding_count == 1
    assert context.findings[0].group_id == "pmd:BestPractices.UnusedLocalVariable"
    assert context.static_analysis_summary.raw_observation_count == 1
    assert context.static_analysis_summary.grouped_finding_count == 1
    assert len(context.findings) == 1


def test_builder_records_budget_metadata(tmp_path: Path) -> None:
    findings = [
        _finding(rule_id="CRIT", title="Critical", severity=Severity.CRITICAL),
        _finding(
            rule_id="INFO1",
            title="Info one",
            severity=Severity.INFO,
            visibility=CustomerVisibility.INFORMATIONAL.value,
        ),
        _finding(
            rule_id="INFO2",
            title="Info two",
            severity=Severity.INFO,
            visibility=CustomerVisibility.INFORMATIONAL.value,
        ),
    ]
    result = AnalysisResult(
        repository=Repository(name="demo", path=tmp_path, files=["a.java"], total_files=1),
        findings=findings,
    )
    context = LLMAnalysisContextBuilder(limits=LLMContractLimits(max_findings=1)).build(result)
    assert context.budget is not None
    assert context.budget.candidate_finding_count == 3
    assert context.budget.included_finding_count == 1
    assert context.budget.omitted_informational_count == 2
    assert context.budget.estimated_input_tokens > 0
    assert context.findings[0].rule_id == "CRIT"
