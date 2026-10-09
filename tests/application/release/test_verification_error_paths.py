"""Negative, partial and policy-error paths for E14.1 verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.release.verification.crypto import (
    CryptoError,
    decode_b64,
    encode_b64,
    identity_matches,
    load_certificate_from_b64,
    load_certificate_from_pem,
    load_public_key_from_pem,
    parse_iso8601,
)
from codestrata.application.release.verification.models import (
    SignerRole,
    VerificationProfileId,
    VerificationStatus,
    VerifyRequest,
)
from codestrata.application.release.verification.policy import (
    OfflineSelfManagedProfile,
    PublicSigstoreProfile,
    ReleaseVerificationPolicy,
    VerificationPolicyError,
    default_verification_policy,
    policy_from_mapping,
)
from codestrata.application.release.verification.service import (
    verify_payload,
    verify_release_package,
)
from codestrata.domain.contracts.enums import ExecutionPurpose

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "verification"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_crypto_rejects_invalid_material() -> None:
    with pytest.raises(CryptoError):
        decode_b64("****", label="signature")
    with pytest.raises(CryptoError):
        parse_iso8601("not-a-time")
    naive = parse_iso8601("2026-09-21T00:00:00")
    assert naive.tzinfo is not None
    with pytest.raises(CryptoError):
        load_certificate_from_b64(encode_b64(b"not-a-cert"))
    with pytest.raises(CryptoError):
        load_certificate_from_pem("not pem")
    with pytest.raises(CryptoError):
        load_public_key_from_pem("not pem")
    assert identity_matches("abc", "abc")
    assert identity_matches("abcdef", "abc*")
    assert not identity_matches("zzz", "abc*")


def test_policy_validate_rejects_corrupt_mappings() -> None:
    with pytest.raises(VerificationPolicyError):
        ReleaseVerificationPolicy(policy_id="other")
    with pytest.raises(VerificationPolicyError):
        ReleaseVerificationPolicy(policy_version="9.0")
    with pytest.raises(VerificationPolicyError):
        ReleaseVerificationPolicy(max_bundle_bytes=0)
    with pytest.raises(VerificationPolicyError):
        ReleaseVerificationPolicy(
            public_sigstore=PublicSigstoreProfile(profile_id="nope"),
        )
    with pytest.raises(VerificationPolicyError):
        ReleaseVerificationPolicy(
            private_offline=OfflineSelfManagedProfile(instant_revocation=True),
        )
    with pytest.raises(VerificationPolicyError):
        policy_from_mapping({"public_sigstore": {}, "private_offline": "nope"})
    stable = default_verification_policy().to_stable_dict()
    assert stable["public_sigstore"]["signer_role"] != stable["private_offline"]["signer_role"]


def test_unsupported_profile_and_invalid_time() -> None:
    payload = _load("public-valid")
    payload["evaluation_time"] = "not-iso"
    bad_time = verify_payload(payload)
    assert bad_time.status is VerificationStatus.REJECTED
    assert bad_time.reason == "invalid_evaluation_time"


def test_missing_revocation_inventory() -> None:
    payload = _load("private-valid")
    payload["revocation"] = None
    result = verify_payload(payload)
    assert result.status is VerificationStatus.UNAVAILABLE
    assert result.reason == "revocation_inventory_missing"


def test_private_unsupported_algorithm_and_missing_key() -> None:
    payload = _load("private-valid")
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    bundle["algorithm"] = "rsa-pkcs1"
    result = verify_payload(payload)
    assert result.status is VerificationStatus.UNSUPPORTED
    payload = _load("private-valid")
    payload["trust_store"] = []
    missing = verify_payload(payload)
    assert missing.status is VerificationStatus.UNAVAILABLE
    assert missing.reason == "trust_entry_missing"


def test_private_key_purpose_mismatch() -> None:
    payload = _load("private-valid")
    store = payload["trust_store"]
    assert isinstance(store, list)
    entry = store[0]
    assert isinstance(entry, dict)
    entry["purpose"] = ExecutionPurpose.PREVIEW.value
    result = verify_payload(payload)
    assert result.status is VerificationStatus.WRONG_PURPOSE
    assert result.reason == "key_purpose_mismatch"


def test_public_digest_algorithm_and_missing_signature() -> None:
    payload = _load("public-valid")
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    message = bundle["messageSignature"]
    assert isinstance(message, dict)
    digest = message["messageDigest"]
    assert isinstance(digest, dict)
    digest["algorithm"] = "SHA2_512"
    result = verify_payload(payload)
    assert result.status is VerificationStatus.UNSUPPORTED
    payload = _load("public-valid")
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    del bundle["messageSignature"]["signature"]
    missing = verify_payload(payload)
    assert missing.status is VerificationStatus.UNAVAILABLE


def test_public_tlog_kind_unsupported() -> None:
    payload = _load("public-valid")
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    entries = bundle["verificationMaterial"]["tlogEntries"]
    assert isinstance(entries, list)
    entries.append({"extra": True})
    result = verify_payload(payload)
    assert result.status is VerificationStatus.UNSUPPORTED


def test_role_mismatch_via_typed_request() -> None:
    payload = _load("public-valid")
    request = VerifyRequest(
        profile_id=VerificationProfileId.SIGSTORE_PUBLIC,
        signer_role=SignerRole.PRIVATE_RESULT,
        requested_purpose=ExecutionPurpose.PRODUCTION,
        package=payload["package"],  # type: ignore[arg-type]
        artifact_bytes=decode_b64(str(payload["artifact_bytes"]), label="artifact"),
        bundle=payload["bundle"],  # type: ignore[arg-type]
        evaluation_time=str(payload["evaluation_time"]),
        trust_root_pem=str(payload["trust_root_pem"]),
        rekor_public_pem=str(payload["rekor_public_pem"]),
    )
    result = verify_release_package(request)
    assert result.status is VerificationStatus.REJECTED
    assert result.reason == "role_profile_mismatch"


def test_private_role_mismatch_on_offline_profile() -> None:
    payload = _load("private-valid")
    payload["signer_role"] = SignerRole.PUBLIC_DISTRIBUTION.value
    result = verify_payload(payload)
    assert result.status is VerificationStatus.REJECTED
    assert result.reason == "role_profile_mismatch"
