"""Onboarding-focused CLI and configuration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.cli.assess import (
    AssessmentCommandError,
    resolve_assessment_repository,
    run_assessment,
)
from codestrata.config import CodestrataSettings, load_settings
from codestrata.reporting import AssessmentMode

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]  # monorepo root
ENGINE_ROOT = REPO_ROOT / "engine"
SAMPLE_JS = REPO_ROOT / "test-fixtures" / "sample-js-app"


def _settings(**overrides: object) -> CodestrataSettings:
    payload: dict[str, object] = {
        "repository": {
            "path": str(SAMPLE_JS),
        },
        "workspace": {"directory": ".codestrata-workspace", "clean_before_clone": True},
        "static_analysis": {"enabled": False},
        "ai": {"bedrock": {}},
    }
    payload.update(overrides)
    return CodestrataSettings.model_validate(payload)


def test_resolve_assessment_repository_prefers_cli() -> None:
    settings = _settings(
        repository={
            "path": "/configured/path",
            "url": "https://github.com/example/configured.git",
        }
    )
    assert resolve_assessment_repository("/explicit/repo", settings) == "/explicit/repo"


def test_resolve_assessment_repository_prefers_path_over_url() -> None:
    settings = _settings(
        repository={
            "path": "/configured/path",
            "url": "https://github.com/example/configured.git",
        }
    )
    assert resolve_assessment_repository(None, settings) == "/configured/path"


def test_resolve_assessment_repository_falls_back_to_url() -> None:
    settings = _settings(
        repository={"url": "https://github.com/example/configured.git"},
    )
    assert (
        resolve_assessment_repository(None, settings) == "https://github.com/example/configured.git"
    )


def test_repository_settings_require_url_or_path() -> None:
    with pytest.raises(Exception, match="Configure repository"):
        CodestrataSettings.model_validate({"repository": {}})


def test_resolve_assessment_repository_missing_raises_actionable_error() -> None:
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"url": "https://github.com/example/app.git"},
            "static_analysis": {"enabled": False},
        }
    )
    from codestrata.application.assessment import service as assess_service

    original = assess_service.configured_repository_source
    try:
        assess_service.configured_repository_source = lambda _settings: None  # type: ignore[assignment]
        with pytest.raises(AssessmentCommandError, match="No repository configured"):
            resolve_assessment_repository(None, settings)
    finally:
        assess_service.configured_repository_source = original


def test_resolve_assessment_repository_empty_cli_uses_config() -> None:
    settings = _settings(repository={"path": "/from-config"})
    assert resolve_assessment_repository("   ", settings) == "/from-config"


def test_config_driven_javascript_assessment(tmp_path: Path) -> None:
    assert SAMPLE_JS.is_dir()
    output = tmp_path / "reports"
    result = run_assessment(
        repo=None,
        output_directory=output,
        mode=AssessmentMode.DETERMINISTIC,
        settings=_settings(),
        static_analysis_enabled=False,
    )
    assert result.html_report_path.is_file()
    assert result.json_report_path.is_file()
    assert result.technologies_count >= 1
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "JavaScript" in html or "javascript" in html.lower() or "Node" in html
    assert "spring-petclinic" not in html.lower()
    assert result.graphs_directory is not None
    assert result.graphs_directory.is_dir()
    assert (result.graphs_directory / "repository-graph.json").is_file()
    assert (result.graphs_directory / "knowledge-bindings.json").is_file()
    assert (result.graphs_directory / "assessment-graph.json").is_file()
    assert (result.graphs_directory / "graph-summary.json").is_file()
    bindings = json.loads(
        (result.graphs_directory / "knowledge-bindings.json").read_text(encoding="utf-8")
    )
    matched = {item["matched_key"] for item in bindings["bindings"]}
    assert "javascript" in matched
    assert result.knowledge_binding_count is not None
    assert result.knowledge_binding_count >= 1
    assert result.findings_artifact_path is not None
    assert result.findings_artifact_path.is_file()
    assert result.rule_finding_count is not None
    assert result.rule_finding_count >= 1
    assert result.rules_evaluated_count is not None
    assert result.rules_evaluated_count >= 1
    assert result.recommendations_artifact_path is not None
    assert result.recommendations_artifact_path.is_file()
    assert result.phase3_recommendation_count is not None
    assert result.phase3_recommendation_count >= 1
    recommendations = json.loads(result.recommendations_artifact_path.read_text(encoding="utf-8"))
    findings = json.loads(result.findings_artifact_path.read_text(encoding="utf-8"))
    report = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    # Customer universe: findings.json / recommendations.json / report.json / summary agree.
    assert recommendations["recommendation_count"] == result.recommendations_count
    assert findings["finding_count"] == result.findings_count
    assert report["assessment"]["summary"]["recommendation_count"] == result.recommendations_count
    assert report["assessment"]["summary"]["finding_count"] == result.findings_count
    assert result.recommendations_count >= result.phase3_recommendation_count
    assert result.findings_count >= result.rule_finding_count


def test_config_driven_javascript_assessment_with_fake_ai(tmp_path: Path) -> None:
    """Config-driven JS path invokes the injected AI provider once (no Bedrock)."""

    from codestrata.ai.providers.base import AIModelProvider
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

    class CountingFakeProvider(AIModelProvider):
        def __init__(self) -> None:
            self.calls: list[ModernizationModelRequest] = []

        def invoke(
            self,
            request: ModernizationModelRequest,
            options: ModelInvocationOptions,
        ) -> ModelInvocationResult:
            self.calls.append(request)
            grounding: list[str] = []
            for finding in request.analysis_context.findings:
                candidate = finding.rule_id or finding.finding_id
                if candidate:
                    grounding = [candidate]
                    break
            finding_count = len(request.analysis_context.findings)
            recommendation = AIRecommendationResult(
                executive_summary="Executive summary for sample JS app.",
                overall_assessment="Overall assessment for sample JS app.",
                key_risks=["Limited production evidence"],
                recommendations=[
                    AIRecommendation(
                        recommendation_id="AI-REC-001",
                        title="Keep dependencies current",
                        description="Track npm dependency updates.",
                        rationale="Sample app already uses a modern stack.",
                        priority=AIRecommendationPriority.MEDIUM,
                        effort=AIRecommendationEffort.SMALL,
                        impact=AIRecommendationImpact.MEDIUM,
                        confidence=AIRecommendationConfidence.HIGH,
                        related_finding_ids=grounding,
                        suggested_actions=["Review package.json regularly"],
                        dependencies=[],
                    )
                ],
                modernization_phases=[
                    ModernizationPhase(
                        phase=1,
                        name="Stabilize",
                        objective="Keep the current stack healthy.",
                        recommendations=["AI-REC-001"],
                        expected_outcomes=["Predictable dependency posture"],
                    )
                ],
                evidence_coverage=EvidenceCoverage(
                    total_findings=finding_count,
                    findings_considered=finding_count,
                    findings_referenced=len(grounding),
                    coverage_percentage=(
                        round(100.0 * len(grounding) / finding_count, 2) if finding_count else 0.0
                    ),
                ),
                limitations=["Fixture provider; no Bedrock call"],
            )
            return ModelInvocationResult(
                recommendation_result=recommendation,
                metadata=ModelInvocationMetadata(
                    provider="fake",
                    model_id=options.model_id,
                    request_id="req-js-1",
                    latency_ms=1.0,
                    usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
                    stop_reason="end_turn",
                ),
                raw_response_text="{}",
                parsed_model_response=recommendation.model_dump(mode="json"),
            )

    provider = CountingFakeProvider()
    output = tmp_path / "reports"
    result = run_assessment(
        repo=None,
        output_directory=output,
        mode=AssessmentMode.AI_ENHANCED,
        model_id="fake-model",
        settings=_settings(),
        provider=provider,
        static_analysis_enabled=False,
    )
    assert result.html_report_path.is_file()
    assert len(provider.calls) == 1
    assert result.graphs_directory is not None
    assert (result.graphs_directory / "assessment-graph.json").is_file()
    assert result.recommendations_artifact_path is not None
    assert result.recommendations_artifact_path.is_file()
    assert result.phase3_recommendation_count is not None
    assert result.phase3_recommendation_count >= 1
    assert (result.run_directory / "advisor.json").is_file()
    assert "spring-petclinic" not in result.html_report_path.read_text(encoding="utf-8").lower()


def test_config_driven_javascript_zero_ai_calls_deterministic(tmp_path: Path) -> None:
    from codestrata.ai.providers.base import AIModelProvider
    from codestrata.ai.providers.models import ModelInvocationOptions, ModelInvocationResult

    class ForbiddenProvider(AIModelProvider):
        def invoke(self, request, options: ModelInvocationOptions) -> ModelInvocationResult:  # type: ignore[no-untyped-def]
            raise AssertionError("AI provider must not be called in deterministic mode")

    result = run_assessment(
        repo=None,
        output_directory=tmp_path / "reports",
        mode=AssessmentMode.DETERMINISTIC,
        settings=_settings(),
        provider=ForbiddenProvider(),
        static_analysis_enabled=False,
    )
    assert result.ai_executed is False
    assert result.graphs_directory is not None
    assert result.recommendations_artifact_path is not None
    assert result.recommendations_artifact_path.is_file()
    assert not (result.run_directory / "advisor.json").exists()


def test_cli_help_mentions_canonical_workflow() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "codestrata init" in result.output
    assert "codestrata doctor" in result.output
    assert "codestrata assess --repo . --output reports --no-ai" in result.output
    assert "Engineering Assessment" in result.output

    assess_help = runner.invoke(app, ["assess", "--help"])
    assert assess_help.exit_code == 0
    assert "--repo" in assess_help.output
    assert "--config" in assess_help.output
    assert "codestrata.toml" in assess_help.output
    assert "--no-ai" in assess_help.output


def test_readme_documents_canonical_workflow() -> None:
    readme = (ENGINE_ROOT / "README.md").read_text(encoding="utf-8")
    assert "codestrata assess --config codestrata.toml --output reports --with-ai" in readme
    assert "spring-petclinic" not in readme.lower()
    assert "spring petclinic" not in readme.lower()
    assert ".codestrata/workspace/spring-petclinic" not in readme
    assert "ModuleNotFoundError" in readme
    assert "python -m pip install -e " in readme
    assert 'python -c "import codestrata; print(codestrata.__file__)"' in readme
    assert "confirm the active interpreter" in readme
    assert "Amazon Bedrock" in readme or "OpenAI" in readme
    assert "codestrata help" not in readme
    assert "test-fixtures/sample-js-app" in readme
    assert "docs/quick-start.md" in readme


def test_shipped_codestrata_toml_uses_sample_js_not_petclinic() -> None:
    text = (REPO_ROOT / "codestrata.toml").read_text(encoding="utf-8")
    assert "test-fixtures/sample-js-app" in text
    assert "spring-petclinic" not in text
    settings = load_settings(REPO_ROOT / "codestrata.toml")
    assert settings.repository.path == "test-fixtures/sample-js-app"
    assert settings.repository.url is None


def test_cli_assess_config_path_without_repo(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
[repository]
path = "{SAMPLE_JS.as_posix()}"

[static_analysis]
enabled = false
""",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "assess",
            "--config",
            str(config),
            "--output",
            str(output),
            "--no-static-analysis",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Report generated successfully." in result.output
    runs = list(output.glob("*/*"))
    assert runs
    assert (runs[0] / "report.html").is_file()


def test_cli_repo_overrides_config(tmp_path: Path) -> None:
    other = tmp_path / "other-app"
    other.mkdir()
    (other / "package.json").write_text(
        '{"name":"other-app","version":"1.0.0"}',
        encoding="utf-8",
    )
    (other / "index.js").write_text("console.log('hi')\n", encoding="utf-8")

    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
[repository]
path = "{SAMPLE_JS.as_posix()}"

[static_analysis]
enabled = false
""",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "assess",
            "--config",
            str(config),
            "--repo",
            str(other),
            "--output",
            str(output),
            "--no-static-analysis",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "other-app" in result.output


def test_cli_missing_repository_errors_clearly(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
[repository]
url = "https://github.com/example/placeholder.git"

[static_analysis]
enabled = false
""",
        encoding="utf-8",
    )
    # Empty --repo should fall back to url; to force missing, omit both via patch:
    from codestrata.application.assessment import service as assess_service

    original = assess_service.configured_repository_source

    def _none(_settings: CodestrataSettings) -> None:
        return None

    assess_service.configured_repository_source = _none  # type: ignore[assignment]
    try:
        result = runner.invoke(
            app,
            ["assess", "--config", str(config), "--output", str(tmp_path / "out")],
        )
    finally:
        assess_service.configured_repository_source = original

    assert result.exit_code != 0
    assert "No repository configured" in result.output
    assert "--repo" in result.output
