"""Architecture boundary tests for knowledge query package."""

from __future__ import annotations

from pathlib import Path

import codestrata.application.knowledge.queries as queries_pkg


def test_query_package_avoids_sqlite_typer_and_reports() -> None:
    root = Path(queries_pkg.__file__).resolve().parent
    forbidden = ("sqlite3", "typer", "report.json", "report.html", "SqliteKnowledgeStore")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} unexpectedly contains {token!r}"


def test_query_service_accepts_injected_store(tmp_path: Path) -> None:
    from codestrata.application.knowledge.queries import KnowledgeQueryService
    from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore

    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        service = KnowledgeQueryService(store)
        assert service.list_repositories() == ()
