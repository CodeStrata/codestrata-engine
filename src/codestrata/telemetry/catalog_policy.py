"""Independent public telemetry catalog policy (Slice 9.8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_ID = (
    "community-telemetry-public-catalog-policy"
)
COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_VERSION}"
)

PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_NAME = "privacy-first-telemetry-catalog"
PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION = "1.0.0"
PRIVACY_FIRST_TELEMETRY_CATALOG_ID = "codestrata-privacy-first-telemetry-catalog"

_REVIEW_STATUS = "authoritative_catalog_no_transmission"

_LIMITATIONS: tuple[str, ...] = (
    "derived_from_typed_runtime_models",
    "transmission_not_operational",
    "installation_identity_not_used",
    "consent_cannot_expand_fields",
    "legacy_events_excluded",
    "extension_clients_deferred",
    "preview_command_available",
    "pre_transport_privacy_gate_required",
    "community_cloud_contracts_separate",
    "http_transport_requires_explicit_configuration",
    "cloud_mapping_independently_versioned",
    "runtime_event_schema_remains_1_0",
)


class CatalogPolicyError(ValueError):
    """Raised when catalog-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryPublicCatalogPolicy:
    """Versioned public catalog reporting contract."""

    policy_id: str = COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_VERSION
    catalog_id: str = PRIVACY_FIRST_TELEMETRY_CATALOG_ID
    catalog_schema_name: str = PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_NAME
    catalog_schema_version: str = PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION
    client_name: str = "codestrata_cli"
    transmission_operational: bool = False
    installation_identity_used: bool = False
    consent_persisted: bool = False
    consent_expands_fields: bool = False
    legacy_events_included: bool = False
    extension_clients_included: bool = False
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_ID:
            raise CatalogPolicyError("unsupported catalog policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_VERSION:
            raise CatalogPolicyError("unsupported catalog policy version")
        if self.catalog_id != PRIVACY_FIRST_TELEMETRY_CATALOG_ID:
            raise CatalogPolicyError("unsupported catalog id")
        if self.catalog_schema_name != PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_NAME:
            raise CatalogPolicyError("unsupported catalog schema name")
        if self.catalog_schema_version != PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION:
            raise CatalogPolicyError("unsupported catalog schema version")
        if self.client_name != "codestrata_cli":
            raise CatalogPolicyError("client_name must be codestrata_cli")
        if self.transmission_operational:
            raise CatalogPolicyError("transmission_operational must be false")
        if self.installation_identity_used:
            raise CatalogPolicyError("installation_identity_used must be false")
        if self.consent_persisted:
            raise CatalogPolicyError("consent_persisted must be false")
        if self.consent_expands_fields:
            raise CatalogPolicyError("consent_expands_fields must be false")
        if self.legacy_events_included:
            raise CatalogPolicyError("legacy_events_included must be false")
        if self.extension_clients_included:
            raise CatalogPolicyError("extension_clients_included must be false")
        if self.review_status != _REVIEW_STATUS:
            raise CatalogPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetryPublicCatalogPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_schema_name": self.catalog_schema_name,
            "catalog_schema_version": self.catalog_schema_version,
            "client_name": self.client_name,
            "consent_expands_fields": self.consent_expands_fields,
            "consent_persisted": self.consent_persisted,
            "extension_clients_included": self.extension_clients_included,
            "installation_identity_used": self.installation_identity_used,
            "legacy_events_included": self.legacy_events_included,
            "limitations": list(self.limitations),
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "review_status": self.review_status,
            "transmission_operational": self.transmission_operational,
        }


def default_catalog_policy() -> CommunityTelemetryPublicCatalogPolicy:
    return CommunityTelemetryPublicCatalogPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_ID",
    "COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_URN",
    "COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_VERSION",
    "CatalogPolicyError",
    "CommunityTelemetryPublicCatalogPolicy",
    "PRIVACY_FIRST_TELEMETRY_CATALOG_ID",
    "PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_NAME",
    "PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION",
    "default_catalog_policy",
]
