"""HTTP request, auth, status, retry, and fail-silent tests (Slice 9.11)."""

from __future__ import annotations

import json

from codestrata.telemetry.infrastructure.http_client import FakeTelemetryHttpResponse
from codestrata.telemetry.transport import TelemetryTransportResultKind
from codestrata.telemetry.transport_errors import TransportFailureCategory
from codestrata.telemetry.transport_retry import should_retry
from tests.telemetry.transport_test_helpers import (
    FIXED_EVENT_ID,
    TEST_ENDPOINT,
    TEST_TOKEN,
    accepted_body,
    already_accepted_body,
    assert_no_secret_leak,
    gated_event,
    make_http_transport,
)


def test_accepted_and_headers() -> None:
    transport, client = make_http_transport()
    result = transport.send(gated_event())
    assert result.kind is TelemetryTransportResultKind.SENT
    assert result.failure_category == TransportFailureCategory.ACCEPTED.value
    assert result.acknowledged is True
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == TEST_ENDPOINT
    headers = call["headers"]
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["Authorization"] == "Bearer [redacted]"
    body = json.loads(call["body"])
    assert body["event_id"] == FIXED_EVENT_ID
    # Slice 19.1: optional privacy-safe anonymous installation_id for Insights
    # first/repeat. Must be UUID-shaped when present; never a secret.
    iid = body.get("installation_id")
    assert isinstance(iid, str) and len(iid) >= 32
    assert TEST_TOKEN.encode() not in call["body"]
    assert iid.encode() not in TEST_TOKEN.encode()


def test_already_accepted() -> None:
    transport, _ = make_http_transport(
        responses=FakeTelemetryHttpResponse(
            status_code=200, body=already_accepted_body()
        )
    )
    result = transport.send(gated_event())
    assert result.kind is TelemetryTransportResultKind.SENT
    assert result.failure_category == TransportFailureCategory.ALREADY_ACCEPTED.value


def test_malformed_ack_not_accepted() -> None:
    transport, _ = make_http_transport(
        responses=FakeTelemetryHttpResponse(status_code=202, body=b'{"status":"nope"}')
    )
    result = transport.send(gated_event())
    assert result.kind is TelemetryTransportResultKind.FAILED_SILENTLY
    assert result.failure_category == TransportFailureCategory.INVALID_RESPONSE.value
    assert result.sent is False
    assert result.acknowledged is False


def test_status_classification_matrix() -> None:
    cases = [
        (401, TransportFailureCategory.AUTHENTICATION_FAILED, TelemetryTransportResultKind.REJECTED),
        (403, TransportFailureCategory.AUTHORIZATION_DENIED, TelemetryTransportResultKind.REJECTED),
        (409, TransportFailureCategory.CONFLICT, TelemetryTransportResultKind.REJECTED),
        (413, TransportFailureCategory.PAYLOAD_TOO_LARGE, TelemetryTransportResultKind.REJECTED),
        (422, TransportFailureCategory.VALIDATION_REJECTED, TelemetryTransportResultKind.REJECTED),
        (429, TransportFailureCategory.RATE_LIMITED, TelemetryTransportResultKind.FAILED_SILENTLY),
        (500, TransportFailureCategory.SERVER_UNAVAILABLE, TelemetryTransportResultKind.FAILED_SILENTLY),
        (502, TransportFailureCategory.SERVER_UNAVAILABLE, TelemetryTransportResultKind.FAILED_SILENTLY),
        (503, TransportFailureCategory.SERVER_UNAVAILABLE, TelemetryTransportResultKind.FAILED_SILENTLY),
        (504, TransportFailureCategory.SERVER_UNAVAILABLE, TelemetryTransportResultKind.FAILED_SILENTLY),
    ]
    for status, category, kind in cases:
        transport, client = make_http_transport(
            responses=FakeTelemetryHttpResponse(status_code=status, body=b"{}")
        )
        result = transport.send(gated_event())
        assert result.failure_category == category.value
        assert result.kind is kind
        assert len(client.calls) == 1  # default max attempts = 1


def test_redirect_rejected() -> None:
    transport, _ = make_http_transport(
        responses=FakeTelemetryHttpResponse(status_code=302, redirected=True, body=b"")
    )
    result = transport.send(gated_event())
    assert result.failure_category == TransportFailureCategory.REDIRECT_REJECTED.value


def test_timeout_and_connection() -> None:
    transport, _ = make_http_transport(
        responses=FakeTelemetryHttpResponse(status_code=0, raise_timeout=True)
    )
    result = transport.send(gated_event())
    assert result.failure_category == TransportFailureCategory.TIMEOUT.value

    transport2, _ = make_http_transport(
        responses=FakeTelemetryHttpResponse(status_code=0, raise_connection=True)
    )
    result2 = transport2.send(gated_event())
    assert result2.failure_category == TransportFailureCategory.CONNECTION_FAILED.value


def test_no_retry_on_auth_or_conflict() -> None:
    assert should_retry(
        attempt=1,
        maximum_attempts=2,
        category=TransportFailureCategory.AUTHENTICATION_FAILED,
    ) is False
    assert should_retry(
        attempt=1,
        maximum_attempts=2,
        category=TransportFailureCategory.CONFLICT,
    ) is False
    assert should_retry(
        attempt=1,
        maximum_attempts=1,
        category=TransportFailureCategory.SERVER_UNAVAILABLE,
    ) is False


def test_optional_retry_reuses_event_id() -> None:
    transport, client = make_http_transport(
        maximum_attempts=2,
        responses=[
            FakeTelemetryHttpResponse(status_code=503, body=b"{}"),
            FakeTelemetryHttpResponse(status_code=202, body=accepted_body()),
        ],
    )
    result = transport.send(gated_event())
    assert result.kind is TelemetryTransportResultKind.SENT
    assert result.attempt_count == 2
    assert len(client.calls) == 2
    bodies = [json.loads(call["body"]) for call in client.calls]
    assert bodies[0]["event_id"] == bodies[1]["event_id"] == FIXED_EVENT_ID


def test_reject_non_privacy_safe_event() -> None:
    transport, client = make_http_transport()
    result = transport.send({"event_type": "application_started"})  # type: ignore[arg-type]
    assert result.kind is TelemetryTransportResultKind.REJECTED
    assert result.failure_category == TransportFailureCategory.PRIVACY_REJECTED.value
    assert client.calls == []


def test_diagnostics_have_no_secrets() -> None:
    transport, _ = make_http_transport()
    transport.send(gated_event())
    blob = transport.diagnostics.to_stable_json()
    assert_no_secret_leak(blob)
    assert transport.diagnostics.accepted_count == 1
