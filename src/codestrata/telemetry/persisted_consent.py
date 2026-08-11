"""Persisted Community telemetry preference (Slice 19.4).

Explicit local Yes/No survives CLI restarts. Default remains undecided/disabled.
Does not collect source code or repository identity.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from codestrata.telemetry.consent import TelemetrySessionConsent
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.preferences import load_preferences, mark_decision


class TelemetryPreferenceState(StrEnum):
    UNDECIDED = "undecided"
    ENABLED = "enabled"
    DISABLED = "disabled"


def preference_state(*, path: Path | None = None) -> TelemetryPreferenceState:
    prefs = load_preferences(path=path)
    if not bool(prefs.get("decision_made")):
        return TelemetryPreferenceState.UNDECIDED
    if bool(prefs.get("enabled")):
        return TelemetryPreferenceState.ENABLED
    return TelemetryPreferenceState.DISABLED


def persist_preference(enabled: bool, *, path: Path | None = None) -> TelemetryPreferenceState:
    mark_decision(bool(enabled), path=path)
    return (
        TelemetryPreferenceState.ENABLED
        if enabled
        else TelemetryPreferenceState.DISABLED
    )


def consent_from_persisted_preference(
    *,
    path: Path | None = None,
) -> TelemetrySessionConsent | None:
    """Return session consent when an explicit local preference exists."""

    state = preference_state(path=path)
    if state is TelemetryPreferenceState.UNDECIDED:
        return None
    if state is TelemetryPreferenceState.ENABLED:
        return TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.PERSISTED_PREFERENCE,
            explicit=True,
            persisted=True,
            prior_consent_reused=True,
            installation_identity_required=False,
            transmission_authorized=True,
        )
    return TelemetrySessionConsent(
        decision=TelemetryDecision.DENIED_FOR_SESSION,
        source=TelemetryDecisionSource.PERSISTED_PREFERENCE,
        explicit=True,
        persisted=True,
        prior_consent_reused=True,
        installation_identity_required=False,
        transmission_authorized=False,
    )


__all__ = [
    "TelemetryPreferenceState",
    "consent_from_persisted_preference",
    "persist_preference",
    "preference_state",
]
