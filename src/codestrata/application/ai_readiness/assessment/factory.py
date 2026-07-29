"""AI Readiness assessment factory and enablement helpers (Phase 4.8.5)."""

from __future__ import annotations

from codestrata.application.ai_readiness.assessment.assembler import AiReadinessAssessmentAssembler
from codestrata.config.settings import AiReadinessAnalysisSettings, CodestrataSettings


def create_ai_readiness_assessment_assembler() -> AiReadinessAssessmentAssembler:
    return AiReadinessAssessmentAssembler()


def ai_readiness_pack_enabled(settings: CodestrataSettings | None) -> bool:
    """Rule pack gate: ``[rules].enabled`` and ``[rules.ai_readiness].enabled``."""

    if settings is None:
        return False
    return bool(settings.rules.enabled and settings.rules.ai_readiness.enabled)


def ai_readiness_analysis_enabled(settings: CodestrataSettings | None) -> bool:
    """Primary write gate: ``[analysis.ai_readiness].enabled``."""

    if settings is None:
        return False
    return bool(settings.analysis.ai_readiness.enabled)


def ai_readiness_report_section_enabled(settings: CodestrataSettings | None) -> bool:
    """Report presentation gate: ``[report.sections.ai_readiness].enabled``."""

    if settings is None:
        return False
    return bool(settings.report.sections.ai_readiness.enabled)


def ai_readiness_analysis_settings(
    settings: CodestrataSettings | None,
) -> AiReadinessAnalysisSettings:
    if settings is None:
        return AiReadinessAnalysisSettings()
    return settings.analysis.ai_readiness


def configuration_fingerprint_payload(
    settings: CodestrataSettings | None,
    *,
    pack_enabled: bool,
) -> str:
    section = ai_readiness_analysis_settings(settings)
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
