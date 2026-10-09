"""Seal a canonical Effective RuleSet digest from composed + overridden bytes."""

from __future__ import annotations

from codestrata.application.rules.composition.catalog import RuleCatalog
from codestrata.application.rules.composition.models import ComposedRuleSet
from codestrata.application.rules.effective.errors import EffectiveSealError
from codestrata.application.rules.effective.models import ENGINE_VERSION, LocalUnsignedConfig
from codestrata.application.rules.effective.timestamps import not_after_exceeds
from codestrata.application.rules.overrides.models import AppliedRule, OverriddenRuleSet
from codestrata.application.rules.overrides.parameters import merge_and_validate_parameters
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.rules import (
    CAPABILITY_VERSION,
    DSL_VERSION,
    RESOLVER_VERSION,
    EffectiveRuleSet,
    ResolvedRule,
)
from codestrata.domain.contracts.serialization import (
    bind_content_digest,
    digest_canonical,
    dumps_canonical,
)


def seal_effective_ruleset(
    *,
    composed: ComposedRuleSet,
    overridden: OverriddenRuleSet,
    catalog: RuleCatalog,
    purpose: ExecutionPurpose,
    input_digest: str,
    local_config: LocalUnsignedConfig | None = None,
    package_digest: str | None = None,
    feed_digest: str | None = None,
    validity_not_before: str | None = None,
    validity_not_after: str | None = None,
) -> EffectiveRuleSet:
    """Bind resolver/DSL/capability versions, defaults, scoped settings and attribution."""

    if composed.composition_digest != overridden.composition_digest:
        raise EffectiveSealError(
            "identity_mismatch",
            "overridden composition_digest does not match the composed RuleSet",
        )
    if (
        composed.ruleset_id != overridden.ruleset_id
        or composed.ruleset_version != overridden.ruleset_version
    ):
        raise EffectiveSealError(
            "identity_mismatch",
            "overridden RuleSet identity does not match composition",
        )
    unsigned = local_config or LocalUnsignedConfig()
    exception_limits = _exception_validities(overridden)
    earliest = min(exception_limits) if exception_limits else None
    if validity_not_after is not None and earliest is not None:
        if not_after_exceeds(validity_not_after, earliest):
            raise EffectiveSealError(
                "expiry_exceeds_exception_validity",
                "package/candidate expiry cannot exceed included exception validity",
            )
    if purpose is ExecutionPurpose.PRODUCTION and validity_not_after is None:
        raise EffectiveSealError(
            "missing_validity",
            "production effective ruleset needs validity_not_after",
        )

    signed_rules: list[ResolvedRule] = []
    effective_rules: list[ResolvedRule] = []
    for applied in overridden.rules:
        signed = applied.resolved
        signed_rules.append(signed)
        effective_rules.append(_apply_local_parameters(applied, catalog, unsigned))

    signed_base_digest = digest_canonical(
        {
            "attribution": [
                {
                    "exception_refs": list(item.resolved.exception_refs),
                    "policy_refs": list(item.resolved.policy_refs),
                    "rule_id": item.resolved.rule_id,
                    "scoped_exceptions": [
                        exception.model_dump(mode="json") for exception in item.scoped_exceptions
                    ],
                }
                for item in overridden.rules
            ],
            "capability_version": CAPABILITY_VERSION,
            "composition_digest": composed.composition_digest,
            "defaults": [
                {
                    "default_enabled": item.resolved.default_enabled,
                    "default_severity": item.resolved.default_severity.value,
                    "rule_id": item.resolved.rule_id,
                }
                for item in overridden.rules
            ],
            "dsl_version": DSL_VERSION,
            "ordered_composition": [
                parent.model_dump(mode="json") for parent in composed.ordered_composition
            ],
            "overlay_digest": overridden.overlay_digest,
            "resolver_version": RESOLVER_VERSION,
            "rules": [rule.model_dump(mode="json") for rule in signed_rules],
            "scoped_settings": [
                {
                    "enabled": item.resolved.enabled,
                    "parameters": item.resolved.parameters,
                    "rule_id": item.resolved.rule_id,
                    "severity": item.resolved.effective_severity.value,
                }
                for item in overridden.rules
            ],
        }
    )
    local_unsigned_config_digest = digest_canonical(unsigned.model_dump(mode="json"))
    config_digest = digest_canonical(
        {
            "local_unsigned_config_digest": local_unsigned_config_digest,
            "signed_base_digest": signed_base_digest,
        }
    )
    return bind_content_digest(
        EffectiveRuleSet,
        {
            "capability_version": CAPABILITY_VERSION,
            "config_digest": config_digest,
            "dsl_version": DSL_VERSION,
            "execution_purpose": purpose,
            "feed_digest": feed_digest,
            "input_digest": input_digest,
            "local_unsigned_config_digest": local_unsigned_config_digest,
            "ordered_composition": composed.ordered_composition,
            "package_digest": package_digest,
            "preview_cannot_authorize_production": True,
            "resolver_version": RESOLVER_VERSION,
            "rules": tuple(effective_rules),
            "ruleset_id": composed.ruleset_id,
            "ruleset_version": composed.ruleset_version,
            "signed_base_digest": signed_base_digest,
            "validity_not_after": validity_not_after,
            "validity_not_before": validity_not_before,
        },
        key="effective_ruleset_digest",
    )


def signed_identity_bytes(effective: EffectiveRuleSet) -> str:
    """Canonical identity excluding purpose, validity and the effective digest itself."""

    payload = effective.model_dump(mode="json")
    for key in (
        "effective_ruleset_digest",
        "execution_purpose",
        "validity_not_after",
        "validity_not_before",
    ):
        payload.pop(key, None)
    return dumps_canonical(payload)


def compare_reviewed_and_production(
    reviewed: EffectiveRuleSet,
    production: EffectiveRuleSet,
) -> None:
    """Reviewed candidate and production share signed identity; purpose stays distinct."""

    if production.execution_purpose is not ExecutionPurpose.PRODUCTION:
        raise EffectiveSealError(
            "identity_mismatch",
            "production comparison requires a production Effective RuleSet",
        )
    if reviewed.execution_purpose is ExecutionPurpose.PRODUCTION:
        raise EffectiveSealError(
            "preview_cannot_authorize_production",
            "reviewed candidate cannot carry production purpose",
        )
    if reviewed.signed_base_digest != production.signed_base_digest:
        raise EffectiveSealError(
            "identity_mismatch",
            "reviewed candidate signed base does not match resolved production bytes",
        )
    if reviewed.local_unsigned_config_digest != production.local_unsigned_config_digest:
        raise EffectiveSealError(
            "parameter_change",
            "local unsigned config differs between reviewed candidate and production",
        )


def engine_digest() -> str:
    return digest_canonical({"engine": ENGINE_VERSION})


def dsl_digest() -> str:
    return digest_canonical({"dsl": DSL_VERSION, "capability": CAPABILITY_VERSION})


def _apply_local_parameters(
    applied: AppliedRule,
    catalog: RuleCatalog,
    unsigned: LocalUnsignedConfig,
) -> ResolvedRule:
    overlay = unsigned.parameters_by_rule.get(applied.resolved.rule_id)
    if not overlay:
        return applied.resolved
    rule = catalog.get_rule(
        applied.resolved.rule_id,
        applied.resolved.revision,
        applied.resolved.rule_digest,
    )
    merged = merge_and_validate_parameters(rule, dict(applied.resolved.parameters), overlay)
    return applied.resolved.model_copy(update={"parameters": merged})


def _exception_validities(overridden: OverriddenRuleSet) -> tuple[str, ...]:
    return tuple(
        item.valid_not_after
        for applied in overridden.rules
        for item in applied.scoped_exceptions
        if item.valid_not_after is not None
    )
