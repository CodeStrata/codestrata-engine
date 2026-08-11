"""Tests for configuration_compatibility: version helpers and CR statements."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.configuration_compatibility import (
    SUPPORTED_CONFIGURATION_VERSIONS,
    build_configuration_compatibility_statements,
    is_supported_configuration_version,
    validate_configuration_version,
)
from codestrata.ai.provider_contracts.configuration_policy import (
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError


def test_supported_configuration_versions_is_1_0() -> None:
    assert SUPPORTED_CONFIGURATION_VERSIONS == ("1.0",)


def test_is_supported_configuration_version() -> None:
    assert is_supported_configuration_version("1.0") is True
    assert is_supported_configuration_version("99.0") is False


def test_validate_configuration_version_accepts_supported() -> None:
    validate_configuration_version("1.0")


def test_validate_configuration_version_rejects_malformed() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_configuration_version("not-a-version")


def test_validate_configuration_version_rejects_unsupported() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_configuration_version("2.0")


def test_compatibility_statements_cover_exactly_cr1_through_cr6() -> None:
    statements = build_configuration_compatibility_statements()
    ids = tuple(sorted(s.requirement_id for s in statements))
    assert ids == tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))


def test_every_compatibility_statement_holds() -> None:
    statements = build_configuration_compatibility_statements()
    assert all(s.holds for s in statements)


def test_every_compatibility_statement_has_a_non_empty_explanation() -> None:
    statements = build_configuration_compatibility_statements()
    assert all(s.explanation.strip() for s in statements)
