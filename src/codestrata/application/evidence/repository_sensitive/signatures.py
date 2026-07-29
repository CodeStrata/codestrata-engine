"""Content-signature classification for repository-sensitive evidence."""

from __future__ import annotations

import re

from codestrata.domain.evidence.repository_sensitive.enums import ContentClassification

_PRIVATE_KEY_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
)
_CERTIFICATE_MARKERS = ("-----BEGIN CERTIFICATE-----",)
_OPENSSH_PRIVATE = "-----BEGIN OPENSSH PRIVATE KEY-----"

# Conservative credential-section markers for INI-like credential files.
_CREDENTIAL_SECTION = re.compile(r"(?im)^\s*\[(default|profile\s+[^\]]+|server)\]\s*$")
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?"
    r"[A-Za-z0-9_]*?"
    r"(?:password|passwd|secret|token|api_key|apikey|access_key|client_secret)"
    r"[A-Za-z0-9_]*\s*="
)


def classify_text_signatures(text: str) -> tuple[ContentClassification, ...]:
    """Return content classifications from structural markers only.

    Does not decode keys, validate certificates, or use entropy scoring.
    """

    if not text:
        return (ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,)

    found: list[ContentClassification] = []
    if any(marker in text for marker in _PRIVATE_KEY_MARKERS):
        found.append(ContentClassification.PRIVATE_KEY_MATERIAL)
    if _OPENSSH_PRIVATE in text and ContentClassification.PRIVATE_KEY_MATERIAL not in found:
        found.append(ContentClassification.PRIVATE_KEY_MATERIAL)
    if any(marker in text for marker in _CERTIFICATE_MARKERS):
        found.append(ContentClassification.PUBLIC_CERTIFICATE_MATERIAL)
    if _CREDENTIAL_SECTION.search(text) or _CREDENTIAL_ASSIGNMENT.search(text):
        found.append(ContentClassification.CREDENTIAL_ENTRIES)

    if not found:
        return (ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,)
    return tuple(dict.fromkeys(found))


def has_private_key_signature(text: str) -> bool:
    return ContentClassification.PRIVATE_KEY_MATERIAL in classify_text_signatures(text)


def has_certificate_signature(text: str) -> bool:
    return (
        ContentClassification.PUBLIC_CERTIFICATE_MATERIAL
        in classify_text_signatures(text)
    )
