"""Declared assessment-area catalog for coverage denominators (Slice 5.6).

Denominator policy:
- claimed → supported denominator
- partial → partially supported denominator (limitation required)
- not_claimed → excluded from supported coverage ratio denominator
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.domain.assessment_heads.assessment_coverage import AreaClaimState


@dataclass(frozen=True, slots=True)
class DeclaredAssessmentArea:
    area_id: str
    title: str
    claim_state: AreaClaimState


# Claimed/partial areas only contribute to the supported denominator.
# Finding-count based areas are intentionally omitted.
HEAD_DECLARED_AREAS: dict[str, tuple[DeclaredAssessmentArea, ...]] = {
    "technology_inventory": (
        DeclaredAssessmentArea(
            "language_detection", "Language detection", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "build_system_detection", "Build system detection", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "dependency_manifest_detection",
            "Dependency manifest detection",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "version_availability", "Version availability", AreaClaimState.PARTIAL
        ),
        DeclaredAssessmentArea(
            "composition_facts", "Composition facts", AreaClaimState.PARTIAL
        ),
    ),
    "architecture_intelligence": (
        DeclaredAssessmentArea(
            "extraction_coverage", "Source extraction", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "classification_coverage", "Unit classification", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "framework_coverage", "Framework evidence", AreaClaimState.PARTIAL
        ),
        DeclaredAssessmentArea(
            "build_metadata_coverage", "Build metadata", AreaClaimState.PARTIAL
        ),
        DeclaredAssessmentArea(
            "architecture_rules", "Architecture rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "enterprise_context_coverage",
            "Enterprise context",
            AreaClaimState.NOT_CLAIMED,
        ),
    ),
    "technical_debt_intelligence": (
        DeclaredAssessmentArea(
            "debt_rule_coverage", "Technical debt rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "complexity_coverage", "Complexity measurements", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "duplication_coverage", "Duplication analysis", AreaClaimState.NOT_CLAIMED
        ),
        DeclaredAssessmentArea(
            "dependency_support_coverage",
            "Dependency support window",
            AreaClaimState.NOT_CLAIMED,
        ),
    ),
    "dependency_intelligence": (
        DeclaredAssessmentArea(
            "dependency_rule_coverage", "Dependency rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "dependency_evidence_coverage",
            "Manifest evidence",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "enterprise_context_coverage",
            "Enterprise context",
            AreaClaimState.NOT_CLAIMED,
        ),
    ),
    "security_intelligence": (
        DeclaredAssessmentArea(
            "security_capability_requested",
            "Security capability",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "security_rules_enabled", "Security rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "security_evidence_availability",
            "Sensitive evidence availability",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "security_inventory_complete",
            "Security inventory",
            AreaClaimState.PARTIAL,
        ),
    ),
    "cloud_readiness": (
        DeclaredAssessmentArea(
            "cloud_capability_requested", "Cloud capability", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "cloud_rules_enabled", "Cloud rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "cloud_evidence_availability",
            "Cloud artifact evidence",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "cloud_inventory_complete", "Cloud inventory", AreaClaimState.PARTIAL
        ),
    ),
    "ai_readiness": (
        DeclaredAssessmentArea(
            "ai_readiness_capability_requested",
            "AI readiness capability",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "ai_readiness_rules_enabled", "AI readiness rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "ai_readiness_evidence_availability",
            "AI readiness evidence",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "ai_readiness_inventory_complete",
            "AI readiness inventory",
            AreaClaimState.PARTIAL,
        ),
    ),
    "testing": (
        DeclaredAssessmentArea(
            "testing_capability_requested", "Testing capability", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "testing_rules_enabled", "Testing rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "testing_evidence_availability",
            "Testing evidence",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "testing_inventory_complete", "Testing inventory", AreaClaimState.PARTIAL
        ),
    ),
    "performance": (
        DeclaredAssessmentArea(
            "performance_capability_requested",
            "Performance capability",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "performance_rules_enabled", "Performance rules", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "performance_evidence_availability",
            "Performance evidence",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "performance_inventory_complete",
            "Performance inventory",
            AreaClaimState.PARTIAL,
        ),
    ),
    "modernization_assessment": (
        DeclaredAssessmentArea(
            "contributing_heads", "Contributing assessment heads", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "finding_backed_recommendations",
            "Finding-backed recommendations",
            AreaClaimState.CLAIMED,
        ),
        DeclaredAssessmentArea(
            "priority_actions", "Priority Actions", AreaClaimState.CLAIMED
        ),
        DeclaredAssessmentArea(
            "roadmap_chain", "Roadmap chain completeness", AreaClaimState.PARTIAL
        ),
    ),
}


def declared_areas_for_head(head_id: str) -> tuple[DeclaredAssessmentArea, ...]:
    return HEAD_DECLARED_AREAS.get(str(head_id).strip(), ())
