"""Technical debt assessment factory and enablement helpers (Phase 4.3.1)."""

from __future__ import annotations

from codestrata.application.technical_debt.assessment.assembler import (
    TechnicalDebtAssessmentAssembler,
)
from codestrata.config.settings import CodestrataSettings, TechnicalDebtAssessmentSectionSettings


def create_technical_debt_assessment_assembler() -> TechnicalDebtAssessmentAssembler:
    return TechnicalDebtAssessmentAssembler()


def technical_debt_assessment_section_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.assessment.sections.technical_debt.enabled)


def technical_debt_pack_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.rules.enabled and settings.rules.technical_debt.enabled)


def technical_debt_assessment_section_settings(
    settings: CodestrataSettings | None,
) -> TechnicalDebtAssessmentSectionSettings:
    if settings is None:
        return TechnicalDebtAssessmentSectionSettings()
    return settings.assessment.sections.technical_debt


def configuration_fingerprint_payload(
    settings: CodestrataSettings | None,
    *,
    pack_enabled: bool,
) -> str:
    section = technical_debt_assessment_section_settings(settings)
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
