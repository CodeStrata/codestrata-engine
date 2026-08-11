"""SV.2 contract unit tests."""

from __future__ import annotations

from verification.cli_installation.contract import (
    CLI_INSTALLATION_VERIFICATION_URN,
    MINIMUM_PYTHON,
    default_contract,
    os_family_supported,
    python_version_supported,
)


def test_contract_identity_and_matrix() -> None:
    contract = default_contract()
    assert contract.verification_id == "cli-installation-verification"
    assert contract.verification_version == "1.0.0"
    assert CLI_INSTALLATION_VERIFICATION_URN.endswith("1.0.0")
    assert contract.minimum_python == MINIMUM_PYTHON == (3, 12)
    assert "darwin" in contract.supported_os_families
    assert "linux" in contract.supported_os_families
    assert "win32" in contract.supported_os_families
    assert "pip_wheel" in contract.installation_methods
    assert "pip_sdist" in contract.installation_methods
    assert "pip_path_non_editable" in contract.installation_methods


def test_required_commands_cover_user_flow() -> None:
    names = {item.name for item in default_contract().required_commands}
    assert names == {
        "codestrata_version_flag",
        "codestrata_help",
        "codestrata_init",
        "codestrata_doctor",
    }


def test_python_and_os_gates() -> None:
    assert python_version_supported((3, 12)) is True
    assert python_version_supported((3, 13)) is True
    assert python_version_supported((3, 11)) is False
    assert os_family_supported("darwin") is True
    assert os_family_supported("linux") is True
    assert os_family_supported("win32") is True
    assert os_family_supported("win64") is True  # normalized via startswith win
    assert os_family_supported("plan9") is False


def test_pass_criteria_document_clean_env() -> None:
    criteria = default_contract().pass_criteria
    assert "Fresh venv" in criteria["environment"]
    assert "editable" in criteria["environment"].lower()
    assert "PYTHONPATH" in criteria["environment"]
