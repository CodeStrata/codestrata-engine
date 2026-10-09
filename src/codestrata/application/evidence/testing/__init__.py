"""E08.2 testing evidence: M19 association, M20 skipped tests, M21 CI gaps."""

from codestrata.application.evidence.testing.capability import (
    CAP_M19,
    CAP_M20,
    CAP_M21,
    capability_manifests,
)
from codestrata.application.evidence.testing.consumer import consume_envelope
from codestrata.application.evidence.testing.envelope import (
    TestingEnvelope,
    seal_testing_envelope,
)
from codestrata.application.evidence.testing.models import TestingEvidence
from codestrata.application.evidence.testing.projections import (
    project_testing_html,
    project_testing_json,
    project_testing_sarif,
)
from codestrata.application.evidence.testing.service import TestingEvidenceService

__all__ = [
    "CAP_M19",
    "CAP_M20",
    "CAP_M21",
    "TestingEnvelope",
    "TestingEvidence",
    "TestingEvidenceService",
    "capability_manifests",
    "consume_envelope",
    "project_testing_html",
    "project_testing_json",
    "project_testing_sarif",
    "seal_testing_envelope",
]
