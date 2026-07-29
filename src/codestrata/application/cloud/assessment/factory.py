"""Cloud assessment factory and enablement helpers (Phase 4.7.1)."""

from __future__ import annotations

from codestrata.application.cloud.assessment.assembler import CloudAssessmentAssembler
from codestrata.config.settings import CloudAnalysisSettings, CodestrataSettings


def create_cloud_assessment_assembler() -> CloudAssessmentAssembler:
    return CloudAssessmentAssembler()


def cloud_pack_enabled(settings: CodestrataSettings | None) -> bool:
    """Rule pack gate: ``[rules].enabled`` and ``[rules.cloud].enabled``."""

    if settings is None:
        return False
    return bool(settings.rules.enabled and settings.rules.cloud.enabled)


def cloud_analysis_enabled(settings: CodestrataSettings | None) -> bool:
    """Primary write gate: ``[analysis.cloud].enabled``."""

    if settings is None:
        return False
    return bool(settings.analysis.cloud.enabled)


def cloud_report_section_enabled(settings: CodestrataSettings | None) -> bool:
    """Report presentation gate: ``[report.sections.cloud].enabled``."""

    if settings is None:
        return False
    return bool(settings.report.sections.cloud.enabled)


def cloud_analysis_settings(
    settings: CodestrataSettings | None,
) -> CloudAnalysisSettings:
    if settings is None:
        return CloudAnalysisSettings()
    return settings.analysis.cloud


def configuration_fingerprint_payload(
    settings: CodestrataSettings | None,
    *,
    pack_enabled: bool,
) -> str:
    section = cloud_analysis_settings(settings)
    return (
        f"analysis_enabled={section.enabled}|"
        f"include_findings={section.include_findings}|"
        f"include_coverage={section.include_coverage}|"
        f"include_limitations={section.include_limitations}|"
        f"include_traceability={section.include_traceability}|"
        f"include_execution_summary={section.include_execution_summary}|"
        f"include_synthesis={section.include_synthesis}|"
        f"pack_enabled={pack_enabled}"
    )
