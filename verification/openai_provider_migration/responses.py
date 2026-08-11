"""Response mapping: tolerant reads, bounded failures, and no leaked text."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openai import error_mapping, response_mapping
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.provider_contracts.serialization import serialize_result_for_diagnostics
from verification.openai_provider_migration import fixtures
from verification.openai_provider_migration.determinism import canonical_json
from verification.openai_provider_migration.models import CheckResult

_LATENCY_MS = 12.5


def _extract(response: Any) -> response_mapping.ExtractionOutcome:
    return response_mapping.extract_chat_response(response)


def _success_result(
    *, text: str = fixtures.SYNTHETIC_RESPONSE_TEXT, expectation: ResponseExpectation
) -> tuple[Any, Any]:
    outcome = _extract(fixtures.response(text))
    assert outcome.extracted is not None
    return response_mapping.build_success_result(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        response_expectation=expectation,
        extracted=outcome.extracted,
        latency_ms=_LATENCY_MS,
    )


def check_a_well_formed_response_is_extracted() -> CheckResult:
    outcome = _extract(fixtures.response())
    extracted = outcome.extracted
    ok = (
        extracted is not None
        and extracted.text == fixtures.SYNTHETIC_RESPONSE_TEXT
        and extracted.stop_reason == "stop"
        and extracted.request_id == fixtures.SYNTHETIC_REQUEST_ID
        and extracted.usage_object is not None
    )
    return CheckResult(
        name="a_well_formed_chat_response_yields_text_stop_reason_request_id_and_usage",
        category="responses",
        ok=ok,
        detail="all four response fields were read",
    )


def check_empty_content_is_an_invalid_response_failure() -> CheckResult:
    """Empty assistant text was an invocation error before and is still bounded."""

    cases = {
        "empty_string": fixtures.response(""),
        "whitespace_only": fixtures.response("   \n  "),
        "non_string": fixtures.response(None),
    }
    wrong = sorted(
        name
        for name, response in cases.items()
        if not (
            (failure := _extract(response).failure) is not None
            and failure.error.code == error_mapping.CODE_EMPTY_RESPONSE
            and failure.error.category is ErrorCategory.INVALID_RESPONSE
        )
    )
    return CheckResult(
        name="empty_or_non_string_assistant_text_maps_to_a_bounded_invalid_response",
        category="responses",
        ok=not wrong,
        detail=f"unbounded_cases={wrong}",
        evidence={"cases_compared": sorted(cases)},
    )


def check_a_malformed_response_object_is_unreadable_not_a_crash() -> CheckResult:
    cases: dict[str, Any] = {
        "no_choices_attribute": object(),
        "empty_choices": fixtures.Response(choices=[]),
        "choice_without_message": fixtures.Response(choices=[object()]),  # type: ignore[list-item]
    }
    wrong: list[str] = []
    for name, response in cases.items():
        try:
            outcome = _extract(response)
        except Exception:  # noqa: BLE001 - verification asserts non-raising
            wrong.append(name)
            continue
        failure = outcome.failure
        if failure is None or failure.error.category is not ErrorCategory.INVALID_RESPONSE:
            wrong.append(name)
    return CheckResult(
        name="a_malformed_response_object_yields_a_bounded_invalid_response_not_an_exception",
        category="responses",
        ok=not wrong,
        detail=f"unbounded_cases={sorted(wrong)}",
    )


def check_oversized_response_text_is_rejected_boundedly() -> CheckResult:
    oversized = "x" * (response_mapping.MAX_RESPONSE_TEXT_LENGTH + 1)
    failure = _extract(fixtures.response(oversized)).failure
    ok = (
        failure is not None
        and failure.error.code == error_mapping.CODE_UNREADABLE_RESPONSE
        and oversized not in failure.legacy_detail
        and len(failure.legacy_detail) <= 240
    )
    return CheckResult(
        name="an_oversized_response_body_is_rejected_without_echoing_the_body",
        category="responses",
        ok=ok,
        detail=f"max_response_text_length={response_mapping.MAX_RESPONSE_TEXT_LENGTH}",
    )


def check_structured_json_is_decoded_when_expected() -> CheckResult:
    result, _ = _success_result(expectation=ResponseExpectation.STRUCTURED_JSON)
    content = result.content
    ok = (
        content is not None
        and content.structured_payload == {"synthetic_response": True}
        and content.text == fixtures.SYNTHETIC_RESPONSE_TEXT
    )
    return CheckResult(
        name="a_structured_json_expectation_decodes_the_payload_and_keeps_the_raw_text",
        category="responses",
        ok=ok,
        detail="both text and structured_payload are populated",
    )


def check_undecodable_text_still_succeeds_with_raw_text() -> CheckResult:
    """Parsing stays the caller's responsibility, exactly as before the migration."""

    outcome = _extract(fixtures.response("not json at all"))
    assert outcome.extracted is not None
    result, _ = response_mapping.build_success_result(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
        extracted=outcome.extracted,
        latency_ms=_LATENCY_MS,
    )
    content = result.content
    ok = (
        result.status is ProviderExecutionStatus.SUCCESS
        and content is not None
        and content.structured_payload is None
        and content.text == "not json at all"
    )
    return CheckResult(
        name="undecodable_text_is_returned_as_raw_text_rather_than_failing_in_the_adapter",
        category="responses",
        ok=ok,
        detail="structured_payload is None and the status stays success",
    )


def check_a_json_array_is_not_treated_as_a_json_object() -> CheckResult:
    decoded = response_mapping.decode_structured_payload("[1, 2, 3]")
    return CheckResult(
        name="a_json_array_body_is_not_mistaken_for_the_expected_json_object",
        category="responses",
        ok=decoded is None,
        detail="only a top-level JSON object decodes to a structured payload",
    )


def check_a_text_expectation_does_not_decode() -> CheckResult:
    result, _ = _success_result(expectation=ResponseExpectation.TEXT)
    content = result.content
    ok = content is not None and content.structured_payload is None
    return CheckResult(
        name="a_text_expectation_never_attempts_structured_decoding",
        category="responses",
        ok=ok,
        detail="structured_payload stays None for a TEXT expectation",
    )


def check_latency_is_carried_onto_the_result_usage() -> CheckResult:
    result, detail = _success_result(expectation=ResponseExpectation.STRUCTURED_JSON)
    usage = result.usage
    ok = usage is not None and usage.latency_ms == _LATENCY_MS and detail.latency_ms == _LATENCY_MS
    return CheckResult(
        name="measured_latency_is_carried_onto_both_the_usage_record_and_the_bridge_detail",
        category="responses",
        ok=ok,
        detail="latency_ms is recorded once and reused",
    )


def check_the_request_id_never_reaches_the_contract_result() -> CheckResult:
    """A provider-issued request ID is bridge-only, never part of a result."""

    result, detail = _success_result(expectation=ResponseExpectation.STRUCTURED_JSON)
    serialized = canonical_json(serialize_result_for_diagnostics(result))
    ok = (
        detail.request_id == fixtures.SYNTHETIC_REQUEST_ID
        and fixtures.SYNTHETIC_REQUEST_ID not in serialized
    )
    return CheckResult(
        name="the_provider_request_id_stays_on_the_bridge_detail_and_out_of_the_result",
        category="responses",
        ok=ok,
        detail="request_id is absent from the diagnostic serialization",
    )


def check_a_failure_result_carries_no_content_and_no_raw_text() -> CheckResult:
    failure = error_mapping.classify_sdk_exception(
        fixtures.sdk_exception("BadRequestError", "raw sdk text with sk-secret-value")
    )
    result, detail = response_mapping.build_failure_result(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.FAILED,
        failure=failure,
        latency_ms=_LATENCY_MS,
    )
    serialized = canonical_json(serialize_result_for_diagnostics(result))
    ok = (
        result.content is None
        and "raw sdk text" not in serialized
        and detail.error_code == error_mapping.CODE_INVALID_REQUEST
    )
    return CheckResult(
        name="a_failure_result_carries_no_content_and_no_raw_sdk_text",
        category="responses",
        ok=ok,
        detail="the sanitized legacy detail stays on the bridge detail only",
    )


def run_response_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_a_well_formed_response_is_extracted(),
        check_empty_content_is_an_invalid_response_failure(),
        check_a_malformed_response_object_is_unreadable_not_a_crash(),
        check_oversized_response_text_is_rejected_boundedly(),
        check_structured_json_is_decoded_when_expected(),
        check_undecodable_text_still_succeeds_with_raw_text(),
        check_a_json_array_is_not_treated_as_a_json_object(),
        check_a_text_expectation_does_not_decode(),
        check_latency_is_carried_onto_the_result_usage(),
        check_the_request_id_never_reaches_the_contract_result(),
        check_a_failure_result_carries_no_content_and_no_raw_text(),
    ]
    matrix: dict[str, Any] = {
        "empty_response_code": error_mapping.CODE_EMPTY_RESPONSE,
        "max_response_text_length": response_mapping.MAX_RESPONSE_TEXT_LENGTH,
        "unreadable_response_code": error_mapping.CODE_UNREADABLE_RESPONSE,
    }
    return checks, matrix


__all__ = [
    "check_a_failure_result_carries_no_content_and_no_raw_text",
    "check_a_json_array_is_not_treated_as_a_json_object",
    "check_a_malformed_response_object_is_unreadable_not_a_crash",
    "check_a_text_expectation_does_not_decode",
    "check_a_well_formed_response_is_extracted",
    "check_empty_content_is_an_invalid_response_failure",
    "check_latency_is_carried_onto_the_result_usage",
    "check_oversized_response_text_is_rejected_boundedly",
    "check_structured_json_is_decoded_when_expected",
    "check_the_request_id_never_reaches_the_contract_result",
    "check_undecodable_text_still_succeeds_with_raw_text",
    "run_response_checks",
]
