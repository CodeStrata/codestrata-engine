"""CLI mapping for Shared Rule Platform."""

from __future__ import annotations

from typing import Any

from codestrata.application.rules.models import RuleExplanation, RuleInspectionView


def map_rule_view(view: RuleInspectionView) -> dict[str, Any]:
    meta = view.metadata
    return {
        "rule_id": str(meta.rule_id),
        "version": str(meta.version),
        "title": meta.title,
        "description": meta.description,
        "category": meta.category.value,
        "default_severity": meta.default_severity.value,
        "supported_languages": list(meta.supported_languages),
        "enabled_by_default": meta.enabled_by_default,
        "experimental": meta.experimental,
        "requires_enterprise_context": meta.requires_enterprise_context,
        "production": view.production,
    }


def map_explanation(item: RuleExplanation) -> dict[str, Any]:
    return {
        "subject": item.subject,
        "reason_code": item.reason_code,
        "message": item.message,
        "details": dict(item.details),
    }
