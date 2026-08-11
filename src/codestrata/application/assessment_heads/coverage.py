"""Deterministic Assessment Coverage derivation (Slice 5.6).

Coverage is measured from structured pack/activation/evidence signals only.
Finding counts, confidence levels, severity, and AI output are never inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.domain.assessment_heads.area_catalog import (
    DeclaredAssessmentArea,
    declared_areas_for_head,
)
from codestrata.domain.assessment_heads.assessment_coverage import (
    AreaClaimState,
    AreaEvaluationState,
    AreaSupportState,
    AssessmentAreaCoverage,
    AssessmentCoverage,
    AssessmentCoverageScope,
    AssessmentCoverageTotals,
    CoverageDerivationStatus,
    CoverageMetric,
    CoverageMetricId,
    CoverageStatus,
    assessment_coverage_to_json,
)


# Pack coverage area status → evaluation/support mapping.
_PACK_STATUS_MAP = {
    "measured": (AreaSupportState.SUPPORTED, AreaEvaluationState.EVALUATED),
    "partial": (
        AreaSupportState.PARTIALLY_SUPPORTED,
        AreaEvaluationState.PARTIALLY_EVALUATED,
    ),
    "unsupported": (AreaSupportState.UNSUPPORTED, AreaEvaluationState.NOT_APPLICABLE),
    "not_applicable": (
        AreaSupportState.NOT_APPLICABLE,
        AreaEvaluationState.NOT_APPLICABLE,
    ),
    "unknown": (AreaSupportState.UNAVAILABLE, AreaEvaluationState.UNAVAILABLE),
}

_DISABLED_PACK_STATUSES = {"disabled", "not_requested"}
_UNAVAILABLE_PACK_STATUSES = {"failed", "not_applicable"}
_INSUFFICIENT_PACK_STATUSES = {"insufficient_evidence"}
_PARTIAL_PACK_STATUSES = {"partially_succeeded"}
_COMPLETE_PACK_STATUSES = {"succeeded", "inventory_generated"}


def derive_assessment_coverage(
    *,
    head_id: str,
    pack_id: str | None = None,
    pack_status: str | None = None,
    activated: bool | None = None,
    pack_section: Mapping[str, Any] | None = None,
    contributing_head_coverage: Sequence[AssessmentCoverage] = (),
    limitations: Sequence[str] = (),
) -> AssessmentCoverage:
    """Derive canonical Assessment Coverage for one head."""

    status_token = str(pack_status or "").strip().lower()
    is_activated = bool(activated) if activated is not None else status_token not in {
        "",
        *_DISABLED_PACK_STATUSES,
        *_UNAVAILABLE_PACK_STATUSES,
    }
    limit_set = {str(item).strip() for item in limitations if str(item).strip()}
    declared = declared_areas_for_head(head_id)

    if status_token in _DISABLED_PACK_STATUSES or activated is False:
        return AssessmentCoverage(
            status=CoverageStatus.DISABLED,
            scope=AssessmentCoverageScope(
                head_id=head_id,
                pack_id=pack_id,
                activated=False,
                support_summary="disabled",
            ),
            areas=_disabled_areas(declared),
            totals=_totals_from_areas(_disabled_areas(declared)),
            metrics=(),
            limitations=tuple(
                sorted({*limit_set, "Assessment head was disabled for this run."})
            ),
            derivation_status=CoverageDerivationStatus.DERIVED,
        )

    if status_token in _UNAVAILABLE_PACK_STATUSES and status_token == "not_applicable":
        return AssessmentCoverage(
            status=CoverageStatus.NOT_APPLICABLE,
            scope=AssessmentCoverageScope(
                head_id=head_id,
                pack_id=pack_id,
                activated=False,
                support_summary="not_applicable",
            ),
            areas=_not_applicable_areas(declared),
            totals=_totals_from_areas(_not_applicable_areas(declared)),
            metrics=(),
            limitations=tuple(
                sorted({*limit_set, "Assessment head is not applicable for this repository."})
            ),
            derivation_status=CoverageDerivationStatus.DERIVED,
        )

    if status_token == "failed" or (
        pack_section is None and status_token in _UNAVAILABLE_PACK_STATUSES
    ):
        return AssessmentCoverage.unavailable(
            head_id=head_id,
            pack_id=pack_id,
            activated=is_activated,
            limitations=tuple(
                sorted({*limit_set, "Assessment coverage unavailable for this head."})
            ),
        )

    if head_id == "modernization_assessment":
        return _modernization_coverage(
            head_id=head_id,
            pack_id=pack_id or "roadmap",
            pack_section=pack_section,
            contributing=contributing_head_coverage,
            limitations=limit_set,
            activated=is_activated,
            pack_status=status_token,
        )

    if head_id == "technology_inventory":
        return _inventory_coverage(
            head_id=head_id,
            pack_id=pack_id or "technology",
            pack_section=pack_section,
            limitations=limit_set,
            activated=is_activated,
            pack_status=status_token,
            declared=declared,
        )

    return _pack_section_coverage(
        head_id=head_id,
        pack_id=pack_id,
        pack_section=pack_section,
        limitations=limit_set,
        activated=is_activated,
        pack_status=status_token,
        declared=declared,
    )


def build_assessment_coverage_map(
    *,
    pack_sections: Mapping[str, Mapping[str, Any] | None] | None = None,
    activation: Mapping[str, Any] | None = None,
    technologies_present: bool = False,
    contributing_for_modernization: Sequence[str] = (),
) -> dict[str, dict[str, Any]]:
    """Build additive ``assessment.assessment_coverage`` keyed by head id."""

    packs = pack_sections or {}
    assessed = {
        str(item).strip().lower()
        for item in (activation or {}).get("assessed_packs") or ()
        if str(item).strip()
    }
    not_assessed = {
        str(item[0] if isinstance(item, (list, tuple)) else item).strip().lower()
        for item in (activation or {}).get("not_assessed_packs") or ()
        if item
    }

    head_pack = {
        "technology_inventory": None,
        "architecture_intelligence": "architecture",
        "technical_debt_intelligence": "technical_debt",
        "dependency_intelligence": "dependency",
        "security_intelligence": "security",
        "cloud_readiness": "cloud",
        "ai_readiness": "ai_readiness",
        "testing": "testing",
        "performance": "performance",
        "modernization_assessment": "roadmap",
    }

    out: dict[str, AssessmentCoverage] = {}
    for head_id, pack_key in head_pack.items():
        section = packs.get(pack_key) if pack_key else None
        if head_id == "technology_inventory" and section is None and technologies_present:
            section = {"status": "inventory_generated"}
        pack_status = None
        if isinstance(section, Mapping):
            pack_status = str(section.get("status") or "").strip().lower() or None
        enabled = None
        if pack_key:
            if pack_key in assessed:
                enabled = True
            elif pack_key in not_assessed:
                enabled = False
        if head_id == "technology_inventory":
            enabled = True if technologies_present or section else enabled

        coverage = derive_assessment_coverage(
            head_id=head_id,
            pack_id=pack_key,
            pack_status=pack_status,
            activated=enabled,
            pack_section=section if isinstance(section, Mapping) else None,
            contributing_head_coverage=tuple(
                out[item]
                for item in contributing_for_modernization
                if item in out
            )
            if head_id == "modernization_assessment"
            else (),
            limitations=_section_limitations(section if isinstance(section, Mapping) else None),
        )
        out[head_id] = coverage

    # Modernization second pass with all contributing heads.
    if "modernization_assessment" in out:
        contributors = tuple(
            coverage
            for head_id, coverage in out.items()
            if head_id != "modernization_assessment"
            and coverage.status
            not in {CoverageStatus.DISABLED, CoverageStatus.NOT_APPLICABLE}
        )
        section = packs.get("roadmap")
        out["modernization_assessment"] = derive_assessment_coverage(
            head_id="modernization_assessment",
            pack_id="roadmap",
            pack_status=(
                str(section.get("status") or "").strip().lower()
                if isinstance(section, Mapping)
                else None
            ),
            activated=True,
            pack_section=section if isinstance(section, Mapping) else None,
            contributing_head_coverage=contributors,
            limitations=_section_limitations(section if isinstance(section, Mapping) else None),
        )

    return {
        key: assessment_coverage_to_json(value)
        for key, value in sorted(out.items(), key=lambda pair: pair[0])
    }


def coverage_summary_rows(coverage: AssessmentCoverage) -> tuple[tuple[str, str, str, str], ...]:
    """Customer-facing CCL rows with numerator/denominator (no false percentages)."""

    rows: list[tuple[str, str, str, str]] = []
    totals = coverage.totals
    applicable = totals.applicable_area_count
    evaluated = totals.evaluated_area_count + totals.partially_evaluated_area_count
    if applicable > 0:
        rows.append(
            (
                "Supported areas evaluated",
                coverage.status.value.replace("_", " "),
                f"{evaluated} of {applicable} supported areas evaluated",
                "",
            )
        )
    if totals.candidate_count is not None and totals.candidate_count > 0:
        processed = (totals.successfully_processed_count or 0) + (
            totals.partially_processed_count or 0
        )
        rows.append(
            (
                "Candidates processed",
                coverage.status.value.replace("_", " "),
                f"{processed} of {totals.candidate_count} candidates processed",
                "",
            )
        )
    if totals.eligible_rule_count is not None and totals.eligible_rule_count > 0:
        rows.append(
            (
                "Eligible rules executed",
                coverage.status.value.replace("_", " "),
                f"{totals.executed_rule_count or 0} of {totals.eligible_rule_count} "
                "eligible rules executed",
                "",
            )
        )
    if not rows:
        rows.append(
            (
                "Assessment coverage",
                coverage.status.value.replace("_", " "),
                coverage.status.value.replace("_", " ").title(),
                coverage.limitations[0] if coverage.limitations else "",
            )
        )
    return tuple(rows)


def _pack_section_coverage(
    *,
    head_id: str,
    pack_id: str | None,
    pack_section: Mapping[str, Any] | None,
    limitations: set[str],
    activated: bool,
    pack_status: str,
    declared: tuple[DeclaredAssessmentArea, ...],
) -> AssessmentCoverage:
    pack_areas = _extract_pack_areas(pack_section)
    execution = _extract_execution(pack_section)
    evidence = _extract_evidence_counts(pack_section, head_id=head_id)

    areas: list[AssessmentAreaCoverage] = []
    for declared_area in declared:
        pack_area = pack_areas.get(declared_area.area_id)
        if declared_area.claim_state is AreaClaimState.NOT_CLAIMED:
            support = AreaSupportState.UNSUPPORTED
            evaluation = AreaEvaluationState.NOT_APPLICABLE
            area_limits = (
                "Area is not claimed by the current assessment methodology.",
            )
            if pack_area:
                status = str(pack_area.get("status") or "").strip().lower()
                if status == "unsupported":
                    area_limits = ("Area remains unsupported.",)
            areas.append(
                AssessmentAreaCoverage(
                    area_id=declared_area.area_id,
                    title=declared_area.title,
                    claim_state=declared_area.claim_state,
                    support_state=support,
                    evaluation_state=evaluation,
                    limitations=area_limits,
                )
            )
            continue

        if pack_area is None:
            # Declared but no pack measurement — provisional evaluation state.
            if pack_status in _INSUFFICIENT_PACK_STATUSES:
                evaluation = AreaEvaluationState.INSUFFICIENT_EVIDENCE
                support = (
                    AreaSupportState.PARTIALLY_SUPPORTED
                    if declared_area.claim_state is AreaClaimState.PARTIAL
                    else AreaSupportState.SUPPORTED
                )
            elif pack_status in _COMPLETE_PACK_STATUSES:
                evaluation = AreaEvaluationState.EVALUATED
                support = (
                    AreaSupportState.PARTIALLY_SUPPORTED
                    if declared_area.claim_state is AreaClaimState.PARTIAL
                    else AreaSupportState.SUPPORTED
                )
            elif pack_status in _PARTIAL_PACK_STATUSES:
                evaluation = AreaEvaluationState.PARTIALLY_EVALUATED
                support = AreaSupportState.PARTIALLY_SUPPORTED
            elif not activated:
                evaluation = AreaEvaluationState.DISABLED
                support = AreaSupportState.UNAVAILABLE
            else:
                evaluation = AreaEvaluationState.NOT_EVALUATED
                support = (
                    AreaSupportState.PARTIALLY_SUPPORTED
                    if declared_area.claim_state is AreaClaimState.PARTIAL
                    else AreaSupportState.SUPPORTED
                )
            area_limits: tuple[str, ...] = ()
            if declared_area.claim_state is AreaClaimState.PARTIAL:
                area_limits = ("Area is only partially claimed by methodology.",)
            areas.append(
                AssessmentAreaCoverage(
                    area_id=declared_area.area_id,
                    title=declared_area.title,
                    claim_state=declared_area.claim_state,
                    support_state=support,
                    evaluation_state=evaluation,
                    eligible_rule_count=execution.get("eligible"),
                    executed_rule_count=execution.get("executed")
                    if "rule" in declared_area.area_id
                    else None,
                    limitations=area_limits,
                )
            )
            continue

        status = str(pack_area.get("status") or "unknown").strip().lower()
        support, evaluation = _PACK_STATUS_MAP.get(
            status,
            (AreaSupportState.UNAVAILABLE, AreaEvaluationState.UNAVAILABLE),
        )
        if declared_area.claim_state is AreaClaimState.PARTIAL and support is AreaSupportState.SUPPORTED:
            support = AreaSupportState.PARTIALLY_SUPPORTED
        area_limits = tuple(
            str(item).strip()
            for item in (pack_area.get("limitations") or ())
            if str(item).strip()
        )
        if declared_area.claim_state is AreaClaimState.PARTIAL and not area_limits:
            area_limits = ("Area is only partially claimed by methodology.",)
        areas.append(
            AssessmentAreaCoverage(
                area_id=declared_area.area_id,
                title=declared_area.title,
                claim_state=declared_area.claim_state,
                support_state=support,
                evaluation_state=evaluation,
                evidence_available=_truthy(pack_area.get("evidence_available")),
                eligible_rule_count=_int_or_none(pack_area.get("denominator"))
                if "rule" in declared_area.area_id
                else execution.get("eligible"),
                executed_rule_count=_int_or_none(pack_area.get("numerator"))
                if "rule" in declared_area.area_id
                else execution.get("executed"),
                limitations=area_limits,
            )
        )

    area_tuple = tuple(areas)
    totals = _totals_from_areas(
        area_tuple,
        candidate_count=evidence.get("candidate_count"),
        inspected_candidate_count=evidence.get("inspected_candidate_count"),
        successfully_processed_count=evidence.get("successfully_processed_count"),
        partially_processed_count=evidence.get("partially_processed_count"),
        failed_count=evidence.get("failed_count"),
        skipped_count=evidence.get("skipped_count"),
        eligible_rule_count=execution.get("eligible"),
        executed_rule_count=execution.get("executed"),
        unavailable_rule_count=execution.get("unavailable"),
    )
    metrics = _build_metrics(totals)
    status = _status_from_pack_and_totals(pack_status, totals, activated=activated)
    derivation = (
        CoverageDerivationStatus.MEASURED
        if pack_areas or execution.get("eligible") is not None
        else CoverageDerivationStatus.PROVISIONAL
    )
    if status in {CoverageStatus.UNAVAILABLE, CoverageStatus.DISABLED}:
        derivation = CoverageDerivationStatus.UNAVAILABLE
    out_limits = set(limitations)
    if any(area.claim_state is AreaClaimState.PARTIAL for area in area_tuple):
        out_limits.add("One or more methodology areas are only partially claimed.")
    if head_id in {"cloud_readiness", "ai_readiness", "testing", "performance"}:
        out_limits.add(
            "Repository observation coverage does not imply live runtime, "
            "organizational, or external service coverage."
        )
    return AssessmentCoverage(
        status=status,
        scope=AssessmentCoverageScope(
            head_id=head_id,
            pack_id=pack_id,
            activated=activated,
            support_summary=status.value,
        ),
        areas=area_tuple,
        totals=totals,
        metrics=metrics,
        limitations=tuple(sorted(out_limits)),
        derivation_status=derivation,
    )


def _inventory_coverage(
    *,
    head_id: str,
    pack_id: str,
    pack_section: Mapping[str, Any] | None,
    limitations: set[str],
    activated: bool,
    pack_status: str,
    declared: tuple[DeclaredAssessmentArea, ...],
) -> AssessmentCoverage:
    status_token = pack_status or (
        str((pack_section or {}).get("status") or "").strip().lower()
        if pack_section
        else ""
    )
    if status_token in {"inventory_unavailable", "unavailable", "failed"}:
        return AssessmentCoverage.unavailable(
            head_id=head_id,
            pack_id=pack_id,
            activated=activated,
            limitations=tuple(
                sorted({*limitations, "Technology inventory evidence is unavailable."})
            ),
        )
    if status_token in {"legacy_inventory", "legacy"}:
        return AssessmentCoverage.unavailable(
            head_id=head_id,
            pack_id=pack_id,
            activated=activated,
            limitations=tuple(
                sorted({*limitations, "Legacy inventory coverage is unavailable."})
            ),
        )
    partial = status_token in {"partial_inventory", "partial", "partially_succeeded"}
    areas: list[AssessmentAreaCoverage] = []
    for item in declared:
        if item.claim_state is AreaClaimState.NOT_CLAIMED:
            areas.append(
                AssessmentAreaCoverage(
                    area_id=item.area_id,
                    title=item.title,
                    claim_state=item.claim_state,
                    support_state=AreaSupportState.UNSUPPORTED,
                    evaluation_state=AreaEvaluationState.NOT_APPLICABLE,
                    limitations=("Area is not claimed by the inventory methodology.",),
                )
            )
            continue
        evaluation = (
            AreaEvaluationState.PARTIALLY_EVALUATED
            if partial or item.claim_state is AreaClaimState.PARTIAL
            else AreaEvaluationState.EVALUATED
        )
        support = (
            AreaSupportState.PARTIALLY_SUPPORTED
            if item.claim_state is AreaClaimState.PARTIAL or partial
            else AreaSupportState.SUPPORTED
        )
        area_limits = ()
        if item.claim_state is AreaClaimState.PARTIAL:
            area_limits = ("Inventory area is only partially claimed.",)
        if item.area_id == "version_availability":
            area_limits = (
                "Missing version facts do not imply missing technology detection.",
            )
        areas.append(
            AssessmentAreaCoverage(
                area_id=item.area_id,
                title=item.title,
                claim_state=item.claim_state,
                support_state=support,
                evaluation_state=evaluation,
                evidence_available=True,
                limitations=area_limits,
            )
        )
    area_tuple = tuple(areas)
    totals = _totals_from_areas(area_tuple)
    status = CoverageStatus.PARTIAL if partial else CoverageStatus.COMPLETE
    return AssessmentCoverage(
        status=status,
        scope=AssessmentCoverageScope(
            head_id=head_id,
            pack_id=pack_id,
            activated=activated,
            support_summary=status.value,
        ),
        areas=area_tuple,
        totals=totals,
        metrics=_build_metrics(totals),
        limitations=tuple(
            sorted(
                {
                    *limitations,
                    "Technology Inventory coverage reflects inventory evidence, "
                    "not repository health.",
                }
            )
        ),
        derivation_status=CoverageDerivationStatus.DERIVED,
    )


def _modernization_coverage(
    *,
    head_id: str,
    pack_id: str,
    pack_section: Mapping[str, Any] | None,
    contributing: Sequence[AssessmentCoverage],
    limitations: set[str],
    activated: bool,
    pack_status: str,
) -> AssessmentCoverage:
    declared = declared_areas_for_head(head_id)
    eligible = [
        item
        for item in contributing
        if item.status
        not in {
            CoverageStatus.DISABLED,
            CoverageStatus.NOT_APPLICABLE,
            CoverageStatus.UNAVAILABLE,
        }
    ]
    unavailable = [
        item
        for item in contributing
        if item.status in {CoverageStatus.UNAVAILABLE, CoverageStatus.INSUFFICIENT_EVIDENCE}
    ]
    if not contributing:
        return AssessmentCoverage.unavailable(
            head_id=head_id,
            pack_id=pack_id,
            activated=activated,
            limitations=tuple(
                sorted({*limitations, "No contributing assessment heads were available."})
            ),
        )

    initiative_count = 0
    if isinstance(pack_section, Mapping):
        initiatives = pack_section.get("initiatives") or []
        initiative_count = len(initiatives) if isinstance(initiatives, list) else int(
            pack_section.get("initiatives_total") or 0
        )

    areas: list[AssessmentAreaCoverage] = []
    for item in declared:
        if item.area_id == "contributing_heads":
            areas.append(
                AssessmentAreaCoverage(
                    area_id=item.area_id,
                    title=item.title,
                    claim_state=item.claim_state,
                    support_state=AreaSupportState.SUPPORTED,
                    evaluation_state=(
                        AreaEvaluationState.EVALUATED
                        if eligible
                        else AreaEvaluationState.INSUFFICIENT_EVIDENCE
                    ),
                    candidate_count=len(contributing),
                    processed_count=len(eligible),
                    failed_count=len(unavailable),
                    limitations=(
                        "Modernization coverage cannot exceed contributing head coverage.",
                    ),
                )
            )
        elif item.area_id == "roadmap_chain":
            areas.append(
                AssessmentAreaCoverage(
                    area_id=item.area_id,
                    title=item.title,
                    claim_state=item.claim_state,
                    support_state=AreaSupportState.PARTIALLY_SUPPORTED,
                    evaluation_state=(
                        AreaEvaluationState.PARTIALLY_EVALUATED
                        if initiative_count or eligible
                        else AreaEvaluationState.NOT_EVALUATED
                    ),
                    processed_count=initiative_count if initiative_count else None,
                    limitations=(
                        "Modernization does not invent a numeric ratio from actions.",
                        "Area is only partially claimed by methodology.",
                    ),
                )
            )
        else:
            areas.append(
                AssessmentAreaCoverage(
                    area_id=item.area_id,
                    title=item.title,
                    claim_state=item.claim_state,
                    support_state=AreaSupportState.SUPPORTED,
                    evaluation_state=(
                        AreaEvaluationState.EVALUATED
                        if eligible
                        else AreaEvaluationState.NOT_EVALUATED
                    ),
                    limitations=(),
                )
            )

    # Cap status by weakest contributing coverage.
    contributor_statuses = [item.status for item in eligible] or [
        item.status for item in contributing
    ]
    status = _weakest_coverage_status(contributor_statuses)
    if pack_status in {"legacy"}:
        status = CoverageStatus.UNAVAILABLE
    totals = _totals_from_areas(
        tuple(areas),
        candidate_count=len(contributing),
        successfully_processed_count=len(eligible),
        failed_count=len(unavailable),
    )
    # No synthetic action-based ratio metrics for modernization.
    metrics = (
        CoverageMetric.build(
            metric_id=CoverageMetricId.AREA_COVERAGE,
            numerator=totals.evaluated_area_count + totals.partially_evaluated_area_count,
            denominator=totals.applicable_area_count,
        ),
    )
    return AssessmentCoverage(
        status=status,
        scope=AssessmentCoverageScope(
            head_id=head_id,
            pack_id=pack_id,
            activated=activated,
            support_summary=status.value,
        ),
        areas=tuple(areas),
        totals=totals,
        metrics=metrics,
        limitations=tuple(
            sorted(
                {
                    *limitations,
                    "Modernization coverage is synthesized from contributing heads.",
                    "Modernization coverage cannot exceed contributing head coverage.",
                }
            )
        ),
        derivation_status=CoverageDerivationStatus.DERIVED,
    )


def _extract_pack_areas(
    section: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(section, Mapping):
        return {}
    coverage = section.get("coverage") or section.get("coverage_summary") or {}
    areas = ()
    if isinstance(coverage, Mapping):
        areas = coverage.get("areas") or ()
    out: dict[str, Mapping[str, Any]] = {}
    for item in areas:
        if isinstance(item, Mapping) and item.get("area_id"):
            out[str(item["area_id"])] = item
    return out


def _extract_execution(section: Mapping[str, Any] | None) -> dict[str, int | None]:
    if not isinstance(section, Mapping):
        return {"eligible": None, "executed": None, "unavailable": None}
    summary = (
        section.get("execution_summary")
        or section.get("execution")
        or section.get("summary")
        or {}
    )
    if not isinstance(summary, Mapping):
        summary = {}
    eligible = _first_int(
        summary,
        (
            "rules_planned",
            "architecture_rules_planned",
            "security_rules_planned",
            "dependency_rules_planned",
            "technical_debt_rules_planned",
            "cloud_rules_planned",
            "ai_readiness_rules_planned",
            "testing_rules_planned",
            "performance_rules_planned",
            "eligible_rule_count",
        ),
    )
    executed = _first_int(summary, ("rules_executed", "executed_rule_count"))
    unavailable = _first_int(
        summary,
        ("rules_insufficient_evidence", "rules_failed", "unavailable_rule_count"),
    )
    return {"eligible": eligible, "executed": executed, "unavailable": unavailable}


def _extract_evidence_counts(
    section: Mapping[str, Any] | None,
    *,
    head_id: str,
) -> dict[str, int | None]:
    if not isinstance(section, Mapping):
        return {}
    evidence = (
        section.get("evidence_coverage")
        or section.get("evidence_summary")
        or section.get("inventory")
        or {}
    )
    if not isinstance(evidence, Mapping):
        evidence = {}
    # Also accept nested under section keys used by reports.
    for key in (
        "repository_sensitive_coverage",
        "dependency_evidence_coverage",
        "testing_evidence_coverage",
        "cloud_evidence_coverage",
        "ai_readiness_evidence_coverage",
        "performance_evidence_coverage",
    ):
        nested = section.get(key)
        if isinstance(nested, Mapping):
            evidence = {**evidence, **nested}
    return {
        "candidate_count": _first_int(
            evidence,
            (
                "candidate_files_discovered",
                "candidate_count",
                "manifests_discovered",
                "candidate_test_files_discovered",
            ),
        ),
        "inspected_candidate_count": _first_int(
            evidence,
            ("candidate_files_inspected", "inspected_candidate_count", "manifests_parsed"),
        ),
        "successfully_processed_count": _first_int(
            evidence,
            (
                "candidate_files_parsed",
                "successfully_processed_count",
                "manifests_parsed",
                "parsed_count",
            ),
        ),
        "partially_processed_count": _first_int(
            evidence,
            (
                "candidate_files_partially_parsed",
                "partially_processed_count",
                "manifests_partially_parsed",
            ),
        ),
        "failed_count": _first_int(
            evidence,
            (
                "candidate_files_malformed",
                "failed_count",
                "manifests_failed",
                "parse_failures",
            ),
        ),
        "skipped_count": _first_int(
            evidence,
            ("candidate_files_skipped", "skipped_count", "unsupported_files"),
        ),
    }


def _totals_from_areas(
    areas: Sequence[AssessmentAreaCoverage],
    **counts: int | None,
) -> AssessmentCoverageTotals:
    declared = len(areas)
    supported = sum(
        1
        for item in areas
        if item.claim_state is AreaClaimState.CLAIMED
        and item.support_state
        in {AreaSupportState.SUPPORTED, AreaSupportState.PARTIALLY_SUPPORTED}
    )
    partial_supported = sum(
        1
        for item in areas
        if item.claim_state is AreaClaimState.PARTIAL
        or item.support_state is AreaSupportState.PARTIALLY_SUPPORTED
    )
    unsupported = sum(
        1 for item in areas if item.support_state is AreaSupportState.UNSUPPORTED
    )
    applicable = sum(
        1
        for item in areas
        if item.claim_state in {AreaClaimState.CLAIMED, AreaClaimState.PARTIAL}
        and item.support_state
        not in {
            AreaSupportState.UNSUPPORTED,
            AreaSupportState.NOT_APPLICABLE,
        }
    )
    evaluated = sum(
        1
        for item in areas
        if item.claim_state in {AreaClaimState.CLAIMED, AreaClaimState.PARTIAL}
        and item.evaluation_state is AreaEvaluationState.EVALUATED
    )
    partially_evaluated = sum(
        1
        for item in areas
        if item.claim_state in {AreaClaimState.CLAIMED, AreaClaimState.PARTIAL}
        and item.evaluation_state is AreaEvaluationState.PARTIALLY_EVALUATED
    )
    unevaluated = max(0, applicable - evaluated - partially_evaluated)
    return AssessmentCoverageTotals(
        declared_area_count=declared,
        supported_area_count=supported,
        partially_supported_area_count=partial_supported,
        unsupported_area_count=unsupported,
        applicable_area_count=applicable,
        evaluated_area_count=evaluated,
        partially_evaluated_area_count=partially_evaluated,
        unevaluated_area_count=unevaluated,
        candidate_count=counts.get("candidate_count"),
        inspected_candidate_count=counts.get("inspected_candidate_count"),
        successfully_processed_count=counts.get("successfully_processed_count"),
        partially_processed_count=counts.get("partially_processed_count"),
        failed_count=counts.get("failed_count"),
        skipped_count=counts.get("skipped_count"),
        eligible_rule_count=counts.get("eligible_rule_count"),
        executed_rule_count=counts.get("executed_rule_count"),
        unavailable_rule_count=counts.get("unavailable_rule_count"),
    )


def _build_metrics(totals: AssessmentCoverageTotals) -> tuple[CoverageMetric, ...]:
    metrics: list[CoverageMetric] = []
    metrics.append(
        CoverageMetric.build(
            metric_id=CoverageMetricId.AREA_COVERAGE,
            numerator=totals.evaluated_area_count + totals.partially_evaluated_area_count,
            denominator=totals.applicable_area_count,
        )
    )
    if totals.candidate_count is not None:
        processed = (totals.successfully_processed_count or 0) + (
            totals.partially_processed_count or 0
        )
        metrics.append(
            CoverageMetric.build(
                metric_id=CoverageMetricId.CANDIDATE_PROCESSING,
                numerator=processed,
                denominator=totals.candidate_count,
            )
        )
    if totals.eligible_rule_count is not None:
        metrics.append(
            CoverageMetric.build(
                metric_id=CoverageMetricId.RULE_EXECUTION,
                numerator=totals.executed_rule_count or 0,
                denominator=totals.eligible_rule_count,
            )
        )
    return tuple(metrics)


def _status_from_pack_and_totals(
    pack_status: str,
    totals: AssessmentCoverageTotals,
    *,
    activated: bool,
) -> CoverageStatus:
    if not activated or pack_status in _DISABLED_PACK_STATUSES:
        return CoverageStatus.DISABLED
    if pack_status in _INSUFFICIENT_PACK_STATUSES:
        return CoverageStatus.INSUFFICIENT_EVIDENCE
    if pack_status == "not_applicable":
        return CoverageStatus.NOT_APPLICABLE
    if pack_status == "failed":
        return CoverageStatus.UNAVAILABLE
    if totals.applicable_area_count == 0:
        return CoverageStatus.UNAVAILABLE
    if totals.unevaluated_area_count == 0 and totals.partially_evaluated_area_count == 0:
        return CoverageStatus.COMPLETE
    if totals.evaluated_area_count == 0 and totals.partially_evaluated_area_count == 0:
        return CoverageStatus.INSUFFICIENT_EVIDENCE
    return CoverageStatus.PARTIAL


def _weakest_coverage_status(statuses: Sequence[CoverageStatus]) -> CoverageStatus:
    rank = {
        CoverageStatus.UNAVAILABLE: 0,
        CoverageStatus.DISABLED: 1,
        CoverageStatus.INSUFFICIENT_EVIDENCE: 2,
        CoverageStatus.NOT_APPLICABLE: 3,
        CoverageStatus.PARTIAL: 4,
        CoverageStatus.COMPLETE: 5,
    }
    if not statuses:
        return CoverageStatus.UNAVAILABLE
    return min(statuses, key=lambda item: rank[item])


def _disabled_areas(
    declared: Sequence[DeclaredAssessmentArea],
) -> tuple[AssessmentAreaCoverage, ...]:
    return tuple(
        AssessmentAreaCoverage(
            area_id=item.area_id,
            title=item.title,
            claim_state=item.claim_state,
            support_state=(
                AreaSupportState.UNSUPPORTED
                if item.claim_state is AreaClaimState.NOT_CLAIMED
                else AreaSupportState.SUPPORTED
            ),
            evaluation_state=AreaEvaluationState.DISABLED,
            limitations=("Head disabled.",),
        )
        for item in declared
        if item.claim_state is not AreaClaimState.NOT_CLAIMED
    )


def _not_applicable_areas(
    declared: Sequence[DeclaredAssessmentArea],
) -> tuple[AssessmentAreaCoverage, ...]:
    return tuple(
        AssessmentAreaCoverage(
            area_id=item.area_id,
            title=item.title,
            claim_state=item.claim_state,
            support_state=AreaSupportState.NOT_APPLICABLE,
            evaluation_state=AreaEvaluationState.NOT_APPLICABLE,
            limitations=("Head not applicable.",),
        )
        for item in declared
        if item.claim_state is not AreaClaimState.NOT_CLAIMED
    )


def _section_limitations(section: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(section, Mapping):
        return ()
    return tuple(
        str(item).strip() for item in (section.get("limitations") or ()) if str(item).strip()
    )


def _first_int(mapping: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            try:
                value = int(mapping[key])
            except (TypeError, ValueError):
                continue
            if value >= 0:
                return value
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _truthy(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return None
