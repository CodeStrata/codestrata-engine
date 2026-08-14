"""Slice 20.11 — Engine privacy + cross-surface E2E (CLI / consent / amd)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.assessment_isolation import (
    run_assessment_with_telemetry_isolation,
)
from codestrata.telemetry.assessment_metadata.diagnostics import (
    AssessmentMetadataEmissionDiagnostics,
)
from codestrata.telemetry.assessment_metadata.emitter import emit_assessment_metadata_safely
from codestrata.telemetry.assessment_metadata.policy import (
    authorized_assessment_metadata_emission_policy,
)
from codestrata.telemetry.assessment_metadata.projector import project_assessment_metadata
from codestrata.telemetry.assessment_metadata.source import (
    build_failure_projection_source,
    finding_rows_from_artifact,
    new_assessment_id,
)
from codestrata.telemetry.assessment_metadata.transport import (
    CaptureAssessmentMetadataTransport,
    HttpAssessmentMetadataTransport,
)
from codestrata.telemetry.consent import allow_session_consent, deny_session_consent
from codestrata.telemetry.consent_scope import CommunityConsentState, resolve_consent_capabilities
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.event_identity import TelemetryTransportCredential
from codestrata.telemetry.identity import read_installation_id, write_installation_id
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.http_client import FakeTelemetryHttpClient, FakeTelemetryHttpResponse
from codestrata.telemetry.persisted_consent import (
    assessment_metadata_policy_for_session,
    decline_v2_upgrade,
    persist_disabled,
    persist_v2_yes,
)
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
)
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.service import reset_telemetry_singletons

from tests.telemetry.privacy_canaries import (
    FIXTURE_ROOT,
    MANDATORY_CANARIES,
    REPO_NAME,
    SECRET,
    assert_amd_1_1_allowlist,
    assert_no_canaries,
    assert_no_forbidden_fields,
    canary_findings_artifact,
    canary_rich_projection_source,
    canonical_json,
)

_INSTALL = "11111111-1111-4111-8111-111111111111"
_TOKEN = "cscc_v1_" + ("a" * 32)


def _legacy_v1(path: Path, *, upgrade_declined: bool = False) -> None:
    payload = {
        "schema_version": "1.0.0",
        "enabled": True,
        "decision_made": True,
        "decision_at": "2026-01-01T00:00:00Z",
        "installation_created_at": None,
        "installation_event_sent": False,
        "last_codestrata_version": None,
        "local_counters": {},
    }
    if upgrade_declined:
        payload["v2_upgrade_declined"] = True
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class _OkResult:
    duration_ms = 12.0
    ai_executed = False


class _FailingPrimary:
    def __call__(self) -> None:
        raise TimeoutError(
            f"Assess failed under {FIXTURE_ROOT} secret={SECRET} path leak"
        )


def _facade(*, allow: bool = True, life: CaptureTelemetryTransport | None = None):
    consent = allow_session_consent() if allow else deny_session_consent()
    return DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=consent,
            transport=life or CaptureTelemetryTransport(),
        )
    )


def _event_type(event: object) -> str:
    fields = getattr(event, "fields", None)
    if isinstance(fields, dict) and "event_type" in fields:
        return str(fields["event_type"])
    if isinstance(event, dict):
        return str(event.get("event_type") or "")
    stable = getattr(event, "to_stable_dict", None)
    if callable(stable):
        return str(stable().get("event_type") or "")
    return ""


def _status_json() -> dict[str, object]:
    runner = CliRunner()
    result = runner.invoke(app, ["telemetry", "status", "--json"])
    assert result.exit_code == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_e2e01_cli_v2_happy_path_lifecycle_and_amd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "AKIA_CANARY_DO_NOT_TRANSMIT")
    reset_telemetry_singletons()
    write_installation_id(_INSTALL)
    runner = CliRunner()
    assert runner.invoke(app, ["telemetry", "enable"]).exit_code == 0
    caps = resolve_consent_capabilities(path=home / "telemetry.json")
    assert caps.state is CommunityConsentState.V2_YES

    life = CaptureTelemetryTransport()
    amd = CaptureAssessmentMetadataTransport()
    policy = assessment_metadata_policy_for_session(
        path=home / "telemetry.json", transmission_authorized=True
    )
    assert policy.emission_enabled is True

    result, _ = run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(life=life),
        assessment_metadata_policy=policy,
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert result is not None
    invoked = [e for e in life.captured if _event_type(e) == "feature_invoked"]
    completed = [e for e in life.captured if _event_type(e) == "feature_completed"]
    assert len(invoked) >= 1
    assert len(completed) >= 1
    assert len(amd.captured) == 1
    payload = amd.captured[0]
    assert payload["schema_version"] == "1.1"
    assert payload["installation_id"] == _INSTALL
    assert payload.get("assessment_id")
    assert REPO_NAME not in str(payload["assessment_id"])
    assert "report_id" not in payload
    assert "report_url" not in payload
    assert "failure_category" not in payload["execution"]
    assert_amd_1_1_allowlist(payload)
    assert_no_forbidden_fields(payload)
    assert_no_canaries(payload)
    for event in life.captured:
        stable = event.to_stable_dict() if hasattr(event, "to_stable_dict") else event
        assert_no_canaries(stable, canaries=MANDATORY_CANARIES)
        blob = canonical_json(stable)
        assert "AKIA_CANARY_DO_NOT_TRANSMIT" not in blob
        assert "cscc_v1_SYNTHETIC_CREDENTIAL_CANARY_DO_NOT_TRANSMIT" not in blob


def test_e2e03_cli_yes_then_status_json_authorizes_amd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "enable"])
    status = _status_json()
    assert status["state"] == "v2_yes"
    assert status["assessment_metadata_allowed"] is True
    assert status["lifecycle_allowed"] is True
    assert "installation_id" not in status
    amd = CaptureAssessmentMetadataTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=home / "telemetry.json", transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert len(amd.captured) == 1


def test_e2e04_vscode_shaped_enable_cli_assess_sees_v2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    assert CliRunner().invoke(app, ["telemetry", "enable"]).exit_code == 0
    assert _status_json()["state"] == "v2_yes"
    amd = CaptureAssessmentMetadataTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=home / "telemetry.json", transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert len(amd.captured) == 1


def test_e2e05_cli_disable_overrides_stale_enabled_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "enable"])
    CliRunner().invoke(app, ["telemetry", "disable"])
    status = _status_json()
    assert status["state"] == "disabled"
    assert status["lifecycle_allowed"] is False
    assert status["assessment_metadata_allowed"] is False
    amd = CaptureAssessmentMetadataTransport()
    life = CaptureTelemetryTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(allow=False, life=life),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=home / "telemetry.json", transmission_authorized=False
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert life.captured == []
    assert amd.captured == []


def test_e2e06_vscode_shaped_disable_cli_assess_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    persist_v2_yes(path=home / "telemetry.json")
    CliRunner().invoke(app, ["telemetry", "disable"])
    assert _status_json()["state"] == "disabled"
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        quiet=True,
        json_output=True,
        telemetry_allow=True,
        preference_path=home / "telemetry.json",
    )
    assert facade.runtime.session.consent.transmission_authorized is False


def test_e2e07_v1_decline_upgrade_preserves_lifecycle_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    pref = home / "telemetry.json"
    _legacy_v1(pref)
    decline_v2_upgrade(path=pref)
    status = _status_json()
    assert status["state"] == "v1_yes"
    assert status["assessment_metadata_allowed"] is False
    assert status["lifecycle_allowed"] is True
    assert status["v2_upgrade_declined"] is True
    life = CaptureTelemetryTransport()
    amd = CaptureAssessmentMetadataTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(life=life),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=pref, transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert len(life.captured) >= 2
    assert amd.captured == []
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V1_YES


def test_e2e08_legacy_v1_no_silent_v2_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    pref = home / "telemetry.json"
    _legacy_v1(pref)
    life = CaptureTelemetryTransport()
    amd = CaptureAssessmentMetadataTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(life=life),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=pref, transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert len(life.captured) >= 2
    assert amd.captured == []
    after = json.loads(pref.read_text(encoding="utf-8"))
    assert "consent_scope" not in after
    assert after.get("enabled") is True
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V1_YES


def test_e2e09_disabled_hard_off_allow_cannot_override(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_disabled(path=pref)
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        quiet=True,
        json_output=True,
        telemetry_allow=True,
        preference_path=pref,
    )
    assert facade.runtime.session.consent.transmission_authorized is False
    amd = CaptureAssessmentMetadataTransport()
    life = CaptureTelemetryTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(allow=False, life=life),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=pref, transmission_authorized=False
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert life.captured == []
    assert amd.captured == []


def test_e2e10_undecided_noninteractive_no_prompt_no_collection(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        quiet=True,
        json_output=True,
        stdin_interactive=False,
        automation_detected=True,
        output_interactive=False,
        telemetry_allow=False,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert result.prompted is False
    assert facade.runtime.session.consent.transmission_authorized is False
    assert assessment_metadata_policy_for_session(
        path=pref, transmission_authorized=False
    ).emission_enabled is False


def test_e2e_full_payload_canary_and_allowlist() -> None:
    source = canary_rich_projection_source(
        assessment_id=new_assessment_id(), installation_id=_INSTALL
    )
    payload = project_assessment_metadata(source).to_stable_dict()
    assert_amd_1_1_allowlist(payload)
    assert_no_forbidden_fields(payload)
    assert_no_canaries(payload)
    rows = payload["finding_aggregates"]
    assert rows == sorted(
        rows, key=lambda r: (r["rule_id"], r["severity"], r["category"])
    )
    arch = [
        r
        for r in rows
        if r["rule_id"] == "architecture.layer-dependency"
        and r["severity"] == "high"
        and r["category"] == "architecture"
    ]
    assert len(arch) == 1 and arch[0]["count"] == 2
    sec_med = [
        r
        for r in rows
        if r["rule_id"] == "security.debug-enabled" and r["severity"] == "medium"
    ]
    sec_high = [
        r
        for r in rows
        if r["rule_id"] == "security.debug-enabled" and r["severity"] == "high"
    ]
    assert len(sec_med) == 1 and sec_med[0]["count"] == 1
    assert len(sec_high) == 1 and sec_high[0]["count"] == 1
    blob = canonical_json(rows)
    assert "PMD." not in blob
    assert "provider:" not in blob
    assert "https://" not in blob
    assert "/Users/" not in blob
    levels = {r["confidence_level"] for r in payload["head_confidence"]}
    assert levels == {"high", "moderate", "limited", "unavailable"}
    for row in payload["head_confidence"]:
        assert set(row.keys()) == {"confidence_level", "head"}


def test_e2e_findings_artifact_projection_strips_canaries() -> None:
    rows = finding_rows_from_artifact(canary_findings_artifact())
    assert rows
    source = replace(
        canary_rich_projection_source(
            assessment_id=new_assessment_id(), installation_id=_INSTALL
        ),
        findings=rows,
    )
    payload = project_assessment_metadata(source).to_stable_dict()
    assert_no_canaries(payload)
    assert_no_forbidden_fields(payload)


def test_e2e11_failure_path_privacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    persist_v2_yes(path=home / "telemetry.json")
    write_installation_id(_INSTALL)
    life = CaptureTelemetryTransport()
    amd = CaptureAssessmentMetadataTransport()
    with pytest.raises(TimeoutError):
        run_assessment_with_telemetry_isolation(
            _FailingPrimary(),
            telemetry=_facade(life=life),
            assessment_metadata_policy=assessment_metadata_policy_for_session(
                path=home / "telemetry.json", transmission_authorized=True
            ),
            assessment_metadata_transport=amd,
            network_available=True,
        )
    failed = [e for e in life.captured if _event_type(e) == "operation_failed"]
    assert failed
    assert len(amd.captured) == 1
    payload = amd.captured[0]
    assert payload["execution"]["result"] == "failed"
    assert payload["execution"]["failure_category"] in {
        "timeout",
        "unknown",
        "internal",
        "unavailable",
        "validation",
    }
    assert_no_canaries(payload)
    assert_no_forbidden_fields(payload)
    for event in life.captured:
        stable = event.to_stable_dict() if hasattr(event, "to_stable_dict") else event
        blob = canonical_json(stable)
        assert SECRET not in blob
        assert str(FIXTURE_ROOT) not in blob


@pytest.mark.parametrize(
    "response",
    [
        FakeTelemetryHttpResponse(status_code=422, body=b"{}"),
        FakeTelemetryHttpResponse(status_code=401, body=b"{}"),
        FakeTelemetryHttpResponse(status_code=403, body=b"{}"),
        FakeTelemetryHttpResponse(status_code=429, body=b"{}"),
        FakeTelemetryHttpResponse(status_code=500, body=b"{}"),
        FakeTelemetryHttpResponse(status_code=0, raise_timeout=True),
        FakeTelemetryHttpResponse(status_code=0, raise_connection=True),
    ],
)
def test_e2e12_cloud_amd_failures_do_not_break_local_assess(
    response: FakeTelemetryHttpResponse,
) -> None:
    client = FakeTelemetryHttpClient(response)
    transport = HttpAssessmentMetadataTransport(
        endpoint="https://community.test.invalid/api/v1/assessment-metadata",
        credential=TelemetryTransportCredential(bearer_token=_TOKEN),
        client=client,
        policy=authorized_assessment_metadata_emission_policy(),
    )
    diag = AssessmentMetadataEmissionDiagnostics()
    local_ok = {"report": True, "artifacts": ["a"]}

    result, isolation = run_assessment_with_telemetry_isolation(
        lambda: local_ok,
        telemetry=_facade(),
        assessment_metadata_policy=authorized_assessment_metadata_emission_policy(),
        assessment_metadata_transport=transport,
        assessment_metadata_diagnostics=diag,
        network_available=True,
    )
    assert result is local_ok
    assert isolation.primary_status == "success"
    assert isolation.primary_result_preserved is True
    msg = diag.safe_log_message()
    for canary in MANDATORY_CANARIES:
        assert canary not in msg
    assert _TOKEN not in msg
    assert "community.test.invalid" not in msg


def test_e2e13_offline_v2_no_amd_no_consent_downgrade(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    before = pref.read_text(encoding="utf-8")
    amd = CaptureAssessmentMetadataTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=pref, transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=False,
    )
    assert pref.read_text(encoding="utf-8") == before
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V2_YES
    assert amd.captured == []
    assert list(tmp_path.glob("**/*amd*")) == []
    assert list(tmp_path.glob("**/*queue*")) == []


def test_e2e14_15_16_report_independence_from_amd() -> None:
    from codestrata.community_cloud.report_publishing import (
        telemetry_eligible_for_publish,
    )
    from codestrata.telemetry.session import TelemetrySession

    assert telemetry_eligible_for_publish(None) is True
    assert (
        telemetry_eligible_for_publish(
            TelemetrySession(consent=deny_session_consent())
        )
        is True
    )
    payload = project_assessment_metadata(
        canary_rich_projection_source(
            assessment_id=new_assessment_id(), installation_id=_INSTALL
        )
    ).to_stable_dict()
    assert "report_id" not in payload
    assert "report_url" not in payload


def test_e2e18_installation_continuity_and_opaque_assessment_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    write_installation_id(_INSTALL)
    persist_v2_yes(path=home / "telemetry.json")
    amd = CaptureAssessmentMetadataTransport()
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=home / "telemetry.json", transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=_facade(),
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=home / "telemetry.json", transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert len(amd.captured) == 2
    assert amd.captured[0]["installation_id"] == _INSTALL
    assert amd.captured[1]["installation_id"] == _INSTALL
    assert amd.captured[0]["assessment_id"] != amd.captured[1]["assessment_id"]
    for payload in amd.captured:
        aid = payload["assessment_id"]
        assert "VERY_PRIVATE" not in aid
        assert "Acme" not in aid
        assert "/" not in aid
    persist_disabled(path=home / "telemetry.json")
    persist_v2_yes(path=home / "telemetry.json")
    assert read_installation_id() == _INSTALL


def test_schema_allowlist_snapshot_guard() -> None:
    payload = project_assessment_metadata(
        canary_rich_projection_source(
            assessment_id=new_assessment_id(), installation_id=_INSTALL
        )
    ).to_stable_dict()
    assert set(payload.keys()) == {
        "assessment",
        "assessment_id",
        "artifacts",
        "client",
        "event_id",
        "execution",
        "finding_aggregates",
        "head_confidence",
        "installation_id",
        "repository",
        "schema_version",
    }
    assert_amd_1_1_allowlist(payload)


def test_amd_request_has_no_client_timestamp_fields() -> None:
    payload = project_assessment_metadata(
        canary_rich_projection_source(
            assessment_id=new_assessment_id(), installation_id=_INSTALL
        )
    ).to_stable_dict()
    blob = canonical_json(payload)
    for token in ("occurred_at", "client_timestamp", "executed_at"):
        assert token not in blob


def test_failure_projection_source_excludes_exception_text() -> None:
    source = build_failure_projection_source(
        assessment_id=new_assessment_id(),
        installation_id=_INSTALL,
        failure_category="timeout",
        event_id="amd-fail-001",
        client_version="0.2.1",
        platform_name="darwin",
    )
    payload = project_assessment_metadata(source).to_stable_dict()
    assert_no_canaries(payload)
    assert payload["execution"]["failure_category"] == "timeout"


def test_canary_rich_emit_scans_outbound_request() -> None:
    """Canary-stuffed source → emit → captured request must stay clean."""

    amd = CaptureAssessmentMetadataTransport()
    source = canary_rich_projection_source(
        assessment_id=new_assessment_id(), installation_id=_INSTALL
    )
    emit_assessment_metadata_safely(
        source=source,
        telemetry=_facade(),
        policy=authorized_assessment_metadata_emission_policy(),
        transport=amd,
        network_available=True,
    )
    assert len(amd.captured) == 1
    assert_no_canaries(amd.captured[0])
    assert_no_forbidden_fields(amd.captured[0])
    assert_amd_1_1_allowlist(amd.captured[0])
