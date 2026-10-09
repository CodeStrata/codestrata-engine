"""Read-only inventory of outside-Engine Python imports of ``codestrata``."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONSUMER_ROOTS: tuple[str, ...] = (
    "platform",
    "vscode-plugin",
    "infrastructure",
    "verification",
)

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        ".venv-engine-next",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
    }
)


@dataclass(frozen=True, slots=True)
class ConsumerImport:
    consumer_root: str
    relative_path: str
    module: str
    lineno: int


def _iter_python_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return tuple(sorted(files))


def _modules_from_ast(tree: ast.AST) -> tuple[tuple[str, int], ...]:
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "codestrata" or name.startswith("codestrata."):
                    found.append((name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "codestrata" or module.startswith("codestrata."):
                found.append((module, node.lineno))
    return tuple(found)


def collect_consumer_imports(
    repo_root: Path,
    *,
    consumer_roots: tuple[str, ...] = DEFAULT_CONSUMER_ROOTS,
) -> tuple[ConsumerImport, ...]:
    """List ``import codestrata`` / ``from codestrata...`` in other packages.

    Read-only: open and parse only. Syntax errors are skipped, not rewritten.
    This is a compatibility *observation* for E00.2, not an E01 contract freeze.
    """

    records: list[ConsumerImport] = []
    for root_name in consumer_roots:
        consumer_dir = repo_root / root_name
        for file_path in _iter_python_files(consumer_dir):
            try:
                source = file_path.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                tree = ast.parse(source, filename=str(file_path))
            except SyntaxError:
                continue
            relative = file_path.relative_to(repo_root).as_posix()
            for module, lineno in _modules_from_ast(tree):
                records.append(
                    ConsumerImport(
                        consumer_root=root_name,
                        relative_path=relative,
                        module=module,
                        lineno=lineno,
                    )
                )
    return tuple(records)


def summarize_imports(records: tuple[ConsumerImport, ...]) -> dict[str, object]:
    modules = sorted({item.module for item in records})
    by_root: dict[str, int] = {}
    for item in records:
        by_root[item.consumer_root] = by_root.get(item.consumer_root, 0) + 1
    return {
        "import_count": len(records),
        "unique_modules": modules,
        "counts_by_consumer_root": by_root,
        "read_only": True,
    }
