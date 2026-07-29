"""Tests for Phase 6.5 extension architecture."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.ai.providers.factory import (
    SUPPORTED_ASSESS_AI_PROVIDERS,
    create_assess_ai_provider,
    supported_assess_ai_providers,
)
from codestrata.cli import app
from codestrata.cli.doctor import run_doctor_checks
from codestrata.config.settings import CodestrataSettings
from codestrata.extensions.analyzers import (
    discover_analyzer_extensions,
    resolve_enabled_analyzers,
)
from codestrata.extensions.assess_ai import (
    AssessAIProviderRegistry,
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)
from codestrata.extensions.contracts import AnalyzerExtension, ReportRenderer
from codestrata.extensions.namespaces import (
    RESERVED_EXTENSION_NAMESPACES,
    assert_third_party_analyzer_id,
    is_reserved_analyzer_id,
)
from codestrata.extensions.renderers import (
    HtmlCustomerReportRenderer,
    get_report_renderer_registry,
    reset_report_renderer_registry_for_tests,
)
from codestrata.extensions.version import (
    EXTENSION_API_VERSION,
    extension_api_compatible,
)
from codestrata.models import AnalyzerResult, Repository, Technology
from codestrata.package_metadata import format_version_details
from codestrata.services.default_pipeline import builtin_analyzers, create_default_analysis_service

runner = CliRunner()


def test_extension_api_version_is_semver() -> None:
    assert EXTENSION_API_VERSION.count(".") == 2
    assert extension_api_compatible("1.0.0")
    assert extension_api_compatible("1.9.9")
    assert not extension_api_compatible("2.0.0")
    assert not extension_api_compatible("not-a-version")


def test_reserved_namespaces_documented() -> None:
    assert "codestrata." in RESERVED_EXTENSION_NAMESPACES
    assert is_reserved_analyzer_id("codestrata.custom")
    with pytest.raises(ValueError, match="reserved"):
        assert_third_party_analyzer_id("codestrata.evil")


def test_assess_ai_registry_includes_builtins() -> None:
    reset_assess_ai_provider_registry_for_tests()
    registry = get_assess_ai_provider_registry()
    assert set(registry.list_providers()) >= set(SUPPORTED_ASSESS_AI_PROVIDERS)
    assert supported_assess_ai_providers() >= SUPPORTED_ASSESS_AI_PROVIDERS

    settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "openai"}}
    )
    provider = create_assess_ai_provider(settings)
    assert provider.__class__.__name__ == "OpenAIAIModelProvider"


def test_assess_ai_registry_rejects_unknown() -> None:
    reset_assess_ai_provider_registry_for_tests()
    settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "not-real"}}
    )
    with pytest.raises(Exception, match="Unsupported assess AI provider"):
        create_assess_ai_provider(settings)


def test_assess_ai_registry_rejects_incompatible_api() -> None:
    registry = AssessAIProviderRegistry()

    def _factory(_settings: CodestrataSettings):  # type: ignore[no-untyped-def]
        raise AssertionError("should not create")

    with pytest.raises(ValueError, match="incompatible"):
        registry.register("custom", _factory, api_version="9.0.0")


def test_empty_analyzer_allowlist_loads_nothing() -> None:
    loaded, issues = discover_analyzer_extensions(enabled=[])
    assert loaded == []
    assert issues == []
    assert resolve_enabled_analyzers([]) == []


def test_unknown_enabled_analyzer_strict_raises() -> None:
    with pytest.raises(ValueError, match="not found"):
        resolve_enabled_analyzers(["com.example.missing_analyzer"], strict=True)


def test_default_pipeline_builtins_only_without_extensions(tmp_path: Path) -> None:
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": str(tmp_path)},
            "extensions": {"analyzers": {"enabled": []}},
        }
    )
    service = create_default_analysis_service(settings)
    composite = service._analyzer  # noqa: SLF001 - test inspects wiring
    assert len(composite._analyzers) == len(builtin_analyzers())  # noqa: SLF001


def test_html_renderer_implements_report_renderer_protocol() -> None:
    reset_report_renderer_registry_for_tests()
    registry = get_report_renderer_registry()
    assert "html" in registry.list_ids()
    renderer = HtmlCustomerReportRenderer()
    assert renderer.id == "html"
    assert renderer.media_type == "text/html"
    assert renderer.api_version == EXTENSION_API_VERSION
    assert isinstance(renderer, ReportRenderer)


def test_extensions_list_command() -> None:
    result = runner.invoke(app, ["extensions", "list"])
    assert result.exit_code == 0
    assert "Extension API:" in result.stdout
    assert "assess_ai/bedrock" in result.stdout
    assert "renderer/html" in result.stdout

    json_result = runner.invoke(app, ["extensions", "list", "--json"])
    assert json_result.exit_code == 0
    payload = json.loads(json_result.stdout)
    assert payload["extension_api_version"] == EXTENSION_API_VERSION
    assert "reserved_namespaces" in payload


def test_doctor_extensions_flag(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
[repository]
path = "{tmp_path}"

[extensions.analyzers]
enabled = ["com.example.not_installed"]
""",
        encoding="utf-8",
    )
    checks = run_doctor_checks(
        config_path=config,
        output_directory=tmp_path / "reports",
        include_extensions=True,
    )
    assert any(not check.ok and "not_installed" in check.name for check in checks)

    result = runner.invoke(
        app,
        ["doctor", "--config", str(config), "--output", str(tmp_path / "reports"), "--extensions"],
    )
    assert result.exit_code == 1
    assert "FAIL" in result.stdout


def test_version_includes_extension_api() -> None:
    text = format_version_details()
    assert f"Extension API: {EXTENSION_API_VERSION}" in text


class _StubAnalyzer:
    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts=None,  # noqa: ANN001
    ) -> AnalyzerResult:
        del repository, technologies, facts
        return AnalyzerResult(findings=[], facts=None)


class _StubExtension:
    id = "com.example.stub"
    api_version = EXTENSION_API_VERSION

    def create(self) -> _StubAnalyzer:
        return _StubAnalyzer()


def test_analyzer_extension_protocol_shape() -> None:
    extension: AnalyzerExtension = _StubExtension()
    assert extension.id == "com.example.stub"
    assert isinstance(extension.create(), _StubAnalyzer)
