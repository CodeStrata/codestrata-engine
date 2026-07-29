"""Architecture assessment integration factory and enablement helpers."""

from __future__ import annotations

from codestrata.application.architecture.assessment.assembler import ArchitectureAssessmentAssembler
from codestrata.config.settings import ArchitectureAssessmentSectionSettings, CodestrataSettings


def create_architecture_assessment_assembler() -> ArchitectureAssessmentAssembler:
    return ArchitectureAssessmentAssembler()


def architecture_assessment_section_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.assessment.sections.architecture.enabled)


def architecture_assessment_section_settings(
    settings: CodestrataSettings | None,
) -> ArchitectureAssessmentSectionSettings:
    if settings is None:
        return ArchitectureAssessmentSectionSettings()
    return settings.assessment.sections.architecture


def configuration_fingerprint_payload(
    settings: CodestrataSettings | None,
    *,
    pack_enabled: bool,
    conclusions_enabled: bool,
) -> str:
    section = architecture_assessment_section_settings(settings)
    return (
        f"section_enabled={section.enabled}|"
        f"include_findings={section.include_findings}|"
        f"include_conclusions={section.include_conclusions}|"
        f"include_recommendation_groups={section.include_recommendation_groups}|"
        f"include_coverage={section.include_coverage}|"
        f"include_limitations={section.include_limitations}|"
        f"include_traceability={section.include_traceability}|"
        f"include_execution_summary={section.include_execution_summary}|"
        f"pack_enabled={pack_enabled}|conclusions_enabled={conclusions_enabled}"
    )
