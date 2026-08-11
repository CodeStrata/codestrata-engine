"""Session-scoped telemetry runtime state (Slices 9.1–9.3).

One telemetry session means one CLI process invocation and one explicitly
constructed TelemetryRuntime. Consent is process-local and never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from codestrata.telemetry.consent import (
    TelemetrySessionConsent,
    default_session_consent,
)
from codestrata.telemetry.decisions import (
    TelemetryDecision,
    TelemetryDecisionSource,
    is_transmission_allowed,
)
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.runtime_policy import (
    CommunityTelemetryRuntimePolicy,
    default_runtime_policy,
)
from codestrata.telemetry.transport import TelemetryTransport


@dataclass(frozen=True, slots=True)
class TelemetrySessionCounters:
    events_seen: int = 0
    events_projected: int = 0
    events_dropped: int = 0
    transmission_attempts: int = 0
    failures: int = 0
    transport_unavailable: int = 0
    transport_sent: int = 0
    transport_rejected: int = 0
    privacy_gate_attempts: int = 0
    privacy_gate_accepted: int = 0
    privacy_gate_rejected: int = 0
    privacy_gate_failures: int = 0
    last_privacy_result_category: str | None = None

    def to_stable_dict(self) -> dict[str, int | str | None]:
        return {
            "events_dropped": self.events_dropped,
            "events_projected": self.events_projected,
            "events_seen": self.events_seen,
            "failures": self.failures,
            "last_privacy_result_category": self.last_privacy_result_category,
            "privacy_gate_accepted": self.privacy_gate_accepted,
            "privacy_gate_attempts": self.privacy_gate_attempts,
            "privacy_gate_failures": self.privacy_gate_failures,
            "privacy_gate_rejected": self.privacy_gate_rejected,
            "transmission_attempts": self.transmission_attempts,
            "transport_rejected": self.transport_rejected,
            "transport_sent": self.transport_sent,
            "transport_unavailable": self.transport_unavailable,
        }


@dataclass(frozen=True, slots=True)
class TelemetrySession:
    """Process-scoped session — consent fixed at construction; no installation ID."""

    consent: TelemetrySessionConsent = field(default_factory=default_session_consent)
    interactive: bool = False
    transport: TelemetryTransport = field(default_factory=UnavailableTelemetryTransport)
    policy: CommunityTelemetryRuntimePolicy = field(default_factory=default_runtime_policy)
    counters: TelemetrySessionCounters = field(default_factory=TelemetrySessionCounters)
    limitation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Consent validates itself; re-validate for construction-time fail-fast.
        self.consent.validate()
        codes = tuple(
            sorted(
                set(self.limitation_codes)
                | set(self.policy.limitations)
                | set(self.consent.limitations)
            )
        )
        object.__setattr__(self, "limitation_codes", codes)

    @property
    def decision(self) -> TelemetryDecision:
        return self.consent.decision

    @property
    def decision_source(self) -> TelemetryDecisionSource:
        return self.consent.source

    @property
    def telemetry_enabled(self) -> bool:
        return is_transmission_allowed(self.decision)

    @property
    def transmission_authorized(self) -> bool:
        return self.consent.transmission_authorized

    @property
    def transport_available(self) -> bool:
        return self.transport.transport_category not in {"unavailable", "disabled"}

    def with_counters(self, counters: TelemetrySessionCounters) -> TelemetrySession:
        return replace(self, counters=counters)

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "consent": self.consent.to_stable_dict(),
            "decision": self.decision.value,
            "decision_source": self.decision_source.value,
            "interactive": self.interactive,
            "limitation_codes": list(self.limitation_codes),
            "policy_version": self.policy.policy_version,
            "telemetry_enabled": self.telemetry_enabled,
            "transmission_authorized": self.transmission_authorized,
            "transport_available": self.transport_available,
            "transport_category": self.transport.transport_category,
            **{f"counters.{key}": value for key, value in self.counters.to_stable_dict().items()},
        }


def new_disabled_session(
    *,
    policy: CommunityTelemetryRuntimePolicy | None = None,
    transport: TelemetryTransport | None = None,
    interactive: bool = False,
) -> TelemetrySession:
    """Construct a session that is disabled by default and never reads consent."""

    return TelemetrySession(
        consent=default_session_consent(),
        interactive=interactive,
        transport=transport or UnavailableTelemetryTransport(),
        policy=policy or default_runtime_policy(),
    )


def new_session_from_consent(
    consent: TelemetrySessionConsent,
    *,
    policy: CommunityTelemetryRuntimePolicy | None = None,
    transport: TelemetryTransport | None = None,
    interactive: bool = False,
) -> TelemetrySession:
    """Construct a session from an explicit immutable consent object."""

    return TelemetrySession(
        consent=consent,
        interactive=interactive,
        transport=transport or UnavailableTelemetryTransport(),
        policy=policy or default_runtime_policy(),
    )


__all__ = [
    "TelemetrySession",
    "TelemetrySessionCounters",
    "new_disabled_session",
    "new_session_from_consent",
]
