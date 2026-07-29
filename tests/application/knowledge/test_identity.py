"""Tests for knowledge-store identity normalization and models."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from codestrata.application.knowledge import (
    RepositoryIdentityError,
    RepositoryIdentityHints,
    RepositoryRecord,
    build_github_canonical_key,
    normalize_identity_hints,
)
from codestrata.domain.repository.enums import RepositorySourceType


def test_github_canonical_key_is_lowercase() -> None:
    assert build_github_canonical_key("OpenAI", "Example") == "github:openai/example"


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/OpenAI/example",
        "https://github.com/OpenAI/example.git",
        "https://github.com/OpenAI/example/",
        "git@github.com:OpenAI/example.git",
        "ssh://git@github.com/OpenAI/example.git",
        "HTTPS://GitHub.com/OpenAI/example.git",
    ],
)
def test_equivalent_github_urls_share_canonical_key(url: str) -> None:
    normalized = normalize_identity_hints(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="example",
            source_location=url,
        )
    )
    assert normalized.canonical_key == "github:openai/example"
    assert normalized.source_type is RepositorySourceType.GITHUB
    assert any(a.alias_value == "https://github.com/openai/example.git" for a in normalized.aliases)


def test_credential_url_rejected() -> None:
    with pytest.raises(RepositoryIdentityError, match="credential"):
        normalize_identity_hints(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="example",
                source_location="https://user:token@github.com/OpenAI/example.git",
            )
        )


def test_query_token_rejected() -> None:
    with pytest.raises(RepositoryIdentityError, match="query"):
        normalize_identity_hints(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="example",
                source_location="https://github.com/OpenAI/example.git?token=secret",
            )
        )


def test_local_path_is_alias_not_canonical(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    normalized = normalize_identity_hints(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="repo",
            local_path=root,
            existing_repository_key="My-Repo",
        )
    )
    assert normalized.canonical_key is None
    assert any(a.alias_type.value == "local_path" for a in normalized.aliases)
    assert any(
        a.alias_type.value == "legacy_repository_key" and a.alias_value == "my-repo"
        for a in normalized.aliases
    )


def test_local_with_github_remote_uses_github_canonical(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    normalized = normalize_identity_hints(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="checkout",
            source_location="https://github.com/Acme/App.git",
            local_path=root,
        )
    )
    assert normalized.canonical_key == "github:acme/app"
    assert normalized.source_type is RepositorySourceType.GITHUB


def test_repository_record_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValidationError):
        RepositoryRecord(
            repository_id=str(uuid4()),
            canonical_key="local:x",
            source_type=RepositorySourceType.LOCAL,
            display_name="x",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
