"""Quality-command manifest loading, sanitization, and status honesty."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from verification.quality_commands import (
    QualityCommand,
    load_manifest,
    overall_status,
    run_command,
    run_suite,
)

MANIFEST = Path(__file__).resolve().parents[2] / "verification" / "quality-commands.yaml"


def test_manifest_pins_product_coverage_floor_and_engine_tests_gap() -> None:
    manifest = load_manifest(MANIFEST)
    assert manifest.package_revision == "ENGINE-2026-09-15-R1"
    assert manifest.coverage_source == "codestrata"
    assert manifest.coverage_floor == 80
    assert manifest.branch_measurement is True
    assert manifest.engine_tests_job["present_in_clone"] is False
    assert manifest.engine_tests_job["collects_engine_tests_verification"] is False
    assert manifest.security_scanner["id"] == "pip-audit"
    product = {cmd.id: cmd for cmd in manifest.commands if cmd.suite == "product"}
    assert product["ruff"].record_as_baseline is True
    assert product["mypy"].record_as_baseline is True
    assert product["pytest_product_coverage"].record_as_baseline is True


def test_baseline_failure_is_not_classified_pass(tmp_path: Path) -> None:
    command = QualityCommand(
        id="always_fail",
        argv=(sys.executable, "-c", "raise SystemExit(1)"),
        suite="product",
        cwd="repository_root",
        record_as_baseline=True,
        notes="fixture",
        optional=False,
    )
    result = run_command(command, tmp_path)
    assert result.exit_code == 1
    assert result.status == "BASELINE_FAIL"
    assert overall_status((result,)) == "BASELINE_FAIL"


def test_new_harness_failure_is_fail_not_baseline(tmp_path: Path) -> None:
    command = QualityCommand(
        id="harness_fail",
        argv=(sys.executable, "-c", "raise SystemExit(1)"),
        suite="harness",
        cwd="repository_root",
        record_as_baseline=False,
        notes="",
        optional=False,
    )
    result = run_command(command, tmp_path)
    assert result.status == "FAIL"
    assert overall_status((result,)) == "FAIL"


def test_missing_optional_module_is_blocked_not_clean(tmp_path: Path) -> None:
    command = QualityCommand(
        id="missing",
        argv=(sys.executable, "-c", "import codestrata_missing_scanner_mod"),
        suite="security",
        cwd="repository_root",
        record_as_baseline=False,
        notes="",
        optional=True,
    )
    result = run_command(command, tmp_path)
    assert result.status == "BLOCKED"
    assert result.exit_code != 0
    assert overall_status((result,)) == "BLOCKED"


def test_publish_credentials_are_stripped_from_command_env(tmp_path: Path) -> None:
    command = QualityCommand(
        id="env_probe",
        argv=(
            sys.executable,
            "-c",
            "import os,sys; "
            "sys.exit(1 if os.environ.get('TWINE_PASSWORD') "
            "or os.environ.get('PYPI_TOKEN') else 0)",
        ),
        suite="harness",
        cwd="repository_root",
        record_as_baseline=False,
        notes="",
        optional=False,
    )
    env = dict(os.environ)
    env["TWINE_PASSWORD"] = "should-not-be-forwarded"
    env["PYPI_TOKEN"] = "should-not-be-forwarded"
    result = run_command(command, tmp_path, env=env)
    assert result.exit_code == 0
    assert result.status == "PASS"


def test_run_suite_selects_only_requested_suite(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST)
    # Empty suite name matches nothing.
    results = tuple(cmd for cmd in manifest.commands if cmd.suite == "does-not-exist")
    assert results == ()
    assert run_suite(manifest, tmp_path, suite="does-not-exist") == ()
