"""SV.3 workspace fixture tests."""

from __future__ import annotations

from pathlib import Path

from verification.cli_initialization.workspace import (
    compare_snapshots,
    create_minimal_repository,
    create_space_path_repository,
    ensure_no_codestrata_config,
    snapshot_workspace,
)


def test_minimal_repository_and_integrity(tmp_path: Path) -> None:
    repo = create_minimal_repository(tmp_path / "repo")
    assert ensure_no_codestrata_config(repo)
    before = snapshot_workspace(repo)
    (repo / "codestrata.toml").write_text("x\n", encoding="utf-8")
    after = snapshot_workspace(repo)
    ok, failures = compare_snapshots(before, after, allowed_new={"codestrata.toml"})
    assert ok is True
    assert failures == []


def test_space_path_repository(tmp_path: Path) -> None:
    repo = create_space_path_repository(tmp_path)
    assert " " in repo.name
    assert (repo / "src" / "hello.py").is_file()
