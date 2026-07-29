"""Apply an ActivationPlan onto CodestrataSettings (non-forced packs only)."""

from __future__ import annotations

from typing import Any

from codestrata.application.activation.models import (
    ActivationPlan,
    AssessmentActivationMode,
    ExplicitActivationOverrides,
    PackId,
)
from codestrata.config.settings import CodestrataSettings


def apply_activation_plan(
    settings: CodestrataSettings,
    plan: ActivationPlan,
    *,
    overrides: ExplicitActivationOverrides | None = None,
) -> CodestrataSettings:
    """Return settings with smart-default enablement applied.

    Explicit pack overrides are left untouched. ``custom`` mode leaves pack
    toggles unchanged (only records the activation mode on settings).
    """

    active_overrides = overrides or ExplicitActivationOverrides()
    if plan.mode == AssessmentActivationMode.CUSTOM:
        return settings.model_copy(
            update={
                "assessment": settings.assessment.model_copy(
                    update={"activation": plan.mode}
                )
            }
        )

    payload = settings.model_dump(mode="python")
    for record in plan.packs:
        if active_overrides.pack_override(record.pack_id) is not None:
            continue
        _set_pack_enabled(payload, record.pack_id, record.enabled)

    needs_rules_master = any(
        item.enabled and item.pack_id != PackId.ROADMAP for item in plan.packs
    )
    if active_overrides.rules_master_enabled is None and needs_rules_master:
        payload.setdefault("rules", {})["enabled"] = True

    assessment = payload.setdefault("assessment", {})
    assessment["activation"] = plan.mode.value
    return CodestrataSettings.model_validate(payload)


def _set_pack_enabled(payload: dict[str, Any], pack_id: PackId, enabled: bool) -> None:
    rules = payload.setdefault("rules", {})
    assessment_sections = payload.setdefault("assessment", {}).setdefault("sections", {})
    report_sections = payload.setdefault("report", {}).setdefault("sections", {})
    analysis = payload.setdefault("analysis", {})
    evidence = payload.setdefault("evidence", {})

    if pack_id == PackId.SECURITY:
        rules.setdefault("security", {})["enabled"] = enabled
        assessment_sections.setdefault("security", {})["enabled"] = enabled
        report_sections.setdefault("security", {})["enabled"] = enabled
        evidence.setdefault("repository_sensitive", {})["enabled"] = enabled
    elif pack_id == PackId.DEPENDENCY:
        rules.setdefault("dependency", {})["enabled"] = enabled
        assessment_sections.setdefault("dependency", {})["enabled"] = enabled
        report_sections.setdefault("dependency", {})["enabled"] = enabled
        evidence.setdefault("dependency", {})["enabled"] = enabled
    elif pack_id == PackId.ARCHITECTURE:
        rules.setdefault("architecture", {})["enabled"] = enabled
        assessment_sections.setdefault("architecture", {})["enabled"] = enabled
        report_sections.setdefault("architecture", {})["enabled"] = enabled
        analysis.setdefault("architecture_conclusions", {})["enabled"] = enabled
        if enabled:
            evidence.setdefault("language", {})["enabled"] = True
    elif pack_id == PackId.TECHNICAL_DEBT:
        rules.setdefault("technical_debt", {})["enabled"] = enabled
        assessment_sections.setdefault("technical_debt", {})["enabled"] = enabled
        report_sections.setdefault("technical_debt", {})["enabled"] = enabled
        if enabled:
            evidence.setdefault("language", {})["enabled"] = True
            evidence.setdefault("complexity", {})["enabled"] = True
    elif pack_id == PackId.TESTING:
        rules.setdefault("testing", {})["enabled"] = enabled
        assessment_sections.setdefault("testing", {})["enabled"] = enabled
        report_sections.setdefault("testing", {})["enabled"] = enabled
        evidence.setdefault("repository_testing", {})["enabled"] = enabled
    elif pack_id == PackId.CLOUD:
        rules.setdefault("cloud", {})["enabled"] = enabled
        analysis.setdefault("cloud", {})["enabled"] = enabled
        report_sections.setdefault("cloud", {})["enabled"] = enabled
        evidence.setdefault("repository_cloud", {})["enabled"] = enabled
    elif pack_id == PackId.AI_READINESS:
        rules.setdefault("ai_readiness", {})["enabled"] = enabled
        analysis.setdefault("ai_readiness", {})["enabled"] = enabled
        report_sections.setdefault("ai_readiness", {})["enabled"] = enabled
        evidence.setdefault("repository_ai_readiness", {})["enabled"] = enabled
    elif pack_id == PackId.PERFORMANCE:
        rules.setdefault("performance", {})["enabled"] = enabled
        analysis.setdefault("performance", {})["enabled"] = enabled
        report_sections.setdefault("performance", {})["enabled"] = enabled
        evidence.setdefault("repository_performance", {})["enabled"] = enabled
    elif pack_id == PackId.ROADMAP:
        report_sections.setdefault("roadmap", {})["enabled"] = enabled


__all__ = ["apply_activation_plan"]
