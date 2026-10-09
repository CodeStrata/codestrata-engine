"""Typed selector AST, capability catalog and compilation plan (E03.1).

Presentation metadata (title, message, documentation URL) is hashed separately
from selector identity. A selector change cannot hide in presentation fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.contracts.rules import (
    CAPABILITY_VERSION,
    DISALLOWED_OPERATORS,
    ConditionNode,
    Rule,
    RuleSet,
    SelectClause,
    SelectorDef,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.graph.validation import require_nonblank

COMPILER_VERSION = "1.0.0"
PLAN_SCHEMA = "codestrata.rule-compilation-plan.v1"
PLAN_SCHEMA_VERSION = "1.0.0"

# Launch-bounded facts the YAML compiler admits. Anything else is a capability error.
SUPPORTED_FACTS = frozenset(
    {
        "module.declaration",
        "graph.imports",
        "graph.depends_on",
        "graph.nodes",
        "source.span",
        "metric.value",
        "metric.component_concentration",
        "metric.direction_violations",
        "metric.framework_leakage",
        "finding.occurrence",
        "repository.files",
        "test.association",
        "ci.job",
    }
)

# Security-rejected operators in addition to E01.3 DISALLOWED_OPERATORS.
FORBIDDEN_OPERATOR_ALIASES = frozenset(
    {
        "shell",
        "file",
        "readfile",
        "write_file",
        "subprocess",
        "system",
        "popen",
        "fetch",
        "http",
        "urlopen",
        "open",
        "compile",
        "execfile",
    }
)

SELECTOR_COMBINATORS = frozenset({"all", "any", "not", "none"})
SELECTOR_PREDICATE_KEYS = frozenset({"type", "kind", "generated", "language", "path", "id", "name"})

PRESENTATION_METADATA_KEYS = frozenset({"title", "owner", "category"})
PRESENTATION_FINDING_KEYS = frozenset(
    {"message_template", "documentation_url", "bindings", "default_severity"}
)


def disallowed_operators() -> frozenset[str]:
    return DISALLOWED_OPERATORS | FORBIDDEN_OPERATOR_ALIASES


def selector_identity_payload(
    *,
    source: str | None,
    nodes: dict[str, Any] | None,
    selector_ref: str | None,
) -> dict[str, Any]:
    return {
        "nodes": nodes if nodes is not None else {},
        "selector_ref": selector_ref,
        "source": source,
    }


def selector_ast_digest_for(
    *,
    source: str | None,
    nodes: dict[str, Any] | None,
    selector_ref: str | None = None,
) -> str:
    """Pin selector identity to source+nodes (+ optional ref), never presentation."""

    return digest_canonical(
        selector_identity_payload(source=source, nodes=nodes, selector_ref=selector_ref)
    )


def presentation_payload_from_rule(rule: Rule) -> dict[str, Any]:
    finding = rule.finding.model_dump(mode="json")
    return {
        "finding": {key: finding.get(key) for key in sorted(PRESENTATION_FINDING_KEYS)},
        "metadata": {
            key: getattr(rule.metadata, key) for key in sorted(PRESENTATION_METADATA_KEYS)
        },
        "metric": None if rule.metric is None else rule.metric.model_dump(mode="json"),
    }


def presentation_digest_for(rule: Rule) -> str:
    return digest_canonical(presentation_payload_from_rule(rule))


class SelectorPredicate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str | None = None
    kind: str | None = None
    generated: bool | None = None
    language: str | None = None
    path: str | None = None
    id: str | None = None
    name: str | None = None

    @field_validator("type", "kind", "language", "path", "id", "name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_nonblank(str(value), label="selector predicate")

    @model_validator(mode="after")
    def require_one_field(self) -> SelectorPredicate:
        if not any(
            value is not None
            for value in (
                self.type,
                self.kind,
                self.generated,
                self.language,
                self.path,
                self.id,
                self.name,
            )
        ):
            raise ValueError("selector predicate must declare at least one field")
        return self


class SelectorAst(BaseModel):
    """Typed selector AST. Combinators are closed; unknown keys are rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str | None = None
    selector_ref: str | None = None
    combinator: str | None = None
    predicates: tuple[SelectorPredicate, ...] = ()
    nodes: dict[str, Any] = Field(default_factory=dict)
    digest: str

    @field_validator("combinator", mode="before")
    @classmethod
    def normalize_combinator(cls, value: object) -> str | None:
        if value is None:
            return None
        token = require_nonblank(str(value), label="selector combinator").lower()
        if token not in SELECTOR_COMBINATORS:
            raise ValueError(f"unknown selector combinator {token}")
        return token


class ConditionPlan(BaseModel):
    """Serializable condition tree. Traversal and view pins are preserved for E03.2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operator: str
    fact: str | None = None
    value: str | int | float | bool | None = None
    edge_types: tuple[str, ...] = ()
    traversal: str | None = None
    max_depth: int | None = Field(default=None, ge=1)
    dependency_view: str | None = None
    operands: tuple[ConditionPlan, ...] = ()

    @field_validator("operator", mode="before")
    @classmethod
    def normalize_operator(cls, value: object) -> str:
        return require_nonblank(str(value), label="operator").lower()

    @model_validator(mode="after")
    def bound_traversal(self) -> ConditionPlan:
        if self.traversal == "direct" and self.max_depth not in (None, 1):
            raise ValueError("direct traversal has max_depth 1")
        if self.traversal == "transitive" and (self.max_depth is None or self.max_depth < 1):
            raise ValueError("transitive traversal requires a positive bounded max_depth")
        if self.dependency_view is not None and self.dependency_view not in {
            "declared",
            "resolved",
        }:
            raise ValueError("dependency_view must be declared or resolved")
        return self


class CapabilityBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operators: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    capability_version: str = CAPABILITY_VERSION
    unsupported: tuple[str, ...] = ()


class CompilationPlan(BaseModel):
    """Serializable intermediate plan. Selector digest is independent of presentation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = PLAN_SCHEMA
    schema_version: str = PLAN_SCHEMA_VERSION
    compiler_version: str = COMPILER_VERSION
    kind: str
    source_digest: str
    document_digest: str
    selector_digest: str
    presentation_digest: str
    plan_digest: str
    selector_ast: SelectorAst | None = None
    selectors: tuple[SelectorAst, ...] = ()
    condition: ConditionPlan | None = None
    capabilities: CapabilityBinding
    rule: Rule | None = None
    ruleset: RuleSet | None = None


def condition_plan_from(node: ConditionNode) -> ConditionPlan:
    return ConditionPlan(
        operator=node.operator,
        fact=node.fact,
        value=node.value,
        edge_types=tuple(node.edge_types),
        traversal=node.traversal,
        max_depth=node.max_depth,
        dependency_view=node.dependency_view,
        operands=tuple(condition_plan_from(item) for item in node.operands),
    )


def collect_operators(node: ConditionNode) -> tuple[str, ...]:
    found = [node.operator]
    for child in node.operands:
        found.extend(collect_operators(child))
    return tuple(found)


def collect_facts(rule: Rule) -> tuple[str, ...]:
    facts = list(rule.applies_to.facts)
    facts.extend(_facts_from_condition(rule.condition))
    ordered: list[str] = []
    seen: set[str] = set()
    for fact in facts:
        if fact not in seen:
            seen.add(fact)
            ordered.append(fact)
    return tuple(ordered)


def _facts_from_condition(node: ConditionNode) -> tuple[str, ...]:
    found: list[str] = []
    # crosses_boundary stores a node-id pattern in fact, not a capability fact.
    if node.fact and node.operator != "crosses_boundary":
        found.append(node.fact)
    for child in node.operands:
        found.extend(_facts_from_condition(child))
    return tuple(found)


def capability_binding_for(rule: Rule) -> CapabilityBinding:
    operators = tuple(sorted(set(collect_operators(rule.condition))))
    facts = collect_facts(rule)
    return CapabilityBinding(operators=operators, facts=facts)


def select_clause_digest(select: SelectClause) -> str:
    return selector_ast_digest_for(
        source=select.source,
        nodes=select.nodes,
        selector_ref=select.selector_ref,
    )


def selector_def_digest(selector: SelectorDef) -> str:
    return selector_ast_digest_for(
        source=selector.source,
        nodes=selector.nodes,
        selector_ref=None,
    )
