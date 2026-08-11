"""Provider-family mapping tests (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_mapping import map_provider_to_family
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("openai", "openai"),
        ("bedrock", "aws_bedrock"),
        ("aws_bedrock", "aws_bedrock"),
        ("openrouter", "openrouter"),
        ("unavailable", "unavailable"),
    ],
)
def test_map_known_providers(raw: str, expected: str) -> None:
    assert map_provider_to_family(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["anthropic", "custom-provider", "AzureOpenAI"],
)
def test_unknown_provider_rejected(raw: str) -> None:
    with pytest.raises(AnalyticsError) as exc:
        map_provider_to_family(raw)
    assert exc.value.code == AnalyticsErrorCode.INVALID_PROVIDER_FAMILY
    assert raw not in str(exc.value)


@pytest.mark.parametrize(
    "raw",
    [
        "https://api.openai.com/v1",
        "bedrock.us-east-1.amazonaws.com",
        "org@account",
    ],
)
def test_raw_provider_identifier_rejected(raw: str) -> None:
    with pytest.raises(AnalyticsError) as exc:
        map_provider_to_family(raw)
    assert exc.value.code == AnalyticsErrorCode.RAW_PROVIDER_IDENTIFIER_REJECTED
    assert raw not in str(exc.value)
