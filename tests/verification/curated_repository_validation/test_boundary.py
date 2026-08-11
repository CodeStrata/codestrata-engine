"""Boundary tests for SV.10 package."""

from __future__ import annotations

from pathlib import Path

from verification.curated_repository_validation.contract import default_contract


def test_package_does_not_enable_ai_or_deps() -> None:
    contract = default_contract()
    assert contract.ai_enabled is False
    assert contract.telemetry_enabled is False
    assert contract.install_repo_dependencies is False
    assert contract.build_repository is False
    assert contract.run_repository_tests is False
    assert contract.initialize_submodules is False
    assert contract.download_git_lfs is False


def test_readme_exists() -> None:
    readme = Path(__file__).resolve().parents[3] / "verification" / "curated_repository_validation" / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert "22" in text
    assert "--no-ai" in text
