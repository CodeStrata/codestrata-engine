"""E01.1–E01.3 published descriptors, identities, envelopes, rules and invocation."""

from __future__ import annotations

from codestrata.domain.contracts.catalog import (
    RATIFICATION_ID,
    RATIFICATION_VERSION,
    load_launch_ratification,
)
from codestrata.domain.contracts.comparison import ComparisonEnvelope, parse_comparison
from codestrata.domain.contracts.descriptors import AnalyzerDescriptor, launch_descriptors
from codestrata.domain.contracts.driver_manifest import (
    OutcomeDriverManifest,
    build_outcome_driver_manifest,
)
from codestrata.domain.contracts.envelope import CanonicalEnvelope, parse_envelope, seal_envelope
from codestrata.domain.contracts.invocation import HeadlessInvocation, parse_invocation
from codestrata.domain.contracts.models import LaunchRatification
from codestrata.domain.contracts.rules import (
    EffectiveRuleSet,
    Rule,
    RuleSet,
    SignedPackageManifest,
    parse_rule,
)

__all__ = [
    "AnalyzerDescriptor",
    "CanonicalEnvelope",
    "ComparisonEnvelope",
    "EffectiveRuleSet",
    "HeadlessInvocation",
    "LaunchRatification",
    "OutcomeDriverManifest",
    "RATIFICATION_ID",
    "RATIFICATION_VERSION",
    "Rule",
    "RuleSet",
    "SignedPackageManifest",
    "build_outcome_driver_manifest",
    "launch_descriptors",
    "load_launch_ratification",
    "parse_comparison",
    "parse_envelope",
    "parse_invocation",
    "parse_rule",
    "seal_envelope",
]
