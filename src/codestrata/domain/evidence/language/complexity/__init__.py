"""Structural complexity evidence models (Language Evidence Platform; Phase 4.3.2).

These models describe source facts only. They do not encode debt, severity,
thresholds, or remediation priority.
"""

from codestrata.domain.evidence.language.complexity.enums import (
    ComplexityCallableKind,
    ComplexityTypeKind,
    MetricAvailability,
)
from codestrata.domain.evidence.language.complexity.identifiers import (
    COMPLEXITY_ARTIFACT_FILENAME,
    COMPLEXITY_BUNDLE_SCHEMA_VERSION,
    make_callable_complexity_id,
    make_file_complexity_id,
    make_type_complexity_id,
)
from codestrata.domain.evidence.language.complexity.models import (
    AggregatedComplexityEvidence,
    CallableComplexityEvidence,
    ComplexityEvidenceBundle,
    FileComplexityEvidence,
    IntMetric,
    SourceSpan,
    TypeComplexityEvidence,
)

__all__ = [
    "COMPLEXITY_ARTIFACT_FILENAME",
    "COMPLEXITY_BUNDLE_SCHEMA_VERSION",
    "AggregatedComplexityEvidence",
    "CallableComplexityEvidence",
    "ComplexityCallableKind",
    "ComplexityEvidenceBundle",
    "ComplexityTypeKind",
    "FileComplexityEvidence",
    "IntMetric",
    "MetricAvailability",
    "SourceSpan",
    "TypeComplexityEvidence",
    "make_callable_complexity_id",
    "make_file_complexity_id",
    "make_type_complexity_id",
]
