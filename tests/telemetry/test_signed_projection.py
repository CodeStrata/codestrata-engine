"""E13.3 signed projections: original preserved, separate signed redaction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.domain.contracts.enums import ExecutionPurpose, ExportMode
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.telemetry.export_projection_models import (
    ProjectionEnvelopeError,
    ProjectionVerificationStatus,
    SignedExportProjection,
    canonical_body_bytes,
)
from codestrata.telemetry.export_projection_policy import (
    LOCAL_HMAC_VERIFICATION_PROFILE,
    EngineExportProjectionPolicy,
)
from codestrata.telemetry.export_signing import (
    LOCAL_TEST_KEY_ID,
    UNTRUSTED_TEST_KEY_ID,
    default_local_keyring,
    keyring_with_untrusted,
)
from codestrata.telemetry.signed_projection import (
    build_original_package,
    parse_original_package,
    project_export,
    run_headless_export,
    verify_signed_projection,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "export_projection"
PINNED_NOW = "2026-09-20T00:00:00Z"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_full_restricted_no_export_preserve_original_bytes() -> None:
    original = build_original_package()
    snapshot = bytes(original.canonical_bytes)
    digest = original.package_digest
    assert digest == digest_canonical(original.body_dict())

    for mode, withheld in (
        (ExportMode.FULL, None),
        (ExportMode.RESTRICTED, ("graph",)),
        (ExportMode.NONE, None),
    ):
        same, projection = project_export(original, mode, withheld_categories=withheld)
        assert same.canonical_bytes == snapshot
        assert original.canonical_bytes == snapshot
        assert projection.original_digest == digest
        assert projection.export_policy_version == original.export_policy_version
        assert projection.signature is not None
        assert projection.signature.verification_profile == LOCAL_HMAC_VERIFICATION_PROFILE
        assert projection.signature.algorithm == "hmac-sha256"
        assert "signature" not in projection.body_dict()
        assert projection.unseen_evidence_externally_verified is False
        assert projection.transmission_performed is False
        if mode is ExportMode.NONE:
            assert projection.allowed_categories == ()
            assert projection.withheld_categories == ("evidence", "graph")
        if mode is ExportMode.RESTRICTED:
            assert projection.allowed_categories == ("evidence",)
            assert projection.withheld_categories == ("graph",)
        if mode is ExportMode.FULL:
            assert projection.withheld_categories == ()


def test_headless_no_export_retains_local_utility_and_does_not_transfer() -> None:
    result = run_headless_export("no-export")
    assert result.transmission_performed is False
    assert result.local_utility_retained is True
    assert result.mode is ExportMode.NONE
    assert result.projection.transmission_performed is False
    first = result.to_stable_json()
    second = run_headless_export("no-export").to_stable_json()
    third = run_headless_export(ExportMode.NONE).to_stable_json()
    assert first == second == third


def test_signed_projection_cannot_claim_unseen_verified() -> None:
    payload = _load("unseen-claimed-verified.json")
    original = build_original_package()
    _, projection = project_export(original, "restricted", withheld_categories=("graph",))
    with pytest.raises(ProjectionEnvelopeError, match="unseen evidence"):
        SignedExportProjection(
            schema=projection.schema,
            schema_version=projection.schema_version,
            original_digest=projection.original_digest,
            package_digest=projection.package_digest,
            export_mode=projection.export_mode,
            export_policy_version=projection.export_policy_version,
            projection_policy_version=projection.projection_policy_version,
            allowed_categories=projection.allowed_categories,
            withheld_categories=tuple(str(item) for item in payload["withheld_categories"]),  # type: ignore[arg-type]
            verification_profile=projection.verification_profile,
            purpose=projection.purpose,
            canonical_bytes=projection.canonical_bytes,
            unseen_evidence_externally_verified=True,
            externally_verified_categories=("graph",),
        )


def test_tampering_is_detected() -> None:
    original = build_original_package()
    _, projection = project_export(original, ExportMode.FULL)
    ring = default_local_keyring()
    ok = verify_signed_projection(
        projection,
        original=original,
        keyring=ring,
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert ok.status is ProjectionVerificationStatus.VERIFIED

    tampered_original = build_original_package(package_id="codestrata.tampered-original")
    object.__setattr__(tampered_original, "canonical_bytes", original.canonical_bytes)
    object.__setattr__(tampered_original, "signature", original.signature)
    broken = verify_signed_projection(
        projection,
        original=tampered_original,
        keyring=ring,
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert broken.status is ProjectionVerificationStatus.TAMPERED

    mutated = SignedExportProjection(
        schema=projection.schema,
        schema_version=projection.schema_version,
        original_digest=projection.original_digest,
        package_digest="0" * 64,
        export_mode=projection.export_mode,
        export_policy_version=projection.export_policy_version,
        projection_policy_version=projection.projection_policy_version,
        allowed_categories=projection.allowed_categories,
        withheld_categories=projection.withheld_categories,
        verification_profile=projection.verification_profile,
        purpose=projection.purpose,
        canonical_bytes=projection.canonical_bytes,
        signature=projection.signature,
    )
    digest_fail = verify_signed_projection(
        mutated,
        original=original,
        keyring=ring,
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert digest_fail.status is ProjectionVerificationStatus.TAMPERED


def test_stale_package_and_wrong_purpose_and_missing_original() -> None:
    stale_body = _load("stale-package.json")["body"]
    assert isinstance(stale_body, dict)
    stale = build_original_package(
        purpose=str(stale_body["purpose"]),
        validity_not_after=str(stale_body["validity_not_after"]),
    )
    _, stale_projection = project_export(stale, ExportMode.FULL)
    stale_result = verify_signed_projection(
        stale_projection,
        original=stale,
        keyring=default_local_keyring(),
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert stale_result.status is ProjectionVerificationStatus.STALE

    preview_body = _load("wrong-purpose-preview.json")["body"]
    assert isinstance(preview_body, dict)
    preview = build_original_package(purpose=str(preview_body["purpose"]))
    _, preview_projection = project_export(preview, ExportMode.FULL)
    wrong = verify_signed_projection(
        preview_projection,
        original=preview,
        keyring=default_local_keyring(),
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert wrong.status is ProjectionVerificationStatus.WRONG_PURPOSE

    missing = verify_signed_projection(
        preview_projection,
        original=None,
        keyring=default_local_keyring(),
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert missing.status is ProjectionVerificationStatus.UNAVAILABLE
    assert missing.reason == "original_unavailable"


def test_untrusted_key_is_unverified() -> None:
    ring = keyring_with_untrusted()
    original = build_original_package(keyring=ring, key_id=UNTRUSTED_TEST_KEY_ID)
    _, projection = project_export(
        original,
        ExportMode.FULL,
        keyring=ring,
        key_id=UNTRUSTED_TEST_KEY_ID,
    )
    result = verify_signed_projection(
        projection,
        original=original,
        keyring=ring,
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert result.status is ProjectionVerificationStatus.UNVERIFIED
    assert result.reason == "untrusted_key"
    assert result.trusted_key is False


def test_negative_and_partial_fixtures() -> None:
    parse_original_package(_load("original-good.json"))
    with pytest.raises(ProjectionEnvelopeError, match="prohibited"):
        parse_original_package(_load("prohibited-fields.json"))
    with pytest.raises(json.JSONDecodeError):
        json.loads((FIXTURE_DIR / "corrupt.json").read_text(encoding="utf-8"))


def test_budget_failure_on_oversized_projection() -> None:
    tiny = EngineExportProjectionPolicy(max_projection_size_bytes=64)
    original = build_original_package(policy=tiny)
    with pytest.raises(ProjectionEnvelopeError, match="maximum size"):
        project_export(original, ExportMode.FULL, policy=tiny)


def test_trusted_local_key_inventory_omits_secrets() -> None:
    inventory = default_local_keyring().public_inventory()
    blob = json.dumps(inventory)
    assert LOCAL_TEST_KEY_ID in blob
    assert "not-for-production" not in blob
    assert "secret" not in blob.lower()


def test_missing_and_partial_verification_paths() -> None:
    with pytest.raises(ProjectionEnvelopeError, match="unsupported execution purpose"):
        build_original_package(purpose="lake")
    with pytest.raises(ProjectionEnvelopeError, match="candidate_validation"):
        build_original_package(purpose=ExecutionPurpose.CANDIDATE_VALIDATION)
    with pytest.raises(ProjectionEnvelopeError, match="pinned sha256"):
        build_original_package(artifact_digest="nope")
    with pytest.raises(ProjectionEnvelopeError, match="must be a mapping"):
        parse_original_package("not-a-mapping")
    with pytest.raises(ProjectionEnvelopeError, match="body must be a mapping"):
        parse_original_package({"body": "x"})

    unsigned = build_original_package(sign=False)
    _, unsigned_projection = project_export(unsigned, ExportMode.FULL, sign=False)
    unverified = verify_signed_projection(
        unsigned_projection,
        original=unsigned,
        keyring=default_local_keyring(),
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert unverified.status is ProjectionVerificationStatus.UNVERIFIED

    original = build_original_package()
    _, projection = project_export(original, ExportMode.FULL)
    body = dict(projection.body_dict())
    body["original_digest"] = "0" * 64
    canonical = canonical_body_bytes(body)
    mismatched = SignedExportProjection(
        schema=projection.schema,
        schema_version=projection.schema_version,
        original_digest="0" * 64,
        package_digest=digest_canonical(body),
        export_mode=projection.export_mode,
        export_policy_version=projection.export_policy_version,
        projection_policy_version=projection.projection_policy_version,
        allowed_categories=projection.allowed_categories,
        withheld_categories=projection.withheld_categories,
        verification_profile=projection.verification_profile,
        purpose=projection.purpose,
        canonical_bytes=canonical,
        signature=projection.signature,
    )
    rejected = verify_signed_projection(
        mismatched,
        original=original,
        keyring=default_local_keyring(),
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert rejected.status is ProjectionVerificationStatus.REJECTED

    not_yet = build_original_package(
        validity_not_before="2026-12-01T00:00:00Z",
        validity_not_after="2027-09-15T00:00:00Z",
    )
    _, not_yet_projection = project_export(not_yet, ExportMode.FULL)
    early = verify_signed_projection(
        not_yet_projection,
        original=not_yet,
        keyring=default_local_keyring(),
        requested_purpose=ExecutionPurpose.PRODUCTION,
        now=PINNED_NOW,
    )
    assert early.status is ProjectionVerificationStatus.STALE
    assert early.reason == "package_not_yet_valid"

    production = build_original_package(purpose=ExecutionPurpose.PRODUCTION)
    _, production_projection = project_export(production, ExportMode.FULL)
    purpose_mismatch = verify_signed_projection(
        production_projection,
        original=production,
        keyring=default_local_keyring(),
        requested_purpose=ExecutionPurpose.PREVIEW,
        now=PINNED_NOW,
    )
    assert purpose_mismatch.status is ProjectionVerificationStatus.WRONG_PURPOSE
