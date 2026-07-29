"""Tests for data-driven file-kind classification."""

from __future__ import annotations

import pytest

from codestrata.domain.repository import RepositoryFileKind
from codestrata.services.inventory import RepositoryFileKindClassifier


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("pom.xml", RepositoryFileKind.DEPENDENCY_MANIFEST),
        ("package.json", RepositoryFileKind.DEPENDENCY_MANIFEST),
        ("build.gradle", RepositoryFileKind.BUILD),
        ("README.md", RepositoryFileKind.DOCUMENTATION),
        ("Dockerfile", RepositoryFileKind.INFRASTRUCTURE),
        ("docker-compose.yml", RepositoryFileKind.INFRASTRUCTURE),
        ("application.yml", RepositoryFileKind.CONFIGURATION),
        ("application.yaml", RepositoryFileKind.CONFIGURATION),
        ("src/main/resources/app.properties", RepositoryFileKind.CONFIGURATION),
        ("src/main/java/com/example/App.java", RepositoryFileKind.SOURCE),
        ("src/test/java/com/example/AppTest.java", RepositoryFileKind.TEST),
        ("src/main/java/com/example/AppTest.java", RepositoryFileKind.TEST),
        ("web/app.spec.ts", RepositoryFileKind.TEST),
        (".github/workflows/ci.yml", RepositoryFileKind.INFRASTRUCTURE),
        ("target/generated-sources/annotations/X.java", RepositoryFileKind.GENERATED),
        ("docs/guide.md", RepositoryFileKind.DOCUMENTATION),
        ("binary.dat", RepositoryFileKind.UNKNOWN),
    ],
)
def test_file_kind_classification(path: str, expected: RepositoryFileKind) -> None:
    assert RepositoryFileKindClassifier().classify(path) is expected


def test_generated_helper_filename_is_not_path_marker_false_positive() -> None:
    classifier = RepositoryFileKindClassifier()
    assert (
        classifier.classify("src/main/java/com/example/GeneratedHelper.java")
        is RepositoryFileKind.SOURCE
    )
