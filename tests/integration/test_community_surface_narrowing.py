"""E02.3 Community surface narrowing: hosted, portfolio, SQLite helper, CLI/MCP."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.artifacts.lifecycle import LifecycleError, promote_intelligence_run
from codestrata.artifacts.lifecycle_migration import migrate_intelligence_run_folders
from codestrata.artifacts.portfolio_identity import resolve_portfolio_artifact_id
from codestrata.cli.report import report_app
from codestrata.cli.rules import rules_app
from codestrata.community_cloud.report_publishing import (
    ReportPublishError,
    publish_local_assessment,
    publish_local_eir,
)
from codestrata.config import PlatformIntegrationSettings
from codestrata.infrastructure.knowledge_store import create_knowledge_store
from codestrata.infrastructure.knowledge_store.sqlite.export import (
    EXPORT_SCHEMA,
    SqliteExportError,
    export_legacy_sqlite,
)
from codestrata.infrastructure.knowledge_store.sqlite.export import (
    main as sqlite_export_main,
)
from codestrata.integration.commercial.client import OfflinePlatformClient, RestPlatformClient
from codestrata.integration.commercial.configuration import platform_client_from_settings
from codestrata.integration.community_runtime import (
    CUSTOMER_RULE_AUTHORING_REMOVED,
    PORTFOLIO_LIFECYCLE_REMOVED,
)


def test_sqlite_is_lazy_compatibility_export() -> None:
    from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
    from codestrata.infrastructure.knowledge_store.factory import create_knowledge_store

    assert SqliteKnowledgeStore.__name__ == "SqliteKnowledgeStore"
    assert type(create_knowledge_store()).__name__ == "FileKnowledgeStore"


def test_factory_does_not_import_sqlite_export() -> None:
    factory = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "codestrata"
        / "infrastructure"
        / "knowledge_store"
        / "factory.py"
    )
    text = factory.read_text(encoding="utf-8")
    assert "sqlite.export" not in text
    assert "export_legacy_sqlite" not in text
    store = create_knowledge_store()
    assert type(store).__name__ == "FileKnowledgeStore"


def test_sqlite_export_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SqliteExportError, match="not found"):
        export_legacy_sqlite(
            sqlite_path=tmp_path / "missing.sqlite",
            output_directory=tmp_path / "out",
        )


def test_sqlite_export_refuses_overwrite_and_does_not_mutate_source(tmp_path: Path) -> None:
    db = tmp_path / "knowledge.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE schema_metadata (key TEXT, value TEXT)")
    connection.execute("INSERT INTO schema_metadata VALUES ('schema_version', '3')")
    connection.commit()
    connection.close()
    original = db.read_bytes()
    destination = tmp_path / "export"
    destination.mkdir()
    (destination / "keep.txt").write_text("stay\n", encoding="utf-8")
    with pytest.raises(SqliteExportError, match="refusing to overwrite"):
        export_legacy_sqlite(sqlite_path=db, output_directory=destination)
    assert db.read_bytes() == original
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "stay\n"


def test_sqlite_export_writes_bounded_jsonl_and_main_exit(tmp_path: Path) -> None:
    db = tmp_path / "knowledge.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE repositories (repository_id TEXT, display_name TEXT)")
    connection.execute("INSERT INTO repositories VALUES ('r1', 'one')")
    connection.commit()
    connection.close()
    out = tmp_path / "export"
    result = export_legacy_sqlite(sqlite_path=db, output_directory=out)
    assert result.schema == EXPORT_SCHEMA
    assert result.row_counts["repositories"] == 1
    assert result.truncated_tables == ()
    lines = (out / "repositories.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["repository_id"] == "r1"
    manifest = json.loads((out / "export-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mutated_source"] is False
    assert sqlite_export_main(["--sqlite", str(db), "--output", str(tmp_path / "second")]) == 0
    missing = sqlite_export_main(
        ["--sqlite", str(tmp_path / "nope.sqlite"), "--output", str(tmp_path / "x")]
    )
    assert missing == 1


def test_sqlite_export_truncates_over_budget(tmp_path: Path) -> None:
    db = tmp_path / "knowledge.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE repositories (repository_id TEXT)")
    connection.executemany(
        "INSERT INTO repositories VALUES (?)",
        [(f"r{i}",) for i in range(501)],
    )
    connection.commit()
    connection.close()
    result = export_legacy_sqlite(sqlite_path=db, output_directory=tmp_path / "export")
    assert result.row_counts["repositories"] == 500
    assert "repositories" in result.truncated_tables


def test_promote_intelligence_refuses_and_leaves_existing_tree(tmp_path: Path) -> None:
    pid = resolve_portfolio_artifact_id(suite_id="sv17-13")
    existing = tmp_path / ".codestrata-artifacts" / "intelligence" / pid / "current"
    existing.mkdir(parents=True)
    marker = existing / "engineering-intelligence-report.json"
    marker.write_text('{"keep":true}\n', encoding="utf-8")
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(LifecycleError, match="Portfolio"):
        promote_intelligence_run(portfolio_id=pid, staging_directory=staging, base=tmp_path)
    assert marker.read_text(encoding="utf-8") == '{"keep":true}\n'
    assert PORTFOLIO_LIFECYCLE_REMOVED


def test_intelligence_migration_skips_without_deleting(tmp_path: Path) -> None:
    leftover = (
        tmp_path / ".codestrata-artifacts" / "intelligence" / "release-validation" / "old-run"
    )
    leftover.mkdir(parents=True)
    (leftover / "engineering-intelligence-report.json").write_text("{}\n", encoding="utf-8")
    result = migrate_intelligence_run_folders(workspace=tmp_path)
    assert result.intelligence_skipped == 1
    assert result.intelligence_migrated == 0
    assert leftover.is_dir()


def test_rest_client_remains_importable_projection() -> None:
    assert RestPlatformClient.__name__ == "RestPlatformClient"

    class Settings:
        platform = PlatformIntegrationSettings(enabled=True)

    assert isinstance(platform_client_from_settings(Settings()), OfflinePlatformClient)


def test_community_cloud_publish_refuses(tmp_path: Path) -> None:
    current = tmp_path / "current"
    current.mkdir()
    (current / "assessment.html").write_text("<html></html>", encoding="utf-8")
    (current / "assessment.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ReportPublishError, match="deprecated"):
        publish_local_assessment(
            current_dir=current,
            logical_repository_id="local-demo",
            private_repository_acknowledged=True,
            confirm_public_publish=True,
        )
    with pytest.raises(ReportPublishError, match="deprecated"):
        publish_local_eir(
            current_dir=current,
            portfolio_id="release-validation",
            confirm_public_publish=True,
        )
    assert (current / "assessment.html").is_file()


def test_cli_report_publish_is_deprecated() -> None:
    runner = CliRunner()
    result = runner.invoke(report_app, ["publish", "--confirm-public-publish"])
    assert result.exit_code == 2
    combined = result.stdout + result.stderr
    assert "deprecated" in combined.lower()
    help_result = runner.invoke(report_app, ["publish", "--help"])
    assert help_result.exit_code == 0
    assert "deprecated" in help_result.stdout.lower()


def test_cli_rules_are_read_only() -> None:
    commands = {item.name for item in rules_app.registered_commands}
    assert commands == {"list", "inspect", "explain"}
    forbidden = {"create", "write", "add", "author", "edit", "save", "delete", "publish"}
    assert not (commands & forbidden)
    assert CUSTOMER_RULE_AUTHORING_REMOVED


def test_mcp_rule_tools_are_read_only() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "codestrata"
        / "interfaces"
        / "mcp"
        / "tools"
        / "rules.py"
    )
    text = source.read_text(encoding="utf-8")
    assert 'name="list_shared_rules"' in text
    assert 'name="get_shared_rule"' in text
    assert "write_shared_rule" not in text
    assert "create_shared_rule" not in text
    assert "author_rule" not in text


def test_sqlite_export_module_invoked_as_separate_process(tmp_path: Path) -> None:
    from codestrata.application.process_launch import child_process_env

    db = tmp_path / "knowledge.sqlite"
    sqlite3.connect(db).close()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "codestrata.infrastructure.knowledge_store.sqlite.export",
            "--sqlite",
            str(db),
            "--output",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=child_process_env(),
    )
    assert completed.returncode == 0
    assert "codestrata-sqlite-maintainer-export:1" in completed.stdout
