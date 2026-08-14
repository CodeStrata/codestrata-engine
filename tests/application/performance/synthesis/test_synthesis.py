"""Performance synthesis tests (Phase 4.9.5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.application.performance.assessment.artifacts import (
    performance_assessment_payload as build_performance_assessment_payload,
)
from codestrata.application.performance.assessment.artifacts import (
    write_performance_assessment_artifact,
)
from codestrata.application.performance.assessment.assembler import PerformanceAssessmentAssembler
from codestrata.application.performance.assessment.inventory import execution_facts_from_status_map
from codestrata.application.performance.synthesis import synthesize_performance
from codestrata.artifacts.heads import resolve_head_path
from codestrata.config import load_settings
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.domain.performance.assessment.enums import (
    PerformanceAssessmentStatus,
    PerformanceLimitationCategory,
)
from codestrata.domain.performance.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.performance.assessment.models import (
    PerformanceFamilyInventory,
    PerformanceFindingInventory,
    PerformanceLimitation,
    PerformanceRuleInventory,
)
from codestrata.domain.performance.ids import (
    HYGIENE_RULE_IDS,
    RULE_BLOCKING_SLEEP,
    RULE_BROAD_FOUNDATIONS,
    RULE_CACHING,
    RULE_CONCURRENCY,
    RULE_CONCURRENCY_WITHOUT_CONFIG,
    RULE_CONFIG_CONTROLS,
    RULE_DATA_ACCESS,
    RULE_DATA_ACCESS_WITHOUT_BATCHING,
    RULE_DATA_WITHOUT_CACHING,
    RULE_EXECUTOR_CONFIG,
    RULE_FRONTEND_BUNDLE,
    RULE_FRONTEND_LAZY,
    RULE_FRONTEND_LIMITED,
    RULE_LIMITED_CONTROLS,
    RULE_MULTIPLE_DATA_ACCESS,
    RULE_OBSERVABILITY,
    RULE_RESOURCE_MGMT,
    RULE_RESOURCES_WITHOUT_MGMT,
    RULE_SYNC_IO,
    RULE_WITHOUT_OBSERVABILITY,
)
from codestrata.domain.performance.synthesis.enums import (
    PerformanceConclusionKind,
    PerformanceRecommendationKind,
    PerformanceSynthesisStatus,
    PerformanceThemeKind,
)
from codestrata.domain.performance.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.services.artifact_serialization import dumps_stable_json


def _finding(
    *,
    rule_id: str,
    finding_id: str,
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
    confidence: str = "high",
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=severity,
        category=FindingCategory.PERFORMANCE,
        metadata={"confidence": confidence},
    )


def _facts_all_matched(matched: set[str]) -> tuple:
    status = {
        rule_id: ("matched" if rule_id in matched else "not_matched")
        for rule_id in HYGIENE_RULE_IDS
    }
    return execution_facts_from_status_map(status)


def _limitation() -> PerformanceLimitation:
    return PerformanceLimitation(
        limitation_id="performance-limitation:scope",
        category=PerformanceLimitationCategory.NO_PERFORMANCE_CONCLUSION,
        summary="Performance scoring remains out of scope for this assessment.",
        affected_capability="performance",
    )


def _rule_inventory(*, matched: int, executed: int | None = None) -> PerformanceRuleInventory:
    executed_count = executed if executed is not None else len(HYGIENE_RULE_IDS)
    return PerformanceRuleInventory(
        rules_planned=len(HYGIENE_RULE_IDS),
        rules_executed=executed_count,
        rules_matched=matched,
        rules_not_matched=max(executed_count - matched, 0),
    )


def _assert_no_forbidden(result: object) -> None:
    texts: list[str] = []
    overall = getattr(result, "overall_posture_summary", "") or ""
    texts.append(overall)
    for item in getattr(result, "themes", ()) or ():
        texts.extend([item.title, item.description])
    for item in getattr(result, "conclusions", ()) or ():
        texts.extend([item.title, item.summary, item.technical_interpretation])
    for item in getattr(result, "recommendations", ()) or ():
        texts.extend([item.title, item.action, item.rationale])
    joined = " ".join(texts).lower()
    sanitized = (
        joined.replace("does not establish that the repository is performant", "")
        .replace("do not establish that the repository is performant", "")
        .replace("does not mean the repository is performant", "")
        .replace("the repository is performant", "")
        .replace("does not establish performance", "")
        .replace("without claiming the repository is performant", "")
        .replace("from claiming the repository is performant", "")
        .replace("claiming the repository is performant", "")
        .replace("not performance scores", "")
        .replace("performance scoring", "")
        .replace("performance scores", "")
        .replace("free of latency risk", "")
        .replace("production-ready under load", "")
        .replace("is performant", "")
        .replace("are performant", "")
        .replace("performant", "")
        .replace("scalable", "")
        .replace("bottleneck", "")
        .replace("hotspot", "")
    )
    for phrase in (
        "is performant",
        "are performant",
        "performant",
        "bottleneck",
        "latency bottleneck",
        "is slow",
        "repository is slow",
        "performance score",
        "performance grade",
        "readiness score",
        "production ready",
        "production-ready under load",
        "scalable",
        "free of latency",
        "modernize",
        "modernisation",
        "modernization path",
        "migrate to",
        "hotspot",
    ):
        assert phrase not in sanitized, phrase


def test_schema_and_synthesis_gate(tmp_path: Path) -> None:
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert SYNTHESIS_VERSION == "1.0.0"
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [rules]
        enabled = true
        [rules.performance]
        enabled = true
        [analysis.performance]
        enabled = true
        include_synthesis = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.analysis.performance.include_synthesis is False
    section = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:gate",
        findings=(),
        include_synthesis=False,
        rules_executed=len(HYGIENE_RULE_IDS),
        rule_execution_facts=_facts_all_matched(set()),
        evidence_fingerprint="syn-fp-1",
    )
    assert section.section_version == "1.2.0"
    assert section.synthesis.status is PerformanceSynthesisStatus.NOT_REQUESTED
    assert section.metadata.get("assessment_milestone") == "4.9.5"
    assert section.metadata.get("synthesis_version") == SYNTHESIS_VERSION


def test_zero_findings_neutral_posture() -> None:
    result = synthesize_performance(
        repository_id="repo:empty",
        pack_enabled=True,
        section_status=PerformanceAssessmentStatus.SUCCEEDED,
        findings=(),
        finding_inventory=PerformanceFindingInventory(),
        rule_inventory=_rule_inventory(matched=0),
        evidence_status="succeeded",
    )
    assert result.status is PerformanceSynthesisStatus.EMPTY
    kinds = {item.kind for item in result.themes}
    assert PerformanceThemeKind.PERFORMANCE_HYGIENE_LANDSCAPE in kinds
    assert PerformanceThemeKind.RULE_EXECUTION_COVERAGE in kinds
    assert PerformanceThemeKind.NO_PERFORMANCE_FINDINGS in kinds
    assert PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS not in kinds
    assert result.overall_posture_summary
    _assert_no_forbidden(result)


def test_each_supported_theme() -> None:
    cases = [
        (
            RULE_DATA_ACCESS,
            PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS,
            PerformanceConclusionKind.DATA_ACCESS_FOUNDATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_DATA_ACCESS_FOUNDATION_SIGNALS,
        ),
        (
            RULE_MULTIPLE_DATA_ACCESS,
            PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS,
            PerformanceConclusionKind.DATA_ACCESS_FOUNDATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_DATA_ACCESS_FOUNDATION_SIGNALS,
        ),
        (
            RULE_DATA_ACCESS_WITHOUT_BATCHING,
            PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS,
            PerformanceConclusionKind.DATA_ACCESS_FOUNDATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_DATA_ACCESS_FOUNDATION_SIGNALS,
        ),
        (
            RULE_BLOCKING_SLEEP,
            PerformanceThemeKind.BLOCKING_OPERATIONS,
            PerformanceConclusionKind.BLOCKING_OPERATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_BLOCKING_OPERATION_SIGNALS,
        ),
        (
            RULE_SYNC_IO,
            PerformanceThemeKind.BLOCKING_OPERATIONS,
            PerformanceConclusionKind.BLOCKING_OPERATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_BLOCKING_OPERATION_SIGNALS,
        ),
        (
            RULE_CACHING,
            PerformanceThemeKind.CACHING_FOUNDATIONS,
            PerformanceConclusionKind.CACHING_FOUNDATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_CACHING_FOUNDATION_SIGNALS,
        ),
        (
            RULE_DATA_WITHOUT_CACHING,
            PerformanceThemeKind.CACHING_FOUNDATIONS,
            PerformanceConclusionKind.CACHING_FOUNDATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_CACHING_FOUNDATION_SIGNALS,
        ),
        (
            RULE_CONCURRENCY,
            PerformanceThemeKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING,
            PerformanceConclusionKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_OBSERVED,
            PerformanceRecommendationKind.REVIEW_CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_SIGNALS,
        ),
        (
            RULE_EXECUTOR_CONFIG,
            PerformanceThemeKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING,
            PerformanceConclusionKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_OBSERVED,
            PerformanceRecommendationKind.REVIEW_CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_SIGNALS,
        ),
        (
            RULE_CONCURRENCY_WITHOUT_CONFIG,
            PerformanceThemeKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING,
            PerformanceConclusionKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_OBSERVED,
            PerformanceRecommendationKind.REVIEW_CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_SIGNALS,
        ),
        (
            RULE_RESOURCE_MGMT,
            PerformanceThemeKind.RESOURCE_MANAGEMENT,
            PerformanceConclusionKind.RESOURCE_MANAGEMENT_OBSERVED,
            PerformanceRecommendationKind.REVIEW_RESOURCE_MANAGEMENT_SIGNALS,
        ),
        (
            RULE_RESOURCES_WITHOUT_MGMT,
            PerformanceThemeKind.RESOURCE_MANAGEMENT,
            PerformanceConclusionKind.RESOURCE_MANAGEMENT_OBSERVED,
            PerformanceRecommendationKind.REVIEW_RESOURCE_MANAGEMENT_SIGNALS,
        ),
        (
            RULE_FRONTEND_BUNDLE,
            PerformanceThemeKind.FRONTEND_PERFORMANCE_CONTROLS,
            PerformanceConclusionKind.FRONTEND_PERFORMANCE_CONTROLS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_FRONTEND_PERFORMANCE_CONTROL_SIGNALS,
        ),
        (
            RULE_FRONTEND_LAZY,
            PerformanceThemeKind.FRONTEND_PERFORMANCE_CONTROLS,
            PerformanceConclusionKind.FRONTEND_PERFORMANCE_CONTROLS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_FRONTEND_PERFORMANCE_CONTROL_SIGNALS,
        ),
        (
            RULE_FRONTEND_LIMITED,
            PerformanceThemeKind.FRONTEND_PERFORMANCE_CONTROLS,
            PerformanceConclusionKind.FRONTEND_PERFORMANCE_CONTROLS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_FRONTEND_PERFORMANCE_CONTROL_SIGNALS,
        ),
        (
            RULE_OBSERVABILITY,
            PerformanceThemeKind.PERFORMANCE_OBSERVABILITY_AND_PROFILING,
            PerformanceConclusionKind.PERFORMANCE_OBSERVABILITY_AND_PROFILING_OBSERVED,
            PerformanceRecommendationKind.VALIDATE_OBSERVED_PERFORMANCE_OBSERVABILITY_SIGNALS,
        ),
        (
            RULE_WITHOUT_OBSERVABILITY,
            PerformanceThemeKind.PERFORMANCE_OBSERVABILITY_AND_PROFILING,
            PerformanceConclusionKind.PERFORMANCE_OBSERVABILITY_AND_PROFILING_OBSERVED,
            PerformanceRecommendationKind.VALIDATE_OBSERVED_PERFORMANCE_OBSERVABILITY_SIGNALS,
        ),
        (
            RULE_CONFIG_CONTROLS,
            PerformanceThemeKind.CONFIGURATION_CONTROLS,
            PerformanceConclusionKind.CONFIGURATION_CONTROLS_OBSERVED,
            PerformanceRecommendationKind.VALIDATE_OBSERVED_CONFIGURATION_CONTROLS,
        ),
        (
            RULE_BROAD_FOUNDATIONS,
            PerformanceThemeKind.BROAD_PERFORMANCE_FOUNDATIONS,
            PerformanceConclusionKind.BROAD_PERFORMANCE_FOUNDATIONS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_BROAD_PERFORMANCE_FOUNDATIONS,
        ),
        (
            RULE_LIMITED_CONTROLS,
            PerformanceThemeKind.LIMITED_SUPPORTING_CONTROLS,
            PerformanceConclusionKind.LIMITED_SUPPORTING_CONTROLS_OBSERVED,
            PerformanceRecommendationKind.REVIEW_LIMITED_SUPPORTING_CONTROLS,
        ),
    ]
    for rule_id, theme_kind, conclusion_kind, recommendation_kind in cases:
        finding = _finding(rule_id=rule_id, finding_id=f"f-{rule_id}")
        result = synthesize_performance(
            repository_id="repo:themes",
            pack_enabled=True,
            section_status=PerformanceAssessmentStatus.SUCCEEDED,
            findings=(finding,),
            finding_inventory=PerformanceFindingInventory(
                finding_ids=(finding.id,),
                finding_count=1,
                rule_counts={rule_id: 1},
            ),
            rule_inventory=_rule_inventory(matched=1),
        )
        assert result.status is PerformanceSynthesisStatus.SUCCEEDED
        assert theme_kind in {item.kind for item in result.themes}
        assert conclusion_kind in {item.kind for item in result.conclusions}
        assert recommendation_kind in {item.kind for item in result.recommendations}
        rec = next(item for item in result.recommendations if item.kind is recommendation_kind)
        assert finding.id in rec.finding_ids
        assert rule_id in rec.rule_ids
        assert rec.conclusion_ids
        _assert_no_forbidden(result)


def test_broad_foundations_from_families_without_perf071() -> None:
    findings = (
        _finding(rule_id=RULE_DATA_ACCESS, finding_id="f-data"),
        _finding(rule_id=RULE_CACHING, finding_id="f-cache"),
        _finding(rule_id=RULE_CONFIG_CONTROLS, finding_id="f-cfg"),
    )
    result = synthesize_performance(
        repository_id="repo:partial",
        pack_enabled=True,
        section_status=PerformanceAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=PerformanceFindingInventory(
            finding_ids=("f-data", "f-cache", "f-cfg"),
            finding_count=3,
        ),
        rule_inventory=_rule_inventory(matched=3),
        performance_family_inventory=PerformanceFamilyInventory(
            families_observed=3,
            families_total=8,
        ),
    )
    kinds = {item.kind for item in result.themes}
    assert PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS in kinds
    assert PerformanceThemeKind.CACHING_FOUNDATIONS in kinds
    assert PerformanceThemeKind.CONFIGURATION_CONTROLS in kinds
    assert PerformanceThemeKind.BROAD_PERFORMANCE_FOUNDATIONS in kinds
    assert PerformanceThemeKind.LIMITED_SUPPORTING_CONTROLS not in kinds


def test_limited_supporting_controls() -> None:
    finding = _finding(rule_id=RULE_LIMITED_CONTROLS, finding_id="f-lim")
    result = synthesize_performance(
        repository_id="repo:limited",
        pack_enabled=True,
        section_status=PerformanceAssessmentStatus.SUCCEEDED,
        findings=(finding,),
        finding_inventory=PerformanceFindingInventory(
            finding_ids=(finding.id,),
            finding_count=1,
        ),
        rule_inventory=_rule_inventory(matched=1),
        performance_family_inventory=PerformanceFamilyInventory(
            families_observed=1,
            families_total=8,
        ),
    )
    kinds = {item.kind for item in result.themes}
    assert PerformanceThemeKind.LIMITED_SUPPORTING_CONTROLS in kinds
    assert PerformanceThemeKind.BROAD_PERFORMANCE_FOUNDATIONS not in kinds


def test_unsupported_scope_theme() -> None:
    result = synthesize_performance(
        repository_id="repo:limits",
        pack_enabled=True,
        section_status=PerformanceAssessmentStatus.SUCCEEDED,
        findings=(),
        finding_inventory=PerformanceFindingInventory(),
        rule_inventory=_rule_inventory(matched=0),
        limitations=(_limitation(),),
    )
    kinds = {item.kind for item in result.themes}
    assert PerformanceThemeKind.UNSUPPORTED_ANALYSIS_SCOPE in kinds
    assert PerformanceThemeKind.NO_PERFORMANCE_FINDINGS in kinds
    assert PerformanceRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_PERFORMANCE_ANALYSIS_SCOPE in {
        item.kind for item in result.recommendations
    }


def test_partial_foundations_assembler(tmp_path: Path) -> None:
    findings = (
        _finding(rule_id=RULE_DATA_ACCESS, finding_id="f-001"),
        _finding(
            rule_id=RULE_CACHING,
            finding_id="f-002",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    section = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:partial",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        rule_execution_facts=_facts_all_matched({RULE_DATA_ACCESS, RULE_CACHING}),
        evidence_fingerprint="syn-fp-1",
        configuration_payload="partial-config",
    )
    assert section.synthesis.status is PerformanceSynthesisStatus.SUCCEEDED
    theme_kinds = {item.kind for item in section.themes}
    assert PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS in theme_kinds
    assert PerformanceThemeKind.CACHING_FOUNDATIONS in theme_kinds
    assert PerformanceThemeKind.UNSUPPORTED_ANALYSIS_SCOPE in theme_kinds
    assert PerformanceThemeKind.FRONTEND_PERFORMANCE_CONTROLS not in theme_kinds
    assert PerformanceThemeKind.BLOCKING_OPERATIONS not in theme_kinds
    assert section.execution_summary.theme_count == len(section.themes)
    assert section.execution_summary.conclusion_count == len(section.conclusions)
    assert section.execution_summary.recommendation_count == len(section.recommendations)
    for recommendation in section.recommendations:
        assert recommendation.conclusion_ids
        if recommendation.kind in {
            PerformanceRecommendationKind.REVIEW_DATA_ACCESS_FOUNDATION_SIGNALS,
            PerformanceRecommendationKind.REVIEW_CACHING_FOUNDATION_SIGNALS,
        }:
            assert recommendation.finding_ids
            assert recommendation.rule_ids
    body = dumps_stable_json(build_performance_assessment_payload(section))
    assert '"themes"' in body
    assert '"conclusions"' in body
    assert '"recommendations"' in body
    assert '"overall_posture_summary"' in body
    write_performance_assessment_artifact(section, tmp_path)
    assert (
        resolve_head_path(tmp_path, legacy_filename="performance-assessment.json").read_text(
            encoding="utf-8"
        )
        == body
    )
    _assert_no_forbidden(section.synthesis)


def test_deterministic_ordering_and_ids() -> None:
    findings = (
        _finding(rule_id=RULE_CACHING, finding_id="f-b"),
        _finding(rule_id=RULE_DATA_ACCESS, finding_id="f-a"),
    )
    left = synthesize_performance(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=PerformanceAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=PerformanceFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=_rule_inventory(matched=2),
    )
    right = synthesize_performance(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=PerformanceAssessmentStatus.SUCCEEDED,
        findings=tuple(reversed(findings)),
        finding_inventory=PerformanceFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=_rule_inventory(matched=2),
    )
    assert left.model_dump_json() == right.model_dump_json()
    assert dumps_stable_json(left.model_dump(mode="json")) == dumps_stable_json(
        right.model_dump(mode="json")
    )
    assert left.theme_ids == tuple(item.theme_id for item in left.themes)
    assert left.conclusion_ids == tuple(item.conclusion_id for item in left.conclusions)
    assert all(item.startswith("performance-theme:") for item in left.theme_ids)
    assert all(item.startswith("performance-conclusion:") for item in left.conclusion_ids)
    assert all(item.startswith("performance-recommendation:") for item in left.recommendation_ids)


def test_disabled_and_insufficient_synthesis() -> None:
    disabled = synthesize_performance(
        repository_id="repo:x",
        pack_enabled=False,
        section_status=PerformanceAssessmentStatus.DISABLED,
    )
    assert disabled.status is PerformanceSynthesisStatus.DISABLED
    insufficient = synthesize_performance(
        repository_id="repo:x",
        pack_enabled=True,
        section_status=PerformanceAssessmentStatus.INSUFFICIENT_EVIDENCE,
    )
    assert insufficient.status is PerformanceSynthesisStatus.INSUFFICIENT_EVIDENCE


def test_synthesis_failure_isolation() -> None:
    with patch(
        "codestrata.application.performance.assessment.assembler.synthesize_performance",
        side_effect=RuntimeError("boom"),
    ):
        section = PerformanceAssessmentAssembler().assemble(
            repository_id="repo:fail",
            findings=(),
            rules_executed=len(HYGIENE_RULE_IDS),
            rule_execution_facts=_facts_all_matched(set()),
            evidence_fingerprint="syn-fp-1",
        )
    assert section.synthesis.status is PerformanceSynthesisStatus.FAILED
    assert section.finding_inventory.finding_count == 0
    assert any("synthesis_failed" in item for item in section.diagnostics)
