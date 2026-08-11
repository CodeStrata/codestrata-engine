"""Characterize the AI provider exception hierarchy and error-mapping matrices.

Exercises the real ``_map_bedrock_exception`` / ``_map_openai_exception``
helpers with synthetic, clearly-fake exception instances — never a real
botocore/OpenAI SDK exception raised by an actual network call.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.ai.providers import bedrock as bedrock_module
from codestrata.ai.providers import openai_provider as openai_module
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvocationError,
    AIProviderTimeoutError,
    AIResponseParsingError,
    AIResponseValidationError,
)
from verification.ai_provider_baseline.models import CheckResult


class _FakeClientError(Exception):
    """Synthetic stand-in for botocore.exceptions.ClientError (no botocore import)."""

    def __init__(self, code: str) -> None:
        super().__init__(f"fake client error ({code})")
        self.response = {"Error": {"Code": code}}


def check_exception_hierarchy(_source_root: Path) -> CheckResult:
    hierarchy_ok = (
        issubclass(AIProviderConfigurationError, AIProviderError)
        and issubclass(AIProviderInvocationError, AIProviderError)
        and issubclass(AIProviderTimeoutError, AIProviderInvocationError)
        and issubclass(AIResponseParsingError, AIProviderError)
        and issubclass(AIResponseValidationError, AIProviderError)
    )
    return CheckResult(
        name="ai_provider_exception_hierarchy_matches_ground_truth",
        category="errors",
        ok=hierarchy_ok,
        detail="AIProviderTimeoutError is-a AIProviderInvocationError is-a AIProviderError",
    )


def build_bedrock_error_mapping_matrix() -> list[dict[str, str]]:
    scenarios: list[tuple[str, Exception]] = [
        ("no_credentials_error", type("NoCredentialsError", (Exception,), {})()),
        ("read_timeout_error", type("ReadTimeoutError", (Exception,), {})()),
        ("throttling_exception", _FakeClientError("ThrottlingException")),
        ("access_denied_exception", _FakeClientError("AccessDeniedException")),
        ("validation_exception", _FakeClientError("ValidationException")),
        ("unrecognized_client_exception", _FakeClientError("UnrecognizedClientException")),
        ("unknown_error", RuntimeError("something unexpected")),
    ]
    results: list[dict[str, str]] = []
    for scenario_name, exc in scenarios:
        mapped = bedrock_module._map_bedrock_exception(exc, profile=None)  # noqa: SLF001
        results.append(
            {
                "mapped_type": type(mapped).__name__,
                "scenario": scenario_name,
            }
        )
    results.sort(key=lambda item: item["scenario"])
    return results


def build_openai_error_mapping_matrix() -> list[dict[str, str]]:
    scenarios: list[tuple[str, Exception]] = [
        ("authentication_error", type("AuthenticationError", (Exception,), {})()),
        ("rate_limit_error", type("RateLimitError", (Exception,), {})()),
        ("bad_request_error", type("BadRequestError", (Exception,), {})()),
        ("unknown_error", RuntimeError("something unexpected")),
    ]
    results: list[dict[str, str]] = []
    for scenario_name, exc in scenarios:
        mapped = openai_module._map_openai_exception(exc)  # noqa: SLF001
        results.append(
            {
                "mapped_type": type(mapped).__name__,
                "scenario": scenario_name,
            }
        )
    results.sort(key=lambda item: item["scenario"])
    return results


def check_bedrock_error_mapping_categories(_source_root: Path) -> CheckResult:
    matrix = {
        item["scenario"]: item["mapped_type"] for item in build_bedrock_error_mapping_matrix()
    }
    ok = (
        matrix["read_timeout_error"] == "AIProviderTimeoutError"
        and matrix["throttling_exception"] == "AIProviderTimeoutError"
        and matrix["no_credentials_error"] == "AIProviderInvocationError"
        and matrix["access_denied_exception"] == "AIProviderInvocationError"
    )
    return CheckResult(
        name="bedrock_error_mapping_categorizes_timeouts_vs_invocation_failures",
        category="errors",
        ok=ok,
        detail=f"matrix={matrix}",
        evidence={"matrix": matrix},
    )


def check_openai_error_mapping_categories(_source_root: Path) -> CheckResult:
    matrix = {item["scenario"]: item["mapped_type"] for item in build_openai_error_mapping_matrix()}
    ok = (
        matrix["rate_limit_error"] == "AIProviderTimeoutError"
        and matrix["authentication_error"] == "AIProviderInvocationError"
        and matrix["bad_request_error"] == "AIProviderInvocationError"
    )
    return CheckResult(
        name="openai_error_mapping_categorizes_timeouts_vs_invocation_failures",
        category="errors",
        ok=ok,
        detail=f"matrix={matrix}",
        evidence={"matrix": matrix},
    )


def check_response_contract_errors_carry_metadata(_source_root: Path) -> CheckResult:
    error = AIResponseParsingError(
        "fixture parsing failure",
        raw_response_text="not json",
        validation_details="fixture detail",
    )
    ok = error.raw_response_text == "not json" and error.validation_details == "fixture detail"
    return CheckResult(
        name="response_contract_errors_carry_raw_text_and_validation_details",
        category="errors",
        ok=ok,
        detail="AIResponseParsingError preserves raw_response_text/validation_details",
    )


def run_error_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_exception_hierarchy(source_root),
        check_bedrock_error_mapping_categories(source_root),
        check_openai_error_mapping_categories(source_root),
        check_response_contract_errors_carry_metadata(source_root),
    ]
    matrix = {
        "bedrock": build_bedrock_error_mapping_matrix(),
        "openai": build_openai_error_mapping_matrix(),
    }
    return checks, matrix


__all__ = [
    "build_bedrock_error_mapping_matrix",
    "build_openai_error_mapping_matrix",
    "check_bedrock_error_mapping_categories",
    "check_exception_hierarchy",
    "check_openai_error_mapping_categories",
    "check_response_contract_errors_carry_metadata",
    "run_error_checks",
]
