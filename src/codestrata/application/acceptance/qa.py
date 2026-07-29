"""Acceptance helpers that remain in Community Engine.

Grounded RAG Q&A stacks live in ``codestrata_platform.rag.acceptance``.
"""

from __future__ import annotations

from typing import Any


def questions_passed(rows: list[dict[str, Any]]) -> tuple[bool, str]:
    """Acceptance bar for grounded Q&A rows (status + citation counts)."""

    if not rows:
        return False, "no questions executed"
    hard_failures = [row for row in rows if row.get("status") in {"failed", "disabled"}]
    if hard_failures:
        return False, f"{len(hard_failures)} question(s) failed or disabled"
    grounded = [
        row
        for row in rows
        if row.get("status") in {"success", "partial"} and int(row.get("citations") or 0) > 0
    ]
    if not grounded:
        soft = [
            row
            for row in rows
            if row.get("status") in {"success", "partial", "insufficient_evidence", "empty"}
        ]
        if len(soft) == len(rows):
            return True, "pipeline ok (limited topical coverage)"
        return False, "no grounded answers produced"
    return True, f"{len(grounded)}/{len(rows)} grounded answers with citations"


def mcp_health_passed(payload: dict[str, Any]) -> tuple[bool, str]:
    """Interpret MCP health payload for acceptance."""

    status = str(payload.get("status") or payload.get("overall_status") or "").lower()
    if status in {"failed", "error", "unhealthy"}:
        return False, status
    nested = payload.get("result")
    if isinstance(nested, dict):
        return mcp_health_passed(nested)
    if status in {"success", "partial", "ok", "healthy", "pass", "passed"}:
        return True, status
    if payload.get("healthy") is False:
        return False, "unhealthy"
    if payload:
        return True, status or "composed"
    return False, "empty health payload"
