"""Configurable size limits for the LLM evidence contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMContractLimits:
    """Deterministic truncation limits for LLM analysis context."""

    max_findings: int = 100
    max_evidence_per_finding: int = 10
    max_excerpt_characters: int = 500
    max_metadata_value_characters: int = 200

    def __post_init__(self) -> None:
        if self.max_findings < 0:
            raise ValueError("max_findings must be >= 0")
        if self.max_evidence_per_finding < 0:
            raise ValueError("max_evidence_per_finding must be >= 0")
        if self.max_excerpt_characters < 0:
            raise ValueError("max_excerpt_characters must be >= 0")
        if self.max_metadata_value_characters < 0:
            raise ValueError("max_metadata_value_characters must be >= 0")
