"""Tests for CodeStrata configuration loading."""

from pathlib import Path

import pytest

from codestrata.config import load_settings


def test_load_settings_reads_repository_configuration(
    tmp_path: Path,
) -> None:
    """Configuration loader should parse repository settings."""

    config_file = tmp_path / "codestrata.toml"

    config_file.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-java-app.git"
        branch = "main"

        [workspace]
        directory = ".codestrata-workspace"
        clean_before_clone = true
        """,
        encoding="utf-8",
    )

    settings = load_settings(config_file)

    assert str(settings.repository.url) == ("https://github.com/example/sample-java-app.git")
    assert settings.repository.branch == "main"
    assert settings.workspace.directory == Path(".codestrata-workspace")
    assert settings.workspace.clean_before_clone is True


def test_load_settings_uses_workspace_defaults(
    tmp_path: Path,
) -> None:
    """Workspace settings should be optional."""

    config_file = tmp_path / "codestrata.toml"

    config_file.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-php-app.git"
        """,
        encoding="utf-8",
    )

    settings = load_settings(config_file)

    assert settings.repository.branch is None
    assert settings.workspace.directory == Path(".codestrata-workspace")
    assert settings.workspace.clean_before_clone is True


def test_load_settings_reads_static_analysis_configuration(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-java-app.git"

        [static_analysis]
        enabled = true
        fail_on_provider_error = false

        [static_analysis.pmd]
        enabled = true
        executable = "pmd"
        minimum_priority = 4
        timeout_seconds = 60
        """,
        encoding="utf-8",
    )

    settings = load_settings(config_file)

    assert settings.static_analysis.enabled is True
    assert settings.static_analysis.pmd.minimum_priority == 4
    assert settings.static_analysis.pmd.timeout_seconds == 60


def test_load_settings_accepts_local_repository_path(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.repository.path == "test-fixtures/sample-js-app"
    assert settings.repository.url is None


def test_load_settings_rejects_empty_repository_section(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        branch = "main"
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Configure repository"):
        load_settings(config_file)


def test_load_settings_uses_knowledge_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-php-app.git"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.knowledge.directory == Path(".codestrata/knowledge")


def test_load_settings_reads_knowledge_directory(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"

        [knowledge]
        directory = ".codestrata/custom-knowledge"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.knowledge.directory == Path(".codestrata/custom-knowledge")


def test_load_settings_reads_mcp_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.mcp.enabled is False
    assert settings.mcp.transport == "stdio"


def test_load_settings_reads_mcp_section(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"

        [mcp]
        enabled = true
        transport = "stdio"
        log_level = "DEBUG"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.mcp.log_level == "DEBUG"


def test_language_evidence_pipeline_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.evidence.language.enabled is False
    assert settings.evidence.language.providers.auto_detect is True
    assert settings.evidence.language.python.enabled is True


def test_complexity_evidence_enabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.evidence.complexity.enabled is True
    assert settings.evidence.complexity.python.enabled is True
    assert settings.evidence.complexity.java.enabled is True
    assert "/.codestrata/" in settings.evidence.complexity.ignore_path_markers


def test_architecture_conclusions_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.analysis.architecture_conclusions.enabled is False
    policies = settings.analysis.architecture_conclusions.policies
    assert policies.positive_boundary_conformance is False


def test_assessment_activation_defaults_to_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.assessment.activation == "default"


def test_assessment_activation_accepts_known_modes(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [assessment]
        activation = "minimal"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.assessment.activation == "minimal"


def test_architecture_assessment_section_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.assessment.sections.architecture.enabled is False
    assert settings.assessment.sections.architecture.include_findings is True
    assert settings.assessment.sections.architecture.include_conclusions is True


def test_architecture_report_section_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.report.sections.architecture.enabled is False
    assert settings.report.sections.architecture.include_executive_summary is True


def test_technical_debt_gates_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.technical_debt.enabled is False
    assert settings.assessment.sections.technical_debt.enabled is False
    assert settings.assessment.sections.technical_debt.include_findings is True
    assert settings.report.sections.technical_debt.enabled is False
    assert settings.report.sections.technical_debt.include_executive_summary is True
    assert settings.rules.dependency.enabled is False
    assert settings.assessment.sections.dependency.enabled is False
    assert settings.report.sections.dependency.enabled is False
    assert settings.report.sections.dependency.include_executive_summary is True


def test_dependency_gates_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.dependency.enabled is False
    assert settings.rules.dependency.unresolved_version.enabled is True
    assert settings.rules.dependency.mutable_version.enabled is True
    assert settings.rules.dependency.unbounded_requirement.enabled is True
    assert settings.rules.dependency.conflicting_exact_versions.enabled is True
    assert settings.rules.dependency.duplicate_declaration.enabled is True
    assert settings.assessment.sections.dependency.enabled is False
    assert settings.assessment.sections.dependency.include_findings is True
    assert settings.assessment.sections.dependency.include_synthesis is True
    assert settings.report.sections.dependency.enabled is False
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False


def test_security_gates_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False
    assert settings.assessment.sections.security.include_findings is True
    assert settings.assessment.sections.security.include_synthesis is True
    assert settings.report.sections.security.enabled is False
    assert settings.rules.testing.enabled is False
    assert settings.assessment.sections.testing.enabled is False


def test_cloud_gates_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.analysis.cloud.enabled is False
    assert settings.analysis.cloud.include_findings is True
    assert settings.analysis.cloud.include_coverage is True
    assert settings.report.sections.cloud.enabled is False
    assert settings.report.sections.cloud.include_findings is True
    assert settings.report.sections.cloud.include_inventory is True
    assert settings.report.sections.cloud.include_themes is True
    assert settings.evidence.repository_cloud.enabled is False
    assert settings.evidence.repository_ai_readiness.enabled is False
    assert settings.evidence.repository_performance.enabled is False
    assert settings.rules.cloud.enabled is False
    assert settings.rules.ai_readiness.enabled is False
    assert settings.rules.performance.enabled is False
    assert settings.rules.testing.enabled is False
    assert settings.assessment.sections.testing.enabled is False
    assert settings.report.sections.testing.enabled is False
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.report.sections.ai_readiness.enabled is False
    assert settings.report.sections.ai_readiness.include_inventory is True
    assert settings.report.sections.ai_readiness.include_themes is True
    assert settings.report.sections.ai_readiness.include_execution_summary is True
    assert settings.analysis.performance.enabled is False
    assert settings.analysis.performance.include_findings is True
    assert settings.analysis.performance.include_synthesis is True
    assert settings.report.sections.performance.enabled is False
    assert settings.report.sections.performance.include_inventory is True
    assert settings.report.sections.performance.include_themes is True
    assert settings.report.sections.performance.include_execution_summary is True
    assert settings.report.sections.roadmap.enabled is False
    assert settings.report.sections.roadmap.include_assumptions is True
    assert settings.report.sections.roadmap.include_limitations is True
    assert settings.report.sections.roadmap.include_evidence is True


def test_performance_gates_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [analysis.performance]
        enabled = true
        include_limitations = false
        include_synthesis = true

        [report.sections.performance]
        enabled = true
        include_diagnostics = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.analysis.performance.enabled is True
    assert settings.analysis.performance.include_limitations is False
    assert settings.analysis.performance.include_synthesis is True
    assert settings.report.sections.performance.enabled is True
    assert settings.report.sections.performance.include_diagnostics is False
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.analysis.cloud.enabled is False


def test_ai_readiness_gates_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [analysis.ai_readiness]
        enabled = true
        include_limitations = false

        [evidence.repository_ai_readiness]
        enabled = true
        max_files = 250

        [report.sections.ai_readiness]
        enabled = true
        include_diagnostics = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.analysis.ai_readiness.enabled is True
    assert settings.analysis.ai_readiness.include_limitations is False
    assert settings.evidence.repository_ai_readiness.enabled is True
    assert settings.evidence.repository_ai_readiness.max_files == 250
    assert settings.report.sections.ai_readiness.enabled is True
    assert settings.report.sections.ai_readiness.include_diagnostics is False
    assert settings.analysis.cloud.enabled is False
    assert settings.rules.ai_readiness.enabled is False


def test_ai_readiness_rules_gate_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.ai_readiness]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.enabled is True
    assert settings.rules.ai_readiness.enabled is True
    assert settings.rules.ai_readiness.ai_001.enabled is True
    assert settings.analysis.ai_readiness.enabled is False


def test_performance_rules_gate_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.performance]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.enabled is True
    assert settings.rules.performance.enabled is True
    assert settings.rules.performance.perf_001.enabled is True
    assert settings.analysis.performance.enabled is False


def test_repository_ai_readiness_evidence_enablement_independent(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [evidence.repository_ai_readiness]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.evidence.repository_ai_readiness.enabled is True
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.report.sections.ai_readiness.enabled is False


def test_repository_performance_evidence_enablement_independent(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [evidence.repository_performance]
        enabled = true
        max_files = 250
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.evidence.repository_performance.enabled is True
    assert settings.evidence.repository_performance.max_files == 250
    assert settings.analysis.performance.enabled is False
    assert settings.report.sections.performance.enabled is False


def test_cloud_gates_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [analysis.cloud]
        enabled = true
        include_limitations = false

        [evidence.repository_cloud]
        enabled = true
        max_files = 250

        [rules]
        enabled = true

        [rules.cloud]
        enabled = true

        [report.sections.cloud]
        enabled = true
        include_diagnostics = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.analysis.cloud.enabled is True
    assert settings.analysis.cloud.include_limitations is False
    assert settings.evidence.repository_cloud.enabled is True
    assert settings.evidence.repository_cloud.max_files == 250
    assert settings.rules.enabled is True
    assert settings.rules.cloud.enabled is True
    assert settings.rules.cloud.cloud_001.enabled is True
    assert settings.report.sections.cloud.enabled is True
    assert settings.report.sections.cloud.include_diagnostics is False
    assert settings.assessment.sections.testing.enabled is False
    assert settings.report.sections.testing.enabled is False


def test_testing_gates_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.testing.enabled is False
    assert settings.assessment.sections.testing.enabled is False
    assert settings.assessment.sections.testing.include_findings is True
    assert settings.assessment.sections.testing.include_synthesis is True
    assert settings.report.sections.testing.enabled is False
    assert settings.report.sections.testing.include_inventory is True
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False


def test_testing_gates_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.testing]
        enabled = true

        [assessment.sections.testing]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.testing.enabled is True
    assert settings.assessment.sections.testing.enabled is True
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False
    assert settings.report.sections.security.enabled is False
    assert settings.report.sections.testing.enabled is False


def test_testing_report_gate_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [report.sections.testing]
        enabled = true
        include_themes = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.report.sections.testing.enabled is True
    assert settings.report.sections.testing.include_themes is False
    assert settings.report.sections.security.enabled is False


def test_security_gates_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.security]
        enabled = true

        [assessment.sections.security]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.security.enabled is True
    assert settings.assessment.sections.security.enabled is True
    assert settings.report.sections.security.enabled is False
    assert settings.rules.dependency.enabled is False
    assert settings.assessment.sections.dependency.enabled is False
    assert settings.rules.architecture.enabled is False
    assert settings.rules.technical_debt.enabled is False


def test_security_report_section_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [report.sections.security]
        enabled = true
        include_hotspots = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.report.sections.security.enabled is True
    assert settings.report.sections.security.include_hotspots is False
    assert settings.report.sections.security.include_themes is True
    assert settings.report.sections.dependency.enabled is False
    assert settings.assessment.sections.security.enabled is False


def test_dependency_gates_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.dependency]
        enabled = true

        [assessment.sections.dependency]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.rules.dependency.enabled is True
    assert settings.assessment.sections.dependency.enabled is True
    # Backward compatible: existing packs unchanged by dependency enablement.
    assert settings.rules.technical_debt.enabled is False
    assert settings.assessment.sections.technical_debt.enabled is False


def test_technical_debt_report_section_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [report.sections.technical_debt]
        enabled = true
        include_hotspots = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.report.sections.technical_debt.enabled is True
    assert settings.report.sections.technical_debt.include_hotspots is False
    assert settings.report.sections.technical_debt.include_themes is True


def test_extensions_default_to_empty_analyzer_allowlist(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.extensions.analyzers.enabled == []
    assert settings.extensions.renderers.enabled == []
    assert settings.extensions.cli.disabled == []
    assert settings.extensions.mcp.disabled == []


def test_extensions_analyzers_allowlist_loads(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [extensions.analyzers]
        enabled = ["com.example.license_scan"]
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.extensions.analyzers.enabled == ["com.example.license_scan"]


def test_blank_bedrock_answer_model_is_treated_as_unset(tmp_path: Path) -> None:
    """Blank ai.bedrock.answer_model must load as empty string (not None)."""

    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [ai.bedrock]
        answer_model = ""
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.ai.bedrock.answer_model == ""
    assert isinstance(settings.ai.bedrock.answer_model, str)
