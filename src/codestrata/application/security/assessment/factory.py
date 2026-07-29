"""Security assessment factory and enablement helpers (Phase 4.5.1)."""

from __future__ import annotations

from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.config.settings import CodestrataSettings, SecurityAssessmentSectionSettings


def create_security_assessment_assembler() -> SecurityAssessmentAssembler:
    return SecurityAssessmentAssembler()


def security_assessment_section_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.assessment.sections.security.enabled)


def security_pack_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.rules.enabled and settings.rules.security.enabled)


def security_assessment_section_settings(
    settings: CodestrataSettings | None,
) -> SecurityAssessmentSectionSettings:
    if settings is None:
        return SecurityAssessmentSectionSettings()
    return settings.assessment.sections.security


def configuration_fingerprint_payload(
    settings: CodestrataSettings | None,
    *,
    pack_enabled: bool,
) -> str:
    section = security_assessment_section_settings(settings)
    return (
        f"section_enabled={section.enabled}|"
        f"include_findings={section.include_findings}|"
        f"include_coverage={section.include_coverage}|"
        f"include_limitations={section.include_limitations}|"
        f"include_traceability={section.include_traceability}|"
        f"include_execution_summary={section.include_execution_summary}|"
        f"include_synthesis={section.include_synthesis}|"
        f"pack_enabled={pack_enabled}"
    )
