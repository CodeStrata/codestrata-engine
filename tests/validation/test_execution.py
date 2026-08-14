"""Execution, verdict, cleanup, and determinism tests for the validation harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.actual import actual_from_report, normalized_for_determinism, run_real_assessment
from validation.models import (
    RepositorySourceType,
    ValidationRepository,
    ValidationVerdict,
)
from validation.runner import run_repository_validation
from validation.summary import build_validation_summary


@pytest.fixture
def local_definition() -> ValidationRepository:
    return ValidationRepository(
        repository_id="local-sample-js",
        display_name="Local sample JavaScript fixture",
        source_type=RepositorySourceType.LOCAL,
        local_path="../../test-fixtures/sample-js-app",
        expected_results_path="expectations/local-sample-js.json",
        tags=("local", "fixture"),
        languages=("javascript",),
    )


def test_real_assessment_path_produces_report_json(
    tmp_path: Path,
    test_fixtures_root: Path,
) -> None:
    repo = test_fixtures_root / "sample-js-app"
    assert repo.is_dir()
    actual, report_path = run_real_assessment(
        repository_path=repo,
        output_directory=tmp_path / "assessment",
    )
    assert report_path.is_file()
    assert report_path.name == "report.json" or report_path.suffix == ".json"
    assert actual.persisted_layout == "manifest_0_2_0"
    assert actual.schema_version is None
    assert actual.ai_executed is False
    assert "JavaScript" in actual.technologies
    assert actual.findings_count >= 1
    document = json.loads(report_path.read_text(encoding="utf-8"))
    assert str(document.get("schema") or "").startswith("codestrata-assessment-manifest")
    blob = json.dumps(normalized_for_determinism(actual))
    assert "function " not in blob
    assert "console.log" not in blob


def test_local_fixture_validation_pass_and_cleanup(
    local_definition: ValidationRepository,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "results"
    records_root = tmp_path / "records"
    result = run_repository_validation(
        local_definition,
        output_root=output_root,
        keep_results=False,
        include_remote=False,
        local_only=True,
        records_root=records_root,
    )
    assert result.verdict == ValidationVerdict.PASS
    assert result.ai_executed is False
    assert result.expectations_evaluated >= 1
    assert not (output_root / local_definition.repository_id).exists()
    # Permanent records survive assessment cleanup.
    assert result.record_dir is not None
    assert (records_root / local_definition.repository_id / "latest" / "record.json").is_file()


def test_keep_results_retains_artifacts(
    local_definition: ValidationRepository,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "results"
    records_root = tmp_path / "records"
    result = run_repository_validation(
        local_definition,
        output_root=output_root,
        keep_results=True,
        include_remote=False,
        local_only=True,
        records_root=records_root,
    )
    assert result.verdict == ValidationVerdict.PASS
    assert result.artifact_dir is not None
    assert Path(result.artifact_dir).is_dir()
    # ACTIVE_0_2_0_RELEASE_GATE: shipped layout emits assessment.json, not report.json.
    assert any(Path(result.artifact_dir).rglob("assessment.json"))
    assert (records_root / local_definition.repository_id / "latest" / "comparison.json").is_file()


def test_assessment_error_classified_as_error(tmp_path: Path) -> None:
    definition = ValidationRepository(
        repository_id="missing-local",
        display_name="Missing",
        source_type=RepositorySourceType.LOCAL,
        local_path="fixtures/does-not-exist",
        expected_results_path="expectations/local-sample-js.json",
    )
    # Path missing => SKIPPED (unavailable), not ERROR.
    skipped = run_repository_validation(
        definition,
        output_root=tmp_path / "out",
        keep_results=False,
        records_root=tmp_path / "records",
    )
    assert skipped.verdict == ValidationVerdict.SKIPPED

    bad_expected = ValidationRepository(
        repository_id="bad-expected",
        display_name="Bad expected",
        source_type=RepositorySourceType.LOCAL,
        local_path="../../test-fixtures/sample-js-app",
        expected_results_path="expectations/does-not-exist.json",
    )
    errored = run_repository_validation(
        bad_expected,
        output_root=tmp_path / "out2",
        keep_results=False,
        records_root=tmp_path / "records",
    )
    assert errored.verdict == ValidationVerdict.ERROR
    assert errored.error_message


def test_fail_verdict_when_expectations_miss(
    local_definition: ValidationRepository,
    tmp_path: Path,
) -> None:
    # Point at a temporary contradictory expectation file via a custom definition.
    expectations = tmp_path / "expectations"
    expectations.mkdir()
    expectation_path = expectations / "strict.json"
    expectation_path.write_text(
        json.dumps(
            {
                "technology_facts_forbidden": ["JavaScript"],
                "schema_version": "1.2",
            }
        ),
        encoding="utf-8",
    )
    # Place expectation relative to a temporary validation root.
    validation_root = tmp_path / "validation-root"
    (validation_root / "expectations").mkdir(parents=True)
    (validation_root / "expectations" / "strict.json").write_text(
        expectation_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    definition = ValidationRepository(
        repository_id="local-fail-case",
        display_name="Fail case",
        source_type=RepositorySourceType.LOCAL,
        local_path="../../test-fixtures/sample-js-app",
        expected_results_path="expectations/strict.json",
    )
    # local_path is resolved from validation_root; point relative path that still
    # reaches workspace fixtures by using an absolute-style relative climb from tmp.
    # Instead, symlink or use the real validation root local path trick:
    # Copy definition to use the package validation root path resolution by
    # writing expectation into the real expectations dir is undesirable.
    # Use resolve via custom validation_root with a symlink to the fixture.
    fixture_link = validation_root / "fixture"
    real_fixture = (
        Path(__file__).resolve().parents[3] / "test-fixtures" / "sample-js-app"
    )
    if not real_fixture.is_dir():
        real_fixture = Path(__file__).resolve().parents[2].parent / "test-fixtures" / "sample-js-app"
    fixture_link.symlink_to(real_fixture, target_is_directory=True)
    definition = ValidationRepository(
        repository_id="local-fail-case",
        display_name="Fail case",
        source_type=RepositorySourceType.LOCAL,
        local_path="fixture",
        expected_results_path="expectations/strict.json",
    )
    result = run_repository_validation(
        definition,
        output_root=tmp_path / "out",
        keep_results=False,
        validation_root=validation_root,
        records_root=tmp_path / "records",
    )
    assert result.verdict == ValidationVerdict.FAIL
    assert result.mismatches
    assert result.mismatches[0].assessment_area == "technology_inventory"
    assert (tmp_path / "records" / "local-fail-case" / "latest" / "comparison.json").is_file()


def test_remote_skipped_without_include_flag(tmp_path: Path) -> None:
    definition = ValidationRepository(
        repository_id="remote-example",
        display_name="Remote",
        source_type=RepositorySourceType.REMOTE,
        remote_url="https://github.com/example/repo.git",
        pinned_ref="v1.0.0",
        expected_results_path="expectations/local-sample-js.json",
    )
    result = run_repository_validation(
        definition,
        output_root=tmp_path / "out",
        include_remote=False,
        local_only=True,
        records_root=tmp_path / "records",
    )
    assert result.verdict == ValidationVerdict.SKIPPED


def test_determinism_repeated_local_runs(test_fixtures_root: Path, tmp_path: Path) -> None:
    repo = test_fixtures_root / "sample-js-app"
    first, _ = run_real_assessment(repository_path=repo, output_directory=tmp_path / "a")
    second, _ = run_real_assessment(repository_path=repo, output_directory=tmp_path / "b")
    left = normalized_for_determinism(first)
    right = normalized_for_determinism(second)
    assert left == right
    assert left["finding_rule_ids"] == right["finding_rule_ids"]
    assert "assessment_duration_ms" not in left


def test_actual_from_report_extracts_core_fields() -> None:
    document = {
        "schema_version": "1.2",
        "assessment": {
            "status": "completed",
            "summary": {"finding_count": 1, "recommendation_count": 1, "ai_executed": False},
            "ai": {"executed": False},
            "technologies": [{"name": "JavaScript"}],
            "findings": [{"id": "f1", "rule_id": "rule-a", "file": "./src/a.js"}],
            "recommendations": [{"id": "r1", "category": "security"}],
            "priority_actions": [{"category": "security"}],
            "security": {"status": "succeeded"},
            "roadmap": {"phases": [{"id": "phase-1"}]},
            "limitations": ["no-runtime"],
            "coverage": {"state": "partial"},
        },
    }
    actual = actual_from_report(document)
    assert actual.schema_version == "1.2"
    assert actual.technologies == ("JavaScript",)
    assert actual.finding_rule_ids == ("rule-a",)
    assert actual.evidence_paths == ("src/a.js",)
    assert actual.priority_action_categories == ("security",)
    assert actual.roadmap_phases == ("phase-1",)
    assert "no-runtime" in actual.limitations
    assert "security" in actual.assessment_heads
    assert actual.ai_executed is False


def test_summary_marks_durations_volatile_separately(
    local_definition: ValidationRepository,
    tmp_path: Path,
) -> None:
    result = run_repository_validation(
        local_definition,
        output_root=tmp_path / "out",
        keep_results=True,
        records_root=tmp_path / "records",
    )
    summary = build_validation_summary([result])
    assert result.repository_id in summary.repository_durations_ms
    # Durations exist on the in-memory summary but are not part of normalized actuals.
    assert result.duration_ms is not None
