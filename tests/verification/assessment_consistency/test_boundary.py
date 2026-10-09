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
    assert "not_evaluated" in text
    assert "verification.assessment_ingestion" in text


def test_exported_suite_does_not_import_platform() -> None:
    import ast

    package = Path(__file__).resolve().parents[3] / "verification" / "assessment_consistency"
    assert not (package / "platform_ingestion_adapter.py").exists()
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all(not name.startswith("codestrata_platform") for name in names)
            assert all("sys" != name for name in names)


def test_platform_ingestion_is_not_recorded_as_pass() -> None:
    from verification.assessment_consistency.models import RepositoryBundle
    from verification.assessment_consistency.reporting import (
        PLATFORM_INGESTION_NOT_EVALUATED,
        check_engineering_intelligence_input_ready,
    )

    bundle = RepositoryBundle(
        repository_id="sample",
        record={"repository_id": "sample", "final_checkout_sha": "abc123"},
        report={
            "schema_version": "1.2",
            "assessment": {
                "findings": [],
                "assessment_coverage": {"security_intelligence": {"status": "complete"}},
                "assessment_head_confidence": {"security_intelligence": {"level": "moderate"}},
            },
        },
        findings_doc={"findings": []},
        recommendations_doc={"recommendations": []},
        artifact_dir_name="abc123abc123",
        html_present=False,
    )
    ready, checks, defects = check_engineering_intelligence_input_ready([bundle])
    assert ready == {"sample": True}
    assert defects == []
    platform = next(item for item in checks if item.name == "platform_ingestion_safety")
    assert platform.ok is False
    assert platform.detail == PLATFORM_INGESTION_NOT_EVALUATED
