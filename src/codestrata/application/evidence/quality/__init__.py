"""E08.1 structural quality evidence: M16 size/complexity, M17 nesting, M18 clones."""

from codestrata.application.evidence.quality.capability import (
    CAP_M16,
    CAP_M17,
    CAP_M18,
    capability_manifests,
)
from codestrata.application.evidence.quality.consumer import consume_envelope
from codestrata.application.evidence.quality.envelope import (
    QualityEnvelope,
    seal_quality_envelope,
)
from codestrata.application.evidence.quality.models import QualityEvidence
from codestrata.application.evidence.quality.projections import (
    project_quality_html,
    project_quality_json,
    project_quality_sarif,
)
from codestrata.application.evidence.quality.service import QualityEvidenceService

__all__ = [
    "CAP_M16",
    "CAP_M17",
    "CAP_M18",
    "QualityEnvelope",
    "QualityEvidence",
    "QualityEvidenceService",
    "capability_manifests",
    "consume_envelope",
    "project_quality_html",
    "project_quality_json",
    "project_quality_sarif",
    "seal_quality_envelope",
]
