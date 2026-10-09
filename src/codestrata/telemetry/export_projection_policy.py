"""Versioned signed-projection / export-mode policy (E13.3 / M32).

Local original canonical bytes stay immutable. A separate projection lists
the original digest, allowed/withheld categories, export-policy version and
signature metadata that is not part of the canonical body. No-export performs
no collector transfer. Live server deletion/admission is follow-on work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.domain.contracts.enums import ExportMode
from codestrata.telemetry.export_policy import ENGINE_EXPORT_POLICY_VERSION

ENGINE_PROJECTION_POLICY_ID = "engine-export-projection-policy"
ENGINE_PROJECTION_POLICY_VERSION = "1.0"
ENGINE_PROJECTION_POLICY_URN = (
    f"{ENGINE_PROJECTION_POLICY_ID}:{ENGINE_PROJECTION_POLICY_VERSION}"
)

ORIGINAL_PACKAGE_SCHEMA = "codestrata.export-original.v1"
PROJECTION_SCHEMA = "codestrata.export-projection.v1"
PROJECTION_SCHEMA_VERSION = "1.0.0"

LOCAL_HMAC_VERIFICATION_PROFILE = "codestrata.export-projection.local-hmac.v1"
HMAC_SHA256_ALGORITHM = "hmac-sha256"

DEFAULT_MAX_PROJECTION_SIZE_BYTES = 8192
DEFAULT_RECEIPT_TTL_SECONDS = 3600

_REVIEW_STATUS = "signed_projection_local_hmac_no_server_deletion"

_LIMITATIONS: tuple[str, ...] = (
    "original_canonical_bytes_immutable",
    "redaction_produces_separate_projection",
    "signature_metadata_outside_canonical_body",
    "no_export_performs_no_transfer",
    "signed_projection_cannot_claim_unseen_verified",
    "local_hmac_is_not_public_sigstore",
    "fake_collector_revocation_is_local_only",
    "server_deletion_admission_not_this_story",
    "no_public_private_data_logging",
    "no_consent_local_utility_preserved",
    "no_community_api_s3_infrastructure_edits",
)


class ProjectionPolicyError(ValueError):
    """Raised when the E13.3 projection policy invariants fail."""


@dataclass(frozen=True, slots=True)
class EngineExportProjectionPolicy:
    """Local signed projections: preserve original, never claim live admission."""

    policy_id: str = ENGINE_PROJECTION_POLICY_ID
    policy_version: str = ENGINE_PROJECTION_POLICY_VERSION
    export_policy_version: str = ENGINE_EXPORT_POLICY_VERSION
    original_schema: str = ORIGINAL_PACKAGE_SCHEMA
    projection_schema: str = PROJECTION_SCHEMA
    schema_version: str = PROJECTION_SCHEMA_VERSION
    verification_profile: str = LOCAL_HMAC_VERIFICATION_PROFILE
    signature_algorithm: str = HMAC_SHA256_ALGORITHM
    mutate_original_canonical_bytes: bool = False
    no_export_transfers: bool = False
    unseen_may_claim_external_verification: bool = False
    public_private_data_logging: bool = False
    public_sigstore_required: bool = False
    server_deletion_implemented: bool = False
    server_admission_implemented: bool = False
    preview_signer_authorizes_production: bool = False
    max_projection_size_bytes: int = DEFAULT_MAX_PROJECTION_SIZE_BYTES
    default_receipt_ttl_seconds: int = DEFAULT_RECEIPT_TTL_SECONDS
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != ENGINE_PROJECTION_POLICY_ID:
            raise ProjectionPolicyError("unsupported projection policy id")
        if self.policy_version != ENGINE_PROJECTION_POLICY_VERSION:
            raise ProjectionPolicyError("unsupported projection policy version")
        if self.export_policy_version != ENGINE_EXPORT_POLICY_VERSION:
            raise ProjectionPolicyError("projection must bind export-policy 1.0")
        if self.mutate_original_canonical_bytes:
            raise ProjectionPolicyError("mutate_original_canonical_bytes must be false")
        if self.no_export_transfers:
            raise ProjectionPolicyError("no_export_transfers must be false")
        if self.unseen_may_claim_external_verification:
            raise ProjectionPolicyError(
                "unseen_may_claim_external_verification must be false"
            )
        if self.public_private_data_logging:
            raise ProjectionPolicyError("public_private_data_logging must be false")
        if self.public_sigstore_required:
            raise ProjectionPolicyError("public_sigstore_required must be false")
        if self.server_deletion_implemented:
            raise ProjectionPolicyError("server_deletion_implemented must be false")
        if self.server_admission_implemented:
            raise ProjectionPolicyError("server_admission_implemented must be false")
        if self.preview_signer_authorizes_production:
            raise ProjectionPolicyError(
                "preview_signer_authorizes_production must be false"
            )
        if self.verification_profile != LOCAL_HMAC_VERIFICATION_PROFILE:
            raise ProjectionPolicyError("unsupported verification_profile")
        if self.signature_algorithm != HMAC_SHA256_ALGORITHM:
            raise ProjectionPolicyError("unsupported signature_algorithm")
        if self.original_schema != ORIGINAL_PACKAGE_SCHEMA:
            raise ProjectionPolicyError("unsupported original schema")
        if self.projection_schema != PROJECTION_SCHEMA:
            raise ProjectionPolicyError("unsupported projection schema")
        if self.schema_version != PROJECTION_SCHEMA_VERSION:
            raise ProjectionPolicyError("unsupported projection schema version")
        if self.max_projection_size_bytes <= 0:
            raise ProjectionPolicyError("max_projection_size_bytes must be positive")
        if self.default_receipt_ttl_seconds <= 0:
            raise ProjectionPolicyError("default_receipt_ttl_seconds must be positive")
        if self.review_status != _REVIEW_STATUS:
            raise ProjectionPolicyError("unsupported review_status")

    def requires_transfer(self, mode: ExportMode) -> bool:
        if mode is ExportMode.NONE:
            return False
        return True

    @classmethod
    def default(cls) -> EngineExportProjectionPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        payload = {
            "default_receipt_ttl_seconds": self.default_receipt_ttl_seconds,
            "export_policy_version": self.export_policy_version,
            "limitations": list(self.limitations),
            "max_projection_size_bytes": self.max_projection_size_bytes,
            "mutate_original_canonical_bytes": self.mutate_original_canonical_bytes,
            "no_export_transfers": self.no_export_transfers,
            "original_schema": self.original_schema,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "preview_signer_authorizes_production": (
                self.preview_signer_authorizes_production
            ),
            "projection_schema": self.projection_schema,
            "public_private_data_logging": self.public_private_data_logging,
            "public_sigstore_required": self.public_sigstore_required,
            "review_status": self.review_status,
            "schema_version": self.schema_version,
            "server_admission_implemented": self.server_admission_implemented,
            "server_deletion_implemented": self.server_deletion_implemented,
            "signature_algorithm": self.signature_algorithm,
            "unseen_may_claim_external_verification": (
                self.unseen_may_claim_external_verification
            ),
            "verification_profile": self.verification_profile,
        }
        return {key: payload[key] for key in sorted(payload)}


def default_projection_policy() -> EngineExportProjectionPolicy:
    return EngineExportProjectionPolicy.default()


__all__ = [
    "DEFAULT_MAX_PROJECTION_SIZE_BYTES",
    "DEFAULT_RECEIPT_TTL_SECONDS",
    "ENGINE_PROJECTION_POLICY_ID",
    "ENGINE_PROJECTION_POLICY_URN",
    "ENGINE_PROJECTION_POLICY_VERSION",
    "EngineExportProjectionPolicy",
    "HMAC_SHA256_ALGORITHM",
    "LOCAL_HMAC_VERIFICATION_PROFILE",
    "ORIGINAL_PACKAGE_SCHEMA",
    "PROJECTION_SCHEMA",
    "PROJECTION_SCHEMA_VERSION",
    "ProjectionPolicyError",
    "default_projection_policy",
]
