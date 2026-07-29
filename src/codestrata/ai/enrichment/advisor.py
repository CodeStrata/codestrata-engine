"""Modernization Advisor constants (customer-facing AI enrichment capability)."""

from __future__ import annotations

# Customer-facing capability name (reports, docs, CLI messaging).
MODERNIZATION_ADVISOR_NAME = "Modernization Advisor"

# Semver for the advisor product surface (independent of Engine package version).
MODERNIZATION_ADVISOR_VERSION = "1.0.0"

# Prompt template version for the advisor system/developer instructions.
MODERNIZATION_ADVISOR_PROMPT_VERSION = "1.1.0"

MODERNIZATION_ADVISOR_PERSONA = (
    "You are a senior engineering modernization advisor helping CTOs and "
    "VP Engineering understand deterministic engineering assessments."
)

__all__ = [
    "MODERNIZATION_ADVISOR_NAME",
    "MODERNIZATION_ADVISOR_PERSONA",
    "MODERNIZATION_ADVISOR_PROMPT_VERSION",
    "MODERNIZATION_ADVISOR_VERSION",
]
