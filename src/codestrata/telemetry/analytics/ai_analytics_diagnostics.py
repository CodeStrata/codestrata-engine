"""AI analytics diagnostics (Epic 10 Slice 10.6).

Never includes installation IDs, raw provider/model values, prompts, or payloads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.ai_analytics_catalogs import (
    AI_ANALYTICS_CAPABILITY_CATALOG_VERSION,
    AI_ANALYTICS_MODEL_FAMILY_CATALOG_VERSION,
    AI_ANALYTICS_PROVIDER_FAMILY_CATALOG_VERSION,
)
from codestrata.telemetry.analytics.ai_analytics_policy import (
    COMMUNITY_AI_ANALYTICS_POLICY_VERSION,
    COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class AIAnalyticsDiagnostics:
    """Process-local AI analytics counters (unpersisted)."""

    policy_version: str = COMMUNITY_AI_ANALYTICS_POLICY_VERSION
    schema_version: str = COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION
    capability_catalog_version: str = AI_ANALYTICS_CAPABILITY_CATALOG_VERSION
    provider_family_catalog_version: str = AI_ANALYTICS_PROVIDER_FAMILY_CATALOG_VERSION
    model_family_catalog_version: str = AI_ANALYTICS_MODEL_FAMILY_CATALOG_VERSION
    attempts: int = 0
    projected: int = 0
    rejected: int = 0
    capability_category: str | None = None
    provider_family_category: str | None = None
    model_family_category: str | None = None
    ownership_category: str | None = None
    outcome_category: str | None = None
    duration_bucket_present: bool = False
    ai_used_present: bool = False
    limitation_codes: tuple[str, ...] = ()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "ai_used_present": self.ai_used_present,
            "attempts": self.attempts,
            "capability_catalog_version": self.capability_catalog_version,
            "capability_category": self.capability_category,
            "duration_bucket_present": self.duration_bucket_present,
            "limitation_codes": list(self.limitation_codes),
            "model_family_catalog_version": self.model_family_catalog_version,
            "model_family_category": self.model_family_category,
            "outcome_category": self.outcome_category,
            "ownership_category": self.ownership_category,
            "policy_version": self.policy_version,
            "projected": self.projected,
            "provider_family_catalog_version": self.provider_family_catalog_version,
            "provider_family_category": self.provider_family_category,
            "rejected": self.rejected,
            "schema_version": self.schema_version,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )


def empty_ai_analytics_diagnostics() -> AIAnalyticsDiagnostics:
    return AIAnalyticsDiagnostics()


__all__ = [
    "AIAnalyticsDiagnostics",
    "empty_ai_analytics_diagnostics",
]
