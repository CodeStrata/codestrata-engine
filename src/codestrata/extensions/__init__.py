"""Optional Platform extension hooks for Community Engine.

Community Edition never imports Platform packages. Platform packages register
CLI groups and MCP tool registrars through ``importlib.metadata`` entry points:

* ``codestrata.cli_extensions`` — callables ``(root: typer.Typer) -> None``
* ``codestrata.mcp_extensions`` — callables matching
  ``register_platform_mcp(server, **services) -> None``
* ``codestrata.ai_provider_extensions`` — RAG embed/answer registrar
* ``codestrata.assess_ai_provider_extensions`` — assess AI provider factories
* ``codestrata.analyzer_extensions`` — opt-in Phase 1 analyzer contributions
* ``codestrata.report_renderer_extensions`` — CustomerReportDocument renderers
* ``codestrata.acceptance_extensions`` — acceptance helpers

Discovery uses entry-point metadata only; Engine source must not import
``codestrata_platform``.

Extension API version: see ``EXTENSION_API_VERSION``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from importlib.metadata import entry_points
from typing import Any, Protocol, runtime_checkable

from codestrata.extensions.version import EXTENSION_API_VERSION

__all__ = [
    "EXTENSION_API_VERSION",
    "EnterpriseExtension",
    "enterprise_runtime_available",
    "load_acceptance_rag_helpers",
    "load_cli_extensions",
    "load_mcp_extensions",
    "platform_rag_runtime_available",
]


@runtime_checkable
class EnterpriseExtension(Protocol):
    """Minimal surface Platform can provide for enterprise commands/tools."""

    @property
    def name(self) -> str: ...

    def is_available(self) -> bool: ...


def _iter_entry_points(group: str) -> Iterator[Any]:
    selected = entry_points().select(group=group)
    yield from selected


def load_cli_extensions() -> list[Callable[..., None]]:
    """Load Platform CLI registrars (no-op when Platform is not installed)."""

    registrars: list[Callable[..., None]] = []
    for ep in _iter_entry_points("codestrata.cli_extensions"):
        try:
            loaded = ep.load()
        except Exception:  # noqa: BLE001 - optional Platform surface
            continue
        if callable(loaded):
            registrars.append(loaded)
    return registrars


def load_mcp_extensions() -> list[Callable[..., Any]]:
    """Load Platform MCP registrars (no-op when Platform is not installed)."""

    registrars: list[Callable[..., Any]] = []
    for ep in _iter_entry_points("codestrata.mcp_extensions"):
        try:
            loaded = ep.load()
        except Exception:  # noqa: BLE001 - optional Platform surface
            continue
        if callable(loaded):
            registrars.append(loaded)
    return registrars


def enterprise_runtime_available() -> bool:
    """Return True when a Platform CLI extension named ``enterprise`` is installed."""

    for ep in _iter_entry_points("codestrata.cli_extensions"):
        if ep.name == "enterprise":
            return True
    return False


def platform_rag_runtime_available() -> bool:
    """Return True when a Platform CLI extension named ``repository`` is installed."""

    for ep in _iter_entry_points("codestrata.cli_extensions"):
        if ep.name == "repository":
            return True
    return False


def load_acceptance_rag_helpers() -> Any | None:
    """Load Platform acceptance RAG helpers when installed; else None."""

    for ep in _iter_entry_points("codestrata.acceptance_extensions"):
        try:
            loaded = ep.load()
        except Exception:  # noqa: BLE001 - optional Platform surface
            continue
        return loaded
    return None
