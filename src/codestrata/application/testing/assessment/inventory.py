"""Test assessment inventory projection (Phase 4.6.4).

Organizes existing Test Hygiene Findings and rule-execution facts into
deterministic inventories. Does not re-collect evidence, re-run rules,
synthesize conclusions, or project report sections.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from codestrata.domain.findings.models import Finding
from codestrata.domain.testing.assessment.models import (
    TestConfidenceInventory,
    TestCountBucket,
    TestFindingInventory,
    TestRuleInventory,
    TestRuleInventoryEntry,
    TestSeverityInventory,
)
from codestrata.domain.testing.ids import HYGIENE_RULE_IDS


class TestingRuleExecutionFact(BaseModel):
    """Bounded per-rule execution fact for inventory (not a Finding).

    Mirrors ``codestrata.application.rules.testing.assessment.TestingRuleExecutionFact``
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


def build_finding_inventory(
    findings: Sequence[Finding],
) -> TestFindingInventory:
    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    finding_ids = tuple(item.id for item in ordered)
    return TestFindingInventory(
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
    execution_facts: Sequence[TestingRuleExecutionFact] = (),
    pack_enabled: bool = True,
) -> TestRuleInventory:
    facts_by_id = {item.rule_id: item for item in execution_facts}
    by_rule: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_rule[finding.rule_id].append(finding)

    entries: list[TestRuleInventoryEntry] = []
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
            TestRuleInventoryEntry(
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
            TestRuleInventoryEntry(
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
    return TestRuleInventory(
        entries=ordered,
        rules_planned=len(registered_rule_ids) if pack_enabled else 0,
        rules_executed=executed_count,
        rules_matched=matched,
        rules_not_matched=not_matched,
        rules_not_applicable=not_applicable,
        rules_failed=failed,
    )


def _count_buckets(counter: Counter[str]) -> tuple[TestCountBucket, ...]:
    return tuple(TestCountBucket(key=key, count=count) for key, count in sorted(counter.items()))


def build_severity_inventory(
    findings: Sequence[Finding],
) -> TestSeverityInventory:
    return TestSeverityInventory(
        buckets=_count_buckets(Counter(item.severity.value for item in findings))
    )


def build_confidence_inventory(
    findings: Sequence[Finding],
) -> TestConfidenceInventory:
    return TestConfidenceInventory(
        buckets=_count_buckets(Counter(_confidence(item) for item in findings))
    )


def findings_by_rule_counts(findings: Sequence[Finding]) -> dict[str, int]:
    return dict(sorted(Counter(item.rule_id for item in findings).items()))


def count_failed_rules(execution_facts: Sequence[TestingRuleExecutionFact]) -> int:
    return sum(1 for item in execution_facts if item.evaluation_status == "failed")


def count_succeeded_rules(
    execution_facts: Sequence[TestingRuleExecutionFact],
) -> int:
    return sum(
        1 for item in execution_facts if item.executed and item.evaluation_status != "failed"
    )


def execution_facts_from_status_map(
    status_by_rule: Mapping[str, str],
    *,
    diagnostics_by_rule: Mapping[str, Sequence[str]] | None = None,
    registered_rule_ids: Sequence[str] = HYGIENE_RULE_IDS,
) -> tuple[TestingRuleExecutionFact, ...]:
    """Build execution facts from rule_id → status mapping (tests / orchestration)."""

    diagnostics_by_rule = diagnostics_by_rule or {}
    facts: list[TestingRuleExecutionFact] = []
    for rule_id in registered_rule_ids:
        status = status_by_rule.get(rule_id, "not_executed")
        executed = status not in {"not_executed", "disabled", "skipped"}
        facts.append(
            TestingRuleExecutionFact(
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
) -> tuple[TestingRuleExecutionFact, ...]:
    """Normalize rule-pack facts into inventory execution facts."""

    converted: list[TestingRuleExecutionFact] = []
    for item in facts:
        if isinstance(item, TestingRuleExecutionFact):
            converted.append(item)
            continue
        converted.append(
            TestingRuleExecutionFact(
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
    "TestingRuleExecutionFact",
    "build_confidence_inventory",
    "build_finding_inventory",
    "build_rule_inventory",
    "build_severity_inventory",
    "coerce_execution_facts",
    "count_failed_rules",
    "count_succeeded_rules",
    "execution_facts_from_status_map",
    "findings_by_rule_counts",
]
