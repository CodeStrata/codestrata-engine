"""Presentation helpers for AI execution lifecycle status."""

from __future__ import annotations

from codestrata.ai.providers.models import ModelInvocationMetadata
from codestrata.reporting.modernization_models import (
    AI_FAILURE_STATUSES,
    AI_POST_INVOCATION_FAILURE_STATUSES,
    AIAttemptInfo,
    AIExecutionStage,
    AIExecutionStatus,
    AssessmentMode,
    ModernizationReportInput,
)

AI_FAILURE_CODE_AUTHENTICATION = "AI_AUTHENTICATION_FAILED"
AI_FAILURE_CODE_PROVIDER = "AI_PROVIDER_FAILED"
AI_FAILURE_CODE_PARSING = "AI_PARSING_FAILED"
AI_FAILURE_CODE_VALIDATION = "AI_VALIDATION_FAILED"

_CUSTOMER_MESSAGES: dict[AIExecutionStatus, str] = {
    AIExecutionStatus.AUTHENTICATION_FAILED: (
        "Unable to authenticate with AWS. Deterministic results were retained."
    ),
    AIExecutionStatus.PROVIDER_FAILED: (
        "AI provider invocation failed. Deterministic results were retained."
    ),
    AIExecutionStatus.PARSING_FAILED: (
        "AI response could not be parsed. Deterministic results were retained."
    ),
    AIExecutionStatus.VALIDATION_FAILED: (
        "AI response failed contract validation. Deterministic results were retained."
    ),
}

_FAILURE_CODES: dict[AIExecutionStatus, str] = {
    AIExecutionStatus.AUTHENTICATION_FAILED: AI_FAILURE_CODE_AUTHENTICATION,
    AIExecutionStatus.PROVIDER_FAILED: AI_FAILURE_CODE_PROVIDER,
    AIExecutionStatus.PARSING_FAILED: AI_FAILURE_CODE_PARSING,
    AIExecutionStatus.VALIDATION_FAILED: AI_FAILURE_CODE_VALIDATION,
}


def stages_for_status(status: AIExecutionStatus) -> tuple[AIExecutionStage, ...]:
    """Return the lifecycle stages completed for an overall AI status."""

    if status == AIExecutionStatus.NOT_REQUESTED:
        return ()
    if status == AIExecutionStatus.AUTHENTICATION_FAILED:
        return (AIExecutionStage.REQUESTED, AIExecutionStage.FALLBACK_USED)
    if status == AIExecutionStatus.PROVIDER_FAILED:
        return (
            AIExecutionStage.REQUESTED,
            AIExecutionStage.PROVIDER_INVOKED,
            AIExecutionStage.FALLBACK_USED,
        )
    if status == AIExecutionStatus.PARSING_FAILED:
        return (
            AIExecutionStage.REQUESTED,
            AIExecutionStage.PROVIDER_INVOKED,
            AIExecutionStage.RESPONSE_RECEIVED,
            AIExecutionStage.FALLBACK_USED,
        )
    if status == AIExecutionStatus.VALIDATION_FAILED:
        return (
            AIExecutionStage.REQUESTED,
            AIExecutionStage.PROVIDER_INVOKED,
            AIExecutionStage.RESPONSE_RECEIVED,
            AIExecutionStage.RESPONSE_PARSED,
            AIExecutionStage.FALLBACK_USED,
        )
    if status == AIExecutionStatus.SUCCEEDED:
        return (
            AIExecutionStage.REQUESTED,
            AIExecutionStage.PROVIDER_INVOKED,
            AIExecutionStage.RESPONSE_RECEIVED,
            AIExecutionStage.RESPONSE_PARSED,
            AIExecutionStage.RESPONSE_VALIDATED,
            AIExecutionStage.RESULT_INCLUDED,
        )
    return ()


def customer_failure_message(status: AIExecutionStatus) -> str | None:
    """Return a concise customer-facing failure summary, if applicable."""

    return _CUSTOMER_MESSAGES.get(status)


def failure_code_for_status(status: AIExecutionStatus) -> str | None:
    """Return a short diagnostic failure code for a failed AI status."""

    return _FAILURE_CODES.get(status)


def attempt_info_from_metadata(
    metadata: ModelInvocationMetadata,
    *,
    status: AIExecutionStatus,
    failure_detail: str | None = None,
) -> AIAttemptInfo:
    """Build attempt metadata from a successful Converse invocation."""

    usage = metadata.usage
    return AIAttemptInfo(
        provider=metadata.provider,
        model_id=metadata.model_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        latency_ms=metadata.latency_ms,
        stop_reason=metadata.stop_reason,
        stages_completed=stages_for_status(status),
        failure_code=failure_code_for_status(status),
        failure_detail=failure_detail,
    )


def assessment_mode_display_label(report_input: ModernizationReportInput) -> str:
    """Return the customer-facing assessment mode label for cover/execution panels."""

    status = report_input.ai_status
    if status == AIExecutionStatus.SUCCEEDED:
        return "AI Enhanced"
    if status == AIExecutionStatus.VALIDATION_FAILED:
        return "Deterministic fallback after AI validation failure"
    if status == AIExecutionStatus.PARSING_FAILED:
        return "Deterministic fallback after AI parsing failure"
    if status == AIExecutionStatus.AUTHENTICATION_FAILED:
        return "Deterministic fallback after AI authentication failure"
    if status == AIExecutionStatus.PROVIDER_FAILED:
        return "Deterministic fallback after AI provider failure"
    if report_input.assessment_mode == AssessmentMode.AI_ENHANCED:
        return "AI requested, deterministic fallback"
    return "Deterministic"


def ai_execution_status_label(status: AIExecutionStatus) -> str:
    """Return a short human-readable AI execution status label."""

    labels = {
        AIExecutionStatus.NOT_REQUESTED: "Not requested",
        AIExecutionStatus.SUCCEEDED: "Succeeded",
        AIExecutionStatus.AUTHENTICATION_FAILED: "Authentication failed",
        AIExecutionStatus.PROVIDER_FAILED: "Provider failed",
        AIExecutionStatus.PARSING_FAILED: "Parsing failed",
        AIExecutionStatus.VALIDATION_FAILED: "Validation failed",
    }
    return labels[status]


def ai_cover_subtitle(report_input: ModernizationReportInput) -> str:
    """Return the cover subtitle reflecting AI outcome."""

    if report_input.ai_executed:
        return "AI-enhanced modernization assessment"
    if report_input.ai_status in AI_FAILURE_STATUSES:
        return "Deterministic modernization assessment (AI attempted and rejected)"
    return "Deterministic modernization assessment"


def ai_legend_chip_label(report_input: ModernizationReportInput) -> str:
    """Return the cover legend chip for AI interpretation state."""

    if report_input.ai_executed:
        return "AI-generated interpretation"
    if report_input.ai_status == AIExecutionStatus.VALIDATION_FAILED:
        return "AI response rejected during contract validation"
    if report_input.ai_status == AIExecutionStatus.PARSING_FAILED:
        return "AI response rejected during parsing"
    if report_input.ai_status in AI_FAILURE_STATUSES:
        return "AI interpretation unavailable (fallback)"
    return "AI interpretation not requested"


def ai_section_guidance(report_input: ModernizationReportInput) -> str:
    """Return AI section guidance when no validated AI content is included."""

    if report_input.ai_status == AIExecutionStatus.VALIDATION_FAILED:
        return (
            "AI interpretation was requested, but the model response did not satisfy "
            "CodeStrata's validated output contract. This report therefore contains "
            "deterministic evidence only."
        )
    if report_input.ai_status == AIExecutionStatus.PARSING_FAILED:
        return (
            "AI interpretation was requested, but the model response could not be parsed "
            "as validated CodeStrata output. This report therefore contains deterministic "
            "evidence only."
        )
    if report_input.ai_status == AIExecutionStatus.AUTHENTICATION_FAILED:
        return (
            "AI interpretation was requested, but AWS authentication failed before a "
            "validated model result could be included. This report contains "
            "deterministic evidence only."
        )
    if report_input.ai_status == AIExecutionStatus.PROVIDER_FAILED:
        return (
            "AI interpretation was requested, but the AI provider call failed. "
            "This report therefore contains deterministic evidence only."
        )
    return (
        "AI interpretation was not requested for this assessment. "
        "The report contains CodeStrata deterministic system intelligence only."
    )


def coverage_guidance(report_input: ModernizationReportInput) -> str:
    """Return Evidence Coverage guidance when AI content is absent."""

    if report_input.ai_status in {
        AIExecutionStatus.VALIDATION_FAILED,
        AIExecutionStatus.PARSING_FAILED,
    }:
        return (
            "AI interpretation was requested, but the model response did not satisfy "
            "CodeStrata's validated output contract. This report therefore contains "
            "deterministic evidence only."
        )
    if report_input.ai_status in AI_FAILURE_STATUSES:
        return (
            "AI interpretation was requested, but a validated AI result was not "
            "produced. This report therefore contains deterministic evidence only."
        )
    return (
        "This report contains deterministic repository evidence only. "
        "Enable AI-enhanced assessment when modernization recommendations "
        "and roadmap interpretation are required."
    )


def provider_invocation_label(report_input: ModernizationReportInput) -> str:
    """Return whether provider invocation succeeded enough to receive a response."""

    status = report_input.ai_status
    if status == AIExecutionStatus.NOT_REQUESTED:
        return "Not requested"
    if status == AIExecutionStatus.AUTHENTICATION_FAILED:
        return "Not invoked"
    if status == AIExecutionStatus.PROVIDER_FAILED:
        return "Failed"
    if status in AI_POST_INVOCATION_FAILURE_STATUSES or status == AIExecutionStatus.SUCCEEDED:
        return "Succeeded"
    return "Unknown"


def is_ai_failure_status(status: AIExecutionStatus) -> bool:
    return status in AI_FAILURE_STATUSES
