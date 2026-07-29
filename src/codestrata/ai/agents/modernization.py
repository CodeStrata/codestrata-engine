"""Modernization assessment agent orchestration."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from codestrata.ai.agents.exceptions import (
    AgentConfigurationError,
    AgentError,
    AgentExecutionError,
    AgentToolError,
    AgentValidationError,
)
from codestrata.ai.agents.models import (
    AgentExecutionOptions,
    AgentExecutionStatus,
    AgentStepType,
    JSONValue,
    ModernizationAssessmentResult,
)
from codestrata.ai.agents.trace import AgentTraceRecorder, summary_size, utc_now
from codestrata.ai.contracts.models import LLMAnalysisContext
from codestrata.ai.prompts.builder import ModernizationPromptBuilder
from codestrata.ai.prompts.models import PromptBuildError, PromptRequest
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderError,
    AIProviderTimeoutError,
    AIResponseParsingError,
    AIResponseValidationError,
)
from codestrata.ai.providers.models import (
    ModelInvocationResult,
    ModernizationModelRequest,
)
from codestrata.ai.providers.parsing import sanitize_provider_text
from codestrata.ai.recommendations.models import AIRecommendationResult
from codestrata.ai.recommendations.validation import (
    AIRecommendationValidationError,
    DeterministicRecommendationNormalizationRemoval,
    validate_recommendation_result_outcome,
)
from codestrata.ai.tools import CodeStrataToolRegistry, build_analysis_tool_registry
from codestrata.ai.tools.models import CodeStrataToolResult

REQUIRED_TOOL_SEQUENCE: tuple[str, ...] = (
    "get_repository_context",
    "list_technologies",
    "get_repository_metrics",
    "get_evidence_coverage",
    "get_llm_analysis_context",
)


class ModernizationAssessmentAgent:
    """Coordinate tools, prompt building, model invocation, and validation."""

    def __init__(
        self,
        provider: AIModelProvider,
        *,
        prompt_builder: ModernizationPromptBuilder | None = None,
        tool_registry: CodeStrataToolRegistry | None = None,
    ) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or ModernizationPromptBuilder()
        self._tool_registry = tool_registry

    def run(
        self,
        context: LLMAnalysisContext,
        options: AgentExecutionOptions,
    ) -> ModernizationAssessmentResult:
        """Execute a deterministic modernization assessment workflow."""

        recorder = AgentTraceRecorder()
        try:
            registry = self._resolve_registry(context)
            self._validate_tool_configuration(registry, options, recorder)

            for tool_name in REQUIRED_TOOL_SEQUENCE:
                self._execute_tool(registry, tool_name, recorder, options)

            prompt_request = self._build_prompt(context, options, recorder)
            model_result = self._invoke_model(
                context,
                prompt_request,
                options,
                recorder,
            )
            if model_result.recommendation_result is None:
                raise AIResponseParsingError(
                    "Model response did not include a recommendation result "
                    "(Modernization Advisor JSON is handled by AiEnrichmentService)",
                    metadata=model_result.metadata,
                    raw_response_text=model_result.raw_response_text,
                )
            recommendation_result, normalization_removals = self._validate_recommendations(
                model_result.recommendation_result,
                context,
                recorder,
            )
            if model_result.normalization_removals:
                normalization_removals = model_result.normalization_removals

            prompt_hash = _stable_content_hash(
                {
                    "template_version": prompt_request.metadata.prompt_template_version,
                    "messages": [
                        {"role": message.role, "content": message.content}
                        for message in prompt_request.messages
                    ],
                }
            )
            context_hash = _stable_content_hash(context.model_dump(mode="json"))

            trace = recorder.finalize(AgentExecutionStatus.COMPLETED)
            return ModernizationAssessmentResult(
                recommendation_result=recommendation_result,
                model_metadata=model_result.metadata,
                trace=trace,
                # Always retain raw text for the internal AI execution artifact.
                # Customer HTML/JSON never serialize this field.
                raw_model_response=model_result.raw_response_text,
                parsed_model_response=model_result.parsed_model_response,
                normalization_removals=normalization_removals,
                prompt_template_version=prompt_request.metadata.prompt_template_version,
                prompt_hash=prompt_hash,
                context_hash=context_hash,
            )
        except AgentError:
            raise
        except Exception as error:  # noqa: BLE001 - agent boundary
            trace = recorder.finalize(AgentExecutionStatus.FAILED)
            raise AgentExecutionError(
                "Modernization assessment agent failed: " + sanitize_provider_text(str(error)),
                trace=trace,
            ) from error

    def _resolve_registry(self, context: LLMAnalysisContext) -> CodeStrataToolRegistry:
        if self._tool_registry is not None:
            return self._tool_registry
        return build_analysis_tool_registry(context)

    def _validate_tool_configuration(
        self,
        registry: CodeStrataToolRegistry,
        options: AgentExecutionOptions,
        recorder: AgentTraceRecorder,
    ) -> None:
        available = {name.lower(): name for name in registry.list_names()}
        enabled = options.enabled_tool_names

        if enabled is not None:
            for name in enabled:
                if name.lower() not in available:
                    raise AgentConfigurationError(
                        f"Unknown enabled tool: {name}",
                        trace=recorder.finalize(AgentExecutionStatus.FAILED),
                    )

            enabled_keys = {name.lower() for name in enabled}
            for required in REQUIRED_TOOL_SEQUENCE:
                if required.lower() not in enabled_keys:
                    raise AgentConfigurationError(
                        f"Required tool is disabled: {required}",
                        trace=recorder.finalize(AgentExecutionStatus.FAILED),
                    )
        else:
            enabled_keys = {name.lower() for name in REQUIRED_TOOL_SEQUENCE}

        for required in REQUIRED_TOOL_SEQUENCE:
            if required.lower() not in available:
                raise AgentConfigurationError(
                    f"Required tool is not registered: {required}",
                    trace=recorder.finalize(AgentExecutionStatus.FAILED),
                )
            if required.lower() not in enabled_keys:
                raise AgentConfigurationError(
                    f"Required tool is disabled: {required}",
                    trace=recorder.finalize(AgentExecutionStatus.FAILED),
                )

        if len(REQUIRED_TOOL_SEQUENCE) > options.max_tool_calls:
            raise AgentConfigurationError(
                "Configured max_tool_calls is too low for the required tool "
                f"sequence ({len(REQUIRED_TOOL_SEQUENCE)} > {options.max_tool_calls})",
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            )

    def _execute_tool(
        self,
        registry: CodeStrataToolRegistry,
        tool_name: str,
        recorder: AgentTraceRecorder,
        options: AgentExecutionOptions,
    ) -> CodeStrataToolResult:
        if recorder.tool_call_count >= options.max_tool_calls:
            error = AgentConfigurationError(f"max_tool_calls exceeded ({options.max_tool_calls})")
            recorder.record_step(
                step_type=AgentStepType.TOOL_CALL,
                name=tool_name,
                started_at_utc=utc_now(),
                started_perf=time.perf_counter(),
                success=False,
                input_summary={"tool_name": tool_name},
                error=error,
            )
            raise AgentConfigurationError(
                f"max_tool_calls exceeded ({options.max_tool_calls})",
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            )

        started_at = utc_now()
        started_perf = time.perf_counter()
        input_summary: dict[str, JSONValue] = {"tool_name": tool_name}
        result = registry.execute(tool_name, {})
        if not result.success:
            tool_error = AgentToolError(
                sanitize_provider_text(result.error or f"Tool '{tool_name}' failed")
            )
            recorder.record_step(
                step_type=AgentStepType.TOOL_CALL,
                name=result.tool_name or tool_name,
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                output_summary={},
                error=tool_error,
            )
            raise AgentToolError(
                sanitize_provider_text(result.error or f"Tool '{tool_name}' failed"),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from tool_error

        recorder.record_step(
            step_type=AgentStepType.TOOL_CALL,
            name=result.tool_name,
            started_at_utc=started_at,
            started_perf=started_perf,
            success=True,
            input_summary=input_summary,
            output_summary=_tool_output_summary(result),
        )
        return result

    def _build_prompt(
        self,
        context: LLMAnalysisContext,
        options: AgentExecutionOptions,
        recorder: AgentTraceRecorder,
    ) -> PromptRequest:
        started_at = utc_now()
        started_perf = time.perf_counter()
        input_summary: dict[str, JSONValue] = {
            "finding_count": len(context.findings),
            "technology_count": len(context.technologies),
            "context_truncated": context.findings_truncation.truncated,
            "template_version": options.prompt_options.template_version,
        }
        try:
            prompt_request = self._prompt_builder.build(context, options.prompt_options)
        except PromptBuildError as error:
            recorder.record_step(
                step_type=AgentStepType.PROMPT_BUILD,
                name="build_prompt_request",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentExecutionError(
                "Prompt construction failed: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error
        except Exception as error:  # noqa: BLE001 - agent boundary
            recorder.record_step(
                step_type=AgentStepType.PROMPT_BUILD,
                name="build_prompt_request",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentExecutionError(
                "Prompt construction failed: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error

        recorder.record_step(
            step_type=AgentStepType.PROMPT_BUILD,
            name="build_prompt_request",
            started_at_utc=started_at,
            started_perf=started_perf,
            success=True,
            input_summary=input_summary,
            output_summary={
                "message_count": len(prompt_request.messages),
                "context_json_size": summary_size(prompt_request.context_json),
                "schema_json_size": summary_size(prompt_request.expected_output_schema_json),
                "repository_identifier": prompt_request.metadata.repository_identifier,
                "prompt_template_version": (prompt_request.metadata.prompt_template_version),
                "finding_count": prompt_request.metadata.finding_count,
                "technology_count": prompt_request.metadata.technology_count,
            },
        )
        return prompt_request

    def _invoke_model(
        self,
        context: LLMAnalysisContext,
        prompt_request: PromptRequest,
        options: AgentExecutionOptions,
        recorder: AgentTraceRecorder,
    ) -> ModelInvocationResult:
        started_at = utc_now()
        started_perf = time.perf_counter()
        input_summary: dict[str, JSONValue] = {
            "model_id": options.model_options.model_id,
            "temperature": options.model_options.temperature,
            "max_output_tokens": options.model_options.max_output_tokens,
            "prompt_message_count": len(prompt_request.messages),
            "context_json_size": summary_size(prompt_request.context_json),
        }
        request = ModernizationModelRequest(
            prompt_request=prompt_request,
            analysis_context=context,
        )
        try:
            result = self._provider.invoke(request, options.model_options)
        except AIProviderTimeoutError as error:
            recorder.record_step(
                step_type=AgentStepType.MODEL_INVOCATION,
                name="invoke_model",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentExecutionError(
                "Model provider timed out: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error
        except (AIResponseValidationError, AIResponseParsingError) as error:
            recorder.record_step(
                step_type=AgentStepType.MODEL_INVOCATION,
                name="invoke_model",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentValidationError(
                "Model response validation failed: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error
        except AIProviderError as error:
            recorder.record_step(
                step_type=AgentStepType.MODEL_INVOCATION,
                name="invoke_model",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentExecutionError(
                "Model provider invocation failed: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error
        except Exception as error:  # noqa: BLE001 - agent boundary
            recorder.record_step(
                step_type=AgentStepType.MODEL_INVOCATION,
                name="invoke_model",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentExecutionError(
                "Model provider invocation failed: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error

        usage = result.metadata.usage
        recorder.set_token_usage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
        )
        recommendation = result.recommendation_result
        recommendation_count = (
            len(recommendation.recommendations) if recommendation is not None else 0
        )
        phase_count = (
            len(recommendation.modernization_phases) if recommendation is not None else 0
        )
        limitation_count = len(recommendation.limitations) if recommendation is not None else 0
        recorder.record_step(
            step_type=AgentStepType.MODEL_INVOCATION,
            name="invoke_model",
            started_at_utc=started_at,
            started_perf=started_perf,
            success=True,
            input_summary=input_summary,
            output_summary={
                "provider": result.metadata.provider,
                "model_id": result.metadata.model_id,
                "request_id": result.metadata.request_id,
                "stop_reason": result.metadata.stop_reason,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "recommendation_count": recommendation_count,
                "phase_count": phase_count,
                "limitation_count": limitation_count,
                "raw_response_size": summary_size(result.raw_response_text),
            },
        )
        return result

    def _validate_recommendations(
        self,
        recommendation_result: AIRecommendationResult,
        context: LLMAnalysisContext,
        recorder: AgentTraceRecorder,
    ) -> tuple[AIRecommendationResult, tuple[DeterministicRecommendationNormalizationRemoval, ...]]:
        started_at = utc_now()
        started_perf = time.perf_counter()
        input_summary: dict[str, JSONValue] = {
            "recommendation_count": len(recommendation_result.recommendations),
            "phase_count": len(recommendation_result.modernization_phases),
            "limitation_count": len(recommendation_result.limitations),
            "finding_count": len(context.findings),
        }
        try:
            outcome = validate_recommendation_result_outcome(recommendation_result, context)
            validated = outcome.result
        except AIRecommendationValidationError as error:
            recorder.record_step(
                step_type=AgentStepType.VALIDATION,
                name="validate_recommendation_result",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentValidationError(
                "Final recommendation validation failed: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error
        except Exception as error:  # noqa: BLE001 - agent boundary
            recorder.record_step(
                step_type=AgentStepType.VALIDATION,
                name="validate_recommendation_result",
                started_at_utc=started_at,
                started_perf=started_perf,
                success=False,
                input_summary=input_summary,
                error=error,
            )
            raise AgentValidationError(
                "Final recommendation validation failed: " + sanitize_provider_text(str(error)),
                trace=recorder.finalize(AgentExecutionStatus.FAILED),
            ) from error

        output_summary: dict[str, JSONValue] = {
            "recommendation_count": len(validated.recommendations),
            "phase_count": len(validated.modernization_phases),
            "limitation_count": len(validated.limitations),
            "schema_version": validated.schema_version,
        }
        if outcome.removed_unknown_deterministic_recommendation_ids:
            output_summary["removed_unknown_deterministic_recommendation_ids"] = list(
                outcome.removed_unknown_deterministic_recommendation_ids
            )
        recorder.record_step(
            step_type=AgentStepType.VALIDATION,
            name="validate_recommendation_result",
            started_at_utc=started_at,
            started_perf=started_perf,
            success=True,
            input_summary=input_summary,
            output_summary=output_summary,
        )
        return validated, outcome.normalization_removals


def _stable_content_hash(payload: str | bytes | dict[str, Any] | list[Any]) -> str:
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _tool_output_summary(result: CodeStrataToolResult) -> dict[str, JSONValue]:
    data = result.data if isinstance(result.data, dict) else {}
    summary: dict[str, JSONValue] = {"tool_name": result.tool_name, "success": True}

    if "repository" in data and isinstance(data["repository"], dict):
        repository = data["repository"]
        summary["repository_identifier"] = repository.get("name")
        summary["source_type"] = repository.get("source_type")
        summary["file_count"] = repository.get("file_count")

    if "count" in data:
        summary["technology_count"] = data.get("count")
    if "technologies" in data and isinstance(data["technologies"], list):
        summary["technology_count"] = len(data["technologies"])

    if "metrics" in data and isinstance(data["metrics"], dict):
        metrics = data["metrics"]
        summary["finding_count"] = metrics.get("finding_count")
        summary["technology_count"] = metrics.get("technology_count")
        summary["file_count"] = metrics.get("file_count")

    for key in (
        "finding_count",
        "findings_included",
        "findings_original_count",
        "findings_truncated",
        "findings_with_evidence",
        "total_evidence_locations",
    ):
        if key in data:
            summary[key] = data.get(key)

    if "context" in data and isinstance(data["context"], dict):
        context = data["context"]
        summary["context_schema_version"] = context.get("schema_version")
        findings = context.get("findings")
        technologies = context.get("technologies")
        summary["finding_count"] = len(findings) if isinstance(findings, list) else 0
        summary["technology_count"] = len(technologies) if isinstance(technologies, list) else 0
        truncation = context.get("findings_truncation")
        if isinstance(truncation, dict):
            summary["context_truncated"] = truncation.get("truncated")
        summary["context_size"] = summary_size(context)

    return {key: value for key, value in summary.items() if value is not None}
