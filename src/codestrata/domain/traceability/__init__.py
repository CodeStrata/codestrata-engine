"""Shared Evidence and Traceability domain contracts.

``EvidenceRef`` is a lightweight traceability envelope. It is not the source of
truth for Aggregated* evidence, RuleEvidence payloads, static-analysis dumps,
or graph contents.
"""

from codestrata.domain.traceability.enums import (
    EvidenceCompleteness,
    EvidenceKind,
    EvidenceProductionMode,
    GraphKind,
    GraphReferenceKind,
    LocationKind,
    LocationPrecision,
    MeasurementAvailability,
    MeasurementComparisonResult,
    MeasurementScope,
    MeasurementValueType,
    SnippetRedactionLevel,
    SnippetSourceKind,
    ThresholdOperator,
)
from codestrata.domain.traceability.evidence_confidence import (
    EvidenceConfidence,
    EvidenceConfidenceBasis,
    EvidenceConfidenceDerivationStatus,
    EvidenceConfidenceLevel,
    evidence_confidence_to_json,
)
from codestrata.domain.traceability.evidence_ref import (
    EvidenceRef,
    dedupe_evidence_refs,
    order_evidence_refs,
)
from codestrata.domain.traceability.graph_reference import GraphReference
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.measurement import EvidenceMeasurement
from codestrata.domain.traceability.serialization import (
    evidence_ref_from_stable_dict,
    evidence_ref_to_stable_dict,
    from_stable_dict,
    to_stable_dict,
)
from codestrata.domain.traceability.snippet import RedactedSnippet
from codestrata.domain.traceability.validators import (
    MAX_SNIPPET_CHARS,
    TraceabilityValidationError,
    normalize_traceability_path,
)

__all__ = [
    "EvidenceCompleteness",
    "EvidenceConfidence",
    "EvidenceConfidenceBasis",
    "EvidenceConfidenceDerivationStatus",
    "EvidenceConfidenceLevel",
    "EvidenceKind",
    "EvidenceLocation",
    "EvidenceMeasurement",
    "EvidenceProductionMode",
    "EvidenceRef",
    "GraphKind",
    "GraphReference",
    "GraphReferenceKind",
    "LocationKind",
    "LocationPrecision",
    "MAX_SNIPPET_CHARS",
    "MeasurementAvailability",
    "MeasurementComparisonResult",
    "MeasurementScope",
    "MeasurementValueType",
    "RedactedSnippet",
    "SnippetRedactionLevel",
    "SnippetSourceKind",
    "ThresholdOperator",
    "TraceabilityValidationError",
    "dedupe_evidence_refs",
    "evidence_confidence_to_json",
    "evidence_ref_from_stable_dict",
    "evidence_ref_to_stable_dict",
    "from_stable_dict",
    "normalize_traceability_path",
    "order_evidence_refs",
    "to_stable_dict",
]
