"""Bounded assessment analytics diagnostics (Epic 10 Slice 10.4).

Counters and categorical codes only — never installation IDs, paths, payloads,
or head name lists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.assessment_analytics_policy import (
    COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class AssessmentAnalyticsDiagnostics:
    """Safe assessment-analytics diagnostics."""

    policy_version: str
    schema_version: str
    local_collection_allowed: bool
    persistence_enabled: bool
    transmission_enabled: bool
    installation_id_required: bool
    installation_id_present: bool
    privacy_projection_applied: bool
    command_category: str | None
    outcome: str | None
    duration_bucket: str | None
    failure_category: str | None
    enabled_head_count: int
    events_collected: int
    events_projected: int
    events_validated: int
    events_rejected: int
    last_error_code: str | None
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "command_category": self.command_category,
            "duration_bucket": self.duration_bucket,
            "enabled_head_count": self.enabled_head_count,
            "events_collected": self.events_collected,
            "events_projected": self.events_projected,
            "events_rejected": self.events_rejected,
            "events_validated": self.events_validated,
            "failure_category": self.failure_category,
            "installation_id_present": self.installation_id_present,
            "installation_id_required": self.installation_id_required,
            "last_error_code": self.last_error_code,
            "limitation_codes": list(self.limitation_codes),
            "local_collection_allowed": self.local_collection_allowed,
            "outcome": self.outcome,
            "persistence_enabled": self.persistence_enabled,
            "policy_version": self.policy_version,
            "privacy_projection_applied": self.privacy_projection_applied,
            "schema_version": self.schema_version,
            "transmission_enabled": self.transmission_enabled,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def empty_assessment_analytics_diagnostics(
    *,
    limitation_codes: tuple[str, ...] = (),
) -> AssessmentAnalyticsDiagnostics:
    return AssessmentAnalyticsDiagnostics(
        policy_version=COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION,
        schema_version=COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION,
        local_collection_allowed=True,
        persistence_enabled=False,
        transmission_enabled=False,
        installation_id_required=True,
        installation_id_present=False,
        privacy_projection_applied=False,
        command_category=None,
        outcome=None,
        duration_bucket=None,
        failure_category=None,
        enabled_head_count=0,
        events_collected=0,
        events_projected=0,
        events_validated=0,
        events_rejected=0,
        last_error_code=None,
        limitation_codes=tuple(sorted(set(limitation_codes))),
    )


def assessment_analytics_diagnostics_for_event(
    *,
    installation_id_present: bool,
    privacy_projection_applied: bool,
    command_category: str | None,
    outcome: str | None,
    duration_bucket: str | None,
    failure_category: str | None,
    enabled_head_count: int,
    projected: bool,
    validated: bool,
    rejected: bool,
    last_error_code: str | None = None,
    limitation_codes: tuple[str, ...] = (),
) -> AssessmentAnalyticsDiagnostics:
    base = empty_assessment_analytics_diagnostics(limitation_codes=limitation_codes)
    return AssessmentAnalyticsDiagnostics(
        policy_version=base.policy_version,
        schema_version=base.schema_version,
        local_collection_allowed=True,
        persistence_enabled=False,
        transmission_enabled=False,
        installation_id_required=True,
        installation_id_present=installation_id_present,
        privacy_projection_applied=privacy_projection_applied,
        command_category=command_category,
        outcome=outcome,
        duration_bucket=duration_bucket,
        failure_category=failure_category,
        enabled_head_count=enabled_head_count,
        events_collected=1 if installation_id_present else 0,
        events_projected=1 if projected else 0,
        events_validated=1 if validated else 0,
        events_rejected=1 if rejected else 0,
        last_error_code=last_error_code,
        limitation_codes=base.limitation_codes,
    )


__all__ = [
    "AssessmentAnalyticsDiagnostics",
    "assessment_analytics_diagnostics_for_event",
    "empty_assessment_analytics_diagnostics",
]
