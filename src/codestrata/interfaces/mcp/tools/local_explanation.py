"""Optional MCP tool for the local/BYO explanation path.

The tool is not part of the bounded artifact evidence server. Both AI and
prompt/evidence egress stay off unless the caller sets those flags. Product
telemetry does not enable egress, and source instructions are not executed.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from codestrata.ai.explanation.local_byo import (
    MAX_PERMITTED_EVIDENCE_IDS,
    ExplanationRequest,
    LocalByoExplanationPath,
    unchanged_explanation_error,
)
from codestrata.application.knowledge.artifact_evidence import LocalArtifactEvidenceService
from codestrata.application.knowledge.permitted_evidence import collect_permitted_evidence_ids
from codestrata.application.knowledge.queries.errors import (
    ArtifactPathSecurityError,
    KnowledgeQueryError,
    QueryBudgetExceededError,
)
from codestrata.interfaces.mcp.tools._common import run_bounded


def register_local_explanation_tool(
    server: FastMCP,
    *,
    explanation_path: LocalByoExplanationPath | None = None,
    evidence_service: LocalArtifactEvidenceService | None = None,
) -> None:
    """Register the single optional explanation tool."""

    path = explanation_path or LocalByoExplanationPath()

    @server.tool(name="explain_local_evidence", structured_output=True)
    def explain_local_evidence(
        assessment_status: str = "",
        canonical_digest: str = "",
        evidence_ids: list[str] | None = None,
        local_root: str | None = None,
        run_id: str | None = None,
        enabled: bool = False,
        prompt_evidence_egress_enabled: bool = False,
        product_telemetry_enabled: bool = False,
        model: str = "",
        source_instructions: str = "",
    ) -> dict[str, object]:
        """Explain permitted local evidence without changing canonical results."""

        def _run() -> dict[str, object]:
            permitted, prep_error = _permitted_ids(
                evidence_ids=evidence_ids,
                local_root=local_root,
                run_id=run_id,
                evidence_service=evidence_service,
                enabled=enabled,
            )
            if prep_error is not None:
                return unchanged_explanation_error(
                    assessment_status=assessment_status,
                    canonical_digest=canonical_digest,
                    code=prep_error[0],
                    category=prep_error[1],
                    detail=prep_error[2],
                    product_telemetry_enabled=product_telemetry_enabled,
                ).to_dict()

            outcome = path.explain(
                ExplanationRequest(
                    assessment_status=assessment_status,
                    canonical_digest=canonical_digest,
                    permitted_evidence_ids=permitted,
                    enabled=enabled,
                    prompt_evidence_egress_enabled=prompt_evidence_egress_enabled,
                    product_telemetry_enabled=product_telemetry_enabled,
                    model=model,
                    source_instructions=source_instructions,
                )
            )
            return outcome.to_dict()

        return run_bounded("explain_local_evidence", _run)


def _permitted_ids(
    *,
    evidence_ids: list[str] | None,
    local_root: str | None,
    run_id: str | None,
    evidence_service: LocalArtifactEvidenceService | None,
    enabled: bool,
) -> tuple[tuple[str, ...], tuple[str, str, str] | None]:
    """Resolve caller IDs or local artifact IDs. Skip artifact reads when AI is off."""

    if not enabled:
        explicit = tuple(evidence_ids or ())
        return explicit, None
    if local_root is not None and str(local_root).strip():
        try:
            service = evidence_service or LocalArtifactEvidenceService(
                allowed_root=Path(local_root)
            )
            collected = collect_permitted_evidence_ids(
                service,
                local_root,
                run_id=run_id,
                budget=MAX_PERMITTED_EVIDENCE_IDS,
            )
        except QueryBudgetExceededError:
            return (), (
                "explanation_budget_exceeded",
                "budget",
                "Local evidence exceeds the explanation budget.",
            )
        except ArtifactPathSecurityError:
            return (), (
                "artifact_path_rejected",
                "validation",
                "The local artifact root was rejected.",
            )
        except KnowledgeQueryError:
            return (), (
                "permitted_evidence_unavailable",
                "validation",
                "Permitted evidence could not be read from local artifacts.",
            )
        if evidence_ids:
            allowed = set(collected)
            requested = tuple(evidence_ids)
            if any(item not in allowed for item in requested):
                return (), (
                    "invalid_evidence_id",
                    "validation",
                    "A requested evidence ID is not in the local artifact set.",
                )
            return requested, None
        return collected, None
    return tuple(evidence_ids or ()), None


__all__ = ["register_local_explanation_tool"]
