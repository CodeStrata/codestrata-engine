"""Performance assessment inventory projection (Phase 4.9.4).

Organizes existing Performance Hygiene Findings and rule-execution facts into
deterministic inventories. Does not re-collect evidence, re-run rules,
synthesize conclusions, or project report sections.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from codestrata.domain.findings.models import Finding
from codestrata.domain.performance.assessment.models import (
    PerformanceConfidenceInventory,
    PerformanceCountBucket,
    PerformanceFamilyEntry,
    PerformanceFamilyInventory,
    PerformanceFindingInventory,
    PerformanceRuleInventory,
    PerformanceRuleInventoryEntry,
    PerformanceSeverityInventory,
)
from codestrata.domain.performance.ids import (
    HYGIENE_RULE_IDS,
    RULE_BLOCKING_SLEEP,
    RULE_BROAD_FOUNDATIONS,
    RULE_CACHING,
    RULE_CONCURRENCY,
    RULE_CONCURRENCY_WITHOUT_CONFIG,
    RULE_CONFIG_CONTROLS,
    RULE_DATA_ACCESS,
    RULE_DATA_ACCESS_WITHOUT_BATCHING,
    RULE_DATA_WITHOUT_CACHING,
    RULE_EXECUTOR_CONFIG,
    RULE_FRONTEND_BUNDLE,
    RULE_FRONTEND_LAZY,
    RULE_FRONTEND_LIMITED,
    RULE_LIMITED_CONTROLS,
    RULE_MULTIPLE_DATA_ACCESS,
    RULE_OBSERVABILITY,
    RULE_RESOURCE_MGMT,
    RULE_RESOURCES_WITHOUT_MGMT,
    RULE_SYNC_IO,
    RULE_WITHOUT_OBSERVABILITY,
)
from codestrata.domain.performance.taxonomy import PerformanceCategory

PERFORMANCE_FAMILY_IDS: tuple[str, ...] = (
    "data_access",
    "blocking_operations",
    "caching",
    "concurrency_async",
    "resource_management",
    "frontend_performance",
    "observability_profiling",
    "configuration_controls",
)

_RULE_TO_FAMILIES: dict[str, tuple[str, ...]] = {
    RULE_DATA_ACCESS: ("data_access",),
    RULE_MULTIPLE_DATA_ACCESS: ("data_access",),
    RULE_DATA_ACCESS_WITHOUT_BATCHING: ("data_access",),
    RULE_BLOCKING_SLEEP: ("blocking_operations",),
    RULE_SYNC_IO: ("blocking_operations",),
    RULE_CACHING: ("caching",),
    RULE_DATA_WITHOUT_CACHING: ("caching",),
    RULE_CONCURRENCY: ("concurrency_async",),
    RULE_EXECUTOR_CONFIG: ("concurrency_async",),
    RULE_CONCURRENCY_WITHOUT_CONFIG: ("concurrency_async",),
    RULE_RESOURCE_MGMT: ("resource_management",),
    RULE_RESOURCES_WITHOUT_MGMT: ("resource_management",),
    RULE_FRONTEND_BUNDLE: ("frontend_performance",),
    RULE_FRONTEND_LAZY: ("frontend_performance",),
    RULE_FRONTEND_LIMITED: ("frontend_performance",),
    RULE_OBSERVABILITY: ("observability_profiling",),
    RULE_WITHOUT_OBSERVABILITY: ("observability_profiling",),
    RULE_CONFIG_CONTROLS: ("configuration_controls",),
}

_FAMILY_METADATA_KEYS: dict[str, tuple[str, ...]] = {
    "data_access": ("data_access_kinds", "data_access_control_kinds"),
    "blocking_operations": ("blocking_sleep_kinds", "sync_io_kinds"),
    "caching": ("caching_kinds",),
    "concurrency_async": (
        "concurrency_kinds",
        "executor_concurrency_kinds",
        "executor_config_kinds",
    ),
    "resource_management": ("resource_kinds",),
    "frontend_performance": (
        "frontend_kinds",
        "frontend_bundle_kinds",
        "frontend_lazy_kinds",
    ),
    "observability_profiling": ("observability_kinds",),
    "configuration_controls": ("configuration_kinds",),
}

_METADATA_FAMILY_ALIASES: dict[str, str] = {
    "data_access": "data_access",
    "blocking_operations": "blocking_operations",
    "blocking": "blocking_operations",
    "caching": "caching",
    "concurrency_async": "concurrency_async",
    "concurrency": "concurrency_async",
    "resource_management": "resource_management",
    "resources": "resource_management",
    "frontend_performance": "frontend_performance",
    "frontend": "frontend_performance",
    "observability_profiling": "observability_profiling",
    "observability": "observability_profiling",
    "configuration_controls": "configuration_controls",
    "configuration": "configuration_controls",
}

_CATEGORY_TO_FAMILY: dict[str, str] = {
    PerformanceCategory.INEFFICIENT_DATA_ACCESS.value: "data_access",
    PerformanceCategory.BLOCKING_OPERATIONS.value: "blocking_operations",
    PerformanceCategory.CACHING.value: "caching",
    PerformanceCategory.CONCURRENCY.value: "concurrency_async",
    PerformanceCategory.RESOURCE_MANAGEMENT.value: "resource_management",
    PerformanceCategory.FRONTEND_RENDERING_BUNDLE.value: "frontend_performance",
    PerformanceCategory.OBSERVABILITY_PROFILING.value: "observability_profiling",
    PerformanceCategory.CONFIGURATION_CONTROLS.value: "configuration_controls",
}


class PerformanceRuleExecutionFact(BaseModel):
    """Bounded per-rule execution fact for inventory (not a Finding).

    Mirrors ``codestrata.application.rules.performance.assessment.PerformanceRuleExecutionFact``
    so inventory builders stay independent of the rule-evaluation package.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    enabled: bool = True
    executed: bool = False
    evaluation_status: str = "not_executed"
    diagnostic_messages: tuple[str, ...] = ()


def _confidence(finding: Finding) -> str:
    return str(finding.metadata.get("confidence", "high")).strip() or "high"


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(sorted({part.strip() for part in raw.split(",") if part.strip()}))


def build_finding_inventory(
    findings: Sequence[Finding],
) -> PerformanceFindingInventory:
    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    finding_ids = tuple(item.id for item in ordered)
    return PerformanceFindingInventory(
        finding_ids=finding_ids,
        finding_count=len(finding_ids),
        rule_counts=dict(sorted(Counter(item.rule_id for item in ordered).items())),
        severity_counts=dict(sorted(Counter(item.severity.value for item in ordered).items())),
        confidence_counts=dict(sorted(Counter(_confidence(item) for item in ordered).items())),
    )


def build_rule_inventory(
    *,
    findings: Sequence[Finding] = (),
    registered_rule_ids: Sequence[str] = HYGIENE_RULE_IDS,
    execution_facts: Sequence[PerformanceRuleExecutionFact] = (),
    pack_enabled: bool = True,
) -> PerformanceRuleInventory:
    facts_by_id = {item.rule_id: item for item in execution_facts}
    by_rule: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_rule[finding.rule_id].append(finding)

    entries: list[PerformanceRuleInventoryEntry] = []
    for rule_id in registered_rule_ids:
        fact = facts_by_id.get(rule_id)
        subset = by_rule.get(rule_id, [])
        executed = bool(fact.executed) if fact is not None else False
        status = (
            fact.evaluation_status
            if fact is not None
            else ("not_executed" if pack_enabled else "disabled")
        )
        entries.append(
            PerformanceRuleInventoryEntry(
                rule_id=rule_id,
                enabled=pack_enabled if fact is None else fact.enabled,
                executed=executed,
                evaluation_status=status,
                finding_count=len(subset),
                diagnostic_count=(len(fact.diagnostic_messages) if fact is not None else 0),
            )
        )

    for rule_id in sorted(by_rule):
        if rule_id in registered_rule_ids:
            continue
        subset = by_rule[rule_id]
        fact = facts_by_id.get(rule_id)
        entries.append(
            PerformanceRuleInventoryEntry(
                rule_id=rule_id,
                enabled=True,
                executed=bool(fact.executed) if fact is not None else True,
                evaluation_status=(fact.evaluation_status if fact is not None else "matched"),
                finding_count=len(subset),
                diagnostic_count=(len(fact.diagnostic_messages) if fact is not None else 0),
            )
        )

    ordered = tuple(sorted(entries, key=lambda item: item.rule_id))
    matched = sum(1 for item in ordered if item.evaluation_status == "matched")
    not_matched = sum(1 for item in ordered if item.evaluation_status == "not_matched")
    not_applicable = sum(1 for item in ordered if item.evaluation_status == "not_applicable")
    failed = sum(1 for item in ordered if item.evaluation_status == "failed")
    executed_count = sum(1 for item in ordered if item.executed)
    return PerformanceRuleInventory(
        entries=ordered,
        rules_planned=len(registered_rule_ids) if pack_enabled else 0,
        rules_executed=executed_count,
        rules_matched=matched,
        rules_not_matched=not_matched,
        rules_not_applicable=not_applicable,
        rules_failed=failed,
    )


def _count_buckets(counter: Counter[str]) -> tuple[PerformanceCountBucket, ...]:
    return tuple(
        PerformanceCountBucket(key=key, count=count) for key, count in sorted(counter.items())
    )


def build_severity_inventory(
    findings: Sequence[Finding],
) -> PerformanceSeverityInventory:
    return PerformanceSeverityInventory(
        buckets=_count_buckets(Counter(item.severity.value for item in findings))
    )


def build_confidence_inventory(
    findings: Sequence[Finding],
) -> PerformanceConfidenceInventory:
    return PerformanceConfidenceInventory(
        buckets=_count_buckets(Counter(_confidence(item) for item in findings))
    )


def _families_from_metadata_csv(raw: str) -> tuple[str, ...]:
    resolved = {
        _METADATA_FAMILY_ALIASES[part]
        for part in _split_csv(raw)
        if part in _METADATA_FAMILY_ALIASES
    }
    return tuple(sorted(resolved))


def _family_from_category(finding: Finding) -> tuple[str, ...]:
    raw = str(finding.metadata.get("performance_category", "")).strip()
    if not raw:
        return ()
    family = _CATEGORY_TO_FAMILY.get(raw)
    if family:
        return (family,)
    bare = raw.removeprefix("performance.")
    for category_value, family_id in _CATEGORY_TO_FAMILY.items():
        if category_value.removeprefix("performance.") == bare:
            return (family_id,)
    return ()


def _families_for_finding(finding: Finding) -> tuple[str, ...]:
    mapped = _RULE_TO_FAMILIES.get(finding.rule_id)
    if mapped:
        return mapped
    if finding.rule_id in {RULE_BROAD_FOUNDATIONS, RULE_LIMITED_CONTROLS}:
        raw = str(finding.metadata.get("families", "")).strip()
        if raw:
            return _families_from_metadata_csv(raw)
    return _family_from_category(finding)


def _signals_for_family(finding: Finding, family_id: str) -> tuple[str, ...]:
    keys = _FAMILY_METADATA_KEYS.get(family_id, ())
    values: set[str] = set()
    for key in keys:
        raw = str(finding.metadata.get(key, "")).strip()
        if raw:
            values.update(_split_csv(raw))
    return tuple(sorted(values))


def build_performance_family_inventory(
    findings: Sequence[Finding],
) -> PerformanceFamilyInventory:
    by_family: dict[str, list[Finding]] = {family: [] for family in PERFORMANCE_FAMILY_IDS}
    signals_by_family: dict[str, set[str]] = {family: set() for family in PERFORMANCE_FAMILY_IDS}
    for finding in findings:
        for family_id in _families_for_finding(finding):
            if family_id not in by_family:
                continue
            by_family[family_id].append(finding)
            signals_by_family[family_id].update(_signals_for_family(finding, family_id))

    entries: list[PerformanceFamilyEntry] = []
    for family_id in PERFORMANCE_FAMILY_IDS:
        subset = by_family[family_id]
        finding_ids = tuple(sorted({item.id for item in subset}))
        entries.append(
            PerformanceFamilyEntry(
                family_id=family_id,
                observed=bool(subset),
                finding_count=len(finding_ids),
                finding_ids=finding_ids,
                signals=tuple(sorted(signals_by_family[family_id])),
            )
        )
    observed = sum(1 for item in entries if item.observed)
    return PerformanceFamilyInventory(
        entries=tuple(entries),
        families_observed=observed,
        families_total=len(PERFORMANCE_FAMILY_IDS),
    )


# Compat alias for callers expecting the prior signal-family name.
build_signal_family_inventory = build_performance_family_inventory


def findings_by_rule_counts(findings: Sequence[Finding]) -> dict[str, int]:
    return dict(sorted(Counter(item.rule_id for item in findings).items()))


def count_failed_rules(execution_facts: Sequence[PerformanceRuleExecutionFact]) -> int:
    return sum(1 for item in execution_facts if item.evaluation_status == "failed")


def count_succeeded_rules(
    execution_facts: Sequence[PerformanceRuleExecutionFact],
) -> int:
    return sum(
        1 for item in execution_facts if item.executed and item.evaluation_status != "failed"
    )


def execution_facts_from_status_map(
    status_by_rule: Mapping[str, str],
    *,
    diagnostics_by_rule: Mapping[str, Sequence[str]] | None = None,
    registered_rule_ids: Sequence[str] = HYGIENE_RULE_IDS,
) -> tuple[PerformanceRuleExecutionFact, ...]:
    """Build execution facts from rule_id → status mapping (tests / orchestration)."""

    diagnostics_by_rule = diagnostics_by_rule or {}
    facts: list[PerformanceRuleExecutionFact] = []
    for rule_id in registered_rule_ids:
        status = status_by_rule.get(rule_id, "not_executed")
        executed = status not in {"not_executed", "disabled", "skipped"}
        facts.append(
            PerformanceRuleExecutionFact(
                rule_id=rule_id,
                enabled=status != "disabled",
                executed=executed,
                evaluation_status=status,
                diagnostic_messages=tuple(
                    str(item) for item in diagnostics_by_rule.get(rule_id, ())
                ),
            )
        )
    return tuple(sorted(facts, key=lambda item: item.rule_id))


def coerce_execution_facts(
    facts: Sequence[object],
) -> tuple[PerformanceRuleExecutionFact, ...]:
    """Normalize rule-pack facts into inventory execution facts."""

    converted: list[PerformanceRuleExecutionFact] = []
    for item in facts:
        if isinstance(item, PerformanceRuleExecutionFact):
            converted.append(item)
            continue
        converted.append(
            PerformanceRuleExecutionFact(
                rule_id=str(getattr(item, "rule_id", "")),
                enabled=bool(getattr(item, "enabled", True)),
                executed=bool(getattr(item, "executed", False)),
                evaluation_status=str(getattr(item, "evaluation_status", "not_executed")),
                diagnostic_messages=tuple(
                    str(message) for message in getattr(item, "diagnostic_messages", ())
                ),
            )
        )
    return tuple(sorted(converted, key=lambda item: item.rule_id))


__all__ = [
    "PERFORMANCE_FAMILY_IDS",
    "PerformanceRuleExecutionFact",
    "build_confidence_inventory",
    "build_finding_inventory",
    "build_performance_family_inventory",
    "build_rule_inventory",
    "build_severity_inventory",
    "build_signal_family_inventory",
    "coerce_execution_facts",
    "count_failed_rules",
    "count_succeeded_rules",
    "execution_facts_from_status_map",
    "findings_by_rule_counts",
]
