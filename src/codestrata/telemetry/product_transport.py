"""Resolve production Community HTTP telemetry transport after explicit opt-in.

Disabled / denied / non-interactive sessions remain on UnavailableTelemetryTransport.
When transmission is authorized and a Community client credential is available,
product construction targets the public Community API (api.codestrata.ai).

Never reads CODESTRATA_TELEMETRY_ENDPOINT. Fail-soft on missing/invalid credential
(returns Unavailable) so assessment is never blocked.
"""

from __future__ import annotations

from codestrata.community_cloud.public_api_authority import production_telemetry_ingest_url
from codestrata.telemetry.consent import TelemetrySessionConsent
from codestrata.telemetry.event_identity import TransportCredentialError
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.transport import TelemetryTransport
from codestrata.telemetry.transport_configuration import (
    TelemetryTransportConfiguration,
    TransportConfigurationError,
)
from codestrata.telemetry.transport_factory import create_http_telemetry_transport


def try_create_production_http_transport() -> TelemetryTransport | None:
    """Build HTTP transport for production ingest when a Community client is available."""

    from codestrata.community_cloud.report_publishing import resolve_community_credential

    try:
        credential = resolve_community_credential()
        configuration = TelemetryTransportConfiguration(
            endpoint=production_telemetry_ingest_url(),
            credential=credential,
        )
    except (TransportCredentialError, TransportConfigurationError, ValueError):
        return None
    except Exception:  # noqa: BLE001 - never break product construction
        return None
    return create_http_telemetry_transport(configuration)


def resolve_product_telemetry_transport(
    consent: TelemetrySessionConsent,
    *,
    transport: TelemetryTransport | None = None,
) -> TelemetryTransport:
    """Choose transport for a command-session runtime.

    Explicit ``transport`` injection (tests) always wins. Unauthorized consent
    stays unavailable. Authorized consent uses production HTTP when a valid
    Community client credential is available (env override or packaged public
    client); otherwise unavailable (best-effort — no anonymous ingestion).
    """

    if transport is not None:
        return transport
    if not consent.transmission_authorized:
        return UnavailableTelemetryTransport()
    http = try_create_production_http_transport()
    if http is not None:
        return http
    return UnavailableTelemetryTransport()


__all__ = [
    "resolve_product_telemetry_transport",
    "try_create_production_http_transport",
]
