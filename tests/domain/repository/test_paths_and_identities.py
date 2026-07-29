"""Tests for RepositoryPath and repository identity/revision contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from codestrata.domain.repository import (
    RepositoryIdentity,
    RepositoryPath,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)


def test_repository_path_normalization() -> None:
    assert RepositoryPath("src/App.java").root == "src/App.java"
    assert RepositoryPath(r"src\main\App.java").root == "src/main/App.java"
    assert RepositoryPath("src//main///App.java").root == "src/main/App.java"
    assert RepositoryPath("./src/App.java").root == "src/App.java"
    assert RepositoryPath("Src/App.JAVA").root == "Src/App.JAVA"


def test_repository_path_rejections() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        RepositoryPath("/abs/App.java")
    with pytest.raises(ValidationError, match="absolute"):
        RepositoryPath("C:/Windows/App.java")
    with pytest.raises(ValidationError, match=r"\.\."):
        RepositoryPath("../secret")
    with pytest.raises(ValidationError, match=r"\.\."):
        RepositoryPath("source/../../file")
    with pytest.raises(ValidationError, match="blank"):
        RepositoryPath(" ")
    with pytest.raises(ValidationError, match="blank"):
        RepositoryPath(".")


def test_repository_identity_validation() -> None:
    identity = RepositoryIdentity(
        repository_key="petclinic",
        source_type=RepositorySourceType.GITHUB,
        display_name="Spring Petclinic",
        source_location="https://github.com/spring-projects/spring-petclinic",
    )
    assert identity.repository_key == "petclinic"

    with pytest.raises(ValidationError, match="blank"):
        RepositoryIdentity(
            repository_key=" ",
            source_type=RepositorySourceType.LOCAL,
            display_name="x",
        )
    with pytest.raises(ValidationError, match="blank"):
        RepositoryIdentity(
            repository_key="petclinic",
            source_type=RepositorySourceType.LOCAL,
            display_name=" ",
        )
    with pytest.raises(ValidationError, match="credential"):
        RepositoryIdentity(
            repository_key="petclinic",
            source_type=RepositorySourceType.GIT,
            display_name="x",
            source_location="https://user:token@github.com/org/repo",
        )


def test_repository_revision_validation() -> None:
    aware = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    commit = RepositoryRevision(
        revision_id="abc123",
        revision_type=RepositoryRevisionType.COMMIT,
        branch="main",
        captured_at=aware,
    )
    assert commit.branch == "main"

    working = RepositoryRevision(
        revision_id="fingerprint:deadbeef",
        revision_type=RepositoryRevisionType.WORKING_TREE,
    )
    assert working.tag is None

    with pytest.raises(ValidationError, match="blank"):
        RepositoryRevision(revision_id=" ", revision_type=RepositoryRevisionType.COMMIT)
    with pytest.raises(ValidationError, match="timezone-aware"):
        RepositoryRevision(
            revision_id="abc",
            revision_type=RepositoryRevisionType.COMMIT,
            captured_at=datetime(2026, 7, 22, 12, 0),
        )
