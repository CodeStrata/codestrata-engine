"""Allowlisted presentation overlays. Executable messages are rejected."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from codestrata.application.rules.overrides.errors import OverrideError
from codestrata.domain.contracts.rules import MessageBinding
from codestrata.domain.graph.validation import as_tuple, require_nonblank

EXECUTABLE_MARKERS = (
    "eval(",
    "exec(",
    "compile(",
    "__import__",
    "os.system",
    "subprocess",
    "popen(",
    "/bin/sh",
    "/bin/bash",
    "powershell",
    "cmd.exe",
    "import os",
    "import sys",
    "!!python",
    "!expr",
    "!shell",
    "javascript:",
    "{{%",
    "{%",
    "${",
)

_HTTPS_URL = re.compile(r"^https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$")
PRESENTATION_FIELDS = frozenset(
    {"message_template", "documentation_url", "bindings", "remediation_template"}
)


class PresentationFields(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    message_template: str
    documentation_url: str | None = None
    bindings: tuple[MessageBinding, ...] = ()
    remediation_template: str | None = None

    @field_validator("message_template", "remediation_template", mode="before")
    @classmethod
    def safe_message(cls, value: object) -> object:
        if value is None:
            return None
        return reject_executable_message(value, label="presentation message")

    @field_validator("documentation_url", mode="before")
    @classmethod
    def stable_url(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_documentation_url(value)

    @field_validator("bindings", mode="before")
    @classmethod
    def normalize_bindings(cls, value: object) -> tuple[MessageBinding, ...]:
        items = []
        for item in as_tuple(value):
            if isinstance(item, MessageBinding):
                items.append(item)
            elif isinstance(item, dict):
                items.append(MessageBinding.model_validate(item))
            else:
                raise OverrideError("invalid_presentation", "bindings must be objects")
        return tuple(items)


class PresentationOverlay(BaseModel):
    """Omitted fields inherit. Null does not reset a parent presentation value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    message_template: str | None = None
    documentation_url: str | None = None
    bindings: tuple[MessageBinding, ...] | None = None
    remediation_template: str | None = None

    @field_validator("message_template", "remediation_template", mode="before")
    @classmethod
    def safe_optional_message(cls, value: object) -> object:
        if value is None:
            return None
        return reject_executable_message(value, label="presentation message")

    @field_validator("documentation_url", mode="before")
    @classmethod
    def optional_url(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_documentation_url(value)

    @field_validator("bindings", mode="before")
    @classmethod
    def optional_bindings(cls, value: object) -> tuple[MessageBinding, ...] | None:
        if value is None:
            return None
        items = []
        for item in as_tuple(value):
            if isinstance(item, MessageBinding):
                items.append(item)
            elif isinstance(item, dict):
                items.append(MessageBinding.model_validate(item))
            else:
                raise OverrideError("invalid_presentation", "bindings must be objects")
        return tuple(items)

    @model_validator(mode="after")
    def at_least_one(self) -> PresentationOverlay:
        if (
            self.message_template is None
            and self.documentation_url is None
            and self.bindings is None
            and self.remediation_template is None
        ):
            raise OverrideError("invalid_presentation", "presentation overlay is empty")
        return self


def reject_executable_message(value: object, *, label: str) -> str:
    text = require_nonblank(str(value), label=label)
    lowered = text.lower()
    if "(" in text or "|" in text or "lambda" in lowered:
        raise OverrideError(
            "executable_message",
            f"{label} cannot contain expressions, filters or calls",
        )
    for marker in EXECUTABLE_MARKERS:
        if marker in lowered:
            raise OverrideError(
                "executable_message",
                f"{label} contains executable marker {marker!r}",
            )
    return text


def require_documentation_url(value: object) -> str:
    text = require_nonblank(str(value), label="documentation_url")
    if not _HTTPS_URL.fullmatch(text) or "javascript:" in text.lower():
        raise OverrideError(
            "invalid_presentation",
            "documentation_url must be a stable https URL",
        )
    return text


def merge_presentation(
    base: PresentationFields,
    overlay: PresentationOverlay | None,
) -> PresentationFields:
    if overlay is None:
        return base
    return PresentationFields(
        message_template=(
            base.message_template if overlay.message_template is None else overlay.message_template
        ),
        documentation_url=(
            base.documentation_url
            if overlay.documentation_url is None
            else overlay.documentation_url
        ),
        bindings=base.bindings if overlay.bindings is None else overlay.bindings,
        remediation_template=(
            base.remediation_template
            if overlay.remediation_template is None
            else overlay.remediation_template
        ),
    )


def presentation_from_mapping(payload: dict[str, Any]) -> PresentationOverlay:
    unknown = set(payload) - PRESENTATION_FIELDS
    if unknown:
        raise OverrideError(
            "unknown_presentation_field",
            f"presentation fields not allowlisted: {sorted(unknown)}",
        )
    try:
        return PresentationOverlay.model_validate(payload)
    except ValidationError as error:
        text = str(error)
        if "executable_message" in text.lower() or "expressions" in text.lower():
            raise OverrideError("executable_message", text) from error
        raise OverrideError("invalid_presentation", text) from error
