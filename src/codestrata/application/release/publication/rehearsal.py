"""Offline public Sigstore rehearsal for candidate artifacts (E14.4).

Uses the same test Fulcio/Rekor material as E14.1 fixtures. This is a local
rehearsal only; it does not obtain live GitHub OIDC or publish anywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID, ObjectIdentifier

from codestrata.application.release.verification.crypto import encode_b64, sha256_hex
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

DEFAULT_EVALUATION_TIME = "2026-09-21T00:00:00Z"
DEFAULT_INTEGRATED_TIME = "2026-09-21T00:00:00Z"
REHEARSAL_IDENTITY = (
    "https://github.com/CodeStrata/codestrata-engine/.github/workflows/"
    "release.yml@refs/tags/v0.2.1"
)
REHEARSAL_ISSUER = "https://token.actions.githubusercontent.com"
_NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
_NOT_AFTER = datetime(2027, 9, 15, tzinfo=UTC)
_FULCIO_OID = ObjectIdentifier(FULCIO_ISSUER_OID)


def build_rehearsal_verify_payload(
    artifact: bytes,
    *,
    evaluation_time: str = DEFAULT_EVALUATION_TIME,
) -> dict[str, Any]:
    """Return a ``verify_payload`` request for the supplied artifact bytes."""

    ca_key, ca_cert = _issue_ca()
    leaf_key, leaf = _issue_leaf(ca_key, ca_cert, issuer=REHEARSAL_ISSUER, not_after=_NOT_AFTER)
    rekor_key = ec.generate_private_key(ec.SECP256R1())
    trust_root = _pem_cert(ca_cert)
    rekor_public = _pem_public(rekor_key)
    digest = sha256_hex(artifact)
    package = _package(artifact_digest=digest, purpose=ExecutionPurpose.PRODUCTION)
    bundle = _public_bundle(
        leaf=leaf,
        leaf_key=leaf_key,
        rekor_key=rekor_key,
        artifact=artifact,
        integrated_time=DEFAULT_INTEGRATED_TIME,
    )
    return {
        "profile_id": "codestrata.release.sigstore-public.v1",
        "signer_role": "public_distribution",
        "requested_purpose": ExecutionPurpose.PRODUCTION.value,
        "package": package,
        "artifact_bytes": encode_b64(artifact),
        "bundle": bundle,
        "evaluation_time": evaluation_time,
        "trust_root_pem": trust_root,
        "rekor_public_pem": rekor_public,
    }


def _pem_cert(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def _pem_public(key: ec.EllipticCurvePrivateKey | ec.EllipticCurvePublicKey) -> str:
    if isinstance(key, ec.EllipticCurvePrivateKey):
        public = key.public_key()
    else:
        public = key
    return public.public_bytes(
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
        .not_valid_before(_NOT_BEFORE)
        .not_valid_after(_NOT_AFTER)
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
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "codestrata-release-bot")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOT_BEFORE)
        .not_valid_after(not_after)
        .add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(REHEARSAL_IDENTITY)]),
            critical=False,
        )
        .add_extension(
            x509.UnrecognizedExtension(_FULCIO_OID, issuer.encode("utf-8")),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CODE_SIGNING]), critical=False)
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


def _package(*, artifact_digest: str, purpose: ExecutionPurpose) -> dict[str, Any]:
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
        validity_not_after="2027-09-15T00:00:00Z",
    )
    return seal_package(body).model_dump(mode="json")


def _public_bundle(
    *,
    leaf: x509.Certificate,
    leaf_key: ec.EllipticCurvePrivateKey,
    rekor_key: ec.EllipticCurvePrivateKey,
    artifact: bytes,
    integrated_time: str,
) -> dict[str, Any]:
    digest = sha256_hex(artifact)
    signature = leaf_key.sign(artifact, ec.ECDSA(hashes.SHA256()))
    signature_b64 = encode_b64(signature)
    body = hashedrekord_body(artifact_digest=digest, signature_b64=signature_b64)
    body_bytes = dumps_canonical(body).encode("utf-8")
    set_message = signed_entry_timestamp_message(
        body_bytes=body_bytes,
        log_index="1",
        integrated_time=integrated_time,
    )
    set_sig = rekor_key.sign(set_message, ec.ECDSA(hashes.SHA256()))
    return {
        "mediaType": BUNDLE_MEDIA_TYPE,
        "verificationMaterial": {
            "certificate": {"rawBytes": _der_b64(leaf)},
            "tlogEntries": [
                {
                    "logIndex": "1",
                    "integratedTime": integrated_time,
                    "canonicalizedBody": encode_b64(body_bytes),
                    "inclusionPromise": {"signedEntryTimestamp": encode_b64(set_sig)},
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
