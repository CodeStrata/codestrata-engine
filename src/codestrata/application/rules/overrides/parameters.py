"""Validate policy/exception parameters against the pinned Rule schema."""

from __future__ import annotations

from codestrata.application.rules.composition.merge import merge_parameters
from codestrata.application.rules.overrides.errors import OverrideError
from codestrata.domain.contracts.rules import ParameterField, Rule

Scalar = str | int | float | bool


def merge_and_validate_parameters(
    rule: Rule,
    base: dict[str, Scalar],
    overlay: dict[str, Scalar],
) -> dict[str, Scalar]:
    schema = {field.name: field for field in rule.parameter_schema}
    for key in overlay:
        if key not in schema:
            raise OverrideError(
                "unknown_parameter",
                f"parameter {key!r} is not exposed by {rule.metadata.id}@{rule.metadata.version}",
            )
    merged = merge_parameters(base, overlay)
    if schema:
        for key, value in merged.items():
            field = schema.get(key)
            if field is None:
                raise OverrideError(
                    "unknown_parameter",
                    f"parameter {key!r} is not in the pinned parameter schema",
                )
            _assert_in_range(field, value, rule_id=rule.metadata.id)
    elif merged and overlay:
        raise OverrideError(
            "unknown_parameter",
            f"{rule.metadata.id} exposes no parameters",
        )
    return merged


def _assert_in_range(field: ParameterField, value: Scalar, *, rule_id: str) -> None:
    expected = field.value_type.lower()
    if expected in {"integer", "int"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise OverrideError(
                "out_of_range_parameter",
                f"{rule_id}.{field.name} requires an integer",
            )
        number = float(value)
    elif expected in {"number", "float"}:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise OverrideError(
                "out_of_range_parameter",
                f"{rule_id}.{field.name} requires a number",
            )
        number = float(value)
    elif expected in {"boolean", "bool"}:
        if not isinstance(value, bool):
            raise OverrideError(
                "out_of_range_parameter",
                f"{rule_id}.{field.name} requires a boolean",
            )
        return
    elif expected in {"string", "str"}:
        if not isinstance(value, str):
            raise OverrideError(
                "out_of_range_parameter",
                f"{rule_id}.{field.name} requires a string",
            )
        if len(value) > 1024:
            raise OverrideError(
                "out_of_range_parameter",
                f"{rule_id}.{field.name} exceeds 1024 characters",
            )
        return
    else:
        raise OverrideError(
            "unknown_parameter",
            f"unsupported parameter type {field.value_type!r} on {rule_id}.{field.name}",
        )
    if field.minimum is not None and number < field.minimum:
        raise OverrideError(
            "out_of_range_parameter",
            f"{rule_id}.{field.name}={value!r} is below minimum {field.minimum}",
        )
    if field.maximum is not None and number > field.maximum:
        raise OverrideError(
            "out_of_range_parameter",
            f"{rule_id}.{field.name}={value!r} is above maximum {field.maximum}",
        )
