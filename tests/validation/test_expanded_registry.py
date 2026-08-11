"""Slice 4.13 — expanded validation registry tests."""

from __future__ import annotations

import re

from validation.matrix import ACTIVE_VALIDATION_SET, VALIDATION_MATRIX
from validation.models import RepositorySourceType
from validation.paths import EXPECTATIONS_DIR, REPOSITORIES_DIR, resolve_local_path
from validation.registry import load_all_repositories, resolve_expected_results

_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def test_active_set_size_in_expanded_range() -> None:
    definitions = load_all_repositories()
    enabled = [item for item in definitions if item.enabled]
    assert 20 <= len(enabled) <= 30
    assert len(enabled) == len(ACTIVE_VALIDATION_SET)
    assert {item.repository_id for item in enabled} == set(ACTIVE_VALIDATION_SET)


def test_repository_ids_unique() -> None:
    definitions = load_all_repositories()
    ids = [item.repository_id for item in definitions]
    assert len(ids) == len(set(ids))


def test_every_active_repository_has_definition_and_expectation() -> None:
    definitions = {item.repository_id: item for item in load_all_repositories()}
    for repository_id in ACTIVE_VALIDATION_SET:
        assert repository_id in definitions, repository_id
        definition = definitions[repository_id]
        assert definition.enabled
        expected = resolve_expected_results(definition)
        path = EXPECTATIONS_DIR / f"{repository_id}.json"
        assert path.is_file()
        assert expected.schema_version == "1.2"
        assert expected.expect_ai_executed is False


def test_remotes_are_pinned_without_credentials() -> None:
    for definition in load_all_repositories():
        if definition.source_type != RepositorySourceType.REMOTE:
            continue
        assert definition.remote_url
        assert definition.remote_url.startswith("https://")
        host = definition.remote_url.split("://", 1)[-1].split("/", 1)[0]
        assert "@" not in host
        assert "token=" not in definition.remote_url.lower()
        assert definition.pinned_ref
        assert _COMMIT_SHA_RE.match(definition.pinned_ref)
        assert definition.expected_commit
        assert definition.local_path is None


def test_matrix_has_pinned_source_identity_for_active_set() -> None:
    assert set(VALIDATION_MATRIX) == set(ACTIVE_VALIDATION_SET)
    for repository_id in ACTIVE_VALIDATION_SET:
        row = VALIDATION_MATRIX[repository_id]
        assert row["pinned_source_identity"]
        assert "/Users/" not in row["pinned_source_identity"]


def test_local_paths_resolve_for_active_locals() -> None:
    for definition in load_all_repositories():
        if definition.repository_id not in ACTIVE_VALIDATION_SET:
            continue
        if definition.source_type != RepositorySourceType.LOCAL:
            continue
        assert definition.local_path
        assert not definition.local_path.startswith("/")
        resolved = resolve_local_path(definition.local_path)
        assert resolved.is_dir(), definition.repository_id


def test_repository_definition_files_cover_active_set() -> None:
    files = {path.stem for path in REPOSITORIES_DIR.glob("*.toml")}
    for repository_id in ACTIVE_VALIDATION_SET:
        assert repository_id in files
