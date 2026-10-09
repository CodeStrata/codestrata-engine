"""Durable opt-in Engine collection adapter (E13.1 / E13.2 / E13.3).

Local versioned preferences, per-run deny, inspect/enable/disable, and
cancellation of pending collection. No consent means no telemetry, evidence,
or graph transmissions. Evidence/graph upload stays unavailable unless a local
fake collector advertises the supported schema and passes receipt checks.
Export mode none/restricted withholds categories and never mutates local originals.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from codestrata.domain.contracts.enums import ExportMode
from codestrata.telemetry.canaries import (
    collection_surface_violations,
    exceeds_serialization_budget,
)
from codestrata.telemetry.consent import (
    TelemetrySessionConsent,
    deny_session_consent_from_cli_flag,
)
from codestrata.telemetry.consent_scope import CommunityConsentState, resolve_consent_capabilities
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import (
    Lifecycle,
    OperationCategory,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.export_gate import (
    collector_capability,
    evaluate_export_capability,
)
from codestrata.telemetry.export_models import (
    CapabilityCheck,
    CollectionCollector,
    CollectorKind,
    ExportEnvelopeError,
    ScopedExportEnvelope,
)
from codestrata.telemetry.export_modes import (
    ExportCategoryManifest,
    parse_export_mode,
    resolve_export_manifest,
)
from codestrata.telemetry.export_policy import ENGINE_EXPORT_POLICY_VERSION
from codestrata.telemetry.export_serialize import build_scoped_export, parse_scoped_export
from codestrata.telemetry.non_interactive import detect_automation
from codestrata.telemetry.opt_in_policy import (
    ENGINE_OPT_IN_POLICY_VERSION,
    EngineCollectionOptInPolicy,
    default_opt_in_policy,
)
from codestrata.telemetry.pending import cancel_pending_collection, queue_path_for_preference
from codestrata.telemetry.persisted_consent import (
    consent_from_persisted_preference,
    consent_status_payload,
    persist_disabled,
    persist_v2_yes,
)
from codestrata.telemetry.product_transport import resolve_product_telemetry_transport
from codestrata.telemetry.queue import queue_depth
from codestrata.telemetry.runtime import TelemetryRuntime, record_telemetry_safely
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.runtime_policy import DEFAULT_MAX_EVENT_SIZE_BYTES
from codestrata.telemetry.transport import TelemetryTransport


class CollectionChannel(StrEnum):
    TELEMETRY = "telemetry"
    EVIDENCE = "evidence"
    GRAPH = "graph"


class CollectionSubmitStatus(StrEnum):
    DROPPED_NO_CONSENT = "dropped_no_consent"
    DROPPED_PER_RUN_DENY = "dropped_per_run_deny"
    DROPPED_CHANNEL_UNAVAILABLE = "dropped_channel_unavailable"
    DROPPED_UNSUPPORTED = "dropped_unsupported"
    DROPPED_PROHIBITED = "dropped_prohibited"
    DROPPED_BUDGET = "dropped_budget"
    DROPPED_DISABLED = "dropped_disabled"
    ACCEPTED = "accepted"
    FAILED_SILENTLY = "failed_silently"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CollectionSubmitResult:
    status: CollectionSubmitStatus
    channel: str
    transmitted: bool = False
    reason: str | None = None

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "channel": self.channel,
            "status": self.status.value,
            "transmitted": self.transmitted,
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return {key: payload[key] for key in sorted(payload)}


class EngineCollectionAdapter:
    """Local Engine adapter: durable opt-in, per-run deny, no-egress default."""

    def __init__(
        self,
        *,
        preference_path: Path | None = None,
        per_run_deny: bool = False,
        transport: TelemetryTransport | None = None,
        collector: CollectionCollector | None = None,
        policy: EngineCollectionOptInPolicy | None = None,
        automation_detected: bool | None = None,
        environ: Mapping[str, str] | None = None,
        export_mode: ExportMode | str | None = None,
        withheld_categories: tuple[str, ...] | None = None,
    ) -> None:
        self._preference_path = preference_path
        self._per_run_deny = bool(per_run_deny)
        self._transport = transport
        self._collector = collector
        self._policy = policy or default_opt_in_policy()
        self._policy.validate()
        self._pending: list[object] = []
        if automation_detected is None:
            self._automation_detected = detect_automation(environ=environ)
        else:
            self._automation_detected = bool(automation_detected)
        self._export_manifest = _manifest_for_adapter(export_mode, withheld_categories)

    @property
    def policy(self) -> EngineCollectionOptInPolicy:
        return self._policy

    @property
    def per_run_deny(self) -> bool:
        return self._per_run_deny

    def inspect(self) -> dict[str, Any]:
        """Read-only durable + session status. Does not create consent or files."""

        caps = resolve_consent_capabilities(path=self._preference_path)
        channels = {
            channel.value: self.may_transmit(channel) for channel in CollectionChannel
        }
        consent = consent_from_persisted_preference(path=self._preference_path)
        transmission_authorized = bool(
            consent is not None
            and consent.transmission_authorized
            and not self._per_run_deny
        )
        status = consent_status_payload(path=self._preference_path)
        collector = collector_capability(self._collector)
        export_mode = (
            None if self._export_manifest is None else self._export_manifest.mode.value
        )
        withheld = (
            () if self._export_manifest is None else self._export_manifest.withheld_categories
        )
        return {
            "assessment_metadata_allowed": status["assessment_metadata_allowed"],
            "automation_detected": self._automation_detected,
            "channels": channels,
            "collector": collector.to_stable_dict(),
            "export_mode": export_mode,
            "export_policy_version": ENGINE_EXPORT_POLICY_VERSION,
            "lifecycle_allowed": status["lifecycle_allowed"],
            "opt_in_policy_version": ENGINE_OPT_IN_POLICY_VERSION,
            "pending_count": self.pending_count(),
            "per_run_deny": self._per_run_deny,
            "policy_token": self._policy.policy_token,
            "queue_depth": self.queue_depth(),
            "schema_version": status["schema_version"],
            "should_prompt_v2_upgrade": status["should_prompt_v2_upgrade"],
            "state": caps.state.value,
            "transmission_authorized": transmission_authorized,
            "v2_upgrade_declined": status["v2_upgrade_declined"],
            "withheld_categories": list(withheld),
        }

    def enable(self) -> dict[str, Any]:
        """Persist durable v2 opt-in. Does not transmit and does not invent CI consent."""

        persist_v2_yes(path=self._preference_path)
        return self.inspect()

    def disable(self) -> dict[str, Any]:
        """Persist disable, cancel queued sends, and drop in-memory pending."""

        persist_disabled(path=self._preference_path)
        self.cancel_pending()
        return self.inspect()

    def deny_this_run(self) -> None:
        """Per-run deny: process-local, does not change durable preference."""

        self._per_run_deny = True

    def may_transmit(self, channel: CollectionChannel | str) -> bool:
        parsed = _parse_channel(channel)
        if parsed is None:
            return False
        if self._per_run_deny:
            return False
        caps = resolve_consent_capabilities(path=self._preference_path)
        if caps.state is CommunityConsentState.UNDECIDED:
            return False
        if caps.state is CommunityConsentState.DISABLED:
            return False
        if not caps.lifecycle_allowed:
            return False
        if parsed is CollectionChannel.EVIDENCE or parsed is CollectionChannel.GRAPH:
            restriction = _restriction_reason(self._export_manifest, parsed.value)
            if restriction is not None:
                return False
            return evaluate_export_capability(self._collector, parsed.value).allowed
        return True

    def pending_count(self) -> int:
        return len(self._pending) + self.queue_depth()

    def queue_depth(self) -> int:
        return queue_depth(path=queue_path_for_preference(self._preference_path))

    def cancel_pending(self) -> int:
        """Drop in-memory pending items and the durable retry queue."""

        in_memory = len(self._pending)
        self._pending.clear()
        discarded = cancel_pending_collection(preference_path=self._preference_path)
        return in_memory + discarded

    def submit(
        self,
        channel: CollectionChannel | str,
        payload: object,
    ) -> CollectionSubmitResult:
        """Offer a payload to a collection channel. Never raises. Never invents consent."""

        try:
            return self._submit_impl(channel, payload)
        except Exception:  # noqa: BLE001 - upload/analytics cannot fail analysis
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.FAILED_SILENTLY,
                channel=str(channel),
                transmitted=False,
                reason="internal",
            )

    def _submit_impl(
        self,
        channel: CollectionChannel | str,
        payload: object,
    ) -> CollectionSubmitResult:
        parsed = _parse_channel(channel)
        if parsed is None:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_UNSUPPORTED,
                channel=str(channel),
                reason="unsupported_channel",
            )
        name = parsed.value
        scanned = payload
        if isinstance(payload, ScopedExportEnvelope):
            scanned = payload.to_stable_dict()
        if not isinstance(payload, RuntimeTelemetryEvent):
            if exceeds_serialization_budget(scanned, max_bytes=DEFAULT_MAX_EVENT_SIZE_BYTES):
                return CollectionSubmitResult(
                    status=CollectionSubmitStatus.DROPPED_BUDGET,
                    channel=name,
                    reason="payload_too_large",
                )
            violations = collection_surface_violations(scanned)
            if violations:
                return CollectionSubmitResult(
                    status=CollectionSubmitStatus.DROPPED_PROHIBITED,
                    channel=name,
                    reason="prohibited_data",
                )
        if self._per_run_deny:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_PER_RUN_DENY,
                channel=name,
                reason="per_run_deny",
            )
        if parsed is CollectionChannel.EVIDENCE or parsed is CollectionChannel.GRAPH:
            return self._submit_export(parsed, payload)
        if not self.may_transmit(parsed):
            caps = resolve_consent_capabilities(path=self._preference_path)
            status = (
                CollectionSubmitStatus.DROPPED_DISABLED
                if caps.state is CommunityConsentState.DISABLED
                else CollectionSubmitStatus.DROPPED_NO_CONSENT
            )
            return CollectionSubmitResult(
                status=status,
                channel=name,
                reason=caps.state.value,
            )
        event = _as_runtime_event(payload)
        if event is None:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_UNSUPPORTED,
                channel=name,
                reason="unsupported_telemetry_payload",
            )
        consent = consent_from_persisted_preference(path=self._preference_path)
        if consent is None or not consent.transmission_authorized:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_NO_CONSENT,
                channel=name,
                reason="transmission_not_authorized",
            )
        runtime = self._runtime_for(consent)
        result = record_telemetry_safely(runtime, event)
        transmitted = result.status.value == "transport_result" and result.transport_kind == "sent"
        return CollectionSubmitResult(
            status=CollectionSubmitStatus.ACCEPTED,
            channel=name,
            transmitted=transmitted,
            reason=result.transport_kind,
        )

    def _submit_export(
        self,
        channel: CollectionChannel,
        payload: object,
    ) -> CollectionSubmitResult:
        name = channel.value
        restriction = _restriction_reason(self._export_manifest, name)
        if restriction is not None:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE,
                channel=name,
                transmitted=False,
                reason=restriction,
            )
        decision = evaluate_export_capability(self._collector, name)
        if not decision.allowed:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE,
                channel=name,
                reason=decision.reason or f"{name}_upload_unavailable",
            )
        if not self.may_transmit(channel):
            caps = resolve_consent_capabilities(path=self._preference_path)
            status = (
                CollectionSubmitStatus.DROPPED_DISABLED
                if caps.state is CommunityConsentState.DISABLED
                else CollectionSubmitStatus.DROPPED_NO_CONSENT
            )
            return CollectionSubmitResult(
                status=status,
                channel=name,
                reason=caps.state.value,
            )
        try:
            envelope = _export_envelope_for(channel, payload)
        except ExportEnvelopeError as error:
            prohibited = "prohibited" in str(error)
            return CollectionSubmitResult(
                status=(
                    CollectionSubmitStatus.DROPPED_PROHIBITED
                    if prohibited
                    else CollectionSubmitStatus.DROPPED_UNSUPPORTED
                ),
                channel=name,
                reason="prohibited_data" if prohibited else "unsupported_export_payload",
            )
        collector = self._collector
        if collector is None:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE,
                channel=name,
                reason="schema_unadvertised",
            )
        receipt = collector.accept(envelope)
        if not receipt.accepted:
            return CollectionSubmitResult(
                status=CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE,
                channel=name,
                transmitted=False,
                reason=receipt.capability_check,
            )
        return CollectionSubmitResult(
            status=CollectionSubmitStatus.ACCEPTED,
            channel=name,
            transmitted=True,
            reason="fake_collector_local",
        )

    def _runtime_for(self, consent: TelemetrySessionConsent) -> TelemetryRuntime:
        transport = resolve_product_telemetry_transport(consent, transport=self._transport)
        return create_session_telemetry_runtime(consent=consent, transport=transport)

    def stage_pending(self, payload: object) -> None:
        """Test/helper seam: hold a local pending item until cancel or disable."""

        self._pending.append(payload)


def create_collection_adapter(
    *,
    preference_path: Path | None = None,
    per_run_deny: bool = False,
    transport: TelemetryTransport | None = None,
        collector: CollectionCollector | None = None,
        automation_detected: bool | None = None,
        export_mode: ExportMode | str | None = None,
        withheld_categories: tuple[str, ...] | None = None,
    ) -> EngineCollectionAdapter:
    return EngineCollectionAdapter(
        preference_path=preference_path,
        per_run_deny=per_run_deny,
        transport=transport,
        collector=collector,
        automation_detected=automation_detected,
        export_mode=export_mode,
        withheld_categories=withheld_categories,
    )


def run_primary_with_isolated_collection[T](
    primary: Callable[[], T],
    *,
    adapter: EngineCollectionAdapter | None = None,
    on_success: RuntimeTelemetryEvent | None = None,
    on_failure: RuntimeTelemetryEvent | None = None,
) -> T:
    """Run primary analysis; collection failures never alter its result or exception."""

    active = adapter or EngineCollectionAdapter()
    start = RuntimeTelemetryEvent(
        event_type=RuntimeEventType.FEATURE_INVOKED,
        operation_category=OperationCategory.ASSESS,
        lifecycle=Lifecycle.START,
    )
    active.submit(CollectionChannel.TELEMETRY, start)
    try:
        result = primary()
    except Exception:
        failure = on_failure or RuntimeTelemetryEvent(
            event_type=RuntimeEventType.OPERATION_FAILED,
            operation_category=OperationCategory.ASSESS,
            lifecycle=Lifecycle.FAIL,
        )
        active.submit(CollectionChannel.TELEMETRY, failure)
        raise
    success = on_success or RuntimeTelemetryEvent(
        event_type=RuntimeEventType.FEATURE_COMPLETED,
        operation_category=OperationCategory.ASSESS,
        lifecycle=Lifecycle.COMPLETE,
    )
    active.submit(CollectionChannel.TELEMETRY, success)
    return result


def session_deny_from_flag() -> TelemetrySessionConsent:
    """Process-local deny used by ``--telemetry-deny`` (does not persist)."""

    return deny_session_consent_from_cli_flag()


def adapter_decision_is_default_disabled(adapter: EngineCollectionAdapter) -> bool:
    inspect = adapter.inspect()
    return inspect["state"] == CommunityConsentState.UNDECIDED.value and not inspect[
        "transmission_authorized"
    ]


def default_disabled_decision() -> TelemetryDecision:
    return TelemetryDecision.DISABLED_BY_DEFAULT


def _export_envelope_for(channel: CollectionChannel, payload: object) -> ScopedExportEnvelope:
    if isinstance(payload, ScopedExportEnvelope):
        if payload.category != channel.value:
            raise ExportEnvelopeError("category/channel mismatch")
        return build_scoped_export(
            channel.value,
            artifact_digest=payload.artifact_digest,
            collector_kind=CollectorKind.FAKE,
            schema_advertised=True,
        )
    if not isinstance(payload, Mapping):
        raise ExportEnvelopeError("unsupported export payload")
    if payload.get("category") or payload.get("schema") or payload.get("schema_name"):
        parsed = parse_scoped_export(payload)
        if parsed.category != channel.value:
            raise ExportEnvelopeError("category/channel mismatch")
        return build_scoped_export(
            channel.value,
            artifact_digest=parsed.artifact_digest,
            collector_kind=CollectorKind.FAKE,
            schema_advertised=True,
        )
    artifact = payload.get("artifact_digest")
    if artifact is None and not payload:
        artifact = None
    elif "artifact_digest" not in payload and payload:
        raise ExportEnvelopeError("unsupported export payload")
    return build_scoped_export(
        channel.value,
        artifact_digest=str(artifact) if artifact else None,
        collector_kind=CollectorKind.FAKE,
        schema_advertised=True,
    )


def _restriction_reason(
    manifest: ExportCategoryManifest | None,
    category: str,
) -> str | None:
    if manifest is None:
        return None
    if manifest.mode is ExportMode.NONE:
        return CapabilityCheck.EXPORT_MODE_NO_EXPORT.value
    if not manifest.allows(category):
        return CapabilityCheck.CATEGORY_WITHHELD.value
    return None


def _manifest_for_adapter(
    export_mode: ExportMode | str | None,
    withheld_categories: tuple[str, ...] | None,
) -> ExportCategoryManifest | None:
    if export_mode is None:
        return None
    parsed = parse_export_mode(export_mode)
    if parsed is None:
        return None
    return resolve_export_manifest(parsed, withheld_categories=withheld_categories)


def _parse_channel(channel: CollectionChannel | str) -> CollectionChannel | None:
    if isinstance(channel, CollectionChannel):
        return channel
    text = str(channel).strip().lower()
    try:
        return CollectionChannel(text)
    except ValueError:
        return None


def _as_runtime_event(payload: object) -> RuntimeTelemetryEvent | None:
    if isinstance(payload, RuntimeTelemetryEvent):
        return payload
    return None


__all__ = [
    "CollectionChannel",
    "CollectionSubmitResult",
    "CollectionSubmitStatus",
    "EngineCollectionAdapter",
    "adapter_decision_is_default_disabled",
    "create_collection_adapter",
    "default_disabled_decision",
    "run_primary_with_isolated_collection",
    "session_deny_from_flag",
]
