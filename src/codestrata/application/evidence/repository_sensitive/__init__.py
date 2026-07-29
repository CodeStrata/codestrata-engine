"""Repository-sensitive evidence application package (Phase 4.5.2).

Platform evidence for repository-visible sensitive artifacts and configuration
literals. Not owned by Security Intelligence.
"""

from codestrata.application.evidence.repository_sensitive.artifacts import (
    RepositorySensitiveEvidenceArtifactWriteResult,
    repository_sensitive_evidence_payload,
    write_repository_sensitive_evidence_artifact,
)
from codestrata.application.evidence.repository_sensitive.service import (
    RepositorySensitiveEvidenceService,
    create_repository_sensitive_evidence_service,
    repository_sensitive_evidence_collection_enabled,
)

__all__ = [
    "RepositorySensitiveEvidenceArtifactWriteResult",
    "RepositorySensitiveEvidenceService",
    "create_repository_sensitive_evidence_service",
    "repository_sensitive_evidence_collection_enabled",
    "repository_sensitive_evidence_payload",
    "write_repository_sensitive_evidence_artifact",
]
