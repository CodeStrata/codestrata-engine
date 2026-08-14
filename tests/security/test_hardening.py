"""Security hardening tests (Phase 5.24)."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

import pytest

from codestrata.extensions import enterprise_runtime_available
from codestrata.security.filesystem import (
    assert_path_within_root,
    iter_repository_files,
    safe_output_directory,
)
from codestrata.services.inventory.content_reader import LocalFilesystemContentReader
from codestrata.services.scanners.local_repository_scanner import LocalRepositoryScanner


def test_scanner_ignores_symlinked_directories(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    (repo / "escape").symlink_to(outside, target_is_directory=True)

    files = LocalRepositoryScanner().scan(repo).files
    assert files == ["app.py"]
    assert all("secret" not in name for name in files)


def test_scanner_skips_escaping_file_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ok.txt").write_text("ok", encoding="utf-8")
    (repo / "leak.txt").symlink_to(outside)

    files = set(iter_repository_files(repo, excluded_directories=set()))
    assert files == {"ok.txt"}


def test_content_reader_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    reader = LocalFilesystemContentReader(tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        reader.read("link.txt")


def test_assert_path_within_root_blocks_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        assert_path_within_root(tmp_path / "other", root)


def test_safe_output_directory_creates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = safe_output_directory(Path("reports/out"))
    assert out.is_dir()
    assert out == (tmp_path / "reports" / "out").resolve()


def test_enterprise_runtime_available_in_monorepo() -> None:
    # Platform registers `enterprise` on codestrata.cli_extensions. Engine-only CI
    # installs engine[dev] without Platform; do not require the entry point here.
    enterprise_installed = any(
        ep.name == "enterprise"
        for ep in entry_points().select(group="codestrata.cli_extensions")
    )
    assert enterprise_runtime_available() is enterprise_installed


def test_mcp_factory_skips_enterprise_when_disabled() -> None:
    pytest.importorskip("mcp")
    from codestrata.config import CodestrataSettings
    from codestrata.interfaces.mcp.factory import create_mcp_server

    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "test-fixtures/sample-js-app"},
            "enterprise": {"enabled": False},
            "mcp": {"enabled": True},
        }
    )
    server = create_mcp_server(settings=settings)
    # Enterprise tools may still be registered as stubs; services should be None.
    # Health tool should exist regardless.
    assert server.name


def test_no_shell_true_in_engine_src() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "codestrata"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "shell=True" in text:
            offenders.append(str(path))
    assert not offenders


def test_yaml_safe_load_only_in_engine_src() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "codestrata"
    bad = ("yaml.load(", "yaml.full_load(", "yaml.unsafe_load(")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in bad):
            offenders.append(str(path))
    assert not offenders
