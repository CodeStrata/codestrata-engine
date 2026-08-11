"""Slice 4.2 — validation set registry and matrix coverage tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from validation.matrix import ACTIVE_VALIDATION_SET, VALIDATION_MATRIX
from validation.models import RepositorySourceType
from validation.paths import EXPECTATIONS_DIR, REPOSITORIES_DIR, VALIDATION_ROOT, resolve_local_path
from validation.registry import load_all_repositories, resolve_expected_results


def test_active_set_size_is_expanded() -> None:
    definitions = load_all_repositories()
    enabled = [item for item in definitions if item.enabled]
    assert 20 <= len(enabled) <= 30
    assert len(enabled) == len(ACTIVE_VALIDATION_SET)
    assert {item.repository_id for item in enabled} == set(ACTIVE_VALIDATION_SET)


def test_repository_ids_unique_and_stable() -> None:
    definitions = load_all_repositories()
    ids = [item.repository_id for item in definitions]
    assert len(ids) == len(set(ids))
    for repository_id in ACTIVE_VALIDATION_SET:
        assert repository_id in ids


def test_every_repository_has_expectation_file() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        path = VALIDATION_ROOT / definition.expected_results_path
        assert path.is_file()
        assert expected.schema_version == "1.2"
        assert expected.expect_ai_executed is False
        assert "report.json" in expected.expected_artifacts


def test_remotes_are_pinned_without_floating_refs_or_credentials() -> None:
    for definition in load_all_repositories():
        if definition.source_type != RepositorySourceType.REMOTE:
            continue
        assert definition.remote_url
        assert definition.remote_url.startswith("https://")
        assert "@" not in definition.remote_url.split("://", 1)[-1].split("/", 1)[0]
        assert definition.pinned_ref
        assert definition.pinned_ref.lower() not in {"main", "master", "head", "develop"}
        assert definition.expected_commit
        assert definition.local_path is None


def test_local_paths_resolve_and_are_relative() -> None:
    for definition in load_all_repositories():
        if definition.source_type != RepositorySourceType.LOCAL:
            continue
        assert definition.local_path
        assert not Path(definition.local_path).is_absolute()
        resolved = resolve_local_path(definition.local_path)
        assert resolved.is_dir(), definition.repository_id
        assert not Path(definition.expected_results_path).is_absolute()


def test_matrix_covers_required_dimensions() -> None:
    assert set(VALIDATION_MATRIX) == set(ACTIVE_VALIDATION_SET)
    languages = {row["language"].split()[0] for row in VALIDATION_MATRIX.values()}
    assert len(languages) >= 2
    ecosystems = {
        row["ecosystem"]
        for row in VALIDATION_MATRIX.values()
        if row["ecosystem"] not in {"n/a", "Docker/Compose"}
    }
    assert len(ecosystems) >= 2

    def _has(tag_fragment: str) -> bool:
        return any(
            tag_fragment in ",".join(item.tags)
            for item in load_all_repositories()
            if item.enabled
        )

    assert _has("tests-present")
    assert _has("tests-absent") or any(
        "absent" in VALIDATION_MATRIX[rid]["test_posture"]
        or "limited" in VALIDATION_MATRIX[rid]["test_posture"]
        for rid in ACTIVE_VALIDATION_SET
    )
    assert _has("architecture")
    assert _has("technical-debt") or any(
        "measurable" in VALIDATION_MATRIX[rid]["td_coverage"]
        for rid in ACTIVE_VALIDATION_SET
    )
    assert _has("security")
    assert _has("cloud")
    assert _has("ai-readiness")


def test_controlled_security_and_ai_fixtures_exist() -> None:
    security = VALIDATION_ROOT / "fixtures" / "security-hygiene"
    ai = VALIDATION_ROOT / "fixtures" / "ai-readiness"
    cloud = VALIDATION_ROOT / "fixtures" / "cloud-signals"
    assert (security / "README.md").is_file()
    assert (security / "secrets" / "test-only.pem").is_file()
    pem = (security / "secrets" / "test-only.pem").read_text(encoding="utf-8")
    assert "TEST_ONLY" in pem or "CODESTRATA_TEST_ONLY" in pem
    assert "BEGIN PRIVATE KEY" in pem
    assert (ai / "mcp.json").is_file()
    assert (ai / "src" / "openai_agent.py").is_file()
    assert (cloud / "Dockerfile").is_file()
    assert (cloud / "k8s" / "deployment.yaml").is_file()


def test_repository_definition_files_match_set() -> None:
    files = sorted(path.stem for path in REPOSITORIES_DIR.glob("*.toml"))
    assert set(files) == set(ACTIVE_VALIDATION_SET)
    expectation_files = sorted(path.name for path in EXPECTATIONS_DIR.glob("*.json"))
    for repository_id in ACTIVE_VALIDATION_SET:
        assert f"{repository_id}.json" in expectation_files
