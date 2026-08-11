"""Unit tests for verification.ai_provider_contracts.dependency_boundary."""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_contracts.dependency_boundary import (
    run_dependency_boundary_checks,
)
from verification.ai_provider_contracts.runner import engine_root_from_package

ENGINE_ROOT = engine_root_from_package()
PACKAGE_DIR = ENGINE_ROOT / "src" / "codestrata" / "ai" / "provider_contracts"


def test_dependency_boundary_checks_all_pass_against_real_package() -> None:
    checks, matrix = run_dependency_boundary_checks(ENGINE_ROOT, PACKAGE_DIR)
    assert all(check.ok for check in checks), [c for c in checks if not c.ok]
    assert "forbidden_import_prefixes" in matrix


def test_product_path_files_list_is_non_empty_and_exists() -> None:
    from verification.ai_provider_contracts.contract import PRODUCT_PATH_FILES

    assert PRODUCT_PATH_FILES
    for relative in PRODUCT_PATH_FILES:
        path = ENGINE_ROOT / "src" / "codestrata" / relative
        assert path.is_file(), f"expected product-path file to exist: {relative}"


def test_check_no_forbidden_sdk_imports_flags_a_synthetic_offender(tmp_path: Path) -> None:
    from verification.ai_provider_contracts.contract import EXPECTED_MODULES
    from verification.ai_provider_contracts.dependency_boundary import (
        check_no_forbidden_sdk_imports,
    )

    package_dir = tmp_path / "provider_contracts"
    package_dir.mkdir()
    for name in EXPECTED_MODULES:
        (package_dir / name).write_text("", encoding="utf-8")
    (package_dir / "policy.py").write_text("import boto3\n", encoding="utf-8")

    result = check_no_forbidden_sdk_imports(package_dir)
    assert result.ok is False
    assert "policy.py" in result.detail
