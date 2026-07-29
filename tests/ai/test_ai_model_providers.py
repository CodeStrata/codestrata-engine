"""Tests for CodeStrata optional AI model providers and Bedrock Converse integration."""

from __future__ import annotations

import importlib
import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from pydantic import ValidationError

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
)
from codestrata.ai.prompts import ModernizationPromptBuilder
from codestrata.ai.prompts.models import PromptMessage, PromptMetadata, PromptRequest
from codestrata.ai.providers import (
    AIModelProvider,
    AIProviderInvocationError,
    AIProviderTimeoutError,
    AIResponseParsingError,
    AIResponseValidationError,
    BedrockAIModelProvider,
    ModelInvocationMetadata,
    ModelInvocationOptions,
    ModelInvocationResult,
    ModelUsage,
    ModernizationModelRequest,
    parse_recommendation_response,
)
from codestrata.ai.providers import bedrock as bedrock_module
from codestrata.ai.providers.bedrock import (
    build_converse_request,
    extract_converse_response,
    split_prompt_for_converse,
)
from codestrata.ai.providers.parsing import sanitize_provider_text
from codestrata.ai.recommendations import (
    AIRecommendation,
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
    AIRecommendationResult,
    EvidenceCoverage,
    ModernizationPhase,
    ai_recommendation_result_to_json,
)
from codestrata.config import DEFAULT_BEDROCK_MODEL_ID


def _truncation(count: int = 0, *, truncated: bool = False) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=truncated,
        original_count=count,
        included_count=count,
    )


def _context(*rule_ids: str) -> LLMAnalysisContext:
    findings = [
        LLMFindingEvidence(
            rule_id=rule_id,
            title=f"Finding {rule_id}",
            category="security",
            severity="high",
            summary=f"Summary {rule_id}",
            evidence_truncation=_truncation(),
        )
        for rule_id in rule_ids
    ]
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="sample-app",
            source_type="github",
            file_count=3,
        ),
        metrics=LLMMetricsContext(
            finding_count=len(findings),
            technology_count=0,
        ),
        findings=findings,
        findings_truncation=_truncation(len(findings)),
    )


def _recommendation(
    recommendation_id: str,
    *,
    related: list[str] | None = None,
    dependencies: list[str] | None = None,
) -> AIRecommendation:
    return AIRecommendation(
        recommendation_id=recommendation_id,
        title=f"Title {recommendation_id}",
        description=f"Description {recommendation_id}",
        rationale=f"Rationale {recommendation_id}",
        priority=AIRecommendationPriority.HIGH,
        effort=AIRecommendationEffort.MEDIUM,
        impact=AIRecommendationImpact.HIGH,
        confidence=AIRecommendationConfidence.MEDIUM,
        related_finding_ids=related or [],
        suggested_actions=["Take action"],
        dependencies=dependencies or [],
    )


def _valid_result() -> AIRecommendationResult:
    return AIRecommendationResult(
        executive_summary="Executive summary.",
        overall_assessment="Overall assessment.",
        key_risks=["Secret exposure"],
        recommendations=[
            _recommendation("AI-REC-001", related=["SEC001"]),
            _recommendation("AI-REC-002", related=["SEC002"], dependencies=["AI-REC-001"]),
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Address critical gaps",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Lower risk"],
            ),
            ModernizationPhase(
                phase=2,
                name="Hardening",
                objective="Continue modernization",
                recommendations=["AI-REC-002"],
                expected_outcomes=["Safer releases"],
            ),
        ],
        evidence_coverage=EvidenceCoverage(
            total_findings=2,
            findings_considered=2,
            findings_referenced=2,
            coverage_percentage=100.0,
            input_truncated=False,
        ),
        limitations=["No runtime profiling data."],
    )


def _prompt_request(context: LLMAnalysisContext) -> PromptRequest:
    return ModernizationPromptBuilder().build(context)


def _model_request(context: LLMAnalysisContext | None = None) -> ModernizationModelRequest:
    analysis_context = context or _context("SEC001", "SEC002")
    return ModernizationModelRequest(
        prompt_request=_prompt_request(analysis_context),
        analysis_context=analysis_context,
    )


def _options(
    *,
    model_id: str = DEFAULT_BEDROCK_MODEL_ID,
    temperature: float = 0.0,
    max_output_tokens: int = 2048,
    timeout_seconds: float = 30.0,
    request_id: str | None = None,
) -> ModelInvocationOptions:
    return ModelInvocationOptions(
        model_id=model_id,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        request_id=request_id,
    )


def _converse_response(
    text: str | list[str],
    *,
    input_tokens: int | None = 11,
    output_tokens: int | None = 22,
    total_tokens: int | None = None,
    stop_reason: str = "end_turn",
    request_id: str = "req-123",
    latency_ms: float | None = None,
    include_usage: bool = True,
) -> dict[str, Any]:
    blocks = [{"text": item} for item in ([text] if isinstance(text, str) else text)]
    response: dict[str, Any] = {
        "output": {
            "message": {
                "role": "assistant",
                "content": blocks,
            }
        },
        "stopReason": stop_reason,
        "ResponseMetadata": {"RequestId": request_id},
    }
    if include_usage:
        usage: dict[str, Any] = {}
        if input_tokens is not None:
            usage["inputTokens"] = input_tokens
        if output_tokens is not None:
            usage["outputTokens"] = output_tokens
        if total_tokens is not None:
            usage["totalTokens"] = total_tokens
        response["usage"] = usage
    if latency_ms is not None:
        response["metrics"] = {"latencyMs": latency_ms}
    return response


def _client_error(code: str, message: str = "boom") -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"RequestId": "err-1"},
        },
        "Converse",
    )


class _FakeProvider(AIModelProvider):
    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        return ModelInvocationResult(
            recommendation_result=_valid_result(),
            metadata=ModelInvocationMetadata(
                provider="fake",
                model_id=options.model_id,
                request_id=options.request_id,
                latency_ms=1.0,
                usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
                stop_reason="end",
            ),
            raw_response_text="{}",
        )


def test_provider_abstraction() -> None:
    provider: AIModelProvider = _FakeProvider()
    result = provider.invoke(_model_request(), _options())
    assert result.metadata.provider == "fake"
    assert result.recommendation_result.recommendations[0].recommendation_id == "AI-REC-001"


def test_successful_bedrock_converse_invocation() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None),
        latency_ms=42.5,
    )
    provider = BedrockAIModelProvider(client=client)
    request = _model_request()
    result = provider.invoke(request, _options(request_id="client-req"))

    assert result.recommendation_result == _valid_result()
    assert result.metadata.provider == "bedrock"
    assert result.metadata.model_id == DEFAULT_BEDROCK_MODEL_ID
    assert result.metadata.request_id == "client-req"
    assert result.metadata.stop_reason == "end_turn"
    assert result.metadata.usage == ModelUsage(
        input_tokens=11,
        output_tokens=22,
        total_tokens=33,
    )
    assert result.metadata.latency_ms == 42.5
    assert result.raw_response_text
    client.converse.assert_called_once()
    client.invoke_model.assert_not_called()


def test_converse_request_includes_system_and_user() -> None:
    request = _model_request()
    options = _options(temperature=0.0, max_output_tokens=1024)
    first = build_converse_request(request.prompt_request, options)
    second = build_converse_request(request.prompt_request, options)
    assert first == second
    assert first["modelId"] == DEFAULT_BEDROCK_MODEL_ID
    assert first["inferenceConfig"] == {"maxTokens": 1024, "temperature": 0.0}
    assert first["system"][0]["text"]
    assert "JSON object" in first["system"][0]["text"]
    assert first["messages"][0]["role"] == "user"
    assert "text" in first["messages"][0]["content"][0]
    assert "anthropic" not in json.dumps(first).lower()


def test_system_developer_user_message_mapping() -> None:
    prompt = PromptRequest(
        messages=[
            PromptMessage(role="system", content="System rules"),
            PromptMessage(role="developer", content="Developer rules"),
            PromptMessage(role="user", content="Assess this repository"),
        ],
        context_json="{}",
        expected_output_schema_json="{}",
        metadata=PromptMetadata(
            repository_identifier="sample-app",
            context_schema_version="1.0.0",
            recommendation_schema_version="1.0.0",
            finding_count=0,
            technology_count=0,
            context_truncated=False,
            prompt_template_version="1.0.0",
        ),
    )
    system_text, user_text = split_prompt_for_converse(prompt.messages)
    assert "System rules" in system_text
    assert "Developer instructions:\nDeveloper rules" in system_text
    assert "JSON object only" in system_text
    assert user_text == "Assess this repository"
    assert "Assess this repository" not in system_text


def test_configurable_nova_model_id() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None)
    )
    provider = BedrockAIModelProvider(client=client)
    provider.invoke(_model_request(), _options(model_id="amazon.nova-lite-v1:0"))
    assert client.converse.call_args.kwargs["modelId"] == "amazon.nova-lite-v1:0"


def test_temperature_and_token_options() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None)
    )
    provider = BedrockAIModelProvider(client=client)
    provider.invoke(
        _model_request(),
        _options(temperature=0.2, max_output_tokens=512),
    )
    kwargs = client.converse.call_args.kwargs
    assert kwargs["inferenceConfig"]["temperature"] == 0.2
    assert kwargs["inferenceConfig"]["maxTokens"] == 512


def test_multiple_text_blocks_are_concatenated() -> None:
    client = MagicMock()
    payload = ai_recommendation_result_to_json(_valid_result(), indent=None)
    mid = len(payload) // 2
    client.converse.return_value = _converse_response([payload[:mid], payload[mid:]])
    provider = BedrockAIModelProvider(client=client)
    result = provider.invoke(_model_request(), _options())
    assert result.recommendation_result == _valid_result()
    assert result.raw_response_text == payload


def test_missing_usage_metadata_is_tolerated() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None),
        include_usage=False,
    )
    provider = BedrockAIModelProvider(client=client)
    result = provider.invoke(_model_request(), _options())
    assert result.metadata.usage == ModelUsage()
    assert result.metadata.stop_reason == "end_turn"


def test_empty_output_content_rejected() -> None:
    client = MagicMock()
    client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": []}},
        "stopReason": "end_turn",
    }
    provider = BedrockAIModelProvider(client=client)
    with pytest.raises(AIProviderInvocationError, match="assistant text content"):
        provider.invoke(_model_request(), _options())


def test_missing_output_structure_rejected() -> None:
    client = MagicMock()
    client.converse.return_value = {"stopReason": "end_turn"}
    provider = BedrockAIModelProvider(client=client)
    with pytest.raises(AIProviderInvocationError, match="missing output"):
        provider.invoke(_model_request(), _options())


def test_extract_converse_response_helpers() -> None:
    text, usage, stop_reason, request_id, latency = extract_converse_response(
        _converse_response("hello", latency_ms=12.0, total_tokens=40)
    )
    assert text == "hello"
    assert usage.total_tokens == 40
    assert stop_reason == "end_turn"
    assert request_id == "req-123"
    assert latency == 12.0


def test_strict_json_parsing() -> None:
    context = _context("SEC001", "SEC002")
    payload = ai_recommendation_result_to_json(_valid_result(), indent=None)
    parsed = parse_recommendation_response(f"  {payload}  ", context)
    assert parsed.result == _valid_result()


def test_fenced_json_parsing() -> None:
    context = _context("SEC001", "SEC002")
    payload = ai_recommendation_result_to_json(_valid_result(), indent=2)
    fenced = f"```json\n{payload}\n```"
    parsed = parse_recommendation_response(fenced, context)
    assert parsed.result == _valid_result()


def test_bare_fenced_json_parsing() -> None:
    context = _context("SEC001", "SEC002")
    payload = ai_recommendation_result_to_json(_valid_result(), indent=2)
    fenced = f"```\n{payload}\n```"
    parsed = parse_recommendation_response(fenced, context)
    assert parsed.result == _valid_result()


def test_prose_rejection() -> None:
    context = _context("SEC001", "SEC002")
    payload = ai_recommendation_result_to_json(_valid_result(), indent=None)
    with pytest.raises(AIResponseParsingError, match="single JSON object"):
        parse_recommendation_response(f"Here you go:\n{payload}", context)


def test_malformed_json() -> None:
    with pytest.raises(AIResponseParsingError):
        parse_recommendation_response("{not-json", _context("SEC001"))


def test_multiple_object_rejection() -> None:
    with pytest.raises(AIResponseParsingError, match="exactly one JSON object"):
        parse_recommendation_response('{"a": 1}{"b": 2}', _context())


def test_invalid_recommendation_schema() -> None:
    with pytest.raises(AIResponseValidationError, match="AIRecommendationResult") as info:
        parse_recommendation_response('{"executive_summary": "only"}', _context())
    assert info.value.raw_response_text == '{"executive_summary": "only"}'
    assert info.value.parsed_payload == {"executive_summary": "only"}


def test_bedrock_validation_failure_preserves_invocation_metadata() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        '{"executive_summary": "only"}',
        input_tokens=15,
        output_tokens=17,
        stop_reason="end_turn",
        request_id="amzn-req-validation",
    )
    provider = BedrockAIModelProvider(client=client)
    with pytest.raises(AIResponseValidationError) as info:
        provider.invoke(_model_request(), _options())
    error = info.value
    assert error.metadata is not None
    assert error.metadata.provider == "bedrock"
    assert error.metadata.usage.input_tokens == 15
    assert error.metadata.usage.output_tokens == 17
    assert error.metadata.stop_reason == "end_turn"
    assert error.raw_response_text == '{"executive_summary": "only"}'
    assert error.parsed_payload == {"executive_summary": "only"}


def test_usage_latency_request_id_and_stop_reason() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None),
        input_tokens=5,
        output_tokens=7,
        stop_reason="max_tokens",
        request_id="amzn-req-9",
    )
    provider = BedrockAIModelProvider(client=client)
    result = provider.invoke(_model_request(), _options())
    assert result.metadata.usage.total_tokens == 12
    assert result.metadata.stop_reason == "max_tokens"
    assert result.metadata.request_id == "amzn-req-9"
    assert result.metadata.latency_ms >= 0.0


def test_timeout_mapping() -> None:
    client = MagicMock()
    client.converse.side_effect = ReadTimeoutError(endpoint_url="https://example")
    provider = BedrockAIModelProvider(client=client)
    with pytest.raises(AIProviderTimeoutError, match="timed out"):
        provider.invoke(_model_request(), _options())


def test_throttling_mapping() -> None:
    client = MagicMock()
    client.converse.side_effect = _client_error("ThrottlingException", "slow down")
    provider = BedrockAIModelProvider(client=client)
    with pytest.raises(AIProviderTimeoutError, match="temporary service failure"):
        provider.invoke(_model_request(), _options())


def test_authentication_and_access_denied_mapping() -> None:
    client = MagicMock()
    provider = BedrockAIModelProvider(client=client)

    client.converse.side_effect = _client_error(
        "UnrecognizedClientException",
        "AKIAIOSFODNN7EXAMPLE bad key",
    )
    with pytest.raises(
        AIProviderInvocationError,
        match="Unable to authenticate with AWS",
    ) as auth_info:
        provider.invoke(_model_request(), _options())
    assert "AKIAIOSFODNN7EXAMPLE" not in str(auth_info.value)
    assert "aws sso login" in str(auth_info.value)

    client.converse.side_effect = _client_error("AccessDeniedException", "nope")
    with pytest.raises(AIProviderInvocationError, match="model access denied"):
        provider.invoke(_model_request(), _options())


def test_validation_and_resource_errors() -> None:
    client = MagicMock()
    provider = BedrockAIModelProvider(client=client)
    client.converse.side_effect = _client_error("ValidationException", "bad input")
    with pytest.raises(AIProviderInvocationError, match="invalid model or request"):
        provider.invoke(_model_request(), _options())

    client.converse.side_effect = _client_error("ResourceNotFoundException", "missing")
    with pytest.raises(AIProviderInvocationError, match="invalid model or request"):
        provider.invoke(_model_request(), _options())


def test_generic_provider_failure_mapping() -> None:
    client = MagicMock()
    client.converse.side_effect = RuntimeError("unexpected AKIAIOSFODNN7EXAMPLE")
    provider = BedrockAIModelProvider(client=client)
    with pytest.raises(AIProviderInvocationError, match="invocation failed") as info:
        provider.invoke(_model_request(), _options())
    assert "AKIAIOSFODNN7EXAMPLE" not in str(info.value)
    assert "[REDACTED]" in str(info.value)


def test_exception_sanitization() -> None:
    text = sanitize_provider_text(
        "token=AKIAIOSFODNN7EXAMPLE aws_secret_access_key=abcd1234 secret"
    )
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "abcd1234" not in text
    assert "[REDACTED]" in text


def test_injected_client_usage() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None)
    )
    with patch("codestrata.ai.aws_config.create_bedrock_runtime_client") as factory:
        provider = BedrockAIModelProvider(client=client)
        provider.invoke(_model_request(), _options())
        factory.assert_not_called()
    client.converse.assert_called_once()


def test_no_aws_client_creation_during_module_import() -> None:
    module_name = "codestrata.ai.providers.bedrock"
    with patch("codestrata.ai.aws_config.create_bedrock_runtime_client") as factory:
        if module_name in sys.modules:
            importlib.reload(bedrock_module)
        else:
            importlib.import_module(module_name)
        factory.assert_not_called()


def test_frozen_contracts_and_extra_field_rejection() -> None:
    options = _options()
    usage = ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2)
    metadata = ModelInvocationMetadata(
        provider="bedrock",
        model_id="model",
        request_id=None,
        latency_ms=1.0,
        usage=usage,
        stop_reason=None,
    )
    result = ModelInvocationResult(
        recommendation_result=_valid_result(),
        metadata=metadata,
        raw_response_text="{}",
    )
    with pytest.raises(ValidationError):
        options.temperature = 1.0
    with pytest.raises(ValidationError):
        result.raw_response_text = "changed"
    with pytest.raises(ValidationError):
        ModelInvocationOptions(model_id="m", temperature=0.0, unexpected=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ModelUsage(input_tokens=1, extra=True)  # type: ignore[call-arg]


def test_prompt_request_not_mutated() -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None)
    )
    request = _model_request()
    before = request.prompt_request.model_dump(mode="json")
    BedrockAIModelProvider(client=client).invoke(request, _options())
    assert request.prompt_request.model_dump(mode="json") == before


def test_fenced_json_with_trailing_prose_rejected() -> None:
    payload = ai_recommendation_result_to_json(_valid_result(), indent=None)
    with pytest.raises(AIResponseParsingError):
        parse_recommendation_response(
            f"```json\n{payload}\n```\nthanks", _context("SEC001", "SEC002")
        )


def test_no_anthropic_payload_helpers_exported() -> None:
    assert not hasattr(bedrock_module, "ANTHROPIC_BEDROCK_VERSION")
    assert not hasattr(bedrock_module, "build_anthropic_bedrock_payload")


def test_openai_provider_parses_enrichment_shaped_json() -> None:
    from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider

    enrichment_payload = {
        "executive_summary": {"headline": "H", "narrative": "N"},
        "themes": [{"title": "T", "summary": "S"}],
        "priorities": [],
        "risks": [],
        "suggested_next_steps": [],
        "provider_metadata": {"provider": "openai", "model_id": "gpt-4o-mini"},
        "limitations": [],
    }
    choice = MagicMock()
    choice.message.content = json.dumps(enrichment_payload)
    choice.finish_reason = "stop"
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    response.id = "chatcmpl-test"
    client = MagicMock()
    client.chat.completions.create.return_value = response

    provider = OpenAIAIModelProvider(client=client)
    result = provider.invoke(_model_request(), _options(model_id="gpt-4o-mini"))
    assert result.recommendation_result is None
    assert result.metadata.provider == "openai"
    assert result.metadata.model_id == "gpt-4o-mini"
    assert result.metadata.request_id == "chatcmpl-test"
    assert result.metadata.usage.input_tokens == 10
    assert json.loads(result.raw_response_text)["executive_summary"]["headline"] == "H"
    client.chat.completions.create.assert_called_once()
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["model"] == "gpt-4o-mini"


def test_create_assess_ai_provider_selects_openai() -> None:
    from codestrata.ai.providers.factory import create_assess_ai_provider
    from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
    from codestrata.config import CodestrataSettings

    settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "openai", "openai": {}}}
    )
    provider = create_assess_ai_provider(settings)
    assert isinstance(provider, OpenAIAIModelProvider)


def test_resolve_assess_model_id_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    from codestrata.ai.providers.factory import resolve_assess_model_id
    from codestrata.config import CodestrataSettings

    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "ai": {
                "provider": "openai",
                "openai": {"answer_model": "gpt-4o"},
            },
        }
    )
    monkeypatch.setenv("CODESTRATA_OPENAI_MODEL_ID", "env-openai")
    assert resolve_assess_model_id(cli_model_id="cli", settings=settings) == "cli"
    assert resolve_assess_model_id(cli_model_id=None, settings=settings) == "env-openai"
    monkeypatch.delenv("CODESTRATA_OPENAI_MODEL_ID", raising=False)
    assert resolve_assess_model_id(cli_model_id=None, settings=settings) == "gpt-4o"
