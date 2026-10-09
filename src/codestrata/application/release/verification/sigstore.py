"""Public Sigstore expected identity/issuer/bundle verification (E14.1).

Verifies a supplied offline bundle. Fulcio/Rekor URLs are never fetched.
The transparency log body may bind only a hashedrekord of digest + signature.
"""

from __future__ import annotations

import json
from typing import Any

from codestrata.application.release.verification.crypto import (
    CryptoError,
    certificate_identity,
    certificate_is_code_signing,
    certificate_oidc_issuer,
    certificate_valid_at,
    contains_private_key_marker,
    decode_b64,
    identity_matches,
    load_certificate_from_b64,
    load_certificate_from_pem,
    parse_iso8601,
    sha256_hex,
    verify_ecdsa_p256_sha256,
    verify_leaf_against_root,
)
from codestrata.application.release.verification.models import (
    SignerRole,
    VerificationProfileId,
    VerificationResult,
    VerificationStatus,
    VerifyRequest,
)
from codestrata.application.release.verification.policy import (
    HASHEDREKORD_API,
    HASHEDREKORD_KIND,
    ReleaseVerificationPolicy,
)
from codestrata.domain.contracts.enums import FreshnessState
from codestrata.domain.contracts.serialization import dumps_canonical

_FETCH_KEYS = frozenset({"rekor_url", "fulcio_url", "tuf_url", "ctlog_url"})
_FORBIDDEN_TLOG_TOKENS = (
    "api_version: codestrata.io/rules",
    "codestrata.effective-ruleset",
    "\"findings\"",
    "source_text",
    "-----BEGIN PRIVATE KEY",
    "rule_yaml",
    "canonical_result",
)
_ALLOWED_HASHEDREKORD_TOP = frozenset({"apiVersion", "kind", "spec"})
_ALLOWED_SPEC = frozenset({"data", "signature"})
_ALLOWED_DATA = frozenset({"hash"})
_ALLOWED_HASH = frozenset({"algorithm", "value"})
_ALLOWED_SIGNATURE = frozenset({"content", "publicKey"})
BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"


def verify_public_sigstore(
    request: VerifyRequest,
    policy: ReleaseVerificationPolicy,
    *,
    package_digest: str,
    artifact_digest: str,
) -> VerificationResult:
    profile = policy.public_sigstore
    base = {
        "profile_id": profile.profile_id,
        "signer_role": SignerRole.PUBLIC_DISTRIBUTION,
        "requested_purpose": request.requested_purpose,
        "freshness": FreshnessState.NOT_APPLICABLE,
        "artifact_digest": artifact_digest,
        "package_digest": package_digest,
        "transparency_log_used": False,
        "limitations": policy.limitations,
    }
    if request.signer_role is not SignerRole.PUBLIC_DISTRIBUTION:
        return _result(VerificationStatus.REJECTED, "role_profile_mismatch", **base)
    if request.profile_id is not VerificationProfileId.SIGSTORE_PUBLIC:
        return _result(VerificationStatus.UNSUPPORTED, "unsupported_profile", **base)
    if contains_private_key_marker(request.bundle):
        return _result(VerificationStatus.REJECTED, "private_key_in_bundle", **base)
    if _FETCH_KEYS.intersection(request.bundle):
        # Do not egress. Local material must still be present.
        pass
    media = str(request.bundle.get("mediaType") or "")
    if media and media != BUNDLE_MEDIA_TYPE:
        return _result(VerificationStatus.UNSUPPORTED, "unsupported_bundle_media_type", **base)

    material = request.bundle.get("verificationMaterial")
    message = request.bundle.get("messageSignature")
    if not isinstance(material, dict) or not isinstance(message, dict):
        return _result(VerificationStatus.UNAVAILABLE, "bundle_material_missing", **base)

    certificate_obj = material.get("certificate")
    if not isinstance(certificate_obj, dict) or not certificate_obj.get("rawBytes"):
        return _result(VerificationStatus.UNAVAILABLE, "certificate_missing", **base)
    digest_obj = message.get("messageDigest")
    signature_b64 = message.get("signature")
    if not isinstance(digest_obj, dict) or not isinstance(signature_b64, str):
        return _result(VerificationStatus.UNAVAILABLE, "signature_missing", **base)
    algorithm = str(digest_obj.get("algorithm") or "")
    if algorithm != "SHA2_256":
        return _result(VerificationStatus.UNSUPPORTED, "unsupported_digest_algorithm", **base)

    try:
        leaf = load_certificate_from_b64(str(certificate_obj["rawBytes"]))
        signature = decode_b64(signature_b64, label="signature")
        claimed_digest = decode_b64(str(digest_obj.get("digest") or ""), label="digest")
    except CryptoError as error:
        return _result(VerificationStatus.REJECTED, str(error), **base)

    if claimed_digest.hex() != artifact_digest:
        return _result(VerificationStatus.TAMPERED, "artifact_digest_mismatch", **base)
    if sha256_hex(request.artifact_bytes) != artifact_digest:
        return _result(VerificationStatus.TAMPERED, "artifact_bytes_digest_mismatch", **base)

    if request.trust_root_pem is None:
        return _result(VerificationStatus.UNAVAILABLE, "trust_root_missing", **base)
    try:
        root = load_certificate_from_pem(request.trust_root_pem)
        when = parse_iso8601(request.evaluation_time)
        identity = certificate_identity(leaf)
        issuer = certificate_oidc_issuer(leaf)
    except CryptoError as error:
        reason = str(error)
        status = (
            VerificationStatus.UNSUPPORTED
            if "unsupported" in reason
            else VerificationStatus.REJECTED
        )
        return _result(status, reason, **base)

    base = {**base, "identity": identity, "issuer": issuer}
    if not verify_leaf_against_root(leaf, root):
        return _result(VerificationStatus.TAMPERED, "certificate_not_signed_by_trust_root", **base)
    if not certificate_valid_at(leaf, when):
        return _result(VerificationStatus.EXPIRED, "certificate_expired", **base)
    if not certificate_is_code_signing(leaf):
        return _result(VerificationStatus.WRONG_PURPOSE, "certificate_eku_not_code_signing", **base)

    expected_identity = request.expected_identity or profile.expected_identity
    expected_issuer = request.expected_issuer or profile.expected_issuer
    if issuer != expected_issuer:
        return _result(VerificationStatus.WRONG_ISSUER, "oidc_issuer_mismatch", **base)
    if not identity_matches(identity, expected_identity):
        return _result(VerificationStatus.WRONG_ISSUER, "identity_mismatch", **base)

    if not verify_ecdsa_p256_sha256(leaf.public_key(), signature, request.artifact_bytes):
        return _result(VerificationStatus.TAMPERED, "signature_mismatch", **base)

    tlog_entries = material.get("tlogEntries")
    tlog_error = _verify_tlog(
        tlog_entries,
        artifact_digest=artifact_digest,
        signature_b64=signature_b64,
        rekor_public_pem=request.rekor_public_pem,
        evaluation_time=request.evaluation_time,
    )
    if tlog_error is not None:
        status, reason = tlog_error
        return _result(status, reason, **base)
    return _result(
        VerificationStatus.VERIFIED,
        "ok",
        **{**base, "trusted": True, "transparency_log_used": True},
    )


def hashedrekord_body(*, artifact_digest: str, signature_b64: str) -> dict[str, Any]:
    """Digest-only Rekor body. Never include rule or result contents."""

    return {
        "apiVersion": HASHEDREKORD_API,
        "kind": HASHEDREKORD_KIND,
        "spec": {
            "data": {"hash": {"algorithm": "sha256", "value": artifact_digest}},
            "signature": {"content": signature_b64, "publicKey": {"format": "x509"}},
        },
    }


def _verify_tlog(
    entries: object,
    *,
    artifact_digest: str,
    signature_b64: str,
    rekor_public_pem: str | None,
    evaluation_time: str,
) -> tuple[VerificationStatus, str] | None:
    if not isinstance(entries, list) or not entries:
        return VerificationStatus.UNAVAILABLE, "transparency_log_missing"
    if len(entries) != 1 or not isinstance(entries[0], dict):
        return VerificationStatus.UNSUPPORTED, "unsupported_tlog_set"
    entry = entries[0]
    body_b64 = entry.get("canonicalizedBody")
    set_b64 = None
    promise = entry.get("inclusionPromise")
    if isinstance(promise, dict):
        set_b64 = promise.get("signedEntryTimestamp")
    if not isinstance(body_b64, str) or not isinstance(set_b64, str):
        return VerificationStatus.UNAVAILABLE, "tlog_inclusion_missing"
    try:
        body_bytes = decode_b64(body_b64, label="tlog body")
        set_bytes = decode_b64(set_b64, label="signedEntryTimestamp")
    except CryptoError as error:
        return VerificationStatus.REJECTED, str(error)
    decoded = body_bytes.decode("utf-8")
    if any(token in decoded for token in _FORBIDDEN_TLOG_TOKENS):
        return VerificationStatus.REJECTED, "private_contents_in_public_log"
    try:
        payload = json.loads(decoded)
    except (ValueError, UnicodeDecodeError):
        return VerificationStatus.REJECTED, "tlog_body_not_json"
    if not isinstance(payload, dict):
        return VerificationStatus.REJECTED, "tlog_body_not_json"
    leak = _hashedrekord_leak(payload)
    if leak is not None:
        return VerificationStatus.REJECTED, leak
    if payload.get("kind") != HASHEDREKORD_KIND:
        return VerificationStatus.UNSUPPORTED, "unsupported_tlog_kind"
    spec = payload.get("spec")
    if not isinstance(spec, dict):
        return VerificationStatus.REJECTED, "tlog_spec_missing"
    data = spec.get("data")
    signature = spec.get("signature")
    if not isinstance(data, dict) or not isinstance(signature, dict):
        return VerificationStatus.REJECTED, "tlog_spec_missing"
    hash_obj = data.get("hash")
    digest_value = hash_obj.get("value") if isinstance(hash_obj, dict) else None
    if digest_value != artifact_digest:
        return VerificationStatus.TAMPERED, "tlog_digest_mismatch"
    if signature.get("content") != signature_b64:
        return VerificationStatus.TAMPERED, "tlog_signature_mismatch"
    if rekor_public_pem is None:
        return VerificationStatus.UNAVAILABLE, "rekor_key_missing"
    from codestrata.application.release.verification.crypto import load_public_key_from_pem

    try:
        rekor_key = load_public_key_from_pem(rekor_public_pem)
        when = parse_iso8601(evaluation_time)
    except CryptoError as error:
        return VerificationStatus.REJECTED, str(error)
    integrated = str(entry.get("integratedTime") or "")
    try:
        integrated_at = parse_iso8601(integrated) if "T" in integrated else when
    except CryptoError:
        integrated_at = when
    signed_set = signed_entry_timestamp_message(
        body_bytes=body_bytes,
        log_index=str(entry.get("logIndex") or ""),
        integrated_time=integrated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    if not verify_ecdsa_p256_sha256(rekor_key, set_bytes, signed_set):
        return VerificationStatus.TAMPERED, "tlog_set_mismatch"
    return None


def signed_entry_timestamp_message(
    *,
    body_bytes: bytes,
    log_index: str,
    integrated_time: str,
) -> bytes:
    return dumps_canonical(
        {
            "bodyDigest": sha256_hex(body_bytes),
            "integratedTime": integrated_time,
            "logIndex": log_index,
        }
    ).encode("utf-8")


def _hashedrekord_leak(payload: dict[str, Any]) -> str | None:
    extra_top = set(payload) - _ALLOWED_HASHEDREKORD_TOP
    if extra_top:
        return "private_contents_in_public_log"
    spec = payload.get("spec")
    if not isinstance(spec, dict):
        return "tlog_spec_missing"
    if set(spec) - _ALLOWED_SPEC:
        return "private_contents_in_public_log"
    data = spec.get("data")
    signature = spec.get("signature")
    if not isinstance(data, dict) or not isinstance(signature, dict):
        return "tlog_spec_missing"
    if set(data) - _ALLOWED_DATA:
        return "private_contents_in_public_log"
    digest = data.get("hash")
    if not isinstance(digest, dict) or set(digest) - _ALLOWED_HASH:
        return "private_contents_in_public_log"
    if set(signature) - _ALLOWED_SIGNATURE:
        return "private_contents_in_public_log"
    return None


def _result(
    status: VerificationStatus,
    reason: str,
    **kwargs: Any,
) -> VerificationResult:
    return VerificationResult(status=status, reason=reason, **kwargs)


__all__ = [
    "BUNDLE_MEDIA_TYPE",
    "hashedrekord_body",
    "signed_entry_timestamp_message",
    "verify_public_sigstore",
]
