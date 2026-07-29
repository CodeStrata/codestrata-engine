"""Change classifier tests."""

from __future__ import annotations

from codestrata.application.incremental.changes import ChangeClassifier
from codestrata.application.incremental.models import FileChangeKind
from codestrata.domain.repository.enums import RepositoryFileKind
from tests.application.incremental.helpers import entry, manifest


def test_no_changes() -> None:
    previous = manifest(entry("src/A.java", "a" * 64))
    current = manifest(entry("src/A.java", "a" * 64))
    result = ChangeClassifier().classify(previous, current)
    assert result.change_count == 0
    assert result.unchanged_count == 1


def test_added_modified_deleted_and_rename_as_add_delete() -> None:
    previous = manifest(
        entry("src/Old.java", "a" * 64),
        entry("src/Keep.java", "b" * 64),
    )
    current = manifest(
        entry("src/New.java", "a" * 64),
        entry("src/Keep.java", "c" * 64),
    )
    result = ChangeClassifier().classify(previous, current)
    assert [item.path for item in result.added] == ["src/New.java"]
    assert [item.path for item in result.deleted] == ["src/Old.java"]
    assert [item.path for item in result.modified] == ["src/Keep.java"]
    assert result.modified[0].kind is FileChangeKind.MODIFIED
    assert result.modified[0].dimensions.content_changed is True
    assert result.modified[0].dimensions.unknown is True


def test_metadata_only_change() -> None:
    previous = manifest(entry("src/A.java", "a" * 64, executable=False))
    current = manifest(entry("src/A.java", "a" * 64, executable=True))
    result = ChangeClassifier().classify(previous, current)
    assert len(result.metadata_changed) == 1
    assert result.metadata_changed[0].kind is FileChangeKind.METADATA_CHANGED


def test_dependency_build_config_and_documentation_flags() -> None:
    previous = manifest(
        entry("pom.xml", "a" * 64, kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language=None),
        entry("build.gradle", "b" * 64, kind=RepositoryFileKind.BUILD, language=None),
        entry("app.yml", "c" * 64, kind=RepositoryFileKind.CONFIGURATION, language=None),
        entry("README.md", "d" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None),
    )
    current = manifest(
        entry("pom.xml", "e" * 64, kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language=None),
        entry("build.gradle", "f" * 64, kind=RepositoryFileKind.BUILD, language=None),
        entry("app.yml", "1" * 64, kind=RepositoryFileKind.CONFIGURATION, language=None),
        entry("README.md", "2" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None),
    )
    result = ChangeClassifier().classify(previous, current)
    assert result.has_dependency_manifest_changes is True
    assert result.has_build_changes is True
    assert result.has_configuration_changes is True
    assert result.has_documentation_only_changes is False

    doc_only_prev = manifest(
        entry("README.md", "d" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None)
    )
    doc_only_curr = manifest(
        entry("README.md", "e" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None)
    )
    doc = ChangeClassifier().classify(doc_only_prev, doc_only_curr)
    assert doc.has_documentation_only_changes is True
    assert doc.has_source_changes is False


def test_normalized_paths_and_deterministic_ordering() -> None:
    previous = manifest(
        entry("b/B.java", "a" * 64),
        entry("a/A.java", "b" * 64),
    )
    current = manifest(
        entry("b/B.java", "c" * 64),
        entry("a/A.java", "d" * 64),
    )
    first = ChangeClassifier().classify(previous, current)
    second = ChangeClassifier().classify(previous, current)
    assert [item.path for item in first.modified] == ["a/A.java", "b/B.java"]
    assert first.model_dump() == second.model_dump()
