"""Provider contract for external static-analysis engines."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from codestrata.static_analysis.models import StaticAnalysisContext, StaticAnalysisResult


@runtime_checkable
class StaticAnalysisProvider(Protocol):
    """Contract implemented by external static-analysis providers."""

    @property
    def provider_id(self) -> str:
        """Stable provider identifier."""

    @property
    def display_name(self) -> str:
        """Human-readable provider name."""

    @property
    def supported_languages(self) -> frozenset[str]:
        """Languages this provider can analyze."""

    def is_available(self) -> bool:
        """Return whether the provider executable is available."""

    def is_applicable(self, context: StaticAnalysisContext) -> bool:
        """Return whether the provider should run for this repository."""

    def analyze(self, context: StaticAnalysisContext) -> StaticAnalysisResult:
        """Execute the provider and return normalized results."""
