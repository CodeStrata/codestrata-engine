"""Finding application helpers."""

from codestrata.application.findings.finding_confidence import (
    derive_finding_confidence,
    derive_finding_confidence_from_finding_inputs,
    match_evidence_confidence_support,
)

__all__ = [
    "calibrate_finding",
    "calibrate_finding_severity",
    "consolidate_findings",
    "consolidate_rule_evaluation",
    "correlate_findings",
    "correlate_rule_evaluation",
    "derive_finding_confidence",
    "derive_finding_confidence_from_finding_inputs",
    "match_evidence_confidence_support",
    "remap_finding_ids",
]


def __getattr__(name: str):
    # Lazy export to avoid circular import with application.traceability.merge.
    if name in {
        "consolidate_findings",
        "consolidate_rule_evaluation",
        "remap_finding_ids",
    }:
        from codestrata.application.findings import consolidation as _consolidation

        return getattr(_consolidation, name)
    if name in {"correlate_findings", "correlate_rule_evaluation"}:
        from codestrata.application.findings import correlation as _correlation

        return getattr(_correlation, name)
    if name in {"calibrate_finding", "calibrate_finding_severity"}:
        from codestrata.application.findings import severity_calibration as _severity

        return getattr(_severity, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
