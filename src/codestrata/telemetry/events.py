"""Typed Engine-local telemetry runtime events (Slice 9.1).

Narrow intake model — independent from legacy ``EventName`` / Phase 14.3
payloads and from Platform Community Cloud DTOs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata.telemetry.errors import TelemetryRuntimeError, TelemetryRuntimeErrorCode


class RuntimeEventType(StrEnum):
    """Initial runtime event vocabulary aligned toward future cloud mapping."""

    APPLICATION_STARTED = "application_started"
    APPLICATION_COMPLETED = "application_completed"
    FEATURE_INVOKED = "feature_invoked"
    FEATURE_COMPLETED = "feature_completed"
    OPERATION_FAILED = "operation_failed"


class OsFamily(StrEnum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    OTHER = "other"


class ArchFamily(StrEnum):
    X86_64 = "x86_64"
    ARM64 = "arm64"
    OTHER = "other"


class Lifecycle(StrEnum):
    START = "start"
    COMPLETE = "complete"
    FAIL = "fail"


class ResultCategory(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class DurationBucket(StrEnum):
    LT_1S = "lt_1s"
    S_1_10 = "s_1_10"
    S_10_60 = "s_10_60"
    M_1_5 = "m_1_5"
    GT_5M = "gt_5m"


class OperationCategory(StrEnum):
    ASSESS = "assess"
    REPORT = "report"
    OTHER = "other"


class FailureCategory(StrEnum):
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


APPROVED_RUNTIME_EVENT_TYPES: frozenset[str] = frozenset(
    item.value for item in RuntimeEventType
)


@dataclass(frozen=True, slots=True)
class RuntimeTelemetryEvent:
    """Narrow typed runtime event intake — no repository/path/credential fields."""

    event_type: RuntimeEventType
    client_name: str = "codestrata_cli"
    cli_version: str | None = None
    os_family: OsFamily | None = None
    arch_family: ArchFamily | None = None
    lifecycle: Lifecycle | None = None
    result: ResultCategory | None = None
    duration_bucket: DurationBucket | None = None
    operation_category: OperationCategory | None = None
    enabled_assessment_heads: tuple[str, ...] = ()
    offline_mode: bool | None = None
    ai_used: bool | None = None
    failure_category: FailureCategory | None = None

    def __post_init__(self) -> None:
        if self.client_name != "codestrata_cli":
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        if not isinstance(self.event_type, RuntimeEventType):
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.VALIDATION_FAILED)
        heads = tuple(sorted({str(item) for item in self.enabled_assessment_heads if item}))
        for head in heads:
            if "/" in head or "\\" in head or ".." in head or len(head) > 32:
                raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        object.__setattr__(self, "enabled_assessment_heads", heads)
        if self.cli_version is not None:
            version = self.cli_version.strip()
            if not version or len(version) > 32 or "/" in version or "\\" in version:
                raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
            object.__setattr__(self, "cli_version", version)

    def to_intake_dict(self) -> dict[str, Any]:
        """Stable dict of present fields for projection (not a public dump)."""

        payload: dict[str, Any] = {
            "client_name": self.client_name,
            "event_type": self.event_type.value,
        }
        if self.cli_version is not None:
            payload["cli_version"] = self.cli_version
        if self.os_family is not None:
            payload["os_family"] = self.os_family.value
        if self.arch_family is not None:
            payload["arch_family"] = self.arch_family.value
        if self.lifecycle is not None:
            payload["lifecycle"] = self.lifecycle.value
        if self.result is not None:
            payload["result"] = self.result.value
        if self.duration_bucket is not None:
            payload["duration_bucket"] = self.duration_bucket.value
        if self.operation_category is not None:
            payload["operation_category"] = self.operation_category.value
        if self.enabled_assessment_heads:
            payload["enabled_assessment_heads"] = list(self.enabled_assessment_heads)
        if self.offline_mode is not None:
            payload["offline_mode"] = self.offline_mode
        if self.ai_used is not None:
            payload["ai_used"] = self.ai_used
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category.value
        return {key: payload[key] for key in sorted(payload)}


__all__ = [
    "APPROVED_RUNTIME_EVENT_TYPES",
    "ArchFamily",
    "DurationBucket",
    "FailureCategory",
    "Lifecycle",
    "OperationCategory",
    "OsFamily",
    "ResultCategory",
    "RuntimeEventType",
    "RuntimeTelemetryEvent",
]
