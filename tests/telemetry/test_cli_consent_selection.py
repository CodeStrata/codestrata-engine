"""CLI consent flag selection tests (Slice 9.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.cli_consent import (
    CliTelemetryConsentConflict,
    select_cli_telemetry_consent,
)
from codestrata.telemetry.cli_consent_diagnostics import diagnostics_from_cli_selection
from codestrata.telemetry.cli_consent_policy import TELEMETRY_FLAG_CONFLICT_MESSAGE
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource


def test_no_flags() -> None:
    selection = select_cli_telemetry_consent()
    assert selection.explicit_decision_present is False
    assert selection.prompt_required is True
    assert selection.consent is None
    assert selection.conflict is False
    assert selection.safe_status == "no_flags"


def test_allow_maps_to_cli_flag() -> None:
    selection = select_cli_telemetry_consent(allow=True)
    assert selection.consent is not None
    assert selection.consent.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert selection.consent.source is TelemetryDecisionSource.CLI_FLAG
    assert selection.consent.explicit is True
    assert selection.consent.transmission_authorized is True
    assert selection.consent.persisted is False
    assert selection.prompt_required is False


def test_deny_maps_to_cli_flag() -> None:
    selection = select_cli_telemetry_consent(deny=True)
    assert selection.consent is not None
    assert selection.consent.decision is TelemetryDecision.DENIED_FOR_SESSION
    assert selection.consent.source is TelemetryDecisionSource.CLI_FLAG
    assert selection.consent.transmission_authorized is False
    assert selection.prompt_required is False


def test_A_conflict_raises() -> None:
    with pytest.raises(CliTelemetryConsentConflict, match="cannot be used together"):
        select_cli_telemetry_consent(allow=True, deny=True)


def test_conflict_message_stable() -> None:
    assert TELEMETRY_FLAG_CONFLICT_MESSAGE == (
        "--telemetry-allow and --telemetry-deny cannot be used together."
    )


def test_conflict_without_raise() -> None:
    selection = select_cli_telemetry_consent(
        allow=True, deny=True, raise_on_conflict=False
    )
    assert selection.conflict is True
    assert selection.consent is None
    assert selection.prompt_required is False


def test_diagnostics_no_argv() -> None:
    selection = select_cli_telemetry_consent(allow=True)
    diag = diagnostics_from_cli_selection(selection)
    blob = diag.to_stable_json()
    for needle in ("argv", "--repo", "/Users/", "GITHUB", "endpoint"):
        assert needle not in blob
    assert diag.prompt_attempts == 0
    assert diag.prompt_skipped is True
    assert diag.decision_source == "cli_flag"
