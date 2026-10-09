"""Guard + quality packages live beside src/, not in the wheel; no publish secrets."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
PKG = ENGINE / "src" / "codestrata"
SCOPE = ENGINE / "verification" / "engine_scope"
QUALITY = ENGINE / "verification" / "quality_commands"


def test_packages_live_outside_src() -> None:
    assert (SCOPE / "guard.py").is_file()
    assert (QUALITY / "manifest.yaml").is_file()
    assert not (PKG / "verification" / "engine_scope").exists()


def test_does_not_instruct_root_ci_edits() -> None:
    text = (SCOPE / "guard.py").read_text(encoding="utf-8")
    quality = (QUALITY / "manifest.yaml").read_text(encoding="utf-8")
    assert "permissions: write" not in text
    assert "automatic_branch_protection: false" in quality
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "name: engine-tests" in workflow
    assert "python -m pytest tests" in workflow


def test_no_production_publish_credentials_in_scope_sources() -> None:
    forbidden_fragments = (
        "AKIA",
        "pypi-AgE",
        "-----BEGIN",
        "aws_secret_access_key",
        "TWINE_PASSWORD=",
    )
    for path in (*SCOPE.glob("*.py"), *QUALITY.glob("*.py"), *QUALITY.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for fragment in forbidden_fragments:
            assert fragment.lower() not in lowered, f"{path} contains {fragment}"
