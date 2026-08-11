"""Bounded assessment telemetry isolation result model (Slice 9.12)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata.telemetry.assessment_isolation_policy import (
    COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION,
)


class AssessmentPrimaryStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    INTERRUPTED = "interrupted"
    NOT_RUN = "not_run"


class AssessmentTelemetrySideStatus(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    COMPLETED = "completed"
    FAILED_SILENTLY = "failed_silently"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class AssessmentTelemetryIsolationResult:
    """Safe isolation snapshot — no paths, payloads, Findings, or credentials."""

    primary_status: str
    telemetry_status: str
    primary_result_preserved: bool = True
    primary_exception_preserved: bool = True
    exit_code_preserved: bool = True
    artifacts_preserved: bool = True
    source_integrity_preserved: bool = True
    telemetry_failure_category: str | None = None
    telemetry_event_attempts: int = 0
    telemetry_event_failures: int = 0
    policy_version: str = COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION
    limitation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "limitation_codes", tuple(sorted(set(self.limitation_codes)))
        )

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "artifacts_preserved": self.artifacts_preserved,
            "exit_code_preserved": self.exit_code_preserved,
            "limitation_codes": list(self.limitation_codes),
            "policy_version": self.policy_version,
            "primary_exception_preserved": self.primary_exception_preserved,
            "primary_result_preserved": self.primary_result_preserved,
            "primary_status": self.primary_status,
            "source_integrity_preserved": self.source_integrity_preserved,
            "telemetry_event_attempts": self.telemetry_event_attempts,
            "telemetry_event_failures": self.telemetry_event_failures,
            "telemetry_status": self.telemetry_status,
        }
        if self.telemetry_failure_category is not None:
            payload["telemetry_failure_category"] = self.telemetry_failure_category
        return {key: payload[key] for key in sorted(payload)}

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


__all__ = [
    "AssessmentPrimaryStatus",
    "AssessmentTelemetryIsolationResult",
    "AssessmentTelemetrySideStatus",
]
