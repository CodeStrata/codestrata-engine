"""Assessment isolation policy and lifecycle unit tests (Slice 9.12)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codestrata.telemetry.assessment_isolation import (
    run_assessment_with_telemetry_isolation,
)
from codestrata.telemetry.assessment_isolation_models import AssessmentPrimaryStatus
from codestrata.telemetry.assessment_isolation_policy import (
    COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_URN,
    CommunityTelemetryAssessmentIsolationPolicy,
    AssessmentIsolationPolicyError,
    default_assessment_isolation_policy,
)
from codestrata.telemetry.assessment_lifecycle import lifecycle_event_names
from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.http_client import FakeTelemetryHttpResponse
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.transport import TelemetryTransportResultKind
from tests.telemetry.transport_test_helpers import make_http_transport


def test_isolation_policy_defaults() -> None:
    policy = default_assessment_isolation_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_URN
    assert policy.primary_operation_authoritative is True
    assert policy.no_transport_activation_by_default is True
    payload = policy.to_stable_dict()
    assert list(payload.keys()) == sorted(payload.keys())
    assert "endpoint" not in payload


def test_isolation_policy_rejects_weakening() -> None:
    with pytest.raises(AssessmentIsolationPolicyError):
        CommunityTelemetryAssessmentIsolationPolicy(
            primary_operation_authoritative=False
        )


def test_lifecycle_event_names() -> None:
    assert lifecycle_event_names(success=True) == (
        "feature_invoked",
        "feature_completed",
    )
    assert lifecycle_event_names(success=False) == (
        "feature_invoked",
        "operation_failed",
    )


def test_success_survives_raising_transport() -> None:
    capture = CaptureTelemetryTransport(raise_on_send=True)
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=capture,
        )
    )

    def primary() -> str:
        return "ok"

    result, isolation = run_assessment_with_telemetry_isolation(
        primary, telemetry=facade, ai_enabled=False
    )
    assert result == "ok"
    assert isolation.primary_status == AssessmentPrimaryStatus.SUCCESS.value
    assert isolation.primary_result_preserved is True
    assert isolation.exit_code_preserved is True


def test_primary_failure_preserved_when_telemetry_succeeds() -> None:
    capture = CaptureTelemetryTransport()
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=capture,
        )
    )

    def primary() -> None:
        raise ValueError("assessment_boom")

    with pytest.raises(ValueError, match="assessment_boom"):
        run_assessment_with_telemetry_isolation(primary, telemetry=facade)
    assert len(capture.captured) >= 1  # invoked and/or failed recorded


def test_primary_failure_preserved_when_telemetry_also_fails() -> None:
    capture = CaptureTelemetryTransport(raise_on_send=True)
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=capture,
        )
    )

    def primary() -> None:
        raise RuntimeError("product_failure")

    with pytest.raises(RuntimeError, match="product_failure"):
        run_assessment_with_telemetry_isolation(primary, telemetry=facade)


def test_keyboard_interrupt_not_swallowed() -> None:
    facade = DisabledTelemetryFacade()

    def primary() -> None:
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_assessment_with_telemetry_isolation(primary, telemetry=facade)


def test_http_timeout_does_not_alter_success() -> None:
    transport, client = make_http_transport(
        responses=FakeTelemetryHttpResponse(status_code=0, raise_timeout=True)
    )
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=transport,
        )
    )
    result, isolation = run_assessment_with_telemetry_isolation(
        lambda: 7, telemetry=facade
    )
    assert result == 7
    assert isolation.primary_status == AssessmentPrimaryStatus.SUCCESS.value
    assert client.calls  # transport attempted under allow


def test_malformed_ack_does_not_alter_success() -> None:
    transport, _ = make_http_transport(
        responses=FakeTelemetryHttpResponse(status_code=202, body=b'{"status":"nope"}')
    )
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=transport,
        )
    )
    result, isolation = run_assessment_with_telemetry_isolation(
        lambda: {"ok": True}, telemetry=facade
    )
    assert result == {"ok": True}
    assert isolation.primary_result_preserved is True


def test_record_methods_raising_still_preserve_primary() -> None:
    facade = MagicMock(spec=DisabledTelemetryFacade)
    facade.record_assessment_started.side_effect = RuntimeError("start boom")
    facade.record_assessment_completed.side_effect = RuntimeError("end boom")

    result, isolation = run_assessment_with_telemetry_isolation(
        lambda: "done", telemetry=facade
    )
    assert result == "done"
    assert isolation.primary_status == AssessmentPrimaryStatus.SUCCESS.value
    assert isolation.telemetry_event_failures >= 1


def test_isolation_result_has_no_secrets() -> None:
    facade = DisabledTelemetryFacade()
    _, isolation = run_assessment_with_telemetry_isolation(
        lambda: "x", telemetry=facade, repo_root=Path("/tmp/secret-repo")
    )
    blob = isolation.to_stable_json()
    assert "/tmp/secret-repo" not in blob
    assert "endpoint" not in blob
    assert "cscc_v1_" not in blob
    assert list(isolation.to_stable_dict().keys()) == sorted(
        isolation.to_stable_dict().keys()
    )
