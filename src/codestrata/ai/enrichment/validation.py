"""Validate AI enrichment results against supplied context allowlists."""

from __future__ import annotations

from codestrata.ai.enrichment.context import AiEnrichmentContext
from codestrata.domain.ai_enrichment import AiEnrichmentResult


class AiEnrichmentValidationError(ValueError):
    """Raised when enrichment output fails referential or structural checks."""


def validate_ai_enrichment_result(
    result: AiEnrichmentResult,
    context: AiEnrichmentContext,
) -> AiEnrichmentResult:
    """Ensure referenced IDs exist in the compact enrichment context."""

    allowed_findings = set(context.allowed_finding_ids)
    allowed_recommendations = set(context.allowed_recommendation_ids)

    unknown_findings = sorted(set(result.referenced_finding_ids) - allowed_findings)
    unknown_recommendations = sorted(
        set(result.referenced_recommendation_ids) - allowed_recommendations
    )
    if unknown_findings or unknown_recommendations:
        details: list[str] = []
        if unknown_findings:
            details.append(f"unknown finding IDs: {', '.join(unknown_findings)}")
        if unknown_recommendations:
            details.append("unknown recommendation IDs: " + ", ".join(unknown_recommendations))
        raise AiEnrichmentValidationError("; ".join(details))
    return result
