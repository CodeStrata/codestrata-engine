"""SV.3 scenario evaluator / validation unit tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.cli.init_cmd import write_minimal_config
from verification.cli_initialization.validation import validate_generated_config
from verification.cli_initialization.workspace import create_minimal_repository


def test_validate_generated_config_defaults(tmp_path: Path) -> None:
    create_minimal_repository(tmp_path)
    write_minimal_config(tmp_path / "codestrata.toml")
    ok, failures, evidence = validate_generated_config(tmp_path / "codestrata.toml")
    assert ok is True, failures
    assert evidence["telemetry_section_present"] is False
    assert evidence["ai_provider"] == "bedrock"


def test_validate_rejects_absolute_path(tmp_path: Path) -> None:
    cfg = tmp_path / "codestrata.toml"
    cfg.write_text(
        '[repository]\npath = "/Users/someone/project"\nprofile = "community"\n',
        encoding="utf-8",
    )
    ok, failures, _ = validate_generated_config(cfg)
    assert ok is False
    assert any("absolute" in item or "path" in item for item in failures)
