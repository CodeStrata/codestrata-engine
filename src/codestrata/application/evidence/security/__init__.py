"""E06.1 security evidence: YAML-backed M10/M11 envelopes and projections."""

from codestrata.application.evidence.security.capability import (
    CAP_M10,
    CAP_M11,
    capability_manifests,
)
from codestrata.application.evidence.security.consumer import consume_envelope
from codestrata.application.evidence.security.envelope import (
    SecurityEnvelope,
    seal_security_envelope,
)
from codestrata.application.evidence.security.metrics import count_metrics, unique_findings
from codestrata.application.evidence.security.projections import (
    project_security_html,
    project_security_json,
    project_security_sarif,
)

__all__ = [
    "CAP_M10",
    "CAP_M11",
    "SecurityEnvelope",
    "capability_manifests",
    "consume_envelope",
    "count_metrics",
    "project_security_html",
    "project_security_json",
    "project_security_sarif",
    "seal_security_envelope",
    "unique_findings",
]
