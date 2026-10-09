"""E13.3 projection policy invariants."""

from __future__ import annotations

import pytest

from codestrata.domain.contracts.enums import ExportMode
from codestrata.telemetry.export_projection_policy import (
    ENGINE_PROJECTION_POLICY_ID,
    ENGINE_PROJECTION_POLICY_VERSION,
    EngineExportProjectionPolicy,
    ProjectionPolicyError,
    default_projection_policy,
)


def test_default_policy_preserves_original_and_blocks_server_admission() -> None:
    policy = default_projection_policy()
    assert policy.policy_id == ENGINE_PROJECTION_POLICY_ID
    assert policy.policy_version == ENGINE_PROJECTION_POLICY_VERSION
    assert policy.mutate_original_canonical_bytes is False
    assert policy.no_export_transfers is False
    assert policy.unseen_may_claim_external_verification is False
    assert policy.public_private_data_logging is False
    assert policy.server_deletion_implemented is False
    assert policy.server_admission_implemented is False
    assert policy.preview_signer_authorizes_production is False
    assert policy.requires_transfer(ExportMode.NONE) is False
    assert policy.requires_transfer(ExportMode.FULL) is True
    payload = policy.to_stable_dict()
    assert list(payload) == sorted(payload)
    assert payload["policy_token"] == (
        f"{ENGINE_PROJECTION_POLICY_ID}:{ENGINE_PROJECTION_POLICY_VERSION}"
    )


def test_policy_rejects_forbidden_invariants() -> None:
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(mutate_original_canonical_bytes=True)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(no_export_transfers=True)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(unseen_may_claim_external_verification=True)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(public_private_data_logging=True)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(server_deletion_implemented=True)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(preview_signer_authorizes_production=True)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(public_sigstore_required=True)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(policy_id="other")
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(max_projection_size_bytes=0)
    with pytest.raises(ProjectionPolicyError):
        EngineExportProjectionPolicy(server_admission_implemented=True)
