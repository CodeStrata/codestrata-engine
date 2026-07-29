"""Register Security Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.security.pack import SecurityRulePack, security_rules
from codestrata.config.settings import RulesSettings, SecurityRulesSettings
from codestrata.domain.security.ids import HYGIENE_RULE_IDS


def register_security_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | SecurityRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> SecurityRulePack:
    """Register security.core hygiene rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = SecurityRulePack()
    security = _security_settings(settings)
    enabled_ids = _enabled_rule_ids(security) if for_execution else None
    rules = security_rules(enabled_rule_ids=enabled_ids)
    registry.register_collection(rules, production=production)
    return pack


def _security_settings(
    settings: RulesSettings | SecurityRulesSettings | None,
) -> SecurityRulesSettings:
    if settings is None:
        return SecurityRulesSettings()
    if isinstance(settings, SecurityRulesSettings):
        return settings
    return settings.security


def _enabled_rule_ids(security: SecurityRulesSettings) -> frozenset[str]:
    mapping = {
        "security.private-key-material": security.private_key_material.enabled,
        "security.credential-literal": security.credential_literal.enabled,
        "security.placeholder-credential": security.placeholder_credential.enabled,
        "security.tls-verification-disabled": security.tls_verification_disabled.enabled,
        "security.hostname-verification-disabled": (
            security.hostname_verification_disabled.enabled
        ),
        "security.authentication-disabled": security.authentication_disabled.enabled,
        "security.permissive-cors-origin": security.permissive_cors_origin.enabled,
        "security.debug-enabled": security.debug_enabled.enabled,
    }
    # Preserve catalog order for deterministic registration.
    return frozenset(
        rule_id
        for rule_id in HYGIENE_RULE_IDS
        if mapping.get(rule_id, True)
    )
