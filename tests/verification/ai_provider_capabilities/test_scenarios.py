"""Unit tests for verification.ai_provider_capabilities.scenarios (A-AC)."""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_capabilities.contract import NEGATIVE_SCENARIO_COUNT_MIN
from verification.ai_provider_capabilities.runner import (
    engine_root_from_package,
    run_ai_provider_capability_verification,
)

ENGINE_ROOT = engine_root_from_package()


def test_scenario_count_meets_the_documented_minimum(tmp_path: Path) -> None:
    report = run_ai_provider_capability_verification(engine_root=ENGINE_ROOT, output_dir=tmp_path)
    assert len(report.negative_scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN


def test_scenario_ids_are_unique(tmp_path: Path) -> None:
    report = run_ai_provider_capability_verification(engine_root=ENGINE_ROOT, output_dir=tmp_path)
    ids = [s.scenario_id for s in report.negative_scenarios]
    assert len(ids) == len(set(ids))


def test_every_scenario_has_a_non_empty_title_and_forbidden_condition(tmp_path: Path) -> None:
    report = run_ai_provider_capability_verification(engine_root=ENGINE_ROOT, output_dir=tmp_path)
    for scenario in report.negative_scenarios:
        assert scenario.title.strip()
        assert scenario.forbidden_condition.strip()


def test_all_scenarios_pass_against_the_real_package(tmp_path: Path) -> None:
    report = run_ai_provider_capability_verification(engine_root=ENGINE_ROOT, output_dir=tmp_path)
    failing = [s for s in report.negative_scenarios if not s.ok]
    assert failing == [], [(s.scenario_id, s.title, s.detail) for s in failing]
