"""Tests for ``TimeoutPolicy``/``TimeoutScope``."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.timeout_policy import (
    DEFAULT_TIMEOUT_POLICY,
    TimeoutPolicy,
    TimeoutScope,
)


def test_default_timeout_policy_is_sixty_seconds_provider_request_enabled() -> None:
    assert DEFAULT_TIMEOUT_POLICY.timeout_seconds == 60.0
    assert DEFAULT_TIMEOUT_POLICY.scope is TimeoutScope.PROVIDER_REQUEST
    assert DEFAULT_TIMEOUT_POLICY.enabled is True
    assert DEFAULT_TIMEOUT_POLICY.source_category is None


def test_timeout_policy_accepts_total_execution_scope() -> None:
    policy = TimeoutPolicy(timeout_seconds=30.0, scope=TimeoutScope.TOTAL_EXECUTION)
    assert policy.scope is TimeoutScope.TOTAL_EXECUTION


def test_timeout_policy_accepts_a_source_category() -> None:
    policy = TimeoutPolicy(source_category=SourceCategory.CONFIGURATION_FILE)
    assert policy.source_category is SourceCategory.CONFIGURATION_FILE


@pytest.mark.parametrize("bad_value", [0, -1.0, 3600.1, float("inf"), float("nan")])
def test_timeout_policy_rejects_out_of_bounds_or_non_finite_timeout(bad_value: float) -> None:
    with pytest.raises(ProviderContractValidationError):
        TimeoutPolicy(timeout_seconds=bad_value)


def test_timeout_policy_accepts_the_upper_bound() -> None:
    TimeoutPolicy(timeout_seconds=3600.0)


def test_timeout_policy_rejects_non_numeric_timeout() -> None:
    with pytest.raises(ProviderContractValidationError):
        TimeoutPolicy(timeout_seconds="60")  # type: ignore[arg-type]


def test_timeout_policy_rejects_bool_timeout() -> None:
    with pytest.raises(ProviderContractValidationError):
        TimeoutPolicy(timeout_seconds=True)  # type: ignore[arg-type]


def test_timeout_policy_rejects_invalid_scope() -> None:
    with pytest.raises(ProviderContractValidationError):
        TimeoutPolicy(scope="provider_request")  # type: ignore[arg-type]


def test_timeout_policy_rejects_invalid_source_category() -> None:
    with pytest.raises(ProviderContractValidationError):
        TimeoutPolicy(source_category="cli")  # type: ignore[arg-type]


def test_timeout_policy_rejects_non_bool_enabled() -> None:
    with pytest.raises(ProviderContractValidationError):
        TimeoutPolicy(enabled="yes")  # type: ignore[arg-type]


def test_timeout_policy_is_frozen() -> None:
    policy = TimeoutPolicy()
    with pytest.raises(AttributeError):
        policy.timeout_seconds = 10.0  # type: ignore[misc]
