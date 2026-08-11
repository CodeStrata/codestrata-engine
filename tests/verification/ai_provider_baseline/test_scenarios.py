"""SV.11.1 negative scenario (A-Z) unit tests."""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_baseline.contract import NEGATIVE_SCENARIO_COUNT_MIN
from verification.ai_provider_baseline.models import CheckResult
from verification.ai_provider_baseline.runner import (
    engine_root_from_package,
    run_ai_provider_baseline,
)

from verification.ai_provider_baseline import boundaries, scenarios

ENGINE_ROOT = engine_root_from_package()
SOURCE_ROOT = ENGINE_ROOT / "src" / "codestrata"


def _checks_by_name(tmp_path: Path) -> dict[str, CheckResult]:
    report = run_ai_provider_baseline(engine_root=ENGINE_ROOT, output_dir=tmp_path / "reports")
    return {check.name: check for check in report.checks}


def test_negative_scenarios_meet_minimum_count_and_all_pass(tmp_path: Path) -> None:
    checks_by_name = _checks_by_name(tmp_path)
    result = scenarios.build_negative_scenarios(
        SOURCE_ROOT,
        checks_by_name=checks_by_name,
        report_payload_preview={"matrices": {}, "coupling_inventory": []},
    )
    assert len(result) >= NEGATIVE_SCENARIO_COUNT_MIN
    failing = [(s.scenario_id, s.title, s.detail) for s in result if not s.ok]
    assert not failing, failing
    scenario_ids = {s.scenario_id for s in result}
    assert scenario_ids.issuperset(set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:NEGATIVE_SCENARIO_COUNT_MIN]))


def test_scenario_z_does_not_false_positive_on_its_own_prose() -> None:
    """Regression: scenario Z's own docstring/title mentions 'git commit' and
    'subprocess' in prose; it must not flag itself or scenarios.py."""

    result = scenarios._scenario_z_no_git_commit_invocation(SOURCE_ROOT)  # noqa: SLF001
    assert result.ok is True
    assert "scenarios.py" not in result.detail


def test_scenario_z_detects_real_subprocess_usage(tmp_path: Path) -> None:
    package_dir = tmp_path / "verification" / "ai_provider_baseline"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "evil.py").write_text(
        "import subprocess\nsubprocess.run(['git', 'commit', '-m', 'x'])\n",
        encoding="utf-8",
    )
    fake_source_root = tmp_path / "src" / "codestrata"
    fake_source_root.mkdir(parents=True)

    result = scenarios._scenario_z_no_git_commit_invocation(fake_source_root)  # noqa: SLF001
    assert result.ok is False
    assert "evil.py" in result.detail


def test_boundary_no_openrouter_references() -> None:
    check = boundaries.check_no_openrouter_references(SOURCE_ROOT)
    assert check.ok is True


def test_boundary_no_new_common_provider_interface() -> None:
    check = boundaries.check_no_new_common_provider_interface(SOURCE_ROOT)
    assert check.ok is True


def test_boundary_ai_providers_directory_has_no_unexpected_files() -> None:
    check = boundaries.check_no_new_files_in_ai_providers_directory(SOURCE_ROOT)
    assert check.ok is True
