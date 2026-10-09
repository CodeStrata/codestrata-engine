"""Local HMAC signing for export originals and projections (E13.3).

This is a local integrity profile, not public Sigstore (E14.1). Key material
never enters logs, public manifests, or canonical bodies. Signature bytes live
in operational metadata beside the body digest.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256

from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.telemetry.canaries import collection_surface_violations
from codestrata.telemetry.export_projection_models import (
    ProjectionEnvelopeError,
    SignatureMetadata,
)
from codestrata.telemetry.export_projection_policy import (
    HMAC_SHA256_ALGORITHM,
    LOCAL_HMAC_VERIFICATION_PROFILE,
    default_projection_policy,
)

logger = logging.getLogger("codestrata.telemetry.signed_projection")

LOCAL_TEST_KEY_ID = "local-export-hmac-1"
PREVIEW_TEST_KEY_ID = "local-export-hmac-preview"
UNTRUSTED_TEST_KEY_ID = "untrusted-export-hmac"

# Explicit test-only material. Never a product distribution secret.
_LOCAL_TEST_SECRET = b"codestrata-export-projection-test-key-not-for-production"
_PREVIEW_TEST_SECRET = b"codestrata-export-projection-preview-key-not-for-production"
_UNTRUSTED_TEST_SECRET = b"codestrata-export-projection-untrusted-key-not-for-production"


@dataclass(frozen=True, slots=True)
class LocalExportKey:
    key_id: str
    purpose: ExecutionPurpose
    secret: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "secret", bytes(self.secret))
        if not self.key_id.strip():
            raise ProjectionEnvelopeError("key_id must not be blank")
        if not self.secret:
            raise ProjectionEnvelopeError("signing secret must not be empty")


class LocalExportKeyring:
    """Purpose-bound local HMAC keys. Secrets are never serialized."""

    def __init__(
        self,
        keys: Iterable[LocalExportKey],
        *,
        trusted_ids: Iterable[str] | None = None,
    ) -> None:
        packed = tuple(keys)
        by_id: dict[str, LocalExportKey] = {}
        for key in packed:
            if key.key_id in by_id:
                raise ProjectionEnvelopeError(f"duplicate export key id: {key.key_id}")
            by_id[key.key_id] = key
        self._keys = by_id
        if trusted_ids is None:
            self._trusted = frozenset(by_id)
        else:
            self._trusted = frozenset(str(item) for item in trusted_ids)

    def get(self, key_id: str) -> LocalExportKey | None:
        return self._keys.get(key_id)

    def is_trusted(self, key_id: str) -> bool:
        return key_id in self._trusted and key_id in self._keys

    def public_inventory(self) -> tuple[dict[str, str], ...]:
        rows = [
            {"key_id": key.key_id, "purpose": key.purpose.value}
            for key in self._keys.values()
        ]
        return tuple(sorted(rows, key=lambda item: item["key_id"]))

    def sign(
        self,
        body: bytes,
        *,
        key_id: str,
        purpose: ExecutionPurpose,
    ) -> SignatureMetadata:
        key = self._keys.get(key_id)
        if key is None:
            raise ProjectionEnvelopeError("signing key unavailable")
        if key.purpose is not purpose:
            raise ProjectionEnvelopeError("signing key purpose does not match")
        policy = default_projection_policy()
        digest = hmac.new(key.secret, body, sha256).hexdigest()
        logger.info(
            "signed export body key_id=%s purpose=%s profile=%s",
            key.key_id,
            purpose.value,
            policy.verification_profile,
        )
        return SignatureMetadata(
            algorithm=HMAC_SHA256_ALGORITHM,
            key_id=key.key_id,
            purpose=purpose.value,
            signature=digest,
            verification_profile=LOCAL_HMAC_VERIFICATION_PROFILE,
        )

    def signature_matches(
        self,
        body: bytes,
        metadata: SignatureMetadata,
    ) -> bool:
        key = self._keys.get(metadata.key_id)
        if key is None:
            return False
        expected = hmac.new(key.secret, body, sha256).hexdigest()
        return hmac.compare_digest(expected, metadata.signature)


def default_local_keyring() -> LocalExportKeyring:
    return LocalExportKeyring(
        (
            LocalExportKey(
                LOCAL_TEST_KEY_ID,
                ExecutionPurpose.PRODUCTION,
                _LOCAL_TEST_SECRET,
            ),
            LocalExportKey(
                PREVIEW_TEST_KEY_ID,
                ExecutionPurpose.PREVIEW,
                _PREVIEW_TEST_SECRET,
            ),
        )
    )


def keyring_with_untrusted() -> LocalExportKeyring:
    return LocalExportKeyring(
        (
            LocalExportKey(
                LOCAL_TEST_KEY_ID,
                ExecutionPurpose.PRODUCTION,
                _LOCAL_TEST_SECRET,
            ),
            LocalExportKey(
                UNTRUSTED_TEST_KEY_ID,
                ExecutionPurpose.PRODUCTION,
                _UNTRUSTED_TEST_SECRET,
            ),
        ),
        trusted_ids=(LOCAL_TEST_KEY_ID,),
    )


def assert_no_secret_leak(payload: object, *, extra: Iterable[str] = ()) -> None:
    """Reject public/private-data logging of key material or prohibited fields."""

    violations = collection_surface_violations(payload)
    if violations:
        raise ProjectionEnvelopeError("prohibited data in public projection payload")
    blob = str(payload)
    secrets = (
        _LOCAL_TEST_SECRET.decode("ascii"),
        _PREVIEW_TEST_SECRET.decode("ascii"),
        _UNTRUSTED_TEST_SECRET.decode("ascii"),
        *tuple(extra),
    )
    for secret in secrets:
        if secret and secret in blob:
            raise ProjectionEnvelopeError("signing secret must not appear in public payload")
    if isinstance(payload, Mapping):
        for key in payload:
            lowered = str(key).lower()
            if lowered in {"secret", "hmac_key", "private_key"}:
                raise ProjectionEnvelopeError("private key fields cannot be public")


def default_key_id_for_purpose(purpose: ExecutionPurpose) -> str:
    if purpose is ExecutionPurpose.PREVIEW:
        return PREVIEW_TEST_KEY_ID
    if purpose is ExecutionPurpose.PRODUCTION:
        return LOCAL_TEST_KEY_ID
    raise ProjectionEnvelopeError("candidate_validation is not an export signing purpose")


__all__ = [
    "LOCAL_TEST_KEY_ID",
    "PREVIEW_TEST_KEY_ID",
    "UNTRUSTED_TEST_KEY_ID",
    "LocalExportKey",
    "LocalExportKeyring",
    "assert_no_secret_leak",
    "default_key_id_for_purpose",
    "default_local_keyring",
    "keyring_with_untrusted",
]
