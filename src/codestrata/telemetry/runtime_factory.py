"""Authoritative telemetry runtime construction (Slices 9.2–9.3).

Default factory builds disabled-by-default. Session factory accepts explicit
immutable consent. No preference reads, environment enablement, installation
identity, filesystem access, network, or prompts.
"""

from __future__ import annotations

from codestrata.telemetry.consent import TelemetrySessionConsent, default_session_consent
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.runtime import TelemetryRuntime
from codestrata.telemetry.runtime_policy import (
    CommunityTelemetryRuntimePolicy,
    default_runtime_policy,
)
from codestrata.telemetry.session import new_disabled_session, new_session_from_consent
from codestrata.telemetry.transport import TelemetryTransport


def create_default_telemetry_runtime(
    *,
    policy: CommunityTelemetryRuntimePolicy | None = None,
    transport: TelemetryTransport | None = None,
    interactive: bool = False,
) -> TelemetryRuntime:
    """Construct the product-default telemetry runtime (disabled, unavailable)."""

    active_policy = policy or default_runtime_policy()
    active_transport = transport or UnavailableTelemetryTransport()
    session = new_disabled_session(
        policy=active_policy,
        transport=active_transport,
        interactive=interactive,
    )
    return TelemetryRuntime(session)


def create_session_telemetry_runtime(
    *,
    consent: TelemetrySessionConsent | None = None,
    policy: CommunityTelemetryRuntimePolicy | None = None,
    transport: TelemetryTransport | None = None,
    interactive: bool = False,
) -> TelemetryRuntime:
    """Construct a runtime for an explicit process-local consent decision.

    ``consent`` defaults to disabled_by_default. Non-default decisions must be
    supplied as a validated ``TelemetrySessionConsent``. Capture transports are
    allowed only via explicit ``transport`` injection (tests).
    """

    active_consent = consent if consent is not None else default_session_consent()
    active_consent.validate()
    active_policy = policy or default_runtime_policy()
    active_transport = transport or UnavailableTelemetryTransport()
    session = new_session_from_consent(
        active_consent,
        policy=active_policy,
        transport=active_transport,
        interactive=interactive,
    )
    return TelemetryRuntime(session)


__all__ = [
    "create_default_telemetry_runtime",
    "create_session_telemetry_runtime",
]
