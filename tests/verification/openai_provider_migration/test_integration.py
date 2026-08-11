"""End-to-end SV.11.6 runs: verdict, determinism, privacy, and artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from verification.openai_provider_migration.contract import (
    ALLOWED_VERDICTS,
    EXPECTED_LIMITATIONS,
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
)

from verification.openai_provider_migration import determinism, reporting, runner

ENGINE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("sv11-6")
    return runner.run_openai_provider_migration_verification(
        engine_root=ENGINE_ROOT,
        output_dir=out,
    ), out


def test_the_suite_reaches_the_expected_verdict(report) -> None:
    result, _ = report

    assert result.verdict == "pass_with_limitations"
    assert runner.verdict_is_acceptable(result.verdict)


def test_no_check_fails(report) -> None:
    result, _ = report

    failures = [(check.name, check.detail) for check in result.checks if not check.ok]
    assert not failures, failures


def test_no_negative_scenario_holds(report) -> None:
    result, _ = report

    failures = [(s.scenario_id, s.detail) for s in result.negative_scenarios if not s.ok]
    assert not failures, failures


def test_the_report_identity_is_pinned(report) -> None:
    result, _ = report

    assert result.schema_name == SCHEMA_NAME
    assert result.schema_version == SCHEMA_VERSION
    assert result.slice_id == SLICE_ID
    assert result.compatibility_requirement_ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


def test_the_recorded_limitations_are_exactly_the_expected_ones(report) -> None:
    result, _ = report

    assert result.limitations == EXPECTED_LIMITATIONS


def test_the_check_counts_agree_with_the_check_list(report) -> None:
    result, _ = report

    assert result.check_counts["total"] == len(result.checks)
    assert result.check_counts["failed"] == 0
    assert result.check_counts["passed"] == len(result.checks)


def test_both_artifacts_are_written(report) -> None:
    result, out = report

    json_path = out / REPORT_FILENAME
    md_path = out / REPORT_MD_FILENAME

    assert json_path.is_file()
    assert md_path.is_file()
    assert json.loads(json_path.read_text(encoding="utf-8")) == result.to_dict()
    assert result.verdict in md_path.read_text(encoding="utf-8")


def test_markdown_can_be_suppressed(tmp_path: Path) -> None:
    runner.run_openai_provider_migration_verification(
        engine_root=ENGINE_ROOT,
        output_dir=tmp_path,
        write_markdown=False,
    )

    assert (tmp_path / REPORT_FILENAME).is_file()
    assert not (tmp_path / REPORT_MD_FILENAME).exists()


def test_two_runs_produce_byte_identical_reports(tmp_path: Path) -> None:
    first = runner.run_openai_provider_migration_verification(
        engine_root=ENGINE_ROOT, output_dir=tmp_path / "a"
    )
    second = runner.run_openai_provider_migration_verification(
        engine_root=ENGINE_ROOT, output_dir=tmp_path / "b"
    )

    assert determinism.reports_are_identical(first.to_dict(), second.to_dict())
    assert determinism.stable_hash(first.to_dict()) == determinism.stable_hash(second.to_dict())
    assert (tmp_path / "a" / REPORT_FILENAME).read_bytes() == (
        tmp_path / "b" / REPORT_FILENAME
    ).read_bytes()


def test_the_written_report_has_no_forbidden_tokens(report) -> None:
    _, out = report

    blob = (out / REPORT_FILENAME).read_text(encoding="utf-8")
    assert reporting.report_contains_forbidden_leak(blob) == []


def test_the_report_body_carries_no_timestamp_or_duration(report) -> None:
    """No wall-clock value anywhere, which is what makes two runs identical.

    Key names such as ``generated_at`` are checked structurally; the values are
    checked with an ISO-8601 pattern, since some check *names* legitimately
    contain the word "timestamp".
    """

    result, _ = report
    payload = result.to_dict()

    assert not {"generated_at", "generated_on", "duration_ms", "elapsed_ms"} & set(payload)
    blob = determinism.canonical_json(payload)
    assert not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", blob)


def test_the_report_records_the_mixed_mode_and_single_attempt_warnings(report) -> None:
    result, _ = report

    joined = " ".join(result.warnings).lower()
    assert "mixed mode" in joined
    assert "one attempt" in joined


def test_the_default_output_location_is_the_slice_directory() -> None:
    engine = runner.engine_root_from_package()

    assert (engine / "pyproject.toml").is_file()
    assert runner._default_output_dir(engine) == (
        engine / "reports" / "verification" / "sv11-6"
    )


def test_every_allowed_verdict_is_accepted() -> None:
    for verdict in ALLOWED_VERDICTS:
        assert runner.verdict_is_acceptable(verdict)
    assert not runner.verdict_is_acceptable("fail")
