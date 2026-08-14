"""Engine assessment_metadata 1.1 emission policy (Slice 20.8).

Emission is OFF by default. Lifecycle telemetry consent alone must never
enable assessment_metadata 1.1 — Slice 20.9 owns durable consent-v2 UX.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_ID = (
    "community-assessment-metadata-emission-policy"
)
COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_VERSION = "1.0"
COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_URN = (
    f"{COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_ID}:"
    f"{COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_VERSION}"
)

# Wire schema for Community assessment_metadata POST (Platform Slice 20.7).
# Public path literals live only in community_cloud.public_api_authority.
ASSESSMENT_METADATA_WIRE_SCHEMA_VERSION = "1.1"
# Engine report contract version accepted by Platform amd allowlist.
ASSESSMENT_REPORT_SCHEMA_VERSION = "1.2"

DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.0
DEFAULT_READ_TIMEOUT_SECONDS = 5.0
DEFAULT_MAXIMUM_ATTEMPTS = 1
DEFAULT_MAX_BODY_BYTES = 65_536
DEFAULT_MAX_FINDING_AGGREGATES = 500
DEFAULT_MAX_HEAD_CONFIDENCE_ROWS = 16


@dataclass(frozen=True, slots=True)
class CommunityAssessmentMetadataEmissionPolicy:
    """Fail-silent amd 1.1 emission controls — construction gate, not consent UX."""

    policy_id: str = COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_ID
    policy_version: str = COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_VERSION
    # Explicit internal authorization — OFF unless tests/future 20.9 enable it.
    emission_enabled: bool = False
    wire_schema_version: str = ASSESSMENT_METADATA_WIRE_SCHEMA_VERSION
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    maximum_attempts: int = DEFAULT_MAXIMUM_ATTEMPTS
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    maximum_finding_aggregates: int = DEFAULT_MAX_FINDING_AGGREGATES
    maximum_head_confidence_rows: int = DEFAULT_MAX_HEAD_CONFIDENCE_ROWS
    require_transmission_authorized: bool = True
    skip_when_offline: bool = True
    limitations: tuple[str, ...] = (
        "emission_disabled_by_default",
        "lifecycle_consent_does_not_authorize_amd",
        "requires_explicit_emission_authorization",
        "best_effort_non_blocking",
        "maximum_attempts_one",
        "no_payload_logging",
        "no_retry_storm",
        "assessment_outcome_always_wins",
    )

    def __post_init__(self) -> None:
        if self.policy_id != COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_ID:
            raise ValueError("unsupported amd emission policy id")
        if self.policy_version != COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_VERSION:
            raise ValueError("unsupported amd emission policy version")
        if self.maximum_attempts != 1:
            raise ValueError("amd emission maximum_attempts must be 1")
        if self.wire_schema_version != ASSESSMENT_METADATA_WIRE_SCHEMA_VERSION:
            raise ValueError("unsupported amd wire schema version")
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))

    @property
    def policy_token(self) -> str:
        return COMMUNITY_ASSESSMENT_METADATA_EMISSION_POLICY_URN

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "emission_enabled": self.emission_enabled,
            "limitations": list(self.limitations),
            "max_body_bytes": self.max_body_bytes,
            "maximum_attempts": self.maximum_attempts,
            "maximum_finding_aggregates": self.maximum_finding_aggregates,
            "maximum_head_confidence_rows": self.maximum_head_confidence_rows,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "read_timeout_seconds": self.read_timeout_seconds,
            "require_transmission_authorized": self.require_transmission_authorized,
            "skip_when_offline": self.skip_when_offline,
            "wire_schema_version": self.wire_schema_version,
        }


def default_assessment_metadata_emission_policy() -> (
    CommunityAssessmentMetadataEmissionPolicy
):
    return CommunityAssessmentMetadataEmissionPolicy()


def authorized_assessment_metadata_emission_policy() -> (
    CommunityAssessmentMetadataEmissionPolicy
):
    """Test / future 20.9 helper — never the product default."""

    return CommunityAssessmentMetadataEmissionPolicy(emission_enabled=True)
