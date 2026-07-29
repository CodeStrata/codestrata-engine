"""Tests for safe .env loading."""

from __future__ import annotations

import os
from pathlib import Path

from codestrata.config.dotenv import apply_dotenv_file, load_dotenv


def test_apply_dotenv_does_not_override_existing(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CODESTRATA_TEST_TOKEN=from-file\n", encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_TEST_TOKEN", "from-shell")
    applied = apply_dotenv_file(env_file, override=False)
    assert applied == 0
    assert os.environ["CODESTRATA_TEST_TOKEN"] == "from-shell"


def test_apply_dotenv_sets_missing_keys(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CODESTRATA_TEST_NEW=value\n"
        "export CODESTRATA_TEST_EXPORT=exported\n"
        "# comment\n"
        "CODESTRATA_TEST_BAD=${shell}\n"
        'CODESTRATA_TEST_QUOTED="quoted value"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("CODESTRATA_TEST_NEW", raising=False)
    monkeypatch.delenv("CODESTRATA_TEST_EXPORT", raising=False)
    monkeypatch.delenv("CODESTRATA_TEST_QUOTED", raising=False)
    applied = apply_dotenv_file(env_file)
    assert applied == 3
    assert os.environ["CODESTRATA_TEST_NEW"] == "value"
    assert os.environ["CODESTRATA_TEST_EXPORT"] == "exported"
    assert os.environ["CODESTRATA_TEST_QUOTED"] == "quoted value"
    assert (
        "CODESTRATA_TEST_BAD" not in os.environ
        or os.environ.get("CODESTRATA_TEST_BAD") != "${shell}"
    )


def test_load_dotenv_walks_parents(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "project"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / ".env").write_text("CODESTRATA_TEST_WALK=1\n", encoding="utf-8")
    monkeypatch.delenv("CODESTRATA_TEST_WALK", raising=False)
    loaded = load_dotenv(start_directory=nested)
    assert loaded == root / ".env"
    assert os.environ["CODESTRATA_TEST_WALK"] == "1"
