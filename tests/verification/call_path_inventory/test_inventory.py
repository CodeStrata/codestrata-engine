"""Independent expected fixtures for E02.2 factory composition (updates E02.1 inventory)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from verification.call_path_inventory.models import CallPathInventory
from verification.call_path_inventory.render import render_inventory
from verification.call_path_inventory.scan import (
    FACTORY_MODULE,
    FORBIDDEN_DEFAULT_PACKAGES,
    build_inventory,
    inspect_factory_runtime,
    inspect_factory_source,
)

ENGINE = Path(__file__).resolve().parents[3]
REPO = ENGINE.parent
FACTORY = ENGINE / "src" / "codestrata" / "infrastructure" / "knowledge_store" / "factory.py"
DOCS = ENGINE / "docs" / "release" / "sqlite-hosted-portfolio-call-paths.md"
SCAN = ENGINE / "verification" / "call_path_inventory"


def _inventory() -> CallPathInventory:
    return build_inventory(engine_root=ENGINE, repo_root=REPO)


@pytest.fixture(scope="module")
def inventory() -> CallPathInventory:
    return _inventory()


def test_factory_runtime_constructs_file_knowledge_store() -> None:
    assert inspect_factory_runtime() == "FileKnowledgeStore"
    imports_sqlite, annotation = inspect_factory_source(ENGINE)
    assert imports_sqlite is False
    assert annotation == "FileKnowledgeStore"
    tree = ast.parse(FACTORY.read_text(encoding="utf-8"))
    assigned = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name) and func.id == "FileKnowledgeStore":
                assigned = True
    assert assigned, "factory.py must return FileKnowledgeStore(...), not only import it"


def test_inventory_agrees_with_independent_factory_ast(
    inventory: CallPathInventory,
) -> None:
    assert inventory.factory.module == FACTORY_MODULE
    assert inventory.factory.constructs_class == "FileKnowledgeStore"
    assert inventory.factory.source_imports_sqlite_store is False


def test_default_dependencies_do_not_include_db_drivers(
    inventory: CallPathInventory,
) -> None:
    joined = " ".join(inventory.dependencies.default).lower()
    for name in FORBIDDEN_DEFAULT_PACKAGES:
        assert name not in joined
    assert inventory.dependencies.forbidden_in_default == ()
    assert inventory.dependencies.sqlite3_is_stdlib is True
    assert inventory.dependencies.mcp_is_optional_extra is True
    assert any(item.startswith("typer") for item in inventory.dependencies.default)


def test_sqlite_is_quarantined_from_community_runtime(
    inventory: CallPathInventory,
) -> None:
    sqlite_surface = next(
        item for item in inventory.surfaces if item.id == "sqlite-knowledge-store"
    )
    factory_surface = next(
        item for item in inventory.surfaces if item.id == "knowledge-store-factory-sqlite"
    )
    helper = next(item for item in inventory.surfaces if item.id == "sqlite-maintainer-export")
    empty_quarantine = next(
        item
        for item in inventory.surfaces
        if item.id == "sqlite-adapter-not-runtime-exported"
    )
    assert sqlite_surface.classification == "quarantine"
    assert sqlite_surface.in_supported_runtime is False
    assert factory_surface.classification == "retain"
    assert factory_surface.in_supported_runtime is True
    assert helper.classification == "retain"
    assert helper.in_supported_runtime is False
    assert empty_quarantine.classification == "quarantine"
    assert empty_quarantine.paths == ()
    assert empty_quarantine.in_supported_runtime is False


def test_hosted_and_portfolio_are_removed_from_community_runtime(
    inventory: CallPathInventory,
) -> None:
    hosted = next(
        item
        for item in inventory.surfaces
        if item.id == "hosted-platform-ingest-and-community-cloud"
    )
    portfolio = next(item for item in inventory.surfaces if item.id == "portfolio-eir-artifacts")
    assert hosted.classification == "quarantine"
    assert hosted.in_supported_runtime is False
    assert portfolio.classification == "quarantine"
    assert portfolio.in_supported_runtime is False
    assert inventory.hosted_modules
    assert inventory.portfolio_modules


def test_scan_compare_is_file_based_not_sqlite_factory(
    inventory: CallPathInventory,
) -> None:
    scan_surface = next(
        item for item in inventory.surfaces if item.id == "cli-scan-file-comparison"
    )
    assert scan_surface.classification == "retain"
    cli_init = (ENGINE / "src" / "codestrata" / "cli" / "__init__.py").read_text(encoding="utf-8")
    assert "ScanComparisonService" in cli_init
    assert "create_knowledge_store" not in cli_init
    agent = (ENGINE / "src" / "codestrata" / "cli" / "agent.py").read_text(encoding="utf-8")
    assert 'command("compare")' in agent
    assert "create_knowledge_query_service" in agent


def test_assess_mcp_agent_incremental_are_composition_callers(
    inventory: CallPathInventory,
) -> None:
    paths = {item.relative_path for item in inventory.composition_calls}
    assert "src/codestrata/application/assessment/service.py" in paths
    assert "src/codestrata/interfaces/mcp/factory.py" in paths
    assert "src/codestrata/cli/agent.py" in paths
    assert "src/codestrata/application/incremental/factory.py" in paths
    assert "src/codestrata/cli/incremental.py" in paths
    names_by_path = {item.relative_path: set(item.names) for item in inventory.composition_calls}
    factory_path = "src/codestrata/infrastructure/knowledge_store/factory.py"
    assert "create_knowledge_store" in names_by_path[factory_path]


def test_persisted_snapshot_layout_records_file_factory(
    inventory: CallPathInventory,
) -> None:
    assert inventory.snapshots.database_filename.startswith("(none;")
    assert inventory.snapshots.knowledge_directory == ".codestrata/knowledge"
    assert inventory.snapshots.schema_version == 1
    assert "findings" in inventory.snapshots.blob_kinds
    assert any("FileKnowledgeStore" in note for note in inventory.snapshots.layout_notes)


def test_platform_consumers_recorded_before_narrowing(
    inventory: CallPathInventory,
) -> None:
    if not (REPO / "platform").is_dir():
        pytest.skip("platform tree not present in this checkout")
    modules = {hit.module for hit in inventory.platform_consumers}
    assert "codestrata.infrastructure.knowledge_store" in modules
    assert any(item.startswith("codestrata.application.knowledge") for item in modules)
    assert any(hit.relative_path.startswith("platform/") for hit in inventory.platform_consumers)
    assert inventory.vscode_python_codestrata_imports == 0
    assert inventory.workers_codestrata_imports == 0


def test_outside_engine_consumers_record_breaking_sqlite_export(
    inventory: CallPathInventory,
) -> None:
    """Identify Platform breakage; do not edit outside engine/."""

    if not (REPO / "platform").is_dir():
        pytest.skip("platform tree not present in this checkout")
    hits = [
        hit
        for hit in inventory.platform_consumers
        if hit.module == "codestrata.infrastructure.knowledge_store"
    ]
    assert hits
    sample = REPO / hits[0].relative_path
    text = sample.read_text(encoding="utf-8")
    assert "codestrata.infrastructure.knowledge_store" in text


def test_docs_inventory_matches_live_scan(inventory: CallPathInventory) -> None:
    rendered = render_inventory(inventory)
    assert DOCS.is_file()
    assert DOCS.read_text(encoding="utf-8") == rendered
    assert "FileKnowledgeStore" in rendered
    assert "quarantine" in rendered


def test_missing_factory_source_is_error(tmp_path: Path) -> None:
    empty_engine = tmp_path / "engine"
    (empty_engine / "src" / "codestrata" / "infrastructure" / "knowledge_store").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="missing factory source"):
        inspect_factory_source(empty_engine)


def test_scanner_does_not_write_platform_or_workers(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    platform = repo / "platform" / "pkg"
    workers = repo / "workers"
    platform.mkdir(parents=True)
    workers.mkdir()
    marker = platform / "keep.py"
    original = "from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore\n"
    marker.write_text(original, encoding="utf-8")
    (workers / "noop.txt").write_text("stay\n", encoding="utf-8")
    from verification.engine_scope.consumer_imports import collect_consumer_imports

    records = collect_consumer_imports(repo, consumer_roots=("platform", "workers"))
    assert records
    assert marker.read_text(encoding="utf-8") == original
    assert (workers / "noop.txt").read_text(encoding="utf-8") == "stay\n"


def test_package_is_not_in_wheel_payload() -> None:
    pyproject = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["codestrata*"]' in pyproject
    assert not (ENGINE / "src" / "codestrata" / "verification" / "call_path_inventory").exists()
    assert SCAN.is_dir()
