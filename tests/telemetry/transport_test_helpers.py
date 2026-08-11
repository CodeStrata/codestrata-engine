"""Shared helpers for Slice 9.11 transport tests."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.event_identity import TelemetryTransportCredential
from codestrata.telemetry.events import (
    OsFamily,
    ResultCategory,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.infrastructure.http_client import (
    FakeTelemetryHttpClient,
    FakeTelemetryHttpResponse,
)
from codestrata.telemetry.pre_transport_gate import validate_event_before_transport
from codestrata.telemetry.projection import project_runtime_event
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.transport_configuration import TelemetryTransportConfiguration
from codestrata.telemetry.transport_factory import create_http_telemetry_transport

TEST_TOKEN = "cscc_v1_" + ("a" * 20)
TEST_ENDPOINT = "https://telemetry.example.test/api/v1/telemetry"
FIXED_EVENT_ID = "11111111-2222-3333-4444-555555555555"


def accepted_body() -> bytes:
    return json.dumps(
        {
            "retry_status": "first_seen",
            "schema_version": "1.0",
            "status": "accepted",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def already_accepted_body() -> bytes:
    return json.dumps(
        {
            "retry_status": "exact_retry",
            "schema_version": "1.0",
            "status": "already_accepted",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sample_runtime_event() -> RuntimeTelemetryEvent:
    return RuntimeTelemetryEvent(
        event_type=RuntimeEventType.FEATURE_COMPLETED,
        cli_version="0.2.0",
        os_family=OsFamily.LINUX,
        result=ResultCategory.SUCCESS,
        offline_mode=True,
    )


def gated_event():
    projected = project_runtime_event(sample_runtime_event())
    gate = validate_event_before_transport(projected)
    assert gate.accepted and gate.accepted_event is not None
    return gate.accepted_event


def make_config(**kwargs) -> TelemetryTransportConfiguration:
    payload = {
        "endpoint": TEST_ENDPOINT,
        "credential": TelemetryTransportCredential(TEST_TOKEN),
        "event_id_factory": lambda: FIXED_EVENT_ID,
        "client_version": "0.2.0",
    }
    payload.update(kwargs)
    return TelemetryTransportConfiguration(**payload)


def make_http_transport(
    *,
    responses: list[FakeTelemetryHttpResponse] | FakeTelemetryHttpResponse | None = None,
    **config_kwargs,
):
    client = FakeTelemetryHttpClient(
        FakeTelemetryHttpResponse(status_code=202, body=accepted_body())
        if responses is None
        else responses
    )
    transport = create_http_telemetry_transport(
        make_config(**config_kwargs), client=client
    )
    return transport, client


def make_allowed_http_runtime(
    *,
    responses: list[FakeTelemetryHttpResponse] | FakeTelemetryHttpResponse | None = None,
    **config_kwargs,
):
    transport, client = make_http_transport(responses=responses, **config_kwargs)
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=transport,
    )
    return runtime, transport, client


def freeze_home_temp(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    temp = tmp_path / "tmp"
    home.mkdir()
    temp.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMPDIR", str(temp))
    monkeypatch.setenv("TMP", str(temp))
    monkeypatch.setenv("TEMP", str(temp))
    return home


def assert_no_secret_leak(blob: str) -> None:
    lower = blob.lower()
    assert TEST_TOKEN.lower() not in lower
    assert TEST_ENDPOINT.lower() not in lower
    assert FIXED_EVENT_ID not in blob
