"""Bounded private/offline self-managed-key verification profile (E14.1).

Private rule and result contents never enter a public transparency log.
Revocation is freshness-limited: a stale inventory cannot prove instant
revocation and cannot prove a clean key.
"""

from __future__ import annotations

from typing import Any

from codestrata.application.release.verification.crypto import (
    CryptoError,
    contains_private_key_marker,
    decode_b64,
    load_public_key_from_pem,
    parse_iso8601,
    verify_ed25519,
)
from codestrata.application.release.verification.models import (
    RevocationInventory,
    SignerRole,
    VerificationProfileId,
    VerificationResult,
    VerificationStatus,
    VerifyRequest,
)
from codestrata.application.release.verification.policy import ReleaseVerificationPolicy
from codestrata.domain.contracts.enums import ExecutionPurpose, FreshnessState


def verify_offline_self_managed(
    request: VerifyRequest,
    policy: ReleaseVerificationPolicy,
    *,
    package_digest: str,
    artifact_digest: str,
    package_purpose: ExecutionPurpose,
    canonical_body: bytes,
) -> VerificationResult:
    profile = policy.private_offline
    base: dict[str, Any] = {
        "profile_id": profile.profile_id,
        "signer_role": SignerRole.PRIVATE_RESULT,
        "requested_purpose": request.requested_purpose,
        "freshness": FreshnessState.UNKNOWN,
        "artifact_digest": artifact_digest,
        "package_digest": package_digest,
        "transparency_log_used": False,
        "limitations": policy.limitations,
    }
    if request.signer_role is not SignerRole.PRIVATE_RESULT:
        return _result(VerificationStatus.REJECTED, "role_profile_mismatch", **base)
    if request.profile_id is not VerificationProfileId.OFFLINE_SELF_MANAGED:
        return _result(VerificationStatus.UNSUPPORTED, "unsupported_profile", **base)
    if contains_private_key_marker(request.bundle) or any(
        "PRIVATE KEY" in entry.public_key_pem for entry in request.trust_store
    ):
        return _result(VerificationStatus.REJECTED, "private_key_in_bundle", **base)
    if request.bundle.get("tlogEntries") or request.bundle.get("verificationMaterial"):
        return _result(
            VerificationStatus.REJECTED,
            "private_contents_must_not_use_public_tlog",
            **base,
        )
    algorithm = str(request.bundle.get("algorithm") or "")
    if algorithm and algorithm != profile.algorithm:
        return _result(VerificationStatus.UNSUPPORTED, "unsupported_signature_algorithm", **base)
    signature_b64 = request.bundle.get("signature")
    key_id = request.key_id or request.bundle.get("key_id")
    if not isinstance(signature_b64, str) or not isinstance(key_id, str) or not key_id:
        return _result(VerificationStatus.UNAVAILABLE, "signature_missing", **base)

    freshness, stale_reason = _revocation_freshness(
        request.revocation,
        evaluation_time=request.evaluation_time,
        max_age_seconds=profile.revocation_max_age_seconds,
    )
    base["freshness"] = freshness
    if request.revocation is not None and request.revocation.instant_revocation:
        return _result(
            VerificationStatus.REJECTED,
            "instant_revocation_not_supported",
            **base,
        )
    if freshness is FreshnessState.STALE:
        # Freshness limit: do not treat the key as revoked or verified.
        return _result(
            VerificationStatus.STALE,
            stale_reason or "revocation_inventory_exceeds_freshness_limit",
            **base,
        )
    if freshness is FreshnessState.UNKNOWN and request.revocation is None:
        return _result(VerificationStatus.UNAVAILABLE, "revocation_inventory_missing", **base)
    if request.revocation is not None and key_id in request.revocation.revoked_key_ids:
        return _result(VerificationStatus.REVOKED, "key_revoked_in_fresh_inventory", **base)

    entry = next((item for item in request.trust_store if item.key_id == key_id), None)
    if entry is None:
        return _result(VerificationStatus.UNAVAILABLE, "trust_entry_missing", **base)
    if entry.role is not SignerRole.PRIVATE_RESULT:
        return _result(VerificationStatus.REJECTED, "role_profile_mismatch", **base)
    if entry.purpose is not request.requested_purpose:
        return _result(VerificationStatus.WRONG_PURPOSE, "key_purpose_mismatch", **base)
    if entry.purpose is not package_purpose:
        return _result(VerificationStatus.WRONG_PURPOSE, "package_purpose_mismatch", **base)
    if entry.not_after:
        try:
            when = parse_iso8601(request.evaluation_time)
            expiry = parse_iso8601(entry.not_after)
        except CryptoError as error:
            return _result(VerificationStatus.REJECTED, str(error), **base)
        if when > expiry:
            return _result(VerificationStatus.EXPIRED, "trust_entry_expired", **base)

    try:
        public_key = load_public_key_from_pem(entry.public_key_pem)
        signature = decode_b64(signature_b64, label="signature")
    except CryptoError as error:
        return _result(VerificationStatus.REJECTED, str(error), **base)
    if not verify_ed25519(public_key, signature, canonical_body):
        return _result(VerificationStatus.TAMPERED, "signature_mismatch", **base)
    return _result(
        VerificationStatus.VERIFIED,
        "ok",
        **{**base, "trusted": True, "freshness": FreshnessState.FRESH},
    )


def _revocation_freshness(
    inventory: RevocationInventory | None,
    *,
    evaluation_time: str,
    max_age_seconds: int,
) -> tuple[FreshnessState, str | None]:
    if inventory is None:
        return FreshnessState.UNKNOWN, "revocation_inventory_missing"
    try:
        updated = parse_iso8601(inventory.last_updated)
        when = parse_iso8601(evaluation_time)
    except CryptoError:
        return FreshnessState.UNKNOWN, "invalid_revocation_timestamp"
    age = (when - updated).total_seconds()
    if age < 0:
        return FreshnessState.UNKNOWN, "revocation_inventory_from_future"
    if age > max_age_seconds:
        return FreshnessState.STALE, "revocation_inventory_exceeds_freshness_limit"
    return FreshnessState.FRESH, None


def _result(
    status: VerificationStatus,
    reason: str,
    **kwargs: Any,
) -> VerificationResult:
    return VerificationResult(status=status, reason=reason, **kwargs)


__all__ = ["verify_offline_self_managed"]
