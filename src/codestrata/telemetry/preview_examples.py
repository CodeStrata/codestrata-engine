"""Deterministic illustrative RuntimeTelemetryEvent builders (Slice 9.9).

Uses only fixed categorical enum values — never platform/cwd/env detection.
"""

from __future__ import annotations

from codestrata.telemetry.events import (
    ArchFamily,
    DurationBucket,
    FailureCategory,
    Lifecycle,
    OperationCategory,
    OsFamily,
    ResultCategory,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.preview_policy import DEFAULT_PREVIEW_EVENT, PreviewPolicyError

# Stable placeholder — not derived from the running package or machine.
_ILLUSTRATIVE_CLI_VERSION = "0.2.0"
_ILLUSTRATIVE_HEADS = ("architecture", "security")


def illustrative_runtime_event(event_name: str) -> RuntimeTelemetryEvent:
    """Build a typed illustrative intake event for the selected runtime event."""

    try:
        event_type = RuntimeEventType(event_name)
    except ValueError as error:
        raise PreviewPolicyError(f"unsupported preview event: {event_name}") from error

    if event_type is RuntimeEventType.APPLICATION_STARTED:
        return RuntimeTelemetryEvent(
            event_type=event_type,
            cli_version=_ILLUSTRATIVE_CLI_VERSION,
            os_family=OsFamily.LINUX,
            arch_family=ArchFamily.X86_64,
            lifecycle=Lifecycle.START,
            offline_mode=True,
            ai_used=False,
        )
    if event_type is RuntimeEventType.APPLICATION_COMPLETED:
        return RuntimeTelemetryEvent(
            event_type=event_type,
            cli_version=_ILLUSTRATIVE_CLI_VERSION,
            os_family=OsFamily.LINUX,
            arch_family=ArchFamily.X86_64,
            lifecycle=Lifecycle.COMPLETE,
            result=ResultCategory.SUCCESS,
            duration_bucket=DurationBucket.S_1_10,
            offline_mode=True,
            ai_used=False,
        )
    if event_type is RuntimeEventType.FEATURE_INVOKED:
        return RuntimeTelemetryEvent(
            event_type=event_type,
            cli_version=_ILLUSTRATIVE_CLI_VERSION,
            os_family=OsFamily.LINUX,
            arch_family=ArchFamily.X86_64,
            lifecycle=Lifecycle.START,
            operation_category=OperationCategory.ASSESS,
            enabled_assessment_heads=_ILLUSTRATIVE_HEADS,
            offline_mode=True,
            ai_used=False,
        )
    if event_type is RuntimeEventType.FEATURE_COMPLETED:
        return RuntimeTelemetryEvent(
            event_type=event_type,
            cli_version=_ILLUSTRATIVE_CLI_VERSION,
            os_family=OsFamily.LINUX,
            arch_family=ArchFamily.X86_64,
            lifecycle=Lifecycle.COMPLETE,
            result=ResultCategory.SUCCESS,
            duration_bucket=DurationBucket.S_1_10,
            operation_category=OperationCategory.ASSESS,
            enabled_assessment_heads=_ILLUSTRATIVE_HEADS,
            offline_mode=True,
            ai_used=False,
        )
    if event_type is RuntimeEventType.OPERATION_FAILED:
        return RuntimeTelemetryEvent(
            event_type=event_type,
            cli_version=_ILLUSTRATIVE_CLI_VERSION,
            os_family=OsFamily.LINUX,
            arch_family=ArchFamily.X86_64,
            lifecycle=Lifecycle.FAIL,
            result=ResultCategory.FAILURE,
            duration_bucket=DurationBucket.S_1_10,
            operation_category=OperationCategory.ASSESS,
            enabled_assessment_heads=_ILLUSTRATIVE_HEADS,
            offline_mode=True,
            ai_used=False,
            failure_category=FailureCategory.UNAVAILABLE,
        )
    raise PreviewPolicyError(f"unsupported preview event: {event_name}")


def resolve_preview_event_name(event_name: str | None) -> str:
    if event_name is None or event_name.strip() == "":
        return DEFAULT_PREVIEW_EVENT
    name = event_name.strip()
    try:
        return RuntimeEventType(name).value
    except ValueError as error:
        raise PreviewPolicyError(
            "unsupported preview event; expected one of: "
            + ", ".join(sorted(item.value for item in RuntimeEventType))
        ) from error


__all__ = [
    "illustrative_runtime_event",
    "resolve_preview_event_name",
]
