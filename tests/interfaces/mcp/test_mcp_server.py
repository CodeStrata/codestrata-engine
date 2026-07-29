"""MCP server and tool tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.cli.assess import run_assessment
from codestrata.config import CodestrataSettings
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.interfaces.mcp import CODESSTRATA_MCP_NAME, create_mcp_server
from codestrata.reporting import AssessmentMode
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
    seed_completed_assessment,
)


def _settings(repo_path: Path, knowledge_dir: Path) -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo_path)},
            "workspace": {"directory": ".codestrata-workspace"},
            "knowledge": {"directory": str(knowledge_dir)},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
            "mcp": {"enabled": True, "transport": "stdio", "log_level": "WARNING"},
        }
    )


async def _call(server: Any, name: str, arguments: dict[str, Any] | None = None) -> Any:
    result = await server.call_tool(name, arguments or {})
    if isinstance(result, tuple):
        structured = result[1]
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    if isinstance(result, list) and result:
        return json.loads(result[0].text)
    return result


def test_mcp_package_architecture_boundaries() -> None:
    root = Path(__file__).resolve().parents[3] / "src" / "codestrata" / "interfaces" / "mcp"
    forbidden = ("sqlite3", "SqliteKnowledgeStore", "report.json", "report.html")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden token {token!r}"


def test_server_factory_registers_expected_surface(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
        )
        assert server.name == CODESSTRATA_MCP_NAME

        async def _check() -> None:
            tools = {tool.name for tool in await server.list_tools()}
            assert "list_repositories" in tools
            assert "run_assessment" in tools
            assert "explain_finding" in tools
            prompts = {prompt.name for prompt in await server.list_prompts()}
            assert "review_repository" in prompts
            resources = [str(item.uri) for item in await server.list_resources()]
            assert "codestrata://repositories" in resources

        asyncio.run(_check())


def test_repository_and_assessment_tools(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id, run_id, snapshot_id, finding, recommendation = seed_completed_assessment(
            store,
            display_name="alpha",
            github_url="https://github.com/acme/alpha.git",
        )
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
        )

        async def _check() -> None:
            listed = await _call(server, "list_repositories", {"limit": 10})
            assert listed["returned_count"] == 1
            assert "local_path" not in listed["items"][0]
            by_key = await _call(
                server,
                "get_repository",
                {"repository_identifier": "github:acme/alpha"},
            )
            assert by_key["repository_id"] == repo_id
            assessments = await _call(
                server,
                "list_assessments",
                {"repository_identifier": repo_id, "limit": 10},
            )
            assert assessments["items"][0]["run_id"] == run_id
            latest = await _call(
                server,
                "get_latest_assessment",
                {"repository_identifier": repo_id},
            )
            assert latest["present"] is True
            assert latest["assessment"]["status"] == "completed"
            snapshot = await _call(server, "get_snapshot", {"snapshot_id": snapshot_id})
            assert snapshot["snapshot_id"] == snapshot_id
            findings = await _call(server, "list_findings", {"run_id": run_id})
            assert findings["items"][0]["finding_id"] == finding.id
            assert findings["items"][0]["finding_id"].startswith("finding:")
            explained = await _call(
                server,
                "explain_finding",
                {"run_id": run_id, "finding_id": finding.id},
            )
            assert explained["rule_id"] == "rule.demo"
            recs = await _call(server, "list_recommendations", {"run_id": run_id})
            assert recs["items"][0]["recommendation_id"] == recommendation.id
            components = await _call(
                server,
                "list_components",
                {"run_id": run_id, "component_type": "module"},
            )
            assert components["returned_count"] >= 1
            component_id = components["items"][0]["component_id"]
            deps = await _call(
                server,
                "get_component_dependencies",
                {
                    "run_id": run_id,
                    "component_id": component_id,
                    "direction": "outgoing",
                    "depth": 2,
                },
            )
            assert "dependencies" in deps
            absent = await _call(server, "get_ai_enrichment", {"run_id": run_id})
            assert absent["present"] is False

        asyncio.run(_check())


def test_snapshot_comparison_tool(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        from codestrata.application.knowledge.models import RepositoryIdentityHints
        from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType

        repo = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="cmp",
                source_location="https://github.com/acme/cmp.git",
            )
        )
        previous_manifest = make_manifest(
            key="cmp",
            files=(("README.md", "a" * 64, 10), ("old.txt", "b" * 64, 5)),
        )
        current_manifest = make_manifest(
            key="cmp",
            files=(("README.md", "d" * 64, 11), ("new.txt", "e" * 64, 4)),
        )
        previous = store.snapshots.create_or_get_snapshot(
            repository_id=repo.repository_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="1",
            manifest=previous_manifest,
            content_fingerprint=fingerprint_for(previous_manifest),
        )
        current = store.snapshots.create_or_get_snapshot(
            repository_id=repo.repository_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="2",
            manifest=current_manifest,
            content_fingerprint=fingerprint_for(current_manifest),
        )
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
        )

        async def _check() -> None:
            comparison = await _call(
                server,
                "compare_snapshots",
                {
                    "previous_snapshot_id": previous.snapshot_id,
                    "current_snapshot_id": current.snapshot_id,
                },
            )
            assert comparison["counts"]["added"] == 1
            assert comparison["counts"]["deleted"] == 1
            assert comparison["counts"]["modified"] == 1
            assert comparison["renamed_files"] == []

        asyncio.run(_check())


def test_unknown_repository_is_safe_tool_error(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
        )

        async def _check() -> None:
            with pytest.raises(ToolError, match="not found"):
                await server.call_tool(
                    "get_repository",
                    {"repository_identifier": f"github:missing/{uuid4().hex}"},
                )

        asyncio.run(_check())


def test_run_assessment_persists_ids_queryable_via_mcp(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "README.md").write_text("# sample\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name":"sample"}\n', encoding="utf-8")
    knowledge_dir = tmp_path / "knowledge"
    settings = _settings(repo, knowledge_dir)

    with SqliteKnowledgeStore(knowledge_dir) as store:
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
            settings=settings,
        )
        result = run_assessment(
            repo=str(repo),
            output_directory=tmp_path / "reports",
            mode=AssessmentMode.DETERMINISTIC,
            settings=settings,
            static_analysis_enabled=False,
            knowledge_store=store,
        )
        assert result.knowledge_run_id is not None
        assert result.knowledge_repository_id is not None
        assert result.knowledge_snapshot_id is not None

        async def _query() -> None:
            latest = await _call(
                server,
                "get_latest_assessment",
                {"repository_identifier": result.knowledge_repository_id},
            )
            assert latest["present"] is True
            assert latest["assessment"]["run_id"] == result.knowledge_run_id
            findings = await _call(
                server,
                "list_findings",
                {"run_id": result.knowledge_run_id},
            )
            assert "items" in findings
            comparison = await _call(
                server,
                "compare_snapshots",
                {
                    "previous_snapshot_id": result.knowledge_snapshot_id,
                    "current_snapshot_id": result.knowledge_snapshot_id,
                },
            )
            assert comparison["counts"]["added"] == 0

        asyncio.run(_query())


def test_serialization_omits_blob_refs(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        seed_completed_assessment(store, github_url="https://github.com/acme/ser.git")
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
        )

        async def _check() -> None:
            payload = await _call(server, "list_repositories", {"limit": 5})
            encoded = json.dumps(payload)
            assert "blob_ref" not in encoded
            assert "knowledge.sqlite" not in encoded

        asyncio.run(_check())
