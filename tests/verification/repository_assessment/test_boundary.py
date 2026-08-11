"""SV.4 packaging / export boundary tests."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
PKG = ENGINE / "src" / "codestrata"
VERIFICATION = ENGINE / "verification" / "repository_assessment"
CATALOG = REPO / "validation" / "repository-catalog" / "catalog.json"


def test_package_outside_wheel_src() -> None:
    assert (VERIFICATION / "runner.py").is_file()
    assert (VERIFICATION / "README.md").is_file()
    assert not (PKG / "verification").exists()


def test_public_export_includes_verification() -> None:
    manifest = yaml.safe_load((REPO / "public-export-manifest.yaml").read_text(encoding="utf-8"))
    engine = next(item for item in manifest["exports"] if item["name"] == "codestrata-engine")
    assert "verification/**" in engine["include"]


def test_setuptools_excludes_verification_from_wheel() -> None:
    text = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'where = ["src"]' in text
    assert 'include = ["codestrata*"]' in text


def test_catalog_not_duplicated() -> None:
    assert CATALOG.is_file()
    # Suite must reference permanent catalog path, not invent a second list.
    contract_py = (VERIFICATION / "contract.py").read_text(encoding="utf-8")
    assert "validation/repository-catalog/catalog.json" in contract_py
    assert "spring-petclinic" not in (VERIFICATION / "catalog.py").read_text(encoding="utf-8").lower()
    assert "spring-petclinic" not in contract_py.lower()


def test_no_platform_infrastructure_imports() -> None:
    for path in VERIFICATION.glob("*.py"):
        blob = path.read_text(encoding="utf-8")
        assert "codestrata_platform" not in blob
        assert "infrastructure/" not in blob


def test_schema_constants_unchanged() -> None:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
