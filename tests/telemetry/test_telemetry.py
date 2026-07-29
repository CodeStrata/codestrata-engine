"""Phase 14.3 anonymous telemetry tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.telemetry.bands import (
    duration_band,
    repository_size_band,
    scan_anonymous_repo_stats,
)
from codestrata.telemetry.constants import SCHEMA_VERSION, EventName
from codestrata.telemetry.identity import generate_installation_id
from codestrata.telemetry.queue import queue_depth
from codestrata.telemetry.service import TelemetryService
from codestrata.telemetry.validate import build_event_payload, validate_payload


@pytest.fixture()
def telemetry_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "codestrata-home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.delenv("CODESTRATA_TELEMETRY", raising=False)
    monkeypatch.delenv("CODESTRATA_TELEMETRY_ENDPOINT", raising=False)
    return home


def test_installation_id_is_uuid_v4_and_not_personal(telemetry_home: Path) -> None:
    service = TelemetryService(home=telemetry_home)
    first, created = service.ensure_identity()
    assert created is True
    parsed = uuid.UUID(first)
    assert parsed.version == 4
    # Must not embed obvious personal/host tokens.
    lowered = first.lower()
    for needle in ("satish", "local", "mac", "@", "/Users/", "hostname"):
        assert needle not in lowered
    second, created_again = service.ensure_identity()
    assert created_again is False
    assert second == first


def test_telemetry_disabled_by_default(telemetry_home: Path) -> None:
    service = TelemetryService(home=telemetry_home)
    service.ensure_identity()
    assert service.is_enabled() is False
    assert service.decision_made() is False
    assert service.emit(EventName.ASSESSMENT_STARTED, command="assess") is None
    assert queue_depth(path=telemetry_home / "telemetry-queue.jsonl") == 0


def test_enable_disable_reset_and_show(telemetry_home: Path) -> None:
    service = TelemetryService(home=telemetry_home)
    with patch("codestrata.telemetry.service.send_payload", return_value=False):
        status = service.enable()
        assert status["enabled"] is True
        assert service.is_enabled() is True
        sample = service.show_sample_payload()
        assert sample["schema_version"] == SCHEMA_VERSION
        assert sample["event"] == EventName.ASSESSMENT_COMPLETED
        assert "repository_name" not in sample
        assert "/" not in "".join(sample.get("language_categories") or [])
        depth_after_enable = queue_depth(path=telemetry_home / "telemetry-queue.jsonl")
        assert depth_after_enable >= 1

        service.disable()
        assert service.is_enabled() is False

        old_id = (telemetry_home / "installation_id").read_text(encoding="utf-8").strip()
        reset = service.reset()
        assert reset["enabled"] is False
        assert reset["decision_made"] is False
        assert reset["installation_id"] != old_id
        assert queue_depth(path=telemetry_home / "telemetry-queue.jsonl") == 0


def test_payload_validation_rejects_forbidden_keys(telemetry_home: Path) -> None:
    service = TelemetryService(home=telemetry_home)
    installation_id, _ = service.ensure_identity()
    payload = build_event_payload(
        installation_id=installation_id,
        event=EventName.ASSESSMENT_COMPLETED,
        command="assess",
        success=True,
    )
    validate_payload(payload)
    bad = dict(payload)
    bad["repository_name"] = "secret-repo"
    with pytest.raises(ValueError, match="disallowed"):
        validate_payload(bad)


def test_payload_redaction_display_roundtrip(telemetry_home: Path) -> None:
    service = TelemetryService(home=telemetry_home)
    with patch("codestrata.telemetry.service.send_payload", return_value=False):
        service.enable()
        shown = service.show_sample_payload()
    dumped = json.dumps(shown)
    assert "AKIA" not in dumped
    assert "password" not in dumped.lower()


def test_queue_and_retry(telemetry_home: Path) -> None:
    service = TelemetryService(home=telemetry_home)
    with patch("codestrata.telemetry.service.send_payload", return_value=False):
        service.enable()
        service.emit(EventName.ASSESSMENT_STARTED, command="assess", ai_enabled=False)
        assert queue_depth(path=telemetry_home / "telemetry-queue.jsonl") >= 1

    with patch("codestrata.telemetry.service.send_payload", return_value=True):
        sent = service.flush_queue()
        assert sent >= 1
        assert queue_depth(path=telemetry_home / "telemetry-queue.jsonl") == 0


def test_size_and_duration_bands() -> None:
    assert repository_size_band(0) == "0-100"
    assert repository_size_band(100) == "0-100"
    assert repository_size_band(101) == "101-500"
    assert repository_size_band(10001) == "10000+"
    assert duration_band(1000) == "0-5s"
    assert duration_band(10_000) == "5-30s"
    assert duration_band(1_000_000) == "15m+"


def test_anonymous_repo_stats_have_no_paths(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "App.java").write_text("class App {}\n", encoding="utf-8")
    count, categories = scan_anonymous_repo_stats(tmp_path)
    assert count == 2
    assert categories == ["java", "python"]


def test_generate_installation_id_unique() -> None:
    a = generate_installation_id()
    b = generate_installation_id()
    assert a != b
    assert uuid.UUID(a).version == 4


def test_env_force_disable(telemetry_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = TelemetryService(home=telemetry_home)
    service.enable()
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "0")
    assert service.is_enabled() is False


def test_schema_file_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    schema = (
        root
        / "schemas"
        / "telemetry"
        / "codestrata.io"
        / "v1.0"
        / "TelemetryEvent.json"
    )
    assert schema.is_file()
    data = json.loads(schema.read_text(encoding="utf-8"))
    assert data["properties"]["schema_version"]["const"] == "1.0.0"
