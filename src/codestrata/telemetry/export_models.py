"""Scoped evidence/graph export envelope and collector capability models (E13.2)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from codestrata.telemetry.export_policy import (
    ENGINE_EXPORT_POLICY_VERSION,
    EVIDENCE_EXPORT_SCHEMA,
    EXPORT_SCHEMA_VERSION,
    GRAPH_EXPORT_SCHEMA,
    default_export_policy,
)

EXPORT_NOTICE = "local_preview_server_not_ready"

ALLOWED_EXPORT_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "artifact_digest",
        "category",
        "collector_kind",
        "digest",
        "export_policy_version",
        "limitations",
        "notice",
        "notices",
        "export_policy",
        "schema",
        "schema_name",
        "schema_version",
        "server_readiness",
        "transmission_performed",
        "withheld_categories",
    }
)

PROHIBITED_EXPORT_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "findings",
        "finding",
        "snippet",
        "snippets",
        "source_code",
        "repository_name",
        "repository_url",
        "repo_name",
        "nodes",
        "edges",
        "evidence",
        "graph",
    }
)


class ExportCategory(StrEnum):
    EVIDENCE = "evidence"
    GRAPH = "graph"


class CollectorKind(StrEnum):
    NONE = "none"
    FAKE = "fake"
    UNADVERTISED_LIVE = "unadvertised_live"


class ServerReadiness(StrEnum):
    NOT_READY = "not_ready"


class CapabilityCheck(StrEnum):
    PASSED = "passed"
    SCHEMA_UNADVERTISED = "schema_unadvertised"
    SCHEMA_UNSUPPORTED = "schema_unsupported"
    PARTIAL_ADVERTISEMENT = "partial_advertisement"
    RECEIPTS_UNAVAILABLE = "receipts_unavailable"
    LIVE_V2_FORBIDDEN = "live_v2_forbidden"
    NOT_FAKE_LOCAL = "not_fake_local"
    EXPORT_MODE_NO_EXPORT = "export_mode_no_export"
    CATEGORY_WITHHELD = "category_withheld"
    RECEIPT_REVOKED = "receipt_revoked"
    RECEIPT_EXPIRED = "receipt_expired"


class ExportEnvelopeError(ValueError):
    """Invalid scoped export envelope."""


@dataclass(frozen=True, slots=True)
class ScopedExportEnvelope:
    """Permitted evidence/graph JSON: schema, digest, notice, category only."""

    schema: str
    schema_version: str
    category: str
    digest: str
    notice: str
    artifact_digest: str
    schema_name: str = ""
    export_policy_version: str = ENGINE_EXPORT_POLICY_VERSION
    export_policy: str = ""
    collector_kind: str = CollectorKind.NONE.value
    server_readiness: str = ServerReadiness.NOT_READY.value
    transmission_performed: bool = False
    notices: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    withheld_categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_name", self.schema_name or self.schema)
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        object.__setattr__(
            self,
            "withheld_categories",
            tuple(sorted(set(self.withheld_categories))),
        )
        if self.transmission_performed:
            raise ExportEnvelopeError("transmission_performed must be false for local preview")
        if self.server_readiness != ServerReadiness.NOT_READY.value:
            raise ExportEnvelopeError("server_readiness must be not_ready")

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "artifact_digest": self.artifact_digest,
            "category": self.category,
            "collector_kind": self.collector_kind,
            "digest": self.digest,
            "export_policy": self.export_policy,
            "export_policy_version": self.export_policy_version,
            "limitations": list(self.limitations),
            "notice": self.notice,
            "notices": list(self.notices),
            "schema": self.schema,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "server_readiness": self.server_readiness,
            "transmission_performed": self.transmission_performed,
            "withheld_categories": list(self.withheld_categories),
        }
        return {key: payload[key] for key in sorted(payload)}

    def to_stable_json(self, *, indent: int | None = 2) -> str:
        text = json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            indent=indent,
            ensure_ascii=True,
        )
        if indent is not None and not text.endswith("\n"):
            text += "\n"
        return text

    def content_slice(self) -> dict[str, str]:
        return {
            "artifact_digest": self.artifact_digest,
            "category": self.category,
            "schema": self.schema,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class CollectorCapability:
    kind: str = CollectorKind.NONE.value
    advertised_schemas: tuple[str, ...] = ()
    receipts_supported: bool = False
    live_v2_calls: bool = False
    server_ready: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "advertised_schemas",
            tuple(sorted(set(self.advertised_schemas))),
        )
        if self.live_v2_calls:
            raise ExportEnvelopeError("live_v2_calls must be false")
        if self.server_ready:
            raise ExportEnvelopeError("server_ready must be false in E13.2")

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "advertised_schemas": list(self.advertised_schemas),
            "kind": self.kind,
            "live_v2_calls": self.live_v2_calls,
            "receipts_supported": self.receipts_supported,
            "server_ready": self.server_ready,
        }
        return {key: payload[key] for key in sorted(payload)}

    @classmethod
    def none(cls) -> CollectorCapability:
        return cls()


@dataclass(frozen=True, slots=True)
class CollectorReceipt:
    receipt_id: str
    schema: str
    category: str
    accepted: bool
    capability_check: str
    live_v2_invoked: bool = False
    server_ready: bool = False
    receipt_status: str = ""
    issued_at_unix: int | None = None
    expires_at_unix: int | None = None
    revoked: bool = False
    server_deletion_performed: bool = False
    server_admission_performed: bool = False

    def __post_init__(self) -> None:
        if self.live_v2_invoked:
            raise ExportEnvelopeError("receipt must not record a live v2 invocation")
        if self.server_ready:
            raise ExportEnvelopeError("receipt must not claim server readiness")
        if self.server_deletion_performed or self.server_admission_performed:
            raise ExportEnvelopeError("server deletion/admission is not implemented in E13.3")
        status = self.receipt_status
        if not status:
            if self.revoked:
                status = "revoked"
            elif self.accepted:
                status = "accepted"
            else:
                status = "rejected"
            object.__setattr__(self, "receipt_status", status)
        if self.revoked and self.accepted:
            raise ExportEnvelopeError("revoked receipt cannot be accepted")

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "accepted": self.accepted,
            "capability_check": self.capability_check,
            "category": self.category,
            "expires_at_unix": self.expires_at_unix,
            "issued_at_unix": self.issued_at_unix,
            "live_v2_invoked": self.live_v2_invoked,
            "receipt_id": self.receipt_id,
            "receipt_status": self.receipt_status,
            "revoked": self.revoked,
            "schema": self.schema,
            "server_admission_performed": self.server_admission_performed,
            "server_deletion_performed": self.server_deletion_performed,
            "server_ready": self.server_ready,
        }
        return {key: payload[key] for key in sorted(payload)}


@dataclass(frozen=True, slots=True)
class ReceiptDecision:
    receipt_id: str
    status: str
    accepted: bool
    reason: str
    server_deletion_performed: bool = False
    server_admission_performed: bool = False

    def __post_init__(self) -> None:
        if self.server_deletion_performed or self.server_admission_performed:
            raise ExportEnvelopeError("server deletion/admission is not implemented in E13.3")

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "accepted": self.accepted,
            "reason": self.reason,
            "receipt_id": self.receipt_id,
            "server_admission_performed": self.server_admission_performed,
            "server_deletion_performed": self.server_deletion_performed,
            "status": self.status,
        }
        return {key: payload[key] for key in sorted(payload)}


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    allowed: bool
    reason: str
    advertised: bool = False

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "advertised": self.advertised,
            "allowed": self.allowed,
            "reason": self.reason,
        }
        return {key: payload[key] for key in sorted(payload)}


@runtime_checkable
class CollectionCollector(Protocol):
    """Local collector port. Implementations must not perform live v2 HTTP."""

    def capability(self) -> CollectorCapability: ...

    def accept(self, envelope: ScopedExportEnvelope) -> CollectorReceipt: ...


def schema_for_category(category: ExportCategory | str) -> str:
    parsed = parse_export_category(category)
    if parsed is None:
        raise ExportEnvelopeError("unsupported export category")
    policy = default_export_policy()
    return policy.schema_for_category(parsed.value)


def parse_export_category(category: ExportCategory | str) -> ExportCategory | None:
    if isinstance(category, ExportCategory):
        return category
    text = str(category).strip().lower()
    try:
        return ExportCategory(text)
    except ValueError:
        return None


def known_export_schemas() -> frozenset[str]:
    return frozenset({EVIDENCE_EXPORT_SCHEMA, GRAPH_EXPORT_SCHEMA})


def is_supported_export_schema(schema: str, *, version: str = EXPORT_SCHEMA_VERSION) -> bool:
    if schema not in known_export_schemas():
        return False
    return version == EXPORT_SCHEMA_VERSION


def mapping_has_prohibited_export_fields(payload: Mapping[str, Any]) -> tuple[str, ...]:
    hits = {str(key) for key in payload if str(key) in PROHIBITED_EXPORT_FIELD_NAMES}
    extra = {
        str(key)
        for key in payload
        if str(key) not in ALLOWED_EXPORT_FIELD_NAMES
        and str(key) not in PROHIBITED_EXPORT_FIELD_NAMES
    }
    return tuple(sorted(hits | extra))


__all__ = [
    "ALLOWED_EXPORT_FIELD_NAMES",
    "CapabilityCheck",
    "CapabilityDecision",
    "CollectionCollector",
    "CollectorCapability",
    "CollectorKind",
    "CollectorReceipt",
    "EXPORT_NOTICE",
    "ExportCategory",
    "ExportEnvelopeError",
    "PROHIBITED_EXPORT_FIELD_NAMES",
    "ReceiptDecision",
    "ScopedExportEnvelope",
    "ServerReadiness",
    "is_supported_export_schema",
    "known_export_schemas",
    "mapping_has_prohibited_export_fields",
    "parse_export_category",
    "schema_for_category",
]
