"""Pure in-memory RuleSet resolver with pinned composition semantics."""

from __future__ import annotations

from codestrata.application.rules.composition.bounds import composition_budgets
from codestrata.application.rules.composition.catalog import RuleCatalog
from codestrata.application.rules.composition.errors import ResolutionError
from codestrata.application.rules.composition.merge import fold_configuration, overlay_child
from codestrata.application.rules.composition.models import (
    ComposedRuleSet,
    bind_composed,
    selector_ast_digest,
)
from codestrata.domain.contracts.rules import ParentRef, Rule, RuleSet, RuleSetEntry, SelectorDef
from codestrata.domain.contracts.serialization import require_pinned_version


def resolve_ruleset(root: RuleSet, catalog: RuleCatalog) -> ComposedRuleSet:
    max_depth, max_rules, _max_bytes, _max_nesting = composition_budgets()
    composed = _resolve(root, catalog, stack=(), max_depth=max_depth, max_rules=max_rules)
    if len(composed.rules) > max_rules:
        raise ResolutionError(
            "excessive_size",
            f"composed RuleSet exceeds {max_rules} effective rules",
        )
    return composed


def resolve_ruleset_ref(ref: ParentRef, catalog: RuleCatalog) -> ComposedRuleSet:
    return resolve_ruleset(catalog.get_ruleset(ref), catalog)


def _resolve(
    ruleset: RuleSet,
    catalog: RuleCatalog,
    *,
    stack: tuple[str, ...],
    max_depth: int,
    max_rules: int,
) -> ComposedRuleSet:
    if ruleset.digest in stack:
        cycle = " -> ".join((*stack, ruleset.digest))
        raise ResolutionError("cyclic_reference", f"cyclic RuleSet composition: {cycle}")
    depth = len(stack)
    if depth > max_depth:
        raise ResolutionError(
            "excessive_depth",
            f"RuleSet parent depth {depth} exceeds {max_depth}",
        )
    _reject_unpinned_ruleset(ruleset)

    parent_states: list[ComposedRuleSet] = []
    for parent_ref in ruleset.extends:
        parent = catalog.get_ruleset(parent_ref)
        parent_states.append(
            _resolve(
                parent,
                catalog,
                stack=(*stack, ruleset.digest),
                max_depth=max_depth,
                max_rules=max_rules,
            )
        )

    selectors = _merge_selectors(parent_states, ruleset.selectors)
    merged_rules = _merge_rules(parent_states, ruleset, catalog, selectors)
    if len(merged_rules) > max_rules:
        raise ResolutionError(
            "excessive_size",
            f"composed RuleSet exceeds {max_rules} effective rules",
        )
    ordered = tuple(parent_ref for parent_ref in ruleset.extends)
    return bind_composed(
        {
            "ruleset_id": ruleset.metadata.id,
            "ruleset_version": ruleset.metadata.version,
            "root_digest": ruleset.digest,
            "ordered_composition": ordered,
            "selectors": tuple(sorted(selectors.values(), key=lambda item: item.id)),
            "rules": tuple(sorted(merged_rules, key=lambda item: item.rule_id)),
        }
    )


def _reject_unpinned_ruleset(ruleset: RuleSet) -> None:
    require_pinned_version(ruleset.metadata.version, label="ruleset version")
    seen_ids: set[str] = set()
    for entry in ruleset.rules:
        if entry.rule_id in seen_ids:
            raise ResolutionError(
                "duplicate_identity",
                f"RuleSet {ruleset.metadata.id} repeats rule {entry.rule_id}",
            )
        seen_ids.add(entry.rule_id)
        require_pinned_version(entry.revision, label="rule revision")
    for selector in ruleset.selectors:
        if not selector.digest:
            raise ResolutionError("floating_reference", f"selector {selector.id} is not pinned")


def _merge_selectors(
    parents: list[ComposedRuleSet],
    child_selectors: tuple[SelectorDef, ...],
) -> dict[str, SelectorDef]:
    merged: dict[str, SelectorDef] = {}
    for parent in parents:
        for selector in parent.selectors:
            _add_selector(merged, selector)
    for selector in child_selectors:
        _add_selector(merged, selector)
    return merged


def _add_selector(merged: dict[str, SelectorDef], selector: SelectorDef) -> None:
    existing = merged.get(selector.id)
    if existing is None:
        merged[selector.id] = selector
        return
    if selector_ast_digest(existing) == selector_ast_digest(selector):
        return
    raise ResolutionError(
        "selector_conflict",
        f"conflicting selector AST cannot shadow {selector.id}",
    )


def _merge_rules(
    parents: list[ComposedRuleSet],
    child: RuleSet,
    catalog: RuleCatalog,
    selectors: dict[str, SelectorDef],
) -> tuple[RuleSetEntry, ...]:
    layers: dict[str, list[RuleSetEntry]] = {}
    for parent in parents:
        for entry in parent.rules:
            layers.setdefault(entry.rule_id, []).append(entry)

    child_by_id = {entry.rule_id: entry for entry in child.rules}
    result: list[RuleSetEntry] = []
    seen = set(layers) | set(child_by_id)
    for rule_id in sorted(seen):
        parent_entries = tuple(layers.get(rule_id, ()))
        child_entry = child_by_id.get(rule_id)
        votes = {(entry.revision, entry.digest) for entry in parent_entries}
        if len(votes) > 1 and child_entry is None:
            raise ResolutionError(
                "revision_conflict",
                f"parent revision conflict for {rule_id} requires an explicit child pin",
            )
        if child_entry is None:
            folded = fold_configuration(parent_entries)
            _validate_rule(folded, catalog, selectors)
            result.append(folded)
            continue
        if len(votes) > 1:
            matching = tuple(
                entry
                for entry in parent_entries
                if (entry.revision, entry.digest) == (child_entry.revision, child_entry.digest)
            )
            if matching:
                folded = overlay_child(fold_configuration(matching), child_entry)
            else:
                folded = child_entry
        elif parent_entries:
            base = fold_configuration(parent_entries)
            if (child_entry.revision, child_entry.digest) != (base.revision, base.digest):
                folded = overlay_child(base, child_entry)
            else:
                folded = overlay_child(base, child_entry)
        else:
            folded = child_entry
        _validate_rule(folded, catalog, selectors)
        result.append(folded)
    return tuple(result)


def _validate_rule(
    entry: RuleSetEntry,
    catalog: RuleCatalog,
    selectors: dict[str, SelectorDef],
) -> Rule:
    rule = catalog.get_rule(entry.rule_id, entry.revision, entry.digest)
    select = rule.select
    if select.selector_ref is None:
        return rule
    found = selectors.get(select.selector_ref)
    if found is None:
        raise ResolutionError(
            "missing_reference",
            f"rule {entry.rule_id} references missing selector {select.selector_ref}",
        )
    if select.selector_digest != found.digest:
        raise ResolutionError(
            "selector_conflict",
            f"rule {entry.rule_id} selector pin does not match composed selector",
        )
    return rule
