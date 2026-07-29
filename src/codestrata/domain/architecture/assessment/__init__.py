"""Architecture assessment domain package (Phase 4.2.4)."""

from codestrata.domain.architecture.assessment.enums import (
    ArchitectureAssessmentStatus,
    ArchitectureLimitationCategory,
    CoverageAreaStatus,
    CoverageMaturity,
    TraceabilityRelation,
)
from codestrata.domain.architecture.assessment.identifiers import (
    ARCHITECTURE_ASSESSMENT_FILENAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_configuration_fingerprint,
    build_limitation_id,
    build_strength_id,
    build_trace_edge_id,
)
from codestrata.domain.architecture.assessment.models import (
    ArchitectureAssessmentSection,
    ArchitectureCoverageArea,
    ArchitectureCoverageSummary,
    ArchitectureExecutionSummary,
    ArchitectureFindingReference,
    ArchitectureLimitation,
    ArchitectureStrength,
    ArchitectureTraceabilityEdge,
    ArchitectureTraceabilityIndex,
)

__all__ = [
    "ARCHITECTURE_ASSESSMENT_FILENAME",
    "SECTION_ID",
    "SECTION_SCHEMA_VERSION",
    "ArchitectureAssessmentSection",
    "ArchitectureAssessmentStatus",
    "ArchitectureCoverageArea",
    "ArchitectureCoverageSummary",
    "ArchitectureExecutionSummary",
    "ArchitectureFindingReference",
    "ArchitectureLimitation",
    "ArchitectureLimitationCategory",
    "ArchitectureStrength",
    "ArchitectureTraceabilityEdge",
    "ArchitectureTraceabilityIndex",
    "CoverageAreaStatus",
    "CoverageMaturity",
    "TraceabilityRelation",
    "build_configuration_fingerprint",
    "build_limitation_id",
    "build_strength_id",
    "build_trace_edge_id",
]
