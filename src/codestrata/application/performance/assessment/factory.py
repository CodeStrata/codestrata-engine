"""Performance assessment factory and enablement helpers (Phase 4.9.1)."""

from __future__ import annotations

from codestrata.application.performance.assessment.assembler import PerformanceAssessmentAssembler
from codestrata.config.settings import CodestrataSettings, PerformanceAnalysisSettings


def create_performance_assessment_assembler() -> PerformanceAssessmentAssembler:
    return PerformanceAssessmentAssembler()


def performance_pack_enabled(settings: CodestrataSettings | None) -> bool:
    """Rule pack gate: ``[rules].enabled`` and ``[rules.performance].enabled``."""

    if settings is None:
        return False
    return bool(settings.rules.enabled and settings.rules.performance.enabled)


def performance_analysis_enabled(settings: CodestrataSettings | None) -> bool:
    """Primary write gate: ``[analysis.performance].enabled``."""

    if settings is None:
        return False
    return bool(settings.analysis.performance.enabled)


def performance_report_section_enabled(settings: CodestrataSettings | None) -> bool:
    """Report presentation gate: ``[report.sections.performance].enabled``."""

    if settings is None:
        return False
    return bool(settings.report.sections.performance.enabled)


def performance_analysis_settings(
    settings: CodestrataSettings | None,
) -> PerformanceAnalysisSettings:
    if settings is None:
        return PerformanceAnalysisSettings()
    return settings.analysis.performance


def configuration_fingerprint_payload(
    settings: CodestrataSettings | None,
    *,
    pack_enabled: bool,
) -> str:
    section = performance_analysis_settings(settings)
    return (
        f"enabled={section.enabled}|"
        f"pack_enabled={pack_enabled}|"
        f"include_findings={section.include_findings}|"
        f"include_coverage={section.include_coverage}|"
        f"include_limitations={section.include_limitations}|"
        f"include_traceability={section.include_traceability}|"
        f"include_execution_summary={section.include_execution_summary}|"
        f"include_synthesis={section.include_synthesis}"
    )
