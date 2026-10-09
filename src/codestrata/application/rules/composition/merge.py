"""Deterministic map/list merge for RuleSet configuration fields."""

from __future__ import annotations

from typing import Any

from codestrata.domain.contracts.rules import RuleSetEntry


def merge_defined_fields(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge maps by defined fields. Lists/scalars replace. Null does not reset."""

    merged = dict(base)
    for key, value in overlay.items():
        if value is None:
            continue
        current = merged.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            merged[key] = merge_defined_fields(current, value)
        else:
            merged[key] = value
    return merged


def merge_parameters(
    base: dict[str, str | int | float | bool],
    overlay: dict[str, str | int | float | bool],
) -> dict[str, str | int | float | bool]:
    merged = merge_defined_fields(dict(base), dict(overlay))
    return {str(key): _require_scalar(value) for key, value in merged.items()}


def fold_configuration(entries: tuple[RuleSetEntry, ...]) -> RuleSetEntry:
    """Later complete entries override earlier scalars; parameter maps merge."""

    if not entries:
        raise ValueError("fold_configuration requires at least one entry")
    head = entries[0]
    parameters = dict(head.parameters)
    default_enabled = head.default_enabled
    adoption = head.adoption
    severity = head.severity_override
    revision = head.revision
    digest = head.digest
    rule_id = head.rule_id
    for entry in entries[1:]:
        if entry.rule_id != rule_id:
            raise ValueError("cannot fold configuration across different rule ids")
        if (entry.revision, entry.digest) != (revision, digest):
            raise ValueError("cannot fold configuration across different revisions")
        parameters = merge_parameters(parameters, dict(entry.parameters))
        default_enabled = entry.default_enabled
        adoption = entry.adoption
        if entry.severity_override is not None:
            severity = entry.severity_override
    return RuleSetEntry(
        rule_id=rule_id,
        revision=revision,
        digest=digest,
        default_enabled=default_enabled,
        adoption=adoption,
        parameters=parameters,
        severity_override=severity,
    )


def overlay_child(base: RuleSetEntry, child: RuleSetEntry) -> RuleSetEntry:
    """Child pin may change revision; configuration still merges onto the chosen pin."""

    parameters = merge_parameters(dict(base.parameters), dict(child.parameters))
    severity = (
        base.severity_override if child.severity_override is None else child.severity_override
    )
    return RuleSetEntry(
        rule_id=child.rule_id,
        revision=child.revision,
        digest=child.digest,
        default_enabled=child.default_enabled,
        adoption=child.adoption,
        parameters=parameters,
        severity_override=severity,
    )


def _require_scalar(value: object) -> str | int | float | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float | str):
        return value
    raise TypeError(f"parameter values must be scalars, not {type(value).__name__}")
