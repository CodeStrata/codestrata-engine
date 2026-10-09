"""E13.2 CLI local export-preview: payload construction, not server readiness."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.domain.contracts.serialization import PLACEHOLDER_DIGEST, digest_canonical
from codestrata.telemetry.export_models import EXPORT_NOTICE
from codestrata.telemetry.export_policy import EVIDENCE_EXPORT_SCHEMA, GRAPH_EXPORT_SCHEMA
from codestrata.telemetry.service import reset_telemetry_singletons


def test_cli_export_preview_evidence_is_local_only() -> None:
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "export-preview", "--channel", "evidence"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == EVIDENCE_EXPORT_SCHEMA
    assert payload["category"] == "evidence"
    assert payload["notice"] == EXPORT_NOTICE
    assert payload["digest"] == digest_canonical(
        {
            "artifact_digest": payload["artifact_digest"],
            "category": "evidence",
            "schema": EVIDENCE_EXPORT_SCHEMA,
            "schema_version": payload["schema_version"],
        }
    )
    assert payload["artifact_digest"] == PLACEHOLDER_DIGEST
    assert payload["transmission_performed"] is False
    assert payload["server_readiness"] == "not_ready"
    assert "findings" not in payload
    assert "snippet" not in payload
    assert "repository_name" not in payload
    assert result.stderr == ""


def test_cli_export_preview_graph_and_digest_option() -> None:
    digest = "a" * 64
    result = CliRunner().invoke(
        app,
        ["telemetry", "export-preview", "--channel", "graph", "--digest", digest],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == GRAPH_EXPORT_SCHEMA
    assert payload["category"] == "graph"
    assert payload["artifact_digest"] == digest
    assert payload["transmission_performed"] is False
    assert payload["server_readiness"] == "not_ready"


def test_cli_export_preview_invalid_channel_and_digest() -> None:
    bad_channel = CliRunner().invoke(app, ["telemetry", "export-preview", "--channel", "lake"])
    assert bad_channel.exit_code == 2
    assert "unsupported channel" in (bad_channel.stderr or bad_channel.stdout).lower()

    bad_digest = CliRunner().invoke(
        app,
        ["telemetry", "export-preview", "--channel", "evidence", "--digest", "nope"],
    )
    assert bad_digest.exit_code == 2
    assert "Invalid export-preview" in (bad_digest.stderr or bad_digest.stdout)


def test_cli_export_preview_does_not_write_home(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "export-preview", "--channel", "evidence"])
    assert result.exit_code == 0
    assert list(home.iterdir()) == []
