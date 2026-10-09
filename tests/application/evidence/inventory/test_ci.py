"""M03 CI observations: literal, conditional, delegated, absent, malformed."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.inventory.models import SupportKind
from codestrata.application.evidence.inventory.service import ExtractorInventoryService

FIXTURES = Path(__file__).parent / "fixtures"


def _inspect(name: str):
    return ExtractorInventoryService().inspect_tree(FIXTURES / name)


def test_direct_command_is_literal_test_invocation() -> None:
    snapshot = _inspect("ci_direct_command")
    assert len(snapshot.ci) == 1
    document = snapshot.ci[0]
    assert document.support is SupportKind.STRUCTURAL
    assert document.parse_status == "ok"
    assert document.test_count >= 1
    commands = [item.literal_command for item in document.invocations]
    assert "pytest" in commands
    pytest_row = next(item for item in document.invocations if item.literal_command == "pytest")
    assert pytest_row.unresolved is False
    assert pytest_row.parser_rule == "gha.step.run.literal"
    assert pytest_row.line is not None


def test_conditional_job_keeps_expression_unresolved() -> None:
    snapshot = _inspect("ci_conditional_job")
    document = snapshot.ci[0]
    assert any(item.condition and "${{" in item.condition for item in document.invocations)
    flagged = [item for item in document.invocations if item.unresolved]
    assert flagged
    assert all(item.unresolved_reason != "absent_check" for item in document.invocations)


def test_delegated_script_is_unresolved_not_absent() -> None:
    snapshot = _inspect("ci_delegated_script")
    document = snapshot.ci[0]
    delegated = next(
        item for item in document.invocations if item.literal_command == "npm run build"
    )
    assert delegated.unresolved is True
    assert delegated.parser_rule == "gha.step.run.delegated_script"
    assert delegated.unresolved_reason == "delegated_script_body_not_inspected"


def test_no_ci_is_empty_observation_not_a_failed_check() -> None:
    snapshot = _inspect("ci_none")
    assert snapshot.ci == ()
    assert snapshot.files


def test_malformed_yaml_is_unresolved_not_zero_jobs() -> None:
    snapshot = _inspect("ci_malformed_yaml")
    assert len(snapshot.ci) == 1
    document = snapshot.ci[0]
    assert document.parse_status == "malformed"
    assert document.invocations
    row = document.invocations[0]
    assert row.unresolved is True
    assert row.parser_rule == "gha.document.malformed"
