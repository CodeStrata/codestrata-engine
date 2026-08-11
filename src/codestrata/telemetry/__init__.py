"""Anonymous, opt-in Community telemetry (disabled by default).

Never collects source code, repository names, findings, prompts, credentials,
or personal identifiers. See ``engine/PRIVACY.md`` and ``docs/telemetry.md``.

Slice 9.1–9.9: Engine-local **telemetry runtime** is authoritative for product
paths (``get_telemetry_service`` → disabled facade). Legacy ``TelemetryService``
is retained for explicit preference commands and tests via
``get_legacy_telemetry_service``. See ``engine/docs/telemetry-runtime.md``,
``engine/docs/telemetry-disabled-default.md``,
``engine/docs/telemetry-non-interactive.md``,
``engine/docs/telemetry-event-catalog.md``, and
``engine/docs/telemetry-preview.md``.
"""

from __future__ import annotations

from codestrata.telemetry.constants import (
    SCHEMA_VERSION,
    EventName,
)
from codestrata.telemetry.service import (
    TelemetryService,
    ensure_interactive_product_telemetry,
    get_legacy_telemetry_service,
    get_telemetry_service,
    reset_telemetry_singletons,
)

__all__ = [
    "SCHEMA_VERSION",
    "EventName",
    "TelemetryService",
    "ensure_interactive_product_telemetry",
    "get_legacy_telemetry_service",
    "get_telemetry_service",
    "reset_telemetry_singletons",
]
