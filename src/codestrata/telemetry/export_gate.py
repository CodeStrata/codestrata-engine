"""Receipt and capability checks for evidence/graph upload (E13.2).

Upload remains unavailable unless a local fake collector advertises the
supported schema and receipts. Live collectors are never probed with v2 calls.
"""

from __future__ import annotations

from codestrata.telemetry.export_models import (
    CapabilityCheck,
    CapabilityDecision,
    CollectionCollector,
    CollectorCapability,
    CollectorKind,
    ExportCategory,
    known_export_schemas,
    parse_export_category,
)
from codestrata.telemetry.export_policy import EngineCollectionExportPolicy, default_export_policy


def collector_capability(collector: CollectionCollector | None) -> CollectorCapability:
    if collector is None:
        return CollectorCapability.none()
    capability = collector.capability()
    if capability.live_v2_calls or capability.server_ready:
        return CollectorCapability.none()
    return capability


def evaluate_export_capability(
    collector: CollectionCollector | None,
    category: ExportCategory | str,
    *,
    policy: EngineCollectionExportPolicy | None = None,
) -> CapabilityDecision:
    """Decide whether evidence/graph upload may be offered to a collector."""

    active = policy or default_export_policy()
    parsed = parse_export_category(category)
    if parsed is None:
        return CapabilityDecision(
            allowed=False,
            reason=CapabilityCheck.SCHEMA_UNSUPPORTED.value,
            advertised=False,
        )
    schema = active.schema_for_category(parsed.value)
    capability = collector_capability(collector)
    advertised = schema in capability.advertised_schemas

    if capability.live_v2_calls:
        return CapabilityDecision(
            allowed=False,
            reason=CapabilityCheck.LIVE_V2_FORBIDDEN.value,
            advertised=advertised,
        )
    if capability.kind == CollectorKind.UNADVERTISED_LIVE.value:
        return CapabilityDecision(
            allowed=False,
            reason=CapabilityCheck.NOT_FAKE_LOCAL.value,
            advertised=False,
        )
    if capability.kind != CollectorKind.FAKE.value:
        return CapabilityDecision(
            allowed=False,
            reason=CapabilityCheck.SCHEMA_UNADVERTISED.value,
            advertised=False,
        )
    if advertised:
        if not capability.receipts_supported:
            return CapabilityDecision(
                allowed=False,
                reason=CapabilityCheck.RECEIPTS_UNAVAILABLE.value,
                advertised=True,
            )
        return CapabilityDecision(
            allowed=True,
            reason=CapabilityCheck.PASSED.value,
            advertised=True,
        )
    return CapabilityDecision(
        allowed=False,
        reason=_unadvertised_reason(capability.advertised_schemas, schema),
        advertised=False,
    )


def _unadvertised_reason(advertised: tuple[str, ...], requested: str) -> str:
    if not advertised:
        return CapabilityCheck.SCHEMA_UNADVERTISED.value
    known = known_export_schemas()
    if any(item not in known for item in advertised):
        return CapabilityCheck.SCHEMA_UNSUPPORTED.value
    if any(item != requested for item in advertised):
        return CapabilityCheck.PARTIAL_ADVERTISEMENT.value
    return CapabilityCheck.SCHEMA_UNADVERTISED.value


__all__ = [
    "collector_capability",
    "evaluate_export_capability",
]
