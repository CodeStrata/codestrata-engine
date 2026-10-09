"""Dispatch strict package/release verification profiles (E14.1)."""

from __future__ import annotations

import json
import logging
from typing import Any

from codestrata.application.release.verification.crypto import (
    CryptoError,
    contains_private_key_marker,
    parse_iso8601,
    sha256_hex,
)
from codestrata.application.release.verification.models import (
    SignerRole,
    VerificationProfileId,
    VerificationResult,
    VerificationStatus,
    VerifyRequest,
)
from codestrata.application.release.verification.offline import verify_offline_self_managed
from codestrata.application.release.verification.policy import (
    ReleaseVerificationPolicy,
    default_verification_policy,
)
from codestrata.application.release.verification.sigstore import verify_public_sigstore
from codestrata.domain.contracts.enums import ExecutionPurpose, FreshnessState
from codestrata.domain.contracts.rules import (
    ContractError,
    SignedPackageManifest,
    admit_package,
    parse_signed_package,
)
from codestrata.domain.contracts.serialization import dumps_canonical

logger = logging.getLogger("codestrata.release.verification")


def verify_release_package(
    request: VerifyRequest,
    *,
    policy: ReleaseVerificationPolicy | None = None,
) -> VerificationResult:
    """Verify a signed package against one bounded profile. Never fetches."""

    result = _evaluate_release_package(request, policy=policy)
    logger.info(
        "release verification status=%s reason=%s profile=%s role=%s digest=%s tlog=%s",
        result.status.value,
        result.reason,
        result.profile_id,
        result.signer_role.value,
        result.package_digest or "-",
        result.transparency_log_used,
    )
    return result


def _evaluate_release_package(
    request: VerifyRequest,
    *,
    policy: ReleaseVerificationPolicy | None = None,
) -> VerificationResult:
    active = policy or default_verification_policy()
    limitations = active.limitations
    try:
        bundle_bytes = dumps_canonical(request.bundle).encode("utf-8")
    except (TypeError, ValueError):
        return _early(
            request,
            VerificationStatus.ERROR,
            "bundle_not_canonical_json",
            limitations,
        )
    if len(bundle_bytes) > active.max_bundle_bytes:
        return _early(
            request,
            VerificationStatus.ERROR,
            "bundle_exceeds_budget",
            limitations,
            metadata={"max_bundle_bytes": active.max_bundle_bytes},
        )
    if contains_private_key_marker(request.package) or contains_private_key_marker(
        request.bundle
    ):
        return _early(
            request,
            VerificationStatus.REJECTED,
            "private_key_in_bundle",
            limitations,
        )
    try:
        parse_iso8601(request.evaluation_time)
    except CryptoError:
        return _early(
            request,
            VerificationStatus.REJECTED,
            "invalid_evaluation_time",
            limitations,
        )

    try:
        manifest = parse_signed_package(request.package)
    except ContractError as error:
        reason = str(error)
        status = (
            VerificationStatus.UNSUPPORTED
            if "unsupported" in reason.lower()
            else VerificationStatus.REJECTED
        )
        return _early(request, status, "package_contract_rejected", limitations)

    package_digest = manifest.body_digest
    try:
        admit_package(manifest, request.requested_purpose)
    except ContractError:
        return VerificationResult(
            status=VerificationStatus.WRONG_PURPOSE,
            reason="preview_cannot_authorize_production",
            profile_id=request.profile_id.value,
            signer_role=request.signer_role,
            requested_purpose=request.requested_purpose,
            freshness=FreshnessState.NOT_APPLICABLE,
            package_digest=package_digest,
            limitations=limitations,
        )

    expiry = _package_expiry_status(manifest, request.evaluation_time)
    if expiry is not None:
        return VerificationResult(
            status=expiry[0],
            reason=expiry[1],
            profile_id=request.profile_id.value,
            signer_role=request.signer_role,
            requested_purpose=request.requested_purpose,
            freshness=FreshnessState.NOT_APPLICABLE,
            package_digest=package_digest,
            limitations=limitations,
        )

    if request.profile_id is VerificationProfileId.SIGSTORE_PUBLIC:
        if request.signer_role is not SignerRole.PUBLIC_DISTRIBUTION:
            return _early(
                request,
                VerificationStatus.REJECTED,
                "role_profile_mismatch",
                limitations,
                package_digest=package_digest,
            )
        artifact_digest = sha256_hex(request.artifact_bytes)
        if not _digest_bound(manifest, artifact_digest):
            return VerificationResult(
                status=VerificationStatus.TAMPERED,
                reason="artifact_not_bound_in_package",
                profile_id=request.profile_id.value,
                signer_role=request.signer_role,
                requested_purpose=request.requested_purpose,
                freshness=FreshnessState.NOT_APPLICABLE,
                artifact_digest=artifact_digest,
                package_digest=package_digest,
                limitations=limitations,
            )
        return verify_public_sigstore(
            request,
            active,
            package_digest=package_digest,
            artifact_digest=artifact_digest,
        )

    if request.profile_id is VerificationProfileId.OFFLINE_SELF_MANAGED:
        if request.signer_role is not SignerRole.PRIVATE_RESULT:
            return _early(
                request,
                VerificationStatus.REJECTED,
                "role_profile_mismatch",
                limitations,
                package_digest=package_digest,
            )
        canonical_body = dumps_canonical(manifest.body.model_dump(mode="json")).encode("utf-8")
        return verify_offline_self_managed(
            request,
            active,
            package_digest=package_digest,
            artifact_digest=package_digest,
            package_purpose=manifest.body.execution_purpose,
            canonical_body=canonical_body,
        )

    return _early(request, VerificationStatus.UNSUPPORTED, "unsupported_profile", limitations)


def verify_payload(
    payload: dict[str, Any],
    *,
    policy: ReleaseVerificationPolicy | None = None,
) -> VerificationResult:
    """Verify from a JSON-like request. ``artifact_bytes`` may be base64."""

    from codestrata.application.release.verification.crypto import decode_b64
    from codestrata.application.release.verification.models import (
        OfflineTrustEntry,
        RevocationInventory,
    )

    profile = VerificationProfileId(str(payload.get("profile_id") or ""))
    role = SignerRole(str(payload.get("signer_role") or ""))
    purpose = ExecutionPurpose(str(payload.get("requested_purpose") or ""))
    package = payload.get("package")
    bundle = payload.get("bundle")
    if not isinstance(package, dict) or not isinstance(bundle, dict):
        raise ValueError("package and bundle must be objects")
    artifact = payload.get("artifact_bytes")
    if isinstance(artifact, str) and artifact:
        artifact_bytes = decode_b64(artifact, label="artifact")
    elif isinstance(artifact, bytes):
        artifact_bytes = artifact
    else:
        artifact_bytes = b""
    store_raw = payload.get("trust_store") or ()
    rev_raw = payload.get("revocation")
    trust_store = tuple(
        OfflineTrustEntry.model_validate(item) for item in store_raw if isinstance(item, dict)
    )
    revocation = (
        RevocationInventory.model_validate(rev_raw) if isinstance(rev_raw, dict) else None
    )
    request = VerifyRequest(
        profile_id=profile,
        signer_role=role,
        requested_purpose=purpose,
        package=package,
        artifact_bytes=artifact_bytes,
        bundle=bundle,
        evaluation_time=str(payload.get("evaluation_time") or ""),
        expected_identity=_optional_str(payload.get("expected_identity")),
        expected_issuer=_optional_str(payload.get("expected_issuer")),
        trust_root_pem=_optional_str(payload.get("trust_root_pem")),
        rekor_public_pem=_optional_str(payload.get("rekor_public_pem")),
        trust_store=trust_store,
        revocation=revocation,
        key_id=_optional_str(payload.get("key_id")),
    )
    return verify_release_package(request, policy=policy)


def _digest_bound(manifest: SignedPackageManifest, artifact_digest: str) -> bool:
    names = {item.digest for item in manifest.body.payload_digests}
    return artifact_digest in names or artifact_digest == manifest.body_digest


def _package_expiry_status(
    manifest: SignedPackageManifest,
    evaluation_time: str,
) -> tuple[VerificationStatus, str] | None:
    body = manifest.body
    try:
        when = parse_iso8601(evaluation_time)
        if body.validity_not_after:
            if when > parse_iso8601(body.validity_not_after):
                return VerificationStatus.EXPIRED, "package_expired"
        if body.validity_not_before:
            if when < parse_iso8601(body.validity_not_before):
                return VerificationStatus.EXPIRED, "package_not_yet_valid"
    except CryptoError:
        return VerificationStatus.REJECTED, "invalid_package_validity_timestamp"
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _early(
    request: VerifyRequest,
    status: VerificationStatus,
    reason: str,
    limitations: tuple[str, ...],
    *,
    package_digest: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> VerificationResult:
    return VerificationResult(
        status=status,
        reason=reason,
        profile_id=request.profile_id.value,
        signer_role=request.signer_role,
        requested_purpose=request.requested_purpose,
        freshness=FreshnessState.NOT_APPLICABLE,
        package_digest=package_digest,
        limitations=limitations,
        metadata=metadata or {},
    )


def dumps_result(result: VerificationResult) -> str:
    return json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


__all__ = ["dumps_result", "verify_payload", "verify_release_package"]
