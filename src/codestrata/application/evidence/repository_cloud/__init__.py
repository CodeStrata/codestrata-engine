"""Repository-cloud evidence application package (Phase 4.7.2).

Platform evidence for repository-observable cloud technologies and deployment
signals. Not owned by Cloud Intelligence.
"""

from codestrata.application.evidence.repository_cloud.artifacts import (
    RepositoryCloudEvidenceArtifactWriteResult,
    repository_cloud_evidence_payload,
    write_repository_cloud_evidence_artifact,
)
from codestrata.application.evidence.repository_cloud.service import (
    RepositoryCloudEvidenceService,
    create_repository_cloud_evidence_service,
    repository_cloud_evidence_collection_enabled,
)

__all__ = [
    "RepositoryCloudEvidenceArtifactWriteResult",
    "RepositoryCloudEvidenceService",
    "create_repository_cloud_evidence_service",
    "repository_cloud_evidence_collection_enabled",
    "repository_cloud_evidence_payload",
    "write_repository_cloud_evidence_artifact",
]
