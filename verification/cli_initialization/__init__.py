"""SV.3 — CLI Initialization Workflow Verification."""

from __future__ import annotations

from verification.cli_initialization.contract import (
    CLI_INITIALIZATION_VERIFICATION_ID,
    CLI_INITIALIZATION_VERIFICATION_VERSION,
    InitializationContract,
    default_contract,
)
from verification.cli_initialization.models import VerificationReport
from verification.cli_initialization.runner import run_cli_initialization_verification

__all__ = [
    "CLI_INITIALIZATION_VERIFICATION_ID",
    "CLI_INITIALIZATION_VERIFICATION_VERSION",
    "InitializationContract",
    "VerificationReport",
    "default_contract",
    "run_cli_initialization_verification",
]
