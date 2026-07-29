"""Additional MCP execution and CLI smoke tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from typer.testing import CliRunner

from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.cli import app
from codestrata.config import CodestrataSettings
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.interfaces.mcp import create_mcp_server


def test_mcp_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "serve" in result.stdout


def test_run_assessment_mcp_tool(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "README.md").write_text("# sample\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name":"sample"}\n', encoding="utf-8")
    knowledge_dir = tmp_path / "knowledge"
    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
[repository]
path = "{repo}"

[workspace]
directory = ".codestrata-workspace"

[knowledge]
directory = "{knowledge_dir}"

[static_analysis]
enabled = false

[ai.bedrock]

[mcp]
enabled = true
transport = "stdio"
log_level = "WARNING"
""",
        encoding="utf-8",
    )
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "workspace": {"directory": ".codestrata-workspace"},
            "knowledge": {"directory": str(knowledge_dir)},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
            "mcp": {"enabled": True},
        }
    )

    with SqliteKnowledgeStore(knowledge_dir) as store:
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
            settings=settings,
        )

        async def _run() -> None:
            result = await server.call_tool(
                "run_assessment",
                {
                    "repository": str(repo),
                    "with_ai": False,
                    "config_path": str(config),
                },
            )
            payload = result[1] if isinstance(result, tuple) else None
            assert payload is not None
            assert payload["status"] == "completed"
            assert payload["run_id"]
            assert payload["repository_id"]
            assert payload["snapshot_id"]
            assert "blob_ref" not in str(payload)

        asyncio.run(_run())
