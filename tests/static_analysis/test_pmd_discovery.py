"""Tests for PMD executable discovery and version probing."""

from __future__ import annotations

import subprocess
from pathlib import Path

from codestrata.static_analysis.providers.pmd_discovery import (
    CODESTRATA_PMD_PATH_ENV,
    PmdDiscoveryResult,
    probe_pmd_version,
    resolve_pmd_executable,
    sanitize_pmd_user_message,
)


def _exec_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho PMD 7.0.0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_cli_path_precedence_over_env_and_config(tmp_path: Path) -> None:
    cli = _exec_file(tmp_path / "cli" / "pmd")
    env = _exec_file(tmp_path / "env" / "pmd")
    config = _exec_file(tmp_path / "config" / "pmd")
    result = resolve_pmd_executable(
        cli_path=str(cli),
        configured=str(config),
        env={CODESTRATA_PMD_PATH_ENV: str(env)},
        path_lookup=lambda _name: None,
        platform="linux",
    )
    assert result.executable == str(cli)
    assert result.source == "cli"


def test_env_codestrata_pmd_path_over_config(tmp_path: Path) -> None:
    env = _exec_file(tmp_path / "env" / "pmd")
    config = _exec_file(tmp_path / "config" / "pmd")
    result = resolve_pmd_executable(
        cli_path=None,
        configured=str(config),
        env={CODESTRATA_PMD_PATH_ENV: str(env)},
        path_lookup=lambda _name: None,
        platform="linux",
    )
    assert result.executable == str(env)
    assert result.source == "environment"


def test_config_path(tmp_path: Path) -> None:
    config = _exec_file(tmp_path / "config" / "pmd")
    result = resolve_pmd_executable(
        cli_path=None,
        configured=str(config),
        env={},
        path_lookup=lambda _name: None,
        platform="linux",
    )
    assert result.executable == str(config)
    assert result.source == "config"


def test_path_discovery_for_pmd_and_pmd_bin(tmp_path: Path) -> None:
    pmd = _exec_file(tmp_path / "bin" / "pmd")
    pmd_bin = _exec_file(tmp_path / "bin" / "pmd-bin")

    def lookup(name: str) -> str | None:
        if name == "pmd":
            return str(pmd)
        if name == "pmd-bin":
            return str(pmd_bin)
        return None

    result = resolve_pmd_executable(
        cli_path=None,
        configured=None,
        env={},
        path_lookup=lookup,
        platform="linux",
    )
    assert result.executable == str(pmd)
    assert result.source == "path"

    def lookup_bin_only(name: str) -> str | None:
        if name == "pmd-bin":
            return str(pmd_bin)
        return None

    result_bin = resolve_pmd_executable(
        cli_path=None,
        configured=None,
        env={},
        path_lookup=lookup_bin_only,
        platform="linux",
    )
    assert result_bin.executable == str(pmd_bin)
    assert result_bin.source == "path"


def test_homebrew_candidates_on_darwin_when_path_missing(tmp_path: Path) -> None:
    brew = _exec_file(tmp_path / "opt" / "homebrew" / "bin" / "pmd")
    candidates = {
        Path("/opt/homebrew/bin/pmd"): brew,
        Path("/usr/local/bin/pmd"): tmp_path / "missing-usr-local",
        Path("/opt/homebrew/bin/pmd-bin"): tmp_path / "missing-opt-bin",
        Path("/usr/local/bin/pmd-bin"): tmp_path / "missing-usr-bin",
    }

    def exists(path: Path) -> bool:
        mapped = candidates.get(path, path)
        return mapped.exists()

    def is_file(path: Path) -> bool:
        mapped = candidates.get(path, path)
        return mapped.is_file()

    def is_executable(path: Path) -> bool:
        mapped = candidates.get(path, path)
        return mapped.exists() and mapped.is_file()

    result = resolve_pmd_executable(
        cli_path=None,
        configured=None,
        env={},
        path_lookup=lambda _name: None,
        platform="darwin",
        filesystem_exists=exists,
        is_file=is_file,
        is_executable=is_executable,
    )
    assert result.executable == "/opt/homebrew/bin/pmd"
    assert result.source == "homebrew"


def test_missing_explicit_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist" / "pmd"
    result = resolve_pmd_executable(
        cli_path=str(missing),
        configured=None,
        env={},
        path_lookup=lambda _name: None,
        platform="linux",
    )
    assert result.executable is None
    assert result.source == "cli"
    assert result.message is not None
    assert "not found" in result.message.lower()


def test_not_a_file(tmp_path: Path) -> None:
    directory = tmp_path / "pmd-dir"
    directory.mkdir()
    result = resolve_pmd_executable(
        cli_path=str(directory),
        configured=None,
        env={},
        path_lookup=lambda _name: None,
        platform="linux",
    )
    assert result.executable is None
    assert result.source == "cli"
    assert result.message is not None
    assert "not a file" in result.message.lower()


def test_not_executable(tmp_path: Path) -> None:
    path = tmp_path / "pmd"
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o644)
    result = resolve_pmd_executable(
        cli_path=str(path),
        configured=None,
        env={},
        path_lookup=lambda _name: None,
        platform="linux",
    )
    assert result.executable is None
    assert result.source == "cli"
    assert result.message is not None
    assert "not executable" in result.message.lower()


def test_probe_pmd_version_success() -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        assert args == ["/usr/bin/pmd", "--version"]
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="PMD 7.15.0 (build abc)\n",
            stderr="",
        )

    assert probe_pmd_version("/usr/bin/pmd", process_runner=runner) == "7.15.0"


def test_probe_pmd_version_timeout() -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd=["pmd", "--version"], timeout=15)

    assert probe_pmd_version("pmd", process_runner=runner) is None


def test_probe_pmd_version_failure() -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=127,
            stdout="",
            stderr="command not found",
        )

    assert probe_pmd_version("pmd", process_runner=runner) is None


def test_sanitize_pmd_user_message_strips_absolute_paths() -> None:
    message = "Failed to run /Users/satish/tools/pmd/bin/pmd check and C:\\Tools\\pmd\\bin\\pmd.exe"
    sanitized = sanitize_pmd_user_message(message)
    assert "/Users/satish" not in sanitized
    assert "C:\\Tools" not in sanitized
    assert "<path>" in sanitized


def test_resolve_returns_none_when_nothing_found() -> None:
    result = resolve_pmd_executable(
        cli_path=None,
        configured=None,
        env={},
        path_lookup=lambda _name: None,
        platform="linux",
    )
    assert isinstance(result, PmdDiscoveryResult)
    assert result.executable is None
    assert result.source == "none"
