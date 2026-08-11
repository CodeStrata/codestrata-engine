"""Tests for ``execution_compatibility`` statements and version helpers."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution_compatibility import (
    SUPPORTED_EXECUTION_VERSIONS,
    build_execution_compatibility_statements,
    is_supported_execution_version,
    validate_execution_version,
)
from codestrata.ai.provider_contracts.execution_policy import REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


def test_statements_cover_exactly_the_required_requirement_ids() -> None:
    statements = build_execution_compatibility_statements()
    ids = tuple(sorted(s.requirement_id for s in statements))
    assert ids == tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))


def test_every_statement_holds_true() -> None:
    statements = build_execution_compatibility_statements()
    assert all(s.holds for s in statements)


def test_every_statement_has_a_non_empty_explanation() -> None:
    statements = build_execution_compatibility_statements()
    assert all(s.explanation.strip() for s in statements)


def test_supported_execution_versions_is_one_dot_zero() -> None:
    assert SUPPORTED_EXECUTION_VERSIONS == ("1.0",)
    assert is_supported_execution_version("1.0") is True
    assert is_supported_execution_version("99.0") is False


def test_validate_execution_version_accepts_the_current_version() -> None:
    validate_execution_version("1.0")


def test_validate_execution_version_rejects_unsupported_version() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_execution_version("99.0")


def test_validate_execution_version_rejects_malformed_version() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_execution_version("not-a-version")
    with pytest.raises(ProviderContractValidationError):
        validate_execution_version(1.0)  # type: ignore[arg-type]
