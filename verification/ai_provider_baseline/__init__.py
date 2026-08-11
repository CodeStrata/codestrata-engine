"""SV.11.1 — AI Provider Compatibility Baseline (CodeStrata v0.2.0 Epic 11, Slice 11.1).

Characterization-only verification suite. Freezes the *existing* Engine AI
provider architecture (Bedrock + OpenAI assess providers, settings, fail-soft
behavior, doctor diagnostics) as a compatibility baseline for Slice 11.2+. It
does not introduce a common provider interface, provider platform, or
registry redesign, and it does not migrate providers or add OpenRouter.
"""

from __future__ import annotations

from verification.ai_provider_baseline.contract import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
    default_contract,
)
from verification.ai_provider_baseline.models import BaselineReport
from verification.ai_provider_baseline.runner import run_ai_provider_baseline

__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "BaselineReport",
    "default_contract",
    "run_ai_provider_baseline",
]
