"""Factory, boundary, consent, privacy, persistence, and integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from codestrata.telemetry.consent import (
    allow_session_consent,
    default_session_consent,
    deny_session_consent,
)
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.preview_builder import build_privacy_first_telemetry_preview
from codestrata.telemetry.runtime import run_with_isolated_telemetry
from codestrata.telemetry.runtime_factory import (
    create_default_telemetry_runtime,
    create_session_telemetry_runtime,
)
from codestrata.telemetry.status import build_privacy_first_telemetry_status
from codestrata.telemetry.status_formatting import format_privacy_first_telemetry_status
from codestrata.telemetry.transport import TelemetryTransportResultKind
from codestrata.telemetry.transport_factory import create_http_telemetry_transport
from codestrata.telemetry.transport_http import HttpTelemetryTransport
from tests.telemetry.transport_test_helpers import (
    TEST_ENDPOINT,
    TEST_TOKEN,
    assert_no_secret_leak,
    freeze_home_temp,
    gated_event,
    make_allowed_http_runtime,
    make_config,
    make_http_transport,
    sample_runtime_event,
)


def test_default_factory_remains_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", TEST_ENDPOINT)
    runtime = create_default_telemetry_runtime()
    assert isinstance(runtime.session.transport, UnavailableTelemetryTransport)
    result = runtime.record(sample_runtime_event())
    assert result.transport_kind == TelemetryTransportResultKind.DISABLED.value


def test_factory_explicit_only() -> None:
    transport = create_http_telemetry_transport(make_config())
    assert isinstance(transport, HttpTelemetryTransport)
    assert transport.transport_category == "http"


def test_denied_and_default_skip_credentials_and_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, client = make_http_transport()
    for consent in (default_session_consent(), deny_session_consent()):
        runtime = create_session_telemetry_runtime(consent=consent, transport=transport)
        result = runtime.record(sample_runtime_event())
        assert result.transport_kind == TelemetryTransportResultKind.DISABLED.value
    assert client.calls == []


def test_allowed_with_http_transport_sends_gated_event() -> None:
    runtime, transport, client = make_allowed_http_runtime()
    result = runtime.record(sample_runtime_event())
    assert result.transport_kind == TelemetryTransportResultKind.SENT.value
    assert len(client.calls) == 1
    assert transport.diagnostics.accepted_count == 1


def test_capture_still_test_only_and_gated() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(), transport=capture
    )
    runtime.record(sample_runtime_event())
    assert len(capture.captured) == 1
    assert create_default_telemetry_runtime().session.transport.transport_category == (
        "unavailable"
    )


def test_no_persistence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = freeze_home_temp(monkeypatch, tmp_path)
    runtime, _, client = make_allowed_http_runtime()
    runtime.record(sample_runtime_event())
    assert client.calls
    leftover = [p for p in home.rglob("*") if p.is_file()]
    # Anonymous installation identity may be persisted for Insights first/repeat.
    # No queue, credentials, or event payloads may be written.
    allowed = {
        home / ".codestrata" / "installation_id",
    }
    unexpected = [p for p in leftover if p.resolve() not in {a.resolve() for a in allowed}]
    assert unexpected == []
    temp_files = [p for p in (tmp_path / "tmp").rglob("*") if p.is_file()]
    assert temp_files == []
    body = __import__("json").loads(client.calls[0]["body"])
    assert "installation_id" in body
    assert isinstance(body["installation_id"], str)


def test_preview_does_not_invoke_http() -> None:
    transport, client = make_http_transport()
    _ = transport  # ensure transport exists but preview path must not use it
    preview = build_privacy_first_telemetry_preview()
    assert preview.transmission_performed is False
    assert client.calls == []
    blob = preview.to_stable_json()
    assert '"event_id"' not in blob
    assert "Authorization" not in blob
    assert TEST_ENDPOINT not in blob
    assert TEST_TOKEN not in blob


def test_status_reports_unavailable_and_no_secrets() -> None:
    status = build_privacy_first_telemetry_status()
    assert status.transport_status == "unavailable"
    assert status.transmission_available is False
    text = format_privacy_first_telemetry_status(status)
    assert "Transport: Unavailable" in text
    assert "Operational transport configured: No" in text
    assert "HTTP transport implementation: Present" in text
    assert "transport" in {name for name, _ in status.policy_versions}
    assert_no_secret_leak(text)
    assert_no_secret_leak(status.to_stable_json())


def test_primary_operation_isolation_with_failing_http() -> None:
    from codestrata.telemetry.infrastructure.http_client import FakeTelemetryHttpResponse

    runtime, _, client = make_allowed_http_runtime(
        responses=FakeTelemetryHttpResponse(status_code=0, raise_connection=True)
    )

    def primary() -> str:
        return "ok"

    value = run_with_isolated_telemetry(
        primary,
        runtime=runtime,
        on_success_event=sample_runtime_event(),
    )
    assert value == "ok"
    assert client.calls  # telemetry attempted
    assert runtime.diagnostics().transport_sent == 0


def test_platform_boundary_no_imports() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
    forbidden = ("codestrata_platform", "boto3", "botocore")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{path} imports {needle}"


def test_env_proxy_values_not_in_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:8080")
    transport, _ = make_http_transport()
    transport.send(gated_event())
    blob = transport.diagnostics.to_stable_json()
    assert "proxy.example" not in blob
    assert os.environ.get("HTTPS_PROXY")  # still set, but unused by diagnostics
