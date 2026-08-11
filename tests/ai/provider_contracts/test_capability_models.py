"""Tests for ``ProviderCapabilityDescriptor``/``ProviderCapabilityProfile``."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.capability_models import (
    ProviderCapabilityDescriptor,
    ProviderCapabilityProfile,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId


def _valid_kwargs() -> dict[str, object]:
    return {
        "provider_id": ProviderId.OPENAI,
        "supported_capability_ids": (CapabilityId.MODERNIZATION_ADVISOR,),
        "supports_structured_json": True,
        "supports_streaming": False,
        "supports_timeout_policy": True,
        "supports_retry_policy": True,
        "reports_usage_metadata": True,
        "reports_token_accounting": True,
    }


def test_descriptor_requires_a_capability_id() -> None:
    descriptor = ProviderCapabilityDescriptor(capability_id=CapabilityId.MODERNIZATION_ADVISOR)
    assert descriptor.capability_id == CapabilityId.MODERNIZATION_ADVISOR
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityDescriptor(capability_id="modernization_advisor")  # type: ignore[arg-type]


def test_profile_accepts_valid_construction() -> None:
    profile = ProviderCapabilityProfile(**_valid_kwargs())
    assert profile.provider_id == ProviderId.OPENAI
    assert profile.schema_version == "1.0"
    assert profile.limitations == ()


def test_profile_is_frozen() -> None:
    profile = ProviderCapabilityProfile(**_valid_kwargs())
    with pytest.raises(AttributeError):
        profile.supports_structured_json = False  # type: ignore[misc]


def test_profile_rejects_non_provider_id() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(**{**_valid_kwargs(), "provider_id": "openai"})


def test_profile_rejects_empty_supported_capability_ids() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(**{**_valid_kwargs(), "supported_capability_ids": ()})


def test_profile_rejects_a_non_capability_id_entry() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(
            **{**_valid_kwargs(), "supported_capability_ids": ("modernization_advisor",)}
        )


def test_profile_rejects_duplicate_capability_ids() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(
            **{
                **_valid_kwargs(),
                "supported_capability_ids": (
                    CapabilityId.MODERNIZATION_ADVISOR,
                    CapabilityId.MODERNIZATION_ADVISOR,
                ),
            }
        )


@pytest.mark.parametrize(
    "flag_name",
    [
        "supports_structured_json",
        "supports_timeout_policy",
        "supports_retry_policy",
        "reports_usage_metadata",
        "reports_token_accounting",
    ],
)
def test_profile_rejects_a_non_bool_feature_flag(flag_name: str) -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(**{**_valid_kwargs(), flag_name: "yes"})


def test_profile_rejects_supports_streaming_true() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(**{**_valid_kwargs(), "supports_streaming": True})


def test_profile_rejects_too_many_limitations() -> None:
    too_many = tuple(f"not_wired_to_runtime{i}" for i in range(17))
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(**{**_valid_kwargs(), "limitations": too_many})


def test_profile_rejects_duplicate_limitations() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(
            **{**_valid_kwargs(), "limitations": ("not_wired_to_runtime", "not_wired_to_runtime")}
        )


def test_profile_rejects_an_unknown_limitation() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(**{**_valid_kwargs(), "limitations": ("made_up",)})


def test_profile_accepts_known_limitations() -> None:
    profile = ProviderCapabilityProfile(
        **{**_valid_kwargs(), "limitations": ("not_wired_to_runtime",)}
    )
    assert profile.limitations == ("not_wired_to_runtime",)


def test_profile_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCapabilityProfile(**{**_valid_kwargs(), "schema_version": "99.0"})


def test_declares_capability_true_and_false() -> None:
    profile = ProviderCapabilityProfile(**_valid_kwargs())
    assert profile.declares_capability(CapabilityId.MODERNIZATION_ADVISOR) is True


def test_descriptors_returns_one_descriptor_per_supported_capability() -> None:
    profile = ProviderCapabilityProfile(**_valid_kwargs())
    descriptors = profile.descriptors()
    assert descriptors == (
        ProviderCapabilityDescriptor(capability_id=CapabilityId.MODERNIZATION_ADVISOR),
    )
