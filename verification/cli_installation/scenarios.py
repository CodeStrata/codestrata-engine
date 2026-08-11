"""Failure-scenario evaluators for SV.2 (pure, deterministic)."""

from __future__ import annotations

from verification.cli_installation.contract import (
    MINIMUM_PYTHON,
    python_version_supported,
)
from verification.cli_installation.expected import (
    CommandResultView,
    doctor_missing_config_fails,
    init_existing_config_fails,
)


def evaluate_missing_python_version(
    version_info: tuple[int, int],
) -> tuple[bool, str]:
    """Pass when an unsupported Python is correctly rejected by the contract."""

    supported = python_version_supported(version_info)
    if supported:
        return (
            False,
            f"Python {version_info[0]}.{version_info[1]} meets minimum "
            f"{MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}; not a missing-version case",
        )
    return (
        True,
        f"Python {version_info[0]}.{version_info[1]} correctly below minimum "
        f"{MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}",
    )


def evaluate_missing_dependency(
    *,
    import_exit_code: int,
    cli_exit_code: int | None = None,
) -> tuple[bool, str]:
    """Pass when codestrata cannot be imported / invoked without the package."""

    if import_exit_code == 0:
        return False, "import unexpectedly succeeded without dependency"
    if cli_exit_code is not None and cli_exit_code == 0:
        return False, "CLI unexpectedly succeeded without dependency"
    return True, "missing dependency correctly fails import/CLI"


def evaluate_existing_configuration(result: CommandResultView) -> tuple[bool, str]:
    return init_existing_config_fails(result)


def evaluate_invalid_workspace(
    *,
    workspace_is_file: bool,
    init_exit_code: int,
    combined_output: str,
) -> tuple[bool, str]:
    """Pass when init cannot write config into an invalid workspace target."""

    if not workspace_is_file:
        return False, "fixture was not an invalid workspace (expected file path)"
    if init_exit_code == 0:
        return False, "init unexpectedly succeeded against invalid workspace"
    lowered = combined_output.lower()
    if not any(
        token in lowered
        for token in (
            "failed to write",
            "file exists",
            "not a directory",
            "errno",
            "error",
        )
    ):
        return False, "invalid workspace failure message missing"
    return True, "invalid workspace correctly rejected"


def evaluate_doctor_without_config(result: CommandResultView) -> tuple[bool, str]:
    return doctor_missing_config_fails(result)
