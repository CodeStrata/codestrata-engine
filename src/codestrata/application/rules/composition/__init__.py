"""E04.1 pinned RuleSet composition."""

from __future__ import annotations

from codestrata.application.rules.composition.catalog import (
    RuleCatalog,
    catalog_from_directory,
    catalog_from_mapping,
)
from codestrata.application.rules.composition.errors import ResolutionError
from codestrata.application.rules.composition.models import ComposedRuleSet
from codestrata.application.rules.composition.resolver import resolve_ruleset, resolve_ruleset_ref

__all__ = [
    "ComposedRuleSet",
    "ResolutionError",
    "RuleCatalog",
    "catalog_from_directory",
    "catalog_from_mapping",
    "resolve_ruleset",
    "resolve_ruleset_ref",
]
