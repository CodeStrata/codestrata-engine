"""Legacy / product telemetry compatibility helpers (Slice 9.2)."""

from __future__ import annotations

from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.enforcement import create_enforced_product_telemetry
from codestrata.telemetry.runtime import TelemetryRuntime


def product_telemetry_facade(
    *,
    runtime: TelemetryRuntime | None = None,
) -> DisabledTelemetryFacade:
    """Return the disabled product facade used by normal CLI execution."""

    return create_enforced_product_telemetry(runtime=runtime)


__all__ = ["product_telemetry_facade"]
