"""Tests for RepositoryInventoryBuilder pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.domain.repository import (
    RepositoryFileKind,
    RepositoryFingerprintFactory,
    RepositoryIdentity,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)
from codestrata.services.inventory import (
    LocalFilesystemContentReader,
    RepositoryInventoryBuilder,
)
from tests.services.inventory.memory_reader import InMemoryContentReader


def _identity() -> RepositoryIdentity:
    return RepositoryIdentity(
        repository_key="petclinic",
        source_type=RepositorySourceType.LOCAL,
        display_name="Petclinic",
        source_location="/repos/petclinic",
    )


def _revision() -> RepositoryRevision:
    return RepositoryRevision(
        revision_id="working-tree",
        revision_type=RepositoryRevisionType.WORKING_TREE,
        branch="main",
    )


def test_builder_produces_sorted_deterministic_manifest() -> None:
    reader = InMemoryContentReader(
        {
            "src/App.java": b"class App {}",
            "pom.xml": b"<project/>",
            "README.md": b"# App",
            "src/AppTest.java": b"class AppTest {}",
        }
    )
    builder = RepositoryInventoryBuilder(reader)
    paths = ["README.md", "src/AppTest.java", "pom.xml", "src/App.java"]

    first = builder.build(identity=_identity(), revision=_revision(), relative_paths=paths)
    second = builder.build(
        identity=_identity(),
        revision=_revision(),
        relative_paths=list(reversed(paths)),
    )

    assert [entry.path.root for entry in first.files] == [
        "README.md",
        "pom.xml",
        "src/App.java",
        "src/AppTest.java",
    ]
    assert first == second
    assert RepositoryFingerprintFactory.from_manifest(first) == (
        RepositoryFingerprintFactory.from_manifest(second)
    )

    by_path = {entry.path.root: entry for entry in first.files}
    assert by_path["pom.xml"].file_kind is RepositoryFileKind.DEPENDENCY_MANIFEST
    assert by_path["src/App.java"].file_kind is RepositoryFileKind.SOURCE
    assert by_path["src/App.java"].language == "Java"
    assert by_path["src/AppTest.java"].file_kind is RepositoryFileKind.TEST
    assert by_path["README.md"].file_kind is RepositoryFileKind.DOCUMENTATION
    assert by_path["README.md"].language == "Markdown"
    assert by_path["src/App.java"].fingerprint.algorithm.value == "sha256"
    assert len(by_path["src/App.java"].fingerprint.digest) == 64


def test_changed_content_changes_fingerprint() -> None:
    builder_a = RepositoryInventoryBuilder(InMemoryContentReader({"src/App.java": b"class App {}"}))
    builder_b = RepositoryInventoryBuilder(
        InMemoryContentReader({"src/App.java": b"class App { void x() {} }"})
    )
    manifest_a = builder_a.build(
        identity=_identity(),
        revision=_revision(),
        relative_paths=["src/App.java"],
    )
    manifest_b = builder_b.build(
        identity=_identity(),
        revision=_revision(),
        relative_paths=["src/App.java"],
    )
    assert manifest_a.files[0].fingerprint != manifest_b.files[0].fingerprint
    assert RepositoryFingerprintFactory.from_manifest(manifest_a) != (
        RepositoryFingerprintFactory.from_manifest(manifest_b)
    )


def test_local_filesystem_content_reader_and_builder(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    java_file = tmp_path / "src" / "App.java"
    java_file.write_text("class App {}\n", encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project/>\n", encoding="utf-8")

    reader = LocalFilesystemContentReader(tmp_path)
    builder = RepositoryInventoryBuilder(reader)
    manifest = builder.build(
        identity=_identity(),
        revision=_revision(),
        relative_paths=["pom.xml", r"src\App.java"],
    )

    assert len(manifest.files) == 2
    assert manifest.files[0].path.root == "pom.xml"
    assert manifest.files[1].path.root == "src/App.java"
    assert manifest.files[1].language == "Java"
    assert manifest.files[1].size_bytes == java_file.stat().st_size

    with pytest.raises(Exception, match="unique"):
        builder.build(
            identity=_identity(),
            revision=_revision(),
            relative_paths=["pom.xml", "src/App.java", "src/App.java"],
        )


def test_content_reader_rejects_path_escape(tmp_path: Path) -> None:
    reader = LocalFilesystemContentReader(tmp_path)
    with pytest.raises(ValueError, match="traversal|absolute|blank"):
        reader.read("../secret.txt")
