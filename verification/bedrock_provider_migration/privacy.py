"""Privacy: what may never appear in a diagnostic view or in this report.

Two distinct properties are checked:

1. *Adapter privacy* — the adapter's diagnostic views, results, reprs, and
   serializations never carry an AWS profile name, a region, an account ID,
   an ARN, a service endpoint, prompt text, response text, a provider request
   ID, raw exception text, a filesystem path, or a model value.
2. *Report privacy* — the finished SV.11.7 report body carries none of those
   either, and no timestamp or duration that would break determinism.

The pre-migration provider's ``logger.info`` line naming the profile and
region is preserved by the compatibility wrapper. That is a *log*, not a
report: these checks scan diagnostic views and the report body, both of which
carry presence booleans instead.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock import diagnostics, error_mapping
from codestrata.ai.provider_adapters.bedrock.client import resolve_client
from codestrata.ai.provider_adapters.bedrock.configuration import build_runtime_configuration
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.ai.provider_contracts.serialization import serialize_result_for_diagnostics
from codestrata.config.settings import CodestrataSettings
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.determinism import canonical_json
from verification.bedrock_provider_migration.models import CheckResult

# Every synthetic secret injected into the adapter for these checks. None may
# appear in any diagnostic view, result, repr, or report body.
SECRET_PROFILE_NAME = "synthetic-private-aws-profile"
SECRET_REGION_NAME = "synthetic-private-aws-region"
SECRET_ACCOUNT_ID = "000000000000"
SECRET_ARN = "arn:aws:bedrock:synthetic-private:000000000000:model/synthetic-private-model"
SECRET_ENDPOINT = "https://bedrock-runtime.synthetic-private.amazonaws.invalid"
SECRET_MODEL_VALUE = "synthetic-private-model-name"
SECRET_PROMPT_TEXT = "synthetic-private-prompt-body"
SECRET_RESPONSE_TEXT = '{"synthetic_private_response": "synthetic-private-answer"}'
SECRET_REQUEST_ID = "synthetic-private-request-identifier"
SECRET_EXCEPTION_TEXT = "synthetic-private-exception-body at /Users/synthetic/private/path.py"

# Substrings the report body and every diagnostic view must not contain. The
# *names* of AWS environment variables are deliberately excluded: naming them
# (never their values) is how the adapter and doctor tell an operator what to
# configure.
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    SECRET_ACCOUNT_ID,
    SECRET_ARN,
    SECRET_ENDPOINT,
    SECRET_EXCEPTION_TEXT,
    SECRET_MODEL_VALUE,
    SECRET_PROFILE_NAME,
    SECRET_PROMPT_TEXT,
    SECRET_REGION_NAME,
    SECRET_REQUEST_ID,
    SECRET_RESPONSE_TEXT,
    "/Users/synthetic",
    "synthetic-private-answer",
)


def _secret_settings() -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "aws": {"profile": SECRET_PROFILE_NAME, "region": SECRET_REGION_NAME},
        }
    )


def _secret_response() -> dict[str, Any]:
    return fixtures.converse_response(SECRET_RESPONSE_TEXT, request_id=SECRET_REQUEST_ID)


def _secret_adapter(outcome: Any = None) -> Any:
    return build_bedrock_provider(
        settings=_secret_settings(),
        client=fixtures.Client(outcome if outcome is not None else _secret_response()),
    )


def _secret_request() -> Any:
    return fixtures.provider_request(
        payload=fixtures.advisor_payload(
            instruction_text=SECRET_PROMPT_TEXT, context_payload_text=SECRET_PROMPT_TEXT
        ),
        model_id=SECRET_MODEL_VALUE,
    )


def leaked_substrings(rendered: str) -> list[str]:
    """Return every forbidden substring present in ``rendered``."""

    return sorted(token for token in FORBIDDEN_SUBSTRINGS if token in rendered)


def check_the_adapter_diagnostic_view_is_clean() -> CheckResult:
    rendered = canonical_json(diagnostics.diagnostic_view_of_adapter(_secret_adapter()))
    leaked = leaked_substrings(rendered)
    return CheckResult(
        name="the_adapter_diagnostic_view_leaks_no_profile_region_or_model_value",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_success_result_view_is_clean() -> CheckResult:
    result = _secret_adapter().execute(_secret_request())
    rendered = canonical_json(diagnostics.diagnostic_view_of_provider_result(result))
    leaked = leaked_substrings(rendered)
    return CheckResult(
        name="the_success_result_diagnostic_view_leaks_no_response_text_or_request_id",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_serialized_result_is_clean() -> CheckResult:
    result = _secret_adapter().execute(_secret_request())
    rendered = canonical_json(serialize_result_for_diagnostics(result))
    leaked = leaked_substrings(rendered)
    return CheckResult(
        name="the_serialized_result_leaks_no_response_text_or_request_id",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_failure_result_view_is_clean() -> CheckResult:
    adapter = _secret_adapter(
        fixtures.sdk_exception("ValidationException", SECRET_EXCEPTION_TEXT)
    )
    result = adapter.execute(_secret_request())
    rendered = canonical_json(diagnostics.diagnostic_view_of_provider_result(result))
    leaked = leaked_substrings(rendered)
    return CheckResult(
        name="the_failure_result_diagnostic_view_leaks_no_exception_text_or_path",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_configuration_repr_and_view_are_clean() -> CheckResult:
    runtime = build_runtime_configuration(settings=_secret_settings())
    rendered = " ".join(
        (
            repr(runtime),
            repr(runtime.client_inputs),
            canonical_json(dict(runtime.redacted())),
        )
    )
    leaked = leaked_substrings(rendered)
    return CheckResult(
        name="the_configuration_repr_and_redacted_view_leak_no_profile_or_region",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_client_handle_repr_is_clean() -> CheckResult:
    class _EndpointEchoingClient:
        def __repr__(self) -> str:
            return f"<client endpoint={SECRET_ENDPOINT}>"

        def converse(self, **_kwargs: Any) -> Any:  # pragma: no cover - never called
            return _secret_response()

    resolution = resolve_client(
        build_runtime_configuration(settings=_secret_settings()).client_inputs,
        injected_client=_EndpointEchoingClient(),
    )
    leaked = leaked_substrings(repr(resolution.handle))
    return CheckResult(
        name="the_client_handle_repr_leaks_no_endpoint_profile_or_region",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_every_bounded_error_is_clean() -> CheckResult:
    rendered_parts: list[str] = []
    for code in error_mapping.CATEGORY_BY_CODE:
        error = error_mapping.build_error(code)
        rendered_parts.append(f"{error.code} {error.category.value} {error.detail}")
    for class_name in error_mapping.SDK_EXCEPTION_NAME_TO_CODE:
        mapped = error_mapping.classify_sdk_exception(
            fixtures.sdk_exception(class_name, SECRET_EXCEPTION_TEXT)
        )
        rendered_parts.append(f"{mapped.error.code} {mapped.error.detail}")
    for aws_code in error_mapping.SDK_ERROR_CODE_TO_CODE:
        mapped = error_mapping.classify_sdk_exception(
            fixtures.client_error(aws_code, SECRET_EXCEPTION_TEXT)
        )
        rendered_parts.append(f"{mapped.error.code} {mapped.error.detail}")
    leaked = leaked_substrings(" ".join(rendered_parts))
    return CheckResult(
        name="every_bounded_error_object_leaks_no_exception_text_or_path",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_capability_view_is_clean() -> CheckResult:
    rendered = canonical_json(diagnostics.diagnostic_view_of_capabilities())
    leaked = leaked_substrings(rendered)
    return CheckResult(
        name="the_capability_diagnostic_view_carries_no_configuration_value",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_error_matrices_are_clean() -> CheckResult:
    rendered = " ".join(
        (
            canonical_json(diagnostics.error_category_matrix()),
            canonical_json({k: str(v) for k, v in diagnostics.retryability_matrix().items()}),
        )
    )
    leaked = leaked_substrings(rendered)
    return CheckResult(
        name="the_error_category_and_retryability_matrices_carry_no_secret",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def check_the_report_body_is_clean(report_body: dict[str, Any]) -> CheckResult:
    leaked = leaked_substrings(canonical_json(report_body))
    return CheckResult(
        name="the_verification_report_body_leaks_no_profile_region_prompt_or_response",
        category="privacy",
        ok=not leaked,
        detail=f"leaked={leaked}",
        evidence={"forbidden_substring_count": len(FORBIDDEN_SUBSTRINGS)},
    )


def check_the_report_body_records_no_timestamp(report_body: dict[str, Any]) -> CheckResult:
    rendered = canonical_json(report_body).lower()
    offenders = sorted(
        token
        for token in ("generated_at", "timestamp", "created_at", "ran_at", "duration_ms")
        if token in rendered
    )
    return CheckResult(
        name="the_verification_report_body_records_no_timestamp_or_duration",
        category="privacy",
        ok=not offenders,
        detail=f"offending_keys={offenders}",
    )


def check_the_report_body_records_no_absolute_path(report_body: dict[str, Any]) -> CheckResult:
    rendered = canonical_json(report_body)
    offenders = sorted(
        token for token in ("/Users/", "/home/", "C:\\", "/private/var") if token in rendered
    )
    return CheckResult(
        name="the_verification_report_body_records_no_absolute_filesystem_path",
        category="privacy",
        ok=not offenders,
        detail=f"offending_prefixes={offenders}",
    )


def check_the_report_body_records_no_aws_identifier(report_body: dict[str, Any]) -> CheckResult:
    """No ARN, account ID, or service endpoint may reach the report."""

    rendered = canonical_json(report_body).lower()
    offenders = sorted(
        token
        for token in ("arn:aws", "amazonaws.com", "sts.", "169.254.169.254")
        if token in rendered
    )
    return CheckResult(
        name="the_verification_report_body_records_no_arn_account_or_service_endpoint",
        category="privacy",
        ok=not offenders,
        detail=f"offending_tokens={offenders}",
    )


def run_adapter_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_adapter_diagnostic_view_is_clean(),
        check_the_success_result_view_is_clean(),
        check_the_serialized_result_is_clean(),
        check_the_failure_result_view_is_clean(),
        check_the_configuration_repr_and_view_are_clean(),
        check_the_client_handle_repr_is_clean(),
        check_every_bounded_error_is_clean(),
        check_the_capability_view_is_clean(),
        check_the_error_matrices_are_clean(),
    ]
    matrix: dict[str, Any] = {
        "aws_environment_variable_names_are_reportable": True,
        "aws_environment_variable_values_are_reportable": False,
        "forbidden_substring_count": len(FORBIDDEN_SUBSTRINGS),
        "profile_and_region_reported_as": "presence_boolean",
    }
    return checks, matrix


def run_report_privacy_checks(report_body: dict[str, Any]) -> list[CheckResult]:
    return [
        check_the_report_body_is_clean(report_body),
        check_the_report_body_records_no_timestamp(report_body),
        check_the_report_body_records_no_absolute_path(report_body),
        check_the_report_body_records_no_aws_identifier(report_body),
    ]


__all__ = [
    "FORBIDDEN_SUBSTRINGS",
    "SECRET_ACCOUNT_ID",
    "SECRET_ARN",
    "SECRET_ENDPOINT",
    "SECRET_EXCEPTION_TEXT",
    "SECRET_MODEL_VALUE",
    "SECRET_PROFILE_NAME",
    "SECRET_PROMPT_TEXT",
    "SECRET_REGION_NAME",
    "SECRET_REQUEST_ID",
    "SECRET_RESPONSE_TEXT",
    "check_every_bounded_error_is_clean",
    "check_the_adapter_diagnostic_view_is_clean",
    "check_the_capability_view_is_clean",
    "check_the_client_handle_repr_is_clean",
    "check_the_configuration_repr_and_view_are_clean",
    "check_the_error_matrices_are_clean",
    "check_the_failure_result_view_is_clean",
    "check_the_report_body_is_clean",
    "check_the_report_body_records_no_absolute_path",
    "check_the_report_body_records_no_aws_identifier",
    "check_the_report_body_records_no_timestamp",
    "check_the_serialized_result_is_clean",
    "check_the_success_result_view_is_clean",
    "leaked_substrings",
    "run_adapter_privacy_checks",
    "run_report_privacy_checks",
]
