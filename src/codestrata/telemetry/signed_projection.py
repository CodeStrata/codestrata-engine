"""Build immutable originals and separate signed export projections (E13.3)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from codestrata.domain.contracts.enums import ExecutionPurpose, ExportMode
from codestrata.domain.contracts.serialization import (
    PLACEHOLDER_DIGEST,
    digest_canonical,
    require_content_digest,
    require_pinned_version,
)
from codestrata.telemetry.canaries import (
    collection_surface_violations,
    exceeds_serialization_budget,
)
from codestrata.telemetry.export_modes import (
    ExportCategoryManifest,
    ExportModeError,
    resolve_export_manifest,
)
from codestrata.telemetry.export_projection_models import (
    HeadlessExportResult,
    OriginalExportPackage,
    ProjectionEnvelopeError,
    ProjectionVerification,
    ProjectionVerificationStatus,
    SignedExportProjection,
    canonical_body_bytes,
    known_execution_purpose,
)
from codestrata.telemetry.export_projection_policy import (
    EngineExportProjectionPolicy,
    default_projection_policy,
)
from codestrata.telemetry.export_signing import (
    LocalExportKeyring,
    assert_no_secret_leak,
    default_key_id_for_purpose,
    default_local_keyring,
)

logger = logging.getLogger("codestrata.telemetry.signed_projection")

DEFAULT_PACKAGE_ID = "codestrata.local-export-original"
DEFAULT_PACKAGE_VERSION = "1.0.0"
DEFAULT_VALIDITY_NOT_AFTER = "2027-09-15T00:00:00Z"


def build_original_package(
    *,
    artifact_digest: str | None = None,
    purpose: ExecutionPurpose | str = ExecutionPurpose.PRODUCTION,
    categories: tuple[str, ...] | None = None,
    package_id: str = DEFAULT_PACKAGE_ID,
    package_version: str = DEFAULT_PACKAGE_VERSION,
    validity_not_before: str | None = None,
    validity_not_after: str | None = DEFAULT_VALIDITY_NOT_AFTER,
    keyring: LocalExportKeyring | None = None,
    key_id: str | None = None,
    sign: bool = True,
    policy: EngineExportProjectionPolicy | None = None,
) -> OriginalExportPackage:
    """Seal a local original. Signature metadata stays outside canonical bytes."""

    active = policy or default_projection_policy()
    parsed_purpose = _require_purpose(purpose)
    digest = _normalize_artifact_digest(artifact_digest)
    version = require_pinned_version(package_version, label="package_version")
    default_categories = resolve_export_manifest(ExportMode.FULL).allowed_categories
    cats = tuple(sorted(set(categories or default_categories)))
    body = {
        "artifact_digest": digest,
        "categories": list(cats),
        "export_policy_version": active.export_policy_version,
        "package_id": package_id,
        "package_version": version,
        "purpose": parsed_purpose.value,
        "schema": active.original_schema,
        "schema_version": active.schema_version,
        "validity_not_after": validity_not_after,
        "validity_not_before": validity_not_before,
    }
    _reject_prohibited(body)
    canonical = canonical_body_bytes(body)
    package_digest = digest_canonical(body)
    signature = None
    if sign:
        ring = keyring or default_local_keyring()
        used_id = key_id or default_key_id_for_purpose(parsed_purpose)
        signature = ring.sign(canonical, key_id=used_id, purpose=parsed_purpose)
    original = OriginalExportPackage(
        schema=active.original_schema,
        schema_version=active.schema_version,
        package_id=package_id,
        package_version=version,
        purpose=parsed_purpose.value,
        categories=cats,
        artifact_digest=digest,
        package_digest=package_digest,
        canonical_bytes=canonical,
        export_policy_version=active.export_policy_version,
        validity_not_before=validity_not_before,
        validity_not_after=validity_not_after,
        signature=signature,
    )
    assert_no_secret_leak(original.to_manifest_dict())
    if original.canonical_bytes != canonical:
        raise ProjectionEnvelopeError("original canonical bytes mutated during seal")
    logger.info(
        "sealed original package_digest=%s purpose=%s categories=%s",
        package_digest,
        parsed_purpose.value,
        ",".join(cats),
    )
    return original


def project_export(
    original: OriginalExportPackage,
    mode: ExportMode | str,
    *,
    withheld_categories: tuple[str, ...] | None = None,
    allowed_categories: tuple[str, ...] | None = None,
    keyring: LocalExportKeyring | None = None,
    key_id: str | None = None,
    sign: bool = True,
    policy: EngineExportProjectionPolicy | None = None,
) -> tuple[OriginalExportPackage, SignedExportProjection]:
    """Produce a separate projection. Returns the unchanged original plus projection."""

    active = policy or default_projection_policy()
    snapshot = bytes(original.canonical_bytes)
    manifest = resolve_export_manifest(
        mode,
        withheld_categories=withheld_categories,
        allowed_categories=allowed_categories,
    )
    parsed_purpose = _require_purpose(original.purpose)
    if original.package_digest != digest_canonical(original.body_dict()):
        raise ProjectionEnvelopeError("original package digest does not match canonical body")
    if snapshot != original.canonical_bytes:
        raise ProjectionEnvelopeError("original canonical bytes mutated before projection")
    body = {
        "allowed_categories": list(manifest.allowed_categories),
        "export_mode": manifest.mode.value,
        "export_policy_version": original.export_policy_version,
        "externally_verified_categories": [],
        "original_digest": original.package_digest,
        "projection_policy_version": active.policy_version,
        "purpose": original.purpose,
        "schema": active.projection_schema,
        "schema_version": active.schema_version,
        "unseen_evidence_externally_verified": False,
        "verification_profile": active.verification_profile,
        "withheld_categories": list(manifest.withheld_categories),
    }
    _reject_prohibited(body)
    canonical = canonical_body_bytes(body)
    package_digest = digest_canonical(body)
    if exceeds_serialization_budget(body, max_bytes=active.max_projection_size_bytes):
        raise ProjectionEnvelopeError("projection exceeds maximum size")
    if len(canonical) > active.max_projection_size_bytes:
        raise ProjectionEnvelopeError("projection exceeds maximum size")
    signature = None
    if sign:
        ring = keyring or default_local_keyring()
        used_id = key_id or default_key_id_for_purpose(parsed_purpose)
        signature = ring.sign(canonical, key_id=used_id, purpose=parsed_purpose)
    projection = SignedExportProjection(
        schema=active.projection_schema,
        schema_version=active.schema_version,
        original_digest=original.package_digest,
        package_digest=package_digest,
        export_mode=manifest.mode.value,
        export_policy_version=original.export_policy_version,
        projection_policy_version=active.policy_version,
        allowed_categories=manifest.allowed_categories,
        withheld_categories=manifest.withheld_categories,
        verification_profile=active.verification_profile,
        purpose=original.purpose,
        canonical_bytes=canonical,
        signature=signature,
        transmission_performed=False,
    )
    assert_no_secret_leak(projection.to_manifest_dict())
    if original.canonical_bytes != snapshot:
        raise ProjectionEnvelopeError("redaction mutated signed canonical bytes")
    logger.info(
        "projected export mode=%s original_digest=%s withheld=%s",
        manifest.mode.value,
        original.package_digest,
        ",".join(manifest.withheld_categories) or "-",
    )
    return original, projection


def run_headless_export(
    mode: ExportMode | str,
    *,
    withheld_categories: tuple[str, ...] | None = None,
    allowed_categories: tuple[str, ...] | None = None,
    artifact_digest: str | None = None,
    purpose: ExecutionPurpose | str = ExecutionPurpose.PRODUCTION,
    original: OriginalExportPackage | None = None,
    keyring: LocalExportKeyring | None = None,
    key_id: str | None = None,
    policy: EngineExportProjectionPolicy | None = None,
) -> HeadlessExportResult:
    """Headless full/restricted/no-export. Never transfers; local utility retained."""

    ring = keyring or default_local_keyring()
    source = original or build_original_package(
        artifact_digest=artifact_digest,
        purpose=purpose,
        keyring=ring,
        key_id=key_id,
        policy=policy,
    )
    preserved, projection = project_export(
        source,
        mode,
        withheld_categories=withheld_categories,
        allowed_categories=allowed_categories,
        keyring=ring,
        key_id=key_id,
        policy=policy,
    )
    manifest = resolve_export_manifest(
        mode,
        withheld_categories=withheld_categories,
        allowed_categories=allowed_categories,
    )
    return HeadlessExportResult(
        mode=manifest.mode,
        original=preserved,
        projection=projection,
        withheld_categories=manifest.withheld_categories,
        allowed_categories=manifest.allowed_categories,
        transmission_performed=False,
        local_utility_retained=True,
    )


def verify_signed_projection(
    projection: SignedExportProjection,
    *,
    original: OriginalExportPackage | None,
    keyring: LocalExportKeyring,
    requested_purpose: ExecutionPurpose | str,
    now: str | None = None,
) -> ProjectionVerification:
    """Verify projection integrity against the local original and keyring."""

    requested = _require_purpose(requested_purpose)
    if original is None:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.UNAVAILABLE,
            reason="original_unavailable",
            projection_digest=projection.package_digest,
        )
    expected_original = digest_canonical(original.body_dict())
    if original.package_digest != expected_original:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.TAMPERED,
            reason="original_digest_mismatch",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if original.canonical_bytes != canonical_body_bytes(original.body_dict()):
        return ProjectionVerification(
            status=ProjectionVerificationStatus.TAMPERED,
            reason="original_canonical_bytes_mutated",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if projection.original_digest != original.package_digest:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.REJECTED,
            reason="projection_original_digest_mismatch",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    expected_projection = digest_canonical(projection.body_dict())
    if projection.package_digest != expected_projection:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.TAMPERED,
            reason="projection_digest_mismatch",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if projection.canonical_bytes != canonical_body_bytes(projection.body_dict()):
        return ProjectionVerification(
            status=ProjectionVerificationStatus.TAMPERED,
            reason="projection_canonical_bytes_mutated",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if projection.unseen_evidence_externally_verified:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.REJECTED,
            reason="unseen_evidence_claimed_verified",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    withheld = set(projection.withheld_categories)
    if withheld.intersection(projection.externally_verified_categories):
        return ProjectionVerification(
            status=ProjectionVerificationStatus.REJECTED,
            reason="withheld_claimed_externally_verified",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    original_purpose = _require_purpose(original.purpose)
    if requested is ExecutionPurpose.PRODUCTION and original_purpose is ExecutionPurpose.PREVIEW:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.WRONG_PURPOSE,
            reason="preview_cannot_authorize_production",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if requested is not original_purpose:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.WRONG_PURPOSE,
            reason="purpose_mismatch",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
            trusted_key=False,
        )
    stale = _stale_reason(original, now=now)
    if stale is not None:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.STALE,
            reason=stale,
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if projection.signature is None or original.signature is None:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.UNVERIFIED,
            reason="signature_unavailable",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if projection.signature.purpose != requested.value:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.WRONG_PURPOSE,
            reason="signature_purpose_mismatch",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    trusted = keyring.is_trusted(projection.signature.key_id)
    if not trusted:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.UNVERIFIED,
            reason="untrusted_key",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
            trusted_key=False,
        )
    key = keyring.get(projection.signature.key_id)
    if key is None:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.UNAVAILABLE,
            reason="signing_key_unavailable",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
        )
    if key.purpose is not requested:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.WRONG_PURPOSE,
            reason="key_purpose_mismatch",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
            trusted_key=True,
        )
    original_ok = keyring.signature_matches(original.canonical_bytes, original.signature)
    projection_ok = keyring.signature_matches(projection.canonical_bytes, projection.signature)
    if not original_ok or not projection_ok:
        return ProjectionVerification(
            status=ProjectionVerificationStatus.TAMPERED,
            reason="signature_mismatch",
            original_digest=original.package_digest,
            projection_digest=projection.package_digest,
            trusted_key=True,
        )
    return ProjectionVerification(
        status=ProjectionVerificationStatus.VERIFIED,
        reason="ok",
        original_digest=original.package_digest,
        projection_digest=projection.package_digest,
        trusted_key=True,
    )


def parse_original_package(payload: object) -> OriginalExportPackage:
    if isinstance(payload, OriginalExportPackage):
        return payload
    if not isinstance(payload, dict):
        raise ProjectionEnvelopeError("original payload must be a mapping")
    body = payload.get("body")
    if not isinstance(body, dict):
        raise ProjectionEnvelopeError("original body must be a mapping")
    _reject_prohibited(payload)
    return build_original_package(
        artifact_digest=str(body.get("artifact_digest") or ""),
        purpose=str(body.get("purpose") or ExecutionPurpose.PRODUCTION.value),
        categories=tuple(str(item) for item in (body.get("categories") or ())),
        package_id=str(body.get("package_id") or DEFAULT_PACKAGE_ID),
        package_version=str(body.get("package_version") or DEFAULT_PACKAGE_VERSION),
        validity_not_before=_optional_text(body.get("validity_not_before")),
        validity_not_after=_optional_text(body.get("validity_not_after")),
        sign=False,
    )


def _require_purpose(value: ExecutionPurpose | str) -> ExecutionPurpose:
    if isinstance(value, ExecutionPurpose):
        parsed: ExecutionPurpose | None = value
    else:
        parsed = known_execution_purpose(str(value).strip().lower())
    if parsed is None:
        raise ProjectionEnvelopeError("unsupported execution purpose")
    if parsed is ExecutionPurpose.CANDIDATE_VALIDATION:
        raise ProjectionEnvelopeError("candidate_validation is not an export signing purpose")
    return parsed


def _normalize_artifact_digest(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return PLACEHOLDER_DIGEST
    try:
        return require_content_digest(value, label="artifact_digest")
    except ValueError as error:
        raise ProjectionEnvelopeError(
            "artifact_digest must be a pinned sha256 hex digest"
        ) from error


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _reject_prohibited(payload: dict[str, Any]) -> None:
    if collection_surface_violations(payload):
        raise ProjectionEnvelopeError("prohibited data in export projection")


def _stale_reason(original: OriginalExportPackage, *, now: str | None) -> str | None:
    if original.validity_not_after is None:
        return None
    clock = now or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        expiry = _parse_iso(original.validity_not_after)
        current = _parse_iso(clock)
    except ValueError:
        return "invalid_validity_timestamp"
    if current > expiry:
        return "package_expired"
    if original.validity_not_before:
        try:
            start = _parse_iso(original.validity_not_before)
        except ValueError:
            return "invalid_validity_timestamp"
        if current < start:
            return "package_not_yet_valid"
    return None


def _parse_iso(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


__all__ = [
    "DEFAULT_PACKAGE_ID",
    "DEFAULT_PACKAGE_VERSION",
    "DEFAULT_VALIDITY_NOT_AFTER",
    "ExportCategoryManifest",
    "ExportModeError",
    "build_original_package",
    "parse_original_package",
    "project_export",
    "run_headless_export",
    "verify_signed_projection",
]
