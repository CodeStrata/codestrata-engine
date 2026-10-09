"""Compile Rule/RuleSet YAML into a sealed contract and intermediate plan."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from codestrata.application.rules.compiler.loader import load_rule_document
from codestrata.application.rules.compiler.selector import (
    compile_select_clause,
    compile_selector_def,
)
from codestrata.domain.contracts.rules import (
    BOUNDED_OPERATORS,
    CAPABILITY_VERSION,
    ContractError,
    Rule,
    RuleSet,
    bind_digest,
    parse_rule,
    parse_ruleset,
)
from codestrata.domain.contracts.serialization import digest_canonical, omit_key
from codestrata.domain.rules.compiler_errors import CapabilityError, YamlCompileError
from codestrata.domain.rules.compiler_models import (
    COMPILER_VERSION,
    PLAN_SCHEMA,
    PLAN_SCHEMA_VERSION,
    SUPPORTED_FACTS,
    CapabilityBinding,
    CompilationPlan,
    SelectorAst,
    capability_binding_for,
    condition_plan_from,
    disallowed_operators,
    presentation_digest_for,
    selector_ast_digest_for,
)


def compile_rule_yaml(raw: bytes, *, label: str = "rule.yaml") -> CompilationPlan:
    document, source_digest = load_rule_document(raw, label=label)
    return compile_rule_mapping(document, source_digest=source_digest)


def compile_ruleset_yaml(raw: bytes, *, label: str = "ruleset.yaml") -> CompilationPlan:
    document, source_digest = load_rule_document(raw, label=label)
    return compile_ruleset_mapping(document, source_digest=source_digest)


def compile_yaml(raw: bytes, *, label: str = "document.yaml") -> CompilationPlan:
    document, source_digest = load_rule_document(raw, label=label)
    kind = str(document.get("kind") or "")
    if kind == "RuleSet":
        return compile_ruleset_mapping(document, source_digest=source_digest)
    if kind == "Rule":
        return compile_rule_mapping(document, source_digest=source_digest)
    raise YamlCompileError(
        "document kind must be Rule or RuleSet",
        reason_code="unknown_field",
        details={"kind": kind},
    )


def compile_rule_mapping(
    document: dict[str, Any],
    *,
    source_digest: str | None = None,
) -> CompilationPlan:
    _reject_unknown_top_level(document, expected=_RULE_FIELDS)
    _classify_condition_operators(document.get("condition"), rule_id=_rule_id_of(document))
    _classify_facts(document, rule_id=_rule_id_of(document))
    rule = _bind_rule(document)
    selector_ast = compile_select_clause(rule.select)
    selector_digest = selector_ast.digest
    presentation = presentation_digest_for(rule)
    capabilities = capability_binding_for(rule)
    plan_body = _plan_identity(
        kind="Rule",
        source_digest=source_digest or digest_canonical(document),
        document_digest=rule.digest,
        selector_digest=selector_digest,
        presentation_digest=presentation,
        capabilities=capabilities,
    )
    return CompilationPlan(
        schema_name=PLAN_SCHEMA,
        schema_version=PLAN_SCHEMA_VERSION,
        compiler_version=COMPILER_VERSION,
        kind="Rule",
        source_digest=plan_body["source_digest"],
        document_digest=rule.digest,
        selector_digest=selector_digest,
        presentation_digest=presentation,
        plan_digest=digest_canonical(plan_body),
        selector_ast=selector_ast,
        condition=condition_plan_from(rule.condition),
        capabilities=capabilities,
        rule=rule,
    )


def compile_ruleset_mapping(
    document: dict[str, Any],
    *,
    source_digest: str | None = None,
) -> CompilationPlan:
    _reject_unknown_top_level(document, expected=_RULESET_FIELDS)
    ruleset = _bind_ruleset(document)
    selector_asts: list[SelectorAst] = []
    for selector in ruleset.selectors:
        selector_asts.append(compile_selector_def(selector))
    selector_digest = digest_canonical(
        [
            {"digest": ast.digest, "id": item.id}
            for item, ast in zip(ruleset.selectors, selector_asts, strict=True)
        ]
    )
    presentation = digest_canonical(
        {
            "owner": ruleset.metadata.owner,
            "title": ruleset.metadata.title,
        }
    )
    capabilities = CapabilityBinding()
    plan_body = _plan_identity(
        kind="RuleSet",
        source_digest=source_digest or digest_canonical(document),
        document_digest=ruleset.digest,
        selector_digest=selector_digest,
        presentation_digest=presentation,
        capabilities=capabilities,
    )
    return CompilationPlan(
        schema_name=PLAN_SCHEMA,
        schema_version=PLAN_SCHEMA_VERSION,
        compiler_version=COMPILER_VERSION,
        kind="RuleSet",
        source_digest=plan_body["source_digest"],
        document_digest=ruleset.digest,
        selector_digest=selector_digest,
        presentation_digest=presentation,
        plan_digest=digest_canonical(plan_body),
        selectors=tuple(selector_asts),
        capabilities=capabilities,
        ruleset=ruleset,
    )


_RULE_FIELDS = frozenset(
    {
        "schema_name",
        "schema_version",
        "api_version",
        "kind",
        "metadata",
        "digest",
        "applies_to",
        "select",
        "condition",
        "finding",
        "metric",
        "evidence_include",
        "parameter_schema",
    }
)
_RULESET_FIELDS = frozenset(
    {
        "schema_name",
        "schema_version",
        "api_version",
        "kind",
        "metadata",
        "digest",
        "extends",
        "selectors",
        "rules",
    }
)


def _reject_unknown_top_level(document: dict[str, Any], *, expected: frozenset[str]) -> None:
    extra = sorted(set(document) - expected)
    if extra:
        raise YamlCompileError(
            f"unknown fields rejected: {extra}",
            reason_code="unknown_field",
            details={"fields": extra},
        )


def _bind_rule(document: dict[str, Any]) -> Rule:
    payload = dict(document)
    payload.setdefault("kind", "Rule")
    try:
        if payload.get("digest"):
            return parse_rule(payload)
        return bind_digest(Rule, omit_key(payload, "digest"))
    except (ContractError, ValidationError, ValueError) as error:
        raise YamlCompileError(str(error), reason_code="schema") from error


def _bind_ruleset(document: dict[str, Any]) -> RuleSet:
    payload = dict(document)
    payload.setdefault("kind", "RuleSet")
    selectors = payload.get("selectors")
    if isinstance(selectors, list):
        pinned: list[Any] = []
        for item in selectors:
            if not isinstance(item, dict):
                raise YamlCompileError(
                    "selector definition must be a mapping",
                    reason_code="invalid_type",
                )
            pinned.append(_pin_selector_def(item))
        payload["selectors"] = pinned
    try:
        if payload.get("digest"):
            return parse_ruleset(payload)
        return bind_digest(RuleSet, omit_key(payload, "digest"))
    except (ContractError, ValidationError, ValueError) as error:
        raise YamlCompileError(str(error), reason_code="schema") from error


def _pin_selector_def(item: dict[str, Any]) -> dict[str, Any]:
    extra = set(item) - {"id", "source", "nodes", "digest"}
    if extra:
        raise YamlCompileError(
            f"unknown fields rejected: {sorted(extra)}",
            reason_code="unknown_field",
            details={"fields": sorted(extra)},
        )
    expected = selector_ast_digest_for(
        source=item.get("source") if isinstance(item.get("source"), str) else None,
        nodes=item.get("nodes") if isinstance(item.get("nodes"), dict) else {},
    )
    current = item.get("digest")
    if current in (None, ""):
        bound = dict(item)
        bound["digest"] = expected
        return bound
    if current != expected:
        raise YamlCompileError(
            "selector digest does not match AST",
            reason_code="selector_digest_mismatch",
            details={"expected": expected},
        )
    return item


def _rule_id_of(document: dict[str, Any]) -> str | None:
    metadata = document.get("metadata")
    if isinstance(metadata, dict):
        identifier = metadata.get("id")
        if isinstance(identifier, str):
            return identifier
    return None


def _classify_condition_operators(node: object, *, rule_id: str | None) -> None:
    if node is None:
        raise YamlCompileError("condition is required", reason_code="schema", rule_id=rule_id)
    for operator in _raw_operators(node):
        if operator in disallowed_operators():
            raise YamlCompileError(
                f"disallowed operator {operator}",
                reason_code="disallowed_operator",
                rule_id=rule_id,
                details={"operator": operator},
            )
        if operator not in BOUNDED_OPERATORS:
            raise CapabilityError(
                f"unsupported operator {operator}",
                reason_code="unsupported_operator",
                capability_kind="operator",
                token=operator,
                supported=tuple(sorted(BOUNDED_OPERATORS)),
                capability_version=CAPABILITY_VERSION,
                rule_id=rule_id,
            )


def _raw_operators(node: object) -> tuple[str, ...]:
    if not isinstance(node, dict):
        raise YamlCompileError("condition must be a mapping", reason_code="invalid_type")
    operator = node.get("operator")
    found: list[str] = []
    if isinstance(operator, str) and operator.strip():
        found.append(operator.strip().lower())
    operands = node.get("operands") or ()
    if operands in (None, ()):
        return tuple(found)
    if not isinstance(operands, list):
        raise YamlCompileError("condition operands must be a list", reason_code="invalid_type")
    for child in operands:
        found.extend(_raw_operators(child))
    return tuple(found)


def _classify_facts(document: dict[str, Any], *, rule_id: str | None) -> None:
    applies = document.get("applies_to")
    facts: list[object] = []
    if isinstance(applies, dict):
        listed = applies.get("facts") or ()
        if isinstance(listed, list):
            facts.extend(listed)
    condition = document.get("condition")
    if isinstance(condition, dict) and condition.get("fact") is not None:
        operator = str(condition.get("operator") or "").strip().lower()
        # fact on crosses_boundary is the source node pattern, not a fact id.
        if operator != "crosses_boundary":
            facts.append(condition.get("fact"))
    for fact in facts:
        token = str(fact)
        if token not in SUPPORTED_FACTS:
            raise CapabilityError(
                f"unsupported fact {token}",
                reason_code="unsupported_fact",
                capability_kind="fact",
                token=token,
                supported=tuple(sorted(SUPPORTED_FACTS)),
                capability_version=CAPABILITY_VERSION,
                rule_id=rule_id,
            )


def _plan_identity(
    *,
    kind: str,
    source_digest: str,
    document_digest: str,
    selector_digest: str,
    presentation_digest: str,
    capabilities: CapabilityBinding,
) -> dict[str, Any]:
    return {
        "capabilities": capabilities.model_dump(mode="json"),
        "compiler_version": COMPILER_VERSION,
        "document_digest": document_digest,
        "kind": kind,
        "presentation_digest": presentation_digest,
        "schema_name": PLAN_SCHEMA,
        "schema_version": PLAN_SCHEMA_VERSION,
        "selector_digest": selector_digest,
        "source_digest": source_digest,
    }
