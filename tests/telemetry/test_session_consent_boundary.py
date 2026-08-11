"""Boundary negatives for session consent (Slice 9.3)."""

from __future__ import annotations

import ast
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.service import reset_telemetry_singletons


TELEMETRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


def test_F_allowed_does_not_generate_installation_id(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    runtime = create_session_telemetry_runtime(consent=allow_session_consent())
    runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert list(home.iterdir()) == []
    diagnostics = runtime.diagnostics().to_stable_dict()
    assert "installation_id" not in diagnostics
    assert '"installation_id"' not in runtime.diagnostics().to_stable_json()
    # Limitation codes may mention identity policy; that is not an ID value.
    assert "no_installation_identity_required" in diagnostics["limitation_codes"]
    assert diagnostics["persisted"] is False
    assert diagnostics["prior_consent_reused"] is False


def test_X_cli_help_includes_preview_without_assess_flags() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["telemetry", "--help"])
    assert result.exit_code == 0
    for name in ("status", "preview", "enable", "disable", "reset", "show"):
        assert name in result.stdout
    assert "--telemetry-allow" not in result.stdout
    assert "--telemetry-deny" not in result.stdout
    assert "Commands" in result.stdout


def test_Y_no_platform_datalake_imports() -> None:
    forbidden = ("codestrata_platform", "codestrata_platform.community_cloud","community_cloud_api", "boto3", "fastapi", "data_lake")
    for path in TELEMETRY_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for needle in forbidden:
                    assert needle not in (name or ""), f"{path}: {name}"


def test_W_module_singleton_reset_does_not_retain_consent() -> None:
    from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
    from codestrata.telemetry.service import get_telemetry_service

    reset_telemetry_singletons()
    facade = DisabledTelemetryFacade(
        runtime=create_session_telemetry_runtime(consent=allow_session_consent())
    )
    assert facade.is_enabled() is True
    # Product singleton is independent and remains disabled.
    reset_telemetry_singletons()
    assert get_telemetry_service().is_enabled() is False
