"""Tests for E12.1: Serve bounded local evidence queries from artifacts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from codestrata.interfaces.mcp import (
    CODESSTRATA_ARTIFACT_MCP_NAME,
    create_artifact_mcp_server,
)


def _seed_sample_artifacts(root: Path) -> dict[str, Any]:
    """Create a realistic local artifact directory tree."""
    assessments_dir = root / "assessments" / "run-20260925-001"
    assessments_dir.mkdir(parents=True, exist_ok=True)

    report_payload: dict[str, Any] = {
        "schema_version": "1.2",
        "assessment_id": "run-20260925-001",
        "repository_id": "repo-alpha",
        "repository_name": "alpha-repo",
        "snapshot_id": "snap-001",
        "previous_assessment_run_id": "run-20260924-000",
        "executed_at": "2026-09-25T12:00:00Z",
        "engine_version": "0.2.1",
        "ruleset_version": "2026.09",
        "invalidation_fingerprint": "fp-inv-12345",
        "git": {
            "branch": "main",
            "commit_sha": "abc1234def5678",
        },
        "repository": {
            "id": "repo-alpha",
            "name": "alpha-repo",
            "source_type": "github",
            "source_location": "https://github.com/acme/alpha-repo.git",
        },
        "snapshot": {
            "id": "snap-001",
            "file_count": 42,
        },
        "assessment": {
            "components": [
                {
                    "component_id": "comp-core",
                    "name": "core_engine",
                    "component_type": "module",
                    "path": "src/core",
                    "metrics": {"loc": 1200},
                    "dependencies": ["comp-utils"],
                },
                {
                    "component_id": "comp-utils",
                    "name": "utils_pkg",
                    "component_type": "package",
                    "path": "src/utils",
                    "metrics": {"loc": 450},
                    "dependencies": [],
                },
                {
                    "component_id": "comp-api",
                    "name": "api_layer",
                    "component_type": "module",
                    "path": "src/api",
                    "metrics": {"loc": 850},
                    "dependencies": ["comp-core"],
                },
            ],
            "findings": [
                {
                    "finding_id": "finding-001",
                    "rule_id": "sec.sql_injection",
                    "severity": "high",
                    "category": "security",
                    "message": "Potential SQL injection in query builder",
                    "location": {"path": "src/core/db.py", "line": 42},
                    "evidence_refs": ["ev-001"],
                },
                {
                    "finding_id": "finding-002",
                    "rule_id": "arch.cycle",
                    "severity": "medium",
                    "category": "architecture",
                    "message": "Direct boundary violation from api to db",
                    "location": {"path": "src/api/handler.py", "line": 15},
                    "evidence_refs": ["ev-002"],
                },
                {
                    "finding_id": "finding-003",
                    "rule_id": "qual.maintainability",
                    "severity": "low",
                    "category": "code_quality",
                    "message": "High cyclomatic complexity in dispatch",
                    "location": {"path": "src/utils/dispatch.py", "line": 99},
                    "evidence_refs": [],
                },
            ],
            "metrics": [
                {
                    "metric_id": "m.cyclomatic_complexity",
                    "name": "Cyclomatic Complexity",
                    "category": "quality",
                    "value": 14.5,
                    "unit": "ratio",
                    "scope": "component",
                    "coverage": 0.95,
                    "description": "Average cyclomatic complexity across modules",
                },
                {
                    "metric_id": "m.test_coverage",
                    "name": "Test Coverage",
                    "category": "testing",
                    "value": 84.2,
                    "unit": "percent",
                    "scope": "repository",
                    "coverage": 1.0,
                    "description": "Line coverage percentage",
                },
                {
                    "metric_id": "m.afferent_coupling",
                    "name": "Afferent Coupling",
                    "category": "structure",
                    "value": 3,
                    "unit": "count",
                    "scope": "component",
                    "coverage": 1.0,
                    "description": "Incoming dependency count",
                },
            ],
            "dependencies": [
                {
                    "source": "comp-core",
                    "target": "comp-utils",
                    "relationship_type": "depends_on",
                    "weight": 5,
                    "evidence": ["import src.utils"],
                },
                {
                    "source": "comp-api",
                    "target": "comp-core",
                    "relationship_type": "depends_on",
                    "weight": 12,
                    "evidence": ["from src.core import engine"],
                },
            ],
            "change_facts": [
                {
                    "path": "src/core/db.py",
                    "change_type": "modified",
                    "lineage_status": "unique",
                    "diff_stat": {"additions": 15, "deletions": 3},
                    "boundary_crossed": True,
                    "blast_radius": {"impacted_components": ["comp-api"]},
                },
                {
                    "path": "src/utils/helpers.py",
                    "change_type": "added",
                    "lineage_status": "unique",
                    "diff_stat": {"additions": 45, "deletions": 0},
                    "boundary_crossed": False,
                    "blast_radius": {"impacted_components": []},
                },
            ],
            "delta": {
                "summary": {
                    "total_changes": 2,
                    "added_count": 1,
                    "deleted_count": 0,
                    "modified_count": 1,
                    "verdict": "compatible",
                    "boundaries_crossed_count": 1,
                    "affected_components_count": 2,
                }
            },
            "evidence": [
                {
                    "evidence_id": "ev-001",
                    "kind": "source",
                    "source_path": "src/core/db.py",
                    "snippet": "cursor.execute(f'SELECT * FROM users WHERE id={user_id}')",
                    "line_range": [42, 43],
                    "fingerprint": "fp-ev-sql",
                    "confidence": 1.0,
                },
                {
                    "evidence_id": "ev-002",
                    "kind": "ast",
                    "source_path": "src/api/handler.py",
                    "snippet": "from src.core.db import execute_raw",
                    "line_range": [15, 15],
                    "fingerprint": "fp-ev-import",
                    "confidence": 0.9,
                },
            ],
        },
    }

    (assessments_dir / "report.json").write_text(
        json.dumps(report_payload, indent=2), encoding="utf-8"
    )
    (assessments_dir / "assessment.json").write_text(
        json.dumps(report_payload, indent=2), encoding="utf-8"
    )
    return report_payload


async def _call(server: Any, name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Helper to call an MCP tool and unpack response."""
    result = await server.call_tool(name, arguments or {})
    if isinstance(result, tuple):
        structured = result[1]
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    if isinstance(result, list) and result:
        return json.loads(result[0].text)
    return result


# ----------------------------------------------------------------------
# Acceptance Criterion: Server Boundary & Absence of Forbidden Tools
# ----------------------------------------------------------------------


def test_artifact_server_registers_expected_evidence_tools() -> None:
    server = create_artifact_mcp_server(".")
    assert server.name == CODESSTRATA_ARTIFACT_MCP_NAME

    async def _check() -> None:
        tool_names = {tool.name for tool in await server.list_tools()}

        expected_tools = {
            "list_repositories",
            "get_repository",
            "list_snapshots",
            "get_snapshot",
            "list_components",
            "get_component",
            "list_findings",
            "get_finding",
            "list_metrics",
            "get_metric",
            "list_dependencies",
            "get_dependencies",
            "list_changes",
            "get_change_summary",
            "list_evidence",
            "get_evidence",
            "list_lineage",
            "get_lineage",
        }
        for expected in expected_tools:
            assert expected in tool_names, (
                f"Expected tool {expected!r} missing from artifact server"
            )

        # Explicit forbidden tools check (Acceptance: No database, mutation, assessment execution,
        # rule activation, shell, hosted calls, portfolio query or GraphRAG tool)
        forbidden_tools = {
            "run_assessment",
            "evaluate_rule",
            "activate_rule_pack",
            "list_agent_personas",
            "execute_agent_instruction",
            "stream_agent_instruction",
            "plan_incremental_assessment",
            "repository_search",
            "repository_answer",
            "shell_execute",
            "portfolio_overview",
        }
        for forbidden in forbidden_tools:
            assert forbidden not in tool_names, f"Forbidden tool {forbidden!r} registered on server"

    asyncio.run(_check())


def test_mcp_artifact_package_architecture_boundaries() -> None:
    """Ensure no forbidden tokens or database imports leak into interfaces/mcp."""
    root = Path(__file__).resolve().parents[3] / "src" / "codestrata" / "interfaces" / "mcp"
    forbidden = ("sqlite3", "SqliteKnowledgeStore", "report.json", "report.html")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden token {token!r}"


# ----------------------------------------------------------------------
# Deliverable: 9 Tool Categories with Pagination and Root Scope
# ----------------------------------------------------------------------


def test_repository_tools_pagination_and_lookup(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        result = await _call(
            server, "list_repositories", {"local_root": str(tmp_path), "limit": 10}
        )
        assert result["total_count"] >= 1
        assert result["returned_count"] >= 1
        assert result["offset"] == 0
        assert result["limit"] == 10
        assert "items" in result
        assert result["items"][0]["repository_id"] == "repo-alpha"

        repo = await _call(
            server,
            "get_repository",
            {"local_root": str(tmp_path), "repository_id": "repo-alpha"},
        )
        assert repo["repository_id"] == "repo-alpha"
        assert repo["name"] == "alpha-repo"

    asyncio.run(_check())


def test_snapshot_tools_pagination_and_lookup(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        snaps = await _call(
            server,
            "list_snapshots",
            {"local_root": str(tmp_path), "repository_id": "repo-alpha", "limit": 5},
        )
        assert snaps["total_count"] >= 1
        assert snaps["items"][0]["snapshot_id"] == "snap-001"

        snap = await _call(
            server,
            "get_snapshot",
            {"local_root": str(tmp_path), "snapshot_id": "snap-001"},
        )
        assert snap["snapshot_id"] == "snap-001"
        assert snap["branch"] == "main"

    asyncio.run(_check())


def test_component_tools_pagination_and_filtering(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        comps = await _call(
            server,
            "list_components",
            {"local_root": str(tmp_path), "limit": 2, "offset": 0},
        )
        assert comps["total_count"] == 3
        assert comps["returned_count"] == 2
        assert comps["has_more"] is True

        page2 = await _call(
            server,
            "list_components",
            {"local_root": str(tmp_path), "limit": 2, "offset": 2},
        )
        assert page2["returned_count"] == 1
        assert page2["has_more"] is False

        filtered = await _call(
            server,
            "list_components",
            {"local_root": str(tmp_path), "component_type": "package"},
        )
        assert filtered["total_count"] == 1
        assert filtered["items"][0]["name"] == "utils_pkg"

        comp = await _call(
            server,
            "get_component",
            {"local_root": str(tmp_path), "component_id": "comp-core"},
        )
        assert comp["component_id"] == "comp-core"
        assert comp["name"] == "core_engine"

    asyncio.run(_check())


def test_finding_tools_pagination_and_filtering(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        findings = await _call(
            server,
            "list_findings",
            {"local_root": str(tmp_path), "severity": "high"},
        )
        assert findings["total_count"] == 1
        assert findings["items"][0]["finding_id"] == "finding-001"
        assert findings["items"][0]["rule_id"] == "sec.sql_injection"

        finding = await _call(
            server,
            "get_finding",
            {"local_root": str(tmp_path), "finding_id": "finding-001"},
        )
        assert finding["finding_id"] == "finding-001"
        assert "Potential SQL injection" in finding["message"]
        assert finding["evidence_refs"] == ["ev-001"]

    asyncio.run(_check())


def test_metric_tools_pagination_and_filtering(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        metrics = await _call(
            server,
            "list_metrics",
            {"local_root": str(tmp_path), "category": "testing"},
        )
        assert metrics["total_count"] == 1
        assert metrics["items"][0]["name"] == "Test Coverage"
        assert metrics["items"][0]["value"] == 84.2

        metric = await _call(
            server,
            "get_metric",
            {"local_root": str(tmp_path), "metric_id": "m.cyclomatic_complexity"},
        )
        assert metric["metric_id"] == "m.cyclomatic_complexity"
        assert metric["value"] == 14.5

    asyncio.run(_check())


def test_dependency_tools_direction_and_filtering(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        deps = await _call(
            server,
            "list_dependencies",
            {"local_root": str(tmp_path), "source_component_id": "comp-core"},
        )
        assert deps["total_count"] == 1
        assert deps["items"][0]["target"] == "comp-utils"

        outgoing = await _call(
            server,
            "get_dependencies",
            {
                "local_root": str(tmp_path),
                "component_id": "comp-core",
                "direction": "outgoing",
            },
        )
        assert outgoing["total_count"] == 1
        assert outgoing["items"][0]["target"] == "comp-utils"

        incoming = await _call(
            server,
            "get_dependencies",
            {
                "local_root": str(tmp_path),
                "component_id": "comp-core",
                "direction": "incoming",
            },
        )
        assert incoming["total_count"] == 1
        assert incoming["items"][0]["source"] == "comp-api"

    asyncio.run(_check())


def test_change_tools_and_summary(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        changes = await _call(
            server,
            "list_changes",
            {"local_root": str(tmp_path), "change_type": "modified"},
        )
        assert changes["total_count"] == 1
        assert changes["items"][0]["path"] == "src/core/db.py"
        assert changes["items"][0]["boundary_crossed"] is True

        summary = await _call(
            server,
            "get_change_summary",
            {"local_root": str(tmp_path)},
        )
        assert summary["total_changes"] == 2
        assert summary["added_count"] == 1
        assert summary["modified_count"] == 1
        assert summary["verdict"] == "compatible"

    asyncio.run(_check())


def test_evidence_tools_pagination_and_lookup(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        evidence = await _call(
            server,
            "list_evidence",
            {"local_root": str(tmp_path), "evidence_kind": "source"},
        )
        assert evidence["total_count"] == 1
        assert evidence["items"][0]["evidence_id"] == "ev-001"

        item = await _call(
            server,
            "get_evidence",
            {"local_root": str(tmp_path), "evidence_id": "ev-001"},
        )
        assert item["evidence_id"] == "ev-001"
        assert "cursor.execute" in item["snippet"]

    asyncio.run(_check())


def test_lineage_tools(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        lineage_list = await _call(
            server,
            "list_lineage",
            {"local_root": str(tmp_path)},
        )
        assert lineage_list["total_count"] >= 1
        assert lineage_list["items"][0]["run_id"] == "run-20260925-001"
        assert lineage_list["items"][0]["previous_run_id"] == "run-20260924-000"

        lineage = await _call(
            server,
            "get_lineage",
            {"local_root": str(tmp_path), "run_id": "run-20260925-001"},
        )
        assert lineage["run_id"] == "run-20260925-001"
        assert lineage["git_commit"] == "abc1234def5678"
        assert lineage["ruleset_version"] == "2026.09"

    asyncio.run(_check())


# ----------------------------------------------------------------------
# Acceptance Criteria: Rejections, Budgets & Security
# ----------------------------------------------------------------------


def test_reject_arbitrary_paths_and_traversal(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        # Directory traversal attempt
        with pytest.raises(ToolError, match="Path traversal forbidden"):
            await server.call_tool(
                "list_findings",
                {"local_root": str(tmp_path) + "/../outside"},
            )

        # Directory escaping authorized root
        other_dir = tmp_path.parent / "outside_dir"
        other_dir.mkdir(exist_ok=True)
        with pytest.raises(ToolError, match="escapes the authorized root"):
            await server.call_tool(
                "list_findings",
                {"local_root": str(other_dir)},
            )

        # Non-existent root
        with pytest.raises(ToolError, match="does not exist"):
            await server.call_tool(
                "list_findings",
                {"local_root": str(tmp_path / "non_existent_folder")},
            )

    asyncio.run(_check())


def test_reject_unknown_artifact_versions(tmp_path: Path) -> None:
    bad_root = tmp_path / "bad_artifacts"
    bad_root.mkdir()
    bad_doc = {
        "schema_version": "99.0-unsupported",
        "assessment_id": "bad-run",
        "findings": [],
    }
    (bad_root / "assessment.json").write_text(json.dumps(bad_doc), encoding="utf-8")

    server = create_artifact_mcp_server(bad_root)

    async def _check() -> None:
        with pytest.raises(ToolError, match="Unknown artifact version"):
            await server.call_tool(
                "list_findings",
                {"local_root": str(bad_root)},
            )

    asyncio.run(_check())


def test_query_budget_and_oversized_limit_rejection(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        # Oversized limit exceeding budget (max 500)
        with pytest.raises(ToolError, match="exceeds maximum query budget"):
            await server.call_tool(
                "list_findings",
                {"local_root": str(tmp_path), "limit": 1000},
            )

        # Negative / zero limit
        with pytest.raises(ToolError, match="limit must be >= 1"):
            await server.call_tool(
                "list_findings",
                {"local_root": str(tmp_path), "limit": 0},
            )

        # Negative offset
        with pytest.raises(ToolError, match="offset must be >= 0"):
            await server.call_tool(
                "list_findings",
                {"local_root": str(tmp_path), "offset": -1},
            )

    asyncio.run(_check())


def test_character_budget_truncation(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    from codestrata.config import CodestrataSettings, McpSettings, RepositorySettings

    # Configure tiny character budget to force truncation
    settings = CodestrataSettings(
        repository=RepositorySettings(path=str(tmp_path)),
        mcp=McpSettings(max_result_characters=50),
    )
    server = create_artifact_mcp_server(
        tmp_path,
        settings=settings,
    )

    async def _check() -> None:
        result = await _call(server, "list_components", {"local_root": str(tmp_path)})
        assert result["truncated"] is True
        assert result["returned_count"] < result["total_count"]

    asyncio.run(_check())


def test_missing_entities_raise_clear_not_found(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        with pytest.raises(ToolError, match="Finding not found"):
            await server.call_tool(
                "get_finding",
                {"local_root": str(tmp_path), "finding_id": "non-existent-finding"},
            )

        with pytest.raises(ToolError, match="Component not found"):
            await server.call_tool(
                "get_component",
                {"local_root": str(tmp_path), "component_id": "non-existent-comp"},
            )

        with pytest.raises(ToolError, match="Metric not found"):
            await server.call_tool(
                "get_metric",
                {"local_root": str(tmp_path), "metric_id": "non-existent-metric"},
            )

        with pytest.raises(ToolError, match="Evidence not found"):
            await server.call_tool(
                "get_evidence",
                {"local_root": str(tmp_path), "evidence_id": "non-existent-ev"},
            )

    asyncio.run(_check())


def test_read_only_access_does_not_need_collection_consent(tmp_path: Path) -> None:
    """Read-only access to local artifacts operates without any collection consent."""
    _seed_sample_artifacts(tmp_path)
    # No consent environment or file is seeded; queries must succeed
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        result = await _call(server, "list_repositories", {"local_root": str(tmp_path)})
        assert result["total_count"] >= 1

    asyncio.run(_check())


def test_artifact_path_validation_edge_cases(tmp_path: Path) -> None:
    from codestrata.application.knowledge.artifact_evidence import (
        LocalArtifactEvidenceService,
    )
    from codestrata.application.knowledge.queries.errors import (
        ArtifactPathSecurityError,
    )

    svc = LocalArtifactEvidenceService(allowed_root=tmp_path)

    # Empty string
    with pytest.raises(ArtifactPathSecurityError, match="non-empty string"):
        svc.validate_scope("")

    # Null byte
    with pytest.raises(ArtifactPathSecurityError, match="illegal characters"):
        svc.validate_scope("invalid\0path")

    # File instead of directory
    file_path = tmp_path / "regular_file.txt"
    file_path.write_text("hello", encoding="utf-8")
    with pytest.raises(ArtifactPathSecurityError, match="is not a directory"):
        svc.validate_scope(file_path)

    # validate_subpath
    assert svc.validate_subpath("", tmp_path) == tmp_path

    # Traversal in subpath
    with pytest.raises(ArtifactPathSecurityError, match="Path traversal forbidden"):
        svc.validate_subpath("../outside.json", tmp_path)

    # Unauthorized file extension
    unauthorized_file = tmp_path / "script.py"
    unauthorized_file.write_text("print(1)", encoding="utf-8")
    with pytest.raises(ArtifactPathSecurityError, match="Unauthorized file type"):
        svc.validate_subpath(unauthorized_file, tmp_path)


def test_filters_on_findings_dependencies_changes_evidence(tmp_path: Path) -> None:
    _seed_sample_artifacts(tmp_path)
    server = create_artifact_mcp_server(tmp_path)

    async def _check() -> None:
        # Findings filtered by severity, status, rule_id, file_path
        res_sev = await _call(
            server,
            "list_findings",
            {"local_root": str(tmp_path), "severity": "high", "status": "open"},
        )
        assert res_sev["total_count"] == 1
        assert res_sev["items"][0]["finding_id"] == "finding-001"

        res_none = await _call(
            server,
            "list_findings",
            {"local_root": str(tmp_path), "severity": "info"},
        )
        assert res_none["total_count"] == 0

        res_rule = await _call(
            server,
            "list_findings",
            {"local_root": str(tmp_path), "category": "security"},
        )
        assert res_rule["total_count"] == 1

        # Dependencies filtered by source_component_id
        deps = await _call(
            server,
            "list_dependencies",
            {
                "local_root": str(tmp_path),
                "source_component_id": "comp-api",
            },
        )
        assert deps["total_count"] == 1
        assert deps["items"][0]["source"] == "comp-api"

        deps_none = await _call(
            server,
            "list_dependencies",
            {"local_root": str(tmp_path), "source_component_id": "unknown-comp"},
        )
        assert deps_none["total_count"] == 0

        # Changes filtered by path, change_type, lineage_status
        changes = await _call(
            server,
            "list_changes",
            {
                "local_root": str(tmp_path),
                "path": "src/api/auth.py",
                "change_type": "modified",
                "lineage_status": "unique",
            },
        )
        assert changes["total_count"] == 1

        changes_none = await _call(
            server,
            "list_changes",
            {"local_root": str(tmp_path), "change_type": "deleted"},
        )
        assert changes_none["total_count"] == 0

        # Evidence filtered by evidence_kind
        ev_source = await _call(
            server,
            "list_evidence",
            {"local_root": str(tmp_path), "evidence_kind": "source"},
        )
        assert ev_source["total_count"] >= 1
        assert ev_source["items"][0]["evidence_id"] == "ev-001"

        ev_none = await _call(
            server,
            "list_evidence",
            {"local_root": str(tmp_path), "evidence_kind": "runtime"},
        )
        assert ev_none["total_count"] == 0

        # Metrics filtered by category
        metrics_qual = await _call(
            server,
            "list_metrics",
            {"local_root": str(tmp_path), "category": "quality"},
        )
        assert metrics_qual["total_count"] == 1

        metrics_none = await _call(
            server,
            "list_metrics",
            {"local_root": str(tmp_path), "category": "non_existent"},
        )
        assert metrics_none["total_count"] == 0

        # Lineage filtered by repository_id
        lineages = await _call(
            server,
            "list_lineage",
            {"local_root": str(tmp_path), "repository_id": "repo-alpha"},
        )
        assert lineages["total_count"] == 1

        lineages_none = await _call(
            server,
            "list_lineage",
            {"local_root": str(tmp_path), "repository_id": "non-existent-repo"},
        )
        assert lineages_none["total_count"] == 0

    asyncio.run(_check())


def test_standalone_artifact_files_support(tmp_path: Path) -> None:
    """Test reading standalone metrics.json, dependencies.json, manifest.yaml."""
    standalone_dir = tmp_path / "standalone"
    standalone_dir.mkdir()

    manifest_content = {
        "version": "1.0",
        "repository": {"name": "standalone-repo", "branch": "develop"},
        "snapshot": {"snapshot_id": "snap-sa-1", "commit": "def5678"},
        "components": [{"id": "sa-comp-1", "name": "Worker", "type": "service"}],
    }
    (standalone_dir / "manifest.json").write_text(json.dumps(manifest_content), encoding="utf-8")

    metrics_content = {
        "schema_version": "1.0",
        "metrics": [
            {
                "metric_id": "sa-met-1",
                "name": "coverage",
                "value": 88.5,
                "unit": "percent",
                "category": "testing",
            }
        ],
    }
    (standalone_dir / "metrics.json").write_text(json.dumps(metrics_content), encoding="utf-8")

    server = create_artifact_mcp_server(standalone_dir)

    async def _check() -> None:
        repos = await _call(server, "list_repositories", {"local_root": str(standalone_dir)})
        assert repos["total_count"] >= 1
        assert repos["items"][0]["name"] == "standalone-repo"

        snapshots = await _call(server, "list_snapshots", {"local_root": str(standalone_dir)})
        assert snapshots["total_count"] >= 1
        assert snapshots["items"][0]["snapshot_id"] == "snap-sa-1"

        comps = await _call(server, "list_components", {"local_root": str(standalone_dir)})
        assert comps["total_count"] >= 1
        assert comps["items"][0]["component_id"] == "sa-comp-1"

        mets = await _call(server, "list_metrics", {"local_root": str(standalone_dir)})
        assert mets["total_count"] >= 1
        assert mets["items"][0]["metric_id"] == "sa-met-1"

    asyncio.run(_check())
