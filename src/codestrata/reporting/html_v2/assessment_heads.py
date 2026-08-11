"""Customer assessment-head contract for HTML report organization (Epic 3 Slice 3.1).

Presentation-layer only. Does not define analyzers, coverage engines, or taxonomies.
"""

from __future__ import annotations

from enum import StrEnum


class AssessmentHead(StrEnum):
    """Stable assessment-head identifiers for customer report organization."""

    ENGINEERING_INTELLIGENCE = "engineering_intelligence"
    TECHNOLOGY_INVENTORY = "technology_inventory"
    ARCHITECTURE_INTELLIGENCE = "architecture_intelligence"
    TECHNICAL_DEBT_INTELLIGENCE = "technical_debt_intelligence"
    DEPENDENCY_INTELLIGENCE = "dependency_intelligence"
    SECURITY_INTELLIGENCE = "security_intelligence"
    CLOUD_READINESS = "cloud_readiness"
    AI_READINESS = "ai_readiness"
    MODERNIZATION_ASSESSMENT = "modernization_assessment"


# Display order for Assessment Results subsections (excludes Assessment Overview).
ASSESSMENT_RESULT_HEADS: tuple[AssessmentHead, ...] = (
    AssessmentHead.TECHNOLOGY_INVENTORY,
    AssessmentHead.ARCHITECTURE_INTELLIGENCE,
    AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE,
    AssessmentHead.DEPENDENCY_INTELLIGENCE,
    AssessmentHead.SECURITY_INTELLIGENCE,
    AssessmentHead.CLOUD_READINESS,
    AssessmentHead.AI_READINESS,
    AssessmentHead.MODERNIZATION_ASSESSMENT,
)

_TITLES: dict[AssessmentHead, str] = {
    # Display rename (Slice 19.1): unique cross-head synthesis; schema id unchanged.
    AssessmentHead.ENGINEERING_INTELLIGENCE: "Assessment Overview",
    AssessmentHead.TECHNOLOGY_INVENTORY: "Technology Inventory",
    AssessmentHead.ARCHITECTURE_INTELLIGENCE: "Architecture Intelligence",
    AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE: "Technical Debt Intelligence",
    AssessmentHead.DEPENDENCY_INTELLIGENCE: "Dependency Intelligence",
    AssessmentHead.SECURITY_INTELLIGENCE: "Security Intelligence",
    AssessmentHead.CLOUD_READINESS: "Cloud Readiness",
    AssessmentHead.AI_READINESS: "AI Readiness",
    AssessmentHead.MODERNIZATION_ASSESSMENT: "Modernization Assessment",
}

_ANCHORS: dict[AssessmentHead, str] = {
    AssessmentHead.ENGINEERING_INTELLIGENCE: "engineering-intelligence-summary",
    AssessmentHead.TECHNOLOGY_INVENTORY: "technology-inventory",
    AssessmentHead.ARCHITECTURE_INTELLIGENCE: "architecture-intelligence",
    AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE: "technical-debt-intelligence",
    AssessmentHead.DEPENDENCY_INTELLIGENCE: "dependency-intelligence",
    AssessmentHead.SECURITY_INTELLIGENCE: "security-intelligence",
    AssessmentHead.CLOUD_READINESS: "cloud-readiness",
    AssessmentHead.AI_READINESS: "ai-readiness",
    AssessmentHead.MODERNIZATION_ASSESSMENT: "modernization-assessment",
}

# Parent section wrapping Assessment Results subsections.
ASSESSMENT_RESULTS_ANCHOR = "assessment-results"
ASSESSMENT_RESULTS_TITLE = "Assessment Results"

# Legacy Domain Intelligence section ids/titles (Epic 3 Slice 3.1 compatibility).
# Emitted only when the corresponding pack report is present — not duplicate sections.
LEGACY_PACK_SECTION_ALIASES: dict[AssessmentHead, tuple[str, str]] = {
    AssessmentHead.ARCHITECTURE_INTELLIGENCE: (
        "architecture-assessment",
        "Architecture Assessment",
    ),
    AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE: (
        "technical-debt-assessment",
        "Technical Debt Assessment",
    ),
    AssessmentHead.DEPENDENCY_INTELLIGENCE: (
        "dependency-assessment",
        "Dependency Assessment",
    ),
    AssessmentHead.SECURITY_INTELLIGENCE: (
        "security-assessment",
        "Security Assessment",
    ),
    AssessmentHead.CLOUD_READINESS: (
        "cloud-assessment",
        "Cloud Assessment",
    ),
    AssessmentHead.AI_READINESS: (
        "ai-readiness-assessment",
        "AI Readiness Assessment",
    ),
}


def assessment_head_title(head: AssessmentHead | str) -> str:
    key = AssessmentHead(str(head))
    return _TITLES[key]


def assessment_head_anchor(head: AssessmentHead | str) -> str:
    key = AssessmentHead(str(head))
    return _ANCHORS[key]


def assessment_head_order(head: AssessmentHead | str) -> int:
    key = AssessmentHead(str(head))
    if key is AssessmentHead.ENGINEERING_INTELLIGENCE:
        return 0
    try:
        return ASSESSMENT_RESULT_HEADS.index(key) + 1
    except ValueError:
        return 99


def all_assessment_heads() -> tuple[AssessmentHead, ...]:
    return (AssessmentHead.ENGINEERING_INTELLIGENCE, *ASSESSMENT_RESULT_HEADS)
