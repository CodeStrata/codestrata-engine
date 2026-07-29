"""Repository AI-readiness evidence domain package (Phase 4.8.2).

Platform evidence for repository-observable AI/agent readiness signals.
Not owned by AI Readiness Intelligence assessment.
"""

from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessApiBoundaryKind,
    AiReadinessDataRetrievalKind,
    AiReadinessDiscoveryBasis,
    AiReadinessDocumentationKind,
    AiReadinessEvidenceFamily,
    AiReadinessObservabilityGovernanceKind,
    AiReadinessToolMcpKind,
    AiReadinessWorkflowAgentKind,
    EvidenceConfirmationLevel,
    RepositoryAiReadinessLimitationCategory,
    RepositoryAiReadinessParseStatus,
)
from codestrata.domain.evidence.repository_ai_readiness.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_SCHEMA_ID,
    REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.domain.evidence.repository_ai_readiness.models import (
    AggregatedRepositoryAiReadinessEvidence,
    AiReadinessAiIntegrationFactEvidence,
    AiReadinessApiBoundaryFactEvidence,
    AiReadinessDataRetrievalFactEvidence,
    AiReadinessDocumentationFactEvidence,
    AiReadinessFileCandidateEvidence,
    AiReadinessObservabilityGovernanceFactEvidence,
    AiReadinessToolMcpFactEvidence,
    AiReadinessWorkflowAgentFactEvidence,
    RepositoryAiReadinessDiagnostic,
    RepositoryAiReadinessEvidenceCoverage,
    RepositoryAiReadinessLimitation,
)

__all__ = [
    "PROVIDER_ID",
    "PROVIDER_VERSION",
    "REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_FILENAME",
    "REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_SCHEMA_ID",
    "REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_NAME",
    "REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_VERSION",
    "AggregatedRepositoryAiReadinessEvidence",
    "AiReadinessAiIntegrationFactEvidence",
    "AiReadinessAiIntegrationKind",
    "AiReadinessApiBoundaryFactEvidence",
    "AiReadinessApiBoundaryKind",
    "AiReadinessDataRetrievalFactEvidence",
    "AiReadinessDataRetrievalKind",
    "AiReadinessDiscoveryBasis",
    "AiReadinessDocumentationFactEvidence",
    "AiReadinessDocumentationKind",
    "AiReadinessEvidenceFamily",
    "AiReadinessFileCandidateEvidence",
    "AiReadinessObservabilityGovernanceFactEvidence",
    "AiReadinessObservabilityGovernanceKind",
    "AiReadinessToolMcpFactEvidence",
    "AiReadinessToolMcpKind",
    "AiReadinessWorkflowAgentFactEvidence",
    "AiReadinessWorkflowAgentKind",
    "EvidenceConfirmationLevel",
    "RepositoryAiReadinessDiagnostic",
    "RepositoryAiReadinessEvidenceCoverage",
    "RepositoryAiReadinessLimitation",
    "RepositoryAiReadinessLimitationCategory",
    "RepositoryAiReadinessParseStatus",
]
