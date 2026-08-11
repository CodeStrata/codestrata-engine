"""Report-level Evidence / Priority Action / Roadmap traceability (Epic 2 Slice 2.6+2.8)."""

from codestrata.reporting.traceability.evidence_index import (
    collect_assessment_evidence,
    serialize_evidence_index,
)
from codestrata.reporting.traceability.preservation import (
    CanonicalReportLoadError,
    assert_traceability_equivalent,
    classify_traceability_state,
    extract_assessment,
    load_report_document,
    lookup_entity,
    preserve_assessment_collections,
    schema_version_of,
    traceability_snapshot,
    validate_canonical_assessment,
)
from codestrata.reporting.traceability.priority_actions import (
    build_assessment_priority_actions,
    serialize_priority_actions,
)
from codestrata.reporting.traceability.roadmap import (
    build_assessment_roadmap_payload,
)
from codestrata.reporting.traceability.validator import (
    AssessmentTraceabilityError,
    validate_assessment_traceability,
)

__all__ = [
    "AssessmentTraceabilityError",
    "CanonicalReportLoadError",
    "assert_traceability_equivalent",
    "build_assessment_priority_actions",
    "build_assessment_roadmap_payload",
    "classify_traceability_state",
    "collect_assessment_evidence",
    "extract_assessment",
    "load_report_document",
    "lookup_entity",
    "preserve_assessment_collections",
    "schema_version_of",
    "serialize_evidence_index",
    "serialize_priority_actions",
    "traceability_snapshot",
    "validate_assessment_traceability",
    "validate_canonical_assessment",
]
