"""AI analytics determinism tests (Slice 10.6)."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.analytics.ai_analytics import collect_ai_analytics
from codestrata.telemetry.analytics.ai_analytics_diagnostics import (
    empty_ai_analytics_diagnostics,
)
from codestrata.telemetry.analytics.ai_analytics_input import build_ai_analytics_input
from codestrata.telemetry.analytics.ai_analytics_mapping import (
    canonicalize_capability,
    map_model_id_to_family,
    map_provider_to_family,
)
from codestrata.telemetry.analytics.ai_analytics_models import build_ai_analytics_event
from codestrata.telemetry.analytics.ai_analytics_serialization import (
    ai_analytics_event_to_stable_json,
    ai_analytics_policy_to_stable_json,
)
from codestrata.telemetry.analytics.ai_analytics_policy import default_ai_analytics_policy
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)


def test_equivalent_inputs_stable_json() -> None:
    identity = new_anonymous_installation_identity()
    a = build_ai_analytics_input(
        capability="modernization_advisor",
        provider_family="openai",
        model_family="gpt_family",
        provider_ownership="customer_managed",
        outcome="success",
        duration_bucket="lt_1s",
    )
    b = build_ai_analytics_input(
        capability="ai_enrichment",
        provider_family="openai",
        model_family="gpt_family",
        provider_ownership="customer_managed",
        outcome="success",
        duration_bucket="lt_1s",
    )
    ea = build_ai_analytics_event(identity=identity, aggregate=a)
    eb = build_ai_analytics_event(identity=identity, aggregate=b)
    assert ai_analytics_event_to_stable_json(ea) == ai_analytics_event_to_stable_json(eb)
    assert ea.to_analytics_event().to_intake_dict() == eb.to_analytics_event().to_intake_dict()


def test_mapping_aliases_deterministic() -> None:
    assert canonicalize_capability("assess_with_ai") == "modernization_advisor"
    assert map_provider_to_family("bedrock") == map_provider_to_family("aws_bedrock")
    assert map_model_id_to_family("gpt-4o") == map_model_id_to_family("gpt-4o-mini")


def test_policy_json_stable() -> None:
    assert ai_analytics_policy_to_stable_json(
        default_ai_analytics_policy()
    ) == ai_analytics_policy_to_stable_json(default_ai_analytics_policy())


def test_cwd_and_env_do_not_affect_payload(tmp_path: Path, monkeypatch) -> None:
    identity = new_anonymous_installation_identity()
    aggregate = build_ai_analytics_input(
        capability="modernization_advisor",
        provider_family="openai",
        model_family="gpt_family",
        provider_ownership="customer_managed",
        outcome="success",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-should-not-appear")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.chdir(tmp_path)
    event, projected, diag = collect_ai_analytics(
        aggregate=aggregate,
        identity=identity,
        home=tmp_path / "home",
    )
    blob = ai_analytics_event_to_stable_json(event)
    assert "sk-test" not in blob
    assert "AKIA" not in blob
    assert "us-east-1" not in blob
    assert identity.installation_id not in diag.to_stable_json()
    assert projected.installation_id == identity.installation_id


def test_empty_diagnostics_have_no_identity() -> None:
    assert "installation_id" not in empty_ai_analytics_diagnostics().to_stable_dict()
