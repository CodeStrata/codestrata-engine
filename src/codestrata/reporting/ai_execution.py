"""Internal AI execution artifact for observability and evaluation."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from codestrata.ai.agents.models import AGENT_NAME, AGENT_VERSION, ModernizationAssessmentResult
from codestrata.ai.contracts.models import LLM_CONTRACT_SCHEMA_VERSION, LLMAnalysisContext
from codestrata.ai.prompts.models import DEFAULT_PROMPT_TEMPLATE_VERSION
from codestrata.ai.recommendations.models import (
    AI_RECOMMENDATION_SCHEMA_VERSION,
    AIRecommendationResult,
)
from codestrata.ai.recommendations.validation import DeterministicRecommendationNormalizationRemoval
from codestrata.reporting.ai_status import failure_code_for_status
from codestrata.reporting.modernization_models import AIAttemptInfo, AIExecutionStatus

logger = logging.getLogger(__name__)

AI_EXECUTION_FILENAME = "advisor-execution.json"
AI_EXECUTION_SCHEMA_VERSION = "1.0.0"
AI_EXECUTION_ARTIFACT = "advisor-execution"

_CREDENTIAL_KEY_FRAGMENTS = (
    "credential",
    "secret",
    "password",
    "authorization",
    "auth_header",
    "access_key",
    "session_token",
    "aws_access",
    "aws_secret",
    "sso",
    "signing",
    "signature",
    "api_token",
    "bearer",
)


def stable_content_hash(payload: str | bytes | dict[str, Any] | list[Any]) -> str:
    """Return a stable SHA-256 hex digest for JSON-ready content."""

    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_ai_execution_document(
    *,
    status: AIExecutionStatus,
    attempt: AIAttemptInfo | None,
    analysis_context: LLMAnalysisContext | None = None,
    assessment_result: ModernizationAssessmentResult | None = None,
    raw_model_text: str | None = None,
    parsed_model_response: dict[str, Any] | None = None,
    accepted_ai_result: AIRecommendationResult | None = None,
    normalization_removals: (
        Sequence[DeterministicRecommendationNormalizationRemoval] | None
    ) = None,
    prompt_template_version: str | None = None,
    prompt_hash: str | None = None,
    context_hash: str | None = None,
    failure_message: str | None = None,
    failure_detail: str | None = None,
    failure_stage: str | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Build the internal ``advisor-execution.json`` document.

    Distinguishes raw provider text, pre-acceptance parsed JSON, and the final
    CodeStrata-accepted recommendation result. Does not persist full prompt bodies.
    """

    moment = timestamp if timestamp is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)

    accepted = accepted_ai_result
    if accepted is None and assessment_result is not None:
        accepted = assessment_result.recommendation_result

    raw_text = raw_model_text
    if raw_text is None and assessment_result is not None:
        raw_text = assessment_result.raw_model_response

    parsed = parsed_model_response
    if parsed is None and assessment_result is not None:
        parsed = assessment_result.parsed_model_response

    removals = _normalize_removals(
        normalization_removals,
        assessment_result=assessment_result,
    )

    provider = attempt.provider if attempt is not None else None
    model_id = attempt.model_id if attempt is not None else None
    if assessment_result is not None:
        provider = provider or assessment_result.model_metadata.provider
        model_id = model_id or assessment_result.model_metadata.model_id

    stages = [stage.value for stage in attempt.stages_completed] if attempt is not None else []
    latency_ms = attempt.latency_ms if attempt is not None else None
    input_tokens = attempt.input_tokens if attempt is not None else None
    output_tokens = attempt.output_tokens if attempt is not None else None
    total_tokens = attempt.total_tokens if attempt is not None else None
    stop_reason = attempt.stop_reason if attempt is not None else None
    if assessment_result is not None:
        metadata = assessment_result.model_metadata
        usage = metadata.usage
        latency_ms = latency_ms if latency_ms is not None else metadata.latency_ms
        input_tokens = input_tokens if input_tokens is not None else usage.input_tokens
        output_tokens = output_tokens if output_tokens is not None else usage.output_tokens
        total_tokens = total_tokens if total_tokens is not None else usage.total_tokens
        stop_reason = stop_reason if stop_reason is not None else metadata.stop_reason

    provider_invoked = _provider_invoked(status=status, attempt=attempt, raw_text=raw_text)

    resolved_context_hash = context_hash
    if resolved_context_hash is None and analysis_context is not None:
        resolved_context_hash = stable_content_hash(analysis_context.model_dump(mode="json"))

    resolved_prompt_version = (
        prompt_template_version
        or (assessment_result.prompt_template_version if assessment_result is not None else None)
        or DEFAULT_PROMPT_TEMPLATE_VERSION
    )
    resolved_prompt_hash = prompt_hash
    if resolved_prompt_hash is None and assessment_result is not None:
        resolved_prompt_hash = assessment_result.prompt_hash

    context_block = _context_block(
        analysis_context,
        context_hash=resolved_context_hash,
        prompt_template_version=resolved_prompt_version,
        prompt_hash=resolved_prompt_hash,
    )

    authoritative_coverage = None
    if accepted is not None:
        authoritative_coverage = accepted.evidence_coverage.model_dump(mode="json")

    failure_block = None
    if status != AIExecutionStatus.SUCCEEDED:
        failure_block = {
            "code": (
                attempt.failure_code
                if attempt is not None and attempt.failure_code
                else failure_code_for_status(status)
            ),
            "message": failure_message,
            "detail": (
                failure_detail
                if failure_detail is not None
                else (attempt.failure_detail if attempt is not None else None)
            ),
            "stage": failure_stage or _failure_stage(status),
        }

    if removals:
        normalization_block: dict[str, Any] | None = {
            "removed_unknown_deterministic_recommendation_ids": [
                {
                    "recommendation_id": item.recommendation_id,
                    "removed_ids": list(item.removed_ids),
                }
                for item in removals
            ]
        }
    else:
        normalization_block = None

    document: dict[str, Any] = {
        "artifact": AI_EXECUTION_ARTIFACT,
        "schema_version": AI_EXECUTION_SCHEMA_VERSION,
        "timestamp_utc": moment.isoformat().replace("+00:00", "Z"),
        "execution_status": status.value,
        "provider": provider,
        "model_id": model_id,
        "agent": {
            "name": (
                assessment_result.trace.agent_name if assessment_result is not None else AGENT_NAME
            ),
            "version": (
                assessment_result.trace.agent_version
                if assessment_result is not None
                else AGENT_VERSION
            ),
        },
        "schemas": {
            "context": (
                analysis_context.schema_version
                if analysis_context is not None
                else LLM_CONTRACT_SCHEMA_VERSION
            ),
            "recommendation": AI_RECOMMENDATION_SCHEMA_VERSION,
            "prompt_template": resolved_prompt_version,
        },
        "execution": {
            "provider_invoked": provider_invoked,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "stop_reason": stop_reason,
            "stages_completed": stages,
        },
        "context": context_block,
        "raw_model_text": raw_text,
        "parsed_model_response": parsed,
        "accepted_ai_result": (accepted.model_dump(mode="json") if accepted is not None else None),
        "normalization": normalization_block,
        "authoritative_evidence_coverage": authoritative_coverage,
        "failure": failure_block,
    }
    return cast(dict[str, Any], _strip_credential_fields(document))


def write_ai_execution_artifact(run_directory: Path, document: dict[str, Any]) -> Path:
    """Write ``advisor-execution.json`` under the assessment run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / AI_EXECUTION_FILENAME
    sanitized = _strip_credential_fields(document)
    text = json.dumps(
        sanitized,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ": "),
    )
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def try_write_ai_execution_artifact(
    run_directory: Path,
    document: dict[str, Any],
) -> Path | None:
    """Write the execution artifact; return None and log on failure."""

    try:
        return write_ai_execution_artifact(run_directory, document)
    except Exception as error:  # noqa: BLE001 - artifact must not fail assessment
        logger.warning(
            "Failed to write AI execution artifact: %s",
            error,
            exc_info=True,
        )
        return None


def _normalize_removals(
    normalization_removals: Sequence[DeterministicRecommendationNormalizationRemoval] | None,
    *,
    assessment_result: ModernizationAssessmentResult | None,
) -> tuple[DeterministicRecommendationNormalizationRemoval, ...]:
    if normalization_removals is not None:
        return tuple(normalization_removals)
    if assessment_result is not None:
        return tuple(assessment_result.normalization_removals)
    return ()


def _context_block(
    analysis_context: LLMAnalysisContext | None,
    *,
    context_hash: str | None,
    prompt_template_version: str,
    prompt_hash: str | None,
) -> dict[str, Any]:
    budget = analysis_context.budget if analysis_context is not None else None
    truncated = False
    if analysis_context is not None:
        truncated = bool(analysis_context.findings_truncation.truncated)
    return {
        "candidate_finding_count": (budget.candidate_finding_count if budget is not None else None),
        "included_finding_count": (
            budget.included_finding_count
            if budget is not None
            else (
                analysis_context.findings_truncation.included_count
                if analysis_context is not None
                else None
            )
        ),
        "omitted_informational_count": (
            budget.omitted_informational_count if budget is not None else None
        ),
        "estimated_input_tokens": (budget.estimated_input_tokens if budget is not None else None),
        "static_analysis_profile": (budget.static_analysis_profile if budget is not None else None),
        "input_truncated": truncated,
        "context_hash": context_hash,
        "prompt_template_version": prompt_template_version,
        "prompt_hash": prompt_hash,
    }


def _provider_invoked(
    *,
    status: AIExecutionStatus,
    attempt: AIAttemptInfo | None,
    raw_text: str | None,
) -> bool:
    if status == AIExecutionStatus.SUCCEEDED:
        return True
    if raw_text is not None:
        return True
    if attempt is None:
        return False
    if attempt.input_tokens is not None or attempt.output_tokens is not None:
        return True
    if attempt.stop_reason is not None:
        return True
    return status in {
        AIExecutionStatus.PARSING_FAILED,
        AIExecutionStatus.VALIDATION_FAILED,
    }


def _failure_stage(status: AIExecutionStatus) -> str | None:
    mapping = {
        AIExecutionStatus.AUTHENTICATION_FAILED: "authentication",
        AIExecutionStatus.PROVIDER_FAILED: "provider",
        AIExecutionStatus.PARSING_FAILED: "parsing",
        AIExecutionStatus.VALIDATION_FAILED: "validation",
    }
    return mapping.get(status)


def _strip_credential_fields(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in _CREDENTIAL_KEY_FRAGMENTS):
                continue
            cleaned[key] = _strip_credential_fields(item)
        return cleaned
    if isinstance(value, list):
        return [_strip_credential_fields(item) for item in value]
    return value
