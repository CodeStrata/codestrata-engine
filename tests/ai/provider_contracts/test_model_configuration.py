"""Tests for model_configuration's default constants and helpers."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderId
from codestrata.ai.provider_contracts.model_configuration import (
    DEFAULT_MODEL_ID_BY_PROVIDER,
    DEFAULT_PROVIDER_ID_VALUE,
    default_model_id_for_provider,
)


def test_default_provider_id_value_is_bedrock() -> None:
    assert DEFAULT_PROVIDER_ID_VALUE == "bedrock"


def test_default_model_id_by_provider_matches_ground_truth() -> None:
    assert DEFAULT_MODEL_ID_BY_PROVIDER == {
        "bedrock": "amazon.nova-lite-v1:0",
        "openai": "gpt-4o-mini",
    }


def test_default_model_id_for_provider_bedrock() -> None:
    assert default_model_id_for_provider(ProviderId.BEDROCK) == "amazon.nova-lite-v1:0"


def test_default_model_id_for_provider_openai() -> None:
    assert default_model_id_for_provider(ProviderId.OPENAI) == "gpt-4o-mini"


def test_default_model_id_by_provider_is_a_copy_not_the_policy_dict() -> None:
    """Mutating the module-level constant must not corrupt the policy source of truth."""

    from codestrata.ai.provider_contracts.configuration_policy import DEFAULT_MODEL_BY_PROVIDER

    DEFAULT_MODEL_ID_BY_PROVIDER["bedrock"] = "mutated"
    assert DEFAULT_MODEL_BY_PROVIDER["bedrock"] == "amazon.nova-lite-v1:0"
    DEFAULT_MODEL_ID_BY_PROVIDER["bedrock"] = "amazon.nova-lite-v1:0"


def test_default_model_id_for_provider_rejects_non_provider_id() -> None:
    with pytest.raises((ProviderContractValidationError, AttributeError, TypeError)):
        default_model_id_for_provider("bedrock")  # type: ignore[arg-type]
