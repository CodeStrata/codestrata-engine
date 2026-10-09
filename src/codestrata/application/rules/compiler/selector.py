"""Compile select mappings into typed selector ASTs with pinned digests."""

from __future__ import annotations

from typing import Any

from codestrata.domain.contracts.rules import SelectClause, SelectorDef
from codestrata.domain.rules.compiler_errors import YamlCompileError
from codestrata.domain.rules.compiler_models import (
    SELECTOR_COMBINATORS,
    SELECTOR_PREDICATE_KEYS,
    SelectorAst,
    SelectorPredicate,
    select_clause_digest,
    selector_def_digest,
)


def compile_select_clause(select: SelectClause) -> SelectorAst:
    if select.selector_ref:
        if select.selector_digest is None:
            raise YamlCompileError(
                "selector_ref requires a pinned selector_digest",
                reason_code="unpinned_selector",
            )
        return SelectorAst(
            source=select.source,
            selector_ref=select.selector_ref,
            digest=select.selector_digest,
            nodes=dict(select.nodes or {}),
        )
    return _compile_nodes(
        source=select.source,
        nodes=select.nodes or {},
        selector_ref=None,
        digest=select_clause_digest(select),
    )


def compile_selector_def(selector: SelectorDef) -> SelectorAst:
    ast = _compile_nodes(
        source=selector.source,
        nodes=selector.nodes,
        selector_ref=None,
        digest=selector_def_digest(selector),
    )
    expected = ast.digest
    if selector.digest != expected:
        raise YamlCompileError(
            f"selector {selector.id} digest does not match AST",
            reason_code="selector_digest_mismatch",
            details={"selector_id": selector.id, "expected": expected},
        )
    return ast


def _compile_nodes(
    *,
    source: str | None,
    nodes: dict[str, Any],
    selector_ref: str | None,
    digest: str,
) -> SelectorAst:
    if not nodes:
        return SelectorAst(
            source=source,
            selector_ref=selector_ref,
            digest=digest,
            nodes={},
        )
    unknown = set(nodes) - SELECTOR_COMBINATORS
    if unknown:
        raise YamlCompileError(
            f"unknown selector fields {sorted(unknown)}",
            reason_code="unknown_field",
            details={"fields": sorted(unknown)},
        )
    if len(nodes) != 1:
        raise YamlCompileError(
            "selector nodes must use exactly one combinator",
            reason_code="invalid_selector",
        )
    combinator, body = next(iter(nodes.items()))
    predicates = _predicates_from(body, combinator=combinator)
    return SelectorAst(
        source=source,
        selector_ref=selector_ref,
        combinator=combinator,
        predicates=predicates,
        nodes=dict(nodes),
        digest=digest,
    )


def _predicates_from(body: object, *, combinator: str) -> tuple[SelectorPredicate, ...]:
    if combinator == "not":
        items = [body] if isinstance(body, dict) else body
    else:
        items = body
    if not isinstance(items, list):
        raise YamlCompileError(
            f"selector combinator {combinator} requires a list of predicates",
            reason_code="invalid_selector",
        )
    predicates: list[SelectorPredicate] = []
    for item in items:
        if not isinstance(item, dict):
            raise YamlCompileError(
                "selector predicate must be a mapping",
                reason_code="invalid_selector",
            )
        extra = set(item) - SELECTOR_PREDICATE_KEYS
        if extra:
            raise YamlCompileError(
                f"unknown selector predicate fields {sorted(extra)}",
                reason_code="unknown_field",
                details={"fields": sorted(extra)},
            )
        try:
            predicates.append(SelectorPredicate.model_validate(item))
        except ValueError as error:
            raise YamlCompileError(
                str(error),
                reason_code="invalid_selector",
            ) from error
    return tuple(predicates)
