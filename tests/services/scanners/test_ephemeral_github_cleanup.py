"""Phase 6.2 ephemeral GitHub clone cleanup tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from codestrata.application.assessment.service import (
    AssessmentCommandError,
    _cleanup_ephemeral_github_clone,
    run_assessment,
)
from codestrata.config.settings import CodestrataSettings
from codestrata.models import AnalysisResult, Repository, Technology
from codestrata.models.technology import TechnologyCategory
from codestrata.reporting import AssessmentMode
from codestrata.services.scanners.github_repository_scanner import (
    GitHubRepositoryScanner,
    dispose_ephemeral_repository,
)


class RecordingConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, *args: Any, **_kwargs: Any) -> None:
        self.messages.append(" ".join(str(arg) for arg in args))


class FakeScanner:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def scan(self, source: str | Path) -> Repository:
        del source
        return self.repository


class FakeAnalysisService:
    def __init__(self, result: AnalysisResult) -> None:
        self._result = result

    def analyze(self, repository: Repository, **_kwargs: object) -> AnalysisResult:
        del repository
        return self._result


def _local_repo(tmp_path: Path, *, ephemeral: bool = False) -> Repository:
    root = tmp_path / "user-app"
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("demo\n", encoding="utf-8")
    return Repository(
        name="user-app",
        path=root,
        files=["README.md"],
        total_files=1,
        ephemeral=ephemeral,
    )


def _analysis(repository: Repository) -> AnalysisResult:
    return AnalysisResult(
        repository=repository,
        technologies=[
            Technology(name="JavaScript", category=TechnologyCategory.LANGUAGE, confidence=1.0)
        ],
        findings=[],
        analyzer_version="test",
        duration_ms=1.0,
    )


def _settings(tmp_path: Path, repository: Repository) -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repository.path)},
            "knowledge": {"enabled": False, "directory": str(tmp_path / "knowledge")},
        }
    )


def _run_assess(
    tmp_path: Path,
    repository: Repository,
    *,
    analysis_service: Any | None = None,
) -> None:
    run_assessment(
        repo=str(repository.path),
        output_directory=tmp_path / "reports",
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
        settings=_settings(tmp_path, repository),
        scanner=FakeScanner(repository),
        analysis_service=analysis_service or FakeAnalysisService(_analysis(repository)),
        console=RecordingConsole(),
        clock=lambda: datetime(2026, 7, 21, 18, 0, tzinfo=UTC),
    )


def test_dispose_ephemeral_removes_directory(tmp_path: Path) -> None:
    clone = tmp_path / "codestrata-github-demo"
    clone.mkdir()
    (clone / "file.txt").write_text("x\n", encoding="utf-8")
    repository = Repository(name="demo", path=clone, ephemeral=True)
    assert dispose_ephemeral_repository(repository) is True
    assert not clone.exists()


def test_dispose_skips_local_repository(tmp_path: Path) -> None:
    repository = _local_repo(tmp_path, ephemeral=False)
    assert dispose_ephemeral_repository(repository) is False
    assert repository.path.is_dir()


def test_cleanup_helper_preserves_local(tmp_path: Path) -> None:
    warnings: list[str] = []
    repository = _local_repo(tmp_path, ephemeral=False)
    _cleanup_ephemeral_github_clone(repository, warn=warnings.append)
    assert repository.path.is_dir()
    assert warnings == []


def test_cleanup_helper_removes_ephemeral(tmp_path: Path) -> None:
    clone = tmp_path / "ephemeral-clone"
    clone.mkdir()
    repository = Repository(name="demo", path=clone, ephemeral=True)
    _cleanup_ephemeral_github_clone(repository)
    assert not clone.exists()


def test_github_scanner_ephemeral_marks_repository_and_uses_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "codestrata.services.scanners.github_repository_scanner.tempfile.gettempdir",
        lambda: str(tmp_path),
    )
    local_scanner = Mock()

    def _scan(path: Path) -> Repository:
        path.mkdir(parents=True, exist_ok=True)
        (path / "README.md").write_text("ok\n", encoding="utf-8")
        return Repository(name="sample-app", path=path, files=["README.md"], total_files=1)

    local_scanner.scan.side_effect = _scan
    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path / "durable-workspace",
        branch="main",
        local_scanner=local_scanner,
        ephemeral=True,
    )

    completed = __import__("subprocess").CompletedProcess
    with patch("codestrata.repository_auth.git_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            completed(["git"], 0, "", ""),
            completed(["git"], 0, "https://github.com/example/sample-app.git\n", ""),
        ]
        repository = scanner.scan("https://github.com/example/sample-app.git")

    assert repository.ephemeral is True
    assert repository.name == "sample-app"
    assert Path(repository.path).name != repository.name
    assert "codestrata-github-sample-app-" in Path(repository.path).name
    assert str(repository.path).startswith(str(tmp_path))
    assert "durable-workspace" not in str(repository.path)
    assert run_mock.call_args_list[0].args[0][:4] == ["git", "clone", "--depth", "1"]
    dispose_ephemeral_repository(repository)
    assert not repository.path.exists()


def test_assess_cleans_ephemeral_clone_on_success(tmp_path: Path) -> None:
    clone = tmp_path / "ephemeral-success"
    clone.mkdir()
    (clone / "README.md").write_text("x\n", encoding="utf-8")
    repository = Repository(
        name="ephemeral-success",
        path=clone,
        files=["README.md"],
        total_files=1,
        ephemeral=True,
        source_url="https://github.com/example/ephemeral-success.git",
    )
    _run_assess(tmp_path, repository)
    assert not clone.exists()


def test_assess_cleans_ephemeral_clone_after_failure(tmp_path: Path) -> None:
    clone = tmp_path / "ephemeral-fail"
    clone.mkdir()
    (clone / "README.md").write_text("x\n", encoding="utf-8")
    repository = Repository(
        name="ephemeral-fail",
        path=clone,
        files=["README.md"],
        total_files=1,
        ephemeral=True,
    )

    class BoomAnalysis:
        def analyze(self, repository: Repository, **_kwargs: object) -> AnalysisResult:
            del repository
            raise RuntimeError("analysis exploded")

    with pytest.raises(AssessmentCommandError, match="analysis exploded"):
        _run_assess(tmp_path, repository, analysis_service=BoomAnalysis())
    assert not clone.exists()


def test_assess_preserves_local_repository(tmp_path: Path) -> None:
    repository = _local_repo(tmp_path, ephemeral=False)
    _run_assess(tmp_path, repository)
    assert repository.path.is_dir()
    assert (repository.path / "README.md").is_file()
