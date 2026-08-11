"""SV.2 scenario and expected-output tests."""

from __future__ import annotations

from verification.cli_installation.expected import (
    CommandResultView,
    doctor_missing_config_fails,
    doctor_ok,
    help_ok,
    help_subcommand_absent,
    init_existing_config_fails,
    init_ok,
    version_flag_ok,
)
from verification.cli_installation.scenarios import (
    evaluate_invalid_workspace,
    evaluate_missing_dependency,
    evaluate_missing_python_version,
)


def test_expected_markers() -> None:
    assert version_flag_ok(CommandResultView(0, "CodeStrata 0.1.0\n", ""))[0]
    assert not version_flag_ok(CommandResultView(1, "CodeStrata 0.1.0\n", ""))[0]
    help_text = "Primary workflow: assess\n  init\n  doctor\n  assess\n"
    assert help_ok(CommandResultView(0, help_text, ""))[0]
    assert help_subcommand_absent(
        CommandResultView(2, "", "No such command 'help'. Try --help")
    )[0]
    assert init_ok(
        CommandResultView(0, "Wrote codestrata.toml\nSuccess: Configuration ready.\n", "")
    )[0]
    assert doctor_ok(
        CommandResultView(0, "[OK] python: ...\nAll doctor checks passed.\n", "")
    )[0]


def test_failure_scenario_evaluators() -> None:
    ok, detail = evaluate_missing_python_version((3, 11))
    assert ok is True
    assert "3.11" in detail

    assert evaluate_missing_python_version((3, 12))[0] is False
    assert evaluate_missing_dependency(import_exit_code=1)[0] is True
    assert evaluate_missing_dependency(import_exit_code=0)[0] is False

    assert doctor_missing_config_fails(
        CommandResultView(1, "[FAIL] config: missing\nRun: codestrata init\n", "")
    )[0]
    assert init_existing_config_fails(
        CommandResultView(1, "", "Configuration already exists: codestrata.toml")
    )[0]
    assert evaluate_invalid_workspace(
        workspace_is_file=True,
        init_exit_code=1,
        combined_output="[Errno 17] File exists: '/tmp/not-a-directory'",
    )[0]
