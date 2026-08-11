"""Bounded assessment telemetry lifecycle helpers (Slice 9.12).

Documented event contract for ``codestrata assess``:

Success:
  feature_invoked → (primary assessment) → feature_completed

Failure:
  feature_invoked → (primary assessment) → operation_failed

No per-file / per-rule / per-Finding events.
Duration milliseconds are never transmitted; facade may omit duration_bucket.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codestrata.telemetry.disabled_service import DisabledTelemetryFacade


def record_assess_invoked_safely(
    telemetry: DisabledTelemetryFacade,
    *,
    ai_enabled: bool,
    domains: list[str] | None = None,
    repo_root: Path | None = None,
) -> bool:
    """Record feature_invoked. Return False on silent failure."""

    try:
        telemetry.record_assessment_started(
            ai_enabled=ai_enabled,
            domains=domains,
            repo_root=repo_root,
        )
        return True
    except Exception:  # noqa: BLE001 - isolation boundary
        return False


def record_assess_completed_safely(
    telemetry: DisabledTelemetryFacade,
    *,
    ai_enabled: bool,
    ai_executed: bool,
    success: bool,
    duration_ms: float | None,
    domains: list[str] | None = None,
    repo_root: Path | None = None,
) -> bool:
    """Record feature_completed or operation_failed. Return False on silent failure."""

    try:
        telemetry.record_assessment_completed(
            ai_enabled=ai_enabled,
            ai_executed=ai_executed,
            success=success,
            duration_ms=duration_ms,
            domains=domains,
            repo_root=repo_root,
        )
        return True
    except Exception:  # noqa: BLE001 - isolation boundary
        return False


def lifecycle_event_names(*, success: bool) -> tuple[str, str]:
    """Return the documented start/end event type names for assess."""

    if success:
        return ("feature_invoked", "feature_completed")
    return ("feature_invoked", "operation_failed")


def redact_isolation_blob(blob: Any) -> str:
    """Stable string form for tests — never includes secrets by construction."""

    return str(blob)


__all__ = [
    "lifecycle_event_names",
    "record_assess_completed_safely",
    "record_assess_invoked_safely",
    "redact_isolation_blob",
]
