"""Tests for SourceCategory / FieldSource."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.configuration_sources import FieldSource, SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError


def test_source_category_values() -> None:
    assert {s.value for s in SourceCategory} == {
        "cli",
        "environment",
        "configuration_file",
        "default",
    }


def test_field_source_construction() -> None:
    source = FieldSource("model_reference", SourceCategory.CLI)
    assert source.field_name == "model_reference"
    assert source.source_category is SourceCategory.CLI


def test_field_source_rejects_blank_field_name() -> None:
    with pytest.raises(ProviderContractValidationError):
        FieldSource("", SourceCategory.DEFAULT)


def test_field_source_rejects_non_source_category() -> None:
    with pytest.raises(ProviderContractValidationError):
        FieldSource("model_reference", "cli")  # type: ignore[arg-type]


def test_field_source_never_carries_a_resolved_value() -> None:
    """Structural check: FieldSource has exactly field_name/source_category."""

    fields = {f.name for f in FieldSource.__dataclass_fields__.values()}
    assert fields == {"field_name", "source_category"}
