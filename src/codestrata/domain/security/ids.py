"""Security Intelligence pack identifiers (Phase 4.5.3).

``security.core`` hygiene rules consume repository-sensitive evidence only.
"""

from __future__ import annotations

PACK_ID = "security.core"
PACK_VERSION = "1.0.0"
PACK_TITLE = "Security Intelligence Core"
PACK_DESCRIPTION = (
    "Security Intelligence SharedRule pack for repository-local security "
    "hygiene. Rules consume AggregatedRepositorySensitiveEvidence only and "
    "never re-read repository files or reparse configuration."
)

RULE_ID_PREFIX = "security."
RULE_VERSION = "1.0.0"

TAXONOMY_NAMESPACE = "security"

RULE_PRIVATE_KEY_MATERIAL = "security.private-key-material"
RULE_CREDENTIAL_LITERAL = "security.credential-literal"
RULE_PLACEHOLDER_CREDENTIAL = "security.placeholder-credential"
RULE_TLS_VERIFICATION_DISABLED = "security.tls-verification-disabled"
RULE_HOSTNAME_VERIFICATION_DISABLED = "security.hostname-verification-disabled"
RULE_AUTHENTICATION_DISABLED = "security.authentication-disabled"
RULE_PERMISSIVE_CORS_ORIGIN = "security.permissive-cors-origin"
RULE_DEBUG_ENABLED = "security.debug-enabled"

HYGIENE_RULE_IDS: tuple[str, ...] = (
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_CREDENTIAL_LITERAL,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_TLS_VERIFICATION_DISABLED,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_AUTHENTICATION_DISABLED,
    RULE_PERMISSIVE_CORS_ORIGIN,
    RULE_DEBUG_ENABLED,
)
