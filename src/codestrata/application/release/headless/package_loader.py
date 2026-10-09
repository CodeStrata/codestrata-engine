"""Load and pin-check prepared customer Effective RuleSets (E14.3)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.release.headless.models import HeadlessRunError
from codestrata.domain.contracts.invocation import HeadlessInvocation, PinnedInputs
from codestrata.domain.contracts.rules import EffectiveRuleSet, parse_effective_ruleset


def load_prepared_effective(package_dir: Path) -> EffectiveRuleSet:
    """Load ``EffectiveRuleSet.json`` from a prepared customer package directory."""

    path = package_dir / "EffectiveRuleSet.json"
    if not path.is_file():
        raise HeadlessRunError(f"missing prepared Effective RuleSet at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_effective_ruleset(payload)


def validate_pinned_inputs(effective: EffectiveRuleSet, pinned: PinnedInputs) -> None:
    """Reject packages whose digests diverge from the invocation envelope."""

    checks = (
        ("input_digest", effective.input_digest, pinned.input_digest),
        ("package_digest", effective.package_digest, pinned.package_digest),
        ("config_digest", effective.config_digest, pinned.config_digest),
        ("ruleset_digest", effective.effective_ruleset_digest, pinned.ruleset_digest),
    )
    for label, actual, expected in checks:
        if actual != expected:
            raise HeadlessRunError(
                f"pinned {label} mismatch: package {actual} != invocation {expected}",
            )


def assert_invocation_offline(invocation: HeadlessInvocation) -> None:
    if invocation.hosted_calls or invocation.network_mode != "offline":
        raise HeadlessRunError("headless invocation requires offline mode and no hosted calls")
