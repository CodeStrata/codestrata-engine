"""Bounded anonymous analytics diagnostics (Epic 10 Slice 10.1).

Counters and versions only — never payloads, paths, credentials, or identities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class AnalyticsDiagnostics:
    """Safe analytics-contract diagnostics."""

    policy_version: str
    schema_version: str
    collection_enabled: bool
    persistence_enabled: bool
    transmission_enabled: bool
    installation_id_allowed: bool
    events_seen: int
    events_projected: int
    events_validated: int
    events_rejected: int
    validation_failures: int
    privacy_required_failures: int
    last_error_code: str | None
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "collection_enabled": self.collection_enabled,
            "events_projected": self.events_projected,
            "events_rejected": self.events_rejected,
            "events_seen": self.events_seen,
            "events_validated": self.events_validated,
            "installation_id_allowed": self.installation_id_allowed,
            "last_error_code": self.last_error_code,
            "limitation_codes": list(self.limitation_codes),
            "persistence_enabled": self.persistence_enabled,
            "policy_version": self.policy_version,
            "privacy_required_failures": self.privacy_required_failures,
            "schema_version": self.schema_version,
            "transmission_enabled": self.transmission_enabled,
            "validation_failures": self.validation_failures,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def empty_analytics_diagnostics(
    *,
    limitation_codes: tuple[str, ...] = (),
) -> AnalyticsDiagnostics:
    return AnalyticsDiagnostics(
        policy_version=COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
        schema_version=COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
        collection_enabled=False,
        persistence_enabled=False,
        transmission_enabled=False,
        installation_id_allowed=False,
        events_seen=0,
        events_projected=0,
        events_validated=0,
        events_rejected=0,
        validation_failures=0,
        privacy_required_failures=0,
        last_error_code=None,
        limitation_codes=tuple(sorted(set(limitation_codes))),
    )


__all__ = ["AnalyticsDiagnostics", "empty_analytics_diagnostics"]
