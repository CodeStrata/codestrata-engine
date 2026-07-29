"""Telemetry helpers for Shared Rule Platform."""

from __future__ import annotations

from codestrata.application.rules.models import RulePlatformExecutionResult, RuleTelemetry


def summarize_telemetry(result: RulePlatformExecutionResult) -> RuleTelemetry:
    """Return bounded telemetry already attached to an execution result."""

    return result.telemetry
