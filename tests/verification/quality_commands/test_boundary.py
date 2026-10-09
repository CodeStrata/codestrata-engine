"""Quality commands are maintainer-only; they must not ship in the codestrata wheel."""

from __future__ import annotations

from pathlib import Path

ENGINE = Path(__file__).resolve().parents[3]


def test_quality_package_is_not_in_wheel_payload() -> None:
    pyproject = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["codestrata*"]' in pyproject
    assert (ENGINE / "verification" / "quality_commands" / "manifest.yaml").is_file()
    assert not (ENGINE / "src" / "codestrata" / "quality_commands").exists()
