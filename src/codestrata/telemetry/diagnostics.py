"""Bounded telemetry runtime diagnostics (Slices 9.1–9.10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.pre_transport_policy import (
    COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION,
)
from codestrata.telemetry.runtime_policy import PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION
from codestrata.telemetry.session import TelemetrySession


@dataclass(frozen=True, slots=True)
class TelemetryRuntimeDiagnostics:
    """Safe counters and consent state — no payloads, paths, or credentials."""

    runtime_policy_version: str
    event_schema_version: str
    consent_policy_version: str
    privacy_policy_version: str
    decision: str
    decision_source: str
    consent_scope: str
    explicit_decision: bool
    persisted: bool
    prior_consent_reused: bool
    transmission_authorized: bool
    transport_category: str
    telemetry_enabled: bool
    events_seen: int
    events_projected: int
    events_dropped: int
    transmission_attempts: int
    transport_sent: int
    transport_unavailable: int
    transport_rejected: int
    failure_count: int
    privacy_gate_attempts: int
    privacy_gate_accepted: int
    privacy_gate_rejected: int
    privacy_gate_failures: int
    last_privacy_result_category: str | None
    validation_status: str
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "consent_policy_version": self.consent_policy_version,
            "consent_scope": self.consent_scope,
            "decision": self.decision,
            "decision_source": self.decision_source,
            "event_schema_version": self.event_schema_version,
            "events_dropped": self.events_dropped,
            "events_projected": self.events_projected,
            "events_seen": self.events_seen,
            "explicit_decision": self.explicit_decision,
            "failure_count": self.failure_count,
            "last_privacy_result_category": self.last_privacy_result_category,
            "limitation_codes": list(self.limitation_codes),
            "persisted": self.persisted,
            "prior_consent_reused": self.prior_consent_reused,
            "privacy_gate_accepted": self.privacy_gate_accepted,
            "privacy_gate_attempts": self.privacy_gate_attempts,
            "privacy_gate_failures": self.privacy_gate_failures,
            "privacy_gate_rejected": self.privacy_gate_rejected,
            "privacy_policy_version": self.privacy_policy_version,
            "runtime_policy_version": self.runtime_policy_version,
            "telemetry_enabled": self.telemetry_enabled,
            "transmission_attempts": self.transmission_attempts,
            "transmission_authorized": self.transmission_authorized,
            "transport_category": self.transport_category,
            "transport_rejected": self.transport_rejected,
            "transport_sent": self.transport_sent,
            "transport_unavailable": self.transport_unavailable,
            "validation_status": self.validation_status,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def diagnostics_from_session(
    session: TelemetrySession,
    *,
    validation_status: str = "ok",
) -> TelemetryRuntimeDiagnostics:
    consent = session.consent
    return TelemetryRuntimeDiagnostics(
        runtime_policy_version=session.policy.policy_version,
        event_schema_version=PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
        consent_policy_version=consent.policy_version,
        privacy_policy_version=COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION,
        decision=session.decision.value,
        decision_source=session.decision_source.value,
        consent_scope=consent.scope,
        explicit_decision=consent.explicit,
        persisted=consent.persisted,
        prior_consent_reused=consent.prior_consent_reused,
        transmission_authorized=consent.transmission_authorized,
        transport_category=session.transport.transport_category,
        telemetry_enabled=session.telemetry_enabled,
        events_seen=session.counters.events_seen,
        events_projected=session.counters.events_projected,
        events_dropped=session.counters.events_dropped,
        transmission_attempts=session.counters.transmission_attempts,
        transport_sent=session.counters.transport_sent,
        transport_unavailable=session.counters.transport_unavailable,
        transport_rejected=session.counters.transport_rejected,
        failure_count=session.counters.failures,
        privacy_gate_attempts=session.counters.privacy_gate_attempts,
        privacy_gate_accepted=session.counters.privacy_gate_accepted,
        privacy_gate_rejected=session.counters.privacy_gate_rejected,
        privacy_gate_failures=session.counters.privacy_gate_failures,
        last_privacy_result_category=session.counters.last_privacy_result_category,
        validation_status=validation_status,
        limitation_codes=session.limitation_codes,
    )


__all__ = [
    "TelemetryRuntimeDiagnostics",
    "diagnostics_from_session",
]
