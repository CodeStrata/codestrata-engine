"""Anonymous installation identity policy (Epic 10 Slice 10.2).

Local anonymous continuity for future analytics. Not telemetry consent,
authentication, licensing, or customer identity. Collection remains disabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_ID = (
    "community-anonymous-installation-identity-policy"
)
COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION = "1.0"
COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_URN = (
    f"{COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_ID}:"
    f"{COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION}"
)

COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID = (
    "community-anonymous-installation-identity-schema"
)
COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION = "1.0"
COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_URN = (
    f"{COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID}:"
    f"{COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION}"
)

IDENTITY_FILENAME = "anonymous-installation-identity.json"

_REVIEW_STATUS = "local_only_unused_operationally_no_transmission"

_LIMITATIONS: tuple[str, ...] = (
    "anonymous_only",
    "local_persistence_only",
    "unused_operationally_in_slice_10_2",
    "used_by_runtime_analytics_local_only_in_slice_10_3",
    "used_by_assessment_analytics_local_envelope_in_slice_10_4",
    "no_transmission",
    "no_analytics_collection",
    "no_customer_identity",
    "no_authentication",
    "no_licensing",
    "independent_from_telemetry_consent",
    "independent_from_legacy_installation_id_file",
    "no_machine_fingerprint_derivation",
    "uuid_v4_random_only",
    "recover_on_corruption_creates_fresh_identity",
)


class InstallationIdentityPolicyError(ValueError):
    """Raised when installation-identity policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityAnonymousInstallationIdentityPolicy:
    """Deterministic policy for anonymous installation identity."""

    policy_id: str = COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_ID
    policy_version: str = COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION
    schema_id: str = COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID
    schema_version: str = COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION
    local_persistence_allowed: bool = True
    transmission_allowed: bool = False
    analytics_collection_required: bool = False
    telemetry_consent_coupled: bool = False
    authentication_coupled: bool = False
    licensing_coupled: bool = False
    machine_fingerprint_allowed: bool = False
    recover_on_corruption: bool = True
    regenerate_automatically: bool = False
    filename: str = IDENTITY_FILENAME
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    @property
    def schema_token(self) -> str:
        return f"{self.schema_id}:{self.schema_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_ID:
            raise InstallationIdentityPolicyError("unsupported identity policy id")
        if self.policy_version != COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION:
            raise InstallationIdentityPolicyError("unsupported identity policy version")
        if self.schema_id != COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID:
            raise InstallationIdentityPolicyError("unsupported identity schema id")
        if self.schema_version != COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION:
            raise InstallationIdentityPolicyError("unsupported identity schema version")
        if self.review_status != _REVIEW_STATUS:
            raise InstallationIdentityPolicyError("unsupported identity review_status")
        if not self.local_persistence_allowed:
            raise InstallationIdentityPolicyError("local_persistence_allowed must be true")
        if self.transmission_allowed:
            raise InstallationIdentityPolicyError("transmission_allowed must be false")
        if self.analytics_collection_required:
            raise InstallationIdentityPolicyError(
                "analytics_collection_required must be false"
            )
        if self.telemetry_consent_coupled:
            raise InstallationIdentityPolicyError(
                "telemetry_consent_coupled must be false"
            )
        if self.authentication_coupled:
            raise InstallationIdentityPolicyError("authentication_coupled must be false")
        if self.licensing_coupled:
            raise InstallationIdentityPolicyError("licensing_coupled must be false")
        if self.machine_fingerprint_allowed:
            raise InstallationIdentityPolicyError(
                "machine_fingerprint_allowed must be false"
            )
        if self.regenerate_automatically:
            raise InstallationIdentityPolicyError(
                "regenerate_automatically must be false"
            )
        if self.filename != IDENTITY_FILENAME:
            raise InstallationIdentityPolicyError("unsupported identity filename")

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "analytics_collection_required": self.analytics_collection_required,
            "authentication_coupled": self.authentication_coupled,
            "filename": self.filename,
            "licensing_coupled": self.licensing_coupled,
            "limitations": list(self.limitations),
            "local_persistence_allowed": self.local_persistence_allowed,
            "machine_fingerprint_allowed": self.machine_fingerprint_allowed,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "recover_on_corruption": self.recover_on_corruption,
            "regenerate_automatically": self.regenerate_automatically,
            "review_status": self.review_status,
            "schema_id": self.schema_id,
            "schema_token": self.schema_token,
            "schema_version": self.schema_version,
            "telemetry_consent_coupled": self.telemetry_consent_coupled,
            "transmission_allowed": self.transmission_allowed,
        }

    @classmethod
    def default(cls) -> CommunityAnonymousInstallationIdentityPolicy:
        return cls()


def default_installation_identity_policy() -> CommunityAnonymousInstallationIdentityPolicy:
    return CommunityAnonymousInstallationIdentityPolicy.default()


__all__ = [
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_ID",
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_URN",
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION",
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID",
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_URN",
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION",
    "IDENTITY_FILENAME",
    "CommunityAnonymousInstallationIdentityPolicy",
    "InstallationIdentityPolicyError",
    "default_installation_identity_policy",
]
