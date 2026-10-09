"""MCP tools for bounded local evidence queries from artifacts.

Exposes read-only tools scoped to an explicit local root:
- repository: list_repositories, get_repository
- snapshot: list_snapshots, get_snapshot
- component: list_components, get_component
- finding: list_findings, get_finding
- metric: list_metrics, get_metric
- dependency: list_dependencies, get_dependencies
- change: list_changes, get_change_summary
- evidence: list_evidence, get_evidence
- lineage: list_lineage, get_lineage

Zero database connection; read-only; paginated with query budgeting.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.artifact_evidence import (
    DEFAULT_PAGE_LIMIT,
    MAX_CHARACTER_BUDGET,
    LocalArtifactEvidenceService,
)
from codestrata.interfaces.mcp.mapping import paginated_list, to_mcp_dict
from codestrata.interfaces.mcp.security import optional_filter, require_nonblank
from codestrata.interfaces.mcp.tools._common import run_bounded


def default_evidence_service(default_root: str) -> LocalArtifactEvidenceService:
    """Bind artifact queries to an explicit authorized root."""

    root = str(default_root).strip() or "."
    return LocalArtifactEvidenceService(allowed_root=root)


def register_artifact_evidence_tools(
    server: FastMCP,
    service: LocalArtifactEvidenceService | None = None,
    *,
    default_root: str = ".",
    max_character_budget: int = MAX_CHARACTER_BUDGET,
) -> None:
    """Register bounded local artifact evidence tools on a FastMCP server."""

    evidence_service = service or default_evidence_service(default_root)

    def _resolve_root(local_root: str | None) -> str:
        if local_root is None or not str(local_root).strip():
            return default_root
        return require_nonblank(str(local_root), label="local_root")

    def _apply_character_budget(
        items: list[dict[str, Any]],
        *,
        budget: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Truncate items if total JSON character size exceeds the character budget."""
        serialized = json.dumps(items)
        if len(serialized) <= budget:
            return items, False

        kept: list[dict[str, Any]] = []
        current_len = 2  # []
        for item in items:
            item_len = len(json.dumps(item)) + 1
            if current_len + item_len > budget:
                break
            kept.append(item)
            current_len += item_len
        return kept, True

    # ------------------------------------------------------------------
    # Repository tools
    # ------------------------------------------------------------------

    @server.tool(name="list_repositories", structured_output=True)
    def list_repositories(
        local_root: str = ".",
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List repositories discovered under local root artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            items, total_count = evidence_service.list_repositories(
                root,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_repositories", _run)

    @server.tool(name="get_repository", structured_output=True)
    def get_repository(
        local_root: str = ".",
        repository_id: str = "",
    ) -> dict[str, Any]:
        """Get repository metadata from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = require_nonblank(repository_id, label="repository_id")
            return to_mcp_dict(evidence_service.get_repository(root, repository_id=rid))

        return run_bounded("get_repository", _run)

    # ------------------------------------------------------------------
    # Snapshot tools
    # ------------------------------------------------------------------

    @server.tool(name="list_snapshots", structured_output=True)
    def list_snapshots(
        local_root: str = ".",
        repository_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List snapshots discovered under local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(repository_id, label="repository_id")
            items, total_count = evidence_service.list_snapshots(
                root,
                repository_id=rid,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_snapshots", _run)

    @server.tool(name="get_snapshot", structured_output=True)
    def get_snapshot(
        local_root: str = ".",
        snapshot_id: str = "",
        repository_id: str | None = None,
    ) -> dict[str, Any]:
        """Get details for a snapshot from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            sid = require_nonblank(snapshot_id, label="snapshot_id")
            rid = optional_filter(repository_id, label="repository_id")
            return to_mcp_dict(
                evidence_service.get_snapshot(root, snapshot_id=sid, repository_id=rid)
            )

        return run_bounded("get_snapshot", _run)

    # ------------------------------------------------------------------
    # Component tools
    # ------------------------------------------------------------------

    @server.tool(name="list_components", structured_output=True)
    def list_components(
        local_root: str = ".",
        run_id: str | None = None,
        component_type: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List architecture components from local assessment artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            ctype = optional_filter(component_type, label="component_type")
            items, total_count = evidence_service.list_components(
                root,
                run_id=rid,
                component_type=ctype,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_components", _run)

    @server.tool(name="get_component", structured_output=True)
    def get_component(
        local_root: str = ".",
        component_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Get component details by ID from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            cid = require_nonblank(component_id, label="component_id")
            rid = optional_filter(run_id, label="run_id")
            return to_mcp_dict(evidence_service.get_component(root, component_id=cid, run_id=rid))

        return run_bounded("get_component", _run)

    # ------------------------------------------------------------------
    # Finding tools
    # ------------------------------------------------------------------

    @server.tool(name="list_findings", structured_output=True)
    def list_findings(
        local_root: str = ".",
        run_id: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List findings from local assessment artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            sev = optional_filter(severity, label="severity")
            cat = optional_filter(category, label="category")
            items, total_count = evidence_service.list_findings(
                root,
                run_id=rid,
                severity=sev,
                category=cat,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_findings", _run)

    @server.tool(name="get_finding", structured_output=True)
    def get_finding(
        local_root: str = ".",
        finding_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Get finding details by ID from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            fid = require_nonblank(finding_id, label="finding_id")
            rid = optional_filter(run_id, label="run_id")
            return to_mcp_dict(evidence_service.get_finding(root, finding_id=fid, run_id=rid))

        return run_bounded("get_finding", _run)

    # ------------------------------------------------------------------
    # Metric tools
    # ------------------------------------------------------------------

    @server.tool(name="list_metrics", structured_output=True)
    def list_metrics(
        local_root: str = ".",
        run_id: str | None = None,
        category: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List metrics from local assessment artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            cat = optional_filter(category, label="category")
            items, total_count = evidence_service.list_metrics(
                root,
                run_id=rid,
                category=cat,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_metrics", _run)

    @server.tool(name="get_metric", structured_output=True)
    def get_metric(
        local_root: str = ".",
        metric_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Get metric details by ID or name from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            mid = require_nonblank(metric_id, label="metric_id")
            rid = optional_filter(run_id, label="run_id")
            return to_mcp_dict(evidence_service.get_metric(root, metric_id=mid, run_id=rid))

        return run_bounded("get_metric", _run)

    # ------------------------------------------------------------------
    # Dependency tools
    # ------------------------------------------------------------------

    @server.tool(name="list_dependencies", structured_output=True)
    def list_dependencies(
        local_root: str = ".",
        run_id: str | None = None,
        source_component_id: str | None = None,
        target_component_id: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List dependencies from local assessment artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            src = optional_filter(source_component_id, label="source_component_id")
            tgt = optional_filter(target_component_id, label="target_component_id")
            items, total_count = evidence_service.list_dependencies(
                root,
                run_id=rid,
                source_component_id=src,
                target_component_id=tgt,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_dependencies", _run)

    @server.tool(name="get_dependencies", structured_output=True)
    def get_dependencies(
        local_root: str = ".",
        component_id: str = "",
        run_id: str | None = None,
        direction: str = "outgoing",
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get component dependencies (incoming/outgoing/both) from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            cid = require_nonblank(component_id, label="component_id")
            rid = optional_filter(run_id, label="run_id")
            items, total_count = evidence_service.get_dependencies(
                root,
                component_id=cid,
                run_id=rid,
                direction=direction,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("get_dependencies", _run)

    # ------------------------------------------------------------------
    # Change tools
    # ------------------------------------------------------------------

    @server.tool(name="list_changes", structured_output=True)
    def list_changes(
        local_root: str = ".",
        run_id: str | None = None,
        change_type: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List changes and change facts from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            ctype = optional_filter(change_type, label="change_type")
            items, total_count = evidence_service.list_changes(
                root,
                run_id=rid,
                change_type=ctype,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_changes", _run)

    @server.tool(name="get_change_summary", structured_output=True)
    def get_change_summary(
        local_root: str = ".",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Get summary of changes, boundaries, and impact from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            return to_mcp_dict(evidence_service.get_change_summary(root, run_id=rid))

        return run_bounded("get_change_summary", _run)

    # ------------------------------------------------------------------
    # Evidence tools
    # ------------------------------------------------------------------

    @server.tool(name="list_evidence", structured_output=True)
    def list_evidence(
        local_root: str = ".",
        run_id: str | None = None,
        evidence_kind: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List evidence records from local assessment artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            ekind = optional_filter(evidence_kind, label="evidence_kind")
            items, total_count = evidence_service.list_evidence(
                root,
                run_id=rid,
                evidence_kind=ekind,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_evidence", _run)

    @server.tool(name="get_evidence", structured_output=True)
    def get_evidence(
        local_root: str = ".",
        evidence_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Get an evidence item by ID from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            eid = require_nonblank(evidence_id, label="evidence_id")
            rid = optional_filter(run_id, label="run_id")
            return to_mcp_dict(evidence_service.get_evidence(root, evidence_id=eid, run_id=rid))

        return run_bounded("get_evidence", _run)

    # ------------------------------------------------------------------
    # Lineage tools
    # ------------------------------------------------------------------

    @server.tool(name="list_lineage", structured_output=True)
    def list_lineage(
        local_root: str = ".",
        repository_id: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List execution lineage and provenance records from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(repository_id, label="repository_id")
            items, total_count = evidence_service.list_lineage(
                root,
                repository_id=rid,
                limit=limit,
                offset=offset,
            )
            kept, truncated = _apply_character_budget(items, budget=max_character_budget)
            has_more = (offset + len(items)) < total_count
            return paginated_list(
                kept,
                total_count=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
                truncated=truncated,
            )

        return run_bounded("list_lineage", _run)

    @server.tool(name="get_lineage", structured_output=True)
    def get_lineage(
        local_root: str = ".",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Get execution lineage and provenance details for a run from local artifacts."""

        def _run() -> dict[str, Any]:
            root = _resolve_root(local_root)
            rid = optional_filter(run_id, label="run_id")
            return to_mcp_dict(evidence_service.get_lineage(root, run_id=rid))

        return run_bounded("get_lineage", _run)
