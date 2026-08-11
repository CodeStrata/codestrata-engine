"""Bounded repository aggregate analytics diagnostics (Epic 10 Slice 10.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.repository_aggregate_policy import (
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION,
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class RepositoryAggregateAnalyticsDiagnostics:
    policy_version: str
    schema_version: str
    local_collection_allowed: bool
    persistence_enabled: bool
    transmission_enabled: bool
    installation_id_required: bool
    installation_id_present: bool
    privacy_projection_applied: bool
    language_group_count: int
    total_language_files: int
    rule_attempted: int
    rule_completed: int
    rule_skipped: int
    rule_failed: int
    head_group_count: int
    events_collected: int
    events_projected: int
    events_validated: int
    events_rejected: int
    last_error_code: str | None
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "events_collected": self.events_collected,
            "events_projected": self.events_projected,
            "events_rejected": self.events_rejected,
            "events_validated": self.events_validated,
            "head_group_count": self.head_group_count,
            "installation_id_present": self.installation_id_present,
            "installation_id_required": self.installation_id_required,
            "language_group_count": self.language_group_count,
            "last_error_code": self.last_error_code,
            "limitation_codes": list(self.limitation_codes),
            "local_collection_allowed": self.local_collection_allowed,
            "persistence_enabled": self.persistence_enabled,
            "policy_version": self.policy_version,
            "privacy_projection_applied": self.privacy_projection_applied,
            "rule_attempted": self.rule_attempted,
            "rule_completed": self.rule_completed,
            "rule_failed": self.rule_failed,
            "rule_skipped": self.rule_skipped,
            "schema_version": self.schema_version,
            "total_language_files": self.total_language_files,
            "transmission_enabled": self.transmission_enabled,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def empty_repository_aggregate_analytics_diagnostics(
    *,
    limitation_codes: tuple[str, ...] = (),
) -> RepositoryAggregateAnalyticsDiagnostics:
    return RepositoryAggregateAnalyticsDiagnostics(
        policy_version=COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION,
        schema_version=COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION,
        local_collection_allowed=True,
        persistence_enabled=False,
        transmission_enabled=False,
        installation_id_required=True,
        installation_id_present=False,
        privacy_projection_applied=False,
        language_group_count=0,
        total_language_files=0,
        rule_attempted=0,
        rule_completed=0,
        rule_skipped=0,
        rule_failed=0,
        head_group_count=0,
        events_collected=0,
        events_projected=0,
        events_validated=0,
        events_rejected=0,
        last_error_code=None,
        limitation_codes=tuple(sorted(set(limitation_codes))),
    )


__all__ = [
    "RepositoryAggregateAnalyticsDiagnostics",
    "empty_repository_aggregate_analytics_diagnostics",
]
