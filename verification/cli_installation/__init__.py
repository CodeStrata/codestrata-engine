"""SV.2 — Clean CLI Installation Verification."""

from __future__ import annotations

from verification.cli_installation.contract import (
    CLI_INSTALLATION_VERIFICATION_ID,
    CLI_INSTALLATION_VERIFICATION_VERSION,
    InstallationContract,
    default_contract,
)
from verification.cli_installation.models import (
    VerificationCheck,
    VerificationReport,
)
from verification.cli_installation.runner import run_cli_installation_verification

__all__ = [
    "CLI_INSTALLATION_VERIFICATION_ID",
    "CLI_INSTALLATION_VERIFICATION_VERSION",
    "InstallationContract",
    "VerificationCheck",
    "VerificationReport",
    "default_contract",
    "run_cli_installation_verification",
]
