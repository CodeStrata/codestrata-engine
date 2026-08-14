"""Engine assessment_metadata 1.1 projector + gated emitter (Slice 20.8)."""

from __future__ import annotations

from codestrata.telemetry.assessment_metadata.diagnostics import (
    AssessmentMetadataEmissionDiagnostics,
)
from codestrata.telemetry.assessment_metadata.emitter import (
    emit_assessment_metadata_safely,
    emission_authorized,
    project_only,
)
from codestrata.telemetry.assessment_metadata.models import (
    AssessmentMetadataProjectionSource,
    AssessmentMetadataWireRequest,
    FindingProjectionRow,
    HeadConfidenceProjectionRow,
)
from codestrata.telemetry.assessment_metadata.policy import (
    CommunityAssessmentMetadataEmissionPolicy,
    authorized_assessment_metadata_emission_policy,
    default_assessment_metadata_emission_policy,
)
from codestrata.telemetry.assessment_metadata.projector import project_assessment_metadata
from codestrata.telemetry.assessment_metadata.source import (
    build_failure_projection_source,
    build_success_projection_source,
    new_assessment_id,
)
from codestrata.telemetry.assessment_metadata.transport import (
    CaptureAssessmentMetadataTransport,
    HttpAssessmentMetadataTransport,
)

__all__ = [
    "AssessmentMetadataEmissionDiagnostics",
    "AssessmentMetadataProjectionSource",
    "AssessmentMetadataWireRequest",
    "CaptureAssessmentMetadataTransport",
    "CommunityAssessmentMetadataEmissionPolicy",
    "FindingProjectionRow",
    "HeadConfidenceProjectionRow",
    "HttpAssessmentMetadataTransport",
    "authorized_assessment_metadata_emission_policy",
    "build_failure_projection_source",
    "build_success_projection_source",
    "default_assessment_metadata_emission_policy",
    "emit_assessment_metadata_safely",
    "emission_authorized",
    "new_assessment_id",
    "project_assessment_metadata",
    "project_only",
]
