"""Repository registration and alias integration tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from codestrata.application.knowledge import (
    RepositoryAliasConflictError,
    RepositoryAliasType,
    RepositoryIdentityConflictError,
    RepositoryIdentityError,
    RepositoryIdentityHints,
)
from codestrata.domain.repository.enums import RepositorySourceType
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore


@pytest.fixture
def store(tmp_path: Path) -> SqliteKnowledgeStore:
    knowledge = SqliteKnowledgeStore(tmp_path / "knowledge")
    knowledge.open()
    yield knowledge
    knowledge.close()


def test_register_github_repository(store: SqliteKnowledgeStore) -> None:
    record = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="Example",
            source_location="https://github.com/OpenAI/example.git",
        )
    )
    assert record.canonical_key == "github:openai/example"
    assert record.source_type is RepositorySourceType.GITHUB
    assert store.registry.get_by_canonical_key("github:openai/example") == record


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/OpenAI/example",
        "https://github.com/OpenAI/example.git",
        "git@github.com:OpenAI/example.git",
        "ssh://git@github.com/OpenAI/example.git",
    ],
)
def test_equivalent_github_urls_resolve_same_repository(
    store: SqliteKnowledgeStore,
    url: str,
) -> None:
    first = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="Example",
            source_location="https://github.com/OpenAI/example.git",
        )
    )
    second = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="Example Renamed",
            source_location=url,
        )
    )
    assert second.repository_id == first.repository_id
    assert second.display_name == "Example Renamed"
    assert second.canonical_key == first.canonical_key


def test_github_forks_remain_separate(store: SqliteKnowledgeStore) -> None:
    upstream = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="app",
            source_location="https://github.com/acme/app.git",
        )
    )
    fork = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="app",
            source_location="https://github.com/contributor/app.git",
        )
    )
    assert upstream.repository_id != fork.repository_id
    assert upstream.canonical_key == "github:acme/app"
    assert fork.canonical_key == "github:contributor/app"


def test_same_repo_two_local_paths_resolve_via_remote(
    store: SqliteKnowledgeStore,
    tmp_path: Path,
) -> None:
    path_a = tmp_path / "clone-a"
    path_b = tmp_path / "clone-b"
    path_a.mkdir()
    path_b.mkdir()
    first = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="app",
            source_location="https://github.com/acme/app.git",
            local_path=path_a,
        )
    )
    second = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="app",
            source_location="https://github.com/acme/app.git",
            local_path=path_b,
        )
    )
    assert second.repository_id == first.repository_id
    aliases = store.registry.list_aliases(first.repository_id)
    paths = {a.alias_value for a in aliases if a.alias_type is RepositoryAliasType.LOCAL_PATH}
    assert str(path_a.resolve()) in paths
    assert str(path_b.resolve()) in paths


def test_local_without_remote_stable_across_reopen(tmp_path: Path) -> None:
    store_dir = tmp_path / "knowledge"
    local = tmp_path / "local-app"
    local.mkdir()
    with SqliteKnowledgeStore(store_dir) as store:
        created = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.LOCAL,
                display_name="local-app",
                local_path=local,
            )
        )
        assert created.canonical_key == f"local:{created.repository_id}"
        repository_id = created.repository_id

    with SqliteKnowledgeStore(store_dir) as store:
        resolved = store.registry.resolve_alias(
            RepositoryAliasType.LOCAL_PATH,
            str(local.resolve()),
        )
        assert resolved is not None
        assert resolved.repository_id == repository_id
        assert resolved.canonical_key == f"local:{repository_id}"


def test_legacy_repository_key_alias_resolves(store: SqliteKnowledgeStore) -> None:
    created = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="Pet Clinic",
            existing_repository_key="spring-petclinic",
        )
    )
    found = store.registry.resolve_alias(
        RepositoryAliasType.LEGACY_REPOSITORY_KEY,
        "spring-petclinic",
    )
    assert found is not None
    assert found.repository_id == created.repository_id


def test_same_display_name_does_not_collide(store: SqliteKnowledgeStore) -> None:
    a = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="app",
            source_location="https://github.com/one/app.git",
        )
    )
    b = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="app",
            source_location="https://github.com/two/app.git",
        )
    )
    assert a.repository_id != b.repository_id


def test_conflicting_aliases_fail_explicitly(
    store: SqliteKnowledgeStore,
    tmp_path: Path,
) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    first = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="one",
            local_path=shared,
        )
    )
    other = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="other",
            source_location="https://github.com/acme/other.git",
        )
    )
    with pytest.raises(RepositoryAliasConflictError):
        store.registry.add_alias(
            other.repository_id,
            RepositoryAliasType.LOCAL_PATH,
            str(shared.resolve()),
        )
    assert (
        store.registry.resolve_alias(
            RepositoryAliasType.LOCAL_PATH,
            str(shared.resolve()),
        ).repository_id
        == first.repository_id
    )


def test_identity_hints_conflict_across_repositories(
    store: SqliteKnowledgeStore,
    tmp_path: Path,
) -> None:
    path = tmp_path / "checkout"
    path.mkdir()
    store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="a",
            source_location="https://github.com/acme/a.git",
        )
    )
    store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="b",
            local_path=path,
        )
    )
    # Force conflict: claim GitHub A while also presenting path already bound to B.
    with pytest.raises(RepositoryIdentityConflictError):
        store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.LOCAL,
                display_name="mixed",
                source_location="https://github.com/acme/a.git",
                local_path=path,
            )
        )


def test_registration_aliases_are_atomic(
    store: SqliteKnowledgeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = store.registry._insert_alias  # noqa: SLF001
    calls = {"n": 0}

    def fail_second(*args: object, **kwargs: object) -> None:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(store.registry, "_insert_alias", fail_second)
    with pytest.raises(RuntimeError, match="boom"):
        store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="app",
                source_location="https://github.com/acme/atomic.git",
                existing_repository_key="atomic-app",
            )
        )
    assert store.registry.get_by_canonical_key("github:acme/atomic") is None
    assert store.registry.list_repositories() == ()


def test_display_name_update_keeps_repository_id(store: SqliteKnowledgeStore) -> None:
    first = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="Old",
            source_location="https://github.com/acme/rename.git",
        )
    )
    second = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="New",
            source_location="https://github.com/acme/rename.git",
        )
    )
    assert second.repository_id == first.repository_id
    assert second.display_name == "New"


def test_canonical_key_uniqueness_enforced(store: SqliteKnowledgeStore) -> None:
    store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="app",
            source_location="https://github.com/acme/unique.git",
        )
    )
    # Bypass register_or_resolve and attempt a duplicate insert.
    with pytest.raises(sqlite3.IntegrityError):
        store.registry._connection.execute(  # noqa: SLF001
            """
            INSERT INTO repositories(
                repository_id, canonical_key, source_type,
                display_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                "github:acme/unique",
                "github",
                "dup",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )


def test_sql_injection_treated_as_value(store: SqliteKnowledgeStore) -> None:
    malicious = "https://github.com/acme/app.git'; DROP TABLE repositories;--"
    # Invalid GitHub repo name characters / path → identity error, not SQL exec.
    with pytest.raises(RepositoryIdentityError):
        store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="x",
                source_location=malicious,
            )
        )
    assert store.registry.list_repositories() == ()


def test_no_source_contents_persisted(
    store: SqliteKnowledgeStore,
    tmp_path: Path,
) -> None:
    root = tmp_path / "src-app"
    root.mkdir()
    secret = root / "Secret.java"
    secret.write_text("class Secret {}", encoding="utf-8")
    store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="src-app",
            local_path=root,
        )
    )
    raw = store.database_path.read_bytes()
    assert b"class Secret" not in raw
    assert b"password" not in raw.lower()
