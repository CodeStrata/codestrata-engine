"""Capability coverage records for inventory facts (M01–M04)."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.evidence.inventory.facts import (
    CAP_M01,
    CAP_M02,
    CAP_M03,
    CAP_M04,
    INVENTORY_EMITTER_VERSION,
    CapabilityApplicability,
    CapabilityCoverageRecord,
    ExtractionStatus,
    SurfaceDeclarationFact,
)
from codestrata.application.evidence.inventory.models import (
    ClassificationMetric,
    InventoryMetricStatus,
)


def _ratio(evaluated: int, eligible: int) -> tuple[str | None, str | None]:
    if eligible <= 0:
        return None, "zero_eligible"
    return f"{(evaluated / eligible):.6f}", None


def m01_coverage(metric: ClassificationMetric) -> CapabilityCoverageRecord:
    if metric.status is InventoryMetricStatus.NOT_APPLICABLE:
        return CapabilityCoverageRecord(
            capability_id=CAP_M01,
            version=INVENTORY_EMITTER_VERSION,
            scope="repository",
            applicability=CapabilityApplicability.NOT_APPLICABLE,
            evaluated=0,
            eligible=0,
            coverage_ratio=None,
            coverage_reason="zero_eligible_files",
            limitations=("classification_metric_only_no_health_verdict",),
        )
    ratio, reason = _ratio(metric.numerator, metric.denominator)
    return CapabilityCoverageRecord(
        capability_id=CAP_M01,
        version=INVENTORY_EMITTER_VERSION,
        scope="eligible_source_test_files",
        applicability=CapabilityApplicability.APPLICABLE,
        evaluated=metric.numerator,
        eligible=metric.denominator,
        excluded=metric.ignored_in_inventory,
        coverage_ratio=ratio,
        coverage_reason=reason,
        limitations=("detection_is_not_structural_support",),
    )


def m02_coverage(
    *,
    declaration_ids: Sequence[str],
    resolved_declaration_ids: Sequence[str],
    unknown_declaration_ids: Sequence[str],
    error_count: int,
    resolution_occurrence_count: int,
    unsupported_manifest_count: int = 0,
) -> CapabilityCoverageRecord:
    """Coverage unit is declaration IDs; occurrences are reported as a limitation."""

    eligible = len(tuple(dict.fromkeys(declaration_ids)))
    unknown = len(tuple(dict.fromkeys(unknown_declaration_ids)))
    resolved = len(tuple(dict.fromkeys(resolved_declaration_ids)))
    if eligible == 0 and unsupported_manifest_count > 0:
        return CapabilityCoverageRecord(
            capability_id=CAP_M02,
            version=INVENTORY_EMITTER_VERSION,
            scope="dependency_declarations",
            applicability=CapabilityApplicability.UNKNOWN,
            evaluated=0,
            eligible=0,
            unknown=unsupported_manifest_count,
            error=error_count,
            coverage_ratio=None,
            coverage_reason="unsupported_manifest_unknown_depth",
            limitations=(
                "parseable_unsupported_ecosystem_is_detection_only",
                "missing_lock_is_not_resolved_absence",
                f"resolution_occurrences={resolution_occurrence_count}",
            ),
        )
    if eligible == 0:
        return CapabilityCoverageRecord(
            capability_id=CAP_M02,
            version=INVENTORY_EMITTER_VERSION,
            scope="dependency_declarations",
            applicability=CapabilityApplicability.NOT_APPLICABLE,
            evaluated=0,
            eligible=0,
            unknown=0,
            error=error_count,
            coverage_ratio=None,
            coverage_reason="no_declarations",
            limitations=(
                "missing_lock_is_not_resolved_absence",
                f"resolution_occurrences={resolution_occurrence_count}",
            ),
        )
    evaluated = resolved
    ratio, reason = _ratio(evaluated, eligible)
    return CapabilityCoverageRecord(
        capability_id=CAP_M02,
        version=INVENTORY_EMITTER_VERSION,
        scope="dependency_declarations",
        applicability=CapabilityApplicability.APPLICABLE,
        evaluated=evaluated,
        eligible=eligible,
        unknown=unknown,
        error=error_count,
        coverage_ratio=ratio,
        coverage_reason=reason,
        limitations=(
            "coverage_unit_is_declaration_id",
            f"resolution_occurrences={resolution_occurrence_count}",
            "missing_lock_is_not_resolved_absence",
        ),
    )


def m03_coverage(
    *,
    invocation_count: int,
    unresolved_count: int,
    documents: int,
) -> CapabilityCoverageRecord:
    if documents == 0:
        return CapabilityCoverageRecord(
            capability_id=CAP_M03,
            version=INVENTORY_EMITTER_VERSION,
            scope="ci_invocations",
            applicability=CapabilityApplicability.NOT_APPLICABLE,
            evaluated=0,
            eligible=0,
            coverage_ratio=None,
            coverage_reason="no_ci_documents",
            limitations=("configuration_is_not_execution",),
        )
    eligible = invocation_count
    evaluated = max(0, invocation_count - unresolved_count)
    ratio, reason = _ratio(evaluated, eligible) if eligible else (None, "unresolved_invocations")
    if eligible == 0:
        return CapabilityCoverageRecord(
            capability_id=CAP_M03,
            version=INVENTORY_EMITTER_VERSION,
            scope="ci_invocations",
            applicability=CapabilityApplicability.UNKNOWN,
            evaluated=0,
            eligible=0,
            unknown=1,
            coverage_ratio=None,
            coverage_reason="ci_present_without_parsed_invocations",
            limitations=("configuration_is_not_execution",),
        )
    return CapabilityCoverageRecord(
        capability_id=CAP_M03,
        version=INVENTORY_EMITTER_VERSION,
        scope="ci_invocations",
        applicability=CapabilityApplicability.APPLICABLE,
        evaluated=evaluated,
        eligible=eligible,
        unknown=unresolved_count,
        coverage_ratio=ratio,
        coverage_reason=reason,
        limitations=("configuration_is_not_execution",),
    )


def m04_coverage(
    surfaces: Sequence[SurfaceDeclarationFact],
    *,
    eligible_source_files: int,
    parse_failures: int,
    unknown_areas: int,
) -> CapabilityCoverageRecord:
    if eligible_source_files == 0 and not surfaces:
        return CapabilityCoverageRecord(
            capability_id=CAP_M04,
            version=INVENTORY_EMITTER_VERSION,
            scope="api_config_surfaces",
            applicability=CapabilityApplicability.NOT_APPLICABLE,
            evaluated=0,
            eligible=0,
            coverage_ratio=None,
            coverage_reason="no_eligible_source",
            limitations=("no_runtime_availability_score",),
        )
    complete = sum(
        1
        for item in surfaces
        if item.extraction_status is ExtractionStatus.COMPLETE
        and item.declaration_kind != "parse_failure"
    )
    unknown = (
        sum(1 for item in surfaces if item.extraction_status is ExtractionStatus.UNKNOWN)
        + unknown_areas
    )
    errors = (
        sum(1 for item in surfaces if item.extraction_status is ExtractionStatus.ERROR)
        + parse_failures
    )
    eligible = max(eligible_source_files, len(surfaces), 1 if surfaces else eligible_source_files)
    ratio, reason = _ratio(complete, eligible) if eligible else (None, "zero_eligible")
    return CapabilityCoverageRecord(
        capability_id=CAP_M04,
        version=INVENTORY_EMITTER_VERSION,
        scope="api_config_surfaces",
        applicability=CapabilityApplicability.APPLICABLE,
        evaluated=complete,
        eligible=eligible,
        unknown=unknown,
        error=errors,
        coverage_ratio=ratio,
        coverage_reason=reason,
        limitations=(
            "no_runtime_availability_score",
            "dynamic_or_unsupported_framework_is_unknown",
        ),
    )
