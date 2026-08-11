"""Immutable pre-transport privacy gate result model (Slice 9.10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.pre_transport_errors import (
    PreTransportPrivacyStatus,
    PreTransportReasonCode,
)
from codestrata.telemetry.projection import PrivacySafeTelemetryEvent


@dataclass(frozen=True, slots=True)
class PreTransportPrivacyResult:
    """Bounded gate outcome — never includes payloads, values, or exceptions."""

    status: str
    accepted: bool
    safe_reason_code: str
    event_type: str | None = None
    schema_version: str | None = None
    runtime_policy_version: str | None = None
    privacy_policy_version: str = "1.0"
    catalog_schema_version: str | None = None
    field_count: int = 0
    serialized_size_bucket: str = "lt_256b"
    limitation_codes: tuple[str, ...] = ()
    accepted_event: PrivacySafeTelemetryEvent | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "limitation_codes", tuple(sorted(set(self.limitation_codes)))
        )
        if self.accepted and self.accepted_event is None:
            raise ValueError("accepted result requires accepted_event")
        if not self.accepted and self.accepted_event is not None:
            raise ValueError("rejected result must not carry accepted_event")

    def to_stable_dict(self) -> dict[str, Any]:
        # Never serialize accepted_event payloads into diagnostics JSON.
        return {
            "accepted": self.accepted,
            "catalog_schema_version": self.catalog_schema_version,
            "event_type": self.event_type,
            "field_count": self.field_count,
            "limitation_codes": list(self.limitation_codes),
            "privacy_policy_version": self.privacy_policy_version,
            "runtime_policy_version": self.runtime_policy_version,
            "safe_reason_code": self.safe_reason_code,
            "schema_version": self.schema_version,
            "serialized_size_bucket": self.serialized_size_bucket,
            "status": self.status,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def accepted_result(
    *,
    event: PrivacySafeTelemetryEvent,
    event_type: str,
    schema_version: str,
    runtime_policy_version: str,
    privacy_policy_version: str,
    catalog_schema_version: str,
    field_count: int,
    serialized_size_bucket: str,
    limitations: tuple[str, ...],
) -> PreTransportPrivacyResult:
    return PreTransportPrivacyResult(
        status=PreTransportPrivacyStatus.ACCEPTED.value,
        accepted=True,
        safe_reason_code=PreTransportReasonCode.ACCEPTED.value,
        event_type=event_type,
        schema_version=schema_version,
        runtime_policy_version=runtime_policy_version,
        privacy_policy_version=privacy_policy_version,
        catalog_schema_version=catalog_schema_version,
        field_count=field_count,
        serialized_size_bucket=serialized_size_bucket,
        limitation_codes=limitations,
        accepted_event=event,
    )


def rejected_result(
    *,
    status: PreTransportPrivacyStatus,
    reason: PreTransportReasonCode,
    privacy_policy_version: str,
    limitations: tuple[str, ...],
    event_type: str | None = None,
    schema_version: str | None = None,
    runtime_policy_version: str | None = None,
    catalog_schema_version: str | None = None,
    field_count: int = 0,
    serialized_size_bucket: str = "lt_256b",
) -> PreTransportPrivacyResult:
    return PreTransportPrivacyResult(
        status=status.value,
        accepted=False,
        safe_reason_code=reason.value,
        event_type=event_type,
        schema_version=schema_version,
        runtime_policy_version=runtime_policy_version,
        privacy_policy_version=privacy_policy_version,
        catalog_schema_version=catalog_schema_version,
        field_count=field_count,
        serialized_size_bucket=serialized_size_bucket,
        limitation_codes=limitations,
        accepted_event=None,
    )


__all__ = [
    "PreTransportPrivacyResult",
    "accepted_result",
    "rejected_result",
]
