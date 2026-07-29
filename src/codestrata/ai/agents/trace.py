"""Execution tracing helpers for the modernization assessment agent."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from codestrata.ai.agents.models import (
    AGENT_NAME,
    AGENT_VERSION,
    AgentExecutionStatus,
    AgentExecutionStep,
    AgentExecutionTrace,
    AgentStepType,
    JSONValue,
)
from codestrata.ai.providers.parsing import sanitize_provider_text


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def new_trace_id() -> str:
    """Return a unique trace identifier."""

    return uuid.uuid4().hex


class AgentTraceRecorder:
    """Mutable recorder that produces an immutable AgentExecutionTrace."""

    def __init__(self, *, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or new_trace_id()
        self.started_at_utc = utc_now()
        self._started_perf = time.perf_counter()
        self._steps: list[AgentExecutionStep] = []
        self.tool_call_count = 0
        self.model_call_count = 0
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.total_tokens: int | None = None

    @property
    def next_sequence_number(self) -> int:
        return len(self._steps) + 1

    def record_step(
        self,
        *,
        step_type: AgentStepType,
        name: str,
        started_at_utc: datetime,
        started_perf: float,
        success: bool,
        input_summary: dict[str, JSONValue] | None = None,
        output_summary: dict[str, JSONValue] | None = None,
        error: BaseException | None = None,
    ) -> AgentExecutionStep:
        """Record one completed step and return it."""

        completed_at_utc = utc_now()
        latency_ms = max(0.0, (time.perf_counter() - started_perf) * 1000.0)
        error_type: str | None = None
        error_message: str | None = None
        if error is not None:
            error_type = type(error).__name__
            error_message = sanitize_provider_text(str(error))

        step = AgentExecutionStep(
            sequence_number=self.next_sequence_number,
            step_type=step_type,
            name=name,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            latency_ms=latency_ms,
            success=success,
            input_summary=dict(input_summary or {}),
            output_summary=dict(output_summary or {}),
            error_type=error_type,
            error_message=error_message,
        )
        self._steps.append(step)

        if step_type == AgentStepType.TOOL_CALL:
            self.tool_call_count += 1
        if step_type == AgentStepType.MODEL_INVOCATION:
            self.model_call_count += 1

        return step

    def set_token_usage(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
    ) -> None:
        """Capture aggregated model token usage for the trace."""

        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens

    def finalize(self, status: AgentExecutionStatus) -> AgentExecutionTrace:
        """Build the immutable completed trace."""

        completed_at_utc = utc_now()
        total_latency_ms = max(0.0, (time.perf_counter() - self._started_perf) * 1000.0)
        return AgentExecutionTrace(
            trace_id=self.trace_id,
            agent_name=AGENT_NAME,
            agent_version=AGENT_VERSION,
            started_at_utc=self.started_at_utc,
            completed_at_utc=completed_at_utc,
            total_latency_ms=total_latency_ms,
            status=status,
            steps=tuple(self._steps),
            tool_call_count=self.tool_call_count,
            model_call_count=self.model_call_count,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
        )


def summary_size(value: Any) -> int:
    """Return a safe size metric for tracing."""

    if value is None:
        return 0
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    return len(str(value))
