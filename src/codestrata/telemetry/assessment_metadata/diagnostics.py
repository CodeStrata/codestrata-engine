"""Safe diagnostics for assessment_metadata emission (Slice 20.8).

Allowed: status category, safe failure reason.
Forbidden: request/response bodies, findings, paths, URLs, secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssessmentMetadataEmissionDiagnostics:
    """In-memory counters — never stores payloads or endpoints."""

    attempts: int = 0
    successes: int = 0
    failures: int = 0
    skipped: int = 0
    last_status: str = "not_attempted"
    last_failure_category: str | None = None
    limitation_codes: list[str] = field(default_factory=list)

    def record_skip(self, reason: str) -> None:
        self.skipped += 1
        self.last_status = "skipped"
        self.last_failure_category = reason
        if reason not in self.limitation_codes:
            self.limitation_codes.append(reason)

    def record_success(self, *, status_category: str = "accepted") -> None:
        self.attempts += 1
        self.successes += 1
        self.last_status = "succeeded"
        self.last_failure_category = status_category

    def record_failure(self, category: str) -> None:
        self.attempts += 1
        self.failures += 1
        self.last_status = "failed_silently"
        self.last_failure_category = category

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "failures": self.failures,
            "last_failure_category": self.last_failure_category,
            "last_status": self.last_status,
            "limitation_codes": sorted(set(self.limitation_codes)),
            "skipped": self.skipped,
            "successes": self.successes,
        }

    def safe_log_message(self) -> str:
        """Human-safe one-liner — never includes body/path/URL/secret."""

        if self.last_status == "skipped":
            return (
                "assessment metadata upload skipped "
                f"({self.last_failure_category or 'not_authorized'})"
            )
        if self.last_status == "succeeded":
            return "assessment metadata upload accepted"
        if self.attempts == 0:
            return "assessment metadata upload not attempted"
        return (
            "assessment metadata upload failed "
            f"({self.last_failure_category or 'unknown'})"
        )


__all__ = ["AssessmentMetadataEmissionDiagnostics"]
