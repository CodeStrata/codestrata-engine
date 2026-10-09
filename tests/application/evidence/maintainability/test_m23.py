"""M23 fixtures: dependency staleness and finding-concern ordering."""

from __future__ import annotations

from codestrata.application.evidence.maintainability.capability import (
    CONCERN_ORDER_VERSION,
    EVIDENCE_CLASS_ORDER_VERSION,
)
from codestrata.application.evidence.maintainability.consumer import consume_envelope
from codestrata.application.evidence.maintainability.derive import EVIDENCE_CLASS_ORDER_V1
from codestrata.application.evidence.maintainability.models import (
    ComponentSpec,
    CoverageScope,
    DependencyReleaseRecord,
    EvidenceClass,
    FileChurnRecord,
    FindingLifecycle,
    FindingReferenceInput,
    HistoryWindow,
    MetricStatusName,
)
from codestrata.application.evidence.maintainability.service import MaintainabilityEvidenceService
from codestrata.application.evidence.quality.models import (
    CloneMetric,
    FileRole,
    FunctionRecord,
    FunctionStatus,
    QualityEvidence,
    SourceSpan,
)
from codestrata.application.evidence.quality.models import (
    CoverageScope as QualityCoverage,
)
from codestrata.application.evidence.quality.models import (
    MetricStatusName as QualityMetric,
)
from codestrata.application.rules.technical_debt.yaml_catalog import quality_catalog_digests
from codestrata.application.rules.technical_debt.yaml_maintainability import DependencyAgeRule
from codestrata.domain.contracts.formulas import m23_staleness_days
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus, RuleSeverity

EVAL_TIME = 1_700_000_000


def _quality() -> QualityEvidence:
    return QualityEvidence(
        repository_id="fixture",
        functions=(
            FunctionRecord(
                function_id="pkg/a.py:run",
                language="python",
                path="pkg/a.py",
                name="run",
                qualified_name="run",
                span=SourceSpan(path="pkg/a.py", line_start=1, line_end=4),
                role=FileRole.SOURCE,
                status=FunctionStatus.MEASURED,
                cyclomatic=3,
                branch_count=2,
                nloc=4,
                max_nesting_depth=1,
                cyclomatic_version="cyclomatic.v1",
                nesting_version="nesting.v1",
                size_version="nloc.v1",
                branch_map_language="python",
            ),
        ),
        clone=CloneMetric(
            status=QualityMetric.NOT_APPLICABLE,
            full_scope_status=QualityCoverage.NOT_APPLICABLE,
            reason="unused",
            normalization_version="token.normalize.v1",
            formula_version="clone.v1",
            min_tokens=50,
            min_lines=5,
        ),
    )


def _history(lines: int = 2) -> HistoryWindow:
    return HistoryWindow(
        profile_id="m24.history.profile.v1",
        window="180d_then_latest_1000",
        head_sha="abc",
        coverage=CoverageScope.COMPLETE,
        coverage_reason="complete",
        evaluation_time_unix=EVAL_TIME,
        included_commit_count=1,
        file_churn=(FileChurnRecord(path="pkg/a.py", changed_lines=lines),),
    )


def _run(*, dependencies, evaluation_time_unix=EVAL_TIME, findings=(), snapshot="snap-a", **kwargs):
    return MaintainabilityEvidenceService().collect(
        repository_id="fixture",
        quality=_quality(),
        components=(ComponentSpec(component_id="pkg", file_paths=("pkg/a.py",)),),
        history=_history(),
        catalog_digest=quality_catalog_digests()["maintainability.dependency_age"],
        dependencies=dependencies,
        evaluation_time_unix=evaluation_time_unix,
        metadata_snapshot_digest=snapshot,
        findings=findings,
        **kwargs,
    )


def _ctx(evidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        assessment_graph=evidence,
    )


def test_known_old_is_low_advisory_not_insecurity() -> None:
    old = EVAL_TIME - 800 * 86400
    deps = (
        DependencyReleaseRecord(
            package_id="eco:leftpad",
            ecosystem="pypi",
            installed_version="1.0.0",
            publication_time_unix=old,
            source_snapshot_id="snap-a",
        ),
    )
    evidence, envelope = _run(dependencies=deps)
    consume_envelope(envelope.model_dump(mode="json"))
    record = evidence.staleness[0]
    assert record.status is MetricStatusName.VALUE
    assert record.days == int(m23_staleness_days(EVAL_TIME, old).value or 0)
    assert record.days == 800
    result = DependencyAgeRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW
    assert "does not prove" in result.matches[0].summary
    html = __import__(
        "codestrata.application.evidence.maintainability.projections",
        fromlist=["project_maintainability_html"],
    ).project_maintainability_html(envelope)
    assert "does not prove insecure" in html


def test_known_new_is_not_a_finding() -> None:
    deps = (
        DependencyReleaseRecord(
            package_id="eco:fresh",
            ecosystem="pypi",
            installed_version="2.0.0",
            publication_time_unix=EVAL_TIME - 10 * 86400,
            source_snapshot_id="snap-a",
        ),
    )
    evidence, _ = _run(dependencies=deps)
    assert evidence.staleness[0].days == 10
    assert DependencyAgeRule().evaluate(_ctx(evidence)).status is RuleResultStatus.NOT_MATCHED


def test_unknown_date_is_unknown_age() -> None:
    deps = (
        DependencyReleaseRecord(
            package_id="eco:mystery",
            ecosystem="pypi",
            installed_version="0.1.0",
            publication_time_unix=None,
            source_snapshot_id="snap-a",
        ),
    )
    evidence, _ = _run(dependencies=deps)
    assert evidence.staleness[0].status is MetricStatusName.UNKNOWN
    assert evidence.staleness[0].days is None
    assert evidence.staleness[0].reason == "missing_timestamp"
    assert DependencyAgeRule().evaluate(_ctx(evidence)).status is RuleResultStatus.NOT_MATCHED


def test_future_timestamp_is_unknown() -> None:
    deps = (
        DependencyReleaseRecord(
            package_id="eco:future",
            ecosystem="pypi",
            installed_version="9.0.0",
            publication_time_unix=EVAL_TIME + 86400,
            source_snapshot_id="snap-a",
        ),
    )
    evidence, _ = _run(dependencies=deps)
    assert evidence.staleness[0].status is MetricStatusName.UNKNOWN
    assert evidence.staleness[0].reason == "future_or_invalid_timestamp"


def test_unpinned_evaluation_time_is_unknown() -> None:
    deps = (
        DependencyReleaseRecord(
            package_id="eco:leftpad",
            ecosystem="pypi",
            installed_version="1.0.0",
            publication_time_unix=EVAL_TIME - 800 * 86400,
            source_snapshot_id="snap-a",
        ),
    )
    evidence, _ = _run(dependencies=deps, evaluation_time_unix=None)
    assert evidence.staleness[0].status is MetricStatusName.UNKNOWN
    assert evidence.staleness[0].reason == "unpinned_evaluation_time"


def test_identical_severity_ties_use_evidence_class_then_hotspot_then_id() -> None:
    findings = (
        FindingReferenceInput(
            finding_id="finding.z",
            subject_id="pkg",
            state=FindingLifecycle.ACTIVE,
            evidence_class=EvidenceClass.HIGH,
            effective_severity="medium",
        ),
        FindingReferenceInput(
            finding_id="finding.a",
            subject_id="other",
            state=FindingLifecycle.ACTIVE,
            evidence_class=EvidenceClass.HIGH,
            effective_severity="medium",
        ),
        FindingReferenceInput(
            finding_id="finding.b",
            subject_id="pkg",
            state=FindingLifecycle.ACTIVE,
            evidence_class=EvidenceClass.LOW,
            effective_severity="medium",
        ),
    )
    evidence, _ = _run(dependencies=(), findings=findings)
    order = [item.finding_id for item in evidence.concerns]
    # comparable hotspot (pkg) before incomparable (other) within same class? 
    # finding.z and finding.a are both high/medium; z is comparable, a is not
    # comparable sorts before incomparable, so z then a, then b (low class)
    assert order == ["finding.z", "finding.a", "finding.b"]
    assert evidence.concerns[0].hotspot_comparable is True
    assert evidence.concerns[1].hotspot_comparable is False
    assert EVIDENCE_CLASS_ORDER_V1[0] == "high"
    assert CONCERN_ORDER_VERSION == "concern.order.v1"
    assert EVIDENCE_CLASS_ORDER_VERSION == "evidence_class.order.v1"
    assert "no_weighted_score=true" in evidence.concerns[0].explanation


def test_changed_metadata_snapshot_changes_digest_and_age() -> None:
    old = (
        DependencyReleaseRecord(
            package_id="eco:leftpad",
            ecosystem="pypi",
            installed_version="1.0.0",
            publication_time_unix=EVAL_TIME - 800 * 86400,
            source_snapshot_id="snap-old",
        ),
    )
    new = (
        DependencyReleaseRecord(
            package_id="eco:leftpad",
            ecosystem="pypi",
            installed_version="1.0.0",
            publication_time_unix=EVAL_TIME - 10 * 86400,
            source_snapshot_id="snap-new",
        ),
    )
    first, _ = _run(dependencies=old, snapshot="snap-old")
    second, _ = _run(dependencies=new, snapshot="snap-new")
    assert first.metadata_snapshot_digest != second.metadata_snapshot_digest
    assert first.staleness[0].days != second.staleness[0].days
    assert first.staleness[0].source_snapshot_id == "snap-old"
