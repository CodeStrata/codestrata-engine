"""Original package and signed-projection models (E13.3 / M32).

Canonical body bytes never include signature metadata. Operational signature
fields stay beside the body so redaction cannot rewrite a signed original.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata.domain.contracts.enums import ExecutionPurpose, ExportMode
from codestrata.domain.contracts.serialization import dumps_canonical
from codestrata.telemetry.export_policy import ENGINE_EXPORT_POLICY_VERSION
from codestrata.telemetry.export_projection_policy import (
    HMAC_SHA256_ALGORITHM,
    LOCAL_HMAC_VERIFICATION_PROFILE,
    ORIGINAL_PACKAGE_SCHEMA,
    PROJECTION_SCHEMA,
    PROJECTION_SCHEMA_VERSION,
    default_projection_policy,
)


class ProjectionEnvelopeError(ValueError):
    """Invalid original package or signed projection."""


class ProjectionVerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"
    STALE = "stale"
    TAMPERED = "tampered"
    WRONG_PURPOSE = "wrong_purpose"


class ReceiptLifecycle(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class SignatureMetadata:
    """Operational signature. Never part of the canonical body digest."""

    algorithm: str
    key_id: str
    purpose: str
    signature: str
    verification_profile: str = LOCAL_HMAC_VERIFICATION_PROFILE

    def to_stable_dict(self) -> dict[str, str]:
        payload = {
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "purpose": self.purpose,
            "signature": self.signature,
            "verification_profile": self.verification_profile,
        }
        return {key: payload[key] for key in sorted(payload)}


@dataclass(frozen=True, slots=True)
class OriginalExportPackage:
    """Local original. Canonical bytes are immutable after construction."""

    schema: str
    schema_version: str
    package_id: str
    package_version: str
    purpose: str
    categories: tuple[str, ...]
    artifact_digest: str
    package_digest: str
    canonical_bytes: bytes
    export_policy_version: str = ENGINE_EXPORT_POLICY_VERSION
    validity_not_before: str | None = None
    validity_not_after: str | None = None
    signature: SignatureMetadata | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "categories", tuple(sorted(set(self.categories))))
        object.__setattr__(self, "canonical_bytes", bytes(self.canonical_bytes))

    def body_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "artifact_digest": self.artifact_digest,
            "categories": list(self.categories),
            "export_policy_version": self.export_policy_version,
            "package_id": self.package_id,
            "package_version": self.package_version,
            "purpose": self.purpose,
            "schema": self.schema,
            "schema_version": self.schema_version,
            "validity_not_after": self.validity_not_after,
            "validity_not_before": self.validity_not_before,
        }
        return {key: payload[key] for key in sorted(payload)}

    def to_manifest_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "body": self.body_dict(),
            "package_digest": self.package_digest,
            "signature": None if self.signature is None else self.signature.to_stable_dict(),
        }
        return {key: payload[key] for key in sorted(payload)}

    def to_stable_json(self, *, indent: int | None = 2) -> str:
        text = json.dumps(
            self.to_manifest_dict(),
            sort_keys=True,
            indent=indent,
            ensure_ascii=True,
        )
        if indent is not None and not text.endswith("\n"):
            text += "\n"
        return text


@dataclass(frozen=True, slots=True)
class SignedExportProjection:
    """Separate redacted projection. Does not rewrite original canonical bytes."""

    schema: str
    schema_version: str
    original_digest: str
    package_digest: str
    export_mode: str
    export_policy_version: str
    projection_policy_version: str
    allowed_categories: tuple[str, ...]
    withheld_categories: tuple[str, ...]
    verification_profile: str
    purpose: str
    canonical_bytes: bytes
    signature: SignatureMetadata | None = None
    externally_verified_categories: tuple[str, ...] = ()
    unseen_evidence_externally_verified: bool = False
    transmission_performed: bool = False
    server_deletion_performed: bool = False
    server_admission_performed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_categories",
            tuple(sorted(set(self.allowed_categories))),
        )
        object.__setattr__(
            self,
            "withheld_categories",
            tuple(sorted(set(self.withheld_categories))),
        )
        object.__setattr__(
            self,
            "externally_verified_categories",
            tuple(sorted(set(self.externally_verified_categories))),
        )
        object.__setattr__(self, "canonical_bytes", bytes(self.canonical_bytes))
        if self.unseen_evidence_externally_verified:
            raise ProjectionEnvelopeError(
                "signed projection cannot claim unseen evidence was externally verified"
            )
        if self.server_deletion_performed or self.server_admission_performed:
            raise ProjectionEnvelopeError(
                "server deletion/admission is not implemented in E13.3"
            )
        withheld = set(self.withheld_categories)
        if withheld.intersection(self.externally_verified_categories):
            raise ProjectionEnvelopeError(
                "signed projection cannot claim withheld categories were externally verified"
            )

    def body_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed_categories": list(self.allowed_categories),
            "export_mode": self.export_mode,
            "export_policy_version": self.export_policy_version,
            "externally_verified_categories": list(self.externally_verified_categories),
            "original_digest": self.original_digest,
            "projection_policy_version": self.projection_policy_version,
            "purpose": self.purpose,
            "schema": self.schema,
            "schema_version": self.schema_version,
            "unseen_evidence_externally_verified": self.unseen_evidence_externally_verified,
            "verification_profile": self.verification_profile,
            "withheld_categories": list(self.withheld_categories),
        }
        return {key: payload[key] for key in sorted(payload)}

    def to_manifest_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "body": self.body_dict(),
            "package_digest": self.package_digest,
            "server_admission_performed": self.server_admission_performed,
            "server_deletion_performed": self.server_deletion_performed,
            "signature": None if self.signature is None else self.signature.to_stable_dict(),
            "transmission_performed": self.transmission_performed,
        }
        return {key: payload[key] for key in sorted(payload)}

    def to_stable_json(self, *, indent: int | None = 2) -> str:
        text = json.dumps(
            self.to_manifest_dict(),
            sort_keys=True,
            indent=indent,
            ensure_ascii=True,
        )
        if indent is not None and not text.endswith("\n"):
            text += "\n"
        return text


@dataclass(frozen=True, slots=True)
class ProjectionVerification:
    status: ProjectionVerificationStatus
    reason: str
    original_digest: str | None = None
    projection_digest: str | None = None
    trusted_key: bool = False

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "original_digest": self.original_digest,
            "projection_digest": self.projection_digest,
            "reason": self.reason,
            "status": self.status.value,
            "trusted_key": self.trusted_key,
        }
        return {key: payload[key] for key in sorted(payload)}


@dataclass(frozen=True, slots=True)
class HeadlessExportResult:
    mode: ExportMode
    original: OriginalExportPackage
    projection: SignedExportProjection
    withheld_categories: tuple[str, ...]
    allowed_categories: tuple[str, ...]
    transmission_performed: bool
    local_utility_retained: bool = True

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed_categories": list(self.allowed_categories),
            "local_utility_retained": self.local_utility_retained,
            "mode": self.mode.value,
            "original": self.original.to_manifest_dict(),
            "projection": self.projection.to_manifest_dict(),
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


def canonical_body_bytes(payload: dict[str, Any]) -> bytes:
    return dumps_canonical(payload).encode("utf-8")


def default_original_schema() -> str:
    return ORIGINAL_PACKAGE_SCHEMA


def default_projection_schema() -> str:
    return PROJECTION_SCHEMA


def default_hmac_algorithm() -> str:
    policy = default_projection_policy()
    assert policy.signature_algorithm == HMAC_SHA256_ALGORITHM
    return HMAC_SHA256_ALGORITHM


def known_execution_purpose(value: str) -> ExecutionPurpose | None:
    try:
        return ExecutionPurpose(value)
    except ValueError:
        return None


__all__ = [
    "HeadlessExportResult",
    "ORIGINAL_PACKAGE_SCHEMA",
    "OriginalExportPackage",
    "PROJECTION_SCHEMA",
    "PROJECTION_SCHEMA_VERSION",
    "ProjectionEnvelopeError",
    "ProjectionVerification",
    "ProjectionVerificationStatus",
    "ReceiptLifecycle",
    "SignatureMetadata",
    "SignedExportProjection",
    "canonical_body_bytes",
    "default_hmac_algorithm",
    "default_original_schema",
    "default_projection_schema",
    "known_execution_purpose",
]
