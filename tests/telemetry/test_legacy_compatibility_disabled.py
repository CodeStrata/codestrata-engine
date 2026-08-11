"""Legacy compatibility under disabled product facade."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.service import TelemetryService, get_telemetry_service


def test_facade_does_not_construct_active_legacy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path))
    with patch.object(TelemetryService, "__init__", wraps=TelemetryService.__init__) as init:
        facade = get_telemetry_service()
        facade.record_report_opened()
        facade.record_version_check()
        # Product path must not construct TelemetryService.
        assert init.call_count == 0


def test_facade_rejects_repo_path_sensitive_mapping() -> None:
    facade = DisabledTelemetryFacade()
    # repo_root ignored; no scan / no path in diagnostics
    facade.record_assessment_started(
        ai_enabled=False,
        domains=["security"],
        repo_root=Path("/tmp/secret-repo"),
    )
    blob = facade.runtime.diagnostics().to_stable_json()
    assert "secret-repo" not in blob
    assert "/tmp" not in blob


def test_N_O_facade_emit_drops_arbitrary_kwargs() -> None:
    facade = DisabledTelemetryFacade()
    result = facade.emit(
        "assessment_started",
        repository_name="acme",
        source_code="print(1)",
        path="/etc/passwd",
    )
    assert result is None
    assert "repository" not in facade.status()
