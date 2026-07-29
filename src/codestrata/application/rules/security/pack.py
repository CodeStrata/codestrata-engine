"""Security Intelligence pack metadata and rule construction (Phase 4.5.3)."""

from __future__ import annotations

from codestrata.application.rules.security.rules import (
    AuthenticationDisabledRule,
    CredentialLiteralRule,
    DebugEnabledRule,
    HostnameVerificationDisabledRule,
    PermissiveCorsOriginRule,
    PlaceholderCredentialRule,
    PrivateKeyMaterialRule,
    TlsVerificationDisabledRule,
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.security.ids import (
    HYGIENE_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_AUTHENTICATION_DISABLED,
    RULE_CREDENTIAL_LITERAL,
    RULE_DEBUG_ENABLED,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_PERMISSIVE_CORS_ORIGIN,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)


class SecurityRulePack:
    """First-class Security Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.SECURITY
    supported_languages: tuple[str, ...] = (
        "java",
        "python",
        "javascript",
        "typescript",
        "php",
        "csharp",
    )
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = (
        "docs/analysis-intelligence/shared-rule-platform.md"
    )
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.security.enabled=true",
        "evidence.repository_sensitive.enabled=true",
    )
    enterprise_context_requirements: tuple[str, ...] = ()
    included_rule_ids: tuple[str, ...] = HYGIENE_RULE_IDS
    deferred_rule_ids: tuple[str, ...] = (
        "security.plaintext-http-endpoint",
        "security.source-code-secret-regex",
        "security.certificate-expiry",
        "security.keystore-inspection",
        "security.dependency-cve",
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "included_rule_ids": list(self.included_rule_ids),
            "deferred_rule_ids": list(self.deferred_rule_ids),
            "supported_languages": list(self.supported_languages),
            "default_enabled": self.default_enabled,
            "requires_enterprise_context": self.requires_enterprise_context,
            "configuration_requirements": list(self.configuration_requirements),
            "enterprise_context_requirements": list(
                self.enterprise_context_requirements
            ),
            "documentation_reference": self.documentation_reference,
        }


def security_rules(
    *,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    candidates: list[tuple[str, SharedRule]] = [
        (RULE_PRIVATE_KEY_MATERIAL, PrivateKeyMaterialRule()),
        (RULE_CREDENTIAL_LITERAL, CredentialLiteralRule()),
        (RULE_PLACEHOLDER_CREDENTIAL, PlaceholderCredentialRule()),
        (RULE_TLS_VERIFICATION_DISABLED, TlsVerificationDisabledRule()),
        (RULE_HOSTNAME_VERIFICATION_DISABLED, HostnameVerificationDisabledRule()),
        (RULE_AUTHENTICATION_DISABLED, AuthenticationDisabledRule()),
        (RULE_PERMISSIVE_CORS_ORIGIN, PermissiveCorsOriginRule()),
        (RULE_DEBUG_ENABLED, DebugEnabledRule()),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
