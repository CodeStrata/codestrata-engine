"""In-memory Community catalog used by release-time pre-resolution."""

from __future__ import annotations

from codestrata.application.rules.composition.catalog import RuleCatalog
from codestrata.domain.contracts.enums import AdoptionLabel
from codestrata.domain.contracts.examples_e01_3 import example_rule
from codestrata.domain.contracts.rules import (
    ParentRef,
    RuleSet,
    RuleSetEntry,
    RuleSetMetadata,
    SelectorDef,
    bind_digest,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.findings.enums import FindingSeverity


def bundled_community_catalog() -> RuleCatalog:
    """Pinned parent + child used to pre-resolve the Community engineering catalog."""

    rule = example_rule()
    selector = SelectorDef(
        id="codestrata.production_modules",
        source="repository_graph",
        nodes={"all": [{"type": "module"}, {"generated": False}]},
        digest=digest_canonical(
            {
                "source": "repository_graph",
                "nodes": {"all": [{"type": "module"}, {"generated": False}]},
            }
        ),
    )
    parent = bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id="codestrata.engineering-health",
                version="1.0.0",
                title="Engineering health",
                owner="codestrata",
            ),
            "extends": (),
            "selectors": (selector,),
            "rules": (
                RuleSetEntry(
                    rule_id=rule.metadata.id,
                    revision=rule.metadata.version,
                    digest=rule.digest,
                    default_enabled=True,
                    adoption=AdoptionLabel.RECOMMENDED,
                    parameters={"max_cycle_length": 8},
                    severity_override=FindingSeverity.HIGH,
                ),
            ),
        },
    )
    child = bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id="codestrata.engineering-standard",
                version="1.0.0",
                title="Engineering standard",
                owner="codestrata",
            ),
            "extends": (
                ParentRef(
                    id=parent.metadata.id,
                    version=parent.metadata.version,
                    digest=parent.digest,
                ),
            ),
            "selectors": (selector,),
            "rules": (
                RuleSetEntry(
                    rule_id=rule.metadata.id,
                    revision=rule.metadata.version,
                    digest=rule.digest,
                    default_enabled=True,
                    adoption=AdoptionLabel.RECOMMENDED,
                    parameters={"max_cycle_length": 4},
                ),
            ),
        },
    )
    return RuleCatalog((parent, child), (rule,))
