"""Single customer-facing finding and recommendation universe.

HTML, report.json, findings.json, recommendations.json, and summary metrics
must all resolve from these helpers so leadership surfaces never disagree.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from codestrata.domain.findings import Finding as Phase3Finding
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import Recommendation as Phase3Recommendation
from codestrata.domain.recommendations import RecommendationResult
from codestrata.models import Finding as Phase1Finding
from codestrata.models import Recommendation as Phase1Recommendation
from codestrata.models.enums import (
    Effort,
    FindingCategory,
    FindingSource,
    Priority,
    RecommendationCategory,
    Risk,
    Severity,
)
from codestrata.models.evidence import Evidence
from codestrata.reporting.contract.enums import (
    normalize_effort,
    normalize_priority,
    normalize_risk,
    normalize_severity,
)
from codestrata.reporting.contract.identifiers import (
    align_related_finding_ids,
    build_finding_id_map,
    remap_related_finding_ids,
    stable_finding_id,
    stable_recommendation_id,
)
from codestrata.reporting.contract.ordering import (
    sorted_findings,
    sorted_recommendations,
)
from codestrata.reporting.modernization_models import ModernizationReportInput
from codestrata.reporting.modernization_view import sanitize_display_path
from codestrata.services.artifact_serialization import dumps_stable_json
from codestrata.services.recommendations.artifacts import RECOMMENDATIONS_FILENAME
from codestrata.services.rule_engine.artifacts import FINDINGS_FILENAME

# Namespace for deriving stable UUIDs from Phase 3 string ids.
_PHASE3_FINDING_NS = UUID("6c0d5a1e-9b2f-4c8a-a1d3-7e5f0b4c2a91")
_PHASE3_REC_NS = UUID("a91c2b4f-0e7d-4a3c-8f1b-5e2d9c0a6b74")


@dataclass(frozen=True, slots=True)
class CustomerFinding:
    """Neutral finding used by HTML, JSON, and findings.json."""

    id: str
    rule_id: str
    title: str
    description: str
    severity: str
    category: str
    source: str
    evidence: tuple[dict[str, Any], ...]
    affected_technologies: tuple[str, ...]
    metadata: dict[str, Any]
    phase1: Phase1Finding | None = None


@dataclass(frozen=True, slots=True)
class CustomerRecommendation:
    """Neutral recommendation used by HTML, JSON, and recommendations.json."""

    id: str
    rule_id: str | None
    title: str
    description: str
    rationale: str
    priority: str
    category: str
    effort: str
    risk: str
    related_finding_ids: tuple[str, ...]
    actions: tuple[str, ...]
    dependencies: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]
    phase1: Phase1Recommendation | None = None
    # Phase 7.1.3 — presentation ordering metadata (deterministic).
    priority_score: float = 0.0
    presentation_bucket: str = "future"


def resolve_customer_findings(
    report_input: ModernizationReportInput,
) -> tuple[CustomerFinding, ...]:
    """Return the single deterministic finding universe for customer artifacts."""

    return merge_customer_findings(
        report_input.analysis_result.findings,
        evaluation=report_input.assessment_rule_evaluation,
    )


def merge_customer_findings(
    phase1_findings: Sequence[Phase1Finding],
    *,
    evaluation: RuleEvaluationResult | None = None,
) -> tuple[CustomerFinding, ...]:
    """Merge Phase-1 and Phase-3 findings into one customer universe."""

    items: list[CustomerFinding] = []
    seen: set[str] = set()

    for finding in sorted_findings(phase1_findings):
        customer = _from_phase1_finding(finding)
        key = _finding_dedupe_key(customer)
        if key in seen:
            continue
        seen.add(key)
        items.append(customer)

    if evaluation is not None:
        for finding in evaluation.findings:
            customer = _from_phase3_finding(finding)
            key = _finding_dedupe_key(customer)
            if key in seen:
                continue
            seen.add(key)
            items.append(customer)

    items.sort(
        key=lambda item: (
            _severity_rank(item.severity),
            item.category.lower(),
            item.title.lower(),
            item.id,
        )
    )
    return tuple(items)


def merge_customer_recommendations(
    phase1_recommendations: Sequence[Phase1Recommendation],
    *,
    result: RecommendationResult | None = None,
    finding_id_map: dict[str, str] | None = None,
) -> tuple[CustomerRecommendation, ...]:
    """Merge Phase-1 and Phase-3 recommendations into one customer universe."""

    items: list[CustomerRecommendation] = []
    seen: set[str] = set()
    id_map = finding_id_map or {}

    for recommendation in sorted_recommendations(phase1_recommendations):
        customer = _from_phase1_recommendation(recommendation, finding_id_map=id_map)
        key = _recommendation_dedupe_key(customer)
        if key in seen:
            continue
        seen.add(key)
        items.append(customer)

    if result is not None:
        for recommendation in result.recommendations:
            customer = _from_phase3_recommendation(recommendation)
            key = _recommendation_dedupe_key(customer)
            if key in seen:
                continue
            seen.add(key)
            items.append(customer)

    items.sort(
        key=lambda item: (
            _priority_rank(item.priority),
            item.category.lower(),
            item.title.lower(),
            item.id,
        )
    )
    return tuple(items)


def resolve_customer_recommendations(
    report_input: ModernizationReportInput,
) -> tuple[CustomerRecommendation, ...]:
    """Return the single deterministic recommendation universe for customers."""

    from codestrata.reporting.prioritization import prioritize_customer_recommendations

    findings = resolve_customer_findings(report_input)
    allowed_finding_ids = {item.id for item in findings}
    aliases = _related_finding_aliases(report_input, findings)
    finding_id_map = build_finding_id_map(list(report_input.analysis_result.findings))
    merged = merge_customer_recommendations(
        report_input.analysis_result.recommendations,
        result=report_input.assessment_recommendation_result,
        finding_id_map=finding_id_map,
    )
    aligned = tuple(
        replace(
            item,
            related_finding_ids=align_related_finding_ids(
                item.related_finding_ids,
                allowed_finding_ids=allowed_finding_ids,
                alias_to_allowed=aliases,
            ),
        )
        for item in merged
    )
    return prioritize_customer_recommendations(aligned, findings)


def _related_finding_aliases(
    report_input: ModernizationReportInput,
    customer_findings: Sequence[CustomerFinding],
) -> dict[str, str]:
    """Map pre-dedupe finding IDs onto the surviving customer finding ID.

    When multiple findings collapse on ``rule_id::title``, recommendations that
    referenced a dropped finding still retain traceability to the survivor.
    """

    by_key = {_finding_dedupe_key(item): item.id for item in customer_findings}
    aliases: dict[str, str] = {}

    for phase1_finding in report_input.analysis_result.findings:
        customer = _from_phase1_finding(phase1_finding)
        survivor = by_key.get(_finding_dedupe_key(customer))
        if survivor is None:
            continue
        aliases[str(phase1_finding.id)] = survivor
        aliases[customer.id] = survivor

    evaluation = report_input.assessment_rule_evaluation
    if evaluation is not None:
        for phase3_finding in evaluation.findings:
            customer = _from_phase3_finding(phase3_finding)
            survivor = by_key.get(_finding_dedupe_key(customer))
            if survivor is None:
                continue
            aliases[str(phase3_finding.id)] = survivor
            aliases[customer.id] = survivor

    return aliases


def customer_findings_payload(
    findings: Sequence[CustomerFinding],
    *,
    evaluation: RuleEvaluationResult | None = None,
) -> dict[str, Any]:
    """Serialize findings.json from the customer universe."""

    return {
        "finding_count": len(findings),
        "findings": [customer_finding_json(item) for item in findings],
        "rules_evaluated": list(evaluation.rules_evaluated) if evaluation else [],
        "rules_skipped": list(evaluation.rules_skipped) if evaluation else [],
    }


def customer_recommendations_payload(
    recommendations: Sequence[CustomerRecommendation],
    *,
    result: RecommendationResult | None = None,
) -> dict[str, Any]:
    """Serialize recommendations.json from the customer universe."""

    return {
        "providers_evaluated": list(result.providers_evaluated) if result else [],
        "providers_skipped": list(result.providers_skipped) if result else [],
        "recommendation_count": len(recommendations),
        "recommendations": [customer_recommendation_json(item) for item in recommendations],
        "unmatched_finding_ids": list(result.unmatched_finding_ids) if result else [],
        "version": getattr(result, "version", "1.0.0") if result else "1.0.0",
    }


def write_customer_finding_artifacts(
    report_input: ModernizationReportInput,
    run_directory: Path,
) -> None:
    """Overwrite findings.json / recommendations.json with the customer universe."""

    findings = resolve_customer_findings(report_input)
    recommendations = resolve_customer_recommendations(report_input)
    run_directory.mkdir(parents=True, exist_ok=True)
    (run_directory / FINDINGS_FILENAME).write_text(
        dumps_stable_json(
            customer_findings_payload(
                findings,
                evaluation=report_input.assessment_rule_evaluation,
            )
        ),
        encoding="utf-8",
    )
    (run_directory / RECOMMENDATIONS_FILENAME).write_text(
        dumps_stable_json(
            customer_recommendations_payload(
                recommendations,
                result=report_input.assessment_recommendation_result,
            )
        ),
        encoding="utf-8",
    )


def customer_finding_json(item: CustomerFinding) -> dict[str, Any]:
    evidence_items = [_sanitize_evidence_row(row) for row in item.evidence]
    deduped_evidence: list[dict[str, Any]] = []
    seen_evidence: set[tuple[Any, ...]] = set()
    for row in evidence_items:
        key = (
            row.get("file_path") or row.get("path"),
            row.get("line_number"),
            row.get("column_number"),
            row.get("description") or row.get("excerpt"),
        )
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        deduped_evidence.append(row)
    return {
        "id": item.id,
        "rule_id": item.rule_id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "severity": normalize_severity(item.severity),
        "source": item.source,
        "evidence": deduped_evidence,
        "affected_technologies": list(item.affected_technologies),
        "metadata": dict(item.metadata),
        "provider_name": item.metadata.get("provider_name"),
        "customer_visibility": item.metadata.get("customer_visibility"),
        "modernization_relevance": item.metadata.get("modernization_relevance"),
        "group_id": item.metadata.get("group_id"),
        "occurrence_count": item.metadata.get("occurrence_count"),
        "affected_file_count": item.metadata.get("affected_file_count"),
        "provider_priority": item.metadata.get("original_priority"),
        "provider_category": item.metadata.get("ruleset"),
    }


def customer_recommendation_json(item: CustomerRecommendation) -> dict[str, Any]:
    return {
        "id": item.id,
        "rule_id": item.rule_id,
        "title": item.title,
        "description": item.description,
        "rationale": item.rationale,
        "priority": normalize_priority(item.priority),
        "category": item.category,
        "effort": normalize_effort(item.effort),
        "risk": normalize_risk(item.risk),
        "related_finding_ids": list(item.related_finding_ids),
        "actions": list(item.actions),
        "dependencies": list(item.dependencies),
        "evidence": [_sanitize_evidence_row(row) for row in item.evidence],
        "priority_score": round(float(item.priority_score), 2),
        "presentation_bucket": item.presentation_bucket,
    }


def _sanitize_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(row)
    if "file_path" in sanitized and sanitized["file_path"] is not None:
        sanitized["file_path"] = sanitize_display_path(str(sanitized["file_path"]))
    if "path" in sanitized and sanitized["path"] is not None:
        sanitized["path"] = sanitize_display_path(str(sanitized["path"]))
    return sanitized


def phase1_findings_for_contract(
    findings: Sequence[CustomerFinding],
) -> list[Phase1Finding]:
    """Return Phase-1 models for contract helpers that still expect them."""

    out: list[Phase1Finding] = []
    for item in findings:
        if item.phase1 is not None:
            out.append(item.phase1)
            continue
        out.append(_customer_to_phase1_finding(item))
    return out


def phase1_recommendations_for_contract(
    recommendations: Sequence[CustomerRecommendation],
) -> list[Phase1Recommendation]:
    out: list[Phase1Recommendation] = []
    for item in recommendations:
        if item.phase1 is not None:
            out.append(item.phase1)
            continue
        out.append(_customer_to_phase1_recommendation(item))
    return out


def _from_phase1_finding(finding: Phase1Finding) -> CustomerFinding:
    return CustomerFinding(
        id=stable_finding_id(finding),
        rule_id=finding.rule_id or "unknown",
        title=finding.title,
        description=finding.description,
        severity=str(getattr(finding.severity, "value", finding.severity)),
        category=str(getattr(finding.category, "value", finding.category)),
        source=str(getattr(finding.source, "value", finding.source)),
        evidence=tuple(
            {
                "file_path": item.file_path,
                "line_number": item.line_number,
                "column_number": item.column_number,
                "description": item.description,
            }
            for item in finding.evidence
        ),
        affected_technologies=tuple(str(item) for item in finding.affected_technologies),
        metadata=dict(finding.metadata),
        phase1=finding,
    )


def _from_phase3_finding(finding: Phase3Finding) -> CustomerFinding:
    return CustomerFinding(
        id=finding.id,
        rule_id=finding.rule_id,
        title=finding.title,
        description=finding.description,
        severity=finding.severity.value,
        category=finding.category.value,
        source=finding.source.value,
        evidence=tuple(
            {
                "evidence_type": item.evidence_type,
                "source_id": item.source_id,
                "path": item.path,
                "excerpt": item.excerpt,
                "node_id": str(item.node_id.root) if item.node_id is not None else None,
            }
            for item in finding.evidence
        ),
        affected_technologies=(),
        metadata=dict(finding.metadata),
        phase1=None,
    )


def _from_phase1_recommendation(
    recommendation: Phase1Recommendation,
    *,
    finding_id_map: dict[str, str] | None = None,
) -> CustomerRecommendation:
    id_map = finding_id_map or {}
    related = tuple(remap_related_finding_ids(recommendation.related_finding_ids, id_map))
    return CustomerRecommendation(
        id=stable_recommendation_id(recommendation),
        rule_id=recommendation.rule_id,
        title=recommendation.title,
        description=recommendation.description,
        rationale=recommendation.rationale,
        priority=str(getattr(recommendation.priority, "value", recommendation.priority)),
        category=str(getattr(recommendation.category, "value", recommendation.category)),
        effort=str(getattr(recommendation.effort, "value", recommendation.effort)),
        risk=str(getattr(recommendation.risk, "value", recommendation.risk)),
        related_finding_ids=related,
        actions=tuple(str(item) for item in recommendation.actions),
        dependencies=tuple(str(item) for item in recommendation.dependencies),
        evidence=tuple(
            {
                "file_path": item.file_path,
                "line_number": item.line_number,
                "column_number": item.column_number,
                "description": item.description,
            }
            for item in recommendation.evidence
        ),
        phase1=recommendation,
    )


def _from_phase3_recommendation(
    recommendation: Phase3Recommendation,
) -> CustomerRecommendation:
    rule_id = recommendation.metadata.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        rule_id = f"provider:{recommendation.provider_id}"
    return CustomerRecommendation(
        id=recommendation.id,
        rule_id=rule_id,
        title=recommendation.title,
        description=recommendation.summary,
        rationale=recommendation.rationale,
        priority=recommendation.priority.value,
        category=recommendation.category.value,
        effort=Effort.UNKNOWN.value,
        risk=Risk.MEDIUM.value,
        related_finding_ids=tuple(str(item) for item in recommendation.related_finding_ids),
        actions=tuple(
            (
                action.title
                if action.title == action.description
                else f"{action.title}: {action.description}"
            )
            for action in sorted(recommendation.actions, key=lambda row: (row.order, row.title))
        ),
        dependencies=(),
        evidence=tuple(
            {
                "evidence_type": item.evidence_type,
                "source_id": item.source_id,
                "path": item.path,
                "excerpt": item.excerpt,
            }
            for item in recommendation.evidence
        ),
        phase1=None,
    )


def _customer_to_phase1_finding(item: CustomerFinding) -> Phase1Finding:
    severity = _coerce_severity(item.severity)
    category = _coerce_finding_category(item.category)
    source = _coerce_finding_source(item.source)
    evidence = [
        Evidence(
            file_path=str(row.get("file_path") or row.get("path") or ""),
            line_number=row.get("line_number"),
            column_number=row.get("column_number"),
            description=str(row.get("description") or row.get("excerpt") or ""),
        )
        for row in item.evidence
        if isinstance(row, dict)
    ]
    try:
        finding_uuid = UUID(item.id)
    except ValueError:
        finding_uuid = uuid5(_PHASE3_FINDING_NS, item.id)
    return Phase1Finding(
        id=finding_uuid,
        rule_id=item.rule_id,
        title=item.title,
        description=item.description,
        category=category,
        severity=severity,
        source=source,
        evidence=evidence,
        affected_technologies=list(item.affected_technologies),
        metadata=dict(item.metadata),
    )


def _customer_to_phase1_recommendation(
    item: CustomerRecommendation,
) -> Phase1Recommendation:
    try:
        rec_uuid = UUID(item.id)
    except ValueError:
        rec_uuid = uuid5(_PHASE3_REC_NS, item.id)
    return Phase1Recommendation(
        id=rec_uuid,
        rule_id=item.rule_id or "unknown",
        title=item.title,
        description=item.description,
        rationale=item.rationale,
        priority=_coerce_priority(item.priority),
        category=_coerce_recommendation_category(item.category),
        effort=_coerce_effort(item.effort),
        risk=_coerce_risk(item.risk),
        related_finding_ids=list(item.related_finding_ids),
        actions=list(item.actions),
        dependencies=list(item.dependencies),
        evidence=[
            Evidence(
                file_path=str(row.get("file_path") or row.get("path") or ""),
                line_number=row.get("line_number"),
                column_number=row.get("column_number"),
                description=str(row.get("description") or row.get("excerpt") or ""),
            )
            for row in item.evidence
            if isinstance(row, dict)
        ],
    )


def _finding_dedupe_key(item: CustomerFinding) -> str:
    return f"{item.rule_id.strip().lower()}::{item.title.strip().lower()}"


def _recommendation_dedupe_key(item: CustomerRecommendation) -> str:
    rule = (item.rule_id or "").strip().lower()
    return f"{rule}::{item.title.strip().lower()}"


def _severity_rank(value: str) -> int:
    order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "informational": 4,
        "info": 4,
    }
    return order.get(value.lower(), 99)


def _priority_rank(value: str) -> int:
    order = {"immediate": 0, "critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(value.lower(), 99)


def _coerce_severity(value: str) -> Severity:
    normalized = value.lower()
    if normalized == "informational":
        normalized = "info"
    try:
        return Severity(normalized)
    except ValueError:
        return Severity.INFO


def _coerce_finding_category(value: str) -> FindingCategory:
    try:
        return FindingCategory(value.lower())
    except ValueError:
        return FindingCategory.ARCHITECTURE


def _coerce_finding_source(value: str) -> FindingSource:
    normalized = value.lower()
    if normalized == "rule":
        normalized = FindingSource.DETERMINISTIC.value
    try:
        return FindingSource(normalized)
    except ValueError:
        return FindingSource.DETERMINISTIC


def _coerce_priority(value: str) -> Priority:
    normalized = value.lower()
    if normalized == "immediate":
        normalized = Priority.CRITICAL.value
    try:
        return Priority(normalized)
    except ValueError:
        return Priority.LOW


def _coerce_recommendation_category(value: str) -> RecommendationCategory:
    try:
        return RecommendationCategory(value.lower())
    except ValueError:
        return RecommendationCategory.ARCHITECTURE


def _coerce_effort(value: str) -> Effort:
    try:
        return Effort(value.lower())
    except ValueError:
        return Effort.UNKNOWN


def _coerce_risk(value: str) -> Risk:
    try:
        return Risk(value.lower())
    except ValueError:
        return Risk.MEDIUM


__all__ = [
    "CustomerFinding",
    "CustomerRecommendation",
    "customer_finding_json",
    "customer_findings_payload",
    "customer_recommendation_json",
    "customer_recommendations_payload",
    "merge_customer_findings",
    "merge_customer_recommendations",
    "phase1_findings_for_contract",
    "phase1_recommendations_for_contract",
    "resolve_customer_findings",
    "resolve_customer_recommendations",
    "write_customer_finding_artifacts",
]
