"""Disabled-by-default product telemetry facade (Slice 9.2).

Implements the minimum legacy call surface used by assess/report/UX hooks
without constructing an active ``TelemetryService``, reading preferences,
generating installation IDs, queuing, prompting, or sending HTTP.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codestrata.package_metadata import get_package_version
from codestrata.telemetry.constants import EventName
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import (
    Lifecycle,
    OperationCategory,
    ResultCategory,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.runtime import TelemetryRuntime, record_telemetry_safely
from codestrata.telemetry.runtime_factory import create_default_telemetry_runtime
from codestrata.telemetry.runtime_policy import PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION


class DisabledTelemetryFacade:
    """Compatibility surface for product hooks — no legacy side effects.

    Reflects the bound runtime's session decision. Product construction uses the
    default disabled runtime; tests may inject an allowed_for_session runtime.
    """

    def __init__(self, runtime: TelemetryRuntime | None = None) -> None:
        self._runtime = runtime or create_default_telemetry_runtime()

    @property
    def runtime(self) -> TelemetryRuntime:
        return self._runtime

    def force_disabled_by_env(self) -> bool:
        # Do not inspect environment for enablement or disablement signals.
        return False

    def is_enabled(self) -> bool:
        return self._runtime.session.telemetry_enabled

    def decision_made(self) -> bool:
        # Do not read saved preferences; report whether this session is explicit.
        return self._runtime.session.consent.explicit

    def ensure_identity(self) -> tuple[str, bool]:
        """No-op — never generate, read, or persist an installation ID."""

        return ("", False)

    def status(self) -> dict[str, Any]:
        diagnostics = self._runtime.diagnostics().to_stable_dict()
        consent = self._runtime.session.consent
        return {
            "codestrata_version": get_package_version(),
            "decision_made": consent.explicit,
            "disabled_by_default": (
                consent.decision is TelemetryDecision.DISABLED_BY_DEFAULT
            ),
            "enabled": self.is_enabled(),
            "endpoint_configured": False,
            "force_disabled_by_env": False,
            "legacy_consent_not_reused": True,
            "local_counters": {},
            "persisted": False,
            "prior_consent_reused": False,
            "queue_depth": 0,
            "runtime_authoritative": True,
            "runtime_decision": consent.decision.value,
            "runtime_diagnostics": diagnostics,
            "runtime_policy_version": diagnostics.get("runtime_policy_version"),
            "schema_version": PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
            "transmission": "none",
            "transmission_authorized": consent.transmission_authorized,
        }

    def enable(self) -> dict[str, Any]:
        """Product path cannot enable transmission (Slice 9.2)."""

        return self.status()

    def disable(self) -> dict[str, Any]:
        return self.status()

    def reset(self) -> dict[str, Any]:
        """No-op — does not mutate legacy preference, identity, or queue files."""

        return self.status()

    def show_sample_payload(
        self,
        *,
        event: EventName | str = EventName.ASSESSMENT_COMPLETED,
    ) -> dict[str, Any]:
        """Privacy-safe runtime preview — no installation ID, no transmission."""

        _ = event
        runtime_event = RuntimeTelemetryEvent(
            event_type=RuntimeEventType.FEATURE_COMPLETED,
            operation_category=OperationCategory.ASSESS,
            lifecycle=Lifecycle.COMPLETE,
            result=ResultCategory.SUCCESS,
            ai_used=False,
        )
        preview = self._runtime.preview(runtime_event)
        if preview is None:
            return {
                "decision": TelemetryDecision.DISABLED_BY_DEFAULT.value,
                "telemetry_enabled": False,
                "transmission": "none",
            }
        return preview.to_stable_dict()

    def emit(self, event: EventName | str, **kwargs: Any) -> dict[str, Any] | None:
        """Drop legacy emit — never queue, send, or write."""

        _ = (event, kwargs)
        self._safe_record(
            RuntimeTelemetryEvent(
                event_type=RuntimeEventType.FEATURE_INVOKED,
                operation_category=OperationCategory.OTHER,
            )
        )
        return None

    def flush_queue(self) -> int:
        return 0

    def record_assessment_started(
        self,
        *,
        ai_enabled: bool,
        domains: list[str] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        _ = repo_root  # never scan repository for telemetry
        heads = _safe_heads(domains)
        self._safe_record(
            RuntimeTelemetryEvent(
                event_type=RuntimeEventType.FEATURE_INVOKED,
                operation_category=OperationCategory.ASSESS,
                lifecycle=Lifecycle.START,
                ai_used=bool(ai_enabled),
                enabled_assessment_heads=heads,
            )
        )

    def record_assessment_completed(
        self,
        *,
        ai_enabled: bool,
        ai_executed: bool,
        success: bool,
        duration_ms: float | None,
        domains: list[str] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        _ = (duration_ms, repo_root)  # no path scan; duration not required for drop
        heads = _safe_heads(domains)
        self._safe_record(
            RuntimeTelemetryEvent(
                event_type=(
                    RuntimeEventType.FEATURE_COMPLETED
                    if success
                    else RuntimeEventType.OPERATION_FAILED
                ),
                operation_category=OperationCategory.ASSESS,
                lifecycle=Lifecycle.COMPLETE if success else Lifecycle.FAIL,
                result=ResultCategory.SUCCESS if success else ResultCategory.FAILURE,
                ai_used=bool(ai_enabled or ai_executed),
                enabled_assessment_heads=heads,
            )
        )

    def record_report_opened(self) -> None:
        self._safe_record(
            RuntimeTelemetryEvent(
                event_type=RuntimeEventType.FEATURE_INVOKED,
                operation_category=OperationCategory.REPORT,
                lifecycle=Lifecycle.START,
            )
        )

    def record_version_check(self) -> None:
        self._safe_record(
            RuntimeTelemetryEvent(
                event_type=RuntimeEventType.FEATURE_INVOKED,
                operation_category=OperationCategory.OTHER,
                lifecycle=Lifecycle.START,
            )
        )

    def _safe_record(self, event: RuntimeTelemetryEvent) -> None:
        try:
            record_telemetry_safely(self._runtime, event)
        except Exception:  # noqa: BLE001 - fail-silent product boundary
            return


def _safe_heads(domains: list[str] | None) -> tuple[str, ...]:
    if not domains:
        return ()
    cleaned: list[str] = []
    for item in domains:
        text = str(item).strip()
        if not text or len(text) > 32:
            continue
        if any(marker in text for marker in ("/", "\\", ":", "..")):
            continue
        cleaned.append(text)
    return tuple(cleaned)


__all__ = ["DisabledTelemetryFacade"]
