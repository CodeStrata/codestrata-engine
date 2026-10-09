"""Report-path Git identity stays inside the intended repository."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.application.assessment.service import run_assessment
from codestrata.config import CodestrataSettings
from codestrata.models import AnalysisResult, Repository
from codestrata.reporters.report_paths import _git_origin_url, create_report_paths
from codestrata.reporting import AssessmentMode

PARENT_ORIGIN = "https://github.com/CodeStrata/codestrata-mvp-wireframes.git"
INTENDED_ORIGIN = "https://github.com/example/intended.git"


def _git(cwd: Path, *args: str) -> None:
    env = os.environ.copy()
    env.pop("GIT_CEILING_DIRECTORIES", None)
    env.update(
        {
            "GIT_AUTHOR_NAME": "P03c Test",
            "GIT_AUTHOR_EMAIL": "p03c@example.com",
            "GIT_COMMITTER_NAME": "P03c Test",
            "GIT_COMMITTER_EMAIL": "p03c@example.com",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _nested_sample(tmp_path: Path) -> tuple[Path, Path]:
    parent = tmp_path / "unrelated"
    parent.mkdir()
    _git(parent, "init")
    _git(parent, "remote", "add", "origin", PARENT_ORIGIN)
    export_root = parent / "export"
    sample = export_root / "sample-js-app"
    sample.mkdir(parents=True)
    (sample / "package.json").write_text('{"name": "sample-js-app"}\n', encoding="utf-8")
    return export_root, sample


def test_nested_sample_does_not_adopt_unrelated_parent_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export_root, sample = _nested_sample(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(export_root.resolve()))
    assert _git_origin_url(sample) is None


def test_report_paths_resolve_nested_sample_as_local_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export_root, sample = _nested_sample(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(export_root.resolve()))
    result = AnalysisResult(
        repository=Repository(name="sample-js-app", path=sample, files=["package.json"]),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    paths = create_report_paths(
        result,
        tmp_path / "reports",
        timestamp="20261006-120000",
        create_directory=True,
    )
    assert paths.repository_id == "local-sample-js-app"


def test_repository_and_subdirectory_keep_intended_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GIT_CEILING_DIRECTORIES", raising=False)
    root = tmp_path / "intended"
    root.mkdir()
    _git(root, "init")
    _git(root, "remote", "add", "origin", INTENDED_ORIGIN)
    (root / "README.md").write_text("intended\n", encoding="utf-8")
    subdir = root / "services" / "api"
    subdir.mkdir(parents=True)
    (subdir / "main.py").write_text("print('api')\n", encoding="utf-8")
    assert _git_origin_url(root) == INTENDED_ORIGIN
    assert _git_origin_url(subdir) == INTENDED_ORIGIN


def test_linked_worktree_keeps_intended_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GIT_CEILING_DIRECTORIES", raising=False)
    root = tmp_path / "intended"
    root.mkdir()
    _git(root, "init")
    _git(root, "remote", "add", "origin", INTENDED_ORIGIN)
    (root / "README.md").write_text("intended\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "init")
    linked = tmp_path / "linked"
    _git(root, "worktree", "add", "--detach", str(linked))
    assert (linked / ".git").is_file()
    assert _git_origin_url(linked) == INTENDED_ORIGIN


def test_run_assessment_nested_sample_uses_local_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export_root, sample = _nested_sample(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(export_root.resolve()))
    output = tmp_path / "reports"
    result = run_assessment(
        repo=str(sample),
        output_directory=output,
        mode=AssessmentMode.DETERMINISTIC,
        settings=CodestrataSettings.model_validate(
            {
                "repository": {"path": str(sample)},
                "knowledge": {"enabled": False, "directory": str(tmp_path / "knowledge")},
                "static_analysis": {"enabled": False},
                "ai": {"bedrock": {}},
            }
        ),
        quiet=True,
        config_path=tmp_path / "missing.toml",
        clock=lambda: datetime(2026, 10, 6, 12, 0, tzinfo=UTC),
    )
    payload = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    assert payload["repository"] == "sample-js-app"
    assert payload["repository_id"] == "local-sample-js-app"
    assert result.json_report_path.parent.parent.name == "local-sample-js-app"
    assert not (output / "github-codestrata-codestrata-mvp-wireframes").exists()
