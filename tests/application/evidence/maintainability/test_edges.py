"""Negative, partial, unsupported and budget fixtures for E08.3."""

from __future__ import annotations

import pytest

from codestrata.application.evidence.maintainability.consumer import (
    ConsumerContractError,
    consume_envelope,
)
from codestrata.application.evidence.maintainability.envelope import (
    EnvelopeError,
    MaintainabilityEnvelopeBody,
    digest_body,
    parse_envelope_payload,
)
from codestrata.application.evidence.maintainability.models import (
    ComponentSpec,
    CoverageScope,
    DependencyReleaseRecord,
    FileChurnRecord,
    FindingLifecycle,
    FindingReferenceInput,
    HistoryWindow,
)
from codestrata.application.evidence.maintainability.projections import dumps_maintainability_json
from codestrata.application.evidence.maintainability.service import (
    MaintainabilityBudgets,
    MaintainabilityEvidenceService,
)
from codestrata.application.evidence.quality.models import (
    CloneMetric,
    FileRole,
    FunctionRecord,
    FunctionStatus,
    MetricStatusName,
    QualityEvidence,
    SourceSpan,
)
from codestrata.application.evidence.quality.models import (
    CoverageScope as QualityCoverage,
)
from codestrata.application.rules.technical_debt.yaml_maintainability import (
    HotspotRule,
    maintainability_evidence,
)
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus


def _quality(*paths: str, cyclomatic: int = 4) -> QualityEvidence:
    functions = tuple(
        FunctionRecord(
            function_id=f"{path}:fn",
            language="python",
            path=path,
            name="fn",
            qualified_name="fn",
            span=SourceSpan(path=path, line_start=1, line_end=3),
            role=FileRole.SOURCE,
            status=FunctionStatus.MEASURED,
            cyclomatic=cyclomatic,
            branch_count=cyclomatic - 1,
            nloc=3,
            max_nesting_depth=1,
            cyclomatic_version="cyclomatic.v1",
            nesting_version="nesting.v1",
            size_version="nloc.v1",
            branch_map_language="python",
        )
        for path in paths
    )
    return QualityEvidence(
        repository_id="fixture",
        functions=functions,
        clone=CloneMetric(
            status=MetricStatusName.NOT_APPLICABLE,
            full_scope_status=QualityCoverage.NOT_APPLICABLE,
            reason="unused",
            normalization_version="token.normalize.v1",
            formula_version="clone.v1",
            min_tokens=50,
            min_lines=5,
        ),
    )


def test_partial_history_is_unranked_not_missing_as_zero() -> None:
    evidence, _ = MaintainabilityEvidenceService().collect(
        repository_id="fixture",
        quality=_quality("pkg/a.py"),
        components=(ComponentSpec(component_id="pkg", file_paths=("pkg/a.py",)),),
        history=HistoryWindow(
            profile_id="m24.history.profile.v1",
            window="180d_then_latest_1000",
            head_sha="abc",
            coverage=CoverageScope.PARTIAL,
            coverage_reason="shallow_history",
            file_churn=(FileChurnRecord(path="pkg/a.py", changed_lines=9),),
        ),
    )
    record = evidence.partial_hotspots[0]
    churn = next(item for item in record.contributors if item.name == "churn")
    assert churn.value == "9"
    assert record.ranking_value is None
    assert HotspotRule().evaluate(
        RuleExecutionContext(
            repository=RepositoryFactView(repository_id="fixture"),
            languages=LanguageInventoryView(languages=("python",)),
            assessment_graph=evidence,
        )
    ).status is RuleResultStatus.NOT_MATCHED


def test_binary_churn_unknown_is_not_zero() -> None:
    evidence, _ = MaintainabilityEvidenceService().collect(
        repository_id="fixture",
        quality=_quality("pkg/a.py"),
        components=(ComponentSpec(component_id="pkg", file_paths=("pkg/a.py",)),),
        history=HistoryWindow(
            profile_id="m24.history.profile.v1",
            window="180d_then_latest_1000",
            head_sha="abc",
            coverage=CoverageScope.COMPLETE,
            coverage_reason="complete",
            file_churn=(
                FileChurnRecord(
                    path="pkg/a.py",
                    changed_lines=None,
                    coverage_reason="binary_churn_unknown",
                ),
            ),
        ),
    )
    record = evidence.partial_hotspots[0]
    churn = next(item for item in record.contributors if item.name == "churn")
    assert churn.value is None
    assert churn.coverage_reason == "binary_or_unknown_churn"
    assert record.ranking_value is None


def test_empty_component_mapping_is_missing_structure() -> None:
    evidence, _ = MaintainabilityEvidenceService().collect(
        repository_id="fixture",
        quality=_quality("pkg/a.py"),
        components=(ComponentSpec(component_id="ghost", file_paths=()),),
        history=HistoryWindow(
            profile_id="m24.history.profile.v1",
            window="180d_then_latest_1000",
            head_sha="abc",
            coverage=CoverageScope.COMPLETE,
            coverage_reason="complete",
            file_churn=(FileChurnRecord(path="pkg/a.py", changed_lines=4),),
        ),
    )
    record = evidence.partial_hotspots[0]
    complexity = next(item for item in record.contributors if item.name == "complexity")
    assert complexity.coverage_reason == "missing_structure"
    assert evidence.static_function_ids == ("pkg/a.py:fn",)


def test_component_budget_is_visible_not_a_zero() -> None:
    evidence, _ = MaintainabilityEvidenceService(MaintainabilityBudgets(max_components=1)).collect(
        repository_id="fixture",
        quality=_quality("a.py", "b.py"),
        components=(
            ComponentSpec(component_id="a", file_paths=("a.py",)),
            ComponentSpec(component_id="b", file_paths=("b.py",)),
        ),
        history=HistoryWindow(
            profile_id="m24.history.profile.v1",
            window="180d_then_latest_1000",
            head_sha="abc",
            coverage=CoverageScope.COMPLETE,
            coverage_reason="complete",
            file_churn=(
                FileChurnRecord(path="a.py", changed_lines=1),
                FileChurnRecord(path="b.py", changed_lines=1),
            ),
        ),
    )
    assert "component_budget_exceeded" in evidence.limitations
    assert len(evidence.complete_hotspots) + len(evidence.partial_hotspots) == 1
    assert all(
        item.ranking_value != "0" or item.subject_id == "a"
        for item in evidence.complete_hotspots
    )


def test_live_lookup_quality_is_rejected() -> None:
    quality = _quality("pkg/a.py").model_copy(update={"live_lookup": True})
    with pytest.raises(ValueError, match="live-lookup"):
        MaintainabilityEvidenceService().collect(
            repository_id="fixture",
            quality=quality,
            components=(ComponentSpec(component_id="pkg", file_paths=("pkg/a.py",)),),
            history=None,
        )


def test_consumer_rejects_health_score_and_corrupt_digest() -> None:
    evidence, envelope = MaintainabilityEvidenceService().collect(
        repository_id="fixture",
        quality=_quality("pkg/a.py"),
        components=(ComponentSpec(component_id="pkg", file_paths=("pkg/a.py",)),),
        history=HistoryWindow(
            profile_id="m24.history.profile.v1",
            window="180d_then_latest_1000",
            head_sha="abc",
            coverage=CoverageScope.COMPLETE,
            coverage_reason="complete",
            file_churn=(FileChurnRecord(path="pkg/a.py", changed_lines=2),),
        ),
    )
    dumped = envelope.model_dump(mode="json")
    dumped["body"]["health_verdict"] = "healthy"
    dumped["body_digest"] = digest_body(MaintainabilityEnvelopeBody.model_validate(dumped["body"]))
    with pytest.raises(ConsumerContractError, match="health verdict"):
        consume_envelope(dumped)
    broken = envelope.model_dump(mode="json")
    broken["body_digest"] = "0" * 64
    with pytest.raises((ConsumerContractError, EnvelopeError)):
        parse_envelope_payload(broken)
    json_text = dumps_maintainability_json(envelope)
    assert "opaque_score" in json_text
    assert maintainability_evidence(
        RuleExecutionContext(
            repository=RepositoryFactView(repository_id="fixture"),
            languages=LanguageInventoryView(languages=("python",)),
            enterprise_context=evidence,
        )
    ) is evidence


def test_finding_and_dependency_budgets_are_visible() -> None:
    evidence, _ = MaintainabilityEvidenceService(
        MaintainabilityBudgets(max_findings=1, max_dependencies=1)
    ).collect(
        repository_id="fixture",
        quality=_quality("pkg/a.py"),
        components=(ComponentSpec(component_id="pkg", file_paths=("pkg/a.py",)),),
        history=None,
        findings=(
            FindingReferenceInput(
                finding_id="f1",
                subject_id="pkg",
                state=FindingLifecycle.ACTIVE,
            ),
            FindingReferenceInput(
                finding_id="f2",
                subject_id="pkg",
                state=FindingLifecycle.ACTIVE,
            ),
        ),
        dependencies=(
            DependencyReleaseRecord(
                package_id="eco:a",
                ecosystem="pypi",
                installed_version="1",
                publication_time_unix=1,
                source_snapshot_id="s",
            ),
            DependencyReleaseRecord(
                package_id="eco:b",
                ecosystem="pypi",
                installed_version="1",
                publication_time_unix=1,
                source_snapshot_id="s",
            ),
        ),
    )
    assert "finding_budget_exceeded" in evidence.limitations
    assert "dependency_budget_exceeded" in evidence.limitations


def test_parse_rejects_wrong_schema_and_non_object() -> None:
    with pytest.raises(EnvelopeError, match="unsupported envelope schema"):
        parse_envelope_payload({"schema_name": "nope", "schema_version": "1"})
    with pytest.raises(EnvelopeError, match="envelope must be an object"):
        parse_envelope_payload([])
    with pytest.raises(EnvelopeError, match="unsupported envelope version"):
        parse_envelope_payload(
            {
                "schema_name": "codestrata.maintainability.envelope.v1",
                "schema_version": "nope",
            }
        )


def test_unavailable_evidence_is_not_applicable() -> None:
    result = HotspotRule().evaluate(
        RuleExecutionContext(
            repository=RepositoryFactView(repository_id="fixture"),
            languages=LanguageInventoryView(languages=("python",)),
        )
    )
    assert result.status is RuleResultStatus.NOT_APPLICABLE
