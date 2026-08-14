"""Slice 4.11 — permanent per-repository validation records."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.models import (
    ActualAssessmentResult,
    ComparisonMismatch,
    ComparisonOutcome,
    ExpectedResults,
    PackPrecisionRecord,
    RepositorySourceType,
    ValidationRepository,
    ValidationVerdict,
)
from validation.recording import (
    build_repository_validation_record,
    list_run_ids,
    load_repository_validation_record,
    new_run_id,
    write_repository_validation_record,
)
from validation.runner import run_repository_validation


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


def test_new_run_id_shape() -> None:
    run_id = new_run_id()
    assert len(run_id) == 16
    assert run_id.endswith("Z")
    assert run_id[8] == "T"


def test_write_and_load_record_bundle(tmp_path: Path) -> None:
    expected = ExpectedResults(schema_version="1.2", technology_facts_expected=("JavaScript",))
    actual = ActualAssessmentResult(
        schema_version="1.2",
        technologies=("JavaScript",),
        finding_rule_ids=("rule-a",),
        findings_count=1,
        ai_executed=False,
    )
    outcome = ComparisonOutcome(
        mismatches=(),
        expectations_evaluated=2,
        expectations_matched=2,
        pack_precision=(
            PackPrecisionRecord(
                pack="technology_inventory",
                true_positives=1,
                false_positives=0,
                false_negatives=0,
                precision=1.0,
                recall=1.0,
                passed=True,
            ),
        ),
    )
    record = build_repository_validation_record(
        repository_id="demo-repo",
        run_id="20260801T120000Z",
        verdict=ValidationVerdict.PASS,
        expected=expected,
        actual=actual,
        outcome=outcome,
        ai_executed=False,
    )
    run_dir = write_repository_validation_record(record, records_root=tmp_path)
    assert run_dir.name == "20260801T120000Z"
    for name in ("expected.json", "actual.json", "comparison.json", "record.json"):
        assert (run_dir / name).is_file()
        assert (tmp_path / "demo-repo" / "latest" / name).is_file()

    loaded = load_repository_validation_record(run_dir)
    assert loaded.verdict == ValidationVerdict.PASS
    assert loaded.expected["schema_version"] == "1.2"
    assert loaded.actual["technologies"] == ["JavaScript"]
    assert loaded.comparison["expectations_matched"] == 2
    assert loaded.pack_precision[0].pack == "technology_inventory"
    assert loaded.pack_precision[0].precision == 1.0
    assert "report_document" not in loaded.actual
    assert list_run_ids("demo-repo", records_root=tmp_path) == ("20260801T120000Z",)


def test_record_contains_mismatches_and_no_abs_home_paths(tmp_path: Path) -> None:
    outcome = ComparisonOutcome(
        mismatches=(
            ComparisonMismatch(
                repository_id="demo",
                assessment_area="findings",
                expectation="required rule-a",
                actual="absent",
                artifact_path="/Users/someone/secret/report.json",
                diagnostic="missing",
            ),
        ),
        expectations_evaluated=1,
        expectations_matched=0,
    )
    record = build_repository_validation_record(
        repository_id="demo",
        run_id="20260801T120001Z",
        verdict=ValidationVerdict.FAIL,
        expected=ExpectedResults(schema_version="1.2"),
        actual=ActualAssessmentResult(schema_version="1.2"),
        outcome=outcome,
    )
    run_dir = write_repository_validation_record(record, records_root=tmp_path)
    comparison = json.loads((run_dir / "comparison.json").read_text(encoding="utf-8"))
    path = comparison["mismatches"][0]["artifact_path"]
    assert path == "report.json"
    assert "/Users/" not in json.dumps(comparison)


def test_runner_writes_permanent_record_without_keep_results(
    local_definition: ValidationRepository,
    tmp_path: Path,
) -> None:
    records_root = tmp_path / "records"
    result = run_repository_validation(
        local_definition,
        output_root=tmp_path / "assessment-out",
        keep_results=False,
        include_remote=False,
        local_only=True,
        records_root=records_root,
    )
    assert result.verdict == ValidationVerdict.PASS
    assert result.record_dir is not None
    latest = records_root / "local-sample-js" / "latest"
    record = load_repository_validation_record(latest)
    assert record.verdict == ValidationVerdict.PASS
    # ACTIVE_0_2_0: assessment.json is the manifest; schema_version 1.2 is not persisted.
    assert record.schema_version is None
    assert record.ai_executed is False
    assert record.expectations_evaluated >= 1
    assert "JavaScript" in record.actual.get("technologies", [])
    # Assessment cleaned; record retained.
    assert not (tmp_path / "assessment-out" / "local-sample-js").exists()


def test_repeat_runs_create_history_and_stable_latest(
    local_definition: ValidationRepository,
    tmp_path: Path,
) -> None:
    records_root = tmp_path / "records"
    first = run_repository_validation(
        local_definition,
        output_root=tmp_path / "a",
        keep_results=False,
        records_root=records_root,
    )
    second = run_repository_validation(
        local_definition,
        output_root=tmp_path / "b",
        keep_results=False,
        records_root=records_root,
    )
    assert first.verdict == second.verdict == ValidationVerdict.PASS
    run_ids = list_run_ids("local-sample-js", records_root=records_root)
    assert len(run_ids) >= 2
    latest = load_repository_validation_record(
        records_root / "local-sample-js" / "latest"
    )
    assert latest.verdict == ValidationVerdict.PASS
    assert latest.run_id == run_ids[-1]
    # Deterministic actual snapshot fields for technology inventory.
    assert latest.actual["technologies"] == sorted(latest.actual["technologies"])


def test_skip_and_error_still_recorded(tmp_path: Path) -> None:
    remote = ValidationRepository(
        repository_id="remote-skip-record",
        display_name="Remote",
        source_type=RepositorySourceType.REMOTE,
        remote_url="https://github.com/example/repo.git",
        pinned_ref="v1.0.0",
        expected_results_path="expectations/local-sample-js.json",
    )
    skipped = run_repository_validation(
        remote,
        output_root=tmp_path / "out",
        include_remote=False,
        local_only=True,
        records_root=tmp_path / "records",
    )
    assert skipped.verdict == ValidationVerdict.SKIPPED
    loaded = load_repository_validation_record(
        tmp_path / "records" / "remote-skip-record" / "latest"
    )
    assert loaded.skip_reason
    assert loaded.comparison["verdict"] == "SKIPPED"
