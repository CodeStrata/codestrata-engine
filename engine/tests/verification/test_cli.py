"""CLI wiring for scope and quality subcommands."""

from __future__ import annotations

from pathlib import Path

from pytest import CaptureFixture

from tests.verification.gitutil import git
from verification.cli import main


def test_scope_cli_pass_on_engine_only_repo(git_repo: Path, capsys: CaptureFixture[str]) -> None:
    (git_repo / "engine" / "ok.md").write_text("cli\n", encoding="utf-8")
    code = main(["scope", "--repo", str(git_repo), "--base", "release/engine-next"])
    captured = capsys.readouterr()
    assert code == 0
    assert '"status": "PASS"' in captured.out


def test_scope_cli_fail_on_root_edit(git_repo: Path, capsys: CaptureFixture[str]) -> None:
    (git_repo / "README.md").write_text("nope\n", encoding="utf-8")
    code = main(["scope", "--repo", str(git_repo), "--base", "release/engine-next"])
    captured = capsys.readouterr()
    assert code == 1
    assert '"status": "FAIL"' in captured.out


def test_scope_cli_error_on_nongit(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    code = main(["scope", "--repo", str(empty)])
    captured = capsys.readouterr()
    assert code == 2
    assert '"status": "ERROR"' in captured.out


def test_committed_cumulative_diff_is_inspected(git_repo: Path) -> None:
    git(git_repo, "checkout", "engine/story")
    extra = git_repo / "leaked-root.txt"
    extra.write_text("outside\n", encoding="utf-8")
    git(git_repo, "add", "leaked-root.txt")
    git(git_repo, "commit", "-m", "leak")
    from verification.scope_guard import evaluate_repository

    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == "FAIL"
    assert any(finding.event.path == "leaked-root.txt" for finding in verdict.findings)
