"""Inventory and dependency-boundary primitives, including falsifiability.

The checks themselves are asserted green against the real tree in
``test_checks.py``. Here each one is re-run against a synthetic package that
deliberately violates it, so a check that silently stopped inspecting anything
cannot pass unnoticed.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from verification.openai_provider_migration.contract import (
    CREDENTIAL_BOUNDARY_MODULE,
    EXPECTED_MODULES,
    PACKAGE_DOTTED_NAME,
    PACKAGE_RELATIVE_PATH,
)

from verification.openai_provider_migration import dependency_boundary, inventory

ENGINE_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = ENGINE_ROOT / "src" / "codestrata" / PACKAGE_RELATIVE_PATH


@pytest.fixture
def fake_package(tmp_path: Path) -> Path:
    """A package with every expected module present and boundary-clean."""

    package = tmp_path / "openai"
    package.mkdir()
    for filename in EXPECTED_MODULES:
        body = '"""Doc."""\n'
        if filename != "__init__.py":
            body += "\n__all__: list[str] = []\n"
        (package / filename).write_text(body, encoding="utf-8")
    return package


class TestAstPrimitives:
    def test_imported_module_names_covers_both_import_forms(self) -> None:
        tree = ast.parse("import os.path\nfrom a.b import c\nimport json, re\n")

        assert inventory.imported_module_names(tree) == ["a.b", "json", "os.path", "re"]

    def test_relative_imports_have_no_module_name_and_are_skipped(self) -> None:
        assert inventory.imported_module_names(ast.parse("from . import x\n")) == []

    def test_inspect_module_reports_dotted_names_not_paths(self) -> None:
        entry = inventory.inspect_module(PACKAGE_DIR, "adapter.py")

        assert entry["module"] == f"{PACKAGE_DOTTED_NAME}.adapter"
        assert "/" not in entry["module"]
        assert entry["line_count"] > 0

    def test_the_package_init_maps_to_the_package_dotted_name(self) -> None:
        entry = inventory.inspect_module(PACKAGE_DIR, "__init__.py")

        assert entry["module"] == PACKAGE_DOTTED_NAME

    def test_the_inventory_is_sorted_and_covers_every_module(self) -> None:
        entries = inventory.build_package_inventory(PACKAGE_DIR)
        modules = [entry["module"] for entry in entries]

        assert modules == sorted(modules)
        assert len(entries) == len(EXPECTED_MODULES)

    def test_private_functions_are_left_out_of_the_public_surface(self) -> None:
        tree = ast.parse("def public():\n    ...\n\ndef _private():\n    ...\n")

        assert inventory._function_names(tree) == ["public"]

    def test_attribute_accesses_ignore_prose(self, fake_package: Path) -> None:
        (fake_package / "adapter.py").write_text(
            '"""Never calls os.environ in prose."""\n\n__all__: list[str] = []\n',
            encoding="utf-8",
        )

        assert "os.environ" not in dependency_boundary._attribute_accesses(
            fake_package, "adapter.py"
        )


class TestInventoryFalsifiability:
    def test_a_missing_module_is_reported(self, fake_package: Path) -> None:
        (fake_package / "adapter.py").unlink()

        result = inventory.check_expected_modules_present(fake_package)

        assert not result.ok
        assert "adapter.py" in result.detail

    def test_an_unexpected_module_is_reported(self, fake_package: Path) -> None:
        (fake_package / "stray.py").write_text('"""Doc."""\n', encoding="utf-8")

        assert not inventory.check_expected_modules_present(fake_package).ok

    def test_an_undocumented_module_is_reported(self, fake_package: Path) -> None:
        (fake_package / "client.py").write_text("__all__: list[str] = []\n", encoding="utf-8")

        result = inventory.check_every_module_is_documented(fake_package)

        assert not result.ok
        assert "client.py" in result.detail

    def test_a_module_without_an_explicit_surface_is_reported(self, fake_package: Path) -> None:
        (fake_package / "factory.py").write_text('"""Doc."""\n', encoding="utf-8")

        assert not inventory.check_every_module_declares_all(fake_package).ok

    def test_a_missing_package_directory_is_reported(self, tmp_path: Path) -> None:
        assert not inventory.check_package_exists(tmp_path).ok
        assert not inventory.check_adapters_root_is_a_package(tmp_path).ok


class TestBoundaryFalsifiability:
    def test_a_forbidden_layer_import_is_reported(self, fake_package: Path) -> None:
        (fake_package / "adapter.py").write_text(
            '"""Doc."""\n\nfrom codestrata.telemetry import runtime\n\n__all__: list[str] = []\n',
            encoding="utf-8",
        )

        result = dependency_boundary.check_no_forbidden_layer_imports(fake_package)

        assert not result.ok
        assert "adapter.py" in result.detail

    def test_an_out_of_set_internal_import_is_reported(self, fake_package: Path) -> None:
        (fake_package / "adapter.py").write_text(
            '"""Doc."""\n\nfrom codestrata.services import scanner\n\n__all__: list[str] = []\n',
            encoding="utf-8",
        )

        assert not dependency_boundary.check_internal_imports_stay_within_allowed_set(
            fake_package
        ).ok

    def test_an_sdk_import_outside_the_client_module_is_reported(self, fake_package: Path) -> None:
        (fake_package / "adapter.py").write_text(
            '"""Doc."""\n\nimport openai\n\n__all__: list[str] = []\n', encoding="utf-8"
        )

        result = dependency_boundary.check_only_client_imports_the_sdk(fake_package)

        assert not result.ok
        assert "adapter.py" in result.detail

    def test_the_sdk_import_inside_the_client_module_is_accepted(self, fake_package: Path) -> None:
        (fake_package / CREDENTIAL_BOUNDARY_MODULE).write_text(
            '"""Doc."""\n\nimport openai\n\n__all__: list[str] = []\n', encoding="utf-8"
        )

        assert dependency_boundary.check_only_client_imports_the_sdk(fake_package).ok

    def test_an_environment_read_outside_the_client_module_is_reported(
        self, fake_package: Path
    ) -> None:
        (fake_package / "configuration.py").write_text(
            '"""Doc."""\n\nimport os\n\nKEY = os.environ.get("X")\n\n__all__: list[str] = []\n',
            encoding="utf-8",
        )

        assert not dependency_boundary.check_only_client_reads_the_environment(fake_package).ok

    def test_a_networking_or_threading_import_is_reported(self, fake_package: Path) -> None:
        (fake_package / "client.py").write_text(
            '"""Doc."""\n\nimport socket\n\n__all__: list[str] = []\n', encoding="utf-8"
        )

        assert not dependency_boundary.check_no_forbidden_runtime_imports(fake_package).ok

    def test_a_sleep_call_is_reported(self, fake_package: Path) -> None:
        (fake_package / "adapter.py").write_text(
            '"""Doc."""\n\nimport time\n\ntime.sleep(1)\n\n__all__: list[str] = []\n',
            encoding="utf-8",
        )

        assert not dependency_boundary.check_adapter_never_sleeps(fake_package).ok

    def test_an_openrouter_reference_is_reported(self, fake_package: Path) -> None:
        (fake_package / "capabilities.py").write_text(
            '"""Doc about openrouter."""\n\n__all__: list[str] = []\n', encoding="utf-8"
        )

        assert not dependency_boundary.check_no_openrouter_reference(fake_package).ok

    def test_an_unwired_migrated_file_is_reported(self, tmp_path: Path) -> None:
        """An empty tree means the migrated files import no contracts at all."""

        assert not dependency_boundary.check_migrated_files_import_the_contracts(tmp_path).ok

    def test_the_legacy_and_sdk_free_checks_pass_vacuously_on_an_empty_tree(
        self, tmp_path: Path
    ) -> None:
        """Absence-based checks cannot be proven falsifiable by deletion alone.

        They are asserted against the real tree in ``test_checks.py``; here we
        only pin that a missing file is treated as importing nothing.
        """

        assert dependency_boundary._source_imports(tmp_path, "ai/providers/bedrock.py") == set()
