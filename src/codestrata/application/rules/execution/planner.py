"""Plan YAML launch-catalog rules. Disabled and suppressed stay visible."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from codestrata.application.rules.compiler import (
    CapabilityError,
    YamlCompileError,
    compile_rule_yaml,
)
from codestrata.application.rules.execution.budgets import execution_budgets
from codestrata.domain.contracts.enums import CoverageState, ExecutionPurpose
from codestrata.domain.contracts.models import BudgetLimits
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.rules.compiler_models import CompilationPlan
from codestrata.domain.rules.errors import RuleDomainError


class CatalogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    yaml_text: str
    enabled: bool = True
    suppressed: bool = False
    suppression_ref: str | None = None
    rule_revision: str | None = None


class PlannedRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    rule_revision: str
    enabled: bool
    suppressed: bool
    coverage_state: CoverageState
    selected: bool
    plan: CompilationPlan | None = None
    reason: str | None = None
    suppression_ref: str | None = None


class LaunchExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    purpose: ExecutionPurpose
    entries: tuple[PlannedRule, ...]
    selected_rule_ids: tuple[str, ...]
    plan_digest: str
    overflow_rule_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class CatalogCompileError(RuleDomainError):
    pass


def compile_catalog_entry(entry: CatalogEntry) -> CompilationPlan:
    try:
        plan = compile_rule_yaml(entry.yaml_text.encode("utf-8"), label=f"{entry.rule_id}.yaml")
    except (YamlCompileError, CapabilityError, ValueError) as error:
        reason = getattr(error, "reason_code", "catalog_compile_failed")
        raise CatalogCompileError(
            f"catalog YAML failed to compile: {type(error).__name__}",
            reason_code=str(reason),
            rule_id=entry.rule_id,
        ) from error
    if plan.kind != "Rule" or plan.rule is None or plan.condition is None:
        raise CatalogCompileError(
            "launch catalog entries must compile to a Rule with a condition",
            reason_code="catalog_not_rule",
            rule_id=entry.rule_id,
        )
    compiled_id = plan.rule.metadata.id
    if compiled_id != entry.rule_id:
        raise CatalogCompileError(
            f"YAML id {compiled_id} does not match catalog id {entry.rule_id}",
            reason_code="catalog_id_mismatch",
            rule_id=entry.rule_id,
        )
    return plan


def plan_launch_catalog(
    entries: tuple[CatalogEntry, ...] | list[CatalogEntry],
    *,
    purpose: ExecutionPurpose,
    budgets: BudgetLimits | None = None,
) -> LaunchExecutionPlan:
    bound = budgets or execution_budgets()
    planned: list[PlannedRule] = []
    for entry in sorted(entries, key=lambda item: item.rule_id):
        try:
            compiled = compile_catalog_entry(entry)
        except CatalogCompileError as error:
            planned.append(
                PlannedRule(
                    rule_id=entry.rule_id,
                    rule_revision=entry.rule_revision or "0.0.0",
                    enabled=entry.enabled,
                    suppressed=entry.suppressed,
                    coverage_state=CoverageState.ERROR,
                    selected=False,
                    reason=error.reason_code,
                    suppression_ref=entry.suppression_ref,
                )
            )
            continue
        assert compiled.rule is not None
        revision = entry.rule_revision or compiled.rule.metadata.version
        if not entry.enabled:
            planned.append(
                PlannedRule(
                    rule_id=entry.rule_id,
                    rule_revision=revision,
                    enabled=False,
                    suppressed=entry.suppressed,
                    coverage_state=CoverageState.DISABLED,
                    selected=False,
                    plan=compiled,
                    reason="disabled",
                    suppression_ref=entry.suppression_ref,
                )
            )
            continue
        coverage = CoverageState.SUPPRESSED if entry.suppressed else CoverageState.COMPLETE
        planned.append(
            PlannedRule(
                rule_id=entry.rule_id,
                rule_revision=revision,
                enabled=True,
                suppressed=entry.suppressed,
                coverage_state=coverage,
                selected=True,
                plan=compiled,
                suppression_ref=entry.suppression_ref,
            )
        )

    selected = tuple(item.rule_id for item in planned if item.selected)
    overflow: tuple[str, ...] = ()
    limitations: list[str] = []
    if len(selected) > bound.max_effective_rules:
        keep = selected[: bound.max_effective_rules]
        overflow = selected[bound.max_effective_rules :]
        rewritten: list[PlannedRule] = []
        overflow_set = set(overflow)
        for item in planned:
            if item.rule_id in overflow_set:
                rewritten.append(
                    item.model_copy(
                        update={
                            "selected": False,
                            "coverage_state": CoverageState.ERROR,
                            "reason": "max_effective_rules",
                        }
                    )
                )
            else:
                rewritten.append(item)
        planned = rewritten
        selected = keep
        limitations.append("max_effective_rules")

    digest_payload = {
        "purpose": purpose.value,
        "rules": [
            {
                "rule_id": item.rule_id,
                "revision": item.rule_revision,
                "enabled": item.enabled,
                "suppressed": item.suppressed,
                "selected": item.selected,
                "plan_digest": None if item.plan is None else item.plan.plan_digest,
                "reason": item.reason,
            }
            for item in planned
        ],
        "overflow": list(overflow),
    }
    return LaunchExecutionPlan(
        purpose=purpose,
        entries=tuple(planned),
        selected_rule_ids=selected,
        plan_digest=digest_canonical(digest_payload),
        overflow_rule_ids=overflow,
        limitations=tuple(limitations),
    )
