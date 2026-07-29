"""Cloud assessment inventory projection (Phase 4.7.4).

Organizes existing Cloud Hygiene Findings and rule-execution facts into
deterministic inventories. Does not re-collect evidence, re-run rules,
synthesize conclusions, or project report sections.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from codestrata.domain.cloud.assessment.models import (
    CloudConfidenceInventory,
    CloudCountBucket,
    CloudFindingInventory,
    CloudRuleInventory,
    CloudRuleInventoryEntry,
    CloudSeverityInventory,
    CloudTechnologyFamilyEntry,
    CloudTechnologyFamilyInventory,
)
from codestrata.domain.cloud.ids import (
    HYGIENE_RULE_IDS,
    RULE_CLOUD_NATIVE_INDICATORS,
    RULE_CONTAINERIZATION,
    RULE_DEPLOYMENT_PIPELINE,
    RULE_DEPLOYMENT_WITHOUT_PLATFORM,
    RULE_IAC_PRESENT,
    RULE_KUBERNETES,
    RULE_MANAGED_SERVICES,
    RULE_MULTIPLE_IAC,
    RULE_MULTIPLE_PLATFORMS,
    RULE_PLATFORM_DETECTED,
    RULE_SERVERLESS,
)
from codestrata.domain.findings.models import Finding

TECHNOLOGY_FAMILY_IDS: tuple[str, ...] = (
    "platforms",
    "containers",
    "orchestration",
    "iac",
    "serverless",
    "managed_services",
    "deployment_pipelines",
)

_RULE_TO_FAMILIES: dict[str, tuple[str, ...]] = {
    RULE_MULTIPLE_PLATFORMS: ("platforms",),
    RULE_PLATFORM_DETECTED: ("platforms",),
    RULE_CONTAINERIZATION: ("containers",),
    RULE_KUBERNETES: ("orchestration",),
    RULE_IAC_PRESENT: ("iac",),
    RULE_MULTIPLE_IAC: ("iac",),
    RULE_SERVERLESS: ("serverless",),
    RULE_DEPLOYMENT_PIPELINE: ("deployment_pipelines",),
    RULE_MANAGED_SERVICES: ("managed_services",),
}

_FAMILY_METADATA_KEYS: dict[str, tuple[str, ...]] = {
    "platforms": ("platforms",),
    "containers": ("container_kinds",),
    "orchestration": ("orchestration_kinds",),
    "iac": ("iac_kinds",),
    "serverless": ("serverless_kinds",),
    "managed_services": ("managed_services",),
    "deployment_pipelines": ("deployment_systems",),
}

_METADATA_FAMILY_ALIASES: dict[str, str] = {
    "platform": "platforms",
    "platforms": "platforms",
    "container": "containers",
    "containers": "containers",
    "orchestration": "orchestration",
    "iac": "iac",
    "serverless": "serverless",
    "managed_service": "managed_services",
    "managed_services": "managed_services",
    "deployment": "deployment_pipelines",
    "deployment_pipelines": "deployment_pipelines",
}


class CloudRuleExecutionFact(BaseModel):
    """Bounded per-rule execution fact for inventory (not a Finding).

    Mirrors ``codestrata.application.rules.cloud.assessment.CloudRuleExecutionFact``
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
) -> CloudFindingInventory:
    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    finding_ids = tuple(item.id for item in ordered)
    return CloudFindingInventory(
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
    execution_facts: Sequence[CloudRuleExecutionFact] = (),
    pack_enabled: bool = True,
) -> CloudRuleInventory:
    facts_by_id = {item.rule_id: item for item in execution_facts}
    by_rule: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_rule[finding.rule_id].append(finding)

    entries: list[CloudRuleInventoryEntry] = []
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
            CloudRuleInventoryEntry(
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
            CloudRuleInventoryEntry(
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
    return CloudRuleInventory(
        entries=ordered,
        rules_planned=len(registered_rule_ids) if pack_enabled else 0,
        rules_executed=executed_count,
        rules_matched=matched,
        rules_not_matched=not_matched,
        rules_not_applicable=not_applicable,
        rules_failed=failed,
    )


def _count_buckets(counter: Counter[str]) -> tuple[CloudCountBucket, ...]:
    return tuple(CloudCountBucket(key=key, count=count) for key, count in sorted(counter.items()))


def build_severity_inventory(
    findings: Sequence[Finding],
) -> CloudSeverityInventory:
    return CloudSeverityInventory(
        buckets=_count_buckets(Counter(item.severity.value for item in findings))
    )


def build_confidence_inventory(
    findings: Sequence[Finding],
) -> CloudConfidenceInventory:
    return CloudConfidenceInventory(
        buckets=_count_buckets(Counter(_confidence(item) for item in findings))
    )


def _families_for_finding(finding: Finding) -> tuple[str, ...]:
    mapped = _RULE_TO_FAMILIES.get(finding.rule_id)
    if mapped:
        return mapped
    if finding.rule_id in {
        RULE_CLOUD_NATIVE_INDICATORS,
        RULE_DEPLOYMENT_WITHOUT_PLATFORM,
    }:
        raw = str(finding.metadata.get("families", "")).strip()
        if raw:
            resolved = {
                _METADATA_FAMILY_ALIASES[part]
                for part in _split_csv(raw)
                if part in _METADATA_FAMILY_ALIASES
            }
            return tuple(sorted(resolved))
    return ()


def _technologies_for_family(finding: Finding, family_id: str) -> tuple[str, ...]:
    keys = _FAMILY_METADATA_KEYS.get(family_id, ())
    values: set[str] = set()
    for key in keys:
        raw = str(finding.metadata.get(key, "")).strip()
        if raw:
            values.update(_split_csv(raw))
    return tuple(sorted(values))


def build_technology_family_inventory(
    findings: Sequence[Finding],
) -> CloudTechnologyFamilyInventory:
    by_family: dict[str, list[Finding]] = {family: [] for family in TECHNOLOGY_FAMILY_IDS}
    tech_by_family: dict[str, set[str]] = {family: set() for family in TECHNOLOGY_FAMILY_IDS}
    for finding in findings:
        for family_id in _families_for_finding(finding):
            if family_id not in by_family:
                continue
            by_family[family_id].append(finding)
            tech_by_family[family_id].update(_technologies_for_family(finding, family_id))

    entries: list[CloudTechnologyFamilyEntry] = []
    for family_id in TECHNOLOGY_FAMILY_IDS:
        subset = by_family[family_id]
        finding_ids = tuple(sorted({item.id for item in subset}))
        entries.append(
            CloudTechnologyFamilyEntry(
                family_id=family_id,
                observed=bool(subset),
                finding_count=len(finding_ids),
                finding_ids=finding_ids,
                technologies=tuple(sorted(tech_by_family[family_id])),
            )
        )
    observed = sum(1 for item in entries if item.observed)
    return CloudTechnologyFamilyInventory(
        entries=tuple(entries),
        families_observed=observed,
        families_total=len(TECHNOLOGY_FAMILY_IDS),
    )


def findings_by_rule_counts(findings: Sequence[Finding]) -> dict[str, int]:
    return dict(sorted(Counter(item.rule_id for item in findings).items()))


def count_failed_rules(execution_facts: Sequence[CloudRuleExecutionFact]) -> int:
    return sum(1 for item in execution_facts if item.evaluation_status == "failed")


def count_succeeded_rules(
    execution_facts: Sequence[CloudRuleExecutionFact],
) -> int:
    return sum(
        1 for item in execution_facts if item.executed and item.evaluation_status != "failed"
    )


def execution_facts_from_status_map(
    status_by_rule: Mapping[str, str],
    *,
    diagnostics_by_rule: Mapping[str, Sequence[str]] | None = None,
    registered_rule_ids: Sequence[str] = HYGIENE_RULE_IDS,
) -> tuple[CloudRuleExecutionFact, ...]:
    """Build execution facts from rule_id → status mapping (tests / orchestration)."""

    diagnostics_by_rule = diagnostics_by_rule or {}
    facts: list[CloudRuleExecutionFact] = []
    for rule_id in registered_rule_ids:
        status = status_by_rule.get(rule_id, "not_executed")
        executed = status not in {"not_executed", "disabled", "skipped"}
        facts.append(
            CloudRuleExecutionFact(
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
) -> tuple[CloudRuleExecutionFact, ...]:
    """Normalize rule-pack facts into inventory execution facts."""

    converted: list[CloudRuleExecutionFact] = []
    for item in facts:
        if isinstance(item, CloudRuleExecutionFact):
            converted.append(item)
            continue
        converted.append(
            CloudRuleExecutionFact(
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
    "TECHNOLOGY_FAMILY_IDS",
    "CloudRuleExecutionFact",
    "build_confidence_inventory",
    "build_finding_inventory",
    "build_rule_inventory",
    "build_severity_inventory",
    "build_technology_family_inventory",
    "coerce_execution_facts",
    "count_failed_rules",
    "count_succeeded_rules",
    "execution_facts_from_status_map",
    "findings_by_rule_counts",
]
