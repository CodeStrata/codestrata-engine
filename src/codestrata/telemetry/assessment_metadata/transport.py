"""HTTP transport for Community assessment_metadata POST (Slice 20.8).

Reuses StdlibTelemetryHttpClient / FakeTelemetryHttpClient. Never logs bodies.
Endpoint authority is ``codestrata.community_cloud.public_api_authority`` —
this module must not redefine public path literals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from codestrata.community_cloud.public_api_authority import (
    PUBLIC_ASSESSMENT_METADATA_URL,
    production_assessment_metadata_url,
)
from codestrata.community_cloud.report_publishing import resolve_community_credential
from codestrata.package_metadata import get_package_version
from codestrata.telemetry.assessment_metadata.models import AssessmentMetadataWireRequest
from codestrata.telemetry.assessment_metadata.policy import (
    CommunityAssessmentMetadataEmissionPolicy,
    default_assessment_metadata_emission_policy,
)
from codestrata.telemetry.event_identity import (
    TelemetryTransportCredential,
    TransportCredentialError,
)
from codestrata.telemetry.infrastructure.http_client import (
    StdlibTelemetryHttpClient,
    TelemetryHttpClient,
    TelemetryHttpConnectionError,
    TelemetryHttpTimeout,
)


@dataclass(frozen=True, slots=True)
class AssessmentMetadataTransportResult:
    kind: str
    status_category: str
    attempt_count: int = 1

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "attempt_count": self.attempt_count,
            "kind": self.kind,
            "status_category": self.status_category,
        }


class AssessmentMetadataTransport(Protocol):
    def send(
        self, request: AssessmentMetadataWireRequest
    ) -> AssessmentMetadataTransportResult: ...


class HttpAssessmentMetadataTransport:
    """Best-effort POST — one attempt; never raises to callers."""

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        credential: TelemetryTransportCredential | None = None,
        client: TelemetryHttpClient | None = None,
        policy: CommunityAssessmentMetadataEmissionPolicy | None = None,
        client_version: str | None = None,
    ) -> None:
        self._policy = policy or default_assessment_metadata_emission_policy()
        self._endpoint = endpoint or production_assessment_metadata_url()
        self._credential = credential
        self._client = client or StdlibTelemetryHttpClient(
            max_body_bytes=self._policy.max_body_bytes
        )
        self._client_version = client_version or get_package_version()

    def send(
        self, request: AssessmentMetadataWireRequest
    ) -> AssessmentMetadataTransportResult:
        try:
            return self._send_impl(request)
        except Exception:  # noqa: BLE001 — fail-silent
            return AssessmentMetadataTransportResult(
                kind="failed_silently",
                status_category="internal",
                attempt_count=1,
            )

    def _send_impl(
        self, request: AssessmentMetadataWireRequest
    ) -> AssessmentMetadataTransportResult:
        credential = self._credential
        if credential is None:
            try:
                credential = resolve_community_credential()
            except (TransportCredentialError, ValueError, Exception):
                return AssessmentMetadataTransportResult(
                    kind="failed_silently",
                    status_category="unavailable",
                    attempt_count=0,
                )

        payload = request.to_stable_dict()
        body = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        if len(body) > self._policy.max_body_bytes:
            return AssessmentMetadataTransportResult(
                kind="rejected",
                status_category="payload_too_large",
                attempt_count=0,
            )

        headers: Mapping[str, str] = {
            "Accept": "application/json",
            "Authorization": credential.authorization_header_value(),
            "Content-Type": "application/json",
            "User-Agent": f"codestrata-cli/{self._client_version}",
        }

        try:
            response = self._client.post_json(
                url=self._endpoint,
                body=body,
                headers=headers,
                connect_timeout_seconds=self._policy.connect_timeout_seconds,
                read_timeout_seconds=self._policy.read_timeout_seconds,
            )
        except TelemetryHttpTimeout:
            return AssessmentMetadataTransportResult(
                kind="failed_silently",
                status_category="timeout",
                attempt_count=1,
            )
        except TelemetryHttpConnectionError:
            return AssessmentMetadataTransportResult(
                kind="failed_silently",
                status_category="connection_failed",
                attempt_count=1,
            )
        except Exception:
            return AssessmentMetadataTransportResult(
                kind="failed_silently",
                status_category="internal",
                attempt_count=1,
            )

        return _classify_status(response.status_code, response.body)


class CaptureAssessmentMetadataTransport:
    """Test double — records wire dicts without network I/O."""

    def __init__(
        self,
        *,
        result: AssessmentMetadataTransportResult | None = None,
        raise_on_send: bool = False,
    ) -> None:
        self.captured: list[dict[str, Any]] = []
        self._result = result or AssessmentMetadataTransportResult(
            kind="sent",
            status_category="accepted",
            attempt_count=1,
        )
        self._raise = raise_on_send

    def send(
        self, request: AssessmentMetadataWireRequest
    ) -> AssessmentMetadataTransportResult:
        if self._raise:
            raise RuntimeError("capture_transport_boom")
        self.captured.append(request.to_stable_dict())
        return self._result


def _classify_status(status_code: int, body: bytes) -> AssessmentMetadataTransportResult:
    if status_code in {200, 202}:
        ack = _ack_status(body)
        if ack in {"accepted", "already_accepted"} or ack is None:
            return AssessmentMetadataTransportResult(
                kind="sent",
                status_category=ack or "accepted",
                attempt_count=1,
            )
        return AssessmentMetadataTransportResult(
            kind="failed_silently",
            status_category="malformed_response",
            attempt_count=1,
        )
    if status_code in {400, 422}:
        return AssessmentMetadataTransportResult(
            kind="rejected",
            status_category="validation",
            attempt_count=1,
        )
    if status_code in {401, 403}:
        return AssessmentMetadataTransportResult(
            kind="rejected",
            status_category="authorization",
            attempt_count=1,
        )
    if status_code == 429:
        return AssessmentMetadataTransportResult(
            kind="failed_silently",
            status_category="rate_limited",
            attempt_count=1,
        )
    if status_code >= 500:
        return AssessmentMetadataTransportResult(
            kind="failed_silently",
            status_category="server_error",
            attempt_count=1,
        )
    return AssessmentMetadataTransportResult(
        kind="failed_silently",
        status_category="unknown",
        attempt_count=1,
    )


def _ack_status(body: bytes) -> str | None:
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    if isinstance(status, str):
        return status.strip().lower()
    return None


__all__ = [
    "AssessmentMetadataTransport",
    "AssessmentMetadataTransportResult",
    "CaptureAssessmentMetadataTransport",
    "HttpAssessmentMetadataTransport",
    "PUBLIC_ASSESSMENT_METADATA_URL",
    "production_assessment_metadata_url",
]
