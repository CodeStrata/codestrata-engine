"""Slice 20.9 — CLI consent-v2 state, prompts, flags, and amd authorization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.assessment_isolation import (
    run_assessment_with_telemetry_isolation,
)
from codestrata.telemetry.assessment_metadata.policy import (
    default_assessment_metadata_emission_policy,
)
from codestrata.telemetry.assessment_metadata.transport import (
    CaptureAssessmentMetadataTransport,
)
from codestrata.telemetry.consent_scope import (
    CommunityConsentState,
    resolve_consent_capabilities,
)
from codestrata.telemetry.identity import (
    ensure_installation_id,
    read_installation_id,
    write_installation_id,
)
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.interactive_consent import (
    PROMPT_INTRO,
    PROMPT_QUESTION,
    UPGRADE_INTRO,
    UPGRADE_QUESTION,
    run_interactive_consent_prompt,
)
from codestrata.telemetry.persisted_consent import (
    assessment_metadata_policy_for_session,
    consent_capabilities,
    decline_v2_upgrade,
    format_consent_status,
    persist_disabled,
    persist_v1_yes,
    persist_v2_yes,
)
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
)
from codestrata.telemetry.service import reset_telemetry_singletons


def _legacy_v1_fixture(path: Path, *, upgrade_declined: bool = False) -> None:
    """Production-shaped v1 preference: enabled + decision_made, no consent_scope."""

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


def _assert_prompt_semantics(blob: str) -> None:
    text = blob.lower()
    assert "improve codestrata" in text
    assert "anonymous usage" in text
    assert "assessment insights" in text
    assert "source code" in text and "local" in text
    assert "repository identity" in text and "local" in text
    assert "publish" in text and "report" in text
    assert "score" not in text


# --- Capability / persistence -------------------------------------------------


def test_missing_preference_is_undecided(tmp_path: Path) -> None:
    caps = resolve_consent_capabilities(path=tmp_path / "missing.json")
    assert caps.state is CommunityConsentState.UNDECIDED
    assert caps.lifecycle_allowed is False
    assert caps.assessment_metadata_allowed is False


def test_legacy_v1_without_consent_scope(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    _legacy_v1_fixture(pref)
    caps = resolve_consent_capabilities(path=pref)
    assert caps.state is CommunityConsentState.V1_YES
    assert caps.lifecycle_allowed is True
    assert caps.assessment_metadata_allowed is False
    assert caps.should_prompt_v2_upgrade is True


def test_v2_yes_and_disabled(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    caps = resolve_consent_capabilities(path=pref)
    assert caps.state is CommunityConsentState.V2_YES
    assert caps.assessment_metadata_allowed is True
    persist_disabled(path=pref)
    caps = resolve_consent_capabilities(path=pref)
    assert caps.state is CommunityConsentState.DISABLED
    assert caps.lifecycle_allowed is False
    assert caps.assessment_metadata_allowed is False


def test_malformed_and_unsupported_scope_fail_safe(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    assert resolve_consent_capabilities(path=bad).state is CommunityConsentState.UNDECIDED

    pref = tmp_path / "telemetry.json"
    pref.write_text(
        json.dumps(
            {
                "enabled": True,
                "decision_made": True,
                "consent_scope": 99,
                "schema_version": "1.0.0",
            }
        ),
        encoding="utf-8",
    )
    caps = resolve_consent_capabilities(path=pref)
    assert caps.state is CommunityConsentState.UNDECIDED
    assert caps.assessment_metadata_allowed is False


def test_truncated_preference_fail_safe(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    pref.write_text("", encoding="utf-8")
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.UNDECIDED


# --- C1–C12 interactive / durable cases --------------------------------------


def test_c1_fresh_yes_v2(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    echoes: list[str] = []
    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        input_func=lambda _p: "y",
        echo_func=echoes.append,
        preference_path=pref,
    )
    assert result.consent.transmission_authorized is True
    caps = resolve_consent_capabilities(path=pref)
    assert caps.state is CommunityConsentState.V2_YES
    _assert_prompt_semantics("\n".join(echoes) + PROMPT_INTRO + PROMPT_QUESTION)


def test_c2_fresh_no_disabled(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        input_func=lambda _p: "n",
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert result.consent.transmission_authorized is False
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.DISABLED


def test_c3_fresh_invalid_and_eof_undecided(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    invalid = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        input_func=lambda _p: "maybe",
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert invalid.consent.transmission_authorized is False
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.UNDECIDED

    def _eof(_p: str) -> str:
        raise EOFError

    eof = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        input_func=_eof,
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert eof.consent.transmission_authorized is False
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.UNDECIDED


def test_c4_v1_upgrade_yes(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    _legacy_v1_fixture(pref)
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        preference_path=pref,
        input_func=lambda _p: "y",
        echo_func=lambda _m: None,
    )
    assert result.prompted is True
    assert "upgrade" in result.safe_outcome
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V2_YES
    assert facade.runtime.session.consent.transmission_authorized is True
    assert consent_capabilities(path=pref).assessment_metadata_allowed is True


def test_c5_v1_upgrade_decline_keeps_v1_no_nag(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    _legacy_v1_fixture(pref)
    _, first = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        preference_path=pref,
        input_func=lambda _p: "n",
        echo_func=lambda _m: None,
    )
    assert first.safe_outcome == "upgrade_declined"
    caps = resolve_consent_capabilities(path=pref)
    assert caps.state is CommunityConsentState.V1_YES
    assert caps.lifecycle_allowed is True
    assert caps.assessment_metadata_allowed is False
    assert caps.v2_upgrade_declined is True

    _, second = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no nag")),
    )
    assert second.prompted is False
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V1_YES


def test_c6_v1_no_decision_yet_still_lifecycle(tmp_path: Path) -> None:
    """Before upgrade answer, V1 lifecycle remains allowed and amd stays off."""

    pref = tmp_path / "telemetry.json"
    _legacy_v1_fixture(pref)
    caps = resolve_consent_capabilities(path=pref)
    assert caps.lifecycle_allowed is True
    assert caps.assessment_metadata_allowed is False
    assert caps.should_prompt_v2_upgrade is True


def test_c7_existing_v2(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    _, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=True,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert result.prompted is False
    assert resolve_consent_capabilities(path=pref).assessment_metadata_allowed is True


def test_c8_existing_disabled(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_disabled(path=pref)
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=True,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert result.prompted is False
    assert facade.runtime.session.consent.transmission_authorized is False


def test_c9_v2_revoke(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    persist_disabled(path=pref)
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_allow=True,
        preference_path=pref,
    )
    assert facade.runtime.session.consent.transmission_authorized is False
    policy = assessment_metadata_policy_for_session(
        path=pref, transmission_authorized=False
    )
    assert policy.emission_enabled is False


def test_c10_home_deleted_undecided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    persist_v2_yes()
    for child in home.iterdir():
        child.unlink()
    home.rmdir()
    caps = resolve_consent_capabilities()
    assert caps.state is CommunityConsentState.UNDECIDED


def test_c11_c12_corrupt_and_legacy(tmp_path: Path) -> None:
    corrupt = tmp_path / "c.json"
    corrupt.write_text('{"enabled": true', encoding="utf-8")
    assert resolve_consent_capabilities(path=corrupt).state is CommunityConsentState.UNDECIDED
    legacy = tmp_path / "l.json"
    _legacy_v1_fixture(legacy)
    assert resolve_consent_capabilities(path=legacy).state is CommunityConsentState.V1_YES


# --- Non-interactive × allow matrix ------------------------------------------


@pytest.mark.parametrize(
    ("setup", "interactive", "allow", "lifecycle", "amd"),
    [
        ("none", False, False, False, False),
        ("none", False, True, False, False),
        ("none", True, True, False, False),
        ("v1", False, False, True, False),
        ("v1", False, True, True, False),
        ("v2", False, False, True, True),
        ("v2", False, True, True, True),
        ("v2", True, False, True, True),
        ("disabled", False, False, False, False),
        ("disabled", False, True, False, False),
        ("disabled", True, True, False, False),
    ],
)
def test_noninteractive_allow_matrix(
    tmp_path: Path,
    setup: str,
    interactive: bool,
    allow: bool,
    lifecycle: bool,
    amd: bool,
) -> None:
    pref = tmp_path / "telemetry.json"
    if setup == "v1":
        _legacy_v1_fixture(pref, upgrade_declined=True)
    elif setup == "v2":
        persist_v2_yes(path=pref)
    elif setup == "disabled":
        persist_disabled(path=pref)

    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        quiet=not interactive,
        json_output=not interactive,
        stdin_interactive=interactive,
        automation_detected=not interactive,
        output_interactive=interactive,
        telemetry_allow=allow,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert facade.runtime.session.consent.transmission_authorized is lifecycle
    assert result.prompted is False
    policy = assessment_metadata_policy_for_session(
        path=pref,
        transmission_authorized=lifecycle,
    )
    assert policy.emission_enabled is amd


# --- Commands / status / identity --------------------------------------------


def test_telemetry_commands_enable_disable_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    runner = CliRunner()

    status = runner.invoke(app, ["telemetry", "status"])
    assert status.exit_code == 0
    assert "Not configured" in status.stdout

    en = runner.invoke(app, ["telemetry", "enable"])
    assert en.exit_code == 0
    assert "v2" in en.stdout.lower()
    caps = resolve_consent_capabilities(path=home / "telemetry.json")
    assert caps.state is CommunityConsentState.V2_YES

    en2 = runner.invoke(app, ["telemetry", "enable"])
    assert en2.exit_code == 0
    assert resolve_consent_capabilities(path=home / "telemetry.json").state is (
        CommunityConsentState.V2_YES
    )

    st = runner.invoke(app, ["telemetry", "status"])
    assert "Enabled (v2" in st.stdout
    assert "Assessment metadata 1.1: allowed" in st.stdout

    dis = runner.invoke(app, ["telemetry", "disable"])
    assert dis.exit_code == 0
    dis2 = runner.invoke(app, ["telemetry", "disable"])
    assert dis2.exit_code == 0
    assert resolve_consent_capabilities(path=home / "telemetry.json").state is (
        CommunityConsentState.DISABLED
    )
    assert "Disabled" in runner.invoke(app, ["telemetry", "status"]).stdout


def test_legacy_status_label(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    _legacy_v1_fixture(pref)
    text = format_consent_status(path=pref)
    assert "legacy v1" in text.lower()
    assert "lifecycle" in text.lower()
    assert "Assessment metadata 1.1: off" in text


def test_installation_id_continuity_across_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    iid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    write_installation_id(iid)
    _legacy_v1_fixture(home / "telemetry.json")
    persist_v2_yes(path=home / "telemetry.json")
    assert read_installation_id() == iid
    persist_disabled(path=home / "telemetry.json")
    persist_v2_yes(path=home / "telemetry.json")
    assert read_installation_id() == iid
    ensure_installation_id()
    assert read_installation_id() == iid


# --- Successful assess E2E / revoke / offline / report independence ----------


class _OkResult:
    duration_ms = 12.0
    ai_executed = False


def test_successful_assess_e2e_v2_emits_lifecycle_and_amd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    pref = home / "telemetry.json"
    persist_v2_yes(path=pref)
    iid = "11111111-1111-4111-8111-111111111111"
    write_installation_id(iid)

    from codestrata.telemetry.consent import allow_session_consent
    from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
    from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime

    life = CaptureTelemetryTransport()
    amd = CaptureAssessmentMetadataTransport()
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=life,
        )
    )
    policy = assessment_metadata_policy_for_session(
        path=pref, transmission_authorized=True
    )
    assert policy.emission_enabled is True

    result, _ = run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=facade,
        assessment_metadata_policy=policy,
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert result is not None
    assert len(life.captured) >= 2  # invoked + completed
    assert len(amd.captured) == 1
    payload = amd.captured[0]
    assert payload["schema_version"] == "1.1"
    assert payload["installation_id"] == iid
    assert "report_id" not in payload
    assert "report_url" not in payload
    assert payload.get("assessment_id")


def test_legacy_v1_e2e_lifecycle_only_no_amd(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    _legacy_v1_fixture(pref, upgrade_declined=True)
    life = CaptureTelemetryTransport()
    amd = CaptureAssessmentMetadataTransport()
    from codestrata.telemetry.consent import allow_session_consent
    from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
    from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime

    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=life,
        )
    )
    policy = assessment_metadata_policy_for_session(
        path=pref, transmission_authorized=True
    )
    assert policy.emission_enabled is False
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=facade,
        assessment_metadata_policy=policy,
        assessment_metadata_transport=amd,
        network_available=True,
    )
    assert len(life.captured) >= 2
    assert amd.captured == []


def test_revoke_blocks_allow_flag(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    persist_disabled(path=pref)
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_allow=True,
        preference_path=pref,
    )
    assert facade.runtime.session.consent.transmission_authorized is False
    assert assessment_metadata_policy_for_session(
        path=pref, transmission_authorized=False
    ).emission_enabled is False


def test_offline_v2_keeps_consent_skips_amd_network(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    before = pref.read_text(encoding="utf-8")
    amd = CaptureAssessmentMetadataTransport()
    from codestrata.telemetry.consent import allow_session_consent
    from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
    from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime

    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(
            consent=allow_session_consent(),
            transport=CaptureTelemetryTransport(),
        )
    )
    run_assessment_with_telemetry_isolation(
        lambda: _OkResult(),
        telemetry=facade,
        assessment_metadata_policy=assessment_metadata_policy_for_session(
            path=pref, transmission_authorized=True
        ),
        assessment_metadata_transport=amd,
        network_available=False,
    )
    assert pref.read_text(encoding="utf-8") == before
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V2_YES
    # Offline: emitter must not POST (capture stays empty when network_available=False).
    assert amd.captured == []


def test_report_publish_independence_from_consent() -> None:
    from codestrata.community_cloud.report_publishing import (
        telemetry_eligible_for_publish,
    )
    from codestrata.telemetry.consent import deny_session_consent
    from codestrata.telemetry.session import TelemetrySession

    assert telemetry_eligible_for_publish(None) is True
    assert (
        telemetry_eligible_for_publish(
            TelemetrySession(consent=deny_session_consent())
        )
        is True
    )
    # Default amd policy remains off without V2.
    assert default_assessment_metadata_emission_policy().emission_enabled is False


def test_upgrade_copy_semantics() -> None:
    blob = (UPGRADE_INTRO + UPGRADE_QUESTION).lower()
    assert "assessment insights" in blob
    assert "source code" in blob or "repository identity" in blob
    assert "publish" in blob
    assert decline_v2_upgrade  # exported helper used by prompt path
