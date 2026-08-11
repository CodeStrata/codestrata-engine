"""Model-family mapping tests (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_mapping import map_model_id_to_family
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("gpt-4o", "gpt_family"),
        ("gpt-4o-2024-08-06", "gpt_family"),
        ("gpt-4-turbo", "gpt_family"),
        ("amazon.nova-lite-v1:0", "amazon_nova_family"),
        ("amazon.nova-pro-v1:0", "amazon_nova_family"),
        ("gpt_family", "gpt_family"),
        ("amazon_nova_family", "amazon_nova_family"),
        ("unavailable", "unavailable"),
    ],
)
def test_map_known_model_shapes(raw: str, expected: str) -> None:
    assert map_model_id_to_family(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "arn:aws:bedrock:us-east-1:123456789012:foundation-model/amazon.nova",
        "my-custom-deployment-alias",
        "ft:gpt-4o:org:custom:abc",
    ],
)
def test_raw_or_unmapped_model_rejected(raw: str) -> None:
    with pytest.raises(AnalyticsError) as exc:
        map_model_id_to_family(raw)
    assert exc.value.code in {
        AnalyticsErrorCode.RAW_MODEL_IDENTIFIER_REJECTED,
        AnalyticsErrorCode.INVALID_MODEL_FAMILY,
    }
    # Bounded code only — never echo the rejected identifier.
    assert raw not in str(exc.value)
    assert exc.value.args == (exc.value.code.value,)
