"""Tests for the local repository scanner."""

from pathlib import Path

import pytest

from codestrata.services.scanners import LocalRepositoryScanner


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
