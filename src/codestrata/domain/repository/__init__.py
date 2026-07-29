"""Repository inventory, fingerprinting, and change-detection domain contracts.

This package models the source repository itself. Repository Graph packages
model extracted structural knowledge and may depend on these contracts; this
package must not depend on Repository Graph factories or snapshots.
"""

from codestrata.domain.repository.changes import (
    RepositoryFileChange,
    RepositoryGraphChangeSet,
    RepositoryManifestDiff,
    RepositoryManifestDiffer,
    RepositoryManifestDiffError,
)
from codestrata.domain.repository.enums import (
    HashAlgorithm,
    RepositoryChangeType,
    RepositoryFileKind,
    RepositoryRevisionType,
    RepositorySourceType,
)
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.fingerprints import (
    FileFingerprint,
    RepositoryFingerprint,
    RepositoryFingerprintFactory,
    hash_bytes,
    normalize_digest,
)
from codestrata.domain.repository.identities import (
    RepositoryIdentity,
    RepositoryRevision,
    normalize_repository_key,
    normalize_source_location,
)
from codestrata.domain.repository.manifests import (
    REPOSITORY_MANIFEST_VERSION,
    RepositoryManifest,
)
from codestrata.domain.repository.paths import (
    RepositoryPath,
    normalize_repository_relative_path,
)

__all__ = [
    "REPOSITORY_MANIFEST_VERSION",
    "FileFingerprint",
    "HashAlgorithm",
    "RepositoryChangeType",
    "RepositoryFileChange",
    "RepositoryFileEntry",
    "RepositoryFileKind",
    "RepositoryFingerprint",
    "RepositoryFingerprintFactory",
    "RepositoryGraphChangeSet",
    "RepositoryIdentity",
    "RepositoryManifest",
    "RepositoryManifestDiff",
    "RepositoryManifestDiffError",
    "RepositoryManifestDiffer",
    "RepositoryPath",
    "RepositoryRevision",
    "RepositoryRevisionType",
    "RepositorySourceType",
    "hash_bytes",
    "normalize_digest",
    "normalize_repository_key",
    "normalize_repository_relative_path",
    "normalize_source_location",
]
