"""Shared helpers for incremental planning tests."""

from __future__ import annotations

from codestrata.application.incremental.fingerprints import (
    assessment_content_fingerprint,
    current_engine_fingerprint,
)
from codestrata.application.incremental.models import CandidateRepositoryState
from codestrata.domain.repository import (
    FileFingerprint,
    RepositoryFileEntry,
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryPath,
    RepositoryRevision,
)
from codestrata.domain.repository.enums import (
    HashAlgorithm,
    RepositoryFileKind,
    RepositoryRevisionType,
    RepositorySourceType,
)


def entry(
    path: str,
    digest: str,
    *,
    size: int = 10,
    kind: RepositoryFileKind = RepositoryFileKind.SOURCE,
    language: str | None = "java",
    executable: bool = False,
) -> RepositoryFileEntry:
    return RepositoryFileEntry(
        path=RepositoryPath(path),
        file_kind=kind,
        size_bytes=size,
        fingerprint=FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=digest),
        language=language,
        executable=executable,
    )


def manifest(
    *files: RepositoryFileEntry,
    key: str = "demo",
    branch: str | None = "main",
) -> RepositoryManifest:
    return RepositoryManifest(
        identity=RepositoryIdentity(
            repository_key=key,
            source_type=RepositorySourceType.LOCAL,
            display_name=key,
        ),
        revision=RepositoryRevision(
            revision_id="working-tree",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            branch=branch,
        ),
        files=files,
    )


def candidate_state(
    repo_manifest: RepositoryManifest,
    *,
    key: str | None = None,
) -> CandidateRepositoryState:
    engine = current_engine_fingerprint()
    return CandidateRepositoryState(
        repository_key=key or repo_manifest.identity.repository_key,
        display_name=repo_manifest.identity.display_name,
        branch=repo_manifest.revision.branch,
        revision_id=repo_manifest.revision.revision_id,
        manifest=repo_manifest,
        content_fingerprint=assessment_content_fingerprint(repo_manifest, engine=engine),
        engine=engine,
    )
