"""CLI: ``python -m verification.call_path_inventory``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.call_path_inventory.render import render_inventory
from verification.call_path_inventory.scan import build_inventory


def _repo_root_from_cwd() -> Path:
    cwd = Path.cwd()
    if cwd.name == "engine":
        return cwd.parent
    return cwd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E02.1 SQLite / hosted / portfolio call-path inventory (read-only).",
    )
    parser.add_argument("--repo-root", type=Path, default=_repo_root_from_cwd())
    parser.add_argument(
        "--write-docs",
        type=Path,
        default=None,
        help="Write Markdown inventory (default path used when flag is given without a file).",
        nargs="?",
        const=Path("engine/docs/release/sqlite-hosted-portfolio-call-paths.md"),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    engine_root = repo_root / "engine"
    inventory = build_inventory(engine_root=engine_root, repo_root=repo_root)
    if args.write_docs is not None:
        target = args.write_docs
        if not target.is_absolute():
            target = repo_root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_inventory(inventory), encoding="utf-8")
    if args.json:
        payload = {
            "factory_constructs": inventory.factory.constructs_class,
            "source_imports_sqlite_store": inventory.factory.source_imports_sqlite_store,
            "composition_call_count": len(inventory.composition_calls),
            "sqlite3_module_count": len(inventory.sqlite3_production_modules),
            "hosted_module_count": len(inventory.hosted_modules),
            "portfolio_module_count": len(inventory.portfolio_modules),
            "platform_consumer_count": len(inventory.platform_consumers),
            "vscode_python_codestrata_imports": inventory.vscode_python_codestrata_imports,
            "workers_codestrata_imports": inventory.workers_codestrata_imports,
            "forbidden_default_drivers": list(inventory.dependencies.forbidden_in_default),
            "surfaces": [
                {
                    "id": surface.id,
                    "classification": surface.classification,
                    "in_supported_runtime": surface.in_supported_runtime,
                    "in_default_dependency_closure": surface.in_default_dependency_closure,
                }
                for surface in inventory.surfaces
            ],
            "read_only": inventory.read_only,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_inventory(inventory))
    if inventory.factory.constructs_class != "FileKnowledgeStore":
        return 1
    if inventory.dependencies.forbidden_in_default:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
