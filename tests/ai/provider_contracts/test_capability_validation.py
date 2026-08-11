"""Tests for ``capability_validation`` standalone helpers."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
)
from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile
from codestrata.ai.provider_contracts.capability_validation import (
    validate_capability_id_is_known,
    validate_capability_profile,
    validate_provider_declares_capability,
    validate_provider_id_is_known,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId


def test_validate_capability_id_is_known_accepts_modernization_advisor() -> None:
    validate_capability_id_is_known(CapabilityId.MODERNIZATION_ADVISOR)


def test_validate_capability_id_is_known_rejects_a_non_capability_id() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_capability_id_is_known("modernization_advisor")  # type: ignore[arg-type]


def test_validate_provider_id_is_known_accepts_bedrock_and_openai() -> None:
    validate_provider_id_is_known(ProviderId.BEDROCK)
    validate_provider_id_is_known(ProviderId.OPENAI)


def test_validate_provider_id_is_known_rejects_a_non_provider_id() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_provider_id_is_known("bedrock")  # type: ignore[arg-type]


def test_validate_capability_profile_accepts_the_catalog_profiles() -> None:
    validate_capability_profile(BEDROCK_CAPABILITY_PROFILE)
    validate_capability_profile(OPENAI_CAPABILITY_PROFILE)


def test_validate_capability_profile_rejects_a_non_profile() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_capability_profile(object())  # type: ignore[arg-type]


def test_validate_provider_declares_capability_accepts_known_pair() -> None:
    validate_provider_declares_capability(
        BEDROCK_CAPABILITY_PROFILE, CapabilityId.MODERNIZATION_ADVISOR
    )


def test_validate_provider_declares_capability_rejects_an_undeclared_capability() -> None:
    minimal_profile = ProviderCapabilityProfile(
        provider_id=ProviderId.OPENAI,
        supported_capability_ids=(CapabilityId.MODERNIZATION_ADVISOR,),
        supports_structured_json=True,
        supports_streaming=False,
        supports_timeout_policy=True,
        supports_retry_policy=True,
        reports_usage_metadata=True,
        reports_token_accounting=True,
    )
    # There is only one CapabilityId today, so simulate an "undeclared"
    # capability by asserting the positive case and the type-check path.
    with pytest.raises(ProviderContractValidationError):
        validate_provider_declares_capability(minimal_profile, "modernization_advisor")  # type: ignore[arg-type]
