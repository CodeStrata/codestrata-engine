"""Transport configuration and credential tests (Slice 9.11)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.event_identity import (
    TelemetryTransportCredential,
    TransportCredentialError,
)
from codestrata.telemetry.transport_configuration import (
    TelemetryTransportConfiguration,
    TransportConfigurationError,
)
from tests.telemetry.transport_test_helpers import TEST_ENDPOINT, TEST_TOKEN, make_config


def test_credential_valid_and_redacted() -> None:
    cred = TelemetryTransportCredential(TEST_TOKEN)
    assert "Bearer " in cred.authorization_header_value()
    assert TEST_TOKEN not in repr(cred)
    assert TEST_TOKEN not in str(cred)


def test_credential_rejects_bad_format() -> None:
    with pytest.raises(TransportCredentialError):
        TelemetryTransportCredential("not-a-token")
    with pytest.raises(TransportCredentialError):
        TelemetryTransportCredential("cscc_v1_short")


def test_configuration_requires_https_and_path() -> None:
    with pytest.raises(TransportConfigurationError):
        make_config(endpoint="http://example.com/api/v1/telemetry")
    with pytest.raises(TransportConfigurationError):
        make_config(endpoint="https://example.com")
    with pytest.raises(TransportConfigurationError):
        make_config(endpoint="https://user:pass@example.com/api/v1/telemetry")
    with pytest.raises(TransportConfigurationError):
        make_config(endpoint="https://example.com/api/v1/telemetry?token=x")


def test_localhost_http_requires_explicit_flag() -> None:
    with pytest.raises(TransportConfigurationError):
        make_config(endpoint="http://127.0.0.1:9/api/v1/telemetry")
    cfg = make_config(
        endpoint="http://127.0.0.1:9/api/v1/telemetry",
        allow_http_localhost=True,
    )
    assert cfg.allow_http_localhost is True


def test_public_dict_redacts_secrets() -> None:
    public = make_config().to_public_dict()
    blob = str(public)
    assert TEST_TOKEN not in blob
    assert TEST_ENDPOINT not in blob
    assert public["endpoint_configured"] is True
    assert public["scheme"] == "https"
    assert list(public.keys()) == sorted(public.keys())


def test_configuration_does_not_read_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", TEST_ENDPOINT)
    monkeypatch.setenv("CODESTRATA_TELEMETRY_TOKEN", TEST_TOKEN)
    # Construction still requires explicit fields — env alone is insufficient.
    with pytest.raises(TypeError):
        TelemetryTransportConfiguration()  # type: ignore[call-arg]
