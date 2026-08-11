"""Runtime event model tests (Slice 9.1)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.errors import TelemetryRuntimeError
from codestrata.telemetry.events import (
    DurationBucket,
    OsFamily,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)


def test_runtime_event_sorts_heads_deterministically() -> None:
    event = RuntimeTelemetryEvent(
        event_type=RuntimeEventType.FEATURE_INVOKED,
        enabled_assessment_heads=("security", "cloud", "testing"),
        os_family=OsFamily.LINUX,
        duration_bucket=DurationBucket.S_1_10,
    )
    assert event.enabled_assessment_heads == ("cloud", "security", "testing")
    assert list(event.to_intake_dict().keys()) == sorted(event.to_intake_dict().keys())


def test_runtime_event_rejects_non_cli_client() -> None:
    with pytest.raises(TelemetryRuntimeError):
        RuntimeTelemetryEvent(
            event_type=RuntimeEventType.APPLICATION_STARTED,
            client_name="other_client",
        )


def test_runtime_event_rejects_path_like_head() -> None:
    with pytest.raises(TelemetryRuntimeError):
        RuntimeTelemetryEvent(
            event_type=RuntimeEventType.FEATURE_INVOKED,
            enabled_assessment_heads=("/tmp/repo",),
        )
