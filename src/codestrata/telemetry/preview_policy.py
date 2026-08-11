"""Independent privacy-first telemetry preview policy (Slice 9.9)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.events import RuntimeEventType

COMMUNITY_TELEMETRY_PREVIEW_POLICY_ID = "community-telemetry-preview-policy"
COMMUNITY_TELEMETRY_PREVIEW_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_PREVIEW_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_PREVIEW_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_PREVIEW_POLICY_VERSION}"
)

PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_NAME = "privacy-first-telemetry-preview"
PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_VERSION = "1.0.0"

DEFAULT_PREVIEW_EVENT = RuntimeEventType.FEATURE_INVOKED.value

_REVIEW_STATUS = "local_illustrative_preview_no_transmission"

_LIMITATIONS: tuple[str, ...] = (
    "local_only",
    "no_transmission",
    "no_transport_invocation",
    "privacy_projection_required",
    "public_catalog_reconciliation_required",
    "illustrative_values_only",
    "no_repository_inspection",
    "no_installation_identity",
    "no_preference_or_queue_access",
    "no_consent_persistence",
    "deterministic_output",
    "supported_event_selection",
    "json_stdout_only",
    "http_transport_requires_explicit_configuration",
    "preview_is_not_http_body",
    "future_cloud_mapping_separate",
)


class PreviewPolicyError(ValueError):
    """Raised when preview-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryPreviewPolicy:
    """Versioned CLI transparency contract for privacy-first preview."""

    policy_id: str = COMMUNITY_TELEMETRY_PREVIEW_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_PREVIEW_POLICY_VERSION
    preview_schema_name: str = PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_NAME
    preview_schema_version: str = PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_VERSION
    default_event_name: str = DEFAULT_PREVIEW_EVENT
    local_only: bool = True
    transmission_performed: bool = False
    transport_invocation_allowed: bool = False
    privacy_projection_required: bool = True
    catalog_reconciliation_required: bool = True
    illustrative_values_only: bool = True
    repository_inspection_allowed: bool = False
    installation_identity_used: bool = False
    preference_or_queue_access_allowed: bool = False
    consent_persisted: bool = False
    consent_required: bool = False
    deterministic_output: bool = True
    supported_output_formats: tuple[str, ...] = ("json",)
    max_preview_size_bytes: int = 16_384
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supported_output_formats",
            tuple(sorted(set(self.supported_output_formats))),
        )
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_PREVIEW_POLICY_ID:
            raise PreviewPolicyError("unsupported preview policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_PREVIEW_POLICY_VERSION:
            raise PreviewPolicyError("unsupported preview policy version")
        if self.preview_schema_name != PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_NAME:
            raise PreviewPolicyError("unsupported preview schema name")
        if self.preview_schema_version != PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_VERSION:
            raise PreviewPolicyError("unsupported preview schema version")
        if self.default_event_name != DEFAULT_PREVIEW_EVENT:
            raise PreviewPolicyError("default_event_name must be feature_invoked")
        if not self.local_only:
            raise PreviewPolicyError("local_only must be true")
        if self.transmission_performed:
            raise PreviewPolicyError("transmission_performed must be false")
        if self.transport_invocation_allowed:
            raise PreviewPolicyError("transport_invocation_allowed must be false")
        if not self.privacy_projection_required:
            raise PreviewPolicyError("privacy_projection_required must be true")
        if not self.catalog_reconciliation_required:
            raise PreviewPolicyError("catalog_reconciliation_required must be true")
        if not self.illustrative_values_only:
            raise PreviewPolicyError("illustrative_values_only must be true")
        if self.repository_inspection_allowed:
            raise PreviewPolicyError("repository_inspection_allowed must be false")
        if self.installation_identity_used:
            raise PreviewPolicyError("installation_identity_used must be false")
        if self.preference_or_queue_access_allowed:
            raise PreviewPolicyError("preference_or_queue_access_allowed must be false")
        if self.consent_persisted:
            raise PreviewPolicyError("consent_persisted must be false")
        if self.consent_required:
            raise PreviewPolicyError("consent_required must be false")
        if not self.deterministic_output:
            raise PreviewPolicyError("deterministic_output must be true")
        if self.supported_output_formats != ("json",):
            raise PreviewPolicyError("only json output is supported")
        if self.max_preview_size_bytes <= 0:
            raise PreviewPolicyError("max_preview_size_bytes must be positive")
        if self.review_status != _REVIEW_STATUS:
            raise PreviewPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetryPreviewPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "catalog_reconciliation_required": self.catalog_reconciliation_required,
            "consent_persisted": self.consent_persisted,
            "consent_required": self.consent_required,
            "default_event_name": self.default_event_name,
            "deterministic_output": self.deterministic_output,
            "illustrative_values_only": self.illustrative_values_only,
            "installation_identity_used": self.installation_identity_used,
            "limitations": list(self.limitations),
            "local_only": self.local_only,
            "max_preview_size_bytes": self.max_preview_size_bytes,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "preference_or_queue_access_allowed": self.preference_or_queue_access_allowed,
            "preview_schema_name": self.preview_schema_name,
            "preview_schema_version": self.preview_schema_version,
            "privacy_projection_required": self.privacy_projection_required,
            "repository_inspection_allowed": self.repository_inspection_allowed,
            "review_status": self.review_status,
            "supported_output_formats": list(self.supported_output_formats),
            "transmission_performed": self.transmission_performed,
            "transport_invocation_allowed": self.transport_invocation_allowed,
        }


def default_preview_policy() -> CommunityTelemetryPreviewPolicy:
    return CommunityTelemetryPreviewPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_PREVIEW_POLICY_ID",
    "COMMUNITY_TELEMETRY_PREVIEW_POLICY_URN",
    "COMMUNITY_TELEMETRY_PREVIEW_POLICY_VERSION",
    "CommunityTelemetryPreviewPolicy",
    "DEFAULT_PREVIEW_EVENT",
    "PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_NAME",
    "PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_VERSION",
    "PreviewPolicyError",
    "default_preview_policy",
]
