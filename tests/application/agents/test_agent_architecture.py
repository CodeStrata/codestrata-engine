"""Architecture boundary tests for the Agent Framework."""

from __future__ import annotations

from pathlib import Path

import codestrata.application.agents as agents_pkg


def test_agent_package_avoids_forbidden_dependencies() -> None:
    root = Path(agents_pkg.__file__).resolve().parent
    forbidden = (
        "fastmcp",
        "typer",
        "sqlite3",
        "SqliteKnowledgeStore",
        "report.json",
        "report.html",
        "subprocess",
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} unexpectedly contains {token!r}"


def test_agent_package_import_has_no_infrastructure_side_effects() -> None:
    assert agents_pkg.AgentOrchestrator is not None
    assert agents_pkg.KnowledgeAgent is not None
    assert agents_pkg.create_agent_orchestrator is not None
