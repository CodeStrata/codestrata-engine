"""Architecture conclusions domain package."""

from codestrata.domain.architecture.conclusions.enums import (
    ConclusionMateriality,
    ConclusionPolicyStatus,
    ConclusionStatus,
    FindingRelationshipType,
    ModernizationWave,
)
from codestrata.domain.architecture.conclusions.identifiers import (
    CAT_BOUNDARY_INTEGRITY,
    CAT_COUPLING,
    CAT_DEPENDENCY_STRUCTURE,
    CAT_ENTERPRISE_CONFORMANCE,
    CAT_FRAMEWORK_INDEPENDENCE,
    CAT_INSUFFICIENT_EVIDENCE,
    POLICY_BOUNDARY_INTEGRITY,
    POLICY_BROAD_DEPENDENCY,
    POLICY_CYCLIC_DEPENDENCY,
    POLICY_ENTERPRISE_NONCONFORMANCE,
    POLICY_FRAMEWORK_EROSION,
    POLICY_INSUFFICIENT_EVIDENCE,
    POLICY_POSITIVE_BOUNDARY,
    build_cluster_id,
    build_conclusion_id,
    build_recommendation_group_id,
)
from codestrata.domain.architecture.conclusions.models import (
    ArchitectureConclusion,
    ArchitectureSummary,
    ConsolidatedRecommendation,
)
from codestrata.domain.architecture.conclusions.relationships import (
    FindingCluster,
    FindingRelationship,
    SeveritySummary,
)

__all__ = [
    "CAT_BOUNDARY_INTEGRITY",
    "CAT_COUPLING",
    "CAT_DEPENDENCY_STRUCTURE",
    "CAT_ENTERPRISE_CONFORMANCE",
    "CAT_FRAMEWORK_INDEPENDENCE",
    "CAT_INSUFFICIENT_EVIDENCE",
    "POLICY_BOUNDARY_INTEGRITY",
    "POLICY_BROAD_DEPENDENCY",
    "POLICY_CYCLIC_DEPENDENCY",
    "POLICY_ENTERPRISE_NONCONFORMANCE",
    "POLICY_FRAMEWORK_EROSION",
    "POLICY_INSUFFICIENT_EVIDENCE",
    "POLICY_POSITIVE_BOUNDARY",
    "ArchitectureConclusion",
    "ArchitectureSummary",
    "ConclusionMateriality",
    "ConclusionPolicyStatus",
    "ConclusionStatus",
    "ConsolidatedRecommendation",
    "FindingCluster",
    "FindingRelationship",
    "FindingRelationshipType",
    "ModernizationWave",
    "SeveritySummary",
    "build_cluster_id",
    "build_conclusion_id",
    "build_recommendation_group_id",
]
