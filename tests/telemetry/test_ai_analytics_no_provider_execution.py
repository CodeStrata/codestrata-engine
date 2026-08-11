"""Prove AI analytics construction never executes providers (Slice 10.6)."""

from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codestrata.telemetry.analytics.ai_analytics import collect_ai_analytics
from codestrata.telemetry.analytics.ai_analytics_input import build_ai_analytics_input
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)


@pytest.fixture
def block_network(monkeypatch) -> None:
    def _deny(*_a, **_k):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during AI analytics")

    monkeypatch.setattr(socket, "socket", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)


def test_no_openai_or_bedrock_client(monkeypatch, block_network, tmp_path: Path) -> None:
    openai_ctor = MagicMock(side_effect=AssertionError("OpenAI client constructed"))
    bedrock_ctor = MagicMock(side_effect=AssertionError("Bedrock client constructed"))

    # Patch common constructor symbols if modules are importable; otherwise skip.
    try:
        import openai  # type: ignore

        monkeypatch.setattr(openai, "OpenAI", openai_ctor, raising=False)
        monkeypatch.setattr(openai, "Client", openai_ctor, raising=False)
    except Exception:
        pass
    try:
        import boto3  # type: ignore

        monkeypatch.setattr(boto3, "client", bedrock_ctor, raising=False)
        monkeypatch.setattr(boto3, "Session", bedrock_ctor, raising=False)
    except Exception:
        pass

    # Also patch Engine provider modules if present.
    for mod_name, attr in (
        ("codestrata.application.ai.providers.openai_provider", "OpenAIProvider"),
        ("codestrata.application.ai.providers.bedrock_provider", "BedrockProvider"),
        ("codestrata.services.ai.openai", "OpenAIClient"),
        ("codestrata.services.ai.bedrock", "BedrockClient"),
    ):
        try:
            mod = __import__(mod_name, fromlist=[attr])
            if hasattr(mod, attr):
                monkeypatch.setattr(
                    mod,
                    attr,
                    MagicMock(side_effect=AssertionError(f"{attr} constructed")),
                )
        except Exception:
            continue

    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-be-read-for-analytics")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_SHOULD_NOT_BE_READ")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

    aggregate = build_ai_analytics_input(
        capability="modernization_advisor",
        provider_family="openai",
        model_family="gpt_family",
        provider_ownership="customer_managed",
        outcome="success",
        ai_used=True,
    )
    event, projected, _diag = collect_ai_analytics(
        aggregate=aggregate,
        identity=new_anonymous_installation_identity(),
        home=tmp_path / "home",
    )
    assert event.provider_family == "openai"
    assert projected.fields["model_family"] == "gpt_family"
    openai_ctor.assert_not_called()
    bedrock_ctor.assert_not_called()
