"""Safe diagnostics for assessment telemetry isolation (Slice 9.12)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from codestrata.telemetry.assessment_isolation_policy import (
    COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION,
)


@dataclass
class AssessmentIsolationDiagnostics:
    """Process-local isolation counters — never printed automatically."""

    policy_version: str = COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION
    event_attempts: int = 0
    event_failures: int = 0
    primary_success_count: int = 0
    primary_failure_count: int = 0
    last_primary_status: str | None = None
    last_telemetry_status: str | None = None
    last_failure_category: str | None = None
    limitation_codes: tuple[str, ...] = field(
        default_factory=lambda: (
            "primary_operation_authoritative",
            "telemetry_failures_fail_silent",
            "no_transport_activation_by_default",
        )
    )

    def record_event_attempt(self) -> None:
        self.event_attempts += 1

    def record_event_failure(self, category: str = "internal_failure") -> None:
        self.event_failures += 1
        self.last_failure_category = category
        self.last_telemetry_status = "failed_silently"

    def record_primary_success(self) -> None:
        self.primary_success_count += 1
        self.last_primary_status = "success"

    def record_primary_failure(self) -> None:
        self.primary_failure_count += 1
        self.last_primary_status = "failure"

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "event_attempts": self.event_attempts,
            "event_failures": self.event_failures,
            "last_failure_category": self.last_failure_category,
            "last_primary_status": self.last_primary_status,
            "last_telemetry_status": self.last_telemetry_status,
            "limitation_codes": list(sorted(self.limitation_codes)),
            "policy_version": self.policy_version,
            "primary_failure_count": self.primary_failure_count,
            "primary_success_count": self.primary_success_count,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


__all__ = ["AssessmentIsolationDiagnostics"]
