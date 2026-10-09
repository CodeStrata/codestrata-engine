"""Versioned scoped evidence/graph export policy (E13.2).

Existing telemetry aggregate payloads stay on the accepted wire. Evidence and
graph JSON is a separate local envelope. Upload stays unavailable unless a
collector advertises the schema and passes receipt/capability checks. A local
fake collector is the only capability test double; live v2 is never probed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ENGINE_EXPORT_POLICY_ID = "engine-collection-export-policy"
ENGINE_EXPORT_POLICY_VERSION = "1.0"
ENGINE_EXPORT_POLICY_URN = f"{ENGINE_EXPORT_POLICY_ID}:{ENGINE_EXPORT_POLICY_VERSION}"

EVIDENCE_EXPORT_SCHEMA = "codestrata.evidence-export.v1"
GRAPH_EXPORT_SCHEMA = "codestrata.graph-export.v1"
EXPORT_SCHEMA_VERSION = "1.0.0"

DEFAULT_MAX_EXPORT_SIZE_BYTES = 4096

_REVIEW_STATUS = "scoped_export_local_preview_no_live_v2"

_LIMITATIONS: tuple[str, ...] = (
    "existing_telemetry_wire_preserved",
    "telemetry_wire_omits_issue_identity",
    "evidence_graph_export_is_separate_json",
    "local_preview_does_not_claim_server_readiness",
    "no_speculative_live_v2_calls",
    "upload_requires_advertised_schema_and_receipt",
    "fake_collector_is_local_only",
    "no_community_api_s3_infrastructure_edits",
    "no_consent_local_utility_preserved",
)


class ExportPolicyError(ValueError):
    """Raised when the E13.2 export policy invariants fail."""


@dataclass(frozen=True, slots=True)
class EngineCollectionExportPolicy:
    """Local scoped export: construct JSON, never claim a live collector."""

    policy_id: str = ENGINE_EXPORT_POLICY_ID
    policy_version: str = ENGINE_EXPORT_POLICY_VERSION
    telemetry_may_carry_findings: bool = False
    telemetry_may_carry_snippets: bool = False
    telemetry_may_carry_repo_names: bool = False
    separate_evidence_graph_envelope: bool = True
    local_preview_claims_server_readiness: bool = False
    speculative_live_v2_calls: bool = False
    upload_requires_advertised_schema: bool = True
    upload_requires_receipt_check: bool = True
    fake_collector_local_only: bool = True
    community_api_edits_allowed: bool = False
    max_export_size_bytes: int = DEFAULT_MAX_EXPORT_SIZE_BYTES
    evidence_schema: str = EVIDENCE_EXPORT_SCHEMA
    graph_schema: str = GRAPH_EXPORT_SCHEMA
    export_schema_version: str = EXPORT_SCHEMA_VERSION
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != ENGINE_EXPORT_POLICY_ID:
            raise ExportPolicyError("unsupported export policy id")
        if self.policy_version != ENGINE_EXPORT_POLICY_VERSION:
            raise ExportPolicyError("unsupported export policy version")
        if self.telemetry_may_carry_findings:
            raise ExportPolicyError("telemetry_may_carry_findings must be false")
        if self.telemetry_may_carry_snippets:
            raise ExportPolicyError("telemetry_may_carry_snippets must be false")
        if self.telemetry_may_carry_repo_names:
            raise ExportPolicyError("telemetry_may_carry_repo_names must be false")
        if not self.separate_evidence_graph_envelope:
            raise ExportPolicyError("separate_evidence_graph_envelope must be true")
        if self.local_preview_claims_server_readiness:
            raise ExportPolicyError("local_preview_claims_server_readiness must be false")
        if self.speculative_live_v2_calls:
            raise ExportPolicyError("speculative_live_v2_calls must be false")
        if not self.upload_requires_advertised_schema:
            raise ExportPolicyError("upload_requires_advertised_schema must be true")
        if not self.upload_requires_receipt_check:
            raise ExportPolicyError("upload_requires_receipt_check must be true")
        if not self.fake_collector_local_only:
            raise ExportPolicyError("fake_collector_local_only must be true")
        if self.community_api_edits_allowed:
            raise ExportPolicyError("community_api_edits_allowed must be false")
        if self.max_export_size_bytes <= 0:
            raise ExportPolicyError("max_export_size_bytes must be positive")
        if self.evidence_schema != EVIDENCE_EXPORT_SCHEMA:
            raise ExportPolicyError("unsupported evidence schema")
        if self.graph_schema != GRAPH_EXPORT_SCHEMA:
            raise ExportPolicyError("unsupported graph schema")
        if self.export_schema_version != EXPORT_SCHEMA_VERSION:
            raise ExportPolicyError("unsupported export schema version")
        if self.review_status != _REVIEW_STATUS:
            raise ExportPolicyError("unsupported review_status")

    def schema_for_category(self, category: str) -> str:
        if category == "evidence":
            return self.evidence_schema
        if category == "graph":
            return self.graph_schema
        raise ExportPolicyError(f"unsupported export category: {category}")

    @classmethod
    def default(cls) -> EngineCollectionExportPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        payload = {
            "community_api_edits_allowed": self.community_api_edits_allowed,
            "evidence_schema": self.evidence_schema,
            "export_schema_version": self.export_schema_version,
            "fake_collector_local_only": self.fake_collector_local_only,
            "graph_schema": self.graph_schema,
            "limitations": list(self.limitations),
            "local_preview_claims_server_readiness": self.local_preview_claims_server_readiness,
            "max_export_size_bytes": self.max_export_size_bytes,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "review_status": self.review_status,
            "separate_evidence_graph_envelope": self.separate_evidence_graph_envelope,
            "speculative_live_v2_calls": self.speculative_live_v2_calls,
            "telemetry_may_carry_findings": self.telemetry_may_carry_findings,
            "telemetry_may_carry_repo_names": self.telemetry_may_carry_repo_names,
            "telemetry_may_carry_snippets": self.telemetry_may_carry_snippets,
            "upload_requires_advertised_schema": self.upload_requires_advertised_schema,
            "upload_requires_receipt_check": self.upload_requires_receipt_check,
        }
        return {key: payload[key] for key in sorted(payload)}


def default_export_policy() -> EngineCollectionExportPolicy:
    return EngineCollectionExportPolicy.default()


__all__ = [
    "DEFAULT_MAX_EXPORT_SIZE_BYTES",
    "ENGINE_EXPORT_POLICY_ID",
    "ENGINE_EXPORT_POLICY_URN",
    "ENGINE_EXPORT_POLICY_VERSION",
    "EVIDENCE_EXPORT_SCHEMA",
    "EXPORT_SCHEMA_VERSION",
    "EngineCollectionExportPolicy",
    "ExportPolicyError",
    "GRAPH_EXPORT_SCHEMA",
    "default_export_policy",
]
