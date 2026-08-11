"""Assessment isolation — telemetry must not alter primary results (Slice 9.1)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.runtime import (
    TelemetryRuntime,
    record_telemetry_safely,
    run_with_isolated_telemetry,
)


def test_primary_success_survives_telemetry_projection_failure() -> None:
    runtime = TelemetryRuntime()

    class _BadEvent:
        def to_intake_dict(self):
            raise RuntimeError("projection boom")

    def primary() -> str:
        record_telemetry_safely(runtime, _BadEvent())  # type: ignore[arg-type]
        return "ok"

    assert run_with_isolated_telemetry(primary, runtime=runtime) == "ok"
    assert runtime.session.counters.failures >= 1


def test_primary_failure_remains_authoritative_when_telemetry_also_fails() -> None:
    runtime = TelemetryRuntime()

    class _BadEvent:
        def to_intake_dict(self):
            raise RuntimeError("telemetry boom")

    def primary() -> None:
        raise ValueError("product_failure")

    with pytest.raises(ValueError, match="product_failure"):
        run_with_isolated_telemetry(
            primary,
            runtime=runtime,
            on_failure_event=_BadEvent(),  # type: ignore[arg-type]
        )


def test_primary_success_with_normal_telemetry_drop() -> None:
    runtime = TelemetryRuntime()

    def primary() -> int:
        return 42

    assert (
        run_with_isolated_telemetry(
            primary,
            runtime=runtime,
            on_success_event=RuntimeTelemetryEvent(
                event_type=RuntimeEventType.APPLICATION_COMPLETED
            ),
        )
        == 42
    )
    assert runtime.session.counters.events_dropped >= 1
