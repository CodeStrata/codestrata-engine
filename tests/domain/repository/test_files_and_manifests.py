"""Tests for file fingerprints, entries, and manifests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.repository import (
    FileFingerprint,
    HashAlgorithm,
    RepositoryFileEntry,
    RepositoryFileKind,
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)


def _sha256(digest: str = "a" * 64) -> FileFingerprint:
    return FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=digest)


def _entry(
    path: str,
    *,
    digest: str = "a" * 64,
    file_kind: RepositoryFileKind = RepositoryFileKind.SOURCE,
    size_bytes: int = 10,
    language: str | None = "java",
    media_type: str | None = "text/x-java-source",
    executable: bool = False,
    generated: bool = False,
) -> RepositoryFileEntry:
    return RepositoryFileEntry(
        path=path,
        file_kind=file_kind,
        size_bytes=size_bytes,
        fingerprint=_sha256(digest),
        executable=executable,
        generated=generated,
        language=language,
        media_type=media_type,
    )


def _identity(**overrides: object) -> RepositoryIdentity:
    payload: dict[str, object] = {
        "repository_key": "petclinic",
        "source_type": RepositorySourceType.LOCAL,
        "display_name": "Petclinic",
        "source_location": "/repos/petclinic",
    }
    payload.update(overrides)
    return RepositoryIdentity.model_validate(payload)


def _revision(**overrides: object) -> RepositoryRevision:
    payload: dict[str, object] = {
        "revision_id": "rev-1",
        "revision_type": RepositoryRevisionType.WORKING_TREE,
        "branch": "main",
    }
    payload.update(overrides)
    return RepositoryRevision.model_validate(payload)


def test_file_fingerprint_validation() -> None:
    assert FileFingerprint(algorithm=HashAlgorithm.SHA256, digest="A" * 64).digest == "a" * 64
    assert (
        FileFingerprint(algorithm=HashAlgorithm.SHA512, digest="b" * 128).algorithm
        is HashAlgorithm.SHA512
    )
    with pytest.raises(ValidationError, match="exactly 64"):
        FileFingerprint(algorithm=HashAlgorithm.SHA256, digest="a" * 63)
    with pytest.raises(ValidationError, match="hexadecimal"):
        FileFingerprint(algorithm=HashAlgorithm.SHA256, digest="g" * 64)
    with pytest.raises(ValidationError, match="whitespace"):
        FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=("a" * 63) + " ")
    with pytest.raises(ValidationError, match="prefix"):
        FileFingerprint(algorithm=HashAlgorithm.SHA256, digest="sha256:" + ("a" * 64))


def test_repository_file_entry_validation_and_round_trip() -> None:
    entry = _entry("src//App.java")
    assert entry.path.root == "src/App.java"
    payload = entry.model_dump(mode="json")
    restored = RepositoryFileEntry.model_validate(payload)
    assert restored == entry

    with pytest.raises(ValidationError):
        _entry("a.java", size_bytes=-1)
    with pytest.raises(ValidationError, match="blank"):
        _entry("a.java", language=" ")


def test_manifest_ordering_uniqueness_and_round_trip() -> None:
    first = RepositoryManifest(
        identity=_identity(),
        revision=_revision(),
        files=(_entry("b.java", digest="b" * 64), _entry("a.java", digest="a" * 64)),
    )
    second = RepositoryManifest(
        identity=_identity(),
        revision=_revision(),
        files=(_entry("a.java", digest="a" * 64), _entry("b.java", digest="b" * 64)),
    )
    assert [item.path.root for item in first.files] == ["a.java", "b.java"]
    assert first == second

    with pytest.raises(ValidationError, match="unique"):
        RepositoryManifest(
            identity=_identity(),
            revision=_revision(),
            files=(_entry("a.java"), _entry("a.java")),
        )

    restored = RepositoryManifest.model_validate_json(first.model_dump_json())
    assert restored == first

    with pytest.raises(ValidationError, match="blank"):
        RepositoryManifest(
            identity=_identity(),
            revision=_revision(),
            files=(),
            metadata={"": 1},
        )
