"""Parse Platform-resolved override bundles. No fetch or approval lookup."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from codestrata.application.rules.composition.errors import ResolutionError
from codestrata.application.rules.composition.loader import load_document_bytes
from codestrata.application.rules.overrides.authority import assert_engine_local_payload
from codestrata.application.rules.overrides.errors import OverrideError
from codestrata.application.rules.overrides.models import PolicyOverrideBundle
from codestrata.application.rules.overrides.presentation import (
    PRESENTATION_FIELDS,
    presentation_from_mapping,
)

LOGIC_CHANGE_FIELDS = frozenset(
    {
        "select",
        "selector",
        "selector_ref",
        "selector_digest",
        "condition",
        "operator",
        "parameter_schema",
        "applies_to",
        "evidence_include",
        "metric",
        "nodes",
        "operands",
        "edge_types",
        "traversal",
        "max_depth",
        "dependency_view",
        "source",
    }
)


def load_override_bundle(raw: bytes, *, label: str = "overrides") -> PolicyOverrideBundle:
    try:
        document = load_document_bytes(raw, label=label)
    except ResolutionError as error:
        raise OverrideError(error.code, str(error)) from error
    return parse_override_bundle(document)


def parse_override_bundle(document: dict[str, Any]) -> PolicyOverrideBundle:
    assert_engine_local_payload(document)
    _reject_logic_change(document, path="$")
    try:
        return PolicyOverrideBundle.model_validate(document)
    except ValidationError as error:
        _reraise_validation(error)
        raise
    except ValueError as error:
        if isinstance(error, OverrideError):
            raise
        raise OverrideError("invalid_document", str(error)) from error


def _reject_logic_change(payload: object, *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in LOGIC_CHANGE_FIELDS and key not in PRESENTATION_FIELDS:
                raise OverrideError(
                    "logic_change_requires_revision",
                    f"selector/schema/operator field {key!r} at {path} "
                    "requires a new Rule revision",
                )
            child = f"{path}.{key}"
            if key == "parameters":
                continue
            if key == "presentation" and isinstance(value, dict):
                presentation_from_mapping(value)
                continue
            _reject_logic_change(value, path=child)
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            _reject_logic_change(item, path=f"{path}[{index}]")


def _reraise_validation(error: ValidationError) -> None:
    text = str(error)
    lowered = text.lower()
    if "off_is_not_severity" in lowered or "off is never a severity" in lowered:
        raise OverrideError("off_is_not_severity", text) from error
    if "logic_change" in lowered:
        raise OverrideError("logic_change_requires_revision", text) from error
    if "forbidden_authority" in lowered:
        raise OverrideError("forbidden_authority", text) from error
    if "executable_message" in lowered:
        raise OverrideError("executable_message", text) from error
    if "out_of_range" in lowered:
        raise OverrideError("out_of_range_parameter", text) from error
    if "excessive_size" in lowered:
        raise OverrideError("excessive_size", text) from error
    if "invalid_scope" in lowered:
        raise OverrideError("invalid_scope", text) from error
    extra = error.errors()
    for item in extra:
        loc = ".".join(str(part) for part in item.get("loc", ()))
        if item.get("type") == "extra_forbidden":
            field = str(item.get("loc", ("unknown",))[-1])
            if field in LOGIC_CHANGE_FIELDS:
                raise OverrideError(
                    "logic_change_requires_revision",
                    f"selector/schema/operator field {field!r} at {loc} "
                    "requires a new Rule revision",
                ) from error
            raise OverrideError("unknown_field", f"unknown field {field!r} at {loc}") from error
    raise OverrideError("invalid_document", text) from error
