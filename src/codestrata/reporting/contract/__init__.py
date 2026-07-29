"""Report contract package (Phase 5.12)."""

from codestrata.reporting.contract.canonical import (
    reports_structurally_equal,
    strip_volatile_fields,
)
from codestrata.reporting.contract.constants import (
    ASSESSMENT_JSON_REPORT_VERSION,
    ASSESSMENT_JSON_SCHEMA_VERSION,
    REPORT_CONTRACT_VERSION,
    REPORT_HTML_VERSION,
    VOLATILE_JSON_PATHS,
)
from codestrata.reporting.contract.enums import (
    normalize_confidence,
    normalize_effort,
    normalize_priority,
    normalize_risk,
    normalize_severity,
    normalize_status,
)
from codestrata.reporting.contract.identifiers import (
    align_related_finding_ids,
    build_finding_id_map,
    remap_related_finding_ids,
    stable_finding_id,
    stable_recommendation_id,
)
from codestrata.reporting.contract.manifest import build_report_manifest
from codestrata.reporting.contract.ordering import (
    dedupe_by_id,
    sorted_evidence,
    sorted_findings,
    sorted_recommendations,
    sorted_technologies,
)

__all__ = [
    "ASSESSMENT_JSON_REPORT_VERSION",
    "ASSESSMENT_JSON_SCHEMA_VERSION",
    "REPORT_CONTRACT_VERSION",
    "REPORT_HTML_VERSION",
    "VOLATILE_JSON_PATHS",
    "align_related_finding_ids",
    "build_finding_id_map",
    "build_report_manifest",
    "remap_related_finding_ids",
    "dedupe_by_id",
    "normalize_confidence",
    "normalize_effort",
    "normalize_priority",
    "normalize_risk",
    "normalize_severity",
    "normalize_status",
    "reports_structurally_equal",
    "sorted_evidence",
    "sorted_findings",
    "sorted_recommendations",
    "sorted_technologies",
    "stable_finding_id",
    "stable_recommendation_id",
    "strip_volatile_fields",
]
