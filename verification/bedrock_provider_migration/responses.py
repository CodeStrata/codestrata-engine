"""Converse response mapping: same field reads, same tolerance, same failures."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock import error_mapping, response_mapping
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.models import CheckResult


def _execute(response: Any) -> Any:
    return build_bedrock_provider(client=fixtures.Client(response)).execute(
        fixtures.provider_request()
    )


def _category_of(response: Any) -> ErrorCategory | None:
    result = _execute(response)
    return result.error.category if result.error is not None else None


def check_a_well_formed_response_succeeds() -> CheckResult:
    result = _execute(fixtures.converse_response())
    content = result.content
    return CheckResult(
        name="a_well_formed_converse_response_produces_a_success_result",
        category="responses",
        ok=(
            result.status is ProviderExecutionStatus.SUCCESS
            and content is not None
            and content.text == fixtures.SYNTHETIC_RESPONSE_TEXT
        ),
        detail=f"status={result.status.value}",
    )


def check_multiple_text_blocks_are_concatenated() -> CheckResult:
    result = _execute(fixtures.converse_response(text=["alpha", "beta"]))
    content = result.content
    return CheckResult(
        name="multiple_text_content_blocks_are_concatenated_without_a_separator",
        category="responses",
        ok=content is not None and content.text == "alphabeta",
        detail="text blocks join with no separator, unchanged",
    )


def check_non_text_blocks_are_skipped() -> CheckResult:
    response = fixtures.converse_response()
    response["output"]["message"]["content"] = [
        {"toolUse": {"name": "synthetic"}},
        "not-a-dict",
        {"text": ""},
        {"text": "kept"},
    ]
    result = _execute(response)
    content = result.content
    return CheckResult(
        name="non_dict_and_empty_text_content_blocks_are_skipped",
        category="responses",
        ok=content is not None and content.text == "kept",
        detail="skip tolerance is unchanged",
    )


def check_structured_json_is_decoded_when_requested() -> CheckResult:
    result = _execute(fixtures.converse_response())
    content = result.content
    return CheckResult(
        name="a_json_object_response_is_decoded_into_the_structured_payload",
        category="responses",
        ok=content is not None
        and content.structured_payload
        == {
            "executive_summary": {"headline": "H", "narrative": "N"},
            "themes": [],
        },
        detail="decoding is best-effort and never an error",
    )


def check_undecodable_text_is_not_an_error() -> CheckResult:
    result = _execute(fixtures.converse_response(text="not json at all"))
    content = result.content
    return CheckResult(
        name="text_that_is_not_json_still_succeeds_with_no_structured_payload",
        category="responses",
        ok=(
            result.status is ProviderExecutionStatus.SUCCESS
            and content is not None
            and content.structured_payload is None
        ),
        detail="Bedrock has no native JSON mode, so parsing stays the caller's job",
    )


def check_a_text_expectation_skips_decoding() -> CheckResult:
    result = build_bedrock_provider(
        client=fixtures.Client(fixtures.converse_response())
    ).execute(fixtures.provider_request(response_expectation=ResponseExpectation.TEXT))
    content = result.content
    return CheckResult(
        name="a_text_expectation_returns_raw_text_without_decoding_a_payload",
        category="responses",
        ok=content is not None and content.structured_payload is None,
        detail="structured decoding is bound to the structured-JSON expectation",
    )


def check_each_structural_failure_has_its_own_code() -> CheckResult:
    cases: dict[str, Any] = {
        error_mapping.CODE_RESPONSE_NOT_A_MAPPING: "not-a-mapping",
        error_mapping.CODE_RESPONSE_MISSING_OUTPUT: {},
        error_mapping.CODE_RESPONSE_MISSING_MESSAGE: {"output": {}},
        error_mapping.CODE_RESPONSE_MISSING_CONTENT: {"output": {"message": {}}},
        error_mapping.CODE_EMPTY_RESPONSE: {"output": {"message": {"content": []}}},
    }
    mismatches = []
    for expected_code, response in cases.items():
        outcome = response_mapping.extract_converse_response(response)
        actual = outcome.failure.error.code if outcome.failure is not None else None
        if actual != expected_code:
            mismatches.append(f"{expected_code}!={actual}")
    return CheckResult(
        name="each_structural_response_failure_carries_its_own_diagnostic_code",
        category="responses",
        ok=not mismatches,
        detail=f"mismatches={mismatches}",
        evidence={"structural_failure_count": len(cases)},
    )


def check_every_structural_failure_is_invalid_response() -> CheckResult:
    responses: list[Any] = [
        "not-a-mapping",
        {},
        {"output": {}},
        {"output": {"message": {}}},
        {"output": {"message": {"content": []}}},
    ]
    categories = {_category_of(response) for response in responses}
    return CheckResult(
        name="every_structural_response_failure_maps_to_invalid_response",
        category="responses",
        ok=categories == {ErrorCategory.INVALID_RESPONSE},
        detail=f"categories={sorted(category.value for category in categories if category)}",
    )


def check_a_structural_failure_is_failed_not_unavailable() -> CheckResult:
    """A call *was* made, so the run is FAILED rather than UNAVAILABLE."""

    result = _execute({})
    return CheckResult(
        name="a_malformed_response_surfaces_as_failed_rather_than_unavailable",
        category="responses",
        ok=result.status is ProviderExecutionStatus.FAILED,
        detail=f"status={result.status.value}",
    )


def check_an_oversized_response_degrades_gracefully() -> CheckResult:
    oversized = "x" * (response_mapping.MAX_RESPONSE_TEXT_LENGTH + 1)
    outcome = response_mapping.extract_converse_response(
        fixtures.converse_response(text=oversized)
    )
    failure = outcome.failure
    return CheckResult(
        name="an_implausibly_large_response_becomes_a_bounded_invalid_response_failure",
        category="responses",
        ok=(
            failure is not None
            and failure.error.code == error_mapping.CODE_UNREADABLE_RESPONSE
        ),
        detail=f"code={failure.error.code if failure else None}",
    )


def check_the_request_id_is_read_but_kept_off_the_result() -> CheckResult:
    result = _execute(fixtures.converse_response())
    request_id = response_mapping.extract_request_id(fixtures.converse_response())
    rendered = repr(result)
    return CheckResult(
        name="the_provider_request_id_is_read_for_metadata_but_never_placed_on_the_result",
        category="responses",
        ok=request_id == fixtures.SYNTHETIC_REQUEST_ID
        and fixtures.SYNTHETIC_REQUEST_ID not in rendered,
        detail="request IDs travel on the bridge-only invocation detail",
    )


def check_the_stop_reason_reaches_the_detail_sink() -> CheckResult:
    details: list[Any] = []
    build_bedrock_provider(
        client=fixtures.Client(fixtures.converse_response()), detail_sink=details.append
    ).execute(fixtures.provider_request())
    detail = details[-1] if details else None
    return CheckResult(
        name="the_stop_reason_and_request_id_reach_the_bridge_only_detail_sink",
        category="responses",
        ok=(
            detail is not None
            and detail.stop_reason == fixtures.SYNTHETIC_STOP_REASON
            and detail.request_id == fixtures.SYNTHETIC_REQUEST_ID
        ),
        detail="the legacy metadata contract is rebuilt from the detail, not the result",
    )


def run_response_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_a_well_formed_response_succeeds(),
        check_multiple_text_blocks_are_concatenated(),
        check_non_text_blocks_are_skipped(),
        check_structured_json_is_decoded_when_requested(),
        check_undecodable_text_is_not_an_error(),
        check_a_text_expectation_skips_decoding(),
        check_each_structural_failure_has_its_own_code(),
        check_every_structural_failure_is_invalid_response(),
        check_a_structural_failure_is_failed_not_unavailable(),
        check_an_oversized_response_degrades_gracefully(),
        check_the_request_id_is_read_but_kept_off_the_result(),
        check_the_stop_reason_reaches_the_detail_sink(),
    ]
    matrix: dict[str, Any] = {
        "max_response_text_length": response_mapping.MAX_RESPONSE_TEXT_LENGTH,
        "request_id_on_result": False,
        "structural_failure_codes": [
            error_mapping.CODE_RESPONSE_NOT_A_MAPPING,
            error_mapping.CODE_RESPONSE_MISSING_OUTPUT,
            error_mapping.CODE_RESPONSE_MISSING_MESSAGE,
            error_mapping.CODE_RESPONSE_MISSING_CONTENT,
            error_mapping.CODE_EMPTY_RESPONSE,
        ],
    }
    return checks, matrix


__all__ = [
    "check_a_structural_failure_is_failed_not_unavailable",
    "check_a_text_expectation_skips_decoding",
    "check_a_well_formed_response_succeeds",
    "check_an_oversized_response_degrades_gracefully",
    "check_each_structural_failure_has_its_own_code",
    "check_every_structural_failure_is_invalid_response",
    "check_multiple_text_blocks_are_concatenated",
    "check_non_text_blocks_are_skipped",
    "check_structured_json_is_decoded_when_requested",
    "check_the_request_id_is_read_but_kept_off_the_result",
    "check_the_stop_reason_reaches_the_detail_sink",
    "check_undecodable_text_is_not_an_error",
    "run_response_checks",
]
