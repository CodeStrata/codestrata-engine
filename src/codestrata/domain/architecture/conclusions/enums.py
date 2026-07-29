"""Enumerations for architecture conclusions."""

from __future__ import annotations

from enum import StrEnum


class ConclusionStatus(StrEnum):
    ESTABLISHED = "established"
    PROVISIONAL = "provisional"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INFORMATIONAL = "informational"
    POSITIVE = "positive"


class ConclusionMateriality(StrEnum):
    MATERIAL = "material"
    NOTABLE = "notable"
    CONTEXTUAL = "contextual"
    INFORMATIONAL = "informational"
    UNDETERMINED = "undetermined"


class FindingRelationshipType(StrEnum):
    SUPPORTS = "supports"
    REINFORCES = "reinforces"
    OVERLAPS = "overlaps"
    SAME_ROOT_CAUSE = "same_root_cause"
    SAME_SCOPE = "same_scope"
    PARENT_SCOPE = "parent_scope"
    CHILD_SCOPE = "child_scope"
    CONSEQUENCE_OF = "consequence_of"
    PREREQUISITE_FOR = "prerequisite_for"
    CONTRADICTS = "contradicts"
    INDEPENDENT = "independent"


class ConclusionPolicyStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"


class ModernizationWave(StrEnum):
    WAVE_0_VALIDATE = "wave_0_validate_stabilize"
    WAVE_1_QUICK_WINS = "wave_1_quick_wins"
    WAVE_2_FOUNDATION = "wave_2_foundation_modernization"
    WAVE_3_STRUCTURAL = "wave_3_structural_modernization"
    WAVE_4_STRATEGIC_AI = "wave_4_strategic_ai_enablement"
