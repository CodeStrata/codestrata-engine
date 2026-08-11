"""Session model tests (Slice 9.1)."""

from __future__ import annotations

import json

from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.session import new_disabled_session


def test_new_session_disabled_by_default() -> None:
    session = new_disabled_session()
    assert session.decision is TelemetryDecision.DISABLED_BY_DEFAULT
    assert session.decision_source is TelemetryDecisionSource.DEFAULT
    assert session.telemetry_enabled is False
    assert session.transport.transport_category == "unavailable"
    assert session.counters.events_seen == 0


def test_session_stable_dict_excludes_identity() -> None:
    payload = new_disabled_session().to_stable_dict()
    assert "installation_id" not in payload
    assert "username" not in payload
    assert "hostname" not in payload
    assert "repository" not in payload
    assert "cwd" not in payload
    assert "pid" not in payload
    blob = json.dumps(payload)
    assert '"installation_id"' not in blob
    assert "password" not in blob.lower()
    # Limitation code may mention installation id policy; that is not an ID value.
    assert "no_installation_id_in_runtime" in payload["limitation_codes"]


def test_session_does_not_read_saved_consent(monkeypatch, tmp_path) -> None:
    prefs = tmp_path / "telemetry.json"
    prefs.write_text('{"enabled": true}', encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    session = new_disabled_session()
    assert session.decision is TelemetryDecision.DISABLED_BY_DEFAULT
    assert session.telemetry_enabled is False
