"""Unit tests for verification.ai_provider_execution.dependency_boundary."""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_execution.dependency_boundary import (
    check_execution_modules_never_import_forbidden_runtime_modules,
    run_dependency_boundary_checks,
)
from verification.ai_provider_execution.runner import engine_root_from_package

ENGINE_ROOT = engine_root_from_package()
PACKAGE_DIR = ENGINE_ROOT / "src" / "codestrata" / "ai" / "provider_contracts"


def test_dependency_boundary_checks_all_pass_against_real_package() -> None:
    checks, matrix = run_dependency_boundary_checks(ENGINE_ROOT, PACKAGE_DIR)
    assert all(check.ok for check in checks), [c for c in checks if not c.ok]
    assert "forbidden_import_prefixes" in matrix


def test_execution_modules_never_import_forbidden_runtime_modules_against_real_package() -> None:
    result = check_execution_modules_never_import_forbidden_runtime_modules(PACKAGE_DIR)
    assert result.ok is True


def test_product_path_files_list_is_non_empty_and_exists() -> None:
    from verification.ai_provider_execution.contract import PRODUCT_PATH_FILES

    assert PRODUCT_PATH_FILES
    for relative in PRODUCT_PATH_FILES:
        path = ENGINE_ROOT / "src" / "codestrata" / relative
        assert path.is_file(), f"expected product-path file to exist: {relative}"


def test_check_no_forbidden_sdk_imports_flags_a_synthetic_offender(tmp_path: Path) -> None:
    from verification.ai_provider_execution.contract import EXPECTED_MODULES
    from verification.ai_provider_execution.dependency_boundary import (
        check_no_forbidden_sdk_imports,
    )

    package_dir = tmp_path / "provider_contracts"
    package_dir.mkdir()
    for name in EXPECTED_MODULES:
        (package_dir / name).write_text("", encoding="utf-8")
    (package_dir / "executor.py").write_text("import boto3\n", encoding="utf-8")

    result = check_no_forbidden_sdk_imports(package_dir)
    assert result.ok is False
    assert "executor.py" in result.detail


def test_check_execution_modules_never_import_forbidden_flags_a_synthetic_offender(
    tmp_path: Path,
) -> None:
    from verification.ai_provider_execution.contract import EXPECTED_MODULES

    package_dir = tmp_path / "provider_contracts"
    package_dir.mkdir()
    for name in EXPECTED_MODULES:
        (package_dir / name).write_text("", encoding="utf-8")
    (package_dir / "executor.py").write_text("import threading\n", encoding="utf-8")

    result = check_execution_modules_never_import_forbidden_runtime_modules(package_dir)
    assert result.ok is False
    assert "executor.py" in result.detail
