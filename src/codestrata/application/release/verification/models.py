"""Release verification statuses, roles and results (E14.1).

Statuses are specific cryptographic outcomes, not a mocked signature boolean.
Signature bytes stay out of canonical package bodies and logs.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.contracts.enums import ExecutionPurpose, FreshnessState


class SignerRole(StrEnum):
    """Public distribution and private result signing are distinct roles."""

    PUBLIC_DISTRIBUTION = "public_distribution"
    PRIVATE_RESULT = "private_result"


class VerificationProfileId(StrEnum):
    SIGSTORE_PUBLIC = "codestrata.release.sigstore-public.v1"
    OFFLINE_SELF_MANAGED = "codestrata.release.offline-self-managed-key.v1"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    TAMPERED = "tampered"
    WRONG_ISSUER = "wrong_issuer"
    WRONG_PURPOSE = "wrong_purpose"
    EXPIRED = "expired"
    UNSUPPORTED = "unsupported"
    STALE = "stale"
    REVOKED = "revoked"
    REJECTED = "rejected"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


class VerificationResult(BaseModel):
    """One profile evaluation. ``ok`` is derived from status, never the sole check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: VerificationStatus
    reason: str
    profile_id: str
    signer_role: SignerRole
    requested_purpose: ExecutionPurpose
    freshness: FreshnessState
    trusted: bool = False
    artifact_digest: str | None = None
    package_digest: str | None = None
    identity: str | None = None
    issuer: str | None = None
    transparency_log_used: bool = False
    limitations: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is VerificationStatus.VERIFIED


class OfflineTrustEntry(BaseModel):
    """Public half of a self-managed key. Private key material is forbidden."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key_id: str
    public_key_pem: str
    purpose: ExecutionPurpose
    role: SignerRole = SignerRole.PRIVATE_RESULT
    not_after: str | None = None


class RevocationInventory(BaseModel):
    """Offline revocation list. Freshness limits apply; this is not instant CRL."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_updated: str
    revoked_key_ids: tuple[str, ...] = ()
    instant_revocation: bool = False


class VerifyRequest(BaseModel):
    """Offline verification inputs. Network fetch URLs are never followed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: VerificationProfileId
    signer_role: SignerRole
    requested_purpose: ExecutionPurpose
    package: dict[str, Any]
    artifact_bytes: bytes = b""
    bundle: dict[str, Any]
    evaluation_time: str
    expected_identity: str | None = None
    expected_issuer: str | None = None
    trust_root_pem: str | None = None
    rekor_public_pem: str | None = None
    trust_store: tuple[OfflineTrustEntry, ...] = ()
    revocation: RevocationInventory | None = None
    key_id: str | None = None


__all__ = [
    "OfflineTrustEntry",
    "RevocationInventory",
    "SignerRole",
    "VerificationProfileId",
    "VerificationResult",
    "VerificationStatus",
    "VerifyRequest",
]
