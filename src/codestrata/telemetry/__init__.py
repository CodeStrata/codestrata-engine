"""Anonymous, opt-in Community telemetry (disabled by default).

Never collects source code, repository names, findings, prompts, credentials,
or personal identifiers. See ``engine/PRIVACY.md`` and ``docs/telemetry.md``.
"""

from __future__ import annotations

from codestrata.telemetry.constants import (
    SCHEMA_VERSION,
    EventName,
)
from codestrata.telemetry.service import TelemetryService, get_telemetry_service

__all__ = [
    "SCHEMA_VERSION",
    "EventName",
    "TelemetryService",
    "get_telemetry_service",
]
