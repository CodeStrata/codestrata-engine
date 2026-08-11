"""Boundary tests for SV.11."""

from __future__ import annotations

from pathlib import Path

from verification.assessment_consistency.contract import default_contract


def test_package_outside_src_wheel_boundary() -> None:
    engine = Path(__file__).resolve().parents[3]
    assert (engine / "verification" / "assessment_consistency").is_dir()
    assert not (engine / "src" / "codestrata" / "verification" / "assessment_consistency").exists()


def test_contract_forbids_sv12_and_reassess() -> None:
    c = default_contract()
    assert c.start_sv12 is False
    assert c.reassess_by_default is False
    assert c.install_repo_dependencies is False


def test_readme_exists() -> None:
    readme = (
        Path(__file__).resolve().parents[3]
        / "verification"
        / "assessment_consistency"
        / "README.md"
    )
    text = readme.read_text(encoding="utf-8")
    assert "22" in text
    assert "not" in text.lower() and "accuracy" in text.lower()
