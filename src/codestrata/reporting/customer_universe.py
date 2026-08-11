"""Single customer-facing finding and recommendation universe.

``report.json`` is the canonical machine-readable artifact (Epic 2 Slice 2.6).
HTML, findings.json, recommendations.json, and summary metrics must all resolve
from these helpers so leadership surfaces never disagree with report.json.
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
    # Epic 2 Slice 2.6 — EvidenceRef traceability (dual-carry with thin evidence).
    evidence_refs: tuple[Any, ...] = ()
    primary_evidence_id: str | None = None
    synthesized_from_evidence_ids: tuple[str, ...] = ()
    evidence_completeness: str = "legacy"
    limitations: tuple[str, ...] = ()
    finding_confidence: Any | None = None
    # Epic 5 Slice 5.12 — correlation references only.
    correlation_ids: tuple[str, ...] = ()
    correlated_finding_ids: tuple[str, ...] = ()
    # Epic 5 Slice 5.13 — severity calibration (additive).
    base_severity: str | None = None
    severity_assessment: dict[str, Any] | None = None


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
    # Epic 2 Slice 2.3 — dual-written with related_finding_ids.
    supporting_finding_ids: tuple[str, ...] = ()
    primary_finding_id: str | None = None
    recommendation_type: str = "legacy"
    evidence_completeness: str = "legacy"
    limitations: tuple[str, ...] = ()
    recommendation_confidence: Any | None = None
    # Epic 5 Slice 5.14 — calibrated Recommendation priority assessment.
    priority_assessment: Any | None = None
    provider_id: str | None = None


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
    """Merge Phase-1 and Phase-3 findings into one customer universe.

    Phase-3 Findings are consolidated (Slice 5.11) before projection so the
    customer universe is the consolidation authority. Phase-1 rule+title
    collisions union evidence instead of first-wins discard.
    """

    from codestrata.application.findings.consolidation import consolidate_findings
    from codestrata.application.findings.correlation import correlate_findings

    items: list[CustomerFinding] = []
    by_key: dict[str, CustomerFinding] = {}
    order: list[str] = []

    for finding in sorted_findings(phase1_findings):
        customer = _from_phase1_finding(finding)
        key = _finding_dedupe_key(customer)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = customer
            order.append(key)
            continue
        by_key[key] = _merge_customer_finding_evidence(existing, customer)

    if evaluation is not None:
        consolidated = consolidate_findings(evaluation.findings)
        correlated = correlate_findings(consolidated.findings)  # type: ignore[arg-type]
        for finding in correlated.findings:
            customer = _from_phase3_finding(finding)  # type: ignore[arg-type]
            # Surface member aliases for recommendation remapping.
            members = str((customer.metadata or {}).get("duplicate_member_finding_ids") or "")
            if members:
                metadata = dict(customer.metadata)
                metadata["duplicate_member_finding_ids"] = members
                customer = replace(customer, metadata=metadata)
            key = _finding_dedupe_key(customer)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = customer
                order.append(key)
                continue
            # Shared-rule ID key: union rather than first-wins.
            by_key[key] = _merge_customer_finding_evidence(existing, customer)

    items = [by_key[key] for key in order]
    items.sort(
        key=lambda item: (
            _severity_rank(item.severity),
            item.category.lower(),
            item.title.lower(),
            item.id,
        )
    )
    return tuple(items)


def _merge_customer_finding_evidence(
    preferred: CustomerFinding,
    other: CustomerFinding,
) -> CustomerFinding:
    """Union evidence rows for colliding customer findings (no first-wins loss)."""

    evidence_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in (*preferred.evidence, *other.evidence):
        fingerprint = dumps_stable_json(row)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        evidence_rows.append(dict(row))
    limitations = tuple(sorted(set(preferred.limitations) | set(other.limitations)))
    member_meta = dict(preferred.metadata)
    other_members = str((other.metadata or {}).get("duplicate_member_finding_ids") or "")
    pref_members = str(member_meta.get("duplicate_member_finding_ids") or "")
    aliases = {
        part
        for part in f"{pref_members},{other_members},{other.id}".split(",")
        if part and part != preferred.id
    }
    if aliases:
        member_meta["duplicate_member_finding_ids"] = ",".join(sorted(aliases))
    # Prefer Shared Rule finding_confidence when preferred is unavailable.
    confidence = preferred.finding_confidence
    other_conf = other.finding_confidence
    if confidence is not None and other_conf is not None:
        pref_unavailable = getattr(
            getattr(confidence, "level", None), "value", ""
        ) == "unavailable"
        if pref_unavailable:
            confidence = other_conf
    return replace(
        preferred,
        evidence=tuple(evidence_rows),
        limitations=limitations,
        metadata=member_meta,
        finding_confidence=confidence,
        evidence_refs=tuple(preferred.evidence_refs or other.evidence_refs),
        primary_evidence_id=preferred.primary_evidence_id or other.primary_evidence_id,
        synthesized_from_evidence_ids=tuple(
            sorted(
                set(preferred.synthesized_from_evidence_ids)
                | set(other.synthesized_from_evidence_ids)
            )
        ),
    )


def merge_customer_recommendations(
    phase1_recommendations: Sequence[Phase1Recommendation],
    *,
    result: RecommendationResult | None = None,
    finding_id_map: dict[str, str] | None = None,
) -> tuple[CustomerRecommendation, ...]:
    """Merge Phase-1 and Phase-3 recommendations into one customer universe.

    Duplicate rule+title keys union finding traceability instead of first-wins.
    """

    by_key: dict[str, CustomerRecommendation] = {}
    order: list[str] = []
    id_map = finding_id_map or {}

    for recommendation in sorted_recommendations(phase1_recommendations):
        customer = _from_phase1_recommendation(recommendation, finding_id_map=id_map)
        key = _recommendation_dedupe_key(customer)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = customer
            order.append(key)
            continue
        by_key[key] = _merge_customer_recommendation_traceability(existing, customer)

    if result is not None:
        for recommendation in result.recommendations:
            customer = _from_phase3_recommendation(recommendation)
            key = _recommendation_dedupe_key(customer)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = customer
                order.append(key)
                continue
            by_key[key] = _merge_customer_recommendation_traceability(existing, customer)

    items = [by_key[key] for key in order]
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
    findings_by_id = {item.id: item for item in findings}
    aligned = tuple(
        _apply_customer_recommendation_priority(
            _apply_customer_recommendation_confidence(
                _align_customer_recommendation_findings(
                    item, allowed_finding_ids, aliases
                ),
                findings_by_id=findings_by_id,
            ),
            findings_by_id=findings_by_id,
        )
        for item in merged
    )
    return prioritize_customer_recommendations(aligned, findings)


def _align_customer_recommendation_findings(
    item: CustomerRecommendation,
    allowed_finding_ids: set[str],
    aliases: dict[str, str],
) -> CustomerRecommendation:
    related = align_related_finding_ids(
        item.related_finding_ids,
        allowed_finding_ids=allowed_finding_ids,
        alias_to_allowed=aliases,
    )
    supporting_source = item.supporting_finding_ids or item.related_finding_ids
    supporting = align_related_finding_ids(
        supporting_source,
        allowed_finding_ids=allowed_finding_ids,
        alias_to_allowed=aliases,
    )
    # Compatibility dual-write: keep both collections identical after alignment.
    finding_ids = tuple(sorted(set(related) | set(supporting)))
    primary = item.primary_finding_id
    if primary is not None:
        primary = aliases.get(primary, primary)
        if primary not in finding_ids:
            primary = finding_ids[0] if finding_ids else None
    elif finding_ids:
        primary = finding_ids[0]
    return replace(
        item,
        related_finding_ids=finding_ids,
        supporting_finding_ids=finding_ids,
        primary_finding_id=primary,
    )


def _merge_customer_recommendation_traceability(
    preferred: CustomerRecommendation,
    other: CustomerRecommendation,
) -> CustomerRecommendation:
    finding_ids = tuple(
        sorted(
            set(preferred.supporting_finding_ids or preferred.related_finding_ids)
            | set(other.supporting_finding_ids or other.related_finding_ids)
        )
    )
    limitations = tuple(sorted(set(preferred.limitations) | set(other.limitations)))
    primary = preferred.primary_finding_id
    if primary not in finding_ids:
        primary = other.primary_finding_id if other.primary_finding_id in finding_ids else None
    if primary is None and finding_ids:
        primary = finding_ids[0]
    completeness = preferred.evidence_completeness
    if finding_ids and (
        preferred.evidence_completeness == "complete" or other.evidence_completeness == "complete"
    ):
        completeness = "complete"
    elif finding_ids:
        completeness = "partial" if completeness == "legacy" else completeness
    return replace(
        preferred,
        related_finding_ids=finding_ids,
        supporting_finding_ids=finding_ids,
        primary_finding_id=primary,
        recommendation_type="merged",
        evidence_completeness=completeness,
        limitations=limitations,
        recommendation_confidence=None,  # recomputed after finding alignment
        priority_assessment=None,  # recomputed after confidence
        provider_id=preferred.provider_id or other.provider_id,
    )


def _apply_customer_recommendation_confidence(
    item: CustomerRecommendation,
    *,
    findings_by_id: dict[str, CustomerFinding],
) -> CustomerRecommendation:
    from codestrata.application.recommendations.confidence import (
        derive_customer_recommendation_confidence,
    )

    confidence = derive_customer_recommendation_confidence(
        supporting_finding_ids=item.supporting_finding_ids or item.related_finding_ids,
        primary_finding_id=item.primary_finding_id,
        evidence_completeness=item.evidence_completeness,
        recommendation_type=item.recommendation_type,
        limitations=item.limitations,
        findings_by_id=findings_by_id,
    )
    return replace(item, recommendation_confidence=confidence)


def _apply_customer_recommendation_priority(
    item: CustomerRecommendation,
    *,
    findings_by_id: dict[str, CustomerFinding],
) -> CustomerRecommendation:
    """Calibrate customer recommendation priority after confidence is known."""

    from codestrata.application.recommendations.priority_calibration import (
        calibrate_recommendation_priority,
    )
    from codestrata.domain.recommendations.enums import RecommendationPriority
    from types import SimpleNamespace

    provider_id = item.provider_id
    if not provider_id and item.rule_id and str(item.rule_id).startswith("provider:"):
        provider_id = str(item.rule_id).removeprefix("provider:")

    try:
        priority_enum = RecommendationPriority(str(item.priority).strip().lower())
    except ValueError:
        priority_enum = RecommendationPriority.LOW

    supporting_ids = item.supporting_finding_ids or item.related_finding_ids
    # Preserve Phase-1 critical/immediate as Immediate seed for finding-backed
    # compatibility scoring (customer JSON may still normalize aliases).
    if str(item.priority).strip().lower() in {"critical", "immediate"}:
        priority_enum = RecommendationPriority.IMMEDIATE

    proxy = SimpleNamespace(
        provider_id=provider_id or "",
        priority=priority_enum,
        supporting_finding_ids=supporting_ids,
        related_finding_ids=item.related_finding_ids,
        recommendation_type=item.recommendation_type,
        evidence_completeness=item.evidence_completeness,
        limitations=item.limitations,
        recommendation_confidence=item.recommendation_confidence,
        metadata={},
    )
    assessment = calibrate_recommendation_priority(
        proxy,
        findings=tuple(
            findings_by_id[fid]
            for fid in proxy.supporting_finding_ids
            if fid in findings_by_id
        ),
    )
    # Project Immediate → customer-facing critical for Priority Action / JSON parity.
    projected = normalize_priority(assessment.priority.value)
    return replace(
        item,
        priority=projected,
        priority_assessment=assessment,
        provider_id=provider_id,
    )


def _related_finding_aliases(
    report_input: ModernizationReportInput,
    customer_findings: Sequence[CustomerFinding],
) -> dict[str, str]:
    """Map pre-dedupe / consolidated member Finding IDs onto survivors.

    Covers Phase-1 rule+title collapse and Slice 5.11 duplicate member aliases.
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
        from codestrata.application.findings.consolidation import consolidate_findings

        consolidated = consolidate_findings(evaluation.findings)
        for member_id, canonical_id in consolidated.original_to_canonical.items():
            aliases[member_id] = canonical_id
        for phase3_finding in consolidated.findings:
            customer = _from_phase3_finding(phase3_finding)  # type: ignore[arg-type]
            survivor = by_key.get(_finding_dedupe_key(customer))
            if survivor is None:
                continue
            aliases[str(phase3_finding.id)] = survivor
            aliases[customer.id] = survivor

    for item in customer_findings:
        members = str((item.metadata or {}).get("duplicate_member_finding_ids") or "")
        for member_id in members.split(","):
            member_id = member_id.strip()
            if member_id:
                aliases[member_id] = item.id

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
    from codestrata.security.customer_safe_text import sanitize_customer_text

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
    payload = {
        "id": item.id,
        "rule_id": item.rule_id,
        "title": sanitize_customer_text(item.title),
        "description": sanitize_customer_text(item.description),
        "category": item.category,
        "severity": normalize_severity(item.severity),
        "source": item.source,
        "evidence": deduped_evidence,
        "evidence_refs": [
            {"evidence_id": str(getattr(ref, "evidence_id", ref))}
            for ref in item.evidence_refs
        ],
        "primary_evidence_id": item.primary_evidence_id,
        "synthesized_from_evidence_ids": list(item.synthesized_from_evidence_ids),
        "evidence_completeness": item.evidence_completeness,
        "limitations": list(item.limitations),
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
        "correlation_ids": list(item.correlation_ids),
        "correlated_finding_ids": list(item.correlated_finding_ids),
    }
    if item.base_severity:
        payload["base_severity"] = normalize_severity(item.base_severity)
    if isinstance(item.severity_assessment, dict) and item.severity_assessment:
        # Customer-safe subset — no internal class names or secret values.
        assessment = item.severity_assessment
        payload["severity_assessment"] = {
            "severity": normalize_severity(str(assessment.get("severity") or item.severity)),
            "basis": list(assessment.get("basis") or []),
            "calibration_status": assessment.get("calibration_status"),
            "limitations": list(assessment.get("limitations") or []),
        }
    rule_confidence = item.metadata.get("rule_confidence")
    if isinstance(rule_confidence, dict):
        payload["rule_confidence"] = dict(rule_confidence)
    if item.finding_confidence is not None:
        from codestrata.domain.findings.finding_confidence import (
            FindingConfidence,
            finding_confidence_to_json,
        )

        if isinstance(item.finding_confidence, FindingConfidence):
            payload["finding_confidence"] = finding_confidence_to_json(
                item.finding_confidence
            )
        elif isinstance(item.finding_confidence, dict):
            payload["finding_confidence"] = dict(
                sorted(item.finding_confidence.items(), key=lambda pair: str(pair[0]))
            )
    return payload


def customer_recommendation_json(item: CustomerRecommendation) -> dict[str, Any]:
    from codestrata.security.customer_safe_text import sanitize_customer_text

    supporting = list(item.supporting_finding_ids or item.related_finding_ids)
    related = list(item.related_finding_ids or item.supporting_finding_ids)
    # Compatibility dual-write in customer JSON.
    if supporting != related:
        merged = sorted(set(supporting) | set(related))
        supporting = merged
        related = merged
    payload = {
        "id": item.id,
        "rule_id": item.rule_id,
        "title": sanitize_customer_text(item.title),
        "description": sanitize_customer_text(item.description),
        "rationale": sanitize_customer_text(item.rationale),
        "priority": normalize_priority(item.priority),
        "category": item.category,
        "effort": normalize_effort(item.effort),
        "risk": normalize_risk(item.risk),
        "related_finding_ids": related,
        "supporting_finding_ids": supporting,
        "primary_finding_id": item.primary_finding_id,
        "recommendation_type": item.recommendation_type,
        "evidence_completeness": item.evidence_completeness,
        "limitations": list(item.limitations),
        "actions": list(item.actions),
        "dependencies": list(item.dependencies),
        "evidence": [_sanitize_evidence_row(row) for row in item.evidence],
        "priority_score": round(float(item.priority_score), 2),
        "presentation_bucket": item.presentation_bucket,
    }
    if item.recommendation_confidence is not None:
        from codestrata.domain.recommendations.recommendation_confidence import (
            RecommendationConfidence,
            recommendation_confidence_to_json,
        )

        if isinstance(item.recommendation_confidence, RecommendationConfidence):
            payload["recommendation_confidence"] = recommendation_confidence_to_json(
                item.recommendation_confidence
            )
        elif isinstance(item.recommendation_confidence, dict):
            payload["recommendation_confidence"] = dict(
                sorted(
                    item.recommendation_confidence.items(),
                    key=lambda pair: str(pair[0]),
                )
            )
    if item.priority_assessment is not None:
        from codestrata.application.recommendations.priority_calibration import (
            priority_assessment_to_json,
        )
        from codestrata.domain.recommendations.priority import (
            RecommendationPriorityAssessment,
        )

        if isinstance(item.priority_assessment, RecommendationPriorityAssessment):
            payload["priority_assessment"] = priority_assessment_to_json(
                item.priority_assessment
            )
        elif isinstance(item.priority_assessment, dict):
            payload["priority_assessment"] = dict(
                sorted(
                    item.priority_assessment.items(),
                    key=lambda pair: str(pair[0]),
                )
            )
    return payload


def _sanitize_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    from codestrata.security.customer_safe_text import sanitize_customer_text

    sanitized = dict(row)
    if "file_path" in sanitized and sanitized["file_path"] is not None:
        sanitized["file_path"] = sanitize_display_path(str(sanitized["file_path"]))
    if "path" in sanitized and sanitized["path"] is not None:
        sanitized["path"] = sanitize_display_path(str(sanitized["path"]))
    for key in ("description", "excerpt", "detected_value", "redacted_preview", "preview"):
        if key in sanitized and isinstance(sanitized[key], str):
            sanitized[key] = sanitize_customer_text(sanitized[key])
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
    from codestrata.domain.findings.finding_confidence import FindingConfidence

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
        finding_confidence=FindingConfidence.unavailable(
            limitations=(
                "Phase-1 finding lacks Shared Rule Confidence and Evidence Confidence.",
            ),
        ),
    )


def _from_phase3_finding(finding: Phase3Finding) -> CustomerFinding:
    corr_ids = tuple(getattr(finding, "correlation_ids", ()) or ())
    related_ids = tuple(getattr(finding, "correlated_finding_ids", ()) or ())
    if not corr_ids:
        raw = str((finding.metadata or {}).get("correlation_ids") or "")
        corr_ids = tuple(part for part in raw.split(",") if part.strip())
    if not related_ids:
        raw = str((finding.metadata or {}).get("correlated_finding_ids") or "")
        related_ids = tuple(part for part in raw.split(",") if part.strip())
    base_sev = getattr(finding, "base_severity", None)
    assessment = getattr(finding, "severity_assessment", None)
    assessment_payload = None
    if assessment is not None and hasattr(assessment, "canonical_dict"):
        assessment_payload = assessment.canonical_dict()
    elif isinstance(assessment, dict):
        assessment_payload = dict(assessment)
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
        evidence_refs=tuple(finding.evidence_refs),
        primary_evidence_id=finding.primary_evidence_id,
        synthesized_from_evidence_ids=tuple(finding.synthesized_from_evidence_ids),
        evidence_completeness=finding.evidence_completeness.value,
        limitations=tuple(finding.limitations),
        finding_confidence=finding.finding_confidence,
        correlation_ids=corr_ids,
        correlated_finding_ids=related_ids,
        base_severity=base_sev.value if base_sev is not None else finding.metadata.get("base_severity"),
        severity_assessment=assessment_payload,
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
        supporting_finding_ids=related,
        primary_finding_id=related[0] if related else None,
        recommendation_type="legacy" if not related else "finding_backed",
        evidence_completeness="legacy" if not related else "complete",
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
    supporting = tuple(
        str(item)
        for item in (
            recommendation.supporting_finding_ids or recommendation.related_finding_ids
        )
    )
    related = tuple(str(item) for item in recommendation.related_finding_ids) or supporting
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
        related_finding_ids=related,
        supporting_finding_ids=supporting or related,
        primary_finding_id=recommendation.primary_finding_id
        or ((supporting or related)[0] if (supporting or related) else None),
        recommendation_type=recommendation.recommendation_type.value,
        evidence_completeness=recommendation.evidence_completeness.value,
        limitations=tuple(recommendation.limitations),
        recommendation_confidence=recommendation.recommendation_confidence,
        priority_assessment=getattr(recommendation, "priority_assessment", None),
        provider_id=recommendation.provider_id,
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
    """Dedupe key for customer findings.

    Shared-rule findings use evidence-scoped IDs (``finding:…``). Collapsing
    those on rule+title alone drops distinct credential/key hits that share a
    title. Legacy/analyzer findings still collapse on rule+title.
    """

    finding_id = (item.id or "").strip().lower()
    if finding_id.startswith("finding:"):
        return f"id::{finding_id}"
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
