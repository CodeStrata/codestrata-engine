"""Tests for repository fingerprints, diffs, and graph change sets."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from codestrata.domain.repository import (
    FileFingerprint,
    HashAlgorithm,
    RepositoryFileEntry,
    RepositoryFileKind,
    RepositoryFingerprintFactory,
    RepositoryGraphChangeSet,
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryManifestDiffer,
    RepositoryManifestDiffError,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)


def _fp(digest: str) -> FileFingerprint:
    return FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=digest)


def _entry(
    path: str,
    *,
    digest: str = "a" * 64,
    file_kind: RepositoryFileKind = RepositoryFileKind.SOURCE,
    size_bytes: int = 10,
    language: str | None = "java",
    media_type: str | None = None,
    executable: bool = False,
    generated: bool = False,
) -> RepositoryFileEntry:
    return RepositoryFileEntry(
        path=path,
        file_kind=file_kind,
        size_bytes=size_bytes,
        fingerprint=_fp(digest),
        executable=executable,
        generated=generated,
        language=language,
        media_type=media_type,
    )


def _manifest(
    *files: RepositoryFileEntry,
    repository_key: str = "petclinic",
    source_location: str | None = "/repos/petclinic",
    branch: str | None = "main",
    captured_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
    manifest_version: str = "1.0",
) -> RepositoryManifest:
    return RepositoryManifest(
        identity=RepositoryIdentity(
            repository_key=repository_key,
            source_type=RepositorySourceType.LOCAL,
            display_name="Petclinic",
            source_location=source_location,
        ),
        revision=RepositoryRevision(
            revision_id="rev-1",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            branch=branch,
            captured_at=captured_at,
        ),
        files=files,
        manifest_version=manifest_version,
        metadata=metadata or {},
    )


def test_repository_fingerprint_determinism_and_inclusions() -> None:
    base = _manifest(_entry("b.java", digest="b" * 64), _entry("a.java", digest="a" * 64))
    reordered = _manifest(_entry("a.java", digest="a" * 64), _entry("b.java", digest="b" * 64))
    same = RepositoryFingerprintFactory.from_manifest(base)
    assert same == RepositoryFingerprintFactory.from_manifest(reordered)
    assert same == RepositoryFingerprintFactory.from_manifest(base)

    content_changed = _manifest(
        _entry("a.java", digest="c" * 64),
        _entry("b.java", digest="b" * 64),
    )
    assert RepositoryFingerprintFactory.from_manifest(content_changed) != same

    path_changed = _manifest(
        _entry("a2.java", digest="a" * 64),
        _entry("b.java", digest="b" * 64),
    )
    assert RepositoryFingerprintFactory.from_manifest(path_changed) != same

    metadata_changed = _manifest(
        _entry("a.java", digest="a" * 64, language="kotlin"),
        _entry("b.java", digest="b" * 64),
    )
    assert RepositoryFingerprintFactory.from_manifest(metadata_changed) != same

    location_changed = _manifest(
        _entry("a.java", digest="a" * 64),
        _entry("b.java", digest="b" * 64),
        source_location="https://github.com/example/petclinic",
    )
    branch_changed = _manifest(
        _entry("a.java", digest="a" * 64),
        _entry("b.java", digest="b" * 64),
        branch="develop",
    )
    captured_changed = _manifest(
        _entry("a.java", digest="a" * 64),
        _entry("b.java", digest="b" * 64),
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    arbitrary_meta = _manifest(
        _entry("a.java", digest="a" * 64),
        _entry("b.java", digest="b" * 64),
        metadata={"scanner": "local-v2"},
    )
    assert RepositoryFingerprintFactory.from_manifest(location_changed) == same
    assert RepositoryFingerprintFactory.from_manifest(branch_changed) == same
    assert RepositoryFingerprintFactory.from_manifest(captured_changed) == same
    assert RepositoryFingerprintFactory.from_manifest(arbitrary_meta) == same


def test_manifest_diff_and_graph_changeset() -> None:
    previous = _manifest(
        _entry("keep.java", digest="a" * 64),
        _entry("gone.java", digest="b" * 64),
        _entry("changed.java", digest="c" * 64),
        _entry("meta.java", digest="d" * 64, language="java"),
        _entry("renamed_old.java", digest="e" * 64),
    )
    current = _manifest(
        _entry("keep.java", digest="a" * 64),
        _entry("changed.java", digest="f" * 64),
        _entry("meta.java", digest="d" * 64, language="kotlin"),
        _entry("new.java", digest="1" * 64),
        _entry("renamed_new.java", digest="e" * 64),
    )

    identical = RepositoryManifestDiffer.diff(previous, previous)
    assert identical.has_changes is False
    assert identical.changes == ()

    diff = RepositoryManifestDiffer.diff(previous, current)
    assert [c.path.root for c in diff.added] == ["new.java", "renamed_new.java"]
    assert [c.path.root for c in diff.deleted] == ["gone.java", "renamed_old.java"]
    assert [c.path.root for c in diff.modified] == ["changed.java"]
    assert [c.path.root for c in diff.metadata_changed] == ["meta.java"]
    assert [c.path.root for c in diff.changes] == sorted(c.path.root for c in diff.changes)

    with_unchanged = RepositoryManifestDiffer.diff(previous, current, include_unchanged=True)
    assert any(c.path.root == "keep.java" for c in with_unchanged.unchanged)

    with pytest.raises(RepositoryManifestDiffError, match="repository_key"):
        RepositoryManifestDiffer.diff(previous, _manifest(repository_key="other"))
    with pytest.raises(RepositoryManifestDiffError, match="manifest_version"):
        RepositoryManifestDiffer.diff(
            previous,
            _manifest(manifest_version="2.0"),
        )

    changeset = RepositoryGraphChangeSet.from_diff(diff)
    assert [p.root for p in changeset.added_paths] == ["new.java", "renamed_new.java"]
    assert [p.root for p in changeset.deleted_paths] == ["gone.java", "renamed_old.java"]
    assert [p.root for p in changeset.modified_paths] == ["changed.java"]
    assert [p.root for p in changeset.metadata_changed_paths] == ["meta.java"]
    assert "keep.java" not in {p.root for p in changeset.added_paths}
    assert changeset.repository_fingerprint == diff.current_fingerprint
