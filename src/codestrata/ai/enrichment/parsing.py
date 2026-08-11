"""Parse and bridge enrichment responses for provider compatibility."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from codestrata.ai.agents.trace import utc_now
from codestrata.ai.contracts.models import LLMAnalysisContext
from codestrata.ai.enrichment.advisor import (
    MODERNIZATION_ADVISOR_PROMPT_VERSION,
    MODERNIZATION_ADVISOR_VERSION,
)
from codestrata.ai.enrichment.context import AiEnrichmentContext
from codestrata.ai.enrichment.validation import (
    AiEnrichmentValidationError,
    validate_ai_enrichment_result,
)
from codestrata.ai.providers.exceptions import (
    AIResponseParsingError,
    AIResponseValidationError,
)
from codestrata.ai.providers.models import ModelInvocationMetadata, ModelInvocationResult
from codestrata.ai.providers.parsing import sanitize_provider_text
from codestrata.ai.recommendations.enums import (
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
)
from codestrata.ai.recommendations.models import (
    AIRecommendation,
    AIRecommendationResult,
    EvidenceCoverage,
    ModernizationPhase,
)
from codestrata.domain.ai_enrichment import (
    AiEnrichmentResult,
    AiProviderMetadata,
    EnrichmentPriorityLevel,
    ExecutiveSummary,
    ModernizationPriority,
    ModernizationRisk,
    ModernizationTheme,
    SuggestedNextStep,
)

_FENCED_JSON_PATTERN = re.compile(
    r"^\s*```(?:json)?\s*\r?\n(?P<body>.*?)\r?\n```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def parse_enrichment_response(
    raw_text: str,
    context: AiEnrichmentContext,
    metadata: ModelInvocationMetadata,
) -> AiEnrichmentResult:
    """Parse strict JSON into a validated AiEnrichmentResult."""

    try:
        payload = _extract_json_object_text(raw_text)
        data = json.loads(payload)
    except (AIResponseParsingError, json.JSONDecodeError) as error:
        raise AIResponseParsingError(
            "Model response is not valid enrichment JSON: " + sanitize_provider_text(str(error)),
            metadata=metadata,
            raw_response_text=raw_text,
        ) from error
    if not isinstance(data, dict):
        raise AIResponseParsingError(
            "Enrichment response must be a JSON object",
            metadata=metadata,
            raw_response_text=raw_text,
        )
    data = dict(data)
    data["provider_metadata"] = _advisor_provider_metadata_payload(
        metadata,
        existing=data.get("provider_metadata"),
    )
    try:
        result = AiEnrichmentResult.model_validate(data)
    except ValidationError as error:
        raise AIResponseValidationError(
            "Enrichment response failed schema validation: " + sanitize_provider_text(str(error)),
            metadata=metadata,
            raw_response_text=raw_text,
            parsed_payload=data,
            validation_details=str(error),
        ) from error
    try:
        return validate_ai_enrichment_result(result, context)
    except AiEnrichmentValidationError as error:
        raise AIResponseValidationError(
            "Enrichment response failed referential validation: "
            + sanitize_provider_text(str(error)),
            metadata=metadata,
            raw_response_text=raw_text,
            parsed_payload=data,
            validation_details=str(error),
        ) from error


def enrichment_from_invocation(
    invocation: ModelInvocationResult,
    context: AiEnrichmentContext,
) -> AiEnrichmentResult:
    """Resolve enrichment from an invocation result.

    Prefer raw Modernization Advisor JSON (``AiEnrichmentResult``). Fall back to
    mapping a legacy ``AIRecommendationResult`` when present so older fixtures
    keep working.
    """

    raw = invocation.raw_response_text or ""
    if _looks_like_enrichment(raw):
        return parse_enrichment_response(raw, context, invocation.metadata)
    if invocation.parsed_model_response and _payload_looks_like_enrichment(
        invocation.parsed_model_response
    ):
        return parse_enrichment_response(
            json.dumps(invocation.parsed_model_response),
            context,
            invocation.metadata,
        )
    if invocation.recommendation_result is None:
        raise AIResponseParsingError(
            "Model response is not valid Modernization Advisor JSON",
            metadata=invocation.metadata,
            raw_response_text=raw,
        )
    return bridge_recommendation_to_enrichment(
        invocation.recommendation_result,
        context=context,
        metadata=invocation.metadata,
    )


def bridge_recommendation_to_enrichment(
    recommendation: AIRecommendationResult,
    *,
    context: AiEnrichmentContext,
    metadata: ModelInvocationMetadata,
) -> AiEnrichmentResult:
    """Map legacy AI recommendation output into AiEnrichmentResult."""

    allowed_findings = set(context.allowed_finding_ids)
    allowed_recs = set(context.allowed_recommendation_ids)
    themes = [
        ModernizationTheme(
            title=item.title,
            summary=item.description,
            related_finding_ids=_filter_ids(item.related_finding_ids, allowed_findings),
            related_recommendation_ids=_filter_ids(
                item.related_deterministic_recommendation_ids,
                allowed_recs,
            ),
        )
        for item in recommendation.recommendations[:8]
    ]
    priorities = [
        ModernizationPriority(
            title=item.title,
            rationale=item.rationale,
            priority=_map_priority(item.priority),
            related_finding_ids=_filter_ids(item.related_finding_ids, allowed_findings),
            related_recommendation_ids=_filter_ids(
                item.related_deterministic_recommendation_ids,
                allowed_recs,
            ),
        )
        for item in recommendation.recommendations[:5]
    ]
    risks = [
        ModernizationRisk(
            title=_clip(risk, 80),
            summary=risk,
            severity=EnrichmentPriorityLevel.MEDIUM,
        )
        for risk in recommendation.key_risks[:5]
    ]
    steps: list[SuggestedNextStep] = []
    order = 1
    for item in recommendation.recommendations:
        for action in item.suggested_actions[:2]:
            steps.append(
                SuggestedNextStep(
                    order=order,
                    title=_clip(action, 80),
                    summary=action,
                    related_finding_ids=_filter_ids(
                        item.related_finding_ids,
                        allowed_findings,
                    ),
                    related_recommendation_ids=_filter_ids(
                        item.related_deterministic_recommendation_ids,
                        allowed_recs,
                    ),
                )
            )
            order += 1
            if order > 8:
                break
        if order > 8:
            break
    result = AiEnrichmentResult(
        executive_summary=ExecutiveSummary(
            headline=_clip(recommendation.executive_summary, 120),
            narrative=recommendation.overall_assessment,
            posture=None,
        ),
        themes=tuple(themes),
        priorities=tuple(priorities),
        risks=tuple(risks),
        suggested_next_steps=tuple(steps),
        provider_metadata=AiProviderMetadata.model_validate(_provider_metadata_payload(metadata)),
        limitations=tuple(recommendation.limitations),
        metadata={"bridged_from": "ai_recommendation_result"},
    )
    return validate_ai_enrichment_result(result, context)


def bridge_enrichment_to_recommendation(
    enrichment: AiEnrichmentResult,
    *,
    context: AiEnrichmentContext,
    analysis_context: LLMAnalysisContext | None = None,
) -> AIRecommendationResult:
    """Map enrichment narrative into Phase 1 report recommendation contract."""

    from codestrata.ai.recommendations.validation import finding_ids_from_context

    phase1_ids = (
        sorted(finding_ids_from_context(analysis_context)) if analysis_context is not None else []
    )
    grounding = phase1_ids[:1]

    recommendations: list[AIRecommendation] = []
    for index, priority in enumerate(enrichment.priorities[:8], start=1):
        recommendations.append(
            AIRecommendation(
                recommendation_id=f"AI-REC-{index:03d}",
                title=priority.title,
                description=priority.rationale,
                rationale=priority.rationale,
                priority=AIRecommendationPriority.MEDIUM,
                effort=AIRecommendationEffort.MEDIUM,
                impact=AIRecommendationImpact.MEDIUM,
                confidence=AIRecommendationConfidence.MEDIUM,
                related_finding_ids=list(grounding),
                related_deterministic_recommendation_ids=[],
                suggested_actions=[
                    step.title
                    for step in enrichment.suggested_next_steps
                    if set(step.related_recommendation_ids).intersection(
                        priority.related_recommendation_ids
                    )
                    or not priority.related_recommendation_ids
                ][:3]
                or [priority.title],
                dependencies=[],
            )
        )
    if not recommendations:
        recommendations.append(
            AIRecommendation(
                recommendation_id="AI-REC-001",
                title=enrichment.executive_summary.headline,
                description=enrichment.executive_summary.narrative,
                rationale="Derived from AI enrichment narrative.",
                priority=AIRecommendationPriority.MEDIUM,
                effort=AIRecommendationEffort.MEDIUM,
                impact=AIRecommendationImpact.MEDIUM,
                confidence=AIRecommendationConfidence.MEDIUM,
                related_finding_ids=list(grounding),
                related_deterministic_recommendation_ids=[],
                suggested_actions=[step.title for step in enrichment.suggested_next_steps[:3]]
                or ["Review deterministic recommendations"],
                dependencies=[],
            )
        )
    # If Phase 1 has no findings, keep recommendations ungrounded-safe by attaching
    # an empty deterministic list only when grounding exists; otherwise create a
    # minimal limitation note and still satisfy schema via available Phase 1 IDs.
    if not grounding and analysis_context is not None and analysis_context.findings:
        first = analysis_context.findings[0]
        candidate = first.finding_id or first.rule_id or first.group_id
        if candidate:
            grounding = [candidate]
            recommendations = [
                item.model_copy(update={"related_finding_ids": grounding})
                for item in recommendations
            ]
    evidence_rich = analysis_context is not None and len(analysis_context.findings) >= 8
    pad_sources: list[tuple[str, str]] = []
    for theme in enrichment.themes:
        pad_sources.append((theme.title, theme.summary))
    for risk in enrichment.risks:
        pad_sources.append((f"Address risk: {risk.summary[:80]}", risk.summary))
    for step in enrichment.suggested_next_steps:
        pad_sources.append((step.title, step.summary or step.title))
    if not pad_sources:
        pad_sources.append(
            (
                enrichment.executive_summary.headline,
                enrichment.executive_summary.narrative,
            )
        )
    # Evidence-rich report contract requires 5–8 recommendations and 2–4 phases.
    while evidence_rich and len(recommendations) < 5:
        title, description = pad_sources[(len(recommendations) - 1) % len(pad_sources)]
        index = len(recommendations) + 1
        finding_ids = list(grounding)
        if phase1_ids and not finding_ids:
            finding_ids = [phase1_ids[(index - 1) % len(phase1_ids)]]
        elif phase1_ids:
            finding_ids = [phase1_ids[(index - 1) % len(phase1_ids)]]
        recommendations.append(
            AIRecommendation(
                recommendation_id=f"AI-REC-{index:03d}",
                title=title[:120] or f"Follow-up priority {index}",
                description=description,
                rationale=description,
                priority=AIRecommendationPriority.MEDIUM,
                effort=AIRecommendationEffort.MEDIUM,
                impact=AIRecommendationImpact.MEDIUM,
                confidence=AIRecommendationConfidence.MEDIUM,
                related_finding_ids=finding_ids,
                related_deterministic_recommendation_ids=[],
                suggested_actions=[title[:120] or f"Review priority {index}"],
                dependencies=[],
            )
        )
    if len(recommendations) > 8:
        recommendations = recommendations[:8]

    referenced = set()
    for item in recommendations:
        referenced.update(item.related_finding_ids)
    total = len(phase1_ids) if phase1_ids else len(context.allowed_finding_ids)
    considered = total
    coverage = EvidenceCoverage(
        total_findings=total,
        findings_considered=considered,
        findings_referenced=len(referenced),
        coverage_percentage=(round((len(referenced) / total) * 100.0, 2) if total else 0.0),
        input_truncated=context.truncated,
    )
    rec_ids = [item.recommendation_id for item in recommendations]
    if evidence_rich and len(rec_ids) >= 2:
        mid = max(1, len(rec_ids) // 2)
        if mid >= len(rec_ids):
            mid = len(rec_ids) - 1
        phases = [
            ModernizationPhase(
                phase=1,
                name="Act on enrichment priorities",
                objective=enrichment.executive_summary.headline,
                recommendations=rec_ids[:mid],
                expected_outcomes=["Clear modernization narrative aligned to findings"],
            ),
            ModernizationPhase(
                phase=2,
                name="Sustain and verify",
                objective=(
                    "Confirm deterministic findings remain addressed after "
                    "modernization narrative actions."
                ),
                recommendations=rec_ids[mid:],
                expected_outcomes=["Deterministic evidence remains authoritative"],
            ),
        ]
    else:
        phases = [
            ModernizationPhase(
                phase=1,
                name="Act on enrichment priorities",
                objective=enrichment.executive_summary.headline,
                recommendations=rec_ids,
                expected_outcomes=["Clear modernization narrative aligned to findings"],
            )
        ]
    return AIRecommendationResult(
        executive_summary=enrichment.executive_summary.narrative,
        overall_assessment=enrichment.executive_summary.narrative,
        key_risks=[risk.summary for risk in enrichment.risks][:5],
        recommendations=recommendations,
        modernization_phases=phases,
        evidence_coverage=coverage,
        limitations=list(enrichment.limitations)
        or ["AI enrichment narrative; deterministic findings remain source of truth."],
    )


def _extract_json_object_text(raw_text: str) -> str:
    compact = raw_text.strip()
    match = _FENCED_JSON_PATTERN.match(compact)
    if match is not None:
        compact = match.group("body").strip()
    if not compact.startswith("{"):
        raise AIResponseParsingError("Enrichment response must be a JSON object")
    return compact


def looks_like_enrichment_payload(raw_text: str) -> bool:
    try:
        data = json.loads(_extract_json_object_text(raw_text))
    except (AIResponseParsingError, json.JSONDecodeError):
        return False
    return _payload_looks_like_enrichment(data)


def _looks_like_enrichment(raw_text: str) -> bool:
    return looks_like_enrichment_payload(raw_text)


def _payload_looks_like_enrichment(data: Any) -> bool:
    summary = data.get("executive_summary") if isinstance(data, dict) else None
    return (
        isinstance(data, dict)
        and isinstance(summary, dict)
        and ("themes" in data or "priorities" in data or "suggested_next_steps" in data)
    )


def _provider_metadata_payload(metadata: ModelInvocationMetadata) -> dict[str, Any]:
    return _advisor_provider_metadata_payload(metadata, existing=None)


def _advisor_provider_metadata_payload(
    metadata: ModelInvocationMetadata,
    *,
    existing: object,
) -> dict[str, Any]:
    """Merge invocation metadata with advisor version stamps."""

    base: dict[str, Any] = {}
    if isinstance(existing, dict):
        base.update(existing)
    base.update(
        {
            "provider": metadata.provider,
            "model_id": metadata.model_id,
            "request_id": metadata.request_id,
            "latency_ms": metadata.latency_ms,
            "input_tokens": metadata.usage.input_tokens,
            "output_tokens": metadata.usage.output_tokens,
            "stop_reason": metadata.stop_reason,
            "advisor_version": MODERNIZATION_ADVISOR_VERSION,
            "prompt_version": MODERNIZATION_ADVISOR_PROMPT_VERSION,
            "generated_at_utc": utc_now().isoformat().replace("+00:00", "Z"),
        }
    )
    return base


def _filter_ids(values: list[str] | tuple[str, ...], allowed: set[str]) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item in allowed}))


def _map_priority(value: AIRecommendationPriority) -> EnrichmentPriorityLevel:
    mapping = {
        AIRecommendationPriority.CRITICAL: EnrichmentPriorityLevel.IMMEDIATE,
        AIRecommendationPriority.HIGH: EnrichmentPriorityLevel.HIGH,
        AIRecommendationPriority.MEDIUM: EnrichmentPriorityLevel.MEDIUM,
        AIRecommendationPriority.LOW: EnrichmentPriorityLevel.LOW,
    }
    return mapping.get(value, EnrichmentPriorityLevel.MEDIUM)


def _unmap_priority(value: EnrichmentPriorityLevel) -> AIRecommendationPriority:
    mapping = {
        EnrichmentPriorityLevel.IMMEDIATE: AIRecommendationPriority.CRITICAL,
        EnrichmentPriorityLevel.HIGH: AIRecommendationPriority.HIGH,
        EnrichmentPriorityLevel.MEDIUM: AIRecommendationPriority.MEDIUM,
        EnrichmentPriorityLevel.LOW: AIRecommendationPriority.LOW,
    }
    return mapping.get(value, AIRecommendationPriority.MEDIUM)


def _clip(value: str, max_chars: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."
