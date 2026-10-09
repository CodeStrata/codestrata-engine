"""Join M16 complexity with pinned M24 history. Do not extract Git or graphs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from codestrata.application.evidence.maintainability.capability import (
    COMPLEXITY_MEASUREMENT_VERSION,
    CONCERN_ORDER_VERSION,
    EVIDENCE_CLASS_ORDER_VERSION,
    HISTORY_PROFILE_V1,
    HOTSPOT_FORMULA_VERSION,
    STALENESS_FORMULA_VERSION,
)
from codestrata.application.evidence.maintainability.models import (
    ComponentSpec,
    ConcernRecord,
    CoverageScope,
    DependencyReleaseRecord,
    EvidenceClass,
    FindingLifecycle,
    FindingReferenceInput,
    FindingRejection,
    HistoryWindow,
    MaintainabilityEvidence,
    MaintainabilityThresholds,
    MetricStatusName,
    OwnershipReference,
    StalenessRecord,
)
from codestrata.application.evidence.quality.models import (
    FunctionRecord,
    FunctionStatus,
    QualityEvidence,
)
from codestrata.domain.contracts.enums import ContributorRole, HotspotListKind
from codestrata.domain.contracts.formulas import m22_hotspot_value, m23_staleness_days
from codestrata.domain.contracts.hotspot import (
    ContributorRecord,
    EngineeringHotspot,
    build_priority_explanation,
    hotspot_rank_key,
)

# E01.1 / M23: higher evidence class sorts first. Incomparable hotspots follow.
EVIDENCE_CLASS_ORDER_V1: tuple[str, ...] = (
    EvidenceClass.HIGH.value,
    EvidenceClass.MEDIUM.value,
    EvidenceClass.LOW.value,
    EvidenceClass.UNSUPPORTED.value,
    EvidenceClass.UNKNOWN.value,
)
_SEVERITY_ORDER: tuple[str, ...] = (
    "critical",
    "high",
    "medium",
    "low",
    "informational",
)
_RANKING_CONCERN_INPUTS: tuple[str, ...] = (
    "effective_severity",
    "evidence_class",
    "comparable_hotspot",
    "finding_id",
)
_CONTEXT_CONCERN: tuple[str, ...] = (
    "centrality",
    "reach",
    "ownership",
    "temporal_co_change",
)


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(payload: object) -> str:
    return hashlib.sha256(_stable_dumps(payload).encode("utf-8")).hexdigest()


def _path_aliases(history: HistoryWindow | None) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = {}
    if history is None:
        return aliases
    for old, new in history.rename_pairs:
        aliases.setdefault(old, set()).update({old, new})
        aliases.setdefault(new, set()).update({old, new})
    for item in history.file_churn:
        if item.renamed_from:
            aliases.setdefault(item.path, set()).update({item.path, item.renamed_from})
            aliases.setdefault(item.renamed_from, set()).update(
                {item.path, item.renamed_from}
            )
    return aliases


def _expand_paths(
    paths: Sequence[str], aliases: Mapping[str, set[str]]
) -> frozenset[str]:
    expanded: set[str] = set(paths)
    for path in paths:
        expanded.update(aliases.get(path, ()))
    return frozenset(expanded)


def _complexity_for_component(
    functions: Sequence[FunctionRecord],
    paths: frozenset[str],
) -> tuple[int | None, bool, str]:
    if not paths:
        return None, False, "missing_structure"
    mapped = [item for item in functions if item.path in paths]
    measured = [
        item
        for item in mapped
        if item.status is FunctionStatus.MEASURED and item.cyclomatic is not None
    ]
    unknown = [
        item
        for item in mapped
        if item.status is FunctionStatus.UNKNOWN or item.cyclomatic is None
    ]
    observed = sum(int(item.cyclomatic or 0) for item in measured)
    if unknown:
        return (observed if measured else None, False, "partial_complexity")
    return observed, True, "complete"


def _churn_for_component(
    history: HistoryWindow | None,
    paths: frozenset[str],
) -> tuple[int | None, bool, str]:
    if history is None or history.coverage is CoverageScope.MISSING:
        return None, False, "missing_history"
    if history.coverage is CoverageScope.UNKNOWN:
        return None, False, history.coverage_reason or "unknown_history"
    lines = 0
    unknown_lines = False
    known_lines = False
    for item in history.file_churn:
        aliases = {item.path}
        if item.renamed_from:
            aliases.add(item.renamed_from)
        if not aliases.intersection(paths):
            continue
        if item.changed_lines is None:
            unknown_lines = True
            continue
        known_lines = True
        lines += item.changed_lines
    if history.coverage is CoverageScope.PARTIAL:
        return lines, False, history.coverage_reason or "partial_history"
    if unknown_lines:
        return (lines if known_lines else None, False, "binary_or_unknown_churn")
    return lines, True, "complete"


def _context_contributor(
    *,
    name: str,
    measurement_id: str,
    measurement_version: str,
    value: str | None,
    coverage_reason: str | None,
    evidence_ids: tuple[str, ...] = (),
) -> ContributorRecord:
    return ContributorRecord(
        name=name,
        measurement_id=measurement_id,
        measurement_version=measurement_version,
        role=ContributorRole.CONTEXT_ONLY,
        value=value,
        coverage_reason=coverage_reason,
        evidence_ids=evidence_ids,
    )


def _build_contributors(
    *,
    complexity: int | None,
    complexity_complete: bool,
    complexity_reason: str,
    churn: int | None,
    churn_complete: bool,
    churn_reason: str,
    centrality: str | None,
    reach: str | None,
    ownership: OwnershipReference | None,
    active_finding_ids: Sequence[str],
) -> tuple[ContributorRecord, ...]:
    ranking = (
        ContributorRecord(
            name="complexity",
            measurement_id="M16",
            measurement_version=COMPLEXITY_MEASUREMENT_VERSION,
            role=ContributorRole.RANKING,
            value=None if complexity is None else str(complexity),
            coverage_reason=None if complexity_complete else complexity_reason,
            evidence_ids=("m16.function",),
        ),
        ContributorRecord(
            name="churn",
            measurement_id="M24",
            measurement_version=HISTORY_PROFILE_V1,
            role=ContributorRole.RANKING,
            value=None if churn is None else str(churn),
            coverage_reason=None if churn_complete else churn_reason,
            evidence_ids=("m24.file_churn",),
        ),
    )
    ownership_value = None if ownership is None else ownership.serialized_ratio
    ownership_reason = (
        "unsupported_or_missing"
        if ownership is None
        else (ownership.notes or ownership.status)
    )
    context = (
        _context_contributor(
            name="centrality",
            measurement_id="M09",
            measurement_version="v1",
            value=centrality,
            coverage_reason=None if centrality is not None else "unsupported_or_missing",
        ),
        _context_contributor(
            name="reach",
            measurement_id="architecture.reach",
            measurement_version="v1",
            value=reach,
            coverage_reason=None if reach is not None else "unsupported_or_missing",
        ),
        _context_contributor(
            name="ownership",
            measurement_id="M25",
            measurement_version="v1",
            value=ownership_value,
            coverage_reason=ownership_reason,
            evidence_ids=("m25.ownership",) if ownership is not None else (),
        ),
        _context_contributor(
            name="active_findings",
            measurement_id="findings.active",
            measurement_version="v1",
            value=str(len(active_finding_ids)) if active_finding_ids else None,
            coverage_reason=None if active_finding_ids else "none_or_unlinked",
            evidence_ids=tuple(active_finding_ids),
        ),
    )
    return ranking + context


def _link_findings(
    *,
    subject_id: str,
    findings: Sequence[FindingReferenceInput],
) -> tuple[tuple[str, ...], tuple[FindingRejection, ...]]:
    linked: list[str] = []
    rejections: list[FindingRejection] = []
    for item in findings:
        if item.subject_id != subject_id:
            continue
        if not item.present_in_state:
            rejections.append(
                FindingRejection(
                    finding_id=item.finding_id,
                    subject_id=subject_id,
                    reason="dangling_finding_reference",
                )
            )
            continue
        if item.state is FindingLifecycle.RESOLVED:
            rejections.append(
                FindingRejection(
                    finding_id=item.finding_id,
                    subject_id=subject_id,
                    reason="wrong_state_resolved",
                )
            )
            continue
        linked.append(item.finding_id)
    return tuple(sorted(set(linked))), tuple(rejections)


def _hotspot_record(
    *,
    subject_id: str,
    input_state_digest: str,
    history: HistoryWindow | None,
    complexity: int | None,
    complexity_complete: bool,
    complexity_reason: str,
    churn: int | None,
    churn_complete: bool,
    churn_reason: str,
    centrality: str | None,
    reach: str | None,
    ownership: OwnershipReference | None,
    active_finding_ids: Sequence[str],
) -> EngineeringHotspot:
    complete = complexity_complete and churn_complete
    ranking_value: str | None = None
    if complete:
        ranking_value = str(m22_hotspot_value(int(complexity or 0), int(churn or 0)))
    window = history.window if history is not None else "missing"
    profile = history.profile_id if history is not None else "missing"
    complexity_text = "UNKNOWN" if complexity is None else str(complexity)
    churn_text = "UNKNOWN" if churn is None else str(churn)
    explanation = build_priority_explanation(
        formula_version=HOTSPOT_FORMULA_VERSION,
        complexity=complexity_text,
        changed_lines=churn_text,
        ranking_value=ranking_value or "unranked",
        subject_id=subject_id,
        history_window=window,
    )
    record_id = f"m22:{subject_id}:{input_state_digest[:16]}"
    return EngineeringHotspot(
        record_id=record_id,
        subject_id=subject_id,
        input_state_digest=input_state_digest,
        list_kind=(
            HotspotListKind.COMPLETE_COMPARABLE
            if complete
            else HotspotListKind.PARTIAL_OR_UNKNOWN
        ),
        ranking_value=ranking_value,
        history_profile_id=profile,
        history_window=window,
        contributors=_build_contributors(
            complexity=complexity,
            complexity_complete=complexity_complete,
            complexity_reason=complexity_reason,
            churn=churn,
            churn_complete=churn_complete,
            churn_reason=churn_reason,
            centrality=centrality,
            reach=reach,
            ownership=ownership,
            active_finding_ids=active_finding_ids,
        ),
        active_finding_ids=tuple(active_finding_ids),
        evidence_ids=("m16.function", "m24.file_churn", "component.mapping"),
        priority_explanation=explanation,
        opaque_score=False,
    )


def _ranking_digest(
    *,
    history: HistoryWindow | None,
    rows: Sequence[tuple[str, int | None, int | None, bool]],
) -> str:
    payload = {
        "formula_version": HOTSPOT_FORMULA_VERSION,
        "history_profile_id": None if history is None else history.profile_id,
        "history_window": None if history is None else history.window,
        "head_sha": None if history is None else history.head_sha,
        "components": [
            {
                "subject_id": subject_id,
                "complexity": complexity,
                "churn": churn,
                "complete": complete,
            }
            for subject_id, complexity, churn, complete in rows
        ],
    }
    return _digest(payload)


def collect_hotspots(
    *,
    quality: QualityEvidence,
    history: HistoryWindow | None,
    components: Sequence[ComponentSpec],
    centrality: Mapping[str, str] | None = None,
    reach: Mapping[str, str] | None = None,
    ownership: Mapping[str, OwnershipReference] | None = None,
    findings: Sequence[FindingReferenceInput] = (),
) -> tuple[
    tuple[EngineeringHotspot, ...],
    tuple[EngineeringHotspot, ...],
    str,
    tuple[FindingRejection, ...],
    tuple[str, ...],
]:
    aliases = _path_aliases(history)
    centrality = centrality or {}
    reach = reach or {}
    ownership = ownership or {}
    prepared: list[tuple[str, int | None, bool, str, int | None, bool, str, frozenset[str]]] = []
    for spec in sorted(components, key=lambda item: item.component_id):
        paths = _expand_paths(spec.file_paths, aliases)
        complexity, complexity_ok, complexity_reason = _complexity_for_component(
            quality.functions, paths
        )
        churn, churn_ok, churn_reason = _churn_for_component(history, paths)
        prepared.append(
            (
                spec.component_id,
                complexity,
                complexity_ok,
                complexity_reason,
                churn,
                churn_ok,
                churn_reason,
                paths,
            )
        )
    digest_rows = [
        (subject_id, complexity, churn, complexity_ok and churn_ok)
        for subject_id, complexity, complexity_ok, _cr, churn, churn_ok, _hr, _paths in prepared
    ]
    input_state_digest = _ranking_digest(history=history, rows=digest_rows)
    complete: list[EngineeringHotspot] = []
    partial: list[EngineeringHotspot] = []
    rejections: list[FindingRejection] = []
    for (
        subject_id,
        complexity,
        complexity_ok,
        complexity_reason,
        churn,
        churn_ok,
        churn_reason,
        _paths,
    ) in prepared:
        linked, rejected = _link_findings(subject_id=subject_id, findings=findings)
        rejections.extend(rejected)
        record = _hotspot_record(
            subject_id=subject_id,
            input_state_digest=input_state_digest,
            history=history,
            complexity=complexity,
            complexity_complete=complexity_ok,
            complexity_reason=complexity_reason,
            churn=churn,
            churn_complete=churn_ok,
            churn_reason=churn_reason,
            centrality=centrality.get(subject_id),
            reach=reach.get(subject_id),
            ownership=ownership.get(subject_id),
            active_finding_ids=linked,
        )
        if record.list_kind is HotspotListKind.COMPLETE_COMPARABLE:
            complete.append(record)
        else:
            partial.append(record)
    complete.sort(key=hotspot_rank_key)
    partial.sort(key=hotspot_rank_key)
    static_ids = tuple(
        sorted(
            item.function_id
            for item in quality.functions
            if item.status is FunctionStatus.MEASURED
        )
    )
    return (
        tuple(complete),
        tuple(partial),
        input_state_digest,
        tuple(rejections),
        static_ids,
    )


def collect_staleness(
    *,
    dependencies: Sequence[DependencyReleaseRecord],
    evaluation_time_unix: int | None,
    formula_version: str = STALENESS_FORMULA_VERSION,
) -> tuple[StalenessRecord, ...]:
    records: list[StalenessRecord] = []
    for item in sorted(dependencies, key=lambda dep: (dep.package_id, dep.installed_version)):
        if evaluation_time_unix is None:
            metric = m23_staleness_days(None, item.publication_time_unix)
            reason = "unpinned_evaluation_time"
        else:
            metric = m23_staleness_days(evaluation_time_unix, item.publication_time_unix)
            reason = metric.reason or "complete"
        days = None if metric.value is None else int(metric.value)
        status = MetricStatusName.VALUE
        if metric.status.value == "unknown":
            status = MetricStatusName.UNKNOWN
        records.append(
            StalenessRecord(
                package_id=item.package_id,
                installed_version=item.installed_version,
                status=status,
                days=days,
                evaluation_time_unix=evaluation_time_unix,
                publication_time_unix=item.publication_time_unix,
                source_snapshot_id=item.source_snapshot_id,
                reason=reason if status is MetricStatusName.UNKNOWN else "complete",
                formula_version=formula_version,
            )
        )
    return tuple(records)


def _severity_rank(value: str) -> int:
    try:
        return _SEVERITY_ORDER.index(value)
    except ValueError:
        return len(_SEVERITY_ORDER)


def _evidence_rank(value: str) -> int:
    try:
        return EVIDENCE_CLASS_ORDER_V1.index(value)
    except ValueError:
        return len(EVIDENCE_CLASS_ORDER_V1)


def _hotspot_by_subject(
    complete: Sequence[EngineeringHotspot],
) -> dict[str, EngineeringHotspot]:
    return {item.subject_id: item for item in complete}


def collect_concerns(
    *,
    findings: Sequence[FindingReferenceInput],
    complete_hotspots: Sequence[EngineeringHotspot],
) -> tuple[ConcernRecord, ...]:
    by_subject = _hotspot_by_subject(complete_hotspots)
    records: list[ConcernRecord] = []
    for item in findings:
        if not item.present_in_state or item.state is FindingLifecycle.RESOLVED:
            continue
        hotspot = by_subject.get(item.subject_id)
        comparable = hotspot is not None and hotspot.ranking_value is not None
        hotspot_value = None if hotspot is None else hotspot.ranking_value
        hotspot_label = (
            f"comparable:{hotspot_value}" if comparable else "incomparable"
        )
        explanation = (
            f"formula_version={CONCERN_ORDER_VERSION}; "
            f"evidence_class_order={EVIDENCE_CLASS_ORDER_VERSION}; "
            f"tuple=effective_severity,evidence_class,comparable_hotspot,finding_id; "
            f"severity={item.effective_severity}; "
            f"evidence_class={item.evidence_class.value}; "
            f"hotspot={hotspot_label}; "
            f"finding_id={item.finding_id}; incomparable_after_comparable=true; "
            f"no_weighted_score=true"
        )
        records.append(
            ConcernRecord(
                finding_id=item.finding_id,
                effective_severity=item.effective_severity,
                evidence_class=item.evidence_class.value,
                hotspot_comparable=comparable,
                hotspot_value=None if hotspot is None else hotspot.ranking_value,
                hotspot_subject_id=item.subject_id,
                ranking_inputs=_RANKING_CONCERN_INPUTS,
                context_only=_CONTEXT_CONCERN,
                explanation=explanation,
            )
        )
    records.sort(
        key=lambda item: (
            _severity_rank(item.effective_severity),
            _evidence_rank(item.evidence_class),
            0 if item.hotspot_comparable else 1,
            -(int(item.hotspot_value or "0")) if item.hotspot_comparable else 0,
            item.finding_id,
        )
    )
    return tuple(records)


def assemble_evidence(
    *,
    repository_id: str,
    quality: QualityEvidence,
    history: HistoryWindow | None,
    components: Sequence[ComponentSpec],
    centrality: Mapping[str, str] | None = None,
    reach: Mapping[str, str] | None = None,
    ownership: Mapping[str, OwnershipReference] | None = None,
    findings: Sequence[FindingReferenceInput] = (),
    dependencies: Sequence[DependencyReleaseRecord] = (),
    evaluation_time_unix: int | None = None,
    metadata_snapshot_digest: str = "",
    thresholds: MaintainabilityThresholds | None = None,
    limitations: Sequence[str] = (),
) -> MaintainabilityEvidence:
    complete, partial, digest, rejections, static_ids = collect_hotspots(
        quality=quality,
        history=history,
        components=components,
        centrality=centrality,
        reach=reach,
        ownership=ownership,
        findings=findings,
    )
    staleness = collect_staleness(
        dependencies=dependencies,
        evaluation_time_unix=evaluation_time_unix,
    )
    concerns = collect_concerns(findings=findings, complete_hotspots=complete)
    notes = list(limitations)
    notes.extend(
        (
            "ranking_is_complexity_times_churn_only",
            "no_opaque_score",
            "no_runtime_failure_probability",
            "no_cost_to_fix",
            "no_developer_blame",
            "context_only_cannot_change_rank",
            "missing_history_retains_static_complexity",
            "age_does_not_prove_insecure_or_unsupported",
            "consumed_m24_does_not_extract_git",
        )
    )
    if quality.executed_repository_code or quality.live_lookup:
        raise ValueError("maintainability must not execute repository code or live-lookup")
    return MaintainabilityEvidence(
        repository_id=repository_id,
        input_state_digest=digest,
        history=history,
        complete_hotspots=complete,
        partial_hotspots=partial,
        static_function_ids=static_ids,
        staleness=staleness,
        concerns=concerns,
        finding_rejections=rejections,
        thresholds=thresholds or MaintainabilityThresholds(),
        metadata_snapshot_digest=metadata_snapshot_digest,
        limitations=tuple(sorted(set(notes))),
    )


__all__ = [
    "EVIDENCE_CLASS_ORDER_V1",
    "assemble_evidence",
    "collect_concerns",
    "collect_hotspots",
    "collect_staleness",
]
