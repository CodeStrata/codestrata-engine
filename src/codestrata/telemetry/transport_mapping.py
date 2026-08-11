"""Map PrivacySafeTelemetryEvent → Community Cloud wire request (Slice 9.11).

Engine fields without a safe Cloud destination are omitted deliberately.
Does not import Platform models.
"""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.projection import PrivacySafeTelemetryEvent
from codestrata.telemetry.transport_models import (
    ENGINE_CLOUD_WIRE_MAPPING_CONTRACT_VERSION,
    CommunityCloudTelemetryWireRequest,
    CloudWireValidationError,
)

# Exact-safe Engine → Cloud duration mapping only. Non-exact buckets are omitted.
_DURATION_MAP: dict[str, str] = {
    "lt_1s": "under_1s",
}

_OUTCOME_MAP: dict[str, str] = {
    "success": "succeeded",
    "failure": "failed",
    "cancelled": "cancelled",
    "unknown": "unavailable",
}

# Engine fields intentionally not sent on the cloud wire.
OMITTED_ENGINE_FIELDS: frozenset[str] = frozenset(
    {
        "schema_version",
        "runtime_policy_version",
        "arch_family",
        "lifecycle",
        "failure_category",
    }
)


class TransportMappingError(CloudWireValidationError):
    """Raised when a gated event cannot be mapped safely."""


def map_privacy_safe_event_to_cloud_request(
    event: PrivacySafeTelemetryEvent,
    *,
    event_id: str,
    client_version_fallback: str = "0.2.0",
    installation_id: str | None = None,
) -> CommunityCloudTelemetryWireRequest:
    """Map a gated privacy-safe event into the Engine-owned cloud wire DTO.

    Rejects anything that is not a ``PrivacySafeTelemetryEvent``. Does not accept
    raw runtime events, dicts, bytes, or preview wrappers.

    ``installation_id`` is attached at transport time only (optional privacy-safe
    UUID). It is intentionally not part of the PrivacySafeTelemetryEvent
    projection allowlist.
    """

    if type(event) is not PrivacySafeTelemetryEvent:
        raise TransportMappingError("privacy_safe_event_required")
    fields = event.to_stable_dict()
    event_type = fields.get("event_type")
    if not isinstance(event_type, str):
        raise TransportMappingError("missing_event_type")
    client_name = fields.get("client_name", "codestrata_cli")
    if client_name != "codestrata_cli":
        raise TransportMappingError("unsupported_client")

    version = fields.get("cli_version")
    if not isinstance(version, str) or not version.strip():
        version = client_version_fallback

    platform = fields.get("os_family")
    if not isinstance(platform, str) or not platform.strip():
        platform = "other"

    properties = _map_properties(fields)
    return CommunityCloudTelemetryWireRequest(
        event_id=event_id,
        event_type=event_type,
        client_name="codestrata_cli",
        client_version=version,
        client_platform=platform,
        properties=properties or None,
        installation_id=installation_id,
    )


def _map_properties(fields: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {}

    result = fields.get("result")
    if isinstance(result, str) and result in _OUTCOME_MAP:
        props["outcome"] = _OUTCOME_MAP[result]

    duration = fields.get("duration_bucket")
    if isinstance(duration, str) and duration in _DURATION_MAP:
        props["duration_bucket"] = _DURATION_MAP[duration]

    operation = fields.get("operation_category")
    if isinstance(operation, str) and operation:
        props["feature"] = operation
        props["operation"] = "run"

    flags: list[str] = []
    if fields.get("offline_mode") is True:
        flags.append("offline")
    if fields.get("ai_used") is True:
        flags.append("ai_used")
    heads = fields.get("enabled_assessment_heads")
    if isinstance(heads, (list, tuple)):
        for item in heads:
            if isinstance(item, str) and item and len(item) <= 32:
                if "/" not in item and "\\" not in item:
                    flags.append(f"head:{item}")
    if flags:
        # Cloud allows max 8; keep deterministic sorted unique.
        props["flags"] = sorted(set(flags))[:8]

    return props


def mapping_contract_version() -> str:
    return ENGINE_CLOUD_WIRE_MAPPING_CONTRACT_VERSION


__all__ = [
    "OMITTED_ENGINE_FIELDS",
    "TransportMappingError",
    "map_privacy_safe_event_to_cloud_request",
    "mapping_contract_version",
]
