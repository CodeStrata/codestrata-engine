"""SV.2 boundary tests — verification stays outside the wheel and Platform."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
PKG = ENGINE / "src" / "codestrata"
VERIFICATION = ENGINE / "verification" / "cli_installation"


def test_verification_package_exists_outside_src() -> None:
    assert (ENGINE / "verification" / "README.md").is_file()
    assert (VERIFICATION / "contract.py").is_file()
    assert (VERIFICATION / "runner.py").is_file()
    assert (VERIFICATION / "README.md").is_file()
    assert not (PKG / "verification").exists()


def test_manifest_in_does_not_ship_verification_in_wheel() -> None:
    manifest = (ENGINE / "MANIFEST.in").read_text(encoding="utf-8")
    # Wheel packaging uses setuptools package discovery under src/; verification/
    # must remain excluded from the distribution payload.
    assert "verification" not in manifest.lower() or "prune verification" in manifest.lower()
    pyproject = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["codestrata*"]' in pyproject or "codestrata*" in pyproject


def test_public_export_includes_verification() -> None:
    manifest = yaml.safe_load(
        (REPO / "public-export-manifest.yaml").read_text(encoding="utf-8")
    )
    engine = next(item for item in manifest["exports"] if item["name"] == "codestrata-engine")
    assert "verification/**" in engine["include"]


def test_no_schema_constants_changed_by_sv2() -> None:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"


def test_runner_does_not_import_platform() -> None:
    text = (VERIFICATION / "runner.py").read_text(encoding="utf-8")
    assert "codestrata_platform" not in text
    assert "infrastructure" not in text
