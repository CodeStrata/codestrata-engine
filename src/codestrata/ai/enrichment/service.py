"""Single-call AI enrichment service over deterministic findings/recommendations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from codestrata.ai.agents.models import (
    AGENT_NAME,
    AGENT_VERSION,
    AgentExecutionStatus,
    AgentExecutionTrace,
    ModernizationAssessmentResult,
)
from codestrata.ai.agents.trace import new_trace_id, utc_now
from codestrata.ai.contracts import LLMAnalysisContextBuilder
from codestrata.ai.contracts.models import LLMAnalysisContext
from codestrata.ai.enrichment.artifacts import write_ai_enrichment_artifact
from codestrata.ai.enrichment.context import (
    AiEnrichmentBudgetError,
    AiEnrichmentContext,
    AiEnrichmentContextLimits,
    build_ai_enrichment_context,
)
from codestrata.ai.enrichment.parsing import (
    bridge_enrichment_to_recommendation,
    enrichment_from_invocation,
)
from codestrata.ai.enrichment.prompt import (
    AiEnrichmentPromptBuilder,
    AiEnrichmentPromptBuildError,
    AiEnrichmentPromptOptions,
)
from codestrata.ai.prompts.models import PromptBuildOptions, PromptRequest
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderError,
    AIProviderTimeoutError,
    AIResponseParsingError,
    AIResponseValidationError,
)
from codestrata.ai.providers.models import ModelInvocationOptions, ModernizationModelRequest
from codestrata.domain.ai_enrichment import AiEnrichmentResult
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.repository_graph import RepositoryGraph
from codestrata.models import AnalysisResult


@dataclass(frozen=True, slots=True)
class AiEnrichmentRunResult:
    """Successful enrichment plus report-compatible assessment payload."""

    enrichment: AiEnrichmentResult
    enrichment_context: AiEnrichmentContext
    analysis_context: LLMAnalysisContext
    assessment_result: ModernizationAssessmentResult
    prompt_request: PromptRequest


class AiEnrichmentService:
    """Build compact context, invoke provider once, validate enrichment."""

    def __init__(
        self,
        provider: AIModelProvider,
        *,
        prompt_builder: AiEnrichmentPromptBuilder | None = None,
        context_builder: LLMAnalysisContextBuilder | None = None,
    ) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or AiEnrichmentPromptBuilder()
        self._context_builder = context_builder or LLMAnalysisContextBuilder()

    def run(
        self,
        *,
        analysis_result: AnalysisResult,
        rule_evaluation: RuleEvaluationResult,
        recommendation_result: RecommendationResult,
        repository_graph: RepositoryGraph | None,
        model_options: ModelInvocationOptions,
        context_limits: AiEnrichmentContextLimits | None = None,
        prompt_options: AiEnrichmentPromptOptions | None = None,
        phase1_prompt_options: PromptBuildOptions | None = None,
    ) -> AiEnrichmentRunResult:
        """Execute enrichment with exactly one provider.invoke call."""

        _ = phase1_prompt_options  # reserved for future shared budgeting
        enrichment_context = build_ai_enrichment_context(
            analysis_result=analysis_result,
            rule_evaluation=rule_evaluation,
            recommendation_result=recommendation_result,
            repository_graph=repository_graph,
            limits=context_limits,
        )
        prompt_request = self._prompt_builder.build(
            enrichment_context,
            options=prompt_options,
        )
        # Phase 1 context remains available for report/AI-execution compatibility.
        analysis_context = self._context_builder.build(analysis_result)
        request = ModernizationModelRequest(
            prompt_request=prompt_request,
            analysis_context=analysis_context,
        )
        invocation = self._provider.invoke(request, model_options)
        enrichment = enrichment_from_invocation(invocation, enrichment_context)
        recommendation = bridge_enrichment_to_recommendation(
            enrichment,
            context=enrichment_context,
            analysis_context=analysis_context,
        )
        started = utc_now()
        completed = utc_now()
        prompt_hash = _stable_hash(
            {
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in prompt_request.messages
                ]
            }
        )
        context_hash = _stable_hash(enrichment_context.model_dump(mode="json"))
        latency_ms = max(0.0, (completed - started).total_seconds() * 1000.0)
        assessment = ModernizationAssessmentResult(
            recommendation_result=recommendation,
            model_metadata=invocation.metadata,
            trace=AgentExecutionTrace(
                trace_id=new_trace_id(),
                agent_name=AGENT_NAME,
                agent_version=AGENT_VERSION,
                started_at_utc=started,
                completed_at_utc=completed,
                total_latency_ms=latency_ms,
                status=AgentExecutionStatus.COMPLETED,
                steps=(),
                tool_call_count=0,
                model_call_count=1,
                input_tokens=invocation.metadata.usage.input_tokens,
                output_tokens=invocation.metadata.usage.output_tokens,
                total_tokens=invocation.metadata.usage.total_tokens,
            ),
            raw_model_response=invocation.raw_response_text,
            parsed_model_response=invocation.parsed_model_response
            or enrichment.model_dump(mode="json"),
            prompt_template_version=prompt_request.metadata.prompt_template_version,
            prompt_hash=prompt_hash,
            context_hash=context_hash,
            normalization_removals=invocation.normalization_removals,
        )
        return AiEnrichmentRunResult(
            enrichment=enrichment,
            enrichment_context=enrichment_context,
            analysis_context=analysis_context,
            assessment_result=assessment,
            prompt_request=prompt_request,
        )


def _stable_hash(payload: object) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "AIProviderError",
    "AIProviderTimeoutError",
    "AIResponseParsingError",
    "AIResponseValidationError",
    "AiEnrichmentBudgetError",
    "AiEnrichmentPromptBuildError",
    "AiEnrichmentRunResult",
    "AiEnrichmentService",
    "write_ai_enrichment_artifact",
]
