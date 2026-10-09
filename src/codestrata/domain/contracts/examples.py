"""Complete, partial, UNKNOWN and no-baseline example envelopes."""

from __future__ import annotations

from collections.abc import Callable

from codestrata.domain.contracts.descriptors import launch_descriptors
from codestrata.domain.contracts.driver_manifest import outcome_driver_manifest_digest
from codestrata.domain.contracts.enums import (
    ContributorRole,
    CoverageState,
    ExtractionStatus,
    FreshnessState,
    HotspotListKind,
    OwnershipScope,
    ResultStatus,
    SubjectKind,
)
from codestrata.domain.contracts.envelope import (
    CanonicalEnvelope,
    CapabilityCoverage,
    CapabilityFreshness,
    ComparisonRecord,
    EnvelopeBody,
    EnvelopeOperational,
    seal_envelope,
)
from codestrata.domain.contracts.facts import (
    EvidenceRecord,
    FactRecord,
    FindingRecord,
    GraphEdgeRecord,
    GraphNodeRecord,
    GraphRecord,
)
from codestrata.domain.contracts.hotspot import (
    ChangeSummary,
    ContributorRecord,
    EngineeringHotspot,
    OwnershipConcentration,
    build_priority_explanation,
    ownership_ratio,
)
from codestrata.domain.contracts.identity_map import (
    canonical_finding_id,
    component_subject_id,
    evidence_id,
    file_subject_id,
    repository_subject_id,
)

REPO_KEY = "example-repo"
SOURCE_REVISION = "abcdef1234567890"
WORKING = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
EVAL_TIME = "2026-09-15T00:00:00Z"
HISTORY_PROFILE = "m24.history.v1"
HISTORY_WINDOW = "180d+latest-1000"


def _ids() -> tuple[str, str, str, str]:
    repo = repository_subject_id(REPO_KEY)
    component = component_subject_id(REPO_KEY, "services/orders")
    file_id = file_subject_id(REPO_KEY, "services/orders/Handler.java")
    return repo, component, file_id, "orders-graph"


def _evidence(kind: str, locator: str, limitation: str | None = None) -> EvidenceRecord:
    eid = evidence_id(kind=kind, working_state_digest=WORKING, locator=locator)
    relative = locator if "/" in locator or locator.endswith(".java") else None
    return EvidenceRecord(
        evidence_id=eid,
        source_kind=kind,
        working_state_digest=WORKING,
        source_revision=SOURCE_REVISION,
        extractor_version="e01.2.example.v1",
        relative_path=relative,
        limitation=limitation,
    )


def _graph(repo: str, component: str, file_id: str) -> GraphRecord:
    return GraphRecord(
        graph_id="graph:example-repo:v1",
        nodes=(
            GraphNodeRecord(node_id=repo, kind="repository", subject_id=repo),
            GraphNodeRecord(node_id=component, kind="component", subject_id=component),
            GraphNodeRecord(node_id=file_id, kind="file", subject_id=file_id),
        ),
        edges=(
            GraphEdgeRecord(
                edge_id="edge:contains:orders:handler",
                source_id=component,
                target_id=file_id,
                kind="contains",
            ),
        ),
    )


def _descriptors() -> tuple[str, ...]:
    return tuple(item.descriptor_id for item in launch_descriptors())


def _hotspot(
    *,
    component: str,
    evidence_ids: tuple[str, ...],
    finding_ids: tuple[str, ...],
    list_kind: HotspotListKind,
    complexity: str | None,
    churn: str | None,
    ranking_value: str | None,
    extra: tuple[ContributorRecord, ...] = (),
) -> EngineeringHotspot:
    contributors = (
        ContributorRecord(
            name="complexity",
            measurement_id="M16",
            measurement_version="v1",
            role=ContributorRole.RANKING,
            value=complexity,
            coverage_reason=None if complexity else "unsupported_syntax",
            evidence_ids=evidence_ids,
        ),
        ContributorRecord(
            name="churn",
            measurement_id="M24",
            measurement_version="v1",
            role=ContributorRole.RANKING,
            value=churn,
            coverage_reason=None if churn else "git_history_missing",
            evidence_ids=evidence_ids,
        ),
        ContributorRecord(
            name="centrality",
            measurement_id="M09",
            measurement_version="v1",
            role=ContributorRole.CONTEXT_ONLY,
            value="0.250000",
            evidence_ids=evidence_ids,
        ),
        *extra,
    )
    explanation = build_priority_explanation(
        formula_version="M22.v1",
        complexity=complexity or "UNKNOWN",
        changed_lines=churn or "UNKNOWN",
        ranking_value=ranking_value or "UNKNOWN",
        subject_id=component,
        history_window=HISTORY_WINDOW,
    )
    return EngineeringHotspot(
        record_id=f"hotspot:{component}",
        subject_id=component,
        input_state_digest=WORKING,
        list_kind=list_kind,
        ranking_value=ranking_value,
        history_profile_id=HISTORY_PROFILE,
        history_window=HISTORY_WINDOW,
        contributors=contributors,
        active_finding_ids=finding_ids,
        evidence_ids=evidence_ids,
        priority_explanation=explanation,
    )


def _ownership(
    repo: str,
    component: str,
    file_id: str,
    *,
    unknown: bool,
) -> tuple[OwnershipConcentration, ...]:
    evidence = evidence_id(kind="git", working_state_digest=WORKING, locator="history")
    if unknown:
        return (
            OwnershipConcentration(
                record_id="own:repo",
                scope=OwnershipScope.REPOSITORY,
                subject_id=repo,
                numerator=None,
                denominator=None,
                serialized_ratio=None,
                history_profile_id=HISTORY_PROFILE,
                evidence_ids=(evidence,),
                status=ResultStatus.UNKNOWN,
                notes="scoped independently; unknown mapping is UNKNOWN not 0%",
            ),
        )
    return (
        OwnershipConcentration(
            record_id="own:repo",
            scope=OwnershipScope.REPOSITORY,
            subject_id=repo,
            numerator=8,
            denominator=10,
            serialized_ratio=ownership_ratio(8, 10),
            history_profile_id=HISTORY_PROFILE,
            evidence_ids=(evidence,),
            status=ResultStatus.PASS,
            notes="repository scope; not an average of file ratios",
        ),
        OwnershipConcentration(
            record_id="own:component",
            scope=OwnershipScope.COMPONENT,
            subject_id=component,
            numerator=3,
            denominator=4,
            serialized_ratio=ownership_ratio(3, 4),
            history_profile_id=HISTORY_PROFILE,
            evidence_ids=(evidence,),
            status=ResultStatus.PASS,
            notes="component scope computed independently",
        ),
        OwnershipConcentration(
            record_id="own:file",
            scope=OwnershipScope.FILE,
            subject_id=file_id,
            numerator=1,
            denominator=1,
            serialized_ratio=ownership_ratio(1, 1),
            history_profile_id=HISTORY_PROFILE,
            evidence_ids=(evidence,),
            status=ResultStatus.PASS,
            notes="file drill-down is not a file-level hotspot rank",
        ),
    )


def _change_summary(
    file_id: str,
    component: str,
    *,
    unknown_boundary: bool,
) -> ChangeSummary:
    if unknown_boundary:
        return ChangeSummary(
            changed_file_ids=(file_id,),
            changed_component_ids=(component,),
            changed_file_count=1,
            changed_component_count=1,
            unmapped_changed_file_count=0,
            mapping_coverage="1.000000",
            mapping_coverage_status=ResultStatus.PASS,
            boundary_spread_status=ResultStatus.UNKNOWN,
            crossed_boundary_status=ResultStatus.UNKNOWN,
            graph_side="candidate",
            cutoff_reason=None,
        )
    return ChangeSummary(
        changed_file_ids=(file_id,),
        changed_component_ids=(component,),
        changed_file_count=1,
        changed_component_count=1,
        unmapped_changed_file_count=0,
        mapping_coverage="1.000000",
        mapping_coverage_status=ResultStatus.PASS,
        boundary_dimension="layers",
        boundary_spread_member_ids=("layer:domain", "layer:app"),
        boundary_spread_count=2,
        boundary_spread_status=ResultStatus.PASS,
        crossed_boundary_count=1,
        crossed_boundary_pairs=("layer:app->layer:domain",),
        crossed_boundary_status=ResultStatus.PASS,
        affected_component_ids=(component,),
        affected_component_count=1,
        affected_test_ids=(),
        affected_test_count=None,
        visited_nodes=3,
        visited_edges=1,
        graph_side="candidate",
        lower_bound=False,
        narrative_only_context=True,
    )


def _coverage(
    capability_id: str,
    *,
    state: CoverageState,
    eligible: int | None,
    evaluated: int | None,
    reason: str | None,
    ratio: str | None,
) -> CapabilityCoverage:
    return CapabilityCoverage(
        capability_id=capability_id,
        capability_version="1.0.0",
        scope="repository",
        applicability="applicable",
        execution_state=state,
        evaluated_count=evaluated,
        eligible_count=eligible,
        coverage_ratio=ratio,
        coverage_reason=reason,
        evidence_ids=(),
        limitations=() if reason is None else (reason,),
    )


def _fresh(
    capability_id: str,
    state: FreshnessState,
    reason: str,
    explanation: str,
    **extra: object,
) -> CapabilityFreshness:
    payload = {
        "capability_id": capability_id,
        "state": state,
        "reason_code": reason,
        "explanation": explanation,
        "evaluation_time": EVAL_TIME,
        **extra,
    }
    return CapabilityFreshness.model_validate(payload)


def _finding(rule_id: str, subject_id: str, evidence_ids: tuple[str, ...]) -> FindingRecord:
    fid = canonical_finding_id(rule_id, (subject_id,), occurrence_key="symbol:Handler.handle")
    return FindingRecord(
        finding_id=fid,
        rule_id=rule_id,
        subject_id=subject_id,
        result=ResultStatus.FAIL.value,
        default_severity="high",
        effective_severity="high",
        confidence="high",
        evidence_ids=evidence_ids,
        occurrence_key="symbol:Handler.handle",
        override_provenance=None,
    )


def example_complete() -> CanonicalEnvelope:
    repo, component, file_id, _ = _ids()
    ev_src = _evidence("source", "services/orders/Handler.java")
    ev_git = _evidence("git", "history")
    finding = _finding("architecture.dependency-cycle", component, (ev_src.evidence_id,))
    hotspot = _hotspot(
        component=component,
        evidence_ids=(ev_src.evidence_id, ev_git.evidence_id),
        finding_ids=(finding.finding_id,),
        list_kind=HotspotListKind.COMPLETE_COMPARABLE,
        complexity="12",
        churn="40",
        ranking_value="480",
    )
    body = EnvelopeBody(
        repository_subject_id=repo,
        source_revision=SOURCE_REVISION,
        working_state_digest=WORKING,
        evaluation_time=EVAL_TIME,
        descriptor_ids=_descriptors(),
        outcome_driver_manifest_digest=outcome_driver_manifest_digest(),
        facts=(
            FactRecord(
                fact_id="fact:m16:orders",
                measurement_id="M16",
                subject_kind=SubjectKind.COMPONENT,
                subject_id=component,
                source_kind="complexity",
                value=12,
                unit="decisions",
                evidence_ids=(ev_src.evidence_id,),
                extraction_status=ExtractionStatus.COMPLETE,
            ),
        ),
        evidence=(ev_src, ev_git),
        graph=_graph(repo, component, file_id),
        findings=(finding,),
        hotspots=(hotspot,),
        ownership=_ownership(repo, component, file_id, unknown=False),
        change_summary=_change_summary(file_id, component, unknown_boundary=False),
        coverage=(
            _coverage(
                "quality.m22.hotspots",
                state=CoverageState.COMPLETE,
                eligible=1,
                evaluated=1,
                reason=None,
                ratio="1.000000",
            ),
        ),
        freshness=(
            _fresh(
                "quality.m22.hotspots",
                FreshnessState.FRESH,
                "not_time_sensitive",
                "Complexity is bound to the working-state digest.",
                source_digest=WORKING,
            ),
            _fresh(
                "security.m13.vulnerabilities",
                FreshnessState.FRESH,
                "feed_fresh",
                "Pinned OSV snapshot is within seven days of evaluation_time.",
                feed_provider="osv.dev",
                feed_digest="feeddigest0001",
                max_age_days=7,
            ),
        ),
        comparison=ComparisonRecord(
            has_baseline=True,
            movement="stable",
            reason_code="compatible",
            explanation="Compatible baseline present; movement is named, not a score.",
        ),
        limitations=(),
    )
    return seal_envelope(
        body,
        EnvelopeOperational(run_id="run-example-complete", generated_at="2026-09-19T08:00:00Z"),
    )


def example_partial() -> CanonicalEnvelope:
    repo, component, file_id, _ = _ids()
    ev_src = _evidence("source", "services/orders/Handler.java")
    ev_git = _evidence("git", "history", limitation="partial history window")
    hotspot = _hotspot(
        component=component,
        evidence_ids=(ev_src.evidence_id, ev_git.evidence_id),
        finding_ids=(),
        list_kind=HotspotListKind.COMPLETE_COMPARABLE,
        complexity="12",
        churn="40",
        ranking_value="480",
        extra=(
            ContributorRecord(
                name="ownership",
                measurement_id="M25",
                measurement_version="v1",
                role=ContributorRole.CONTEXT_ONLY,
                value=None,
                coverage_reason="unknown_ownership_mapping",
                evidence_ids=(ev_git.evidence_id,),
            ),
        ),
    )
    body = EnvelopeBody(
        repository_subject_id=repo,
        source_revision=SOURCE_REVISION,
        working_state_digest=WORKING,
        evaluation_time=EVAL_TIME,
        descriptor_ids=_descriptors(),
        outcome_driver_manifest_digest=outcome_driver_manifest_digest(),
        facts=(),
        evidence=(ev_src, ev_git),
        graph=_graph(repo, component, file_id),
        findings=(),
        hotspots=(hotspot,),
        ownership=_ownership(repo, component, file_id, unknown=False),
        change_summary=_change_summary(file_id, component, unknown_boundary=False),
        coverage=(
            _coverage(
                "quality.m22.hotspots",
                state=CoverageState.PARTIAL,
                eligible=2,
                evaluated=1,
                reason="partial_required_inputs",
                ratio="0.500000",
            ),
        ),
        freshness=(
            _fresh(
                "maintainability.m24.churn",
                FreshnessState.UNKNOWN,
                "git_history_shallow",
                "Requested window exceeded shallow clone; recency is not checkout age.",
                git_head=SOURCE_REVISION,
                git_window=HISTORY_WINDOW,
            ),
        ),
        comparison=ComparisonRecord(
            has_baseline=True,
            movement="insufficient",
            reason_code="partial_coverage",
            explanation="Known observations retained; missing context does not invent zeros.",
        ),
        limitations=("partial_git_history",),
    )
    return seal_envelope(body, EnvelopeOperational(run_id="run-example-partial"))


def example_unknown() -> CanonicalEnvelope:
    repo, component, file_id, _ = _ids()
    ev_src = _evidence(
        "source",
        "services/orders/Handler.java",
        limitation="js complexity unsupported",
    )
    hotspot = _hotspot(
        component=component,
        evidence_ids=(ev_src.evidence_id,),
        finding_ids=(),
        list_kind=HotspotListKind.PARTIAL_OR_UNKNOWN,
        complexity=None,
        churn=None,
        ranking_value=None,
    )
    body = EnvelopeBody(
        repository_subject_id=repo,
        source_revision=SOURCE_REVISION,
        working_state_digest=WORKING,
        evaluation_time=EVAL_TIME,
        descriptor_ids=_descriptors(),
        outcome_driver_manifest_digest=outcome_driver_manifest_digest(),
        facts=(),
        evidence=(ev_src,),
        graph=_graph(repo, component, file_id),
        findings=(),
        hotspots=(hotspot,),
        ownership=_ownership(repo, component, file_id, unknown=True),
        change_summary=_change_summary(file_id, component, unknown_boundary=True),
        coverage=(
            _coverage(
                "quality.m22.hotspots",
                state=CoverageState.UNKNOWN,
                eligible=None,
                evaluated=None,
                reason="unknown_denominator",
                ratio=None,
            ),
        ),
        freshness=(
            _fresh(
                "security.m13.vulnerabilities",
                FreshnessState.UNKNOWN,
                "feed_missing",
                "Missing feed cannot prove clean.",
            ),
        ),
        comparison=ComparisonRecord(
            has_baseline=True,
            movement="insufficient",
            reason_code="unknown_denominator",
            explanation="Unknown eligible count is UNKNOWN, never 0% or 100%.",
        ),
        limitations=("js_ts_complexity_unsupported", "feed_missing"),
    )
    return seal_envelope(body, EnvelopeOperational(run_id="run-example-unknown"))


def example_no_baseline() -> CanonicalEnvelope:
    complete = example_complete()
    body = complete.body.model_copy(
        update={
            "comparison": ComparisonRecord(
                has_baseline=False,
                movement="not_applicable",
                reason_code="no_baseline",
                explanation="First run; delta and outcome movement unavailable.",
            ),
            "limitations": ("no_baseline",),
        }
    )
    return seal_envelope(body, EnvelopeOperational(run_id="run-example-no-baseline"))


EXAMPLE_BUILDERS: dict[str, Callable[[], CanonicalEnvelope]] = {
    "complete": example_complete,
    "partial": example_partial,
    "unknown": example_unknown,
    "no-baseline": example_no_baseline,
}
