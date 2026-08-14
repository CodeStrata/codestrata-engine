"""Emitter / transport matrix E1–E10 + v1 consent protection (Slice 20.8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.telemetry.assessment_isolation import (
    run_assessment_with_telemetry_isolation,
)
from codestrata.telemetry.assessment_metadata.diagnostics import (
    AssessmentMetadataEmissionDiagnostics,
)
from codestrata.telemetry.assessment_metadata.emitter import (
    emit_assessment_metadata_safely,
    emission_authorized,
)
from codestrata.telemetry.assessment_metadata.models import (
    AssessmentMetadataProjectionSource,
    FindingProjectionRow,
)
from codestrata.telemetry.assessment_metadata.policy import (
    authorized_assessment_metadata_emission_policy,
    default_assessment_metadata_emission_policy,
)
from codestrata.telemetry.assessment_metadata.source import new_assessment_id
from codestrata.telemetry.assessment_metadata.transport import (
    CaptureAssessmentMetadataTransport,
    HttpAssessmentMetadataTransport,
    AssessmentMetadataTransportResult,
)
from codestrata.telemetry.consent import allow_session_consent, deny_session_consent
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.event_identity import TelemetryTransportCredential
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.http_client import (
    FakeTelemetryHttpClient,
    FakeTelemetryHttpResponse,
)
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime

_AID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_INSTALL = "11111111-1111-4111-8111-111111111111"
_TOKEN = "cscc_v1_" + ("a" * 32)


def _source(**overrides: object) -> AssessmentMetadataProjectionSource:
    data: dict[str, object] = {
        "assessment_id": _AID,
        "event_id": "amd-emit-0001",
        "client_version": "0.2.0",
        "platform": "darwin",
        "success": True,
        "assessment_mode": "deterministic",
        "executed_heads": ("security",),
        "findings": (
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="security",
            ),
        ),
        "duration_ms": 5_000.0,
        "installation_id": _INSTALL,
        "finding_count": 1,
        "offline_mode": True,
        "ai_used": False,
        "report_json_generated": True,
        "findings_json_generated": True,
        "html_report_generated": True,
        "artifact_count": 2,
        "primary_language": "python",
        "language_count": 1,
        "file_count_bucket": "1_to_10",
        "source_file_count_bucket": "1_to_10",
        "test_file_count_bucket": "none",
        "repository_shape": "application",
        "has_tests": False,
        "has_build_files": True,
        "has_dependency_manifests": True,
    }
    data.update(overrides)
    return AssessmentMetadataProjectionSource(**data)  # type: ignore[arg-type]


def _facade(*, allow: bool = True) -> DisabledTelemetryFacade:
    consent = allow_session_consent() if allow else deny_session_consent()
    return DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=consent,
            transport=CaptureTelemetryTransport(),
        )
    )


def test_e1_explicit_authorization_one_post() -> None:
    capture = CaptureAssessmentMetadataTransport()
    diag = emit_assessment_metadata_safely(
        source=_source(),
        telemetry=_facade(allow=True),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=capture,
        network_available=True,
    )
    assert diag.successes == 1
    assert len(capture.captured) == 1
    assert capture.captured[0]["schema_version"] == "1.1"
    assert capture.captured[0]["assessment_id"] == _AID


def test_e2_no_authorization_no_post() -> None:
    capture = CaptureAssessmentMetadataTransport()
    diag = emit_assessment_metadata_safely(
        source=_source(),
        telemetry=_facade(allow=True),
        policy=default_assessment_metadata_emission_policy(),
        transport=capture,
        network_available=True,
    )
    assert diag.skipped == 1
    assert diag.last_failure_category == "emission_disabled"
    assert capture.captured == []


def test_e3_post_success_assessment_unaffected() -> None:
    capture = CaptureAssessmentMetadataTransport()
    facade = _facade(allow=True)
    amd_diag = AssessmentMetadataEmissionDiagnostics()

    def primary() -> str:
        return "assessment-ok"

    result, isolation = run_assessment_with_telemetry_isolation(
        primary,
        telemetry=facade,
        assessment_metadata_policy=authorized_assessment_metadata_emission_policy(),
        assessment_metadata_transport=capture,
        assessment_metadata_diagnostics=amd_diag,
        network_available=True,
    )
    assert result == "assessment-ok"
    assert isolation.primary_result_preserved is True
    assert amd_diag.successes == 1
    assert len(capture.captured) == 1


@pytest.mark.parametrize(
    "status,category",
    [
        (400, "validation"),
        (422, "validation"),
        (401, "authorization"),
        (403, "authorization"),
        (429, "rate_limited"),
        (500, "server_error"),
    ],
)
def test_e4_to_e9_http_errors_unaffected(status: int, category: str) -> None:
    client = FakeTelemetryHttpClient(
        FakeTelemetryHttpResponse(status_code=status, body=b'{"error":"x"}')
    )
    transport = HttpAssessmentMetadataTransport(
        endpoint="https://example.test/api/v1/assessment-metadata",
        credential=TelemetryTransportCredential(bearer_token=_TOKEN),
        client=client,
        policy=authorized_assessment_metadata_emission_policy(),
    )
    facade = _facade(allow=True)

    def primary() -> dict[str, str]:
        return {"ok": "yes"}

    result, isolation = run_assessment_with_telemetry_isolation(
        primary,
        telemetry=facade,
        assessment_metadata_policy=authorized_assessment_metadata_emission_policy(),
        assessment_metadata_transport=transport,
        network_available=True,
    )
    assert result == {"ok": "yes"}
    assert isolation.primary_result_preserved is True
    assert len(client.calls) == 1  # no retry storm


def test_e4_timeout_unaffected() -> None:
    client = FakeTelemetryHttpClient(
        FakeTelemetryHttpResponse(status_code=0, raise_timeout=True)
    )
    transport = HttpAssessmentMetadataTransport(
        endpoint="https://example.test/api/v1/assessment-metadata",
        credential=TelemetryTransportCredential(bearer_token=_TOKEN),
        client=client,
        policy=authorized_assessment_metadata_emission_policy(),
    )
    diag = emit_assessment_metadata_safely(
        source=_source(),
        telemetry=_facade(allow=True),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=transport,
        network_available=True,
    )
    assert diag.failures == 1
    assert diag.last_failure_category == "timeout"
    assert len(client.calls) == 1


def test_e5_dns_network_error_unaffected() -> None:
    client = FakeTelemetryHttpClient(
        FakeTelemetryHttpResponse(status_code=0, raise_connection=True)
    )
    transport = HttpAssessmentMetadataTransport(
        endpoint="https://example.test/api/v1/assessment-metadata",
        credential=TelemetryTransportCredential(bearer_token=_TOKEN),
        client=client,
        policy=authorized_assessment_metadata_emission_policy(),
    )
    primary_ok = {"status": "ok"}

    def primary() -> dict[str, str]:
        return primary_ok

    result, _ = run_assessment_with_telemetry_isolation(
        primary,
        telemetry=_facade(allow=True),
        assessment_metadata_policy=authorized_assessment_metadata_emission_policy(),
        assessment_metadata_transport=transport,
        network_available=True,
    )
    assert result is primary_ok
    assert len(client.calls) == 1


def test_e10_malformed_response_unaffected() -> None:
    client = FakeTelemetryHttpClient(
        FakeTelemetryHttpResponse(status_code=202, body=b"not-json{{{")
    )
    transport = HttpAssessmentMetadataTransport(
        endpoint="https://example.test/api/v1/assessment-metadata",
        credential=TelemetryTransportCredential(bearer_token=_TOKEN),
        client=client,
        policy=authorized_assessment_metadata_emission_policy(),
    )
    diag = emit_assessment_metadata_safely(
        source=_source(),
        telemetry=_facade(allow=True),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=transport,
        network_available=True,
    )
    # Empty/non-json ack still treated as accepted when status 202 (body optional).
    assert diag.attempts == 1
    assert len(client.calls) == 1


def test_v1_consent_does_not_enable_amd() -> None:
    """Lifecycle telemetry permitted; assessment_metadata 1.1 NOT emitted."""

    lifecycle = CaptureTelemetryTransport()
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=lifecycle,
        )
    )
    amd = CaptureAssessmentMetadataTransport()

    def primary() -> str:
        return "ok"

    result, _ = run_assessment_with_telemetry_isolation(
        primary,
        telemetry=facade,
        # default amd policy: emission_enabled=False
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert result == "ok"
    assert len(lifecycle.captured) >= 1
    assert amd.captured == []


def test_offline_skips_network_send() -> None:
    capture = CaptureAssessmentMetadataTransport()
    diag = emit_assessment_metadata_safely(
        source=_source(),
        telemetry=_facade(allow=True),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=capture,
        network_available=False,
    )
    assert diag.skipped == 1
    assert diag.last_failure_category == "offline_mode"
    assert capture.captured == []


def test_failure_path_same_assessment_id(tmp_path: Path) -> None:
    capture = CaptureAssessmentMetadataTransport()
    aid = new_assessment_id()
    diag = AssessmentMetadataEmissionDiagnostics()

    def primary() -> None:
        raise ValueError("assessment_boom_path_must_not_leak")

    with pytest.raises(ValueError, match="assessment_boom"):
        run_assessment_with_telemetry_isolation(
            primary,
            telemetry=_facade(allow=True),
            assessment_metadata_policy=authorized_assessment_metadata_emission_policy(),
            assessment_metadata_transport=capture,
            assessment_metadata_diagnostics=diag,
            network_available=True,
        )
    # Isolation generates its own id; assert failed payload shape when we emit directly.
    emit_assessment_metadata_safely(
        failure=ValueError("x"),
        assessment_id=aid,
        telemetry=_facade(allow=True),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=capture,
        network_available=True,
        diagnostics=AssessmentMetadataEmissionDiagnostics(),
    )
    assert any(item.get("assessment_id") == aid for item in capture.captured)
    blob = json.dumps(capture.captured)
    assert "assessment_boom_path_must_not_leak" not in blob
    assert str(tmp_path) not in blob


def test_safe_logging_omits_bodies_and_canaries() -> None:
    diag = AssessmentMetadataEmissionDiagnostics()
    diag.record_failure("server_error")
    message = diag.safe_log_message()
    assert "assessment metadata upload failed" in message
    assert "server_error" in message
    assert "TEST_SECRET_DO_NOT_TRANSMIT" not in message
    assert "body" not in message.lower()
    stable = diag.to_stable_dict()
    assert "payload" not in stable
    assert "url" not in stable


def test_emission_authorized_requires_explicit_flag() -> None:
    policy = default_assessment_metadata_emission_policy()
    ok, reason = emission_authorized(
        policy, consent=allow_session_consent(), network_available=True
    )
    assert ok is False
    assert reason == "emission_disabled"
    ok2, _ = emission_authorized(
        authorized_assessment_metadata_emission_policy(),
        consent=allow_session_consent(),
        network_available=True,
    )
    assert ok2 is True


def test_http_transport_result_helper() -> None:
    result = AssessmentMetadataTransportResult(
        kind="sent", status_category="accepted", attempt_count=1
    )
    assert result.to_stable_dict()["kind"] == "sent"


def test_installation_id_reused_on_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "codestrata.telemetry.assessment_metadata.emitter.ensure_installation_id",
        lambda: (_INSTALL, False),
    )
    capture = CaptureAssessmentMetadataTransport()
    emit_assessment_metadata_safely(
        source=_source(installation_id=None),
        result=None,
        failure=None,
        assessment_id=_AID,
        telemetry=_facade(allow=True),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=capture,
        network_available=True,
    )
    # source already had None installation — rebuild path via failure uses ensure
    capture2 = CaptureAssessmentMetadataTransport()
    emit_assessment_metadata_safely(
        failure=RuntimeError("x"),
        assessment_id=_AID,
        telemetry=_facade(allow=True),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=capture2,
        network_available=True,
    )
    assert capture2.captured[0]["installation_id"] == _INSTALL
    assert capture2.captured[0]["assessment_id"] == _AID
