"""Slice 4.2 — local set smoke execution and remote SKIP behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.actual import normalized_for_determinism, run_real_assessment
from validation.matrix import ACTIVE_VALIDATION_SET
from validation.models import RepositorySourceType, ValidationVerdict
from validation.paths import VALIDATION_ROOT
from validation.registry import filter_repositories, load_all_repositories
from validation.runner import run_repository_validation, run_validation_suite
from validation.summary import build_validation_summary, summary_to_safe_dict


@pytest.fixture(scope="module")
def local_definitions():
    definitions = load_all_repositories()
    return filter_repositories(definitions, local_only=True, include_remote=False)


def test_all_local_repositories_pass_smoke(local_definitions, tmp_path_factory) -> None:
    assert local_definitions
    assert all(item.source_type == RepositorySourceType.LOCAL for item in local_definitions)
    output_root = tmp_path_factory.mktemp("validation-local-smoke")
    results = run_validation_suite(
        local_definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        include_remote=False,
        local_only=True,
    )
    summary = build_validation_summary(results)
    assert summary.errors == 0
    assert summary.failed == 0
    assert summary.passed == len(local_definitions)
    for result in results:
        assert result.verdict == ValidationVerdict.PASS
        assert result.ai_executed is False
        assert result.artifact_dir is not None
        report_files = list(Path(result.artifact_dir).rglob("assessment.json"))
        assert report_files, result.repository_id
        document = json.loads(report_files[0].read_text(encoding="utf-8"))
        assert str(document.get("schema") or "").startswith("codestrata-assessment-manifest")
        blob = json.dumps(summary_to_safe_dict(summary))
        assert "/Users/" not in blob
        assert "BEGIN PRIVATE KEY" not in blob
        assert "function " not in blob


def test_remote_skipped_without_include_remote(tmp_path: Path) -> None:
    remote = next(
        item
        for item in load_all_repositories()
        if item.repository_id == "remote-java-spring-petclinic"
    )
    result = run_repository_validation(
        remote,
        output_root=tmp_path / "out",
        include_remote=False,
        local_only=True,
    )
    assert result.verdict == ValidationVerdict.SKIPPED
    assert result.skip_reason


@pytest.mark.parametrize(
    "repository_id",
    [
        "local-sample-js",
        "local-cloud-signals",
        "local-security-hygiene",
        "local-ai-readiness",
    ],
)
def test_controlled_fixture_determinism(repository_id: str, tmp_path: Path) -> None:
    definition = next(
        item for item in load_all_repositories() if item.repository_id == repository_id
    )
    assert definition.local_path
    repo_path = (VALIDATION_ROOT / definition.local_path).resolve()
    config_path = None
    if definition.assessment_config:
        config_path = VALIDATION_ROOT / definition.assessment_config
    first, _ = run_real_assessment(
        repository_path=repo_path,
        output_directory=tmp_path / "a",
        config_path=config_path,
    )
    second, _ = run_real_assessment(
        repository_path=repo_path,
        output_directory=tmp_path / "b",
        config_path=config_path,
    )
    assert normalized_for_determinism(first) == normalized_for_determinism(second)
    assert first.persisted_layout == "manifest_0_2_0"
    assert first.schema_version is None
    assert first.ai_executed is False


def test_active_set_listed_in_matrix_constant() -> None:
    assert 20 <= len(ACTIVE_VALIDATION_SET) <= 30
