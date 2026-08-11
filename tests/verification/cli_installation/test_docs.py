"""SV.2 documentation presence tests."""

from __future__ import annotations

from pathlib import Path

ENGINE = Path(__file__).resolve().parents[3]
VERIFICATION = ENGINE / "verification"


def test_verification_readme_documents_sv2() -> None:
    root = (VERIFICATION / "README.md").read_text(encoding="utf-8")
    suite = (VERIFICATION / "cli_installation" / "README.md").read_text(encoding="utf-8")
    assert "SV.2" in root
    assert "cli_installation" in root
    assert "Fresh virtualenv" in suite or "fresh virtualenv" in suite.lower()
    assert "pip_wheel" in suite
    assert "PYTHONPATH" in suite
    assert "codestrata --help" in suite
    assert "Do not start SV.3" in suite or "Does not start SV.3" in suite


def test_installation_doc_links_sv2() -> None:
    text = (ENGINE / "docs" / "installation.md").read_text(encoding="utf-8")
    assert "cli_installation" in text or "SV.2" in text
