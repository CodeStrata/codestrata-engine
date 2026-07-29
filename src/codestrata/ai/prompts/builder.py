"""Build provider-neutral modernization assessment prompt packages."""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.contracts.models import LLM_CONTRACT_SCHEMA_VERSION, LLMAnalysisContext
from codestrata.ai.contracts.serialization import llm_context_to_json
from codestrata.ai.prompts.models import (
    PromptBuildError,
    PromptBuildOptions,
    PromptMessage,
    PromptMetadata,
    PromptRequest,
)
from codestrata.ai.prompts.templates import (
    developer_message_content,
    system_message_content,
    user_message_content,
)
from codestrata.ai.recommendations.models import (
    AI_RECOMMENDATION_SCHEMA_VERSION,
    AIRecommendationResult,
)
from codestrata.ai.tools import build_analysis_tool_registry


class ModernizationPromptBuilder:
    """Transform LLMAnalysisContext into a deterministic PromptRequest."""

    def build(
        self,
        context: LLMAnalysisContext,
        options: PromptBuildOptions | None = None,
    ) -> PromptRequest:
        """Build a prompt package for modernization assessment."""

        build_options = options or PromptBuildOptions()
        context_json = llm_context_to_json(context, indent=2)
        if len(context_json) > build_options.max_context_characters:
            raise PromptBuildError(
                "LLMAnalysisContext JSON exceeds max_context_characters "
                f"({len(context_json)} > {build_options.max_context_characters})"
            )

        expected_output_schema_json = _recommendation_schema_json()
        metadata = _build_metadata(context, build_options.template_version)

        messages = [
            PromptMessage(
                role="system",
                content=system_message_content(template_version=build_options.template_version),
            ),
            PromptMessage(
                role="developer",
                content=developer_message_content(template_version=build_options.template_version),
            ),
            PromptMessage(
                role="user",
                content=user_message_content(
                    template_version=build_options.template_version,
                    repository_identifier=metadata.repository_identifier,
                    include_context_json=build_options.include_context_json,
                    include_output_schema=build_options.include_output_schema,
                    context_json=context_json,
                    expected_output_schema_json=expected_output_schema_json,
                ),
            ),
        ]

        return PromptRequest(
            messages=messages,
            context_json=context_json,
            expected_output_schema_json=expected_output_schema_json,
            metadata=metadata,
        )


def _recommendation_schema_json() -> str:
    schema = AIRecommendationResult.model_json_schema(mode="validation")
    return json.dumps(
        schema,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ": "),
    )


def _build_metadata(
    context: LLMAnalysisContext,
    template_version: str,
) -> PromptMetadata:
    """Derive metadata through the CodeStrata tool layer where practical."""

    registry = build_analysis_tool_registry(context)
    repository_result = registry.execute("get_repository_context")
    technologies_result = registry.execute("list_technologies")
    coverage_result = registry.execute("get_evidence_coverage")
    context_result = registry.execute("get_llm_analysis_context")

    if not all(
        (
            repository_result.success,
            technologies_result.success,
            coverage_result.success,
            context_result.success,
        )
    ):
        errors = [
            item.error
            for item in (
                repository_result,
                technologies_result,
                coverage_result,
                context_result,
            )
            if not item.success and item.error
        ]
        raise PromptBuildError(
            "Failed to read analysis context through CodeStrata tools: " + "; ".join(errors)
        )

    repository_data = _require_mapping(repository_result.data, "repository")
    repository = _require_mapping(repository_data.get("repository"), "repository")
    repository_identifier = str(repository.get("name") or "").strip()
    if not repository_identifier:
        raise PromptBuildError("Repository identifier is missing from analysis context")

    technologies_data = _require_mapping(technologies_result.data, "technologies")
    technology_count = int(technologies_data.get("count", 0))

    coverage_data = _require_mapping(coverage_result.data, "coverage")
    finding_count = int(coverage_data.get("finding_count", 0))
    context_truncated = bool(coverage_data.get("findings_truncated", False))

    # Preserve truncation metadata already present on the context contract.
    context_data = _require_mapping(context_result.data, "context")
    nested_context = _require_mapping(context_data.get("context"), "context")
    truncation = _require_mapping(
        nested_context.get("findings_truncation"),
        "findings_truncation",
    )
    if bool(truncation.get("truncated")) != context_truncated:
        context_truncated = bool(truncation.get("truncated"))

    return PromptMetadata(
        repository_identifier=repository_identifier,
        context_schema_version=LLM_CONTRACT_SCHEMA_VERSION,
        recommendation_schema_version=AI_RECOMMENDATION_SCHEMA_VERSION,
        finding_count=finding_count,
        technology_count=technology_count,
        context_truncated=context_truncated,
        prompt_template_version=template_version,
    )


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PromptBuildError(f"Expected mapping for {label}")
    return value
