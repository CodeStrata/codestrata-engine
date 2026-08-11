"""Phase 3 graph-rule findings domain."""

from codestrata.domain.findings.consolidation import (
    FindingConsolidationBasis,
    FindingConsolidationDiagnostics,
    FindingConsolidationResult,
    FindingDuplicateGroup,
    FindingDuplicateKind,
    canonical_finding_condition_key,
)
from codestrata.domain.findings.correlation import (
    CorrelationConfidence,
    CorrelationConfidenceLevel,
    CorrelationDirection,
    FindingCorrelation,
    FindingCorrelationBasis,
    FindingCorrelationCluster,
    FindingCorrelationDiagnostics,
    FindingCorrelationResult,
    FindingCorrelationType,
    build_correlation_id,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity, FindingSource
from codestrata.domain.findings.finding_confidence import (
    FindingConfidence,
    FindingConfidenceBasis,
    FindingConfidenceComponents,
    FindingConfidenceDerivationStatus,
    FindingConfidenceLevel,
    finding_confidence_to_json,
)
from codestrata.domain.findings.ids import build_finding_id
from codestrata.domain.findings.models import Finding, FindingEvidence, RuleEvaluationResult
from codestrata.domain.findings.severity import (
    FindingSeverityAssessment,
    FindingSeverityBasis,
    FindingSeverityComponents,
    RepositoryContextClass,
    SeverityCalibrationStatus,
    compute_threshold_ratio,
    normalize_severity_token,
)

__all__ = [
    "CorrelationConfidence",
    "CorrelationConfidenceLevel",
    "CorrelationDirection",
    "Finding",
    "FindingCategory",
    "FindingConfidence",
    "FindingConfidenceBasis",
    "FindingConfidenceComponents",
    "FindingConfidenceDerivationStatus",
    "FindingConfidenceLevel",
    "FindingConsolidationBasis",
    "FindingConsolidationDiagnostics",
    "FindingConsolidationResult",
    "FindingCorrelation",
    "FindingCorrelationBasis",
    "FindingCorrelationCluster",
    "FindingCorrelationDiagnostics",
    "FindingCorrelationResult",
    "FindingCorrelationType",
    "FindingDuplicateGroup",
    "FindingDuplicateKind",
    "FindingEvidence",
    "FindingSeverity",
    "FindingSeverityAssessment",
    "FindingSeverityBasis",
    "FindingSeverityComponents",
    "FindingSource",
    "RepositoryContextClass",
    "RuleEvaluationResult",
    "SeverityCalibrationStatus",
    "build_correlation_id",
    "build_finding_id",
    "canonical_finding_condition_key",
    "compute_threshold_ratio",
    "finding_confidence_to_json",
    "normalize_severity_token",
]
