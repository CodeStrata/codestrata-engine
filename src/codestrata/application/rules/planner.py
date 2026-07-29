"""Deterministic rule execution planner."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.incremental import (
    rule_invalidation_fingerprint,
    should_invalidate,
)
from codestrata.application.rules.models import RuleExecutionPlan, RulePlanEntry
from codestrata.application.rules.registry import RuleRegistry
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import RuleCategory, RuleSkipReason


class RulePlanner:
    def plan(
        self,
        registry: RuleRegistry,
        context: RuleExecutionContext,
        *,
        enabled_categories: Sequence[RuleCategory] | None = None,
        include_rule_ids: Sequence[str] | None = None,
        exclude_rule_ids: Sequence[str] | None = None,
        include_non_production: bool = False,
    ) -> RuleExecutionPlan:
        include = {item.strip().lower() for item in (include_rule_ids or ()) if item.strip()}
        exclude = {item.strip().lower() for item in (exclude_rule_ids or ()) if item.strip()}
        categories = set(enabled_categories) if enabled_categories is not None else None

        views = registry.list_rules(include_non_production=include_non_production)
        selected: list[str] = []
        skipped: list[RulePlanEntry] = []

        for view in views:
            meta = view.metadata
            rule_id = str(meta.rule_id)
            fingerprint = rule_invalidation_fingerprint(meta, context)

            if include and rule_id not in include:
                skipped.append(
                    RulePlanEntry(
                        rule_id=rule_id,
                        selected=False,
                        skip_reason=RuleSkipReason.NOT_SELECTED,
                        message="Not in explicit include set",
                        invalidation_fingerprint=fingerprint,
                    )
                )
                continue
            if rule_id in exclude:
                skipped.append(
                    RulePlanEntry(
                        rule_id=rule_id,
                        selected=False,
                        skip_reason=RuleSkipReason.EXPLICITLY_EXCLUDED,
                        message="Explicitly excluded",
                        invalidation_fingerprint=fingerprint,
                    )
                )
                continue
            if not meta.enabled_by_default and (not include or rule_id not in include):
                skipped.append(
                    RulePlanEntry(
                        rule_id=rule_id,
                        selected=False,
                        skip_reason=RuleSkipReason.DISABLED,
                        message="Rule disabled by default",
                        invalidation_fingerprint=fingerprint,
                    )
                )
                continue
            if categories is not None and meta.category not in categories:
                skipped.append(
                    RulePlanEntry(
                        rule_id=rule_id,
                        selected=False,
                        skip_reason=RuleSkipReason.CATEGORY_DISABLED,
                        message=f"Category {meta.category.value} not enabled",
                        invalidation_fingerprint=fingerprint,
                    )
                )
                continue
            if meta.supported_languages:
                languages = set(context.languages.languages)
                if not languages.intersection(meta.supported_languages):
                    skipped.append(
                        RulePlanEntry(
                            rule_id=rule_id,
                            selected=False,
                            skip_reason=RuleSkipReason.UNSUPPORTED_LANGUAGE,
                            message="No overlapping language inventory",
                            invalidation_fingerprint=fingerprint,
                        )
                    )
                    continue
            if meta.supported_repository_types:
                repo_type = (context.repository.repository_type or "").strip().lower()
                if repo_type not in meta.supported_repository_types:
                    skipped.append(
                        RulePlanEntry(
                            rule_id=rule_id,
                            selected=False,
                            skip_reason=RuleSkipReason.UNSUPPORTED_REPOSITORY_TYPE,
                            message="Repository type not supported",
                            invalidation_fingerprint=fingerprint,
                        )
                    )
                    continue
            # Enterprise-context requirements are evaluated at applicability time
            # so execution records can surface NOT_APPLICABLE deterministically.
            _ = should_invalidate(meta, context)
            selected.append(rule_id)

        selected_sorted = tuple(sorted(selected))
        if len(selected_sorted) > context.policy.max_rules_per_run:
            overflow = selected_sorted[context.policy.max_rules_per_run :]
            selected_sorted = selected_sorted[: context.policy.max_rules_per_run]
            for rule_id in overflow:
                skipped.append(
                    RulePlanEntry(
                        rule_id=rule_id,
                        selected=False,
                        skip_reason=RuleSkipReason.OTHER,
                        message="Exceeded max_rules_per_run",
                    )
                )

        return RuleExecutionPlan(
            selected_rule_ids=selected_sorted,
            skipped=tuple(sorted(skipped, key=lambda item: item.rule_id)),
            execution_order=selected_sorted,
            incremental_mode="conservative_recompute",
            reuse_claimed=False,
            full_execution_fallback_reason="phase_4_1_conservative_recompute",
        )
