"""Content-signature classification for repository-sensitive evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from codestrata.domain.evidence.repository_sensitive.enums import ContentClassification

_PEM_PRIVATE = re.compile(
    r"(?m)^-----BEGIN ((?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----\s*$"
)
_PEM_PRIVATE_END = re.compile(
    r"(?m)^-----END ((?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----\s*$"
)
_PEM_PGP_PRIVATE = re.compile(r"(?m)^-----BEGIN PGP PRIVATE KEY BLOCK-----\s*$")
_PEM_PUBLIC = re.compile(r"(?m)^-----BEGIN ((?:RSA |EC |DSA )?PUBLIC KEY)-----\s*$")
_PEM_CERTIFICATE = re.compile(r"(?m)^-----BEGIN CERTIFICATE-----\s*$")
_PUTTY_PRIVATE = re.compile(r"(?m)^PuTTY-User-Key-File-\d+:")
_PLACEHOLDER_PEM_BODIES = frozenset(
    {
        "replace_me",
        "your_key_here",
        "your-key-here",
        "example",
        "placeholder",
        "xxx",
        "xxxx",
        "xxxxx",
        "...",
        "snip",
        "redacted",
        "todo",
        "insert_private_key_here",
    }
)
_DETECTOR_BY_HEADER = {
    "PRIVATE KEY": ("pem.pkcs8", "pkcs8_private_key"),
    "RSA PRIVATE KEY": ("pem.rsa", "rsa_private_key"),
    "EC PRIVATE KEY": ("pem.ec", "ec_private_key"),
    "DSA PRIVATE KEY": ("pem.dsa", "dsa_private_key"),
    "OPENSSH PRIVATE KEY": ("openssh.private", "openssh_private_key"),
    "ENCRYPTED PRIVATE KEY": ("pem.encrypted", "encrypted_private_key"),
}

# Conservative credential-section markers for INI-like credential files.
_CREDENTIAL_SECTION = re.compile(r"(?im)^\s*\[(default|profile\s+[^\]]+|server)\]\s*$")
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?"
    r"[A-Za-z0-9_]*?"
    r"(?:password|passwd|secret|token|api_key|apikey|access_key|client_secret)"
    r"[A-Za-z0-9_]*\s*="
)


@dataclass(frozen=True)
class SignatureHit:
    classification: ContentClassification
    detector_id: str
    safe_secret_type: str
    redacted_span: str
    line_start: int | None = None


def _line_number(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1


def _pem_body_is_placeholder(text: str, begin: int, end: int) -> bool:
    body = text[begin:end]
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return True
    return all(line.lower() in _PLACEHOLDER_PEM_BODIES for line in lines)


def _redacted_pem_span(header: str) -> str:
    return f"-----BEGIN {header}-----\n[REDACTED]\n-----END {header}-----"


def inspect_text_signatures(text: str) -> tuple[SignatureHit, ...]:
    """Return verified signature hits. Does not decode or retain key bodies."""

    if not text:
        return ()
    hits: list[SignatureHit] = []
    for match in _PEM_PRIVATE.finditer(text):
        header = match.group(1)
        end_match = _PEM_PRIVATE_END.search(text, match.end())
        end = end_match.start() if end_match else match.end()
        detector_id, secret_type = _DETECTOR_BY_HEADER.get(header, ("pem.private", "private_key"))
        if _pem_body_is_placeholder(text, match.end(), end):
            hits.append(
                SignatureHit(
                    classification=ContentClassification.PLACEHOLDER_ONLY,
                    detector_id=f"{detector_id}.placeholder",
                    safe_secret_type="placeholder_private_key",
                    redacted_span=_redacted_pem_span(header),
                    line_start=_line_number(text, match.start()),
                )
            )
            continue
        hits.append(
            SignatureHit(
                classification=ContentClassification.PRIVATE_KEY_MATERIAL,
                detector_id=detector_id,
                safe_secret_type=secret_type,
                redacted_span=_redacted_pem_span(header),
                line_start=_line_number(text, match.start()),
            )
        )
    pgp_match = _PEM_PGP_PRIVATE.search(text)
    if pgp_match is not None:
        hits.append(
            SignatureHit(
                classification=ContentClassification.PRIVATE_KEY_MATERIAL,
                detector_id="pgp.private",
                safe_secret_type="pgp_private_key",
                redacted_span=(
                    "-----BEGIN PGP PRIVATE KEY BLOCK-----\n[REDACTED]\n"
                    "-----END PGP PRIVATE KEY BLOCK-----"
                ),
                line_start=_line_number(text, pgp_match.start()),
            )
        )
    putty_match = _PUTTY_PRIVATE.search(text)
    if putty_match is not None:
        hits.append(
            SignatureHit(
                classification=ContentClassification.PRIVATE_KEY_MATERIAL,
                detector_id="putty.ppk",
                safe_secret_type="putty_private_key",
                redacted_span="PuTTY-User-Key-File-[REDACTED]",
                line_start=_line_number(text, putty_match.start()),
            )
        )
    cert_match = _PEM_CERTIFICATE.search(text)
    if cert_match is not None:
        hits.append(
            SignatureHit(
                classification=ContentClassification.PUBLIC_CERTIFICATE_MATERIAL,
                detector_id="pem.certificate",
                safe_secret_type="x509_certificate",
                redacted_span="-----BEGIN CERTIFICATE-----\n[REDACTED]\n-----END CERTIFICATE-----",
                line_start=_line_number(text, cert_match.start()),
            )
        )
    public_match = _PEM_PUBLIC.search(text)
    if public_match is not None and ContentClassification.PRIVATE_KEY_MATERIAL not in {
        item.classification for item in hits
    }:
        hits.append(
            SignatureHit(
                classification=ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,
                detector_id="pem.public",
                safe_secret_type="public_key_lookalike",
                redacted_span="-----BEGIN PUBLIC KEY-----\n[REDACTED]\n-----END PUBLIC KEY-----",
                line_start=_line_number(text, public_match.start()),
            )
        )
    if _CREDENTIAL_SECTION.search(text) or _CREDENTIAL_ASSIGNMENT.search(text):
        hits.append(
            SignatureHit(
                classification=ContentClassification.CREDENTIAL_ENTRIES,
                detector_id="config.credential_assignment",
                safe_secret_type="credential_entry",
                redacted_span="[REDACTED]",
            )
        )
    if not hits:
        return ()
    return tuple(hits)


def classify_text_signatures(text: str) -> tuple[ContentClassification, ...]:
    """Return content classifications from structural markers only.

    Does not decode keys, validate certificates, or use entropy scoring.
    Encoded (base64-only) private-key lookalikes are not decoded.
    """

    if not text:
        return (ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,)
    hits = inspect_text_signatures(text)
    found = tuple(
        dict.fromkeys(
            item.classification
            for item in hits
            if item.classification is not ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE
        )
    )
    if not found:
        return (ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,)
    return found


def primary_private_key_hit(text: str) -> SignatureHit | None:
    for item in inspect_text_signatures(text):
        if item.classification is ContentClassification.PRIVATE_KEY_MATERIAL:
            return item
    return None


def looks_like_undecoded_base64(text: str) -> bool:
    compact = "".join(text.split())
    if len(compact) < 80 or "BEGIN " in text:
        return False
    alphabet = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    return all(char in alphabet for char in compact)


def has_private_key_signature(text: str) -> bool:
    return ContentClassification.PRIVATE_KEY_MATERIAL in classify_text_signatures(text)


def has_certificate_signature(text: str) -> bool:
    return ContentClassification.PUBLIC_CERTIFICATE_MATERIAL in classify_text_signatures(text)
