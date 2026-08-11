"""Provider-selection resolution checks against ground truth.

Cross-checks ``resolve_provider_id`` against the real
``codestrata.config.settings.AiSettings`` default and against
``codestrata.ai.providers.factory.create_assess_ai_provider``'s selection
logic (``(settings.ai.provider or "bedrock").strip().lower()``) — without
ever calling the real factory (which would require the assess provider
registry) or touching real settings I/O.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderId
from codestrata.ai.provider_contracts.model_configuration import resolve_provider_id
from codestrata.config.settings import AiSettings
from verification.ai_provider_configuration.models import CheckResult


def check_default_provider_matches_ai_settings_default() -> CheckResult:
    settings_default = AiSettings().provider
    provider_id, _source = resolve_provider_id(file_provider=None)
    ok = provider_id.value == settings_default
    return CheckResult(
        name="resolve_provider_id_default_matches_ai_settings_default",
        category="provider_selection",
        ok=ok,
        detail=f"resolved={provider_id.value!r} ai_settings_default={settings_default!r}",
    )


def check_configuration_file_value_selects_openai() -> CheckResult:
    provider_id, source = resolve_provider_id(file_provider="openai")
    ok = provider_id is ProviderId.OPENAI and str(source) == "configuration_file"
    return CheckResult(
        name="resolve_provider_id_honors_configuration_file_value",
        category="provider_selection",
        ok=ok,
        detail=f"provider_id={provider_id} source={source}",
    )


def check_case_and_whitespace_normalization_matches_factory_behavior() -> CheckResult:
    """create_assess_ai_provider does `.strip().lower()`; this must match exactly."""

    provider_id, _source = resolve_provider_id(file_provider="  BEDROCK  ")
    ok = provider_id is ProviderId.BEDROCK
    return CheckResult(
        name="resolve_provider_id_normalizes_case_and_whitespace_like_the_real_factory",
        category="provider_selection",
        ok=ok,
        detail=f"provider_id={provider_id}",
    )


def check_unsupported_provider_is_rejected_at_construction_time() -> CheckResult:
    try:
        resolve_provider_id(file_provider="not-a-real-provider")
    except ProviderContractValidationError:
        return CheckResult(
            name="resolve_provider_id_rejects_unsupported_provider_names",
            category="provider_selection",
            ok=True,
            detail="raised ProviderContractValidationError as expected",
        )
    return CheckResult(
        name="resolve_provider_id_rejects_unsupported_provider_names",
        category="provider_selection",
        ok=False,
        detail="did not raise for an unsupported provider name",
    )


def run_provider_selection_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_default_provider_matches_ai_settings_default(),
        check_configuration_file_value_selects_openai(),
        check_case_and_whitespace_normalization_matches_factory_behavior(),
        check_unsupported_provider_is_rejected_at_construction_time(),
    ]
    matrix = {"ai_settings_default_provider": AiSettings().provider}
    return checks, matrix


__all__ = [
    "check_case_and_whitespace_normalization_matches_factory_behavior",
    "check_configuration_file_value_selects_openai",
    "check_default_provider_matches_ai_settings_default",
    "check_unsupported_provider_is_rejected_at_construction_time",
    "run_provider_selection_checks",
]
