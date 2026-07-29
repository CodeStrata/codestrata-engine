"""Tests for package metadata helpers."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

from codestrata.package_metadata import (
    PRODUCT_NAME,
    format_about,
    format_version_details,
    format_version_line,
    get_about_info,
    get_package_version,
)


def test_get_package_version_uses_distribution_or_fallback() -> None:
    version = get_package_version()
    assert version
    assert format_version_line() == f"{PRODUCT_NAME} {version}"


def test_get_package_version_falls_back_when_not_installed(monkeypatch) -> None:
    from codestrata import __version__
    from codestrata import package_metadata as module

    def _raise(_name: str) -> str:
        raise PackageNotFoundError(_name)

    monkeypatch.setattr(module, "package_version", _raise)
    assert get_package_version() == __version__


def test_about_info_matches_project_urls() -> None:
    info = get_about_info()
    assert info.website == "https://github.com/CodeStrata/codestrata-engine"
    assert info.github == "https://github.com/CodeStrata/codestrata-engine"
    assert "CodeStrata" in info.summary
    about = format_about()
    assert f"Website: {info.website}" in about
    assert f"GitHub: {info.github}" in about


def test_format_version_details_includes_engine_report_ai() -> None:
    text = format_version_details()
    lines = text.splitlines()
    assert lines[0].startswith("CodeStrata ")
    assert any(line.startswith("CLI: ") for line in lines)
    assert any(line.startswith("Engine: ") for line in lines)
    assert any(line.startswith("Edition: ") for line in lines)
    assert any(line.startswith("Schema version: ") for line in lines)
    assert any(line.startswith("Extension API: ") for line in lines)
    assert any(line.startswith("Report HTML: ") for line in lines)
    assert any(line.startswith("AI provider") for line in lines)
    assert any(line.startswith("Python: ") for line in lines)
    assert any(line.startswith("Operating System: ") for line in lines)
    assert any(line.startswith("Platform: ") for line in lines)
