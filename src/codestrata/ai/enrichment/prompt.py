"""Prompt builder for Modernization Advisor (AI enrichment) over deterministic evidence."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from codestrata.ai.enrichment.advisor import (
    MODERNIZATION_ADVISOR_PERSONA,
    MODERNIZATION_ADVISOR_PROMPT_VERSION,
)
from codestrata.ai.enrichment.context import AiEnrichmentContext
from codestrata.ai.prompts.models import PromptMessage, PromptMetadata, PromptRequest
from codestrata.domain.ai_enrichment import AI_ENRICHMENT_RESULT_VERSION, AiEnrichmentResult

ENRICHMENT_PROMPT_PURPOSE = "modernization_advisor"
ENRICHMENT_PROMPT_TEMPLATE_VERSION = MODERNIZATION_ADVISOR_PROMPT_VERSION
DEFAULT_ENRICHMENT_MAX_CONTEXT_CHARACTERS = 60_000


class AiEnrichmentPromptBuildError(ValueError):
    """Raised when enrichment prompt construction fails."""


class AiEnrichmentPromptOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_context_characters: int = Field(
        default=DEFAULT_ENRICHMENT_MAX_CONTEXT_CHARACTERS,
        gt=0,
    )
    template_version: str = ENRICHMENT_PROMPT_TEMPLATE_VERSION


class AiEnrichmentPromptBuilder:
    """Build a strict JSON Modernization Advisor prompt from compact context."""

    def build(
        self,
        context: AiEnrichmentContext,
        options: AiEnrichmentPromptOptions | None = None,
    ) -> PromptRequest:
        active = options or AiEnrichmentPromptOptions()
        context_json = context.to_stable_json(indent=2)
        if len(context_json) > active.max_context_characters:
            raise AiEnrichmentPromptBuildError(
                "enrichment context JSON exceeds max_context_characters "
                f"({len(context_json)} > {active.max_context_characters})"
            )
        schema_json = json.dumps(
            AiEnrichmentResult.model_json_schema(mode="validation"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        system = (
            f"{MODERNIZATION_ADVISOR_PERSONA} "
            "Use only the supplied findings and recommendations. "
            "Do not invent unsupported issues. "
            "Distinguish facts (supplied IDs and summaries) from interpretation. "
            "Preserve finding and recommendation IDs for traceability. "
            "Return strict JSON only matching the provided schema. "
            "Keep the response concise and actionable for engineering leaders."
        )
        developer = (
            "Rules:\n"
            "1. Reference only IDs present in allowed_finding_ids / "
            "allowed_recommendation_ids.\n"
            "2. Do not create, delete, or rewrite deterministic findings or "
            "recommendations.\n"
            "3. Prefer themes, priorities, risks, and next steps grounded in "
            "the supplied evidence.\n"
            "4. If evidence is thin, say so in limitations instead of inventing "
            "detail.\n"
            "5. Write for CTOs and VP Engineering: clear business language, "
            "no raw rule-id laundry lists in the executive summary.\n"
            f"6. Output schema version: {AI_ENRICHMENT_RESULT_VERSION}."
        )
        user = (
            f"Repository: {context.repository.display_name}\n"
            f"Findings: {len(context.findings)}\n"
            f"Recommendations: {len(context.recommendations)}\n\n"
            "Compact enrichment context JSON:\n"
            f"{context_json}\n\n"
            "Expected output JSON schema:\n"
            f"{schema_json}\n"
        )
        metadata = PromptMetadata(
            repository_identifier=context.repository.repository_key,
            context_schema_version=context.version,
            recommendation_schema_version=AI_ENRICHMENT_RESULT_VERSION,
            finding_count=len(context.findings),
            technology_count=len(context.technologies),
            context_truncated=context.truncated,
            prompt_template_version=active.template_version,
        )
        # PromptRequest.purpose remains modernization_assessment for provider
        # compatibility; advisor semantics live in messages + schema.
        return PromptRequest(
            purpose="modernization_assessment",
            messages=[
                PromptMessage(role="system", content=system),
                PromptMessage(role="developer", content=developer),
                PromptMessage(role="user", content=user),
            ],
            context_json=context_json,
            expected_output_schema_json=schema_json,
            metadata=metadata,
        )
