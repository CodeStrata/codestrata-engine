"""Negative scenarios A-Z: all pass today, and each is actually falsifiable."""

from __future__ import annotations

import ast
from pathlib import Path

from verification.openai_provider_migration.contract import (
    NEGATIVE_SCENARIO_COUNT_MIN,
    PACKAGE_RELATIVE_PATH,
)

from verification.openai_provider_migration import scenarios

ENGINE_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = ENGINE_ROOT / "src" / "codestrata" / PACKAGE_RELATIVE_PATH


def _scenarios() -> tuple:
    return scenarios.build_negative_scenarios(ENGINE_ROOT, PACKAGE_DIR)


def test_every_negative_scenario_passes() -> None:
    failures = [(s.scenario_id, s.title, s.detail) for s in _scenarios() if not s.ok]
    assert not failures, failures


def test_the_minimum_scenario_count_is_met() -> None:
    assert len(_scenarios()) >= NEGATIVE_SCENARIO_COUNT_MIN


def test_scenario_ids_are_unique_and_ordered() -> None:
    ids = [scenario.scenario_id for scenario in _scenarios()]
    assert len(ids) == len(set(ids))
    assert ids[:5] == ["A", "B", "C", "D", "E"]


def test_scenario_ids_cover_the_alphabet() -> None:
    ids = {scenario.scenario_id for scenario in _scenarios()}
    missing = sorted(set("ABCDEFGHIJKLMNOPQRSTUVWXYZ") - ids)
    assert not missing, missing


def test_every_scenario_states_a_forbidden_condition() -> None:
    for scenario in _scenarios():
        assert scenario.title
        assert scenario.forbidden_condition
        assert scenario.detail


def test_a_scenario_records_the_forbidden_condition_as_prose_not_a_negation() -> None:
    """The condition reads as the thing that must not happen."""

    for scenario in _scenarios():
        assert not scenario.forbidden_condition.startswith("not ")


def test_the_scenario_helper_inverts_the_holds_flag() -> None:
    holding = scenarios._scenario("Q1", "t", "f", holds=True, detail="d")
    absent = scenarios._scenario("Q2", "t", "f", holds=False, detail="d")

    assert holding.ok is False
    assert absent.ok is True


def test_a_scenario_fails_when_its_forbidden_condition_is_injected() -> None:
    """Prove the prompt-content scenario is falsifiable, not vacuously true."""

    original = scenarios._chat_messages
    try:
        scenarios._chat_messages = lambda _request: [{"role": "system", "content": "changed"}]  # type: ignore[assignment]
        assert scenarios.scenario_d_prompt_content_changed().ok is False
    finally:
        scenarios._chat_messages = original  # type: ignore[assignment]

    assert scenarios.scenario_d_prompt_content_changed().ok is True


def test_the_retry_scenario_is_falsifiable() -> None:
    from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy

    original = scenarios.OPENAI_RETRY_POLICY
    try:
        scenarios.OPENAI_RETRY_POLICY = AIProviderRetryPolicy(maximum_attempts=3)  # type: ignore[assignment]
        assert scenarios.scenario_f_retry_activated().ok is False
    finally:
        scenarios.OPENAI_RETRY_POLICY = original  # type: ignore[assignment]

    assert scenarios.scenario_f_retry_activated().ok is True


def test_the_scenario_matrix_records_ids_without_outcomes() -> None:
    items = _scenarios()
    matrix = scenarios.scenario_matrix(items)

    assert matrix["scenario_count"] == len(items)
    assert matrix["scenario_ids"] == [scenario.scenario_id for scenario in items]
    assert "ok" not in matrix


def test_scenarios_use_only_synthetic_fixtures() -> None:
    """Nothing in the scenario module reaches a real client or credential.

    Checked against the parsed module rather than its text: the scenarios
    *describe* forbidden environment reads in prose, so a substring search would
    flag its own description.
    """

    tree = ast.parse(Path(scenarios.__file__).read_text(encoding="utf-8"))
    environment_reads = {
        f"{node.value.id}.{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    }
    referenced = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert not environment_reads
    assert "default_environment_reader" not in referenced
    assert "fixtures" in referenced
