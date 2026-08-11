"""Decision vocabulary tests (Slices 9.1 / 9.3)."""

from __future__ import annotations

from codestrata.telemetry.decisions import (
    SLICE_91_ACTIVE_DECISIONS,
    SLICE_93_ACTIVE_DECISIONS,
    TelemetryDecision,
    is_transmission_allowed,
)


def test_slice_91_active_decision_is_disabled_only() -> None:
    assert SLICE_91_ACTIVE_DECISIONS == {TelemetryDecision.DISABLED_BY_DEFAULT}


def test_slice_93_active_decisions() -> None:
    assert SLICE_93_ACTIVE_DECISIONS == {
        TelemetryDecision.DISABLED_BY_DEFAULT,
        TelemetryDecision.ALLOWED_FOR_SESSION,
        TelemetryDecision.DENIED_FOR_SESSION,
    }


def test_transmission_allowed_only_for_explicit_allow() -> None:
    assert is_transmission_allowed(TelemetryDecision.DISABLED_BY_DEFAULT) is False
    assert is_transmission_allowed(TelemetryDecision.DENIED_FOR_SESSION) is False
    assert is_transmission_allowed(TelemetryDecision.NON_INTERACTIVE_DISABLED) is False
    assert is_transmission_allowed(TelemetryDecision.TRANSPORT_UNAVAILABLE) is False
    assert is_transmission_allowed(TelemetryDecision.ALLOWED_FOR_SESSION) is True
