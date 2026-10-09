"""M22 fixtures: churn-weighted complexity Engineering Hotspot records."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.maintainability.capability import (
    HISTORY_PROFILE_V1,
    HOTSPOT_FORMULA_VERSION,
)
from codestrata.application.evidence.maintainability.consumer import consume_envelope
from codestrata.application.evidence.maintainability.models import (
    ComponentSpec,
    CoverageScope,
    EvidenceClass,
    FileChurnRecord,
    FindingLifecycle,
    FindingReferenceInput,
    HistoryWindow,
    OwnershipReference,
)
from codestrata.application.evidence.maintainability.service import MaintainabilityEvidenceService
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
from codestrata.application.rules.technical_debt.yaml_catalog import quality_catalog_digests
from codestrata.application.rules.technical_debt.yaml_maintainability import HotspotRule
from codestrata.domain.contracts.enums import ContributorRole, HotspotListKind
from codestrata.domain.contracts.formulas import m22_hotspot_value
from codestrata.domain.contracts.hotspot import build_priority_explanation
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus, RuleSeverity


def _span(path: str) -> SourceSpan:
    return SourceSpan(path=path, line_start=1, line_end=8)


def _fn(
    path: str,
    name: str,
    cyclomatic: int,
    *,
    status: FunctionStatus = FunctionStatus.MEASURED,
) -> FunctionRecord:
    measured = status is FunctionStatus.MEASURED
    return FunctionRecord(
        function_id=f"{path}:{name}",
        language="python",
        path=path,
        name=name,
        qualified_name=name,
        span=_span(path),
        role=FileRole.SOURCE,
        status=status,
        cyclomatic=cyclomatic if measured else None,
        branch_count=(cyclomatic - 1) if measured else None,
        nloc=8 if measured else None,
        max_nesting_depth=1 if measured else None,
        cyclomatic_version="cyclomatic.v1",
        nesting_version="nesting.v1",
        size_version="nloc.v1",
        branch_map_language="python",
        unknown_reason=None if measured else "unparsed_function",
    )


def _quality(*functions: FunctionRecord) -> QualityEvidence:
    return QualityEvidence(
        repository_id="fixture",
        functions=functions,
        clone=CloneMetric(
            status=MetricStatusName.NOT_APPLICABLE,
            full_scope_status=QualityCoverage.NOT_APPLICABLE,
            reason="unused_in_m22",
            normalization_version="token.normalize.v1",
            formula_version="clone.v1",
            min_tokens=50,
            min_lines=5,
        ),
    )


def _history(
    files: tuple[FileChurnRecord, ...],
    *,
    coverage: CoverageScope = CoverageScope.COMPLETE,
    reason: str = "complete",
    rename_pairs: tuple[tuple[str, str], ...] = (),
) -> HistoryWindow:
    return HistoryWindow(
        profile_id=HISTORY_PROFILE_V1,
        window="180d_then_latest_1000",
        head_sha="abc123def",
        coverage=coverage,
        coverage_reason=reason,
        evaluation_time_unix=1_700_000_000,
        included_commit_count=4,
        file_churn=files,
        rename_pairs=rename_pairs,
    )


def _run(
    quality: QualityEvidence,
    components: tuple[ComponentSpec, ...],
    history: HistoryWindow | None,
    **kwargs: object,
):
    return MaintainabilityEvidenceService().collect(
        repository_id="fixture",
        quality=quality,
        components=components,
        history=history,
        catalog_digest=quality_catalog_digests()["maintainability.hotspot"],
        **kwargs,
    )


def _ctx(evidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        assessment_graph=evidence,
    )


def test_same_complexity_different_churn_orders_by_churn() -> None:
    quality = _quality(
        _fn("alpha/a.py", "one", 10),
        _fn("beta/b.py", "two", 10),
    )
    history = _history(
        (
            FileChurnRecord(path="alpha/a.py", changed_lines=3),
            FileChurnRecord(path="beta/b.py", changed_lines=9),
        )
    )
    components = (
        ComponentSpec(component_id="alpha", file_paths=("alpha/a.py",)),
        ComponentSpec(component_id="beta", file_paths=("beta/b.py",)),
    )
    evidence, envelope = _run(quality, components, history)
    consume_envelope(envelope.model_dump(mode="json"))
    assert [item.subject_id for item in evidence.complete_hotspots] == ["beta", "alpha"]
    assert evidence.complete_hotspots[0].ranking_value == str(m22_hotspot_value(10, 9))
    assert evidence.complete_hotspots[1].ranking_value == str(m22_hotspot_value(10, 3))
    assert evidence.partial_hotspots == ()


def test_zero_churn_is_complete_rank_zero_not_unknown() -> None:
    quality = _quality(_fn("alpha/a.py", "one", 12))
    history = _history((FileChurnRecord(path="alpha/a.py", changed_lines=0),))
    components = (ComponentSpec(component_id="alpha", file_paths=("alpha/a.py",)),)
    evidence, _ = _run(quality, components, history)
    record = evidence.complete_hotspots[0]
    assert record.ranking_value == "0"
    assert record.list_kind is HotspotListKind.COMPLETE_COMPARABLE
    result = HotspotRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_missing_history_is_unknown_and_retains_static_functions() -> None:
    quality = _quality(_fn("alpha/a.py", "one", 15))
    components = (ComponentSpec(component_id="alpha", file_paths=("alpha/a.py",)),)
    evidence, envelope = _run(quality, components, None)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.complete_hotspots == ()
    assert evidence.partial_hotspots[0].ranking_value is None
    assert evidence.partial_hotspots[0].list_kind is HotspotListKind.PARTIAL_OR_UNKNOWN
    assert "alpha/a.py:one" in evidence.static_function_ids
    html = __import__(
        "codestrata.application.evidence.maintainability.projections",
        fromlist=["project_maintainability_html"],
    ).project_maintainability_html(envelope)
    assert "alpha/a.py:one" in html
    assert "UNRANKED" in html


def test_stable_ties_break_by_component_id() -> None:
    quality = _quality(
        _fn("alpha/a.py", "one", 10),
        _fn("beta/b.py", "two", 10),
    )
    history = _history(
        (
            FileChurnRecord(path="alpha/a.py", changed_lines=3),
            FileChurnRecord(path="beta/b.py", changed_lines=3),
        )
    )
    components = (
        ComponentSpec(component_id="beta", file_paths=("beta/b.py",)),
        ComponentSpec(component_id="alpha", file_paths=("alpha/a.py",)),
    )
    evidence, _ = _run(quality, components, history)
    ranked = evidence.complete_hotspots
    assert [item.subject_id for item in ranked] == ["alpha", "beta"]
    assert ranked[0].ranking_value == ranked[1].ranking_value


def test_rename_mapping_attributes_churn_to_current_component() -> None:
    quality = _quality(_fn("lib/new.py", "fn", 6))
    history = _history(
        (FileChurnRecord(path="lib/new.py", changed_lines=4, renamed_from="lib/old.py"),),
        rename_pairs=(("lib/old.py", "lib/new.py"),),
    )
    components = (ComponentSpec(component_id="lib", file_paths=("lib/new.py",)),)
    evidence, _ = _run(quality, components, history)
    record = evidence.complete_hotspots[0]
    churn = next(c for c in record.contributors if c.name == "churn")
    assert churn.value == "4"
    assert record.ranking_value == str(m22_hotspot_value(6, 4))


def test_complete_unified_record_and_priority_explanation() -> None:
    quality = _quality(_fn("svc/a.py", "run", 8))
    history = _history((FileChurnRecord(path="svc/a.py", changed_lines=5),))
    components = (ComponentSpec(component_id="svc", file_paths=("svc/a.py",)),)
    findings = (
        FindingReferenceInput(
            finding_id="finding.quality.1",
            subject_id="svc",
            state=FindingLifecycle.ACTIVE,
            evidence_class=EvidenceClass.HIGH,
            effective_severity="medium",
        ),
    )
    evidence, envelope = _run(
        quality,
        components,
        history,
        centrality={"svc": "0.250000"},
        reach={"svc": "3"},
        ownership={
            "svc": OwnershipReference(
                scope="component",
                subject_id="svc",
                serialized_ratio="0.700000",
                status="value",
                history_profile_id=HISTORY_PROFILE_V1,
                notes="largest_contributor_share",
            )
        },
        findings=findings,
    )
    consume_envelope(envelope.model_dump(mode="json"))
    record = evidence.complete_hotspots[0]
    assert record.schema_name == "codestrata.engineering-hotspot.v1"
    assert record.record_id.startswith("m22:svc:")
    ranking = [c.name for c in record.contributors if c.role is ContributorRole.RANKING]
    context = [c.name for c in record.contributors if c.role is ContributorRole.CONTEXT_ONLY]
    assert ranking == ["complexity", "churn"]
    assert context == ["centrality", "reach", "ownership", "active_findings"]
    assert record.active_finding_ids == ("finding.quality.1",)
    expected = build_priority_explanation(
        formula_version=HOTSPOT_FORMULA_VERSION,
        complexity="8",
        changed_lines="5",
        ranking_value=str(m22_hotspot_value(8, 5)),
        subject_id="svc",
        history_window="180d_then_latest_1000",
    )
    assert record.priority_explanation == expected
    result = HotspotRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL
    assert "runtime failure probability" in result.matches[0].summary


def test_equal_rank_different_context_does_not_change_order() -> None:
    quality = _quality(
        _fn("alpha/a.py", "one", 10),
        _fn("beta/b.py", "two", 10),
    )
    history = _history(
        (
            FileChurnRecord(path="alpha/a.py", changed_lines=4),
            FileChurnRecord(path="beta/b.py", changed_lines=4),
        )
    )
    components = (
        ComponentSpec(component_id="alpha", file_paths=("alpha/a.py",)),
        ComponentSpec(component_id="beta", file_paths=("beta/b.py",)),
    )
    first, _ = _run(
        quality,
        components,
        history,
        centrality={"alpha": "0.900000", "beta": "0.100000"},
        ownership={
            "beta": OwnershipReference(
                scope="component",
                subject_id="beta",
                serialized_ratio="0.990000",
                status="value",
                history_profile_id=HISTORY_PROFILE_V1,
            )
        },
        findings=(
            FindingReferenceInput(
                finding_id="finding.beta",
                subject_id="beta",
                state=FindingLifecycle.ACTIVE,
            ),
        ),
    )
    second, _ = _run(quality, components, history)
    assert [item.subject_id for item in first.complete_hotspots] == ["alpha", "beta"]
    assert [item.ranking_value for item in first.complete_hotspots] == [
        item.ranking_value for item in second.complete_hotspots
    ]
    assert [item.record_id for item in first.complete_hotspots] == [
        item.record_id for item in second.complete_hotspots
    ]
    assert first.input_state_digest == second.input_state_digest


def test_missing_context_keeps_known_rank() -> None:
    quality = _quality(_fn("svc/a.py", "run", 7))
    history = _history((FileChurnRecord(path="svc/a.py", changed_lines=2),))
    components = (ComponentSpec(component_id="svc", file_paths=("svc/a.py",)),)
    evidence, _ = _run(quality, components, history)
    record = evidence.complete_hotspots[0]
    assert record.ranking_value == str(m22_hotspot_value(7, 2))
    centrality = next(c for c in record.contributors if c.name == "centrality")
    assert centrality.value is None
    assert centrality.coverage_reason == "unsupported_or_missing"
    assert centrality.role is ContributorRole.CONTEXT_ONLY


def test_partial_complexity_is_unranked() -> None:
    quality = _quality(
        _fn("svc/a.py", "ok", 4),
        _fn("svc/b.py", "bad", 1, status=FunctionStatus.UNKNOWN),
    )
    history = _history(
        (
            FileChurnRecord(path="svc/a.py", changed_lines=3),
            FileChurnRecord(path="svc/b.py", changed_lines=3),
        )
    )
    components = (ComponentSpec(component_id="svc", file_paths=("svc/a.py", "svc/b.py")),)
    evidence, _ = _run(quality, components, history)
    assert evidence.complete_hotspots == ()
    record = evidence.partial_hotspots[0]
    complexity = next(c for c in record.contributors if c.name == "complexity")
    assert complexity.value == "4"
    assert record.ranking_value is None
    assert "svc/a.py:ok" in evidence.static_function_ids


def test_dangling_and_resolved_findings_are_rejected() -> None:
    quality = _quality(_fn("svc/a.py", "run", 5))
    history = _history((FileChurnRecord(path="svc/a.py", changed_lines=2),))
    components = (ComponentSpec(component_id="svc", file_paths=("svc/a.py",)),)
    evidence, _ = _run(
        quality,
        components,
        history,
        findings=(
            FindingReferenceInput(
                finding_id="finding.dangling",
                subject_id="svc",
                state=FindingLifecycle.ACTIVE,
                present_in_state=False,
            ),
            FindingReferenceInput(
                finding_id="finding.resolved",
                subject_id="svc",
                state=FindingLifecycle.RESOLVED,
            ),
            FindingReferenceInput(
                finding_id="finding.suppressed",
                subject_id="svc",
                state=FindingLifecycle.SUPPRESSED,
            ),
        ),
    )
    reasons = {item.finding_id: item.reason for item in evidence.finding_rejections}
    assert reasons["finding.dangling"] == "dangling_finding_reference"
    assert reasons["finding.resolved"] == "wrong_state_resolved"
    assert evidence.complete_hotspots[0].active_finding_ids == ("finding.suppressed",)


def test_assess_seal_reuses_collect_hotspots_records(tmp_path: Path) -> None:
    """R2-P02 attaches existing M22 records; it does not add a formula."""

    from datetime import UTC, datetime
    from shutil import copytree

    from codestrata.application.assessment.canonical_records import (
        CANONICAL_HOTSPOTS_KEY,
        seal_assess_canonical_records,
    )
    from codestrata.models.analysis_result import AnalysisResult
    from codestrata.models.repository import Repository
    from tests.application.incremental.git_repo_helpers import commit_all, init_repo

    examples = Path(__file__).resolve().parents[4] / "examples" / "journeys" / "complete-js"
    repo = tmp_path / "complete-js"
    copytree(examples, repo)
    init_repo(repo)
    commit_all(repo, "pin")
    sealed = seal_assess_canonical_records(
        AnalysisResult(repository=Repository(name=repo.name, path=repo, files=["src/app.js"])),
        repository_root=repo,
        evaluation_time=datetime(2026, 9, 27, tzinfo=UTC),
    )
    hotspot = sealed.metadata[CANONICAL_HOTSPOTS_KEY][0]
    assert hotspot["ranking_value"] == "12"
    assert HOTSPOT_FORMULA_VERSION in hotspot["priority_explanation"]


def test_deterministic_repeat_stable_ids() -> None:
    quality = _quality(_fn("svc/a.py", "run", 9))
    history = _history((FileChurnRecord(path="svc/a.py", changed_lines=6),))
    components = (ComponentSpec(component_id="svc", file_paths=("svc/a.py",)),)
    first, envelope_a = _run(quality, components, history)
    second, envelope_b = _run(quality, components, history)
    third, envelope_c = _run(quality, components, history)
    assert envelope_a.body_digest == envelope_b.body_digest == envelope_c.body_digest
    assert first.complete_hotspots[0].record_id == second.complete_hotspots[0].record_id
    assert first.input_state_digest == third.input_state_digest
