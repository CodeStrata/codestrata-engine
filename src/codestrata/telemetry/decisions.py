"""Bounded telemetry runtime decision vocabulary (Slices 9.1–9.6)."""

from __future__ import annotations

from enum import StrEnum


class TelemetryDecision(StrEnum):
    """Session consent decision (user consent — not transport outcome)."""

    DISABLED_BY_DEFAULT = "disabled_by_default"
    ALLOWED_FOR_SESSION = "allowed_for_session"
    DENIED_FOR_SESSION = "denied_for_session"
    NON_INTERACTIVE_DISABLED = "non_interactive_disabled"
    # Legacy compatibility value — not a consent decision; do not use for consent.
    TRANSPORT_UNAVAILABLE = "transport_unavailable"


class TelemetryDecisionSource(StrEnum):
    """How the current session decision was established."""

    DEFAULT = "default"
    EXPLICIT_SESSION_ALLOW = "explicit_session_allow"
    EXPLICIT_SESSION_DENY = "explicit_session_deny"
    INTERACTIVE_PROMPT = "interactive_prompt"
    CLI_FLAG = "cli_flag"
    NON_INTERACTIVE_POLICY = "non_interactive_policy"
    PERSISTED_PREFERENCE = "persisted_preference"


# Decisions actively constructible in Slice 9.3–9.5.
SLICE_93_ACTIVE_DECISIONS: frozenset[TelemetryDecision] = frozenset(
    {
        TelemetryDecision.DISABLED_BY_DEFAULT,
        TelemetryDecision.ALLOWED_FOR_SESSION,
        TelemetryDecision.DENIED_FOR_SESSION,
    }
)

SLICE_95_ACTIVE_DECISIONS: frozenset[TelemetryDecision] = frozenset(
    {
        TelemetryDecision.DISABLED_BY_DEFAULT,
        TelemetryDecision.ALLOWED_FOR_SESSION,
        TelemetryDecision.DENIED_FOR_SESSION,
        TelemetryDecision.NON_INTERACTIVE_DISABLED,
    }
)

SLICE_96_ACTIVE_DECISIONS: frozenset[TelemetryDecision] = frozenset(
    {
        TelemetryDecision.DISABLED_BY_DEFAULT,
        TelemetryDecision.ALLOWED_FOR_SESSION,
        TelemetryDecision.DENIED_FOR_SESSION,
        TelemetryDecision.NON_INTERACTIVE_DISABLED,
    }
)

# Backward-compatible alias.
SLICE_91_ACTIVE_DECISIONS: frozenset[TelemetryDecision] = frozenset(
    {TelemetryDecision.DISABLED_BY_DEFAULT}
)


def is_transmission_allowed(decision: TelemetryDecision) -> bool:
    """Return True only for an explicit session allow (consent ≠ transport)."""

    return decision is TelemetryDecision.ALLOWED_FOR_SESSION


__all__ = [
    "SLICE_91_ACTIVE_DECISIONS",
    "SLICE_93_ACTIVE_DECISIONS",
    "SLICE_95_ACTIVE_DECISIONS",
    "SLICE_96_ACTIVE_DECISIONS",
    "TelemetryDecision",
    "TelemetryDecisionSource",
    "is_transmission_allowed",
]
