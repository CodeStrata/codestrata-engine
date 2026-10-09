"""Engineering Health report projection (R2-P03 / R2-P04).

Presentation mapping only. Does not invent outcomes, scores, ranks, deltas,
lifecycle, or movement.
"""

from codestrata.reporting.engineering_health.architecture_map import (
    load_repository_graph,
    project_architecture_map,
)
from codestrata.reporting.engineering_health.baseline import (
    project_attention_summary,
    project_cochange_section,
    project_coverage_trust,
    project_hotspot_section,
    project_ownership_section,
)
from codestrata.reporting.engineering_health.projection import (
    DISPLAY_INSUFFICIENT_EVIDENCE,
    DISPLAY_NEEDS_ATTENTION,
    DISPLAY_NO_MATERIAL_ISSUES,
    DISPLAY_NOT_APPLICABLE,
    SUPPORTING_CONTEXT_GIT,
    apply_engineering_health_projection,
    architecture_evidence_is_sufficient,
    display_label_for_section,
    map_engineering_health_display_label,
    overlay_headline_evidence_coverage,
    partition_assessment_heads,
    security_evidence_is_sufficient,
)

__all__ = [
    "DISPLAY_INSUFFICIENT_EVIDENCE",
    "DISPLAY_NEEDS_ATTENTION",
    "DISPLAY_NO_MATERIAL_ISSUES",
    "DISPLAY_NOT_APPLICABLE",
    "SUPPORTING_CONTEXT_GIT",
    "apply_engineering_health_projection",
    "architecture_evidence_is_sufficient",
    "display_label_for_section",
    "load_repository_graph",
    "map_engineering_health_display_label",
    "overlay_headline_evidence_coverage",
    "partition_assessment_heads",
    "security_evidence_is_sufficient",
    "project_architecture_map",
    "project_attention_summary",
    "project_cochange_section",
    "project_coverage_trust",
    "project_hotspot_section",
    "project_ownership_section",
]
