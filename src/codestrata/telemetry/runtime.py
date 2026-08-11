"""Fail-silent Community telemetry runtime (Slices 9.1–9.10).

Consent is fixed at construction. Transmission requires transmission_authorized,
then the pre-transport privacy gate, then the configured transport port
(default: unavailable). Independent from legacy ``TelemetryService``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.diagnostics import (
    TelemetryRuntimeDiagnostics,
    diagnostics_from_session,
)
from codestrata.telemetry.errors import TelemetryRuntimeError, TelemetryRuntimeErrorCode
from codestrata.telemetry.events import RuntimeTelemetryEvent
from codestrata.telemetry.pre_transport_gate import validate_event_before_transport
from codestrata.telemetry.preview import TelemetryPreview, preview_runtime_event
from codestrata.telemetry.projection import PrivacySafeTelemetryEvent, project_runtime_event
from codestrata.telemetry.session import (
    TelemetrySession,
    TelemetrySessionCounters,
    new_disabled_session,
)
from codestrata.telemetry.transport import (
    TelemetryTransportResult,
    TelemetryTransportResultKind,
)


class TelemetryRecordStatus(StrEnum):
    DROPPED_DISABLED = "dropped_disabled"
    DROPPED_DENIED = "dropped_denied"
    PROJECTED = "projected"
    PREVIEWED = "previewed"
    TRANSPORT_RESULT = "transport_result"
    PRIVACY_REJECTED = "privacy_rejected"
    FAILED_SILENTLY = "failed_silently"


@dataclass(frozen=True, slots=True)
class TelemetryRecordResult:
    """Bounded result for diagnostics — never raises into command execution."""

    status: TelemetryRecordStatus
    decision: str
    transport_kind: str | None = None
    error_code: str | None = None
    projected: PrivacySafeTelemetryEvent | None = None
    preview: TelemetryPreview | None = None

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": self.decision,
            "status": self.status.value,
        }
        if self.transport_kind is not None:
            payload["transport_kind"] = self.transport_kind
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        return {key: payload[key] for key in sorted(payload)}


class TelemetryRuntime:
    """Session-scoped runtime: project, preview, drop, fail-silent."""

    def __init__(self, session: TelemetrySession | None = None) -> None:
        self._session = session or new_disabled_session()

    @property
    def session(self) -> TelemetrySession:
        return self._session

    def diagnostics(self) -> TelemetryRuntimeDiagnostics:
        return diagnostics_from_session(self._session)

    def preview(self, event: RuntimeTelemetryEvent) -> TelemetryPreview | None:
        """Return privacy-safe preview or None on failure (fail-silent)."""

        try:
            return preview_runtime_event(event, session=self._session)
        except Exception:
            self._bump(failures=1)
            return None

    def record(self, event: RuntimeTelemetryEvent) -> TelemetryRecordResult:
        """Project and optionally hand to transport — never raises."""

        return record_telemetry_safely(self, event)

    def _bump(
        self,
        *,
        events_seen: int = 0,
        events_projected: int = 0,
        events_dropped: int = 0,
        transmission_attempts: int = 0,
        failures: int = 0,
        transport_unavailable: int = 0,
        transport_sent: int = 0,
        transport_rejected: int = 0,
        privacy_gate_attempts: int = 0,
        privacy_gate_accepted: int = 0,
        privacy_gate_rejected: int = 0,
        privacy_gate_failures: int = 0,
        last_privacy_result_category: str | None = None,
    ) -> None:
        current = self._session.counters
        last_category = (
            last_privacy_result_category
            if last_privacy_result_category is not None
            else current.last_privacy_result_category
        )
        self._session = self._session.with_counters(
            TelemetrySessionCounters(
                events_seen=current.events_seen + events_seen,
                events_projected=current.events_projected + events_projected,
                events_dropped=current.events_dropped + events_dropped,
                transmission_attempts=current.transmission_attempts + transmission_attempts,
                failures=current.failures + failures,
                transport_unavailable=current.transport_unavailable + transport_unavailable,
                transport_sent=current.transport_sent + transport_sent,
                transport_rejected=current.transport_rejected + transport_rejected,
                privacy_gate_attempts=current.privacy_gate_attempts + privacy_gate_attempts,
                privacy_gate_accepted=current.privacy_gate_accepted + privacy_gate_accepted,
                privacy_gate_rejected=current.privacy_gate_rejected + privacy_gate_rejected,
                privacy_gate_failures=current.privacy_gate_failures + privacy_gate_failures,
                last_privacy_result_category=last_category,
            )
        )


def record_telemetry_safely(
    runtime: TelemetryRuntime,
    event: RuntimeTelemetryEvent,
) -> TelemetryRecordResult:
    """Explicit fail-silent wrapper around event intake / projection / transport."""

    decision = runtime.session.decision
    try:
        runtime._bump(events_seen=1)
        projected = project_runtime_event(event, policy=runtime.session.policy)
        runtime._bump(events_projected=1)
        preview = preview_runtime_event(event, session=runtime.session)

        if not runtime.session.transmission_authorized:
            runtime._bump(events_dropped=1)
            if decision is TelemetryDecision.DENIED_FOR_SESSION:
                return TelemetryRecordResult(
                    status=TelemetryRecordStatus.DROPPED_DENIED,
                    decision=decision.value,
                    transport_kind=TelemetryTransportResultKind.DISABLED.value,
                    projected=projected,
                    preview=preview,
                )
            return TelemetryRecordResult(
                status=TelemetryRecordStatus.DROPPED_DISABLED,
                decision=decision.value,
                transport_kind=TelemetryTransportResultKind.DISABLED.value,
                projected=projected,
                preview=preview,
            )

        # Consent authorizes handoff; privacy gate is mandatory before transport.
        runtime._bump(transmission_attempts=1)
        result, privacy_rejected = _safe_send(runtime, projected)
        _count_transport_result(runtime, result)
        if privacy_rejected:
            return TelemetryRecordResult(
                status=TelemetryRecordStatus.PRIVACY_REJECTED,
                decision=decision.value,
                transport_kind=result.kind.value,
                error_code=TelemetryRuntimeErrorCode.PRIVACY_REJECTED.value,
                projected=projected,
                preview=preview,
            )
        return TelemetryRecordResult(
            status=TelemetryRecordStatus.TRANSPORT_RESULT,
            decision=decision.value,
            transport_kind=result.kind.value,
            projected=projected,
            preview=preview,
        )
    except TelemetryRuntimeError as exc:
        runtime._bump(events_dropped=1, failures=1)
        return TelemetryRecordResult(
            status=TelemetryRecordStatus.FAILED_SILENTLY,
            decision=decision.value,
            error_code=exc.code.value,
        )
    except Exception:
        runtime._bump(events_dropped=1, failures=1)
        return TelemetryRecordResult(
            status=TelemetryRecordStatus.FAILED_SILENTLY,
            decision=decision.value,
            error_code=TelemetryRuntimeErrorCode.INTERNAL.value,
        )


def _count_transport_result(
    runtime: TelemetryRuntime,
    result: TelemetryTransportResult,
) -> None:
    if result.kind is TelemetryTransportResultKind.UNAVAILABLE:
        runtime._bump(transport_unavailable=1)
    elif result.kind is TelemetryTransportResultKind.SENT:
        runtime._bump(transport_sent=1)
    elif result.kind is TelemetryTransportResultKind.REJECTED:
        runtime._bump(transport_rejected=1)
    elif result.kind is TelemetryTransportResultKind.FAILED_SILENTLY:
        runtime._bump(failures=1)


def _safe_send(
    runtime: TelemetryRuntime,
    event: PrivacySafeTelemetryEvent,
) -> tuple[TelemetryTransportResult, bool]:
    """Run the pre-transport privacy gate, then hand accepted events to transport.

    Returns ``(transport_result, privacy_rejected)``.
    """

    try:
        runtime._bump(privacy_gate_attempts=1)
        gate = validate_event_before_transport(
            event,
            runtime_policy=runtime.session.policy,
        )
    except Exception:
        runtime._bump(
            privacy_gate_failures=1,
            failures=1,
            events_dropped=1,
            last_privacy_result_category="internal_failure",
        )
        return (
            TelemetryTransportResult(kind=TelemetryTransportResultKind.FAILED_SILENTLY),
            True,
        )

    if not gate.accepted or gate.accepted_event is None:
        if gate.status == "internal_failure":
            runtime._bump(
                privacy_gate_failures=1,
                events_dropped=1,
                last_privacy_result_category=gate.status,
            )
        else:
            runtime._bump(
                privacy_gate_rejected=1,
                events_dropped=1,
                last_privacy_result_category=gate.status,
            )
        return (
            TelemetryTransportResult(kind=TelemetryTransportResultKind.REJECTED),
            True,
        )

    runtime._bump(
        privacy_gate_accepted=1,
        last_privacy_result_category=gate.status,
    )
    try:
        result = runtime.session.transport.send(gate.accepted_event)
        if not isinstance(result, TelemetryTransportResult):
            runtime._bump(failures=1)
            return (
                TelemetryTransportResult(kind=TelemetryTransportResultKind.FAILED_SILENTLY),
                False,
            )
        return result, False
    except Exception:
        runtime._bump(failures=1)
        return (
            TelemetryTransportResult(kind=TelemetryTransportResultKind.FAILED_SILENTLY),
            False,
        )


def run_with_isolated_telemetry(
    primary: Callable[[], Any],
    *,
    runtime: TelemetryRuntime | None = None,
    on_success_event: RuntimeTelemetryEvent | None = None,
    on_failure_event: RuntimeTelemetryEvent | None = None,
) -> Any:
    """Run a primary operation; telemetry failures never alter its result."""

    active = runtime or TelemetryRuntime()
    try:
        result = primary()
    except Exception:
        if on_failure_event is not None:
            record_telemetry_safely(active, on_failure_event)
        raise
    if on_success_event is not None:
        record_telemetry_safely(active, on_success_event)
    return result


def default_runtime() -> TelemetryRuntime:
    return TelemetryRuntime(new_disabled_session())


__all__ = [
    "TelemetryRecordResult",
    "TelemetryRecordStatus",
    "TelemetryRuntime",
    "default_runtime",
    "record_telemetry_safely",
    "run_with_isolated_telemetry",
]
