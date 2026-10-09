"""Versioned package/release verification profiles (E14.1).

Public Sigstore verification is identity/issuer/bundle based and may use a
transparency log of digests and signatures only. The private offline profile
uses a self-managed key, forbids a public log, and applies freshness limits
instead of instant revocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from codestrata.application.release.verification.models import (
    SignerRole,
    VerificationProfileId,
)
from codestrata.resources import resources_root

POLICY_ID = "engine-release-verification-profiles"
POLICY_VERSION = "1.0"
POLICY_URN = f"{POLICY_ID}:{POLICY_VERSION}"
POLICY_RESOURCE = ("release", "verification-profiles-v1.yaml")

DEFAULT_MAX_BUNDLE_BYTES = 65_536
DEFAULT_REVOCATION_MAX_AGE_SECONDS = 604_800
FULCIO_ISSUER_OID = "1.3.6.1.4.1.57264.1.1"
PUBLIC_ALGORITHM = "ecdsa-p256-sha256"
PRIVATE_ALGORITHM = "ed25519"
HASHEDREKORD_KIND = "hashedrekord"
HASHEDREKORD_API = "0.0.1"

_LIMITATIONS: tuple[str, ...] = (
    "offline_bundle_verification_only",
    "no_live_fulcio_rekor_fetch",
    "public_and_private_signer_roles_distinct",
    "private_rule_result_contents_never_enter_public_tlog",
    "offline_revocation_is_freshness_limited",
    "instant_revocation_not_claimed",
    "no_consent_local_utility_preserved",
    "signature_bytes_outside_canonical_body",
    "official_oidc_publication_is_e14_4",
)


class VerificationPolicyError(ValueError):
    """Raised when the E14.1 profile policy is corrupt or unsupported."""


@dataclass(frozen=True, slots=True)
class PublicSigstoreProfile:
    profile_id: str = VerificationProfileId.SIGSTORE_PUBLIC.value
    signer_role: str = SignerRole.PUBLIC_DISTRIBUTION.value
    algorithm: str = PUBLIC_ALGORITHM
    expected_identity: str = (
        "https://github.com/CodeStrata/codestrata-engine/.github/workflows/"
        "release.yml@refs/tags/v*"
    )
    expected_issuer: str = "https://token.actions.githubusercontent.com"
    certificate_oidc_issuer_oid: str = FULCIO_ISSUER_OID
    transparency_log_required: bool = True
    transparency_log_forbidden: bool = False
    network_mode: str = "offline"


@dataclass(frozen=True, slots=True)
class OfflineSelfManagedProfile:
    profile_id: str = VerificationProfileId.OFFLINE_SELF_MANAGED.value
    signer_role: str = SignerRole.PRIVATE_RESULT.value
    algorithm: str = PRIVATE_ALGORITHM
    transparency_log_required: bool = False
    transparency_log_forbidden: bool = True
    network_mode: str = "offline"
    revocation_max_age_seconds: int = DEFAULT_REVOCATION_MAX_AGE_SECONDS
    instant_revocation: bool = False
    stale_behavior: str = "unknown_not_revoked"


@dataclass(frozen=True, slots=True)
class ReleaseVerificationPolicy:
    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION
    schema_name: str = "codestrata.release.verification-profiles.v1"
    schema_version: str = "1.0.0"
    max_bundle_bytes: int = DEFAULT_MAX_BUNDLE_BYTES
    public_sigstore: PublicSigstoreProfile = PublicSigstoreProfile()
    private_offline: OfflineSelfManagedProfile = OfflineSelfManagedProfile()
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != POLICY_ID:
            raise VerificationPolicyError("unsupported verification policy id")
        if self.policy_version != POLICY_VERSION:
            raise VerificationPolicyError("unsupported verification policy version")
        if self.max_bundle_bytes <= 0:
            raise VerificationPolicyError("max_bundle_bytes must be positive")
        public = self.public_sigstore
        private = self.private_offline
        if public.profile_id != VerificationProfileId.SIGSTORE_PUBLIC.value:
            raise VerificationPolicyError("unsupported public profile id")
        if private.profile_id != VerificationProfileId.OFFLINE_SELF_MANAGED.value:
            raise VerificationPolicyError("unsupported private profile id")
        if public.signer_role != SignerRole.PUBLIC_DISTRIBUTION.value:
            raise VerificationPolicyError("public profile role must be public_distribution")
        if private.signer_role != SignerRole.PRIVATE_RESULT.value:
            raise VerificationPolicyError("private profile role must be private_result")
        if public.algorithm != PUBLIC_ALGORITHM:
            raise VerificationPolicyError("unsupported public algorithm")
        if private.algorithm != PRIVATE_ALGORITHM:
            raise VerificationPolicyError("unsupported private algorithm")
        if public.network_mode != "offline" or private.network_mode != "offline":
            raise VerificationPolicyError("verification profiles are offline-only")
        if not public.transparency_log_required or public.transparency_log_forbidden:
            raise VerificationPolicyError("public profile requires a digest-only tlog")
        if private.transparency_log_required or not private.transparency_log_forbidden:
            raise VerificationPolicyError("private profile must forbid a public tlog")
        if private.instant_revocation:
            raise VerificationPolicyError("instant_revocation must be false")
        if private.stale_behavior != "unknown_not_revoked":
            raise VerificationPolicyError("stale revocation cannot be treated as revoked")
        if private.revocation_max_age_seconds <= 0:
            raise VerificationPolicyError("revocation_max_age_seconds must be positive")
        if public.signer_role == private.signer_role:
            raise VerificationPolicyError("signer roles must be distinct")

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "limitations": list(self.limitations),
            "max_bundle_bytes": self.max_bundle_bytes,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "private_offline": {
                "algorithm": self.private_offline.algorithm,
                "instant_revocation": self.private_offline.instant_revocation,
                "network_mode": self.private_offline.network_mode,
                "profile_id": self.private_offline.profile_id,
                "revocation_max_age_seconds": (
                    self.private_offline.revocation_max_age_seconds
                ),
                "signer_role": self.private_offline.signer_role,
                "stale_behavior": self.private_offline.stale_behavior,
                "transparency_log_forbidden": (
                    self.private_offline.transparency_log_forbidden
                ),
                "transparency_log_required": (
                    self.private_offline.transparency_log_required
                ),
            },
            "public_sigstore": {
                "algorithm": self.public_sigstore.algorithm,
                "certificate_oidc_issuer_oid": (
                    self.public_sigstore.certificate_oidc_issuer_oid
                ),
                "expected_identity": self.public_sigstore.expected_identity,
                "expected_issuer": self.public_sigstore.expected_issuer,
                "network_mode": self.public_sigstore.network_mode,
                "profile_id": self.public_sigstore.profile_id,
                "signer_role": self.public_sigstore.signer_role,
                "transparency_log_forbidden": (
                    self.public_sigstore.transparency_log_forbidden
                ),
                "transparency_log_required": (
                    self.public_sigstore.transparency_log_required
                ),
            },
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
        }
        return {key: payload[key] for key in sorted(payload)}


def default_verification_policy() -> ReleaseVerificationPolicy:
    return ReleaseVerificationPolicy()


def load_packaged_verification_policy() -> ReleaseVerificationPolicy:
    """Load the packaged YAML and bind it to the versioned policy object."""

    node = resources_root()
    for part in POLICY_RESOURCE:
        node = node.joinpath(part)
    raw = yaml.safe_load(node.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise VerificationPolicyError("verification policy must be a mapping")
    return policy_from_mapping(raw)


def policy_from_mapping(raw: dict[str, Any]) -> ReleaseVerificationPolicy:
    public_raw = raw.get("public_sigstore")
    private_raw = raw.get("private_offline")
    if not isinstance(public_raw, dict) or not isinstance(private_raw, dict):
        raise VerificationPolicyError("both verification profiles are required")
    revocation = private_raw.get("revocation")
    if not isinstance(revocation, dict):
        raise VerificationPolicyError("private profile must declare revocation policy")
    public = PublicSigstoreProfile(
        profile_id=str(public_raw.get("profile_id") or ""),
        signer_role=str(public_raw.get("signer_role") or ""),
        algorithm=str(public_raw.get("algorithm") or ""),
        expected_identity=str(public_raw.get("expected_identity") or ""),
        expected_issuer=str(public_raw.get("expected_issuer") or ""),
        certificate_oidc_issuer_oid=str(
            public_raw.get("certificate_oidc_issuer_oid") or FULCIO_ISSUER_OID
        ),
        transparency_log_required=bool(public_raw.get("transparency_log_required")),
        transparency_log_forbidden=bool(public_raw.get("transparency_log_forbidden")),
        network_mode=str(public_raw.get("network_mode") or ""),
    )
    private = OfflineSelfManagedProfile(
        profile_id=str(private_raw.get("profile_id") or ""),
        signer_role=str(private_raw.get("signer_role") or ""),
        algorithm=str(private_raw.get("algorithm") or ""),
        transparency_log_required=bool(private_raw.get("transparency_log_required")),
        transparency_log_forbidden=bool(
            private_raw.get("transparency_log_forbidden", True)
        ),
        network_mode=str(private_raw.get("network_mode") or ""),
        revocation_max_age_seconds=int(
            revocation.get("max_age_seconds") or DEFAULT_REVOCATION_MAX_AGE_SECONDS
        ),
        instant_revocation=bool(revocation.get("instant_revocation")),
        stale_behavior=str(revocation.get("stale_behavior") or ""),
    )
    limitations = raw.get("limitations")
    limit_tuple = (
        tuple(str(item) for item in limitations)
        if isinstance(limitations, list)
        else _LIMITATIONS
    )
    return ReleaseVerificationPolicy(
        policy_id=str(raw.get("policy_id") or ""),
        policy_version=str(raw.get("policy_version") or ""),
        schema_name=str(raw.get("schema_name") or ""),
        schema_version=str(raw.get("schema_version") or ""),
        max_bundle_bytes=int(raw.get("max_bundle_bytes") or DEFAULT_MAX_BUNDLE_BYTES),
        public_sigstore=public,
        private_offline=private,
        limitations=limit_tuple,
    )


__all__ = [
    "DEFAULT_MAX_BUNDLE_BYTES",
    "DEFAULT_REVOCATION_MAX_AGE_SECONDS",
    "FULCIO_ISSUER_OID",
    "HASHEDREKORD_API",
    "HASHEDREKORD_KIND",
    "POLICY_ID",
    "POLICY_RESOURCE",
    "POLICY_URN",
    "POLICY_VERSION",
    "PRIVATE_ALGORITHM",
    "PUBLIC_ALGORITHM",
    "OfflineSelfManagedProfile",
    "PublicSigstoreProfile",
    "ReleaseVerificationPolicy",
    "VerificationPolicyError",
    "default_verification_policy",
    "load_packaged_verification_policy",
    "policy_from_mapping",
]
