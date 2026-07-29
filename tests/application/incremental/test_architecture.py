"""Architecture boundary tests for incremental planning."""

from __future__ import annotations

from pathlib import Path

import codestrata.application.incremental as incremental_pkg


def test_incremental_package_avoids_forbidden_dependencies() -> None:
    root = Path(incremental_pkg.__file__).resolve().parent
    forbidden = (
        "fastmcp",
        "typer",
        "sqlite3",
        "SqliteKnowledgeStore",
        "report.json",
        "report.html",
        "subprocess",
        "boto3",
        "bedrock",
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} unexpectedly contains {token!r}"


def test_incremental_package_import_has_no_side_effects() -> None:
    assert incremental_pkg.IncrementalPlanningService is not None
    assert incremental_pkg.create_incremental_planning_service is not None
    assert incremental_pkg.ChangeClassifier is not None
