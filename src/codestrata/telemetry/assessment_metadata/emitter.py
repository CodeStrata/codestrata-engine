"""Fail-silent assessment_metadata 1.1 emitter (Slice 20.8).

Emission requires explicit ``emission_enabled`` authorization. Lifecycle
telemetry consent alone never enables this path (Slice 20.9 owns consent-v2).
"""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.assessment_metadata.diagnostics import (
    AssessmentMetadataEmissionDiagnostics,
)
from codestrata.telemetry.assessment_metadata.models import (
    AssessmentMetadataProjectionSource,
    AssessmentMetadataWireRequest,
)
from codestrata.telemetry.assessment_metadata.policy import (
    CommunityAssessmentMetadataEmissionPolicy,
    default_assessment_metadata_emission_policy,
)
from codestrata.telemetry.assessment_metadata.projector import project_assessment_metadata
from codestrata.telemetry.assessment_metadata.source import (
    build_failure_projection_source,
    build_success_projection_source,
    new_assessment_id,
)
from codestrata.telemetry.assessment_metadata.transport import (
    AssessmentMetadataTransport,
    AssessmentMetadataTransportResult,
    HttpAssessmentMetadataTransport,
)
from codestrata.telemetry.consent import TelemetrySessionConsent
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.identity import ensure_installation_id


def emission_authorized(
    policy: CommunityAssessmentMetadataEmissionPolicy,
    *,
    consent: TelemetrySessionConsent | None,
    network_available: bool,
) -> tuple[bool, str | None]:
    """Return (allowed, skip_reason)."""

    if not policy.emission_enabled:
        return False, "emission_disabled"
    # Explicit offline assess: do not attempt network (payload offline_mode is separate).
    if policy.skip_when_offline and not network_available:
        return False, "offline_mode"
    if policy.require_transmission_authorized:
        if consent is None or not consent.transmission_authorized:
            return False, "transmission_not_authorized"
    return True, None


def resolve_installation_id_safely() -> str | None:
    try:
        installation_id, _created = ensure_installation_id()
        return installation_id or None
    except Exception:  # noqa: BLE001
        return None


def emit_assessment_metadata_safely(
    *,
    source: AssessmentMetadataProjectionSource | None = None,
    result: object | None = None,
    failure: BaseException | None = None,
    assessment_id: str | None = None,
    telemetry: DisabledTelemetryFacade | None = None,
    policy: CommunityAssessmentMetadataEmissionPolicy | None = None,
    transport: AssessmentMetadataTransport | None = None,
    offline_mode: bool = True,
    network_available: bool = True,
    ai_used: bool = False,
    diagnostics: AssessmentMetadataEmissionDiagnostics | None = None,
) -> AssessmentMetadataEmissionDiagnostics:
    """Project + POST amd 1.1 when explicitly authorized. Never raises."""

    diag = diagnostics or AssessmentMetadataEmissionDiagnostics()
    active_policy = policy or default_assessment_metadata_emission_policy()
    consent = None
    if telemetry is not None:
        try:
            consent = telemetry.runtime.session.consent
        except Exception:  # noqa: BLE001
            consent = None

    try:
        allowed, reason = emission_authorized(
            active_policy,
            consent=consent,
            network_available=network_available,
        )
        if not allowed:
            diag.record_skip(reason or "not_authorized")
            return diag

        aid = assessment_id or new_assessment_id()
        installation_id = resolve_installation_id_safely()
        if source is None:
            if result is not None:
                source = build_success_projection_source(
                    result,
                    assessment_id=aid,
                    installation_id=installation_id,
                    offline_mode=offline_mode,
                )
            else:
                source = build_failure_projection_source(
                    assessment_id=aid,
                    installation_id=installation_id,
                    failure=failure,
                    offline_mode=offline_mode,
                    ai_used=ai_used,
                )

        wire = project_assessment_metadata(source, policy=active_policy)
        active_transport = transport or HttpAssessmentMetadataTransport(
            policy=active_policy
        )
        transport_result = _send_once(active_transport, wire)
        if transport_result.kind == "sent":
            diag.record_success(status_category=transport_result.status_category)
        else:
            diag.record_failure(transport_result.status_category)
        return diag
    except Exception:  # noqa: BLE001 — assessment outcome always wins
        diag.record_failure("internal")
        return diag


def _send_once(
    transport: AssessmentMetadataTransport,
    wire: AssessmentMetadataWireRequest,
) -> AssessmentMetadataTransportResult:
    return transport.send(wire)


def project_only(
    source: AssessmentMetadataProjectionSource,
    *,
    policy: CommunityAssessmentMetadataEmissionPolicy | None = None,
) -> dict[str, Any]:
    """Test helper: project to stable dict without transport."""

    return project_assessment_metadata(source, policy=policy).to_stable_dict()


__all__ = [
    "emit_assessment_metadata_safely",
    "emission_authorized",
    "project_only",
    "resolve_installation_id_safely",
]
