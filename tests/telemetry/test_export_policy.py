"""E13.2 export policy contract."""

from __future__ import annotations

import pytest

from codestrata.telemetry.export_policy import (
    ENGINE_EXPORT_POLICY_ID,
    ENGINE_EXPORT_POLICY_VERSION,
    EVIDENCE_EXPORT_SCHEMA,
    GRAPH_EXPORT_SCHEMA,
    EngineCollectionExportPolicy,
    ExportPolicyError,
    default_export_policy,
)


def test_default_policy_preserves_telemetry_wire_and_blocks_live_v2() -> None:
    policy = default_export_policy()
    assert policy.policy_id == ENGINE_EXPORT_POLICY_ID
    assert policy.policy_version == ENGINE_EXPORT_POLICY_VERSION
    assert policy.telemetry_may_carry_findings is False
    assert policy.telemetry_may_carry_snippets is False
    assert policy.telemetry_may_carry_repo_names is False
    assert policy.separate_evidence_graph_envelope is True
    assert policy.local_preview_claims_server_readiness is False
    assert policy.speculative_live_v2_calls is False
    assert policy.upload_requires_advertised_schema is True
    assert policy.upload_requires_receipt_check is True
    assert policy.evidence_schema == EVIDENCE_EXPORT_SCHEMA
    assert policy.graph_schema == GRAPH_EXPORT_SCHEMA


def test_policy_rejects_server_readiness_and_live_v2() -> None:
    with pytest.raises(ExportPolicyError):
        EngineCollectionExportPolicy(local_preview_claims_server_readiness=True)
    with pytest.raises(ExportPolicyError):
        EngineCollectionExportPolicy(speculative_live_v2_calls=True)
    with pytest.raises(ExportPolicyError):
        EngineCollectionExportPolicy(community_api_edits_allowed=True)


def test_policy_rejects_findings_on_telemetry_wire() -> None:
    with pytest.raises(ExportPolicyError):
        EngineCollectionExportPolicy(telemetry_may_carry_findings=True)
    with pytest.raises(ExportPolicyError):
        EngineCollectionExportPolicy(telemetry_may_carry_snippets=True)
    with pytest.raises(ExportPolicyError):
        EngineCollectionExportPolicy(telemetry_may_carry_repo_names=True)


def test_stable_dict_is_sorted_and_versioned() -> None:
    payload = default_export_policy().to_stable_dict()
    assert list(payload) == sorted(payload)
    assert payload["policy_token"] == (
        f"{ENGINE_EXPORT_POLICY_ID}:{ENGINE_EXPORT_POLICY_VERSION}"
    )
