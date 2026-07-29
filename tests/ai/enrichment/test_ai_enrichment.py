"""Tests for AI enrichment domain, context, prompt, and service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.ai.enrichment import (
    AiEnrichmentContextLimits,
    AiEnrichmentPromptBuilder,
    AiEnrichmentService,
    AiEnrichmentValidationError,
    build_ai_enrichment_context,
    validate_ai_enrichment_result,
    write_ai_enrichment_artifact,
)
from codestrata.ai.enrichment.context import AiEnrichmentBudgetError
from codestrata.ai.enrichment.parsing import parse_enrichment_response
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.models import (
    ModelInvocationMetadata,
    ModelInvocationOptions,
    ModelInvocationResult,
    ModelUsage,
    ModernizationModelRequest,
)
from codestrata.domain.ai_enrichment import (
    AiEnrichmentResult,
    AiProviderMetadata,
    EnrichmentPriorityLevel,
    ExecutiveSummary,
    ModernizationPriority,
    ModernizationRisk,
    ModernizationTheme,
    SuggestedNextStep,
)
from codestrata.models import Repository
from codestrata.services.graph_assessment import GraphAssessmentPipeline
from codestrata.services.recommendations import RecommendationEngine
from codestrata.services.rule_engine import RuleEngine


def _js_repo(root: Path) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(
        json.dumps({"name": "js-app", "dependencies": {"express": "4.0.0"}}),
        encoding="utf-8",
    )
    src = root / "src"
    src.mkdir()
    (src / "index.js").write_text("console.log('ok');\n", encoding="utf-8")
    return Repository(
        name="js-app",
        path=root.resolve(),
        files=["package.json", "src/index.js"],
        total_files=2,
    )


def _java_repo(root: Path) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pom.xml").write_text(
        """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter</artifactId>
      <version>2.7.18</version>
    </dependency>
  </dependencies>
</project>
""",
        encoding="utf-8",
    )
    src = root / "src" / "main" / "java" / "demo"
    src.mkdir(parents=True)
    (src / "App.java").write_text("package demo; class App {}", encoding="utf-8")
    return Repository(
        name="java-app",
        path=root.resolve(),
        files=["pom.xml", "src/main/java/demo/App.java"],
        total_files=2,
    )


def _pipeline_bundle(repository: Repository):
    from codestrata.config import CodestrataSettings
    from codestrata.services.default_pipeline import create_default_analysis_service

    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repository.path)},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
        }
    )
    pipeline = GraphAssessmentPipeline().run(repository)
    rules = RuleEngine().evaluate_pipeline_result(pipeline)
    recs = RecommendationEngine().evaluate_pipeline_result(
        pipeline_result=pipeline,
        evaluation=rules,
    )
    analysis = create_default_analysis_service(
        settings,
        static_analysis_enabled=False,
    ).analyze(repository)
    return pipeline, rules, recs, analysis


def test_domain_validation_round_trip() -> None:
    result = AiEnrichmentResult(
        executive_summary=ExecutiveSummary(
            headline="Modernize dependencies",
            narrative="Focus on lockfiles and CI first.",
        ),
        themes=(
            ModernizationTheme(
                title="Dependency hygiene",
                summary="Lockfiles and engine declarations are missing.",
            ),
        ),
        priorities=(
            ModernizationPriority(
                title="Add lockfile",
                rationale="Reproducible installs",
                priority=EnrichmentPriorityLevel.HIGH,
            ),
        ),
        risks=(
            ModernizationRisk(
                title="Drift",
                summary="Installs may diverge without a lockfile.",
            ),
        ),
        suggested_next_steps=(
            SuggestedNextStep(order=1, title="Commit lockfile", summary="Run npm install."),
        ),
        provider_metadata=AiProviderMetadata(provider="fake", model_id="m"),
    )
    restored = AiEnrichmentResult.model_validate(result.model_dump(mode="json"))
    assert restored == result


def test_context_stable_ordering_and_no_absolute_paths(tmp_path: Path) -> None:
    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    first = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    second = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    assert first.to_stable_json() == second.to_stable_json()
    text = first.to_stable_json().lower()
    assert str(tmp_path).lower() not in text
    assert "/users/" not in text
    assert "akia" not in text


def test_context_budget_enforcement(tmp_path: Path) -> None:
    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    with pytest.raises(AiEnrichmentBudgetError):
        build_ai_enrichment_context(
            analysis_result=analysis,
            rule_evaluation=rules,
            recommendation_result=recs,
            repository_graph=pipeline.repository_graph,
            limits=AiEnrichmentContextLimits(max_context_characters=50),
        )


def test_prompt_mentions_traceability(tmp_path: Path) -> None:
    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    prompt = AiEnrichmentPromptBuilder().build(context)
    joined = "\n".join(message.content for message in prompt.messages)
    assert "allowed_finding_ids" in joined
    assert "strict JSON" in joined.lower() or "JSON" in joined
    assert "Do not invent" in joined or "do not invent" in joined.lower()


def test_unknown_ids_rejected(tmp_path: Path) -> None:
    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    bad = AiEnrichmentResult(
        executive_summary=ExecutiveSummary(headline="x", narrative="y"),
        themes=(
            ModernizationTheme(
                title="t",
                summary="s",
                related_finding_ids=("finding:does-not-exist",),
            ),
        ),
        provider_metadata=AiProviderMetadata(provider="fake", model_id="m"),
    )
    with pytest.raises(AiEnrichmentValidationError):
        validate_ai_enrichment_result(bad, context)


def test_enrichment_json_parse_and_artifact(tmp_path: Path) -> None:
    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    finding_id = context.allowed_finding_ids[0]
    rec_id = context.allowed_recommendation_ids[0]
    payload = {
        "executive_summary": {
            "headline": "Stabilize the JS app",
            "narrative": "Address lockfile and tests first.",
        },
        "themes": [
            {
                "title": "Delivery basics",
                "summary": "Missing tests and lockfile.",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "priorities": [
            {
                "title": "Add lockfile",
                "rationale": "Reproducible installs",
                "priority": "high",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "risks": [
            {
                "title": "Install drift",
                "summary": "Without a lockfile installs can drift.",
                "severity": "medium",
                "related_finding_ids": [finding_id],
            }
        ],
        "suggested_next_steps": [
            {
                "order": 1,
                "title": "Commit package-lock.json",
                "summary": "Generate and commit a lockfile.",
                "related_recommendation_ids": [rec_id],
            }
        ],
        "provider_metadata": {"provider": "fake", "model_id": "m1"},
        "limitations": ["Fixture enrichment"],
    }
    metadata = ModelInvocationMetadata(
        provider="fake",
        model_id="m1",
        latency_ms=1.0,
        usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    result = parse_enrichment_response(json.dumps(payload), context, metadata)
    written = write_ai_enrichment_artifact(result, tmp_path / "run")
    assert written.path.is_file()
    assert written.path.read_text(encoding="utf-8").endswith("\n")


class _EnrichmentFakeProvider(AIModelProvider):
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[ModernizationModelRequest] = []

    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        self.calls.append(request)
        return ModelInvocationResult(
            recommendation_result=None,
            metadata=ModelInvocationMetadata(
                provider="fake",
                model_id=options.model_id,
                latency_ms=1.0,
                usage=ModelUsage(input_tokens=2, output_tokens=3, total_tokens=5),
            ),
            raw_response_text=json.dumps(self.payload),
            parsed_model_response=self.payload,
        )


def test_prompt_includes_advisor_persona() -> None:
    from codestrata.ai.enrichment.advisor import MODERNIZATION_ADVISOR_PERSONA

    assert "CTO" in MODERNIZATION_ADVISOR_PERSONA
    assert "VP Engineering" in MODERNIZATION_ADVISOR_PERSONA
    assert "senior engineering modernization advisor" in MODERNIZATION_ADVISOR_PERSONA


def test_parse_stamps_advisor_metadata(tmp_path: Path) -> None:
    from codestrata.ai.enrichment.advisor import (
        MODERNIZATION_ADVISOR_PROMPT_VERSION,
        MODERNIZATION_ADVISOR_VERSION,
    )

    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    finding_id = context.allowed_finding_ids[0]
    rec_id = context.allowed_recommendation_ids[0]
    payload = {
        "executive_summary": {"headline": "Meta", "narrative": "Stamped."},
        "themes": [
            {
                "title": "T",
                "summary": "S",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "priorities": [
            {
                "title": "P",
                "rationale": "R",
                "priority": "high",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "risks": [],
        "suggested_next_steps": [
            {
                "order": 1,
                "title": "Next",
                "summary": "Do it",
                "related_recommendation_ids": [rec_id],
            }
        ],
        "provider_metadata": {"provider": "fake", "model_id": "m"},
        "limitations": [],
    }
    metadata = ModelInvocationMetadata(
        provider="fake",
        model_id="m",
        latency_ms=1.0,
        usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    result = parse_enrichment_response(json.dumps(payload), context, metadata)
    assert result.provider_metadata.advisor_version == MODERNIZATION_ADVISOR_VERSION
    assert result.provider_metadata.prompt_version == MODERNIZATION_ADVISOR_PROMPT_VERSION
    assert result.provider_metadata.generated_at_utc is not None
    assert result.provider_metadata.generated_at_utc.endswith("Z")


def test_service_prompt_contains_persona(tmp_path: Path) -> None:
    from codestrata.ai.enrichment.advisor import MODERNIZATION_ADVISOR_PERSONA

    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    finding_id = context.allowed_finding_ids[0]
    rec_id = context.allowed_recommendation_ids[0]
    payload = {
        "executive_summary": {"headline": "JS narrative", "narrative": "Act on basics."},
        "themes": [
            {
                "title": "Basics",
                "summary": "Lockfile/tests",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "priorities": [
            {
                "title": "Lockfile",
                "rationale": "Reproducibility",
                "priority": "high",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "risks": [],
        "suggested_next_steps": [
            {
                "order": 1,
                "title": "Add lockfile",
                "summary": "Commit lockfile",
                "related_recommendation_ids": [rec_id],
            }
        ],
        "provider_metadata": {"provider": "fake", "model_id": "m"},
        "limitations": [],
    }
    provider = _EnrichmentFakeProvider(payload)
    run = AiEnrichmentService(provider).run(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
        model_options=ModelInvocationOptions(model_id="m"),
    )
    system = next(msg.content for msg in run.prompt_request.messages if msg.role == "system")
    assert system.startswith(MODERNIZATION_ADVISOR_PERSONA)
    assert run.enrichment.provider_metadata.advisor_version == "1.0.0"
    assert run.enrichment.provider_metadata.prompt_version == "1.1.0"


def test_service_one_call_javascript(tmp_path: Path) -> None:
    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    finding_id = context.allowed_finding_ids[0]
    rec_id = context.allowed_recommendation_ids[0]
    payload = {
        "executive_summary": {"headline": "JS narrative", "narrative": "Act on basics."},
        "themes": [
            {
                "title": "Basics",
                "summary": "Lockfile/tests",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "priorities": [
            {
                "title": "Lockfile",
                "rationale": "Reproducibility",
                "priority": "high",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "risks": [],
        "suggested_next_steps": [
            {
                "order": 1,
                "title": "Add lockfile",
                "summary": "Commit lockfile",
                "related_recommendation_ids": [rec_id],
            }
        ],
        "provider_metadata": {"provider": "fake", "model_id": "m"},
        "limitations": [],
    }
    provider = _EnrichmentFakeProvider(payload)
    run = AiEnrichmentService(provider).run(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
        model_options=ModelInvocationOptions(model_id="m"),
    )
    assert len(provider.calls) == 1
    assert run.enrichment.executive_summary.headline == "JS narrative"
    before_findings = rules.model_dump(mode="json")
    before_recs = recs.model_dump(mode="json")
    assert rules.model_dump(mode="json") == before_findings
    assert recs.model_dump(mode="json") == before_recs


def test_service_java_sample(tmp_path: Path) -> None:
    repository = _java_repo(tmp_path / "java")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    finding_id = next(
        item.id
        for item in context.findings
        if "spring-boot" in item.rule_id or "unsupported" in item.rule_id
    )
    rec_id = context.allowed_recommendation_ids[0]
    payload = {
        "executive_summary": {
            "headline": "Upgrade Spring Boot",
            "narrative": "Boot 2.x should move to 3.x.",
        },
        "themes": [
            {
                "title": "Framework upgrade",
                "summary": "Unsupported Boot line",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "priorities": [
            {
                "title": "Plan Boot 3 upgrade",
                "rationale": finding_id,
                "priority": "high",
                "related_finding_ids": [finding_id],
                "related_recommendation_ids": [rec_id],
            }
        ],
        "risks": [
            {
                "title": "Jakarta migration",
                "summary": "javax to jakarta package moves",
                "severity": "high",
                "related_finding_ids": [finding_id],
            }
        ],
        "suggested_next_steps": [
            {
                "order": 1,
                "title": "Assess compatibility",
                "summary": "Inventory starters",
                "related_recommendation_ids": [rec_id],
            }
        ],
        "provider_metadata": {"provider": "fake", "model_id": "m"},
        "limitations": [],
    }
    provider = _EnrichmentFakeProvider(payload)
    run = AiEnrichmentService(provider).run(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
        model_options=ModelInvocationOptions(model_id="m"),
    )
    assert len(provider.calls) == 1
    assert "Spring Boot" in run.enrichment.executive_summary.headline


def test_provider_failure_does_not_fabricate_enrichment(tmp_path: Path) -> None:
    from codestrata.ai.providers.exceptions import AIProviderInvocationError

    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)

    class FailingProvider(AIModelProvider):
        def __init__(self) -> None:
            self.calls: list[ModernizationModelRequest] = []

        def invoke(
            self,
            request: ModernizationModelRequest,
            options: ModelInvocationOptions,
        ) -> ModelInvocationResult:
            self.calls.append(request)
            raise AIProviderInvocationError("simulated provider failure")

    provider = FailingProvider()
    with pytest.raises(AIProviderInvocationError):
        AiEnrichmentService(provider).run(
            analysis_result=analysis,
            rule_evaluation=rules,
            recommendation_result=recs,
            repository_graph=pipeline.repository_graph,
            model_options=ModelInvocationOptions(model_id="m"),
        )
    assert len(provider.calls) == 1
    assert not (tmp_path / "advisor.json").exists()
    assert rules.findings
    assert recs.recommendations


def test_invalid_enrichment_json_rejected(tmp_path: Path) -> None:
    repository = _js_repo(tmp_path / "app")
    pipeline, rules, recs, analysis = _pipeline_bundle(repository)
    context = build_ai_enrichment_context(
        analysis_result=analysis,
        rule_evaluation=rules,
        recommendation_result=recs,
        repository_graph=pipeline.repository_graph,
    )
    metadata = ModelInvocationMetadata(
        provider="fake",
        model_id="m",
        latency_ms=1.0,
        usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    from codestrata.ai.providers.exceptions import AIResponseParsingError

    with pytest.raises(AIResponseParsingError):
        parse_enrichment_response("not-json", context, metadata)
