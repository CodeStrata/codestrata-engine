"""Tests for the provider-neutral modernization prompt builder."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.ai.contracts.models import (
    LLM_CONTRACT_SCHEMA_VERSION,
    LLMAnalysisContext,
    LLMEvidenceLocation,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
    LLMTechnologyEvidence,
)
from codestrata.ai.contracts.serialization import llm_context_to_json
from codestrata.ai.prompts import (
    DEFAULT_PROMPT_TEMPLATE_VERSION,
    PROMPT_PURPOSE,
    PROMPT_SCHEMA_VERSION,
    ModernizationPromptBuilder,
    PromptBuildError,
    PromptBuildOptions,
    PromptMessage,
    PromptMetadata,
    PromptRequest,
    prompt_request_from_json,
    prompt_request_to_json,
)
from codestrata.ai.recommendations.models import AI_RECOMMENDATION_SCHEMA_VERSION


def _truncation(
    *,
    count: int = 0,
    truncated: bool = False,
    original: int | None = None,
) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=truncated,
        original_count=original if original is not None else count,
        included_count=count,
    )


def _finding(rule_id: str, *, severity: str = "high") -> LLMFindingEvidence:
    return LLMFindingEvidence(
        rule_id=rule_id,
        title=f"Finding {rule_id}",
        category="security",
        severity=severity,
        summary=f"Summary for {rule_id}",
        evidence=[LLMEvidenceLocation(path="src/App.java", line=10)],
        evidence_truncation=_truncation(count=1),
    )


def _complete_context(*, truncated: bool = True) -> LLMAnalysisContext:
    findings = [_finding("SEC001"), _finding("SEC002", severity="medium")]
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="sample-app",
            source_type="github",
            default_branch="main",
            commit_sha="abc1234",
            file_count=12,
        ),
        technologies=[
            LLMTechnologyEvidence(
                name="Java",
                category="language",
                version="17",
                evidence=["pom.xml"],
            ),
            LLMTechnologyEvidence(
                name="Maven",
                category="build_tool",
                evidence=["pom.xml"],
            ),
        ],
        metrics=LLMMetricsContext(
            file_count=12,
            source_file_count=8,
            test_file_count=2,
            finding_count=4,
            technology_count=2,
        ),
        findings=findings,
        findings_truncation=_truncation(
            count=len(findings),
            truncated=truncated,
            original=4 if truncated else len(findings),
        ),
    )


def _minimal_context() -> LLMAnalysisContext:
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="minimal",
            source_type="local",
            file_count=0,
        ),
        metrics=LLMMetricsContext(finding_count=0, technology_count=0),
        findings=[],
        findings_truncation=_truncation(count=0),
    )


def test_complete_prompt_construction() -> None:
    request = ModernizationPromptBuilder().build(_complete_context())
    assert request.schema_version == PROMPT_SCHEMA_VERSION
    assert request.purpose == PROMPT_PURPOSE
    assert len(request.messages) == 3
    assert [message.role for message in request.messages] == [
        "system",
        "developer",
        "user",
    ]
    assert request.context_json
    assert request.expected_output_schema_json
    assert "AIRecommendationResult" in request.expected_output_schema_json or (
        '"title"' in request.expected_output_schema_json
    )
    assert request.metadata.repository_identifier == "sample-app"


def test_minimal_valid_context() -> None:
    request = ModernizationPromptBuilder().build(_minimal_context())
    assert request.metadata.finding_count == 0
    assert request.metadata.technology_count == 0
    assert request.metadata.context_truncated is False
    assert request.metadata.repository_identifier == "minimal"


def test_deterministic_prompt_output() -> None:
    builder = ModernizationPromptBuilder()
    first = builder.build(_complete_context())
    second = builder.build(_complete_context())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_deterministic_json_serialization() -> None:
    request = ModernizationPromptBuilder().build(_complete_context())
    first = prompt_request_to_json(request)
    second = prompt_request_to_json(request)
    assert first == second
    assert '"purpose": "modernization_assessment"' in first


def test_json_round_trip() -> None:
    request = ModernizationPromptBuilder().build(_complete_context())
    restored = prompt_request_from_json(prompt_request_to_json(request))
    assert restored == request


def test_immutable_contracts() -> None:
    request = ModernizationPromptBuilder().build(_minimal_context())
    with pytest.raises(ValidationError):
        request.purpose = "other"
    with pytest.raises(ValidationError):
        request.messages[0].content = "changed"
    with pytest.raises(ValidationError):
        request.metadata.finding_count = 99


def test_extra_field_rejection() -> None:
    with pytest.raises(ValidationError):
        PromptMessage(role="system", content="ok", extra="no")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        PromptBuildOptions(include_context_json=True, unknown=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        PromptMetadata(
            repository_identifier="x",
            context_schema_version="1.0.0",
            recommendation_schema_version="1.0.0",
            finding_count=0,
            technology_count=0,
            context_truncated=False,
            prompt_template_version="1.0.0",
            extra=True,  # type: ignore[call-arg]
        )


def test_stable_message_ordering() -> None:
    request = ModernizationPromptBuilder().build(_complete_context())
    assert [message.role for message in request.messages] == [
        "system",
        "developer",
        "user",
    ]


def test_correct_metadata() -> None:
    context = _complete_context(truncated=True)
    request = ModernizationPromptBuilder().build(context)
    assert request.metadata == PromptMetadata(
        repository_identifier="sample-app",
        context_schema_version=LLM_CONTRACT_SCHEMA_VERSION,
        recommendation_schema_version=AI_RECOMMENDATION_SCHEMA_VERSION,
        finding_count=2,
        technology_count=2,
        context_truncated=True,
        prompt_template_version=DEFAULT_PROMPT_TEMPLATE_VERSION,
    )


def test_context_and_schema_inclusion_options() -> None:
    context = _complete_context()
    included = ModernizationPromptBuilder().build(
        context,
        PromptBuildOptions(include_context_json=True, include_output_schema=True),
    )
    excluded = ModernizationPromptBuilder().build(
        context,
        PromptBuildOptions(include_context_json=False, include_output_schema=False),
    )

    assert context.model_dump(mode="json") == json.loads(included.context_json)
    assert "LLMAnalysisContext JSON:\n" in included.messages[2].content
    assert "Expected AIRecommendationResult JSON Schema:\n" in included.messages[2].content
    assert excluded.context_json == included.context_json
    assert excluded.expected_output_schema_json == included.expected_output_schema_json
    assert "supplied separately on the prompt package as context_json" in (
        excluded.messages[2].content
    )
    assert "supplied separately on the prompt package as expected_output_schema_json" in (
        excluded.messages[2].content
    )
    assert "LLMAnalysisContext JSON:\n{" not in excluded.messages[2].content


def test_maximum_context_character_enforcement() -> None:
    context = _complete_context()
    context_json = llm_context_to_json(context, indent=2)
    with pytest.raises(PromptBuildError, match="max_context_characters"):
        ModernizationPromptBuilder().build(
            context,
            PromptBuildOptions(max_context_characters=max(1, len(context_json) - 1)),
        )


def test_known_finding_reference_instructions() -> None:
    content = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    assert "related_finding_ids" in content
    assert "rule_id" in content
    assert "Never invent finding IDs" in content


def test_deterministic_recommendation_traceability_instructions() -> None:
    content = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    assert "Do not construct deterministic recommendation IDs from PMD rule IDs" in content
    assert "related_deterministic_recommendation_ids may be empty" in content
    assert "even when related_finding_ids is empty" in content
    assert '"recommendation_id": "AI-REC-005"' in content
    assert '"related_deterministic_recommendation_ids": ["REC.CLOUD.003"]' in content
    assert '"related_deterministic_recommendation_ids": []' in content
    assert "pmd-group-" in content


def test_recommendation_id_instructions() -> None:
    content = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    assert "AI-REC-001" in content
    assert "AI-REC-002" in content
    assert "Do not reproduce each deterministic recommendation" in content
    assert "PMD rule IDs" in content


def test_dependency_and_phase_instructions() -> None:
    content = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    assert "dependencies may reference only AI recommendation IDs" in content
    assert "modernization_phases must contain 2 to 4 non-empty phases" in content
    assert "exactly one phase" in content


def test_evidence_coverage_instructions() -> None:
    content = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    assert "evidence_coverage" in content
    assert "CodeStrata recalculates authoritative coverage" in content
    assert "input_truncated" in content


def test_consolidation_and_production_test_instructions() -> None:
    system = ModernizationPromptBuilder().build(_minimal_context()).messages[0].content
    developer = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    user = ModernizationPromptBuilder().build(_minimal_context()).messages[2].content
    assert "evidence inputs" in system
    assert "Do not reproduce each deterministic recommendation" in developer
    assert "Prefer fewer, stronger recommendations" in developer
    assert "production code, test code" in developer
    assert "Do not assign high modernization impact to a test-only" in developer
    assert "Do not copy deterministic recommendations one-for-one" in user
    assert "Address PMD pattern" in developer


def test_limitation_and_uncertainty_instructions() -> None:
    developer = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    system = ModernizationPromptBuilder().build(_minimal_context()).messages[0].content
    user = ModernizationPromptBuilder().build(_minimal_context()).messages[2].content
    assert "uncertainty and missing or truncated evidence" in developer
    assert "limitations" in developer
    assert "incomplete or truncated" in system
    assert "limitations" in user


def test_json_only_output_instructions() -> None:
    system = ModernizationPromptBuilder().build(_minimal_context()).messages[0].content
    developer = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    user = ModernizationPromptBuilder().build(_minimal_context()).messages[2].content
    assert "Respond with valid JSON only" in system
    assert "valid JSON matching the embedded AIRecommendationResult" in developer
    assert "Return only the AIRecommendationResult JSON object" in user
    assert "chain-of-thought" in system.lower() or "chain-of-thought" in developer


def test_no_provider_specific_language_or_imports() -> None:
    package_root = Path("src/codestrata/ai/prompts")
    forbidden_tokens = (
        "bedrock",
        "anthropic",
        "openai",
        "claude",
        "gpt-4",
        "mcp",
        "boto3",
    )
    for path in sorted(package_root.rglob("*.py")):
        source = path.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            assert token not in source, f"{token} found in {path}"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    lowered = alias.name.lower()
                    assert "bedrock" not in lowered
                    assert "anthropic" not in lowered
                    assert "openai" not in lowered
            if isinstance(node, ast.ImportFrom) and node.module:
                lowered = node.module.lower()
                assert "bedrock" not in lowered
                assert "anthropic" not in lowered
                assert "openai" not in lowered


def test_preserved_context_truncation_metadata() -> None:
    context = _complete_context(truncated=True)
    request = ModernizationPromptBuilder().build(context)
    restored_context = json.loads(request.context_json)
    assert restored_context["findings_truncation"] == {
        "truncated": True,
        "original_count": 4,
        "included_count": 2,
    }
    assert request.metadata.context_truncated is True


def test_empty_or_invalid_option_handling() -> None:
    with pytest.raises(ValidationError):
        PromptBuildOptions(template_version="   ")
    with pytest.raises(ValidationError):
        PromptBuildOptions(max_context_characters=0)
    with pytest.raises(ValidationError):
        PromptBuildOptions(max_context_characters=-5)
    with pytest.raises(ValueError, match="Unsupported prompt template_version"):
        ModernizationPromptBuilder().build(
            _minimal_context(),
            PromptBuildOptions(template_version="9.9.9"),
        )


def test_context_json_matches_contract_serialization() -> None:
    context = _complete_context()
    request = ModernizationPromptBuilder().build(context)
    assert request.context_json == llm_context_to_json(context, indent=2)


def test_expected_schema_is_sorted_json() -> None:
    request = ModernizationPromptBuilder().build(_minimal_context())
    parsed = json.loads(request.expected_output_schema_json)
    assert request.expected_output_schema_json == json.dumps(
        parsed,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ": "),
    )


def test_prompt_request_rejects_invalid_purpose_and_version() -> None:
    request = ModernizationPromptBuilder().build(_minimal_context())
    payload = request.model_dump(mode="json")
    payload["purpose"] = "other"
    with pytest.raises(ValidationError):
        PromptRequest.model_validate(payload)
    payload = request.model_dump(mode="json")
    payload["schema_version"] = "0.0.1"
    with pytest.raises(ValidationError):
        PromptRequest.model_validate(payload)


def test_evidence_grounding_and_no_invention_instructions() -> None:
    system = ModernizationPromptBuilder().build(_minimal_context()).messages[0].content
    developer = ModernizationPromptBuilder().build(_minimal_context()).messages[1].content
    assert "Do not invent repository facts" in system
    assert "Prohibit invented repository facts" in developer
    assert "deterministic evidence" in system.lower()
    assert "AI interpretation" in system
