"""Build real cryptographic E14.1 fixtures (test-only keys, not product secrets)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID, ObjectIdentifier

from codestrata.application.release.verification.crypto import encode_b64, sha256_hex
from codestrata.application.release.verification.models import SignerRole
from codestrata.application.release.verification.policy import FULCIO_ISSUER_OID
from codestrata.application.release.verification.sigstore import (
    BUNDLE_MEDIA_TYPE,
    hashedrekord_body,
    signed_entry_timestamp_message,
)
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.examples_e01_3 import example_effective
from codestrata.domain.contracts.rules import (
    PackageCompatibility,
    PayloadDigest,
    SignedPackageBody,
    seal_package,
)
from codestrata.domain.contracts.serialization import dumps_canonical

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "verification"
EVALUATION_TIME = "2026-09-21T00:00:00Z"
INTEGRATED_TIME = "2026-09-21T00:00:00Z"
IDENTITY = (
    "https://github.com/CodeStrata/codestrata-engine/.github/workflows/"
    "release.yml@refs/tags/v0.2.1"
)
ISSUER = "https://token.actions.githubusercontent.com"
WRONG_ISSUER = "https://oidc.example.invalid"
ARTIFACT = b"codestrata-engine-public-artifact-v1.0.0\n"
NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
NOT_AFTER = datetime(2027, 9, 15, tzinfo=UTC)
EXPIRED_AFTER = datetime(2026, 6, 1, tzinfo=UTC)

_FULCIO_OID = ObjectIdentifier(FULCIO_ISSUER_OID)


def _pem_cert(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def _pem_public(key: object) -> str:
    public = key.public_key() if hasattr(key, "public_key") else key
    return public.public_bytes(  # type: ignore[union-attr]
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _der_b64(cert: x509.Certificate) -> str:
    return encode_b64(cert.public_bytes(serialization.Encoding.DER))


def _issue_ca() -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CodeStrata Test Fulcio")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _issue_leaf(
    ca_key: ec.EllipticCurvePrivateKey,
    ca_cert: x509.Certificate,
    *,
    issuer: str,
    not_after: datetime,
    eku: x509.ObjectIdentifier = ExtendedKeyUsageOID.CODE_SIGNING,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "codestrata-release-bot")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(not_after)
        .add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(IDENTITY)]),
            critical=False,
        )
        .add_extension(
            x509.UnrecognizedExtension(_FULCIO_OID, issuer.encode("utf-8")),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([eku]), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


def _package(
    *,
    artifact_digest: str,
    purpose: ExecutionPurpose,
    validity_not_after: str | None = "2027-09-15T00:00:00Z",
) -> dict[str, Any]:
    effective = example_effective()
    body = SignedPackageBody(
        package_id="codestrata.engineering-standard.pkg",
        package_version="1.0.0",
        effective_ruleset_digest=effective.effective_ruleset_digest,
        payload_digests=(
            PayloadDigest(name="artifact", digest=artifact_digest),
            PayloadDigest(name="effective_ruleset", digest=effective.effective_ruleset_digest),
        ),
        execution_purpose=purpose,
        compatibility=PackageCompatibility(),
        validity_not_after=validity_not_after,
    )
    return seal_package(body).model_dump(mode="json")


def _public_bundle(
    *,
    leaf: x509.Certificate,
    leaf_key: ec.EllipticCurvePrivateKey,
    rekor_key: ec.EllipticCurvePrivateKey,
    artifact: bytes,
    tamper_signature: bool = False,
) -> dict[str, Any]:
    digest = sha256_hex(artifact)
    signature = leaf_key.sign(artifact, ec.ECDSA(hashes.SHA256()))
    if tamper_signature:
        signature = bytes([signature[0] ^ 0xFF]) + signature[1:]
    signature_b64 = encode_b64(signature)
    body = hashedrekord_body(artifact_digest=digest, signature_b64=signature_b64)
    body_bytes = dumps_canonical(body).encode("utf-8")
    set_message = signed_entry_timestamp_message(
        body_bytes=body_bytes,
        log_index="1",
        integrated_time=INTEGRATED_TIME,
    )
    set_sig = rekor_key.sign(set_message, ec.ECDSA(hashes.SHA256()))
    return {
        "mediaType": BUNDLE_MEDIA_TYPE,
        "verificationMaterial": {
            "certificate": {"rawBytes": _der_b64(leaf)},
            "tlogEntries": [
                {
                    "logIndex": "1",
                    "integratedTime": INTEGRATED_TIME,
                    "canonicalizedBody": encode_b64(body_bytes),
                    "inclusionPromise": {
                        "signedEntryTimestamp": encode_b64(set_sig),
                    },
                }
            ],
        },
        "messageSignature": {
            "messageDigest": {
                "algorithm": "SHA2_256",
                "digest": encode_b64(bytes.fromhex(digest)),
            },
            "signature": signature_b64,
        },
    }


def _public_request(
    *,
    bundle: dict[str, Any],
    package: dict[str, Any],
    trust_root_pem: str,
    rekor_public_pem: str,
    purpose: ExecutionPurpose = ExecutionPurpose.PRODUCTION,
    role: str = SignerRole.PUBLIC_DISTRIBUTION.value,
    artifact: bytes = ARTIFACT,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "profile_id": "codestrata.release.sigstore-public.v1",
        "signer_role": role,
        "requested_purpose": purpose.value,
        "package": package,
        "artifact_bytes": encode_b64(artifact),
        "bundle": bundle,
        "evaluation_time": EVALUATION_TIME,
        "trust_root_pem": trust_root_pem,
        "rekor_public_pem": rekor_public_pem,
    }
    if extra:
        payload.update(extra)
    return payload


def _offline_request(
    *,
    package: dict[str, Any],
    private_key: ed25519.Ed25519PrivateKey,
    key_id: str,
    purpose: ExecutionPurpose,
    last_updated: str,
    revoked: tuple[str, ...] = (),
    extra_bundle: dict[str, Any] | None = None,
    tamper: bool = False,
    not_after: str | None = "2027-09-15T00:00:00Z",
) -> dict[str, Any]:
    manifest = seal_package_from_dump(package)
    canonical = dumps_canonical(manifest.body.model_dump(mode="json")).encode("utf-8")
    signature = private_key.sign(canonical)
    if tamper:
        signature = bytes([signature[0] ^ 0xFF]) + signature[1:]
    bundle: dict[str, Any] = {
        "algorithm": "ed25519",
        "key_id": key_id,
        "signature": encode_b64(signature),
    }
    if extra_bundle:
        bundle.update(extra_bundle)
    return {
        "profile_id": "codestrata.release.offline-self-managed-key.v1",
        "signer_role": SignerRole.PRIVATE_RESULT.value,
        "requested_purpose": purpose.value,
        "package": package,
        "artifact_bytes": "",
        "bundle": bundle,
        "evaluation_time": EVALUATION_TIME,
        "key_id": key_id,
        "trust_store": [
            {
                "key_id": key_id,
                "public_key_pem": _pem_public(private_key),
                "purpose": purpose.value,
                "role": SignerRole.PRIVATE_RESULT.value,
                "not_after": not_after,
            }
        ],
        "revocation": {
            "last_updated": last_updated,
            "revoked_key_ids": list(revoked),
            "instant_revocation": False,
        },
    }


def seal_package_from_dump(payload: dict[str, Any]) -> Any:
    from codestrata.domain.contracts.rules import parse_signed_package

    return parse_signed_package(payload)


def build_all() -> dict[str, dict[str, Any]]:
    ca_key, ca_cert = _issue_ca()
    leaf_key, leaf = _issue_leaf(ca_key, ca_cert, issuer=ISSUER, not_after=NOT_AFTER)
    wrong_key, wrong_leaf = _issue_leaf(
        ca_key, ca_cert, issuer=WRONG_ISSUER, not_after=NOT_AFTER
    )
    expired_key, expired_leaf = _issue_leaf(
        ca_key, ca_cert, issuer=ISSUER, not_after=EXPIRED_AFTER
    )
    eku_key, eku_leaf = _issue_leaf(
        ca_key,
        ca_cert,
        issuer=ISSUER,
        not_after=NOT_AFTER,
        eku=ExtendedKeyUsageOID.CLIENT_AUTH,
    )
    rekor_key = ec.generate_private_key(ec.SECP256R1())
    trust_root = _pem_cert(ca_cert)
    rekor_public = _pem_public(rekor_key)
    digest = sha256_hex(ARTIFACT)
    production_pkg = _package(artifact_digest=digest, purpose=ExecutionPurpose.PRODUCTION)
    preview_pkg = _package(artifact_digest=digest, purpose=ExecutionPurpose.PREVIEW)
    expired_pkg = _package(
        artifact_digest=digest,
        purpose=ExecutionPurpose.PRODUCTION,
        validity_not_after="2026-01-15T00:00:00Z",
    )

    valid_bundle = _public_bundle(
        leaf=leaf, leaf_key=leaf_key, rekor_key=rekor_key, artifact=ARTIFACT
    )
    tampered_bundle = _public_bundle(
        leaf=leaf,
        leaf_key=leaf_key,
        rekor_key=rekor_key,
        artifact=ARTIFACT,
        tamper_signature=True,
    )
    wrong_issuer_bundle = _public_bundle(
        leaf=wrong_leaf, leaf_key=wrong_key, rekor_key=rekor_key, artifact=ARTIFACT
    )
    expired_cert_bundle = _public_bundle(
        leaf=expired_leaf, leaf_key=expired_key, rekor_key=rekor_key, artifact=ARTIFACT
    )
    eku_bundle = _public_bundle(
        leaf=eku_leaf, leaf_key=eku_key, rekor_key=rekor_key, artifact=ARTIFACT
    )
    unsupported_bundle = dict(valid_bundle)
    unsupported_bundle["mediaType"] = "application/vnd.dev.sigstore.bundle.v9+json"

    leak_bundle = json.loads(json.dumps(valid_bundle))
    leak_body = {
        "apiVersion": "0.0.1",
        "kind": "hashedrekord",
        "spec": {
            "data": {"hash": {"algorithm": "sha256", "value": digest}},
            "signature": {
                "content": valid_bundle["messageSignature"]["signature"],
                "publicKey": {"format": "x509"},
            },
            "rules": "api_version: codestrata.io/rules\nkind: Rule\n",
        },
    }
    leak_bundle["verificationMaterial"]["tlogEntries"][0]["canonicalizedBody"] = encode_b64(
        dumps_canonical(leak_body).encode("utf-8")
    )

    private_key = ed25519.Ed25519PrivateKey.generate()
    preview_key = ed25519.Ed25519PrivateKey.generate()
    private_pkg = _package(
        artifact_digest=digest, purpose=ExecutionPurpose.PRODUCTION
    )
    preview_private_pkg = _package(
        artifact_digest=digest, purpose=ExecutionPurpose.PREVIEW
    )

    fixtures: dict[str, dict[str, Any]] = {
        "public-valid": _public_request(
            bundle=valid_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "public-tampered": _public_request(
            bundle=tampered_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "public-wrong-issuer": _public_request(
            bundle=wrong_issuer_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "public-wrong-purpose": _public_request(
            bundle=valid_bundle,
            package=preview_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
            purpose=ExecutionPurpose.PRODUCTION,
        ),
        "public-expired": _public_request(
            bundle=expired_cert_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "public-unsupported": _public_request(
            bundle=unsupported_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "public-package-expired": _public_request(
            bundle=valid_bundle,
            package=expired_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "public-wrong-eku": _public_request(
            bundle=eku_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "public-private-contents-in-tlog": _public_request(
            bundle=leak_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "role-mismatch-public-as-private": _public_request(
            bundle=valid_bundle,
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
            role=SignerRole.PRIVATE_RESULT.value,
        ),
        "private-valid": _offline_request(
            package=private_pkg,
            private_key=private_key,
            key_id="result-signer-1",
            purpose=ExecutionPurpose.PRODUCTION,
            last_updated="2026-09-20T00:00:00Z",
        ),
        "private-tampered": _offline_request(
            package=private_pkg,
            private_key=private_key,
            key_id="result-signer-1",
            purpose=ExecutionPurpose.PRODUCTION,
            last_updated="2026-09-20T00:00:00Z",
            tamper=True,
        ),
        "private-wrong-purpose": _offline_request(
            package=preview_private_pkg,
            private_key=preview_key,
            key_id="result-signer-preview",
            purpose=ExecutionPurpose.PREVIEW,
            last_updated="2026-09-20T00:00:00Z",
            extra_bundle=None,
        ),
        "private-expired": _offline_request(
            package=private_pkg,
            private_key=private_key,
            key_id="result-signer-1",
            purpose=ExecutionPurpose.PRODUCTION,
            last_updated="2026-09-20T00:00:00Z",
            not_after="2026-01-15T00:00:00Z",
        ),
        "private-stale-revocation": _offline_request(
            package=private_pkg,
            private_key=private_key,
            key_id="result-signer-1",
            purpose=ExecutionPurpose.PRODUCTION,
            last_updated="2026-01-01T00:00:00Z",
        ),
        "private-revoked-fresh": _offline_request(
            package=private_pkg,
            private_key=private_key,
            key_id="result-signer-1",
            purpose=ExecutionPurpose.PRODUCTION,
            last_updated="2026-09-20T00:00:00Z",
            revoked=("result-signer-1",),
        ),
        "private-contents-in-public-log": _offline_request(
            package=private_pkg,
            private_key=private_key,
            key_id="result-signer-1",
            purpose=ExecutionPurpose.PRODUCTION,
            last_updated="2026-09-20T00:00:00Z",
            extra_bundle={"tlogEntries": [{"canonicalizedBody": "rules"}]},
        ),
        "partial-missing-bundle": _public_request(
            bundle={"mediaType": BUNDLE_MEDIA_TYPE},
            package=production_pkg,
            trust_root_pem=trust_root,
            rekor_public_pem=rekor_public,
        ),
        "corrupt": {
            "profile_id": "codestrata.release.sigstore-public.v1",
            "signer_role": SignerRole.PUBLIC_DISTRIBUTION.value,
            "requested_purpose": ExecutionPurpose.PRODUCTION.value,
            "package": {"not": "a package"},
            "artifact_bytes": encode_b64(ARTIFACT),
            "bundle": valid_bundle,
            "evaluation_time": EVALUATION_TIME,
            "trust_root_pem": trust_root,
            "rekor_public_pem": rekor_public,
        },
    }
    # Preview private package requested as production uses the preview package
    # with production purpose — handled as a dedicated fixture below.
    fixtures["private-wrong-purpose"] = {
        **fixtures["private-valid"],
        "package": preview_private_pkg,
        "requested_purpose": ExecutionPurpose.PRODUCTION.value,
    }
    # Re-sign is not applied; admit_package rejects preview for production
    # before the Ed25519 check.
    return fixtures


EXPECTED = {
    "public-valid": {"status": "verified", "reason": "ok"},
    "public-tampered": {"status": "tampered", "reason": "signature_mismatch"},
    "public-wrong-issuer": {"status": "wrong_issuer", "reason": "oidc_issuer_mismatch"},
    "public-wrong-purpose": {
        "status": "wrong_purpose",
        "reason": "preview_cannot_authorize_production",
    },
    "public-expired": {"status": "expired", "reason": "certificate_expired"},
    "public-unsupported": {
        "status": "unsupported",
        "reason": "unsupported_bundle_media_type",
    },
    "public-package-expired": {"status": "expired", "reason": "package_expired"},
    "public-wrong-eku": {
        "status": "wrong_purpose",
        "reason": "certificate_eku_not_code_signing",
    },
    "public-private-contents-in-tlog": {
        "status": "rejected",
        "reason": "private_contents_in_public_log",
    },
    "role-mismatch-public-as-private": {
        "status": "rejected",
        "reason": "role_profile_mismatch",
    },
    "private-valid": {"status": "verified", "reason": "ok"},
    "private-tampered": {"status": "tampered", "reason": "signature_mismatch"},
    "private-wrong-purpose": {
        "status": "wrong_purpose",
        "reason": "preview_cannot_authorize_production",
    },
    "private-expired": {"status": "expired", "reason": "trust_entry_expired"},
    "private-stale-revocation": {
        "status": "stale",
        "reason": "revocation_inventory_exceeds_freshness_limit",
    },
    "private-revoked-fresh": {
        "status": "revoked",
        "reason": "key_revoked_in_fresh_inventory",
    },
    "private-contents-in-public-log": {
        "status": "rejected",
        "reason": "private_contents_must_not_use_public_tlog",
    },
    "partial-missing-bundle": {
        "status": "unavailable",
        "reason": "bundle_material_missing",
    },
    "corrupt": {"status": "rejected", "reason": "package_contract_rejected"},
}


def write_fixtures(directory: Path | None = None) -> Path:
    target = directory or FIXTURE_DIR
    target.mkdir(parents=True, exist_ok=True)
    fixtures = build_all()
    for name, payload in fixtures.items():
        path = target / f"{name}.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    expected_path = target / "expected-outcomes.json"
    expected_path.write_text(
        json.dumps(EXPECTED, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        "Test-only cryptographic fixtures for E14.1. Keys are not product secrets.\n"
        "Regenerate with tests/application/release/support/build_verification_fixtures.py.\n",
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    written = write_fixtures()
    print(f"wrote {written}")
