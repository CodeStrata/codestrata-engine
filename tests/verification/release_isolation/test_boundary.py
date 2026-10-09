"""Isolation package stays beside src/; no publish secrets; no root CI edits."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
PKG = ENGINE / "src" / "codestrata"
ISO = ENGINE / "verification" / "release_isolation"


def test_package_is_not_in_wheel_payload() -> None:
    pyproject = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["codestrata*"]' in pyproject
    assert (ISO / "policy.yaml").is_file()
    assert not (PKG / "verification" / "release_isolation").exists()


def test_no_production_publish_credentials() -> None:
    forbidden = ("AKIA", "pypi-AgE", "-----BEGIN", "aws_secret_access_key", "TWINE_PASSWORD=")
    for path in (*ISO.glob("*.py"), *ISO.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for fragment in forbidden:
            assert fragment.lower() not in lowered, f"{path} contains {fragment}"


def test_does_not_instruct_workflow_edits() -> None:
    for path in ISO.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "edit .github/workflows" not in text
        assert "edit public-export-manifest" not in text
