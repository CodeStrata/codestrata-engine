"""Repository AI-readiness evidence application package (Phase 4.8.2).

Platform evidence for repository-observable AI/agent readiness signals.
Not owned by AI Readiness Intelligence.
"""

from codestrata.application.evidence.repository_ai_readiness.artifacts import (
    RepositoryAiReadinessEvidenceArtifactWriteResult,
    repository_ai_readiness_evidence_payload,
    write_repository_ai_readiness_evidence_artifact,
)
from codestrata.application.evidence.repository_ai_readiness.service import (
    RepositoryAiReadinessEvidenceService,
    create_repository_ai_readiness_evidence_service,
    repository_ai_readiness_evidence_collection_enabled,
)

__all__ = [
    "RepositoryAiReadinessEvidenceArtifactWriteResult",
    "RepositoryAiReadinessEvidenceService",
    "create_repository_ai_readiness_evidence_service",
    "repository_ai_readiness_evidence_collection_enabled",
    "repository_ai_readiness_evidence_payload",
    "write_repository_ai_readiness_evidence_artifact",
]
