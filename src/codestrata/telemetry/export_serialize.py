"""Serialize permitted evidence/graph export JSON (E13.2).

Local construction only. Does not transmit, does not claim server readiness,
and does not embed findings, snippets, or repository names.
"""

from __future__ import annotations

from collections.abc import Mapping

from codestrata.domain.contracts.serialization import (
    PLACEHOLDER_DIGEST,
    digest_canonical,
    require_content_digest,
    require_supported_major,
)
from codestrata.telemetry.canaries import (
    collection_surface_violations,
    exceeds_serialization_budget,
)
from codestrata.telemetry.export_models import (
    EXPORT_NOTICE,
    CollectorKind,
    ExportCategory,
    ExportEnvelopeError,
    ScopedExportEnvelope,
    ServerReadiness,
    mapping_has_prohibited_export_fields,
    parse_export_category,
    schema_for_category,
)
from codestrata.telemetry.export_policy import (
    EngineCollectionExportPolicy,
    default_export_policy,
)


def build_scoped_export(
    category: ExportCategory | str,
    *,
    artifact_digest: str | None = None,
    collector_kind: CollectorKind | str = CollectorKind.NONE,
    schema_advertised: bool = False,
    policy: EngineCollectionExportPolicy | None = None,
) -> ScopedExportEnvelope:
    """Build a local preview envelope. Never transmits."""

    active = policy or default_export_policy()
    parsed = parse_export_category(category)
    if parsed is None:
        raise ExportEnvelopeError("unsupported export category")
    digest = _normalize_artifact_digest(artifact_digest)
    schema = active.schema_for_category(parsed.value)
    kind = (
        collector_kind.value
        if isinstance(collector_kind, CollectorKind)
        else str(collector_kind)
    )
    notices = _notices_for(advertised=schema_advertised, collector_kind=kind)
    limitations = tuple(active.limitations)
    content = {
        "artifact_digest": digest,
        "category": parsed.value,
        "schema": schema,
        "schema_version": active.export_schema_version,
    }
    bound = digest_canonical(content)
    envelope = ScopedExportEnvelope(
        schema=schema,
        schema_name=schema,
        schema_version=active.export_schema_version,
        category=parsed.value,
        digest=bound,
        notice=EXPORT_NOTICE,
        artifact_digest=digest,
        export_policy_version=active.policy_version,
        export_policy=active.policy_token,
        collector_kind=kind,
        server_readiness=ServerReadiness.NOT_READY.value,
        transmission_performed=False,
        notices=notices,
        limitations=limitations,
        withheld_categories=(),
    )
    encoded = envelope.to_stable_json(indent=None)
    if exceeds_serialization_budget(
        envelope.to_stable_dict(),
        max_bytes=active.max_export_size_bytes,
    ):
        raise ExportEnvelopeError("export exceeds maximum size")
    if len(encoded.encode("utf-8")) > active.max_export_size_bytes:
        raise ExportEnvelopeError("export exceeds maximum size")
    return envelope


def parse_scoped_export(
    payload: object,
    *,
    policy: EngineCollectionExportPolicy | None = None,
) -> ScopedExportEnvelope:
    """Admit a mapping as a permitted envelope. Reject unknown/prohibited fields."""

    active = policy or default_export_policy()
    if isinstance(payload, ScopedExportEnvelope):
        _assert_envelope_honest(payload, policy=active)
        return payload
    if not isinstance(payload, Mapping):
        raise ExportEnvelopeError("export payload must be a mapping")
    prohibited = mapping_has_prohibited_export_fields(payload)
    if prohibited:
        raise ExportEnvelopeError(f"prohibited or unknown export fields: {prohibited}")
    violations = collection_surface_violations(dict(payload))
    if violations:
        raise ExportEnvelopeError("prohibited data in export payload")
    category = parse_export_category(str(payload.get("category", "")))
    if category is None:
        raise ExportEnvelopeError("unsupported export category")
    schema = str(payload.get("schema") or payload.get("schema_name") or "")
    expected = schema_for_category(category)
    if schema and schema != expected:
        raise ExportEnvelopeError("unsupported export schema")
    version = str(payload.get("schema_version") or active.export_schema_version)
    try:
        require_supported_major(version)
    except ValueError as error:
        raise ExportEnvelopeError("unsupported export schema version") from error
    if version != active.export_schema_version:
        raise ExportEnvelopeError("unsupported export schema version")
    artifact = payload.get("artifact_digest")
    kind = str(payload.get("collector_kind") or CollectorKind.NONE.value)
    advertised = kind == CollectorKind.FAKE.value
    return build_scoped_export(
        category,
        artifact_digest=str(artifact) if artifact else None,
        collector_kind=kind,
        schema_advertised=advertised,
        policy=active,
    )


def _assert_envelope_honest(
    envelope: ScopedExportEnvelope,
    *,
    policy: EngineCollectionExportPolicy,
) -> None:
    if envelope.transmission_performed:
        raise ExportEnvelopeError("envelope must not claim transmission")
    if envelope.server_readiness != ServerReadiness.NOT_READY.value:
        raise ExportEnvelopeError("envelope must not claim server readiness")
    if envelope.schema != policy.schema_for_category(envelope.category):
        raise ExportEnvelopeError("unsupported export schema")
    expected = digest_canonical(envelope.content_slice())
    if envelope.digest != expected:
        raise ExportEnvelopeError("digest does not match permitted content slice")


def _normalize_artifact_digest(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return PLACEHOLDER_DIGEST
    try:
        return require_content_digest(value, label="artifact_digest")
    except ValueError as error:
        raise ExportEnvelopeError("artifact_digest must be a pinned sha256 hex digest") from error


def _notices_for(*, advertised: bool, collector_kind: str) -> tuple[str, ...]:
    notices = {
        EXPORT_NOTICE,
        "local_preview_only",
        "payload_construction_only",
        "server_not_ready",
        "not_a_live_v2_call",
    }
    if advertised and collector_kind == CollectorKind.FAKE.value:
        notices.add("collector_advertised_local_fake_only")
    else:
        notices.add("collector_has_not_advertised_schema")
    return tuple(sorted(notices))


__all__ = [
    "build_scoped_export",
    "parse_scoped_export",
]
