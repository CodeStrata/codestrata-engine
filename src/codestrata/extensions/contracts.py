"""Versioned extension contracts (Protocols) for Community Edition.

These are stable surfaces for optional contributions. They are not a plugin
framework: discovery uses ``importlib.metadata`` entry points and explicit
config allowlists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from codestrata.ai.providers.base import AIModelProvider
from codestrata.config.settings import CodestrataSettings
from codestrata.reporting.html_v2.models import CustomerReportDocument
from codestrata.services.contracts import Analyzer


@runtime_checkable
class AnalyzerExtension(Protocol):
    """Opt-in Phase 1 analyzer contribution.

    Entry point group: ``codestrata.analyzer_extensions``.
    Enabled only when listed under ``[extensions.analyzers].enabled``.
    """

    @property
    def id(self) -> str:
        """Stable reverse-DNS id (must not use reserved ``codestrata.*`` prefixes)."""

    @property
    def api_version(self) -> str:
        """Declared Extension API version (major must match Engine)."""

    def create(self) -> Analyzer:
        """Instantiate the analyzer for the composite pipeline."""


@runtime_checkable
class AssessAIProviderExtension(Protocol):
    """Optional assess / Modernization Advisor provider factory.

    Built-ins (``bedrock``, ``openai``) register in-process. Additional
    providers may use entry point group ``codestrata.assess_ai_provider_extensions``.
    """

    @property
    def id(self) -> str:
        """Provider name selected via ``[ai].provider``."""

    @property
    def api_version(self) -> str:
        """Declared Extension API version (major must match Engine)."""

    def create(self, settings: CodestrataSettings) -> AIModelProvider:
        """Build a provider for the given settings."""


@runtime_checkable
class ReportRenderer(Protocol):
    """Render a ``CustomerReportDocument`` to an output path.

    Built-in ``html`` wraps the Engine HTML renderer. Additional formats may
    register via ``codestrata.report_renderer_extensions`` and opt-in config.
    """

    @property
    def id(self) -> str:
        """Stable renderer id (``html`` is reserved for the built-in)."""

    @property
    def media_type(self) -> str:
        """IANA media type of the primary artifact (e.g. ``text/html``)."""

    @property
    def api_version(self) -> str:
        """Declared Extension API version (major must match Engine)."""

    def render(self, document: CustomerReportDocument, destination: Path) -> Path:
        """Write the rendered artifact and return the path written."""


__all__ = [
    "AnalyzerExtension",
    "AssessAIProviderExtension",
    "ReportRenderer",
]
