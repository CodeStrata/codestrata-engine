"""AI Readiness assessment inventory projection (Phase 4.8.4).

Organizes existing AI Readiness Hygiene Findings and rule-execution facts into
deterministic inventories. Does not re-collect evidence, re-run rules,
synthesize conclusions, or project report sections.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from codestrata.domain.ai_readiness.assessment.models import (
    AiReadinessCapabilityFamilyEntry,
    AiReadinessCapabilityFamilyInventory,
    AiReadinessConfidenceInventory,
    AiReadinessCountBucket,
    AiReadinessFindingInventory,
    AiReadinessRuleInventory,
    AiReadinessRuleInventoryEntry,
    AiReadinessSeverityInventory,
)
from codestrata.domain.ai_readiness.ids import (
    HYGIENE_RULE_IDS,
    RULE_AI_WITHOUT_OBSERVABILITY,
    RULE_API_BOUNDARIES,
    RULE_ARCHITECTURE_DOCS,
    RULE_BROAD_FOUNDATIONS,
    RULE_DATA_ACCESS,
    RULE_LIMITED_API_BOUNDARIES,
    RULE_LIMITED_DOCUMENTATION,
    RULE_LIMITED_FOUNDATIONS,
    RULE_LLM_SDK,
    RULE_MCP_TOOLS,
    RULE_OBSERVABILITY_GOVERNANCE,
    RULE_PROMPT_ASSETS,
    RULE_RAG_PIPELINE,
    RULE_SEARCH_RETRIEVAL,
    RULE_STRUCTURED_API_SPEC,
    RULE_VECTOR_EMBEDDINGS,
    RULE_WORKFLOW_AGENT,
)
from codestrata.domain.ai_readiness.taxonomy import AiReadinessCategory
from codestrata.domain.findings.models import Finding

CAPABILITY_FAMILY_IDS: tuple[str, ...] = (
    "api_boundaries",
    "documentation_metadata",
    "data_retrieval",
    "ai_integrations",
    "tool_mcp",
    "workflow_agents",
    "observability_governance",
)

_RULE_TO_FAMILIES: dict[str, tuple[str, ...]] = {
    RULE_API_BOUNDARIES: ("api_boundaries",),
    RULE_STRUCTURED_API_SPEC: ("api_boundaries",),
    RULE_LIMITED_API_BOUNDARIES: ("api_boundaries",),
    RULE_ARCHITECTURE_DOCS: ("documentation_metadata",),
    RULE_LIMITED_DOCUMENTATION: ("documentation_metadata",),
    RULE_DATA_ACCESS: ("data_retrieval",),
    RULE_SEARCH_RETRIEVAL: ("data_retrieval",),
    RULE_VECTOR_EMBEDDINGS: ("data_retrieval",),
    RULE_LLM_SDK: ("ai_integrations",),
    RULE_PROMPT_ASSETS: ("ai_integrations",),
    RULE_RAG_PIPELINE: ("ai_integrations",),
    RULE_MCP_TOOLS: ("tool_mcp",),
    RULE_WORKFLOW_AGENT: ("workflow_agents",),
    RULE_OBSERVABILITY_GOVERNANCE: ("observability_governance",),
    RULE_AI_WITHOUT_OBSERVABILITY: ("observability_governance",),
}

_FAMILY_METADATA_KEYS: dict[str, tuple[str, ...]] = {
    "api_boundaries": ("api_boundary_kinds",),
    "documentation_metadata": ("documentation_kinds", "supporting_documentation_kinds"),
    "data_retrieval": (
        "data_access_kinds",
        "search_retrieval_kinds",
        "vector_embedding_signals",
    ),
    "ai_integrations": ("llm_kinds", "prompt_kinds", "rag_kinds"),
    "tool_mcp": ("tool_mcp_kinds",),
    "workflow_agents": ("workflow_agent_kinds",),
    "observability_governance": ("observability_governance_kinds", "ai_related_assets"),
}

_METADATA_FAMILY_ALIASES: dict[str, str] = {
    "api_boundary": "api_boundaries",
    "api_boundaries": "api_boundaries",
    "documentation": "documentation_metadata",
    "documentation_metadata": "documentation_metadata",
    "data_retrieval": "data_retrieval",
    "ai_integration": "ai_integrations",
    "ai_integrations": "ai_integrations",
    "tool_mcp": "tool_mcp",
    "workflow_agent": "workflow_agents",
    "workflow_agents": "workflow_agents",
    "observability_governance": "observability_governance",
}

_CATEGORY_TO_FAMILY: dict[str, str] = {
    AiReadinessCategory.API_AND_SERVICE_BOUNDARIES.value: "api_boundaries",
    AiReadinessCategory.DOCUMENTATION_AND_METADATA_QUALITY.value: "documentation_metadata",
    AiReadinessCategory.DATA_ACCESS_PATTERNS.value: "data_retrieval",
    AiReadinessCategory.SEARCH_AND_RETRIEVAL_READINESS.value: "data_retrieval",
    AiReadinessCategory.RAG_ENABLING_ASSETS.value: "data_retrieval",
    AiReadinessCategory.TOOL_AND_MCP_INTEGRATION.value: "tool_mcp",
    AiReadinessCategory.WORKFLOW_AND_AGENT_BOUNDARIES.value: "workflow_agents",
    AiReadinessCategory.EXISTING_AI_LLM_INTEGRATIONS.value: "ai_integrations",
    AiReadinessCategory.OBSERVABILITY_AND_GOVERNANCE.value: "observability_governance",
}


class AiReadinessRuleExecutionFact(BaseModel):
    """Bounded per-rule execution fact for inventory (not a Finding).

    Mirrors ``codestrata.application.rules.ai_readiness.assessment.AiReadinessRuleExecutionFact``
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
) -> AiReadinessFindingInventory:
    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    finding_ids = tuple(item.id for item in ordered)
    return AiReadinessFindingInventory(
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
    execution_facts: Sequence[AiReadinessRuleExecutionFact] = (),
    pack_enabled: bool = True,
) -> AiReadinessRuleInventory:
    facts_by_id = {item.rule_id: item for item in execution_facts}
    by_rule: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_rule[finding.rule_id].append(finding)

    entries: list[AiReadinessRuleInventoryEntry] = []
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
            AiReadinessRuleInventoryEntry(
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
            AiReadinessRuleInventoryEntry(
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
    return AiReadinessRuleInventory(
        entries=ordered,
        rules_planned=len(registered_rule_ids) if pack_enabled else 0,
        rules_executed=executed_count,
        rules_matched=matched,
        rules_not_matched=not_matched,
        rules_not_applicable=not_applicable,
        rules_failed=failed,
    )


def _count_buckets(counter: Counter[str]) -> tuple[AiReadinessCountBucket, ...]:
    return tuple(
        AiReadinessCountBucket(key=key, count=count) for key, count in sorted(counter.items())
    )


def build_severity_inventory(
    findings: Sequence[Finding],
) -> AiReadinessSeverityInventory:
    return AiReadinessSeverityInventory(
        buckets=_count_buckets(Counter(item.severity.value for item in findings))
    )


def build_confidence_inventory(
    findings: Sequence[Finding],
) -> AiReadinessConfidenceInventory:
    return AiReadinessConfidenceInventory(
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
    raw = str(finding.metadata.get("ai_readiness_category", "")).strip()
    if not raw:
        return ()
    family = _CATEGORY_TO_FAMILY.get(raw)
    if family:
        return (family,)
    # Accept bare category suffixes (without ai_readiness. prefix).
    bare = raw.removeprefix("ai_readiness.")
    for category_value, family_id in _CATEGORY_TO_FAMILY.items():
        if category_value.removeprefix("ai_readiness.") == bare:
            return (family_id,)
    return ()


def _families_for_finding(finding: Finding) -> tuple[str, ...]:
    mapped = _RULE_TO_FAMILIES.get(finding.rule_id)
    if mapped:
        return mapped
    if finding.rule_id in {RULE_BROAD_FOUNDATIONS, RULE_LIMITED_FOUNDATIONS}:
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


def build_capability_family_inventory(
    findings: Sequence[Finding],
) -> AiReadinessCapabilityFamilyInventory:
    by_family: dict[str, list[Finding]] = {family: [] for family in CAPABILITY_FAMILY_IDS}
    signals_by_family: dict[str, set[str]] = {family: set() for family in CAPABILITY_FAMILY_IDS}
    for finding in findings:
        for family_id in _families_for_finding(finding):
            if family_id not in by_family:
                continue
            by_family[family_id].append(finding)
            signals_by_family[family_id].update(_signals_for_family(finding, family_id))

    entries: list[AiReadinessCapabilityFamilyEntry] = []
    for family_id in CAPABILITY_FAMILY_IDS:
        subset = by_family[family_id]
        finding_ids = tuple(sorted({item.id for item in subset}))
        entries.append(
            AiReadinessCapabilityFamilyEntry(
                family_id=family_id,
                observed=bool(subset),
                finding_count=len(finding_ids),
                finding_ids=finding_ids,
                signals=tuple(sorted(signals_by_family[family_id])),
            )
        )
    observed = sum(1 for item in entries if item.observed)
    return AiReadinessCapabilityFamilyInventory(
        entries=tuple(entries),
        families_observed=observed,
        families_total=len(CAPABILITY_FAMILY_IDS),
    )


def findings_by_rule_counts(findings: Sequence[Finding]) -> dict[str, int]:
    return dict(sorted(Counter(item.rule_id for item in findings).items()))


def count_failed_rules(execution_facts: Sequence[AiReadinessRuleExecutionFact]) -> int:
    return sum(1 for item in execution_facts if item.evaluation_status == "failed")


def count_succeeded_rules(
    execution_facts: Sequence[AiReadinessRuleExecutionFact],
) -> int:
    return sum(
        1 for item in execution_facts if item.executed and item.evaluation_status != "failed"
    )


def execution_facts_from_status_map(
    status_by_rule: Mapping[str, str],
    *,
    diagnostics_by_rule: Mapping[str, Sequence[str]] | None = None,
    registered_rule_ids: Sequence[str] = HYGIENE_RULE_IDS,
) -> tuple[AiReadinessRuleExecutionFact, ...]:
    """Build execution facts from rule_id → status mapping (tests / orchestration)."""

    diagnostics_by_rule = diagnostics_by_rule or {}
    facts: list[AiReadinessRuleExecutionFact] = []
    for rule_id in registered_rule_ids:
        status = status_by_rule.get(rule_id, "not_executed")
        executed = status not in {"not_executed", "disabled", "skipped"}
        facts.append(
            AiReadinessRuleExecutionFact(
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
) -> tuple[AiReadinessRuleExecutionFact, ...]:
    """Normalize rule-pack facts into inventory execution facts."""

    converted: list[AiReadinessRuleExecutionFact] = []
    for item in facts:
        if isinstance(item, AiReadinessRuleExecutionFact):
            converted.append(item)
            continue
        converted.append(
            AiReadinessRuleExecutionFact(
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
    "CAPABILITY_FAMILY_IDS",
    "AiReadinessRuleExecutionFact",
    "build_capability_family_inventory",
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
