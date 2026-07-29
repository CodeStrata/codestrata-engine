"""Application-layer knowledge store errors."""

from __future__ import annotations


class KnowledgeStoreError(Exception):
    """Base error for engineering knowledge persistence."""


class KnowledgeStoreVersionError(KnowledgeStoreError):
    """Raised when the on-disk store schema is unsupported."""


class RepositoryIdentityError(KnowledgeStoreError):
    """Raised when repository identity hints cannot be normalized."""


class RepositoryIdentityConflictError(KnowledgeStoreError):
    """Raised when aliases or keys resolve to different repositories."""


class RepositoryNotFoundError(KnowledgeStoreError):
    """Raised when a repository ID or alias does not exist."""


class RepositoryLockTimeoutError(KnowledgeStoreError):
    """Raised when a repository mutation lock cannot be acquired in time."""


class RepositoryAliasConflictError(RepositoryIdentityConflictError):
    """Raised when an alias is already bound to a different repository."""


class KnowledgeStoreCorruptionError(KnowledgeStoreError):
    """Raised when a blob or record fails integrity or schema validation."""


class KnowledgeArtifactNotFoundError(KnowledgeStoreError):
    """Raised when a requested knowledge artifact does not exist."""
