"""Fail-silent Community Cloud HTTP telemetry transport (Slice 9.11)."""

from __future__ import annotations

import json
from typing import Any

from codestrata.telemetry.infrastructure.http_client import (
    StdlibTelemetryHttpClient,
    TelemetryHttpClient,
    TelemetryHttpConnectionError,
    TelemetryHttpTimeout,
)
from codestrata.telemetry.pre_transport_policy import (
    COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION,
)
from codestrata.telemetry.projection import PrivacySafeTelemetryEvent
from codestrata.telemetry.transport import (
    TelemetryTransportResult,
    TelemetryTransportResultKind,
)
from codestrata.telemetry.transport_configuration import TelemetryTransportConfiguration
from codestrata.telemetry.transport_diagnostics import TelemetryTransportDiagnostics
from codestrata.telemetry.transport_errors import TransportFailureCategory
from codestrata.telemetry.transport_mapping import (
    TransportMappingError,
    map_privacy_safe_event_to_cloud_request,
)
from codestrata.telemetry.transport_policy import (
    COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION,
    DEFAULT_MAX_BODY_BYTES,
)
from codestrata.telemetry.transport_retry import should_retry


def _result(
    kind: TelemetryTransportResultKind,
    category: TransportFailureCategory,
    *,
    attempt_count: int,
    policy_version: str,
) -> TelemetryTransportResult:
    sent = kind is TelemetryTransportResultKind.SENT
    acknowledged = category in {
        TransportFailureCategory.ACCEPTED,
        TransportFailureCategory.ALREADY_ACCEPTED,
    }
    return TelemetryTransportResult(
        kind=kind,
        sent=sent,
        acknowledged=acknowledged,
        attempt_count=attempt_count,
        failure_category=category.value,
        transport_policy_version=policy_version,
        cloud_schema_version=COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION,
        privacy_policy_version=COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION,
    )


class HttpTelemetryTransport:
    """Explicit HTTP transport — never the product default."""

    def __init__(
        self,
        configuration: TelemetryTransportConfiguration,
        *,
        client: TelemetryHttpClient | None = None,
    ) -> None:
        self._configuration = configuration
        self._client = client or StdlibTelemetryHttpClient(
            max_body_bytes=DEFAULT_MAX_BODY_BYTES
        )
        self._diagnostics = TelemetryTransportDiagnostics(
            transport_policy_version=configuration.policy.policy_version  # type: ignore[union-attr]
            if configuration.policy is not None
            else "1.0",
            configured=True,
        )

    @property
    def transport_category(self) -> str:
        return "http"

    @property
    def diagnostics(self) -> TelemetryTransportDiagnostics:
        return self._diagnostics

    def send(self, event: PrivacySafeTelemetryEvent) -> TelemetryTransportResult:
        """Map + POST a gated privacy-safe event. Never raises to callers."""

        try:
            return self._send_impl(event)
        except Exception:
            self._diagnostics.record(TransportFailureCategory.INTERNAL_FAILURE.value)
            return _result(
                TelemetryTransportResultKind.FAILED_SILENTLY,
                TransportFailureCategory.INTERNAL_FAILURE,
                attempt_count=1,
                policy_version=self._policy_version(),
            )

    def _policy_version(self) -> str:
        policy = self._configuration.policy
        return policy.policy_version if policy is not None else "1.0"

    def _send_impl(self, event: PrivacySafeTelemetryEvent) -> TelemetryTransportResult:
        if not self._configuration.enabled:
            self._diagnostics.record(TransportFailureCategory.DISABLED.value)
            return _result(
                TelemetryTransportResultKind.DISABLED,
                TransportFailureCategory.DISABLED,
                attempt_count=0,
                policy_version=self._policy_version(),
            )

        if type(event) is not PrivacySafeTelemetryEvent:
            self._diagnostics.record(TransportFailureCategory.PRIVACY_REJECTED.value)
            return _result(
                TelemetryTransportResultKind.REJECTED,
                TransportFailureCategory.PRIVACY_REJECTED,
                attempt_count=0,
                policy_version=self._policy_version(),
            )

        event_id = self._configuration.event_id_factory()
        installation_id: str | None = None
        try:
            from codestrata.telemetry.identity import ensure_installation_id

            installation_id, _created = ensure_installation_id()
        except Exception:  # noqa: BLE001 — optional identity never blocks transport
            installation_id = None
        try:
            wire = map_privacy_safe_event_to_cloud_request(
                event,
                event_id=event_id,
                client_version_fallback=self._configuration.client_version,
                installation_id=installation_id,
            )
        except TransportMappingError:
            self._diagnostics.record(TransportFailureCategory.VALIDATION_REJECTED.value)
            return _result(
                TelemetryTransportResultKind.REJECTED,
                TransportFailureCategory.VALIDATION_REJECTED,
                attempt_count=0,
                policy_version=self._policy_version(),
            )

        body = wire.to_canonical_bytes()
        if len(body) > DEFAULT_MAX_BODY_BYTES:
            self._diagnostics.record(TransportFailureCategory.PAYLOAD_TOO_LARGE.value)
            return _result(
                TelemetryTransportResultKind.REJECTED,
                TransportFailureCategory.PAYLOAD_TOO_LARGE,
                attempt_count=0,
                policy_version=self._policy_version(),
            )

        headers = {
            "Accept": "application/json",
            "Authorization": self._configuration.credential.authorization_header_value(),
            "Content-Type": "application/json",
            "User-Agent": f"codestrata-cli/{self._configuration.client_version}",
        }

        maximum_attempts = self._configuration.maximum_attempts
        attempt = 0
        last_category = TransportFailureCategory.INTERNAL_FAILURE
        last_kind = TelemetryTransportResultKind.FAILED_SILENTLY

        while attempt < maximum_attempts:
            attempt += 1
            category, kind = self._single_attempt(body=body, headers=headers)
            last_category = category
            last_kind = kind
            if kind is TelemetryTransportResultKind.SENT:
                self._diagnostics.record(category.value, attempts=attempt)
                return _result(
                    kind,
                    category,
                    attempt_count=attempt,
                    policy_version=self._policy_version(),
                )
            if not should_retry(
                attempt=attempt,
                maximum_attempts=maximum_attempts,
                category=category,
            ):
                break

        self._diagnostics.record(last_category.value, attempts=attempt)
        return _result(
            last_kind,
            last_category,
            attempt_count=attempt,
            policy_version=self._policy_version(),
        )

    def _single_attempt(
        self,
        *,
        body: bytes,
        headers: dict[str, str],
    ) -> tuple[TransportFailureCategory, TelemetryTransportResultKind]:
        try:
            response = self._client.post_json(
                url=self._configuration.endpoint,
                body=body,
                headers=headers,
                connect_timeout_seconds=self._configuration.connect_timeout_seconds,
                read_timeout_seconds=self._configuration.read_timeout_seconds,
            )
        except TelemetryHttpTimeout:
            return (
                TransportFailureCategory.TIMEOUT,
                TelemetryTransportResultKind.FAILED_SILENTLY,
            )
        except TelemetryHttpConnectionError:
            return (
                TransportFailureCategory.CONNECTION_FAILED,
                TelemetryTransportResultKind.FAILED_SILENTLY,
            )
        except Exception:
            return (
                TransportFailureCategory.INTERNAL_FAILURE,
                TelemetryTransportResultKind.FAILED_SILENTLY,
            )

        if response.redirected or 300 <= response.status_code < 400:
            return (
                TransportFailureCategory.REDIRECT_REJECTED,
                TelemetryTransportResultKind.REJECTED,
            )

        return _classify_http_response(response.status_code, response.body)


def _classify_http_response(
    status_code: int,
    body: bytes,
) -> tuple[TransportFailureCategory, TelemetryTransportResultKind]:
    if status_code == 202:
        if _ack_status(body) == "accepted":
            return (
                TransportFailureCategory.ACCEPTED,
                TelemetryTransportResultKind.SENT,
            )
        return (
            TransportFailureCategory.INVALID_RESPONSE,
            TelemetryTransportResultKind.FAILED_SILENTLY,
        )
    if status_code == 200:
        if _ack_status(body) == "already_accepted":
            return (
                TransportFailureCategory.ALREADY_ACCEPTED,
                TelemetryTransportResultKind.SENT,
            )
        return (
            TransportFailureCategory.INVALID_RESPONSE,
            TelemetryTransportResultKind.FAILED_SILENTLY,
        )
    if status_code == 401:
        return (
            TransportFailureCategory.AUTHENTICATION_FAILED,
            TelemetryTransportResultKind.REJECTED,
        )
    if status_code == 403:
        return (
            TransportFailureCategory.AUTHORIZATION_DENIED,
            TelemetryTransportResultKind.REJECTED,
        )
    if status_code == 409:
        return (
            TransportFailureCategory.CONFLICT,
            TelemetryTransportResultKind.REJECTED,
        )
    if status_code == 413:
        return (
            TransportFailureCategory.PAYLOAD_TOO_LARGE,
            TelemetryTransportResultKind.REJECTED,
        )
    if status_code in {400, 404, 422}:
        return (
            TransportFailureCategory.VALIDATION_REJECTED,
            TelemetryTransportResultKind.REJECTED,
        )
    if status_code == 429:
        return (
            TransportFailureCategory.RATE_LIMITED,
            TelemetryTransportResultKind.FAILED_SILENTLY,
        )
    if status_code in {502, 503, 504}:
        return (
            TransportFailureCategory.SERVER_UNAVAILABLE,
            TelemetryTransportResultKind.FAILED_SILENTLY,
        )
    if status_code >= 500:
        return (
            TransportFailureCategory.SERVER_UNAVAILABLE,
            TelemetryTransportResultKind.FAILED_SILENTLY,
        )
    return (
        TransportFailureCategory.INVALID_RESPONSE,
        TelemetryTransportResultKind.FAILED_SILENTLY,
    )


def _ack_status(body: bytes) -> str | None:
    try:
        payload: Any = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    if status in {"accepted", "already_accepted"}:
        return str(status)
    return None


__all__ = ["HttpTelemetryTransport"]
