"""Tests for the end-to-end `codestrata assess` CLI command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
)
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
from codestrata.cli import app
from codestrata.cli.assess import (
    AssessmentCommandError,
    resolve_bedrock_model_id,
    run_assessment,
)
from codestrata.config import CodestrataSettings, load_settings
from codestrata.models import (
    AnalysisResult,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
)
from codestrata.reporting import AssessmentMode, ModernizationReportValidationError
from codestrata.static_analysis.models import StaticAnalysisResult, StaticAnalysisStatus

runner = CliRunner()


def _settings(**overrides: Any) -> CodestrataSettings:
    payload: dict[str, Any] = {
        "repository": {
            "url": "https://github.com/example/sample-app.git",
            "branch": "main",
        },
        "workspace": {"directory": ".codestrata-workspace", "clean_before_clone": True},
        "knowledge": {"enabled": False, "directory": ".codestrata-test-knowledge"},
        "static_analysis": {"enabled": False},
        "ai": {"bedrock": {}},
    }
    payload.update(overrides)
    return CodestrataSettings.model_validate(payload)


def _truncation(count: int = 1) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=False,
        original_count=count,
        included_count=count,
    )


def _repository(tmp_path: Path, *, name: str = "sample-app") -> Repository:
    repo_path = tmp_path / name
    repo_path.mkdir(parents=True, exist_ok=True)
    (repo_path / "README.md").write_text("demo\n", encoding="utf-8")
    return Repository(
        name=name,
        path=repo_path,
        files=["README.md"],
        total_files=1,
    )


def _analysis_result(
    repository: Repository,
    *,
    static_analysis_results: list[StaticAnalysisResult] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        repository=repository,
        technologies=[
            Technology(
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="test",
            )
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=1,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[
            Finding(
                rule_id="SEC001",
                title="Critical finding",
                description="Secret exposure",
                category=FindingCategory.SECURITY,
                severity=Severity.CRITICAL,
                source=FindingSource.DETERMINISTIC,
                evidence=[],
            )
        ],
        static_analysis_results=static_analysis_results or [],
    )


def _recommendation_result() -> AIRecommendationResult:
    return AIRecommendationResult(
        executive_summary="Executive summary.",
        overall_assessment="Overall assessment.",
        key_risks=["Secret exposure"],
        recommendations=[
            AIRecommendation(
                recommendation_id="AI-REC-001",
                title="Rotate secrets",
                description="Remove secrets",
                rationale="Finding SEC001",
                priority=AIRecommendationPriority.HIGH,
                effort=AIRecommendationEffort.MEDIUM,
                impact=AIRecommendationImpact.HIGH,
                confidence=AIRecommendationConfidence.MEDIUM,
                related_finding_ids=["SEC001"],
                suggested_actions=["Rotate credentials"],
                dependencies=[],
            )
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Reduce risk",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Safer baseline"],
            )
        ],
        evidence_coverage=EvidenceCoverage(
            total_findings=1,
            findings_considered=1,
            findings_referenced=1,
            coverage_percentage=100.0,
        ),
        limitations=["No runtime data"],
    )


class FakeScanner:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.calls: list[str | Path] = []

    def scan(self, source: str | Path) -> Repository:
        self.calls.append(source)
        return self.repository


class FakeAnalysisService:
    def __init__(self, result: AnalysisResult) -> None:
        self.result = result
        self.calls: list[Repository] = []

    def analyze(self, repository: Repository, **_: Any) -> AnalysisResult:
        self.calls.append(repository)
        return self.result


class FakeProvider(AIModelProvider):
    def __init__(
        self,
        result: AIRecommendationResult | None = None,
        *,
        error: Exception | None = None,
        raw_response_text: str = '{"secret":"AKIAIOSFODNN7EXAMPLE"}',
    ) -> None:
        self.result = result or _recommendation_result()
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
                usage=ModelUsage(input_tokens=9, output_tokens=11, total_tokens=20),
                stop_reason="end_turn",
            ),
            raw_response_text=self.raw_response_text,
            parsed_model_response=self.result.model_dump(mode="json"),
        )


class RecordingConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, *args: Any, **kwargs: Any) -> None:
        del kwargs
        self.messages.append(" ".join(str(arg) for arg in args))


class FakeContextBuilder:
    def __init__(self) -> None:
        self.calls: list[AnalysisResult] = []

    def build(self, result: AnalysisResult) -> LLMAnalysisContext:
        self.calls.append(result)
        findings = [
            LLMFindingEvidence(
                rule_id=item.rule_id,
                title=item.title,
                category=str(item.category.value),
                severity=str(item.severity.value),
                summary=item.description,
                evidence_truncation=_truncation(0),
            )
            for item in result.findings
        ]
        return LLMAnalysisContext(
            repository=LLMRepositoryContext(
                name=result.repository.name,
                source_type="local",
                file_count=result.repository.total_files or len(result.repository.files),
            ),
            metrics=LLMMetricsContext(
                finding_count=len(findings),
                technology_count=len(result.technologies),
            ),
            findings=findings,
            findings_truncation=_truncation(len(findings)),
        )


def _run(
    tmp_path: Path,
    *,
    repo_name: str = "sample-app",
    mode: AssessmentMode = AssessmentMode.AI_ENHANCED,
    provider: FakeProvider | None = None,
    scanner: FakeScanner | None = None,
    model_id: str | None = "test-model",
    settings: CodestrataSettings | None = None,
    console: RecordingConsole | None = None,
    analysis: AnalysisResult | None = None,
    context_builder: FakeContextBuilder | None = None,
    prompt_builder: Any = None,
    agent: Any = None,
    clock: Any = None,
    **kwargs: Any,
):
    repository = _repository(tmp_path, name=repo_name)
    analysis_result = analysis or _analysis_result(repository)
    active_provider = provider or FakeProvider()
    active_context_builder = context_builder or FakeContextBuilder()
    active_settings = settings or _settings(
        knowledge={
            "enabled": False,
            "directory": str(tmp_path / "knowledge"),
        }
    )
    return (
        run_assessment(
            repo=str(repository.path),
            output_directory=tmp_path / "reports",
            mode=mode,
            model_id=model_id,
            settings=active_settings,
            scanner=scanner or FakeScanner(repository),
            analysis_service=FakeAnalysisService(analysis_result),
            provider=active_provider,
            prompt_builder=prompt_builder,
            agent=agent,
            context_builder=active_context_builder,
            console=console or RecordingConsole(),
            clock=clock or (lambda: datetime(2026, 7, 21, 18, 0, tzinfo=UTC)),
            **kwargs,
        ),
        active_provider,
        active_context_builder,
    )


def test_assess_appears_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "assess" in result.stdout


def test_assess_help_lists_required_options() -> None:
    result = runner.invoke(app, ["assess", "--help"])
    assert result.exit_code == 0
    assert "--repo" in result.stdout
    assert "--output" in result.stdout
    assert "--model-id" in result.stdout
    assert "--with-ai" in result.stdout
    assert "--no-ai" in result.stdout
    assert "--pmd-path" in result.stdout
    assert "--static-analysis" in result.stdout
    assert "--no-static-analy" in result.stdout


def _assert_dual_reports(result: Any) -> None:
    assert result.run_directory.exists()
    assert result.html_report_path.exists()
    assert result.json_report_path.exists()
    assert result.report_path == result.html_report_path
    assert result.html_report_path.name == "assessment.html"
    assert result.json_report_path.name == "assessment.json"
    assert not (result.run_directory / "report.txt").exists()
    assert result.html_report_path.parent == result.run_directory
    assert result.json_report_path.parent == result.run_directory
    manifest = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    assert str(manifest["schema"]).startswith("codestrata-assessment-manifest")


def test_assess_defaults_to_deterministic_mode() -> None:
    result = runner.invoke(app, ["assess", "--help"])
    assert result.exit_code == 0
    assert "Default is --no-ai" in result.stdout or "--no-ai" in result.stdout


def test_local_repository_assessment_success(tmp_path: Path) -> None:
    result, provider, _ = _run(tmp_path, repo_name="spring-petclinic")
    assert result.repository_name == "spring-petclinic"
    assert result.mode == AssessmentMode.AI_ENHANCED
    assert result.ai_executed is True
    _assert_dual_reports(result)
    assert result.run_directory.parent.name == "local-spring-petclinic"
    assert result.run_directory.name == "current"
    assert result.html_report_path.name == "assessment.html"
    assert result.json_report_path.name == "assessment.json"
    assert result.findings_count == 3
    assert result.technologies_count == 1
    assert result.recommendations_count == 2
    assert result.phases_count == 1
    assert result.input_tokens == 9
    assert result.output_tokens == 11
    assert result.model_id == "test-model"
    assert result.duration_ms is not None
    assert result.duration_ms >= 0
    assert len(provider.calls) == 1
    assert (result.run_directory / "advisor.json").is_file()
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "Findings" in html
    assert "Priority Actions" in html
    assert "Modernization Advisor" in html
    assert 'id="modernization-advisor"' in html
    assert "Modernization Advisor interpretation" in html or "Rotate secrets" in html


def test_deterministic_assessment_success_without_model_or_aws(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "CODESTRATA_BEDROCK_MODEL_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    provider = FakeProvider()
    context_builder = FakeContextBuilder()
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
        provider=provider,
        context_builder=context_builder,
        prompt_builder=MagicMock(),
        agent=MagicMock(),
    )
    assert result.mode == AssessmentMode.DETERMINISTIC
    assert result.ai_executed is False
    _assert_dual_reports(result)
    assert result.recommendations_count == 2
    assert result.phases_count == 0
    assert result.model_id is None
    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.latency_ms is None
    assert provider.calls == []
    assert context_builder.calls == []
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "Leadership Verdict" in html
    assert "Executive Summary" in html
    assert "Deterministic" in html
    assert 'id="ai-enrichment"' not in html
    assert "Findings" in html
    assert "Priority Actions" in html
    assert "AKIAIOSFODNN7EXAMPLE" not in html


def test_deterministic_mode_does_not_construct_ai_components(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _boom_provider(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("provider")
        raise AssertionError("provider must not be constructed")

    def _boom_prompt(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("prompt")
        raise AssertionError("prompt builder must not be constructed")

    def _boom_agent(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("agent")
        raise AssertionError("agent must not be constructed")

    monkeypatch.setattr(
        "codestrata.application.assessment.service._create_bedrock_provider",
        _boom_provider,
    )
    monkeypatch.setattr(
        "codestrata.ai.prompts.ModernizationPromptBuilder",
        _boom_prompt,
    )
    monkeypatch.setattr(
        "codestrata.ai.agents.ModernizationAssessmentAgent",
        _boom_agent,
    )
    result, provider, context_builder = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
    )
    assert result.ai_executed is False
    assert provider.calls == []
    assert context_builder.calls == []
    assert calls == []


def test_github_repository_assessment_success_with_mocked_scanner(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path, name="github-app")
    scanner = FakeScanner(repository)
    result, provider, _ = _run(
        tmp_path,
        repo_name="github-app",
        scanner=scanner,
    )
    assert scanner.calls
    assert result.repository_name == "github-app"
    assert len(provider.calls) == 1


def test_deterministic_orchestration_order(tmp_path: Path) -> None:
    console = RecordingConsole()
    _run(tmp_path, mode=AssessmentMode.DETERMINISTIC, model_id=None, console=console)
    joined = "\n".join(console.messages)
    stages = [
        "Initializing...",
        "Discovering repository...",
        "Analyzing technologies...",
        "Running Engineering Intelligence...",
        "Generating report...",
    ]
    positions = [joined.index(stage) for stage in stages]
    assert positions == sorted(positions)
    assert "Building AI context" not in joined
    assert "Running modernization assessment" not in joined
    assert "Building AI enrichment context" not in joined
    assert "Running AI enrichment" not in joined
    assert "Building Modernization Advisor context" not in joined
    assert "Running Modernization Advisor" not in joined
    assert "Assessment mode: Deterministic" in joined
    assert "Engineering Intelligence:" in joined
    assert "Model ID:" not in joined


def test_ai_enhanced_orchestration_order(tmp_path: Path) -> None:
    console = RecordingConsole()
    _run(tmp_path, mode=AssessmentMode.AI_ENHANCED, console=console)
    joined = "\n".join(console.messages)
    stages = [
        "Initializing...",
        "Discovering repository...",
        "Analyzing technologies...",
        "Running Engineering Intelligence...",
        "Building Modernization Advisor context...",
        "Running Modernization Advisor...",
        "Generating report...",
    ]
    positions = [joined.index(stage) for stage in stages]
    assert positions == sorted(positions)
    assert "Building AI context" not in joined
    assert "Running modernization assessment" not in joined
    assert "Assessment mode: AI Enhanced" in joined
    assert "Engineering Intelligence:" in joined
    assert "Model ID:" in joined


def test_quiet_suppresses_stages_and_json_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    console = RecordingConsole()
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
        console=console,
        quiet=True,
        json_summary=True,
    )
    joined = "\n".join(console.messages)
    assert "Initializing..." not in joined
    # Quiet + json-summary: machine JSON on stdout only (no human completion dump).
    assert "Report generated successfully." not in joined
    assert "Modernization assessment completed" not in joined
    assert "Engineering Intelligence:" not in joined
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["repository"] == result.repository_name
    assert payload["ai_status"] == "not_requested"
    assert "html_report" in payload
    assert "duration_ms" in payload
    assert "findings" in payload


def test_quiet_prints_compact_completion_summary(tmp_path: Path) -> None:
    console = RecordingConsole()
    _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
        console=console,
        quiet=True,
    )
    joined = "\n".join(console.messages)
    assert "Initializing..." not in joined
    assert "Report generated successfully." in joined
    assert "Repository:" in joined
    assert "AI status:" in joined
    assert "HTML Report:" in joined
    assert "JSON Report:" in joined
    assert "Engineering Intelligence:" not in joined


def test_output_directory_creation_and_sanitized_filename(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "out"
    repository = _repository(tmp_path, name="Spring Petclinic!")
    result = run_assessment(
        repo=str(repository.path),
        output_directory=output,
        mode=AssessmentMode.AI_ENHANCED,
        model_id="m",
        settings=_settings(),
        scanner=FakeScanner(repository),
        analysis_service=FakeAnalysisService(_analysis_result(repository)),
        provider=FakeProvider(),
        context_builder=FakeContextBuilder(),
        console=RecordingConsole(),
        clock=lambda: datetime(2026, 7, 21, 18, 0, tzinfo=UTC),
    )
    assert output.exists()
    _assert_dual_reports(result)
    assert result.run_directory == output / "local-spring-petclinic" / "current"
    assert result.html_report_path == result.run_directory / "assessment.html"
    assert result.json_report_path == result.run_directory / "assessment.json"
    assert not (output / "spring-petclinic-modernization-assessment.html").exists()


def test_model_id_from_cli(tmp_path: Path) -> None:
    result, _, _ = _run(tmp_path, model_id="cli-model")
    assert result.model_id == "cli-model"


def test_model_id_from_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODESTRATA_BEDROCK_MODEL_ID", "env-model")
    result, _, _ = _run(tmp_path, model_id=None)
    assert result.model_id == "env-model"


def test_model_id_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODESTRATA_BEDROCK_MODEL_ID", raising=False)
    settings = _settings(ai={"bedrock": {"model_id": "config-model"}})
    result, _, _ = _run(tmp_path, model_id=None, settings=settings)
    assert result.model_id == "config-model"


def test_ai_mode_defaults_to_nova_lite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODESTRATA_BEDROCK_MODEL_ID", raising=False)
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.AI_ENHANCED,
        model_id=None,
        settings=_settings(),
    )
    assert result.model_id == "amazon.nova-lite-v1:0"


def test_model_id_without_with_ai_is_usage_error(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-app.git"
        """,
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "assess",
            "--repo",
            str(repository.path),
            "--output",
            str(tmp_path / "out"),
            "--config",
            str(config),
            "--model-id",
            "test-model",
        ],
    )
    assert result.exit_code == 2
    assert "--model-id requires --with-ai" in result.stderr


def test_provider_timeout(tmp_path: Path) -> None:
    provider = FakeProvider(error=AIProviderTimeoutError("timed out"))
    result, active_provider, _ = _run(tmp_path, provider=provider)
    assert result.html_report_path.is_file()
    assert result.json_report_path.is_file()
    assert result.ai_executed is False
    assert result.mode == AssessmentMode.AI_ENHANCED
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "failed" in html.lower()
    document = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    assert str(document["schema"]).startswith("codestrata-assessment-manifest")
    assert result.ai_executed is False
    assert active_provider.calls


def test_provider_authentication_failure(tmp_path: Path) -> None:
    provider = FakeProvider(error=AIProviderInvocationError("Bedrock authentication error: denied"))
    result, _, _ = _run(tmp_path, provider=provider)
    assert result.html_report_path.is_file()
    assert result.ai_executed is False
    document = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    html = result.html_report_path.read_text(encoding="utf-8")
    assert str(document["schema"]).startswith("codestrata-assessment-manifest")
    combined = html.lower()
    assert result.ai_executed is False
    assert "auth" in combined or "unable to authenticate" in combined or "failed" in combined


def test_ai_provider_failure_retains_deterministic_report(tmp_path: Path) -> None:
    provider = FakeProvider(error=AIProviderInvocationError("provider exploded"))
    result, active_provider, _ = _run(tmp_path, mode=AssessmentMode.AI_ENHANCED, provider=provider)
    assert active_provider.calls  # invoked once before failing
    assert len(active_provider.calls) == 1
    assert result.html_report_path.is_file()
    assert result.json_report_path.is_file()
    assert result.ai_executed is False
    document = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    findings = json.loads((result.run_directory / "findings.json").read_text(encoding="utf-8"))
    assert str(document["schema"]).startswith("codestrata-assessment-manifest")
    assert findings["finding_count"] >= 1
    assert not (result.run_directory / "advisor.json").exists()
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "Findings" in html
    assert 'id="ai-enrichment"' not in html
    assert "raw_response" not in html.lower()


def test_invalid_model_response(tmp_path: Path) -> None:
    provider = FakeProvider(error=AIResponseValidationError("bad schema"))
    result, _, _ = _run(tmp_path, provider=provider)
    assert result.html_report_path.is_file()
    assert result.ai_executed is False
    document = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    html = result.html_report_path.read_text(encoding="utf-8")
    execution = json.loads(
        (result.run_directory / "advisor-execution.json").read_text(encoding="utf-8")
    )
    assert str(document["schema"]).startswith("codestrata-assessment-manifest")
    assert execution["execution_status"] == "validation_failed"
    assert "contract validation" in html.lower() or execution["failure"]["code"] == "AI_VALIDATION_FAILED"
    assert (result.run_directory / "advisor-execution.json").is_file()


def test_report_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> tuple[Path, Path]:
        raise ModernizationReportValidationError("bad report")

    monkeypatch.setattr(
        "codestrata.application.assessment.service.write_modernization_assessment_reports",
        _boom,
    )
    with pytest.raises(AssessmentCommandError, match="Report validation or write failure"):
        _run(tmp_path, mode=AssessmentMode.DETERMINISTIC, model_id=None)


def test_report_write_failure_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> tuple[Path, Path]:
        raise OSError("disk full")

    monkeypatch.setattr(
        "codestrata.application.assessment.service.write_modernization_assessment_reports",
        _boom,
    )
    with pytest.raises(AssessmentCommandError, match="Report validation or write failure"):
        _run(tmp_path, mode=AssessmentMode.DETERMINISTIC, model_id=None)


def test_concise_success_output_without_raw_response_or_credentials(
    tmp_path: Path,
) -> None:
    console = RecordingConsole()
    provider = FakeProvider(raw_response_text="SYSTEM PROMPT AKIAIOSFODNN7EXAMPLE")
    _run(tmp_path, provider=provider, console=console)
    joined = "\n".join(console.messages)
    assert "Report generated successfully." in joined
    assert "Assessment mode: AI Enhanced" in joined
    assert "Repository:" in joined
    assert "Findings:" in joined
    assert "Engineering Intelligence:" in joined
    assert "Report location:" in joined
    assert "HTML Report:" in joined
    assert "JSON Report:" in joined
    assert "Text report:" not in joined
    sanitized = (
        joined.replace("HTML Report:", "")
        .replace("JSON Report:", "")
        .replace("Report location:", "")
        .replace("Report generated successfully.", "")
        .replace("Open report:", "")
    )
    assert "Report:" not in sanitized
    assert "AKIAIOSFODNN7EXAMPLE" not in joined
    assert "SYSTEM PROMPT" not in joined
    assert provider.raw_response_text not in joined


def test_cli_deterministic_succeeds_without_model_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODESTRATA_BEDROCK_MODEL_ID", raising=False)
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [knowledge]
        enabled = false
        directory = "{knowledge}"

        [static_analysis]
        enabled = false
        """.format(knowledge=(tmp_path / "knowledge").as_posix()),
        encoding="utf-8",
    )
    repository = _repository(tmp_path)
    result = runner.invoke(
        app,
        [
            "assess",
            "--repo",
            str(repository.path),
            "--output",
            str(tmp_path / "out"),
            "--config",
            str(config),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Assessment mode: Deterministic" in result.stdout
    assert "Missing Bedrock model ID" not in result.stderr


def test_cli_ai_mode_defaults_model_and_retains_deterministic_on_auth_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODESTRATA_BEDROCK_MODEL_ID", raising=False)
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [knowledge]
        enabled = false
        directory = "{knowledge}"

        [static_analysis]
        enabled = false
        """.format(knowledge=(tmp_path / "knowledge").as_posix()),
        encoding="utf-8",
    )
    repository = _repository(tmp_path)
    result = runner.invoke(
        app,
        [
            "assess",
            "--repo",
            str(repository.path),
            "--output",
            str(tmp_path / "out"),
            "--config",
            str(config),
            "--with-ai",
        ],
    )
    # Without usable AWS credentials the AI stage fails, but deterministic reports remain.
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "AI status: fallback" in result.stdout
    assert "Missing Bedrock model ID" not in result.stderr
    assert "Traceback" not in result.stderr
    out_root = tmp_path / "out"
    manifests = [path for path in out_root.rglob("assessment.json")]
    assert manifests
    document = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert str(document["schema"]).startswith("codestrata-assessment-manifest")
    html_paths = list(out_root.rglob("assessment.html"))
    assert html_paths
    html = html_paths[0].read_text(encoding="utf-8")
    assert "fallback" in html.lower() or "Authentication failed" in html or "Provider failed" in html


def test_verbose_error_mode_includes_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> tuple[Path, Path]:
        raise OSError("disk full")

    monkeypatch.setattr(
        "codestrata.application.assessment.service.write_modernization_assessment_reports",
        _boom,
    )
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [knowledge]
        enabled = false
        directory = "{knowledge}"

        [static_analysis]
        enabled = false
        """.format(knowledge=(tmp_path / "knowledge").as_posix()),
        encoding="utf-8",
    )
    repository = _repository(tmp_path)
    result = runner.invoke(
        app,
        [
            "assess",
            "--repo",
            str(repository.path),
            "--output",
            str(tmp_path / "out"),
            "--config",
            str(config),
            "--verbose",
        ],
    )
    assert result.exit_code != 0
    assert "Report validation or write failure" in result.stderr
    assert "Traceback" in result.stderr


def test_exactly_one_model_invocation_in_ai_mode(tmp_path: Path) -> None:
    _, provider, _ = _run(tmp_path, mode=AssessmentMode.AI_ENHANCED)
    assert len(provider.calls) == 1


def test_zero_model_invocations_in_deterministic_mode(tmp_path: Path) -> None:
    _, provider, context_builder = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
    )
    assert provider.calls == []
    assert context_builder.calls == []


def test_static_analysis_unavailable_warning(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    analysis = _analysis_result(
        repository,
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="pmd",
                status=StaticAnalysisStatus.UNAVAILABLE,
                findings=[],
                error_message="pmd executable not found",
            )
        ],
    )
    console = RecordingConsole()
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
        analysis=analysis,
        console=console,
    )
    assert result.ai_executed is False
    joined = "\n".join(console.messages)
    assert (
        "pmd static analysis was unavailable. Remaining deterministic analyzers completed."
    ) in joined
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "Warnings" in html
    assert "static analysis was unavailable" in html.replace("<wbr>", "")
    assert "Remaining deterministic analyzers completed." in html.replace("<wbr>", "")


def test_deterministic_writes_html_and_json(tmp_path: Path) -> None:
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
    )
    _assert_dual_reports(result)
    assert result.html_report_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    payload = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    assert str(payload["schema"]).startswith("codestrata-assessment-manifest")
    assert result.mode == AssessmentMode.DETERMINISTIC
    assert result.ai_executed is False
    assert result.model_id is None
    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.recommendations_count == 2
    recommendations = json.loads(
        (result.run_directory / "recommendations.json").read_text(encoding="utf-8")
    )
    assert recommendations["recommendation_count"] == 2


def test_ai_mode_writes_html_and_json(tmp_path: Path) -> None:
    result, _, _ = _run(tmp_path, mode=AssessmentMode.AI_ENHANCED)
    _assert_dual_reports(result)
    payload = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    assert str(payload["schema"]).startswith("codestrata-assessment-manifest")
    assert result.mode == AssessmentMode.AI_ENHANCED
    assert result.ai_executed is True
    assert result.model_id == "test-model"
    assert result.input_tokens == 9
    assert result.output_tokens == 11
    assert result.recommendations_count == 2
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "Priority Actions" in html
    assert "Modernization Advisor" in html
    assert 'id="modernization-advisor"' in html


def test_second_assessment_preserves_previous_run(tmp_path: Path) -> None:
    first, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
        clock=lambda: datetime(2026, 7, 21, 15, 30, 45, tzinfo=UTC),
    )
    second, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.DETERMINISTIC,
        model_id=None,
        clock=lambda: datetime(2026, 7, 21, 15, 31, 0, tzinfo=UTC),
    )
    assert first.run_directory.exists()
    assert second.run_directory.exists()
    assert second.run_directory.name == "current"
    previous = second.run_directory.parent / "previous"
    assert previous.is_dir()
    assert (previous / "assessment.html").is_file()
    assert (second.run_directory / "assessment.html").is_file()
    active = sorted(
        path.name
        for path in second.run_directory.parent.iterdir()
        if path.is_dir() and path.name != "archive"
    )
    assert active == ["current", "previous"]
    flat = list((tmp_path / "reports").glob("*-modernization-assessment.*"))
    assert flat == []


def test_fourth_assessment_deletes_oldest_run(tmp_path: Path) -> None:
    clocks = [
        datetime(2026, 7, 21, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 11, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 13, 0, 0, tzinfo=UTC),
    ]
    results = []
    for moment in clocks:
        result, _, _ = _run(
            tmp_path,
            mode=AssessmentMode.DETERMINISTIC,
            model_id=None,
            clock=lambda moment=moment: moment,
        )
        results.append(result)

    repo_dir = results[-1].run_directory.parent
    active = sorted(path.name for path in repo_dir.iterdir() if path.is_dir())
    assert active == ["current", "previous"]
    assert not (repo_dir / "archive").exists()
    assert results[-1].run_directory.name == "current"
    assert results[-1].html_report_path.is_file()
    assert results[-1].json_report_path.is_file()


def test_fifth_assessment_still_keeps_three_runs(tmp_path: Path) -> None:
    clocks = [
        datetime(2026, 7, 21, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 11, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 13, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 14, 0, 0, tzinfo=UTC),
    ]
    for moment in clocks:
        _run(
            tmp_path,
            mode=AssessmentMode.DETERMINISTIC,
            model_id=None,
            clock=lambda moment=moment: moment,
        )

    repo_dir = tmp_path / "reports" / "local-sample-app"
    active = sorted(path.name for path in repo_dir.iterdir() if path.is_dir())
    assert active == ["current", "previous"]
    assert not (repo_dir / "archive").exists()


def test_aged_out_run_deletes_execution_artifact(tmp_path: Path) -> None:
    results = []
    for moment in [
        datetime(2026, 7, 21, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 11, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC),
    ]:
        result, _, _ = _run(
            tmp_path,
            mode=AssessmentMode.DETERMINISTIC,
            model_id=None,
            clock=lambda moment=moment: moment,
        )
        results.append(result)

    repo_dir = results[-1].run_directory.parent
    active = sorted(path.name for path in repo_dir.iterdir() if path.is_dir())
    assert active == ["current", "previous"]
    assert not (repo_dir / "archive").exists()


def test_retention_cleanup_failure_does_not_fail_assessment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> list[Path]:
        raise OSError("cannot delete")

    monkeypatch.setattr(
        "codestrata.application.assessment.service.promote_staged_report",
        _boom,
    )
    result, _, _ = _run(tmp_path, mode=AssessmentMode.DETERMINISTIC, model_id=None)
    assert result.html_report_path.is_file()
    assert result.json_report_path.is_file()


def test_failed_report_write_does_not_trigger_retention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.application.assessment import service as assess_service

    repo_dir = tmp_path / "reports" / "sample-app"
    for timestamp in [
        "20260721-100000",
        "20260721-110000",
        "20260721-120000",
        "20260721-130000",
    ]:
        run = repo_dir / timestamp
        run.mkdir(parents=True)
        (run / "report.html").write_text("html", encoding="utf-8")
        (run / "report.json").write_text("{}", encoding="utf-8")

    def fail_write(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OSError("disk full")

    monkeypatch.setattr(
        assess_service,
        "write_modernization_assessment_reports",
        fail_write,
    )
    with pytest.raises(AssessmentCommandError, match="Report validation or write failure"):
        _run(
            tmp_path,
            mode=AssessmentMode.DETERMINISTIC,
            model_id=None,
            clock=lambda: datetime(2026, 7, 21, 14, 0, 0, tzinfo=UTC),
        )

    active = sorted(path.name for path in repo_dir.iterdir() if path.is_dir())
    assert "archive" not in {path.name for path in repo_dir.iterdir()}
    assert "20260721-100000" in active
    # Graph artifacts are written before HTML/JSON under staging. A failed report
    # write must not prune older completed runs under the legacy timestamp layout.
    staging_run = tmp_path / "reports" / ".staging" / "sample-app-20260721-140000"
    assert staging_run.is_dir()
    assert (staging_run / "graphs").is_dir()
    assert not (staging_run / "assessment.html").exists()
    assert not (staging_run / "report.html").exists()
    assert len([name for name in active if name.startswith("20260721-")]) == 4


def test_artifacts_share_matching_summary_fields(tmp_path: Path) -> None:
    result, _, _ = _run(tmp_path, mode=AssessmentMode.AI_ENHANCED)
    html = result.html_report_path.read_text(encoding="utf-8")
    payload = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    findings = json.loads((result.run_directory / "findings.json").read_text(encoding="utf-8"))
    recommendations = json.loads(
        (result.run_directory / "recommendations.json").read_text(encoding="utf-8")
    )
    assert str(payload["schema"]).startswith("codestrata-assessment-manifest")
    assert findings["finding_count"] == result.findings_count
    assert recommendations["recommendation_count"] == result.recommendations_count
    assert result.repository_name in html
    assert "AI Enhanced" in html or result.mode == AssessmentMode.AI_ENHANCED


def test_json_has_no_absolute_repo_path_or_raw_credentials(tmp_path: Path) -> None:
    provider = FakeProvider(raw_response_text="SYSTEM PROMPT AKIAIOSFODNN7EXAMPLE")
    result, _, _ = _run(tmp_path, provider=provider)
    raw = result.json_report_path.read_bytes()
    text = raw.decode("utf-8")
    assert str(tmp_path) not in text
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "SYSTEM PROMPT" not in text
    assert "raw_model_response" not in text
    assert "AWS_SECRET" not in text
    payload = json.loads(text)
    assert str(payload["schema"]).startswith("codestrata-assessment-manifest")
    git_block = payload.get("git") or {}
    assert "path" not in git_block
    assert not str(git_block.get("remote") or "").startswith("/")


def test_html_and_json_summary_counts_match(tmp_path: Path) -> None:
    result, _, _ = _run(tmp_path, mode=AssessmentMode.AI_ENHANCED)
    payload = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    findings = json.loads((result.run_directory / "findings.json").read_text(encoding="utf-8"))
    recommendations = json.loads(
        (result.run_directory / "recommendations.json").read_text(encoding="utf-8")
    )
    assert str(payload["schema"]).startswith("codestrata-assessment-manifest")
    assert findings["finding_count"] == result.findings_count
    assert recommendations["recommendation_count"] == result.recommendations_count
    assert result.ai_executed is True
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "Leadership Verdict" in html
    assert "Executive Summary" in html
    assert "Priority Actions" in html
    # Finding totals remain visible via severity cards / appendix summary.
    assert str(result.findings_count) in html


def test_json_ends_with_newline_and_valid_utf8(tmp_path: Path) -> None:
    result, _, _ = _run(tmp_path, mode=AssessmentMode.DETERMINISTIC, model_id=None)
    raw = result.json_report_path.read_bytes()
    text = raw.decode("utf-8")
    assert text.endswith("\n")
    json.loads(text)


def test_resolve_model_id_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODESTRATA_BEDROCK_MODEL_ID", "env-model")
    settings = _settings(ai={"bedrock": {"model_id": "config-model"}})
    assert resolve_bedrock_model_id(cli_model_id="cli-model", settings=settings) == "cli-model"
    assert resolve_bedrock_model_id(cli_model_id=None, settings=settings) == "env-model"
    monkeypatch.delenv("CODESTRATA_BEDROCK_MODEL_ID", raising=False)
    assert resolve_bedrock_model_id(cli_model_id=None, settings=settings) == "config-model"
    assert (
        resolve_bedrock_model_id(cli_model_id=None, settings=_settings()) == "amazon.nova-lite-v1:0"
    )


def test_load_settings_reads_bedrock_configuration(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [ai.bedrock]
        model_id = "amazon.nova-lite-v1:0"
        region = "us-west-2"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.ai.provider == "bedrock"
    assert settings.ai.bedrock.model_id == "amazon.nova-lite-v1:0"
    assert settings.ai.bedrock.region == "us-west-2"


def test_invalid_local_repository_path(tmp_path: Path) -> None:
    with pytest.raises(AssessmentCommandError, match="Repository path does not exist"):
        run_assessment(
            repo=str(tmp_path / "missing"),
            output_directory=tmp_path / "out",
            mode=AssessmentMode.DETERMINISTIC,
            settings=_settings(),
            console=RecordingConsole(),
        )
