"""Incremental invalidation fingerprints for shared rules."""

from __future__ import annotations

import hashlib

from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import RuleIncrementalBehavior
from codestrata.domain.rules.metadata import RuleMetadata


def rule_invalidation_fingerprint(
    metadata: RuleMetadata,
    context: RuleExecutionContext,
) -> str:
    """Stable fingerprint for planning / future reuse decisions.

    Phase 4.1 is conservative: planning always recomputes. This fingerprint
    establishes the contract for later selective execution.
    """

    parts = [
        str(metadata.rule_id),
        str(metadata.version),
        metadata.category.value,
        ",".join(sorted(b.value for b in metadata.incremental_behaviors)),
        context.repository.repository_id,
        ",".join(context.languages.languages),
        ",".join(f"{k}={v}" for k, v in sorted(context.configuration_facts.items())),
        "enterprise" if context.has_enterprise_context else "no-enterprise",
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:24]


def should_invalidate(
    metadata: RuleMetadata,
    context: RuleExecutionContext,
) -> bool:
    """Return True when the rule must recompute given incremental hints."""

    behaviors = set(metadata.incremental_behaviors)
    incremental = context.incremental
    if incremental.force_full_execution:
        return True
    if RuleIncrementalBehavior.ALWAYS_RUN in behaviors:
        return True
    if RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT in behaviors:
        return True
    if (
        RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES in behaviors
        and incremental.changed_paths
    ):
        return True
    if (
        RuleIncrementalBehavior.AFFECTED_BY_DEPENDENCY_CHANGES in behaviors
        and incremental.dependency_changed
    ):
        return True
    if (
        RuleIncrementalBehavior.AFFECTED_BY_BUILD_CHANGES in behaviors
        and incremental.build_changed
    ):
        return True
    if (
        RuleIncrementalBehavior.AFFECTED_BY_GRAPH_CHANGES in behaviors
        and incremental.graph_changed
    ):
        return True
    if (
        RuleIncrementalBehavior.AFFECTED_BY_ENTERPRISE_CONTEXT_CHANGES in behaviors
        and incremental.enterprise_context_changed
    ):
        return True
    return True  # conservative default: recompute
