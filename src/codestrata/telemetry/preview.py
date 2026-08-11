"""Deterministic privacy-safe telemetry preview (Slices 9.1–9.3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.consent import TelemetrySessionConsent, default_session_consent
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import RuntimeTelemetryEvent
from codestrata.telemetry.projection import PrivacySafeTelemetryEvent, project_runtime_event
from codestrata.telemetry.runtime_policy import (
    PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
    CommunityTelemetryRuntimePolicy,
    default_runtime_policy,
)
from codestrata.telemetry.session import TelemetrySession


@dataclass(frozen=True, slots=True)
class TelemetryPreview:
    """Exact privacy-safe payload that would be handed to a future transport."""

    telemetry_enabled: bool
    decision: str
    decision_source: str
    transmission_authorized: bool
    transport_category: str
    runtime_policy_version: str
    event_schema_version: str
    event: dict[str, Any]
    omitted_optional_fields: tuple[str, ...]
    transmission: str = "none"
    transmission_performed: bool = False

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "decision_source": self.decision_source,
            "event": {key: self.event[key] for key in sorted(self.event)},
            "event_schema_version": self.event_schema_version,
            "omitted_optional_fields": list(self.omitted_optional_fields),
            "runtime_policy_version": self.runtime_policy_version,
            "telemetry_enabled": self.telemetry_enabled,
            "transmission": self.transmission,
            "transmission_authorized": self.transmission_authorized,
            "transmission_performed": self.transmission_performed,
            "transport_category": self.transport_category,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


_OPTIONAL_FIELDS: tuple[str, ...] = (
    "cli_version",
    "os_family",
    "arch_family",
    "lifecycle",
    "result",
    "duration_bucket",
    "operation_category",
    "enabled_assessment_heads",
    "offline_mode",
    "ai_used",
    "failure_category",
)


def preview_runtime_event(
    event: RuntimeTelemetryEvent,
    *,
    session: TelemetrySession | None = None,
    policy: CommunityTelemetryRuntimePolicy | None = None,
    decision: TelemetryDecision | None = None,
    consent: TelemetrySessionConsent | None = None,
) -> TelemetryPreview:
    """Build a deterministic preview — no transmission, no installation ID."""

    active_policy = policy or (session.policy if session is not None else default_runtime_policy())
    active_consent = (
        consent
        if consent is not None
        else (
            session.consent
            if session is not None
            else default_session_consent()
        )
    )
    if decision is not None and decision is not active_consent.decision:
        # Decision override only for narrow tests; consent fields still from consent.
        pass
    active_decision = decision if decision is not None else active_consent.decision
    projected = project_runtime_event(event, policy=active_policy)
    transport_category = (
        session.transport.transport_category if session is not None else "unavailable"
    )
    return preview_privacy_safe_event(
        projected,
        consent=active_consent,
        decision=active_decision,
        policy=active_policy,
        transport_category=transport_category,
    )


def preview_privacy_safe_event(
    event: PrivacySafeTelemetryEvent,
    *,
    consent: TelemetrySessionConsent | None = None,
    decision: TelemetryDecision | None = None,
    policy: CommunityTelemetryRuntimePolicy | None = None,
    transport_category: str = "unavailable",
) -> TelemetryPreview:
    active = policy or default_runtime_policy()
    active_consent = consent or default_session_consent()
    active_decision = decision if decision is not None else active_consent.decision
    stable = event.to_stable_dict()
    omitted = tuple(
        sorted(field for field in _OPTIONAL_FIELDS if field not in stable)
    )
    return TelemetryPreview(
        telemetry_enabled=active_decision is TelemetryDecision.ALLOWED_FOR_SESSION,
        decision=active_decision.value,
        decision_source=active_consent.source.value,
        transmission_authorized=active_consent.transmission_authorized,
        transport_category=transport_category,
        runtime_policy_version=active.policy_version,
        event_schema_version=PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
        event=stable,
        omitted_optional_fields=omitted,
        transmission="none",
        transmission_performed=False,
    )


__all__ = [
    "TelemetryPreview",
    "preview_privacy_safe_event",
    "preview_runtime_event",
]
