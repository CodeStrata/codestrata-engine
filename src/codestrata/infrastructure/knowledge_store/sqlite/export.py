"""Maintainer helper: export leftover SQLite knowledge snapshots to JSON.

Community runtime (factory, assess, compare, MCP) must not import this module.
Invoke it separately::

    python -m codestrata.infrastructure.knowledge_store.sqlite.export \\
        --sqlite .codestrata/knowledge/knowledge.sqlite \\
        --output /tmp/codestrata-sqlite-export

The helper is read-only against the SQLite file and refuses to overwrite an
existing destination. It does not migrate production FileKnowledgeStore data.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

EXPORT_SCHEMA = "codestrata-sqlite-maintainer-export:1"
_MAX_ROWS_PER_TABLE = 500
_TABLES = (
    "schema_metadata",
    "repositories",
    "repository_aliases",
    "repository_snapshots",
    "assessment_runs",
    "knowledge_artifacts",
)


class SqliteExportError(RuntimeError):
    """Structured maintainer-export failure."""


@dataclass(frozen=True, slots=True)
class SqliteExportResult:
    schema: str
    sqlite_path: str
    output_directory: str
    tables: tuple[str, ...]
    row_counts: dict[str, int]
    truncated_tables: tuple[str, ...]


def export_legacy_sqlite(*, sqlite_path: Path, output_directory: Path) -> SqliteExportResult:
    """Copy bounded table projections into a new directory. Never mutates SQLite."""

    source = sqlite_path.expanduser()
    destination = output_directory.expanduser()
    if not source.is_file():
        raise SqliteExportError(f"SQLite file not found: {source}")
    if destination.exists():
        raise SqliteExportError(
            f"refusing to overwrite existing destination: {destination}. "
            "Old files remain untouched."
        )
    destination.mkdir(parents=True, exist_ok=False)

    connection = sqlite3.connect(str(source.resolve()))
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        available = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        row_counts: dict[str, int] = {}
        truncated: list[str] = []
        exported_tables: list[str] = []
        select_sql = {
            "schema_metadata": "SELECT * FROM schema_metadata LIMIT ?",
            "repositories": "SELECT * FROM repositories LIMIT ?",
            "repository_aliases": "SELECT * FROM repository_aliases LIMIT ?",
            "repository_snapshots": "SELECT * FROM repository_snapshots LIMIT ?",
            "assessment_runs": "SELECT * FROM assessment_runs LIMIT ?",
            "knowledge_artifacts": "SELECT * FROM knowledge_artifacts LIMIT ?",
        }
        for table in _TABLES:
            if table not in available:
                continue
            rows = connection.execute(select_sql[table], (_MAX_ROWS_PER_TABLE + 1,))
            records = [dict(item) for item in rows.fetchall()]
            if len(records) > _MAX_ROWS_PER_TABLE:
                records = records[:_MAX_ROWS_PER_TABLE]
                truncated.append(table)
            target = destination / f"{table}.jsonl"
            with target.open("w", encoding="utf-8", newline="\n") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            row_counts[table] = len(records)
            exported_tables.append(table)
        manifest = {
            "schema": EXPORT_SCHEMA,
            "exported_at": datetime.now(tz=UTC).isoformat(),
            "sqlite_path": str(source),
            "tables": exported_tables,
            "row_counts": row_counts,
            "truncated_tables": truncated,
            "read_only": True,
            "mutated_source": False,
        }
        (destination / "export-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return SqliteExportResult(
            schema=EXPORT_SCHEMA,
            sqlite_path=str(source),
            output_directory=str(destination),
            tables=tuple(exported_tables),
            row_counts=row_counts,
            truncated_tables=tuple(truncated),
        )
    except sqlite3.Error as error:
        raise SqliteExportError(f"SQLite export failed: {error}") from error
    finally:
        connection.close()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Maintainer-only export of a leftover knowledge.sqlite file."
    )
    parser.add_argument("--sqlite", type=Path, required=True, help="Path to knowledge.sqlite")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New empty directory for JSON/JSONL projections",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = export_legacy_sqlite(sqlite_path=args.sqlite, output_directory=args.output)
    except SqliteExportError as error:
        print(str(error), file=sys.stderr)
        return 1
    payload = {
        "schema": result.schema,
        "sqlite_path": result.sqlite_path,
        "output_directory": result.output_directory,
        "tables": list(result.tables),
        "row_counts": result.row_counts,
        "truncated_tables": list(result.truncated_tables),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
