"""Corpus package stays beside src/; no publish secrets; no root CI edits."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
PKG = ENGINE / "src" / "codestrata"
VAL = ENGINE / "verification" / "validation"


def test_package_is_not_in_wheel_payload() -> None:
    pyproject = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["codestrata*"]' in pyproject
    assert (VAL / "corpus" / "policy.yaml").is_file()
    assert not (PKG / "verification" / "validation").exists()


def test_no_production_publish_credentials() -> None:
    forbidden = ("AKIA", "pypi-AgE", "-----BEGIN", "aws_secret_access_key", "TWINE_PASSWORD=")
    for path in (*VAL.rglob("*.py"), *VAL.rglob("*.yaml"), *VAL.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden:
            assert fragment.lower() not in text.lower(), f"{path} contains {fragment}"


def test_does_not_instruct_workflow_edits_or_remote_clones_in_default_tests() -> None:
    for path in VAL.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "edit .github/workflows" not in text
        assert "git clone" not in text
