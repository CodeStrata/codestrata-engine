"""Prebuilt Community packages and neutral customer-package helpers (E04.3)."""

from __future__ import annotations

from codestrata.application.rules.composition.bundled import bundled_community_catalog
from codestrata.application.rules.composition.catalog import RuleCatalog
from codestrata.application.rules.composition.resolver import resolve_ruleset
from codestrata.application.rules.effective.errors import EffectiveSealError
from codestrata.application.rules.effective.models import LocalUnsignedConfig
from codestrata.application.rules.effective.seal import seal_effective_ruleset
from codestrata.application.rules.overrides.apply import apply_overrides
from codestrata.application.rules.overrides.models import PolicyOverrideBundle
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.rules import EffectiveRuleSet
from codestrata.domain.contracts.serialization import digest_canonical

BUNDLED_INPUT = digest_canonical(
    {"kind": "prebuilt-community", "ruleset_id": "codestrata.engineering-standard"}
)
CUSTOMER_INPUT = digest_canonical(
    {"kind": "neutral-customer-package", "ruleset_id": "customer.engineering-pack"}
)
PRODUCTION_VALIDITY = "2027-09-15T00:00:00Z"


def _validity_for(purpose: ExecutionPurpose, requested: str | None) -> str | None:
    if purpose is not ExecutionPurpose.PRODUCTION:
        return None
    return requested


def seal_bundled_community(
    *,
    purpose: ExecutionPurpose = ExecutionPurpose.PRODUCTION,
    overlay: PolicyOverrideBundle | None = None,
    local_config: LocalUnsignedConfig | None = None,
    validity_not_after: str | None = PRODUCTION_VALIDITY,
) -> tuple[EffectiveRuleSet, RuleCatalog]:
    """Seal the in-memory Community engineering catalog. No customer-authoring CLI."""

    catalog = bundled_community_catalog()
    root = next(
        item for item in catalog.rulesets() if item.metadata.id == "codestrata.engineering-standard"
    )
    composed = resolve_ruleset(root, catalog)
    overridden = apply_overrides(composed, catalog, overlay)
    effective = seal_effective_ruleset(
        composed=composed,
        overridden=overridden,
        catalog=catalog,
        purpose=purpose,
        input_digest=BUNDLED_INPUT,
        package_digest=BUNDLED_INPUT,
        local_config=local_config,
        validity_not_after=_validity_for(purpose, validity_not_after),
    )
    return effective, catalog


def seal_neutral_customer_package(
    catalog: RuleCatalog,
    overlay: PolicyOverrideBundle | None = None,
    *,
    ruleset_id: str | None = None,
    purpose: ExecutionPurpose = ExecutionPurpose.PRODUCTION,
    local_config: LocalUnsignedConfig | None = None,
    validity_not_after: str | None = PRODUCTION_VALIDITY,
) -> EffectiveRuleSet:
    """Seal a locally supplied catalog as a customer package fixture. Not Community authoring."""

    rulesets = catalog.rulesets()
    if ruleset_id is not None:
        matching = tuple(item for item in rulesets if item.metadata.id == ruleset_id)
        if len(matching) != 1:
            raise EffectiveSealError(
                "missing_reference",
                f"customer catalog has no unique RuleSet {ruleset_id}",
            )
        root = matching[0]
    elif len(rulesets) == 1:
        root = rulesets[0]
    else:
        raise EffectiveSealError(
            "missing_reference",
            "neutral customer package requires an explicit ruleset_id",
        )
    composed = resolve_ruleset(root, catalog)
    overridden = apply_overrides(composed, catalog, overlay)
    return seal_effective_ruleset(
        composed=composed,
        overridden=overridden,
        catalog=catalog,
        purpose=purpose,
        input_digest=CUSTOMER_INPUT,
        package_digest=CUSTOMER_INPUT,
        local_config=local_config,
        validity_not_after=_validity_for(purpose, validity_not_after),
    )
