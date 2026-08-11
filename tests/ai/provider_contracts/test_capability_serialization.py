"""Tests for ``capability_serialization``."""

from __future__ import annotations

import json

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
)
from codestrata.ai.provider_contracts.capability_serialization import (
    canonical_json,
    serialize_capability_profile_for_diagnostics,
)


def test_serialize_capability_profile_for_diagnostics_is_valid_json() -> None:
    text = serialize_capability_profile_for_diagnostics(OPENAI_CAPABILITY_PROFILE)
    payload = json.loads(text)
    assert payload["provider_id"] == "openai"


def test_serialize_capability_profile_for_diagnostics_is_deterministic() -> None:
    first = serialize_capability_profile_for_diagnostics(BEDROCK_CAPABILITY_PROFILE)
    second = serialize_capability_profile_for_diagnostics(BEDROCK_CAPABILITY_PROFILE)
    assert first == second


def test_serialize_capability_profile_for_diagnostics_is_compact_and_sorted() -> None:
    text = serialize_capability_profile_for_diagnostics(BEDROCK_CAPABILITY_PROFILE)
    assert canonical_json(json.loads(text)) == text


def test_two_different_profiles_serialize_differently() -> None:
    openai_text = serialize_capability_profile_for_diagnostics(OPENAI_CAPABILITY_PROFILE)
    bedrock_text = serialize_capability_profile_for_diagnostics(BEDROCK_CAPABILITY_PROFILE)
    assert openai_text != bedrock_text
