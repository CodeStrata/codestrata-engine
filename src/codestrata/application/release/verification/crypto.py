"""Real cryptographic primitives for E14.1 verification.

Uses the ``cryptography`` library (ECDSA P-256 and Ed25519, X.509). This is
not a mocked signature boolean. Private keys must never appear in results.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID, ObjectIdentifier

from codestrata.application.release.verification.policy import FULCIO_ISSUER_OID

_PRIVATE_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN ENCRYPTED PRIVATE KEY",
)


class CryptoError(ValueError):
    """Malformed cryptographic material. Messages never include key bytes."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_b64(value: str, *, label: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise CryptoError(f"{label} is not valid base64") from error


def encode_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def parse_iso8601(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise CryptoError("invalid timestamp") from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def contains_private_key_marker(payload: object) -> bool:
    blob = str(payload)
    return any(marker in blob for marker in _PRIVATE_MARKERS)


def load_certificate_from_b64(raw_b64: str) -> x509.Certificate:
    der = decode_b64(raw_b64, label="certificate")
    try:
        return x509.load_der_x509_certificate(der)
    except ValueError as error:
        raise CryptoError("certificate is not a valid DER X.509 document") from error


def load_certificate_from_pem(pem: str) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(pem.encode("utf-8"))
    except ValueError as error:
        raise CryptoError("certificate is not a valid PEM X.509 document") from error


def load_public_key_from_pem(pem: str) -> object:
    try:
        return serialization.load_pem_public_key(pem.encode("utf-8"))
    except ValueError as error:
        raise CryptoError("public key PEM is invalid") from error


def certificate_identity(cert: x509.Certificate) -> str:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound as error:
        raise CryptoError("certificate is missing SAN identity") from error
    uris = san.value.get_values_for_type(x509.UniformResourceIdentifier)
    if uris:
        return str(uris[0])
    emails = san.value.get_values_for_type(x509.RFC822Name)
    if emails:
        return str(emails[0])
    raise CryptoError("certificate SAN has no URI or email identity")


def certificate_oidc_issuer(cert: x509.Certificate) -> str:
    oid = ObjectIdentifier(FULCIO_ISSUER_OID)
    try:
        extension = cert.extensions.get_extension_for_oid(oid)
    except x509.ExtensionNotFound as error:
        raise CryptoError("certificate is missing OIDC issuer extension") from error
    raw = extension.value
    if isinstance(raw, x509.UnrecognizedExtension):
        return raw.value.decode("utf-8")
    raise CryptoError("certificate OIDC issuer extension is unsupported")


def certificate_is_code_signing(cert: x509.Certificate) -> bool:
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
    except x509.ExtensionNotFound:
        return False
    return ExtendedKeyUsageOID.CODE_SIGNING in eku.value


def certificate_valid_at(cert: x509.Certificate, when: datetime) -> bool:
    # cryptography 42+ uses aware UTC properties.
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    return not_before <= when <= not_after


def verify_leaf_against_root(leaf: x509.Certificate, root: x509.Certificate) -> bool:
    public = root.public_key()
    if not isinstance(public, EllipticCurvePublicKey):
        return False
    try:
        public.verify(
            leaf.signature,
            leaf.tbs_certificate_bytes,
            ec.ECDSA(leaf.signature_hash_algorithm or hashes.SHA256()),
        )
    except (InvalidSignature, TypeError, ValueError):
        return False
    return True


def verify_ecdsa_p256_sha256(public_key: object, signature: bytes, message: bytes) -> bool:
    if not isinstance(public_key, EllipticCurvePublicKey):
        return False
    try:
        public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError):
        return False
    return True


def verify_ed25519(public_key: object, signature: bytes, message: bytes) -> bool:
    if not isinstance(public_key, ed25519.Ed25519PublicKey):
        return False
    try:
        public_key.verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def load_private_key_from_pem(pem: str) -> object:
    try:
        return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except ValueError as error:
        raise CryptoError("private key PEM is invalid") from error


def sign_ed25519(private_key_pem: str, message: bytes) -> bytes:
    """Sign message with Ed25519. Private key bytes must not be logged."""

    key = load_private_key_from_pem(private_key_pem)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise CryptoError("signer key is not Ed25519")
    return key.sign(message)


def identity_matches(actual: str, expected: str) -> bool:
    if expected.endswith("*"):
        return actual.startswith(expected[:-1])
    return actual == expected


__all__ = [
    "CryptoError",
    "certificate_identity",
    "certificate_is_code_signing",
    "certificate_oidc_issuer",
    "certificate_valid_at",
    "contains_private_key_marker",
    "decode_b64",
    "encode_b64",
    "identity_matches",
    "load_certificate_from_b64",
    "load_certificate_from_pem",
    "load_public_key_from_pem",
    "parse_iso8601",
    "sha256_hex",
    "sign_ed25519",
    "verify_ecdsa_p256_sha256",
    "verify_ed25519",
    "verify_leaf_against_root",
]
