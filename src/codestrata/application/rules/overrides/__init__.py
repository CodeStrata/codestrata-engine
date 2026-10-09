"""E04.2 typed policy overrides and resolved scoped exceptions."""

from __future__ import annotations

from codestrata.application.rules.overrides.apply import apply_overrides
from codestrata.application.rules.overrides.errors import OverrideError
from codestrata.application.rules.overrides.models import (
    OverriddenRuleSet,
    PolicyOverrideBundle,
    ScopedException,
    TypedOverride,
)
from codestrata.application.rules.overrides.parse import load_override_bundle, parse_override_bundle

__all__ = [
    "OverrideError",
    "OverriddenRuleSet",
    "PolicyOverrideBundle",
    "ScopedException",
    "TypedOverride",
    "apply_overrides",
    "load_override_bundle",
    "parse_override_bundle",
]
