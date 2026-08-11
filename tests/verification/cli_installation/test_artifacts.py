"""SV.2 environment scrubbing and artifact validation tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.cli.init_cmd import write_minimal_config
from verification.cli_installation.artifacts import validate_init_artifacts
from verification.cli_installation.environment import scrub_environ


def test_scrub_environ_removes_pythonpath_and_secrets() -> None:
    cleaned = scrub_environ(
        {
            "PATH": "/usr/bin",
            "PYTHONPATH": "/evil/src",
            "PYTHONHOME": "/evil",
            "AWS_SECRET_ACCESS_KEY": "x",
            "OPENAI_API_KEY": "y",
            "HOME": "/tmp/home",
        }
    )
    assert "PYTHONPATH" not in cleaned
    assert "PYTHONHOME" not in cleaned
    assert "AWS_SECRET_ACCESS_KEY" not in cleaned
    assert "OPENAI_API_KEY" not in cleaned
    assert cleaned["PATH"] == "/usr/bin"
    assert cleaned["HOME"] == "/tmp/home"


def test_validate_init_artifacts(tmp_path: Path) -> None:
    write_minimal_config(tmp_path / "codestrata.toml")
    ok, detail, evidence = validate_init_artifacts(tmp_path)
    assert ok is True, detail
    assert evidence["workspace_dir_exists"] is False
    assert evidence["knowledge_dir_exists"] is False


def test_validate_init_artifacts_rejects_missing_config(tmp_path: Path) -> None:
    ok, detail, _ = validate_init_artifacts(tmp_path)
    assert ok is False
    assert "not created" in detail
