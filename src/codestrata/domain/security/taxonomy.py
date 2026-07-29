"""Security capability taxonomy (Phase 4.5.1).

Repository-observable Security categories for future rules and assessment
metadata. These values are methodology identifiers only.

This phase does not map categories to OWASP, CWE, CVE, NIST, PCI, SOC 2, or
other compliance frameworks, and does not implement any security rules.
"""

from __future__ import annotations

from enum import StrEnum


class SecurityCategory(StrEnum):
    """Bounded Security Intelligence categories.

    Serialized values use the ``security.<category>`` namespace.
    """

    CREDENTIAL = "security.credential"
    SECRET = "security.secret"
    PRIVATE_KEY = "security.private_key"
    CERTIFICATE = "security.certificate"
    CONFIGURATION = "security.configuration"
    TRANSPORT_SECURITY = "security.transport_security"
    AUTHENTICATION = "security.authentication"
    AUTHORIZATION = "security.authorization"
    CRYPTOGRAPHY = "security.cryptography"
    REPOSITORY_EXPOSURE = "security.repository_exposure"
    DEPENDENCY_SECURITY = "security.dependency_security"
    LOGGING = "security.logging"
    SESSION = "security.session"
    INPUT_VALIDATION = "security.input_validation"
    MISCELLANEOUS = "security.miscellaneous"
    UNKNOWN = "security.unknown"


SECURITY_CATEGORIES: tuple[SecurityCategory, ...] = tuple(SecurityCategory)


def coerce_security_category(value: object) -> SecurityCategory:
    """Map a raw taxonomy value to a category, defaulting unknown inputs safely."""

    if isinstance(value, SecurityCategory):
        return value
    text = str(value or "").strip()
    if not text:
        return SecurityCategory.UNKNOWN
    try:
        return SecurityCategory(text)
    except ValueError:
        pass
    bare = text if text.startswith("security.") else f"security.{text}"
    try:
        return SecurityCategory(bare)
    except ValueError:
        return SecurityCategory.UNKNOWN
