"""E14.1 strict package/release verification profiles.

Fixtures are independent expected JSON: real ECDSA/Ed25519 material, not a
mocked signature boolean.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.release.checks import check_verification_profiles
from codestrata.application.release.verification import (
    SignerRole,
    VerificationProfileId,
    VerificationStatus,
    load_packaged_verification_policy,
    verify_payload,
)
from codestrata.application.release.verification.crypto import contains_private_key_marker
from codestrata.domain.contracts.enums import FreshnessState

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "verification"
EXPECTED_PATH = FIXTURE_DIR / "expected-outcomes.json"


def _load_expected() -> dict[str, dict[str, str]]:
    payload = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return {
        str(key): {"status": str(value["status"]), "reason": str(value["reason"])}
        for key, value in payload.items()
    }


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _case_names() -> list[str]:
    return sorted(_load_expected())


@pytest.mark.parametrize("name", _case_names())
def test_independent_fixtures_match_expected_status(name: str) -> None:
    expected = _load_expected()[name]
    result = verify_payload(_load_fixture(name))
    assert result.status.value == expected["status"]
    assert result.reason == expected["reason"]
    assert result.ok is (result.status is VerificationStatus.VERIFIED)


def test_valid_public_and_private_are_verified() -> None:
    public = verify_payload(_load_fixture("public-valid"))
    private = verify_payload(_load_fixture("private-valid"))
    assert public.status is VerificationStatus.VERIFIED
    assert private.status is VerificationStatus.VERIFIED
    assert public.signer_role is SignerRole.PUBLIC_DISTRIBUTION
    assert private.signer_role is SignerRole.PRIVATE_RESULT
    assert public.transparency_log_used is True
    assert private.transparency_log_used is False
    assert public.profile_id != private.profile_id


def test_public_and_private_roles_are_distinct() -> None:
    policy = load_packaged_verification_policy()
    assert policy.public_sigstore.signer_role == SignerRole.PUBLIC_DISTRIBUTION.value
    assert policy.private_offline.signer_role == SignerRole.PRIVATE_RESULT.value
    assert policy.public_sigstore.signer_role != policy.private_offline.signer_role
    assert policy.private_offline.instant_revocation is False
    assert policy.private_offline.transparency_log_forbidden is True
    assert policy.public_sigstore.transparency_log_required is True
    assert check_verification_profiles().ok


def test_private_rule_contents_never_enter_public_log() -> None:
    leaked = verify_payload(_load_fixture("public-private-contents-in-tlog"))
    blocked = verify_payload(_load_fixture("private-contents-in-public-log"))
    assert leaked.status is VerificationStatus.REJECTED
    assert leaked.reason == "private_contents_in_public_log"
    assert blocked.status is VerificationStatus.REJECTED
    assert blocked.reason == "private_contents_must_not_use_public_tlog"


def test_offline_freshness_limit_is_not_instant_revocation() -> None:
    stale = verify_payload(_load_fixture("private-stale-revocation"))
    revoked = verify_payload(_load_fixture("private-revoked-fresh"))
    assert stale.status is VerificationStatus.STALE
    assert stale.freshness is FreshnessState.STALE
    assert stale.reason == "revocation_inventory_exceeds_freshness_limit"
    assert revoked.status is VerificationStatus.REVOKED
    policy = load_packaged_verification_policy()
    assert policy.private_offline.stale_behavior == "unknown_not_revoked"
    assert policy.private_offline.revocation_max_age_seconds == 604800


def test_tampered_wrong_issuer_expired_unsupported_are_distinct() -> None:
    mapping = {
        "public-tampered": VerificationStatus.TAMPERED,
        "public-wrong-issuer": VerificationStatus.WRONG_ISSUER,
        "public-wrong-purpose": VerificationStatus.WRONG_PURPOSE,
        "public-expired": VerificationStatus.EXPIRED,
        "public-unsupported": VerificationStatus.UNSUPPORTED,
    }
    for name, status in mapping.items():
        result = verify_payload(_load_fixture(name))
        assert result.status is status
        assert result.ok is False


def test_budget_failure_on_oversized_bundle() -> None:
    payload = _load_fixture("public-valid")
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    bundle["padding"] = "x" * 70_000
    result = verify_payload(payload)
    assert result.status is VerificationStatus.ERROR
    assert result.reason == "bundle_exceeds_budget"


def test_partial_and_corrupt_fixtures() -> None:
    partial = verify_payload(_load_fixture("partial-missing-bundle"))
    corrupt = verify_payload(_load_fixture("corrupt"))
    assert partial.status is VerificationStatus.UNAVAILABLE
    assert corrupt.status is VerificationStatus.REJECTED


def test_deterministic_repeat_on_pinned_valid_fixture() -> None:
    payload = _load_fixture("public-valid")
    results = [verify_payload(payload) for _ in range(3)]
    assert len({(item.status, item.reason, item.package_digest) for item in results}) == 1
    assert results[0].status is VerificationStatus.VERIFIED


def test_fixtures_and_results_omit_private_keys() -> None:
    for name in _case_names():
        payload = _load_fixture(name)
        assert contains_private_key_marker(payload) is False
        result = verify_payload(payload)
        dumped = result.model_dump(mode="json")
        assert contains_private_key_marker(dumped) is False
        assert "BEGIN PRIVATE KEY" not in json.dumps(dumped)


def test_packaged_policy_matches_profile_ids() -> None:
    policy = load_packaged_verification_policy()
    assert policy.public_sigstore.profile_id == VerificationProfileId.SIGSTORE_PUBLIC.value
    assert policy.private_offline.profile_id == VerificationProfileId.OFFLINE_SELF_MANAGED.value
    assert policy.public_sigstore.network_mode == "offline"
    assert policy.private_offline.network_mode == "offline"


def test_fetch_urls_in_bundle_are_not_followed() -> None:
    payload = _load_fixture("public-valid")
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    bundle["rekor_url"] = "https://rekor.sigstore.dev"
    bundle["fulcio_url"] = "https://fulcio.sigstore.dev"
    result = verify_payload(payload)
    assert result.status is VerificationStatus.VERIFIED


def test_instant_revocation_flag_is_rejected() -> None:
    payload = _load_fixture("private-valid")
    revocation = payload["revocation"]
    assert isinstance(revocation, dict)
    revocation["instant_revocation"] = True
    result = verify_payload(payload)
    assert result.status is VerificationStatus.REJECTED
    assert result.reason == "instant_revocation_not_supported"
