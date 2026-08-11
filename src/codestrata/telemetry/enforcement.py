"""Centralized disabled-by-default telemetry enforcement (Slice 9.2)."""

from __future__ import annotations

from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.runtime import TelemetryRuntime
from codestrata.telemetry.runtime_factory import create_default_telemetry_runtime


def create_enforced_product_telemetry(
    *,
    runtime: TelemetryRuntime | None = None,
) -> DisabledTelemetryFacade:
    """Single product entry for assessment/report/UX telemetry hooks."""

    active = runtime or create_default_telemetry_runtime()
    return DisabledTelemetryFacade(runtime=active)


def assert_runtime_disabled_by_default(runtime: TelemetryRuntime) -> None:
    """Raise AssertionError if a runtime is not disabled-by-default."""

    session = runtime.session
    if session.decision is not TelemetryDecision.DISABLED_BY_DEFAULT:
        raise AssertionError("telemetry runtime decision must be disabled_by_default")
    if session.telemetry_enabled:
        raise AssertionError("telemetry must not be enabled by default")
    if session.transport.transport_category != "unavailable":
        raise AssertionError("default transport must be unavailable")


__all__ = [
    "assert_runtime_disabled_by_default",
    "create_enforced_product_telemetry",
]
