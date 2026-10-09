"""Application-layer engineering knowledge persistence contracts."""

from codestrata.application.knowledge.artifact_evidence import (
    LocalArtifactEvidenceService,
    project_canonical_evidence,
)
from codestrata.application.knowledge.errors import (
    KnowledgeArtifactNotFoundError,
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    KnowledgeStoreVersionError,
    RepositoryAliasConflictError,
    RepositoryIdentityConflictError,
    RepositoryIdentityError,
    RepositoryLockTimeoutError,
    RepositoryNotFoundError,
)
from codestrata.application.knowledge.health import local_knowledge_health
from codestrata.application.knowledge.identity import (
    NormalizedAlias,
    NormalizedRepositoryIdentity,
    build_github_canonical_key,
    build_local_canonical_key,
    normalize_github_url_alias,
    normalize_identity_hints,
    normalize_local_path_alias,
)
from codestrata.application.knowledge.models import (
    AssessmentRunRecord,
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    KnowledgeArtifactRecord,
    RepositoryAliasRecord,
    RepositoryAliasType,
    RepositoryIdentityHints,
    RepositoryRecord,
    RepositorySnapshotRecord,
    StagedKnowledgeArtifact,
)
from codestrata.application.knowledge.permitted_evidence import (
    collect_permitted_evidence_ids,
)
from codestrata.application.knowledge.ports import (
    AssessmentRunStore,
    KnowledgeStore,
    RepositoryRegistry,
    SnapshotStore,
)
from codestrata.application.knowledge.session import AssessmentKnowledgeSession

__all__ = [
    "AssessmentKnowledgeSession",
    "LocalArtifactEvidenceService",
    "local_knowledge_health",
    "AssessmentRunRecord",
    "AssessmentRunStatus",
    "AssessmentRunStore",
    "KnowledgeArtifactKind",
    "KnowledgeArtifactNotFoundError",
    "KnowledgeArtifactRecord",
    "KnowledgeStore",
    "KnowledgeStoreCorruptionError",
    "KnowledgeStoreError",
    "KnowledgeStoreVersionError",
    "NormalizedAlias",
    "NormalizedRepositoryIdentity",
    "RepositoryAliasConflictError",
    "RepositoryAliasRecord",
    "RepositoryAliasType",
    "RepositoryIdentityConflictError",
    "RepositoryIdentityError",
    "RepositoryIdentityHints",
    "RepositoryLockTimeoutError",
    "RepositoryNotFoundError",
    "RepositoryRecord",
    "RepositoryRegistry",
    "RepositorySnapshotRecord",
    "SnapshotStore",
    "StagedKnowledgeArtifact",
    "collect_permitted_evidence_ids",
    "project_canonical_evidence",
    "build_github_canonical_key",
    "build_local_canonical_key",
    "normalize_github_url_alias",
    "normalize_identity_hints",
    "normalize_local_path_alias",
]
