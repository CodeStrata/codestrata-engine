"""SV.3 artifact classification tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.cli.init_cmd import write_minimal_config
from verification.cli_initialization.artifacts import (
    classify_artifacts,
    forbidden_present,
    required_missing,
)
from verification.cli_initialization.workspace import create_minimal_repository


def test_classify_required_config(tmp_path: Path) -> None:
    repo = create_minimal_repository(tmp_path)
    pre = {p.relative_to(repo).as_posix() for p in repo.rglob("*") if p.is_file()}
    write_minimal_config(repo / "codestrata.toml")
    classes = classify_artifacts(repo, pre_existing=pre)
    assert classes.get("codestrata.toml") == "required"
    assert required_missing(classes) == []
    assert forbidden_present(classes) == []
