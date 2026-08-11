"""SV.3 boundary tests."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
PKG = ENGINE / "src" / "codestrata"
VERIFICATION = ENGINE / "verification" / "cli_initialization"
CATALOG = REPO / "validation" / "repository-catalog" / "catalog.json"


def test_package_outside_wheel_src() -> None:
    assert (VERIFICATION / "runner.py").is_file()
    assert (VERIFICATION / "README.md").is_file()
    assert not (PKG / "verification").exists()


def test_public_export_includes_verification() -> None:
    manifest = yaml.safe_load((REPO / "public-export-manifest.yaml").read_text(encoding="utf-8"))
    engine = next(item for item in manifest["exports"] if item["name"] == "codestrata-engine")
    assert "verification/**" in engine["include"]


def test_repository_catalog_untouched_by_package() -> None:
    assert CATALOG.is_file()
    text = (VERIFICATION / "runner.py").read_text(encoding="utf-8")
    assert "repository-catalog" not in text
    assert "catalog.json" not in text


def test_no_platform_infrastructure_imports() -> None:
    for path in VERIFICATION.glob("*.py"):
        blob = path.read_text(encoding="utf-8")
        assert "codestrata_platform" not in blob
        assert "infrastructure/" not in blob


def test_schema_constants_unchanged() -> None:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
