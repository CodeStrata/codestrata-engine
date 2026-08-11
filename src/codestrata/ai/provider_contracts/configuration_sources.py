"""Where a resolved configuration value came from.

``SourceCategory`` is the closed set of places a configuration value for
``codestrata assess`` can come from today: an explicit CLI flag, a process
environment variable, the ``codestrata.toml`` configuration file, or a
hardcoded default. ``FieldSource`` pairs a field name with the category that
supplied its value — a small, privacy-safe provenance record. Neither type
ever carries the resolved *value* itself, only where it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from codestrata.ai.provider_contracts.configuration_policy import ALLOWED_SOURCE_CATEGORIES
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

_MAX_FIELD_NAME_LENGTH = 80


class SourceCategory(StrEnum):
    """The closed set of places a resolved configuration value can come from."""

    CLI = "cli"
    ENVIRONMENT = "environment"
    CONFIGURATION_FILE = "configuration_file"
    DEFAULT = "default"


assert tuple(s.value for s in SourceCategory) == ALLOWED_SOURCE_CATEGORIES, (
    "SourceCategory enum values must exactly match configuration_policy.ALLOWED_SOURCE_CATEGORIES"
)


@dataclass(frozen=True, slots=True)
class FieldSource:
    """Records which :class:`SourceCategory` supplied a named field's value.

    Never carries the resolved value itself — only the field name and the
    category of thing that supplied it (e.g. ``field_name="model_reference",
    source_category=SourceCategory.ENVIRONMENT``).
    """

    field_name: str
    source_category: SourceCategory

    def __post_init__(self) -> None:
        if not isinstance(self.field_name, str) or not self.field_name.strip():
            raise ProviderContractValidationError(
                "FieldSource.field_name must be a non-empty string"
            )
        if len(self.field_name) > _MAX_FIELD_NAME_LENGTH:
            raise ProviderContractValidationError(
                f"FieldSource.field_name must be at most {_MAX_FIELD_NAME_LENGTH} characters"
            )
        if not isinstance(self.source_category, SourceCategory):
            raise ProviderContractValidationError(
                "FieldSource.source_category must be a SourceCategory, got "
                f"{type(self.source_category).__name__}"
            )


__all__ = [
    "FieldSource",
    "SourceCategory",
]
