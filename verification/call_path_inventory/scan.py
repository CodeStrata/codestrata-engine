"""Inspect live Engine composition for SQLite, hosted, and portfolio paths."""

from __future__ import annotations

import ast
import sys
import tomllib
from importlib import import_module
from pathlib import Path

from verification.call_path_inventory.models import (
    CallPathInventory,
    CompositionCall,
    ConsumerHit,
    DependencyInventory,
    FactoryComposition,
    SnapshotLayout,
    Surface,
)
from verification.engine_scope.consumer_imports import collect_consumer_imports

FACTORY_MODULE = "codestrata.infrastructure.knowledge_store.factory"
FACTORY_SOURCE = Path("src/codestrata/infrastructure/knowledge_store/factory.py")

COMPOSITION_NAMES = frozenset(
    {
        "create_knowledge_store",
        "create_knowledge_query_service",
        "open_knowledge_store",
        "open_default_knowledge_store",
        "SqliteKnowledgeStore",
        "FileKnowledgeStore",
        "open_file_knowledge_store",
    }
)

HOSTED_MARKERS = frozenset(
    {
        "RestPlatformClient",
        "publish_assessment_to_platform",
        "publish_artifacts_to_platform",
        "platform_client_from_settings",
        "publish_local_eir",
        "resolve_public_community_api_base",
    }
)

PORTFOLIO_MARKERS = frozenset(
    {
        "resolve_portfolio_artifact_id",
        "sanitize_portfolio_id",
        "is_logical_portfolio_id",
        "validate_eir_bundle",
        "intelligence_logical_directory",
    }
)

FORBIDDEN_DEFAULT_PACKAGES = (
    "sqlalchemy",
    "aiosqlite",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "redis",
    "pgvector",
)

CONSUMER_MODULE_PREFIXES = (
    "codestrata.infrastructure.knowledge_store",
    "codestrata.application.knowledge",
    "codestrata.integration.commercial",
    "codestrata.artifacts",
    "codestrata.community_cloud",
)

_SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv"}
)


def _parse_py(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None


def _imported_and_called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
    return names


def _iter_engine_python(engine_root: Path) -> tuple[Path, ...]:
    src = engine_root / "src" / "codestrata"
    files: list[Path] = []
    for path in src.rglob("*.py"):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return tuple(sorted(files))


def _relative_engine(engine_root: Path, path: Path) -> str:
    return path.resolve().relative_to(engine_root.resolve()).as_posix()


def inspect_factory_source(engine_root: Path) -> tuple[bool, str | None]:
    path = engine_root / FACTORY_SOURCE
    tree = _parse_py(path)
    if tree is None:
        raise FileNotFoundError(f"missing factory source: {path}")
    imports_sqlite = False
    return_annotation: str | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.endswith("sqlite.store"):
                if any(alias.name == "SqliteKnowledgeStore" for alias in node.names):
                    imports_sqlite = True
        if isinstance(node, ast.FunctionDef) and node.name == "create_knowledge_store":
            if node.returns is not None:
                return_annotation = ast.unparse(node.returns)
    return imports_sqlite, return_annotation


def inspect_factory_runtime() -> str:
    factory = import_module(FACTORY_MODULE)
    store = factory.create_knowledge_store()
    try:
        return type(store).__name__
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def collect_composition_calls(engine_root: Path) -> tuple[CompositionCall, ...]:
    calls: list[CompositionCall] = []
    for path in _iter_engine_python(engine_root):
        tree = _parse_py(path)
        if tree is None:
            continue
        names = tuple(sorted(_imported_and_called_names(tree) & COMPOSITION_NAMES))
        if not names:
            continue
        calls.append(
            CompositionCall(relative_path=_relative_engine(engine_root, path), names=names)
        )
    return tuple(calls)


def collect_marker_modules(
    engine_root: Path,
    markers: frozenset[str],
) -> tuple[str, ...]:
    found: list[str] = []
    for path in _iter_engine_python(engine_root):
        tree = _parse_py(path)
        if tree is None:
            continue
        names = _imported_and_called_names(tree)
        if names & markers:
            found.append(_relative_engine(engine_root, path))
    return tuple(found)


def collect_sqlite3_modules(engine_root: Path) -> tuple[str, ...]:
    found: list[str] = []
    for path in _iter_engine_python(engine_root):
        tree = _parse_py(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] == "sqlite3" for alias in node.names):
                    found.append(_relative_engine(engine_root, path))
                    break
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "sqlite3":
                found.append(_relative_engine(engine_root, path))
                break
    return tuple(found)


def _requirement_name(spec: str) -> str:
    token = spec.strip()
    for separator in ("[", ">", "<", "=", "!", "~", " "):
        if separator in token:
            token = token.split(separator, 1)[0]
    return token.strip().lower()


def inspect_dependencies(engine_root: Path) -> DependencyInventory:
    pyproject = engine_root / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]
    default = tuple(str(item) for item in project.get("dependencies", ()))
    extras_raw = project.get("optional-dependencies", {})
    extras = {str(name): tuple(str(item) for item in values) for name, values in extras_raw.items()}
    default_names = {_requirement_name(item) for item in default}
    present_forbidden = tuple(name for name in FORBIDDEN_DEFAULT_PACKAGES if name in default_names)
    mcp_extra = "mcp" in extras
    return DependencyInventory(
        default=default,
        extras=extras,
        forbidden_in_default=present_forbidden,
        sqlite3_is_stdlib="sqlite3" in sys.stdlib_module_names,
        mcp_is_optional_extra=mcp_extra,
    )


def inspect_snapshots() -> SnapshotLayout:
    defaults = import_module("codestrata.infrastructure.knowledge_store.defaults")
    file_layout = import_module("codestrata.infrastructure.knowledge_store.file.layout")
    kinds = tuple(sorted(defaults.BLOB_KIND_DIRECTORIES))
    return SnapshotLayout(
        knowledge_directory=str(defaults.DEFAULT_KNOWLEDGE_DIRECTORY).replace("\\", "/"),
        database_filename="(none; legacy knowledge.sqlite is left untouched)",
        schema_version=int(file_layout.FILE_STORE_SCHEMA_VERSION),
        blob_kinds=kinds,
        layout_notes=(
            "production factory constructs FileKnowledgeStore (JSON/JSONL)",
            "repositories/{id}/{repository.json,aliases.json,snapshots/,runs/}",
            "indexes/{repositories,aliases,snapshots,runs}.jsonl (derived, bounded)",
            "locks/",
            "blobs/{manifests,graphs,findings,recommendations,ai}/",
            "tmp/",
            "knowledge.sqlite leftover in defaults; factory does not open it",
            "assessment reports remain under .codestrata-artifacts/assessments",
            "legacy intelligence/<portfolio_id>/ trees are left untouched",
        ),
    )


def _relevant_consumer(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".") for prefix in CONSUMER_MODULE_PREFIXES
    )


def count_root_codestrata_imports(repo_root: Path, consumer_root: str) -> int:
    return len(collect_consumer_imports(repo_root, consumer_roots=(consumer_root,)))


def classified_surfaces(
    *,
    engine_root: Path,
    factory: FactoryComposition,
    composition_calls: tuple[CompositionCall, ...],
    sqlite3_modules: tuple[str, ...],
    hosted_modules: tuple[str, ...],
    portfolio_modules: tuple[str, ...],
    dependencies: DependencyInventory,
) -> tuple[Surface, ...]:
    """Classify inspected surfaces after E02.3 Community narrowing."""

    file_in_runtime = factory.constructs_class == "FileKnowledgeStore"
    sqlite_in_runtime = factory.constructs_class == "SqliteKnowledgeStore"
    configuration = (
        engine_root / "src" / "codestrata" / "integration" / "commercial" / "configuration.py"
    )
    configuration_text = ""
    if configuration.is_file():
        configuration_text = configuration.read_text(encoding="utf-8")
    hosted_in_runtime = "RestPlatformClient(" in configuration_text
    lifecycle = engine_root / "src" / "codestrata" / "artifacts" / "lifecycle.py"
    lifecycle_text = lifecycle.read_text(encoding="utf-8") if lifecycle.is_file() else ""
    portfolio_lifecycle_active = "PORTFOLIO_LIFECYCLE_REMOVED" not in lifecycle_text
    export_module = "src/codestrata/infrastructure/knowledge_store/sqlite/export.py"
    return (
        Surface(
            id="knowledge-ports-and-queries",
            classification="retain",
            summary=(
                "Application KnowledgeStore protocol, query service, session and "
                "staged artifact models stay as the Engine-local contract. E02.2 "
                "replaced the production adapter; ports remain."
            ),
            paths=(
                "src/codestrata/application/knowledge/ports.py",
                "src/codestrata/application/knowledge/queries/service.py",
                "src/codestrata/application/knowledge/session.py",
                "src/codestrata/application/knowledge/persistence.py",
                "src/codestrata/application/knowledge/models.py",
            ),
            in_supported_runtime=True,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="knowledge-store-factory-sqlite",
            classification="retain",
            summary=(
                f"{FACTORY_MODULE}.create_knowledge_store currently constructs "
                f"{factory.constructs_class}. Production composition, not a dead import."
            ),
            paths=(FACTORY_SOURCE.as_posix(),),
            in_supported_runtime=file_in_runtime,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="sqlite-knowledge-store",
            classification="quarantine",
            summary=(
                "SQLite adapter is not factory-composed. A lazy compatibility export "
                "exists for Platform tests. A separately invoked maintainer helper "
                "(`python -m codestrata.infrastructure.knowledge_store.sqlite.export`) "
                "may read leftover knowledge.sqlite files. Community runtime does not "
                "import the helper."
            ),
            paths=sqlite3_modules,
            in_supported_runtime=sqlite_in_runtime,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="sqlite-maintainer-export",
            classification="retain",
            summary=(
                "Legacy SQLite JSON/JSONL export is a maintainer helper only. It is "
                "never imported by create_knowledge_store, assess, compare, or MCP."
            ),
            paths=(export_module,),
            in_supported_runtime=False,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="cli-assess-mcp-agent-incremental-onboard",
            classification="adapt",
            summary=(
                "CLI assess, MCP server factory, agent, incremental and onboard "
                "compose through create_knowledge_store / create_knowledge_query_service. "
                "codestrata scan comparison writes file reports and does not open SQLite."
            ),
            paths=tuple(item.relative_path for item in composition_calls),
            in_supported_runtime=True,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="cli-scan-file-comparison",
            classification="retain",
            summary=(
                "codestrata scan uses ScanComparisonService against file reports. "
                "It does not call create_knowledge_store. codestrata agent compare "
                "reads knowledge snapshots through the query service (file store today)."
            ),
            paths=(
                "src/codestrata/cli/__init__.py",
                "src/codestrata/services/scan_comparison_service.py",
                "src/codestrata/cli/agent.py",
            ),
            in_supported_runtime=True,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="offline-platform-client-default",
            classification="retain",
            summary=(
                "platform_client_from_settings always returns OfflinePlatformClient. "
                "Local assess/compare/MCP stay no-consent without hosted calls."
            ),
            paths=(
                "src/codestrata/integration/commercial/configuration.py",
                "src/codestrata/integration/commercial/client.py",
            ),
            in_supported_runtime=True,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="hosted-platform-ingest-and-community-cloud",
            classification="quarantine",
            summary=(
                "Community composition never constructs RestPlatformClient. "
                "publish_assessment_to_platform and publish_artifacts_to_platform return "
                "status=removed. codestrata report publish and Community Cloud upload "
                "functions refuse hosted submission. RestPlatformClient remains importable "
                "as a compatibility projection for outside-Engine hosts."
            ),
            paths=hosted_modules,
            in_supported_runtime=hosted_in_runtime,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="portfolio-eir-artifacts",
            classification="quarantine",
            summary=(
                "promote_intelligence_run refuses Community portfolio/EIR lifecycle. "
                "Identity helpers remain as read-only compatibility projections. "
                "Existing intelligence/ files are not migrated or deleted."
            ),
            paths=portfolio_modules,
            in_supported_runtime=portfolio_lifecycle_active,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="knowledge-vector-store-pgvector-settings",
            classification="deprecate",
            summary=(
                "KnowledgeSettings.vector_store allows provider=pgvector and "
                "CODESTRATA_DATABASE_URL. No Engine pgvector adapter module exists; "
                "the setting is still loaded with every CodestrataSettings parse so "
                "it is not isolated from the default package."
            ),
            paths=("src/codestrata/config/settings.py",),
            in_supported_runtime=True,
            in_default_dependency_closure=True,
        ),
        Surface(
            id="optional-mcp-extra",
            classification="retain",
            summary=(
                "MCP is an optional extra. Default wheel dependencies do not include mcp. "
                "When installed, create_mcp_server still opens the factory knowledge store."
            ),
            paths=("pyproject.toml", "src/codestrata/interfaces/mcp/factory.py"),
            in_supported_runtime=dependencies.mcp_is_optional_extra,
            in_default_dependency_closure=False,
        ),
        Surface(
            id="sqlite-adapter-not-runtime-exported",
            classification="quarantine",
            summary=(
                "SqliteKnowledgeStore is a lazy compatibility projection, not "
                "factory-composed. Tests may import it from the package. Community "
                "runtime composition uses FileKnowledgeStore."
            ),
            paths=(),
            in_supported_runtime=False,
            in_default_dependency_closure=False,
        ),
    )


def build_inventory(*, engine_root: Path, repo_root: Path) -> CallPathInventory:
    imports_sqlite, return_annotation = inspect_factory_source(engine_root)
    constructs = inspect_factory_runtime()
    factory = FactoryComposition(
        constructs_class=constructs,
        source_imports_sqlite_store=imports_sqlite,
        return_annotation=return_annotation,
        module=FACTORY_MODULE,
    )
    composition_calls = collect_composition_calls(engine_root)
    sqlite3_modules = collect_sqlite3_modules(engine_root)
    hosted_modules = collect_marker_modules(engine_root, HOSTED_MARKERS)
    portfolio_modules = collect_marker_modules(engine_root, PORTFOLIO_MARKERS)
    dependencies = inspect_dependencies(engine_root)
    snapshots = inspect_snapshots()
    all_consumer_records = collect_consumer_imports(repo_root)
    consumers = tuple(
        ConsumerHit(
            consumer_root=item.consumer_root,
            relative_path=item.relative_path,
            module=item.module,
            lineno=item.lineno,
        )
        for item in all_consumer_records
        if _relevant_consumer(item.module)
    )
    vscode_count = sum(1 for item in all_consumer_records if item.consumer_root == "vscode-plugin")
    workers_count = count_root_codestrata_imports(repo_root, "workers")
    surfaces = classified_surfaces(
        engine_root=engine_root,
        factory=factory,
        composition_calls=composition_calls,
        sqlite3_modules=sqlite3_modules,
        hosted_modules=hosted_modules,
        portfolio_modules=portfolio_modules,
        dependencies=dependencies,
    )
    return CallPathInventory(
        factory=factory,
        composition_calls=composition_calls,
        sqlite3_production_modules=sqlite3_modules,
        hosted_modules=hosted_modules,
        portfolio_modules=portfolio_modules,
        dependencies=dependencies,
        snapshots=snapshots,
        platform_consumers=consumers,
        vscode_python_codestrata_imports=vscode_count,
        workers_codestrata_imports=workers_count,
        surfaces=surfaces,
    )
