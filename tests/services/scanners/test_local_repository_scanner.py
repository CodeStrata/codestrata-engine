"""Tests for the local repository scanner."""

import os
import subprocess
from pathlib import Path

import pytest

from codestrata.artifacts.repository_identity import resolve_repository_artifact_id
from codestrata.services.scanners import LocalRepositoryScanner


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
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env)


def test_scan_collects_repository_files(tmp_path: Path) -> None:
    """Scanner should collect files using repository-relative paths."""

    source_directory = tmp_path / "src"
    source_directory.mkdir()

    (tmp_path / "README.md").write_text(
        "# Sample Project",
        encoding="utf-8",
    )
    (source_directory / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    scanner = LocalRepositoryScanner()

    repository = scanner.scan(tmp_path)

    assert repository.name == tmp_path.name
    assert repository.path == tmp_path.resolve()
    assert repository.files == [
        "README.md",
        "src/main.py",
    ]
    assert repository.total_files == 2


def test_scan_excludes_default_directories(
    tmp_path: Path,
) -> None:
    """Scanner should ignore files inside default excluded directories."""

    # Avoid writing under a real ``.git`` directory name: some hosts refuse it.
    staging = tmp_path / ".export-staging"
    virtual_environment = tmp_path / ".venv"
    node_modules = tmp_path / "node_modules"

    staging.mkdir()
    virtual_environment.mkdir()
    node_modules.mkdir()

    (staging / "copied.py").write_text(
        "copied",
        encoding="utf-8",
    )
    (virtual_environment / "python").write_text(
        "binary",
        encoding="utf-8",
    )
    (node_modules / "package.js").write_text(
        "dependency",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "print('app')",
        encoding="utf-8",
    )

    scanner = LocalRepositoryScanner()

    repository = scanner.scan(tmp_path)

    assert repository.files == ["app.py"]
    assert repository.total_files == 1


def test_scan_supports_additional_excluded_directories(
    tmp_path: Path,
) -> None:
    """Scanner should support caller-provided directory exclusions."""

    generated_directory = tmp_path / "generated"
    generated_directory.mkdir()

    (generated_directory / "client.py").write_text(
        "generated code",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "print('main')",
        encoding="utf-8",
    )

    scanner = LocalRepositoryScanner(
        excluded_directories={"generated"},
    )

    repository = scanner.scan(tmp_path)

    assert repository.files == ["main.py"]


def test_scan_raises_error_when_path_does_not_exist(
    tmp_path: Path,
) -> None:
    """Scanner should reject a path that does not exist."""

    missing_path = tmp_path / "missing"

    scanner = LocalRepositoryScanner()

    with pytest.raises(
        FileNotFoundError,
        match="Repository path does not exist",
    ):
        scanner.scan(missing_path)


def test_scan_raises_error_when_path_is_a_file(
    tmp_path: Path,
) -> None:
    """Scanner should reject a path that is not a directory."""

    file_path = tmp_path / "application.py"
    file_path.write_text(
        "print('application')",
        encoding="utf-8",
    )

    scanner = LocalRepositoryScanner()

    with pytest.raises(
        NotADirectoryError,
        match="Repository path is not a directory",
    ):
        scanner.scan(file_path)


def test_nested_sample_does_not_adopt_unrelated_parent_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "unrelated"
    parent.mkdir()
    _git(parent, "init")
    _git(parent, "remote", "add", "origin", "https://github.com/CodeStrata/codestrata-mvp-wireframes.git")
    export_root = parent / "export"
    sample = export_root / "sample-js-app"
    sample.mkdir(parents=True)
    (sample / "package.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(export_root.resolve()))
    repository = LocalRepositoryScanner().scan(sample)
    assert repository.name == "sample-js-app"
    assert repository.source_url is None
    assert (
        resolve_repository_artifact_id(
            repository_name=repository.name,
            source_url=repository.source_url,
        )
        == "local-sample-js-app"
    )


def test_subdirectory_keeps_its_repository_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GIT_CEILING_DIRECTORIES", raising=False)
    origin = "https://github.com/example/intended.git"
    root = tmp_path / "intended"
    root.mkdir()
    _git(root, "init")
    _git(root, "remote", "add", "origin", origin)
    subdir = root / "services" / "api"
    subdir.mkdir(parents=True)
    (subdir / "main.py").write_text("print('api')\n", encoding="utf-8")
    repository = LocalRepositoryScanner().scan(subdir)
    assert repository.source_url == origin


def test_sanitize_git_origin_url_removes_tokens_and_credentials() -> None:
    from codestrata.services.scanners.local_repository_scanner import _sanitize_git_origin_url

    # Personal access token in HTTPS
    assert (
        _sanitize_git_origin_url("https://ghp_abcdef123456@github.com/org/Sales.Portal.Web.git")
        == "https://github.com/org/Sales.Portal.Web.git"
    )

    # Username + password in HTTPS
    assert (
        _sanitize_git_origin_url("https://user:secretpass@github.com/org/Sales.Portal.Web.git")
        == "https://github.com/org/Sales.Portal.Web.git"
    )

    # Azure DevOps with PAT
    assert (
        _sanitize_git_origin_url("https://token@dev.azure.com/org/project/_git/Sales.Portal.Web")
        == "https://dev.azure.com/org/project/_git/Sales.Portal.Web"
    )

    # Clean URL remains unchanged
    assert (
        _sanitize_git_origin_url("https://github.com/org/Sales.Portal.Web.git")
        == "https://github.com/org/Sales.Portal.Web.git"
    )

    # Standard SSH URL remains valid
    assert (
        _sanitize_git_origin_url("git@github.com:org/Sales.Portal.Web.git")
        == "git@github.com:org/Sales.Portal.Web.git"
    )

    # Empty or None
    assert _sanitize_git_origin_url("") is None


def test_phase1_adapter_source_location_drops_credential_urls() -> None:
    from codestrata.models import Repository
    from codestrata.services.graph_assessment.adapter import Phase1RepositoryAdapter

    clean_repo = Repository(
        name="test",
        path=Path("."),
        files=[],
        total_files=0,
        source_url="https://github.com/org/test.git",
    )
    assert (
        Phase1RepositoryAdapter._source_location(clean_repo)
        == "https://github.com/org/test.git"
    )

    dirty_repo = Repository(
        name="test",
        path=Path("."),
        files=[],
        total_files=0,
        source_url="https://user:pass@evil.com/repo.git",
    )
    assert Phase1RepositoryAdapter._source_location(dirty_repo) is None

