"""Optional fixtures for SV.11.13 (no synthetic credentials required)."""

from __future__ import annotations

# Completion verification is inventory/report based; no live or synthetic
# provider payloads are needed. Markers kept for privacy scan tests.
SYNTHETIC_OPENAI_KEY = "sk-synth-completion-1113-not-real"
SYNTHETIC_PROMPT = "SYNTHETIC_COMPLETION_PROMPT_1113"

__all__ = ["SYNTHETIC_OPENAI_KEY", "SYNTHETIC_PROMPT"]
