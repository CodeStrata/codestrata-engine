"""Tests for the modernization assessment agent."""

from __future__ import annotations

import ast
import json
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from codestrata.ai.agents import (
    REQUIRED_TOOL_SEQUENCE,
    AgentConfigurationError,
    AgentExecutionError,
    AgentExecutionOptions,
    AgentExecutionStatus,
    AgentExecutionStep,
    AgentStepType,
    AgentToolError,
    AgentValidationError,
    ModernizationAssessmentAgent,
    ModernizationAssessmentResult,
    agent_execution_trace_from_json,
    agent_execution_trace_to_json,
    modernization_assessment_result_from_json,
    modernization_assessment_result_to_json,
)
from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMEvidenceLocation,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
    LLMTechnologyEvidence,
)
from codestrata.ai.prompts import ModernizationPromptBuilder, PromptBuildOptions
from codestrata.ai.prompts.models import PromptBuildError
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderInvocationError,
    AIProviderTimeoutError,
    AIResponseValidationError,
)
from codestrata.ai.providers.models import (
    ModelInvocationMetadata,
    ModelInvocationOptions,
    ModelInvocationResult,
    ModelUsage,
    ModernizationModelRequest,
)
from codestrata.ai.recommendations import (
    AIRecommendation,
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
    AIRecommendationResult,
    EvidenceCoverage,
    ModernizationPhase,
)
from codestrata.ai.tools import CodeStrataToolRegistry, build_analysis_tool_registry
from codestrata.ai.tools.base import CodeStrataTool, CodeStrataToolExecutionError
from codestrata.ai.tools.models import EmptyToolInput, TechnologiesOutput


def _truncation(
    count: int = 0, *, truncated: bool = False, original: int | None = None
) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=truncated,
        original_count=original if original is not None else count,
        included_count=count,
    )


def _context() -> LLMAnalysisContext:
    findings = [
        LLMFindingEvidence(
            rule_id="SEC001",
            title="Critical finding",
            category="security",
            severity="critical",
            summary="Secret exposure risk",
            evidence=[LLMEvidenceLocation(path="src/App.java", line=10)],
            evidence_truncation=_truncation(1),
        ),
        LLMFindingEvidence(
            rule_id="SEC002",
            title="Medium finding",
            category="security",
            severity="medium",
            summary="Dependency issue",
            evidence_truncation=_truncation(),
        ),
    ]
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="sample-app",
            source_type="github",
            file_count=12,
        ),
        technologies=[
            LLMTechnologyEvidence(name="Java", category="language", version="17"),
            LLMTechnologyEvidence(name="Maven", category="build_tool"),
        ],
        metrics=LLMMetricsContext(
            file_count=12,
            finding_count=2,
            technology_count=2,
        ),
        findings=findings,
        findings_truncation=_truncation(2),
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
        suggested_actions=["Act"],
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
                objective="Reduce risk",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Safer baseline"],
            ),
            ModernizationPhase(
                phase=2,
                name="Hardening",
                objective="Continue modernization",
                recommendations=["AI-REC-002"],
                expected_outcomes=["Better quality"],
            ),
        ],
        evidence_coverage=EvidenceCoverage(
            total_findings=2,
            findings_considered=2,
            findings_referenced=2,
            coverage_percentage=100.0,
        ),
        limitations=["No runtime profiling data."],
    )


def _options(**overrides: object) -> AgentExecutionOptions:
    payload: dict[str, object] = {
        "model_options": ModelInvocationOptions(model_id="test-model"),
        "prompt_options": PromptBuildOptions(),
        "max_tool_calls": 20,
    }
    payload.update(overrides)
    return AgentExecutionOptions.model_validate(payload)


class FakeProvider(AIModelProvider):
    def __init__(
        self,
        result: AIRecommendationResult | None = None,
        *,
        error: Exception | None = None,
        raw_response_text: str = '{"ok":true}',
    ) -> None:
        self.result = result or _valid_result()
        self.error = error
        self.raw_response_text = raw_response_text
        self.calls: list[ModernizationModelRequest] = []

    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return ModelInvocationResult(
            recommendation_result=self.result,
            metadata=ModelInvocationMetadata(
                provider="fake",
                model_id=options.model_id,
                request_id="req-1",
                latency_ms=12.5,
                usage=ModelUsage(input_tokens=10, output_tokens=20, total_tokens=30),
                stop_reason="end_turn",
            ),
            raw_response_text=self.raw_response_text,
            parsed_model_response=self.result.model_dump(mode="json"),
        )


class _FailingTechTool(CodeStrataTool[EmptyToolInput, TechnologiesOutput]):
    name = "list_technologies"
    description = "Fails on purpose"
    input_model = EmptyToolInput
    output_model = TechnologiesOutput

    def run(self, payload: EmptyToolInput) -> TechnologiesOutput:
        del payload
        raise CodeStrataToolExecutionError("tool boom with AKIAIOSFODNN7EXAMPLE")


def test_successful_end_to_end_orchestration() -> None:
    provider = FakeProvider()
    agent = ModernizationAssessmentAgent(provider)
    result = agent.run(_context(), _options())

    assert isinstance(result, ModernizationAssessmentResult)
    assert result.recommendation_result == _valid_result()
    assert result.model_metadata.provider == "fake"
    assert result.trace.status == AgentExecutionStatus.COMPLETED
    assert result.raw_model_response == provider.raw_response_text
    assert len(provider.calls) == 1


def test_deterministic_tool_sequence_and_single_model_call() -> None:
    provider = FakeProvider()
    agent = ModernizationAssessmentAgent(provider)
    result = agent.run(_context(), _options())

    tool_steps = [step for step in result.trace.steps if step.step_type == AgentStepType.TOOL_CALL]
    assert [step.name for step in tool_steps] == list(REQUIRED_TOOL_SEQUENCE)
    assert result.trace.tool_call_count == len(REQUIRED_TOOL_SEQUENCE)
    assert result.trace.model_call_count == 1
    assert len(provider.calls) == 1


def test_provider_neutral_dependency_injection() -> None:
    provider = FakeProvider()
    builder = ModernizationPromptBuilder()
    registry = build_analysis_tool_registry(_context())
    agent = ModernizationAssessmentAgent(
        provider,
        prompt_builder=builder,
        tool_registry=registry,
    )
    result = agent.run(_context(), _options())
    assert result.trace.status == AgentExecutionStatus.COMPLETED


def test_complete_successful_trace_shape() -> None:
    result = ModernizationAssessmentAgent(FakeProvider()).run(_context(), _options())
    trace = result.trace
    assert [step.sequence_number for step in trace.steps] == list(range(1, len(trace.steps) + 1))
    assert len(trace.steps) == len(REQUIRED_TOOL_SEQUENCE) + 3
    assert [step.step_type for step in trace.steps[-3:]] == [
        AgentStepType.PROMPT_BUILD,
        AgentStepType.MODEL_INVOCATION,
        AgentStepType.VALIDATION,
    ]
    for step in trace.steps:
        assert step.started_at_utc.tzinfo is not None
        assert step.completed_at_utc.tzinfo is not None
        assert step.started_at_utc.utcoffset() == UTC.utcoffset(None)
        assert step.latency_ms >= 0.0
    assert trace.started_at_utc.tzinfo is not None
    assert trace.total_latency_ms >= 0.0
    assert trace.input_tokens == 10
    assert trace.output_tokens == 20
    assert trace.total_tokens == 30

    model_step = trace.steps[-2]
    assert model_step.output_summary["recommendation_count"] == 2
    assert model_step.output_summary["phase_count"] == 2
    assert model_step.output_summary["limitation_count"] == 1


def test_raw_model_response_always_retained_for_execution_artifact() -> None:
    provider = FakeProvider(raw_response_text='{"raw":true}')
    result = ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert result.raw_model_response == '{"raw":true}'


def test_unknown_enabled_tool() -> None:
    with pytest.raises(AgentConfigurationError, match="Unknown enabled tool") as info:
        ModernizationAssessmentAgent(FakeProvider()).run(
            _context(),
            _options(enabled_tool_names=(*REQUIRED_TOOL_SEQUENCE, "not_a_tool")),
        )
    assert info.value.trace is not None
    assert info.value.trace.status == AgentExecutionStatus.FAILED


def test_disabled_required_tool() -> None:
    enabled = tuple(name for name in REQUIRED_TOOL_SEQUENCE if name != "list_technologies")
    with pytest.raises(AgentConfigurationError, match="disabled") as info:
        ModernizationAssessmentAgent(FakeProvider()).run(
            _context(),
            _options(enabled_tool_names=enabled),
        )
    assert info.value.trace is not None
    assert info.value.trace.status == AgentExecutionStatus.FAILED


def test_max_tool_call_enforcement() -> None:
    with pytest.raises(AgentConfigurationError, match="max_tool_calls") as info:
        ModernizationAssessmentAgent(FakeProvider()).run(
            _context(),
            _options(max_tool_calls=3),
        )
    assert info.value.trace is not None
    assert info.value.trace.status == AgentExecutionStatus.FAILED


def test_tool_execution_failure() -> None:
    context = _context()
    registry = build_analysis_tool_registry(context)
    # Replace list_technologies with a failing tool.
    failing_registry = CodeStrataToolRegistry()
    for name in registry.list_names():
        if name == "list_technologies":
            failing_registry.register(_FailingTechTool())
        else:
            failing_registry.register(registry.get(name))

    with pytest.raises(AgentToolError) as info:
        ModernizationAssessmentAgent(
            FakeProvider(),
            tool_registry=failing_registry,
        ).run(context, _options())
    assert info.value.trace is not None
    assert info.value.trace.status == AgentExecutionStatus.FAILED
    assert "AKIAIOSFODNN7EXAMPLE" not in str(info.value)
    failed_steps = [step for step in info.value.trace.steps if not step.success]
    assert failed_steps
    assert failed_steps[-1].name == "list_technologies"


def test_prompt_construction_failure() -> None:
    builder = MagicMock(spec=ModernizationPromptBuilder)
    builder.build.side_effect = PromptBuildError("context too large")
    with pytest.raises(AgentExecutionError, match="Prompt construction failed") as info:
        ModernizationAssessmentAgent(
            FakeProvider(),
            prompt_builder=builder,
        ).run(_context(), _options())
    assert info.value.trace is not None
    assert info.value.trace.status == AgentExecutionStatus.FAILED
    assert info.value.trace.steps[-1].step_type == AgentStepType.PROMPT_BUILD


def test_provider_invocation_failure() -> None:
    provider = FakeProvider(error=AIProviderInvocationError("service down"))
    with pytest.raises(AgentExecutionError, match="invocation failed") as info:
        ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert info.value.trace is not None
    assert info.value.__cause__ is provider.error
    assert info.value.trace.steps[-1].step_type == AgentStepType.MODEL_INVOCATION


def test_provider_timeout_propagation() -> None:
    timeout = AIProviderTimeoutError("timed out")
    provider = FakeProvider(error=timeout)
    with pytest.raises(AgentExecutionError, match="timed out") as info:
        ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert info.value.__cause__ is timeout


def test_invalid_recommendation_result_from_provider() -> None:
    provider = FakeProvider(error=AIResponseValidationError("bad schema"))
    with pytest.raises(AgentValidationError, match="validation failed") as info:
        ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert info.value.trace is not None
    assert info.value.trace.status == AgentExecutionStatus.FAILED


def test_final_validation_failure() -> None:
    invalid = AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        recommendations=[_recommendation("AI-REC-001", related=["MISSING"])],
        evidence_coverage=EvidenceCoverage(
            total_findings=1,
            findings_considered=1,
            findings_referenced=1,
            coverage_percentage=100.0,
        ),
    )
    provider = FakeProvider(result=invalid)
    with pytest.raises(AgentValidationError, match="Final recommendation") as info:
        ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert info.value.trace is not None
    assert info.value.trace.steps[-1].step_type == AgentStepType.VALIDATION
    assert info.value.trace.status == AgentExecutionStatus.FAILED


def test_failed_trace_attached_and_no_success_with_failed_status() -> None:
    provider = FakeProvider(error=AIProviderInvocationError("boom"))
    with pytest.raises(AgentExecutionError) as info:
        ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert info.value.trace is not None
    assert info.value.trace.status == AgentExecutionStatus.FAILED


def test_no_prompts_or_source_evidence_in_trace() -> None:
    result = ModernizationAssessmentAgent(FakeProvider()).run(_context(), _options())
    encoded = agent_execution_trace_to_json(result.trace)
    forbidden = (
        "Secret exposure risk",
        "System rules",
        "Developer instructions",
        "src/App.java",
        "Respond with valid JSON only",
        '{"ok":true}',
    )
    for token in forbidden:
        assert token not in encoded
    assert "finding_count" in encoded
    assert "context_json_size" in encoded


def test_secret_sanitization_in_errors() -> None:
    provider = FakeProvider(error=AIProviderInvocationError("failed AKIAIOSFODNN7EXAMPLE"))
    with pytest.raises(AgentExecutionError) as info:
        ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert "AKIAIOSFODNN7EXAMPLE" not in str(info.value)
    assert info.value.trace is not None
    assert "AKIAIOSFODNN7EXAMPLE" not in agent_execution_trace_to_json(info.value.trace)


def test_frozen_contracts_and_extra_field_rejection() -> None:
    result = ModernizationAssessmentAgent(FakeProvider()).run(_context(), _options())
    with pytest.raises(ValidationError):
        result.trace.status = AgentExecutionStatus.FAILED
    with pytest.raises(ValidationError):
        AgentExecutionOptions(
            model_options=ModelInvocationOptions(model_id="m"),
            unexpected=True,  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        AgentExecutionStep(
            sequence_number=1,
            step_type=AgentStepType.TOOL_CALL,
            name="x",
            started_at_utc=result.trace.started_at_utc,
            completed_at_utc=result.trace.completed_at_utc,
            latency_ms=1.0,
            success=True,
            extra=True,  # type: ignore[call-arg]
        )


def test_deterministic_json_serialization_and_round_trip() -> None:
    result = ModernizationAssessmentAgent(FakeProvider()).run(
        _context(),
        _options(),
    )
    # Trace ID/timestamps differ across runs; serialize the same object twice.
    first = modernization_assessment_result_to_json(result)
    second = modernization_assessment_result_to_json(result)
    assert first == second
    restored = modernization_assessment_result_from_json(first)
    assert restored.recommendation_result == result.recommendation_result
    assert restored.model_metadata == result.model_metadata
    assert restored.raw_model_response == result.raw_model_response
    assert restored.trace.tool_call_count == result.trace.tool_call_count

    trace_json = agent_execution_trace_to_json(result.trace)
    assert agent_execution_trace_from_json(trace_json).status == result.trace.status


def test_no_bedrock_imports_in_agent_modules() -> None:
    package_root = Path("src/codestrata/ai/agents")
    for path in sorted(package_root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        assert "bedrock" not in lowered
        assert "boto3" not in lowered
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "bedrock" not in alias.name.lower()
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "bedrock" not in node.module.lower()
                assert node.module != "codestrata.ai.providers"


def test_no_autonomous_tool_selection_or_second_model_call() -> None:
    provider = FakeProvider()
    result = ModernizationAssessmentAgent(provider).run(_context(), _options())
    assert len(provider.calls) == 1
    assert result.trace.model_call_count == 1
    assert "tool_choice" not in json.dumps(result.trace.model_dump(mode="json"))


def test_prompt_builder_and_tool_registry_integration() -> None:
    context = _context()
    provider = FakeProvider()
    agent = ModernizationAssessmentAgent(
        provider,
        prompt_builder=ModernizationPromptBuilder(),
        tool_registry=build_analysis_tool_registry(context),
    )
    result = agent.run(context, _options())
    request = provider.calls[0]
    assert request.analysis_context == context
    assert request.prompt_request.metadata.repository_identifier == "sample-app"
    assert result.trace.steps[0].output_summary["repository_identifier"] == "sample-app"
