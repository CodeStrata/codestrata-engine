"""Sanitized machine-readable assessment JSON artifact."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

from codestrata.models import (
    AnalysisResult,
    Finding,
    Recommendation,
    Technology,
)
from codestrata.reporting.ai_execution import AI_EXECUTION_FILENAME
from codestrata.reporting.contract.constants import (
    ASSESSMENT_JSON_REPORT_VERSION,
    ASSESSMENT_JSON_SCHEMA_VERSION,
)
from codestrata.reporting.contract.enums import (
    normalize_effort,
    normalize_priority,
    normalize_risk,
    normalize_severity,
)
from codestrata.reporting.contract.identifiers import (
    remap_related_finding_ids,
    stable_finding_id,
    stable_recommendation_id,
)
from codestrata.reporting.contract.manifest import build_report_manifest
from codestrata.reporting.contract.ordering import (
    sorted_evidence,
    sorted_technologies,
)
from codestrata.reporting.customer_universe import (
    CustomerFinding,
    CustomerRecommendation,
    customer_finding_json,
    customer_recommendation_json,
    resolve_customer_findings,
    resolve_customer_recommendations,
)
from codestrata.reporting.modernization_models import (
    AIExecutionStatus,
    AssessmentTiming,
    ModernizationReportInput,
)
from codestrata.reporting.modernization_view import (
    repository_identifier,
    sanitize_display_path,
)
from codestrata.reporting.traceability import (
    AssessmentTraceabilityError,
    build_assessment_priority_actions,
    build_assessment_roadmap_payload,
    collect_assessment_evidence,
    serialize_evidence_index,
    serialize_priority_actions,
    validate_assessment_traceability,
)
from codestrata.static_analysis.models import StaticAnalysisResult, StaticAnalysisStatus


def build_assessment_json_document(
    report_input: ModernizationReportInput,
) -> dict[str, Any]:
    """Build a sanitized, customer-safe assessment JSON document.

    ``report.json`` is the canonical machine-readable artifact for the
    Evidence → Finding → Recommendation → Priority Action → Roadmap chain
    (Epic 2 Slice 2.6). Companion findings.json / recommendations.json are
    derived from the same customer universe.
    """

    analysis = report_input.analysis_result
    ai_block = _ai_block(report_input)
    static_analysis = _static_analysis_block(analysis.static_analysis_results)
    timing = _timing_block(report_input.timing)
    repository_reference = report_input.repository_reference or repository_identifier(report_input)
    customer_findings = resolve_customer_findings(report_input)
    customer_recommendations = resolve_customer_recommendations(report_input)
    evidence_refs = collect_assessment_evidence(customer_findings)
    evidence_payload = serialize_evidence_index(evidence_refs)
    priority_actions = build_assessment_priority_actions(customer_recommendations)
    priority_actions_payload = serialize_priority_actions(priority_actions)
    executive = _executive_summary_metrics(
        analysis,
        findings=customer_findings,
        recommendations=customer_recommendations,
    )
    comparison = _comparison_payload(analysis)

    technologies = sorted_technologies(analysis.technologies)

    assessment: dict[str, Any] = {
            "mode": report_input.assessment_mode.value,
            "generated_at": _format_timestamp(report_input.generated_at_utc),
            "report_title": report_input.report_title,
            "organization_name": report_input.organization_name,
            "repository": {
                "name": analysis.repository.name,
                "reference": repository_reference,
                "source_type": ("github" if analysis.repository.source_url else "local"),
                "default_branch": analysis.repository.default_branch,
                "file_count": analysis.repository.total_files or len(analysis.repository.files),
            },
            "summary": {
                "technology_count": len(technologies),
                "finding_count": len(customer_findings),
                "deterministic_recommendation_count": len(customer_recommendations),
                "recommendation_count": len(customer_recommendations),
                "priority_action_count": len(priority_actions),
                "evidence_count": len(evidence_payload),
                "ai_recommendation_count": ai_block["recommendation_count"],
                "phase_count": ai_block["phase_count"],
                "ai_executed": report_input.ai_executed,
                "static_analysis_status": static_analysis["status"],
                "findings_by_severity": executive["findings_by_severity"],
                "recommendations_by_priority": executive["recommendations_by_priority"],
                "critical_high_finding_count": executive["critical_high_finding_count"],
                "tests_detected": executive["tests_detected"],
                "ci_detected": executive["ci_detected"],
                "cloud_capabilities": executive["cloud_capabilities"],
                "summary_text": executive["summary_text"],
            },
            "executive_summary": executive,
            "technologies": [_technology_payload(item) for item in technologies],
            "repository_facts": _facts_payload(analysis),
            "evidence": evidence_payload,
            "findings": [customer_finding_json(item) for item in customer_findings],
            "finding_correlations": _finding_correlations_payload(report_input),
            "deterministic_recommendations": [
                customer_recommendation_json(item) for item in customer_recommendations
            ],
            "priority_actions": priority_actions_payload,
            "comparison": comparison,
            "warnings": list(report_input.warnings),
            "static_analysis": static_analysis,
            "ai": {
                "executed": report_input.ai_executed,
                "status": ai_block.get("status"),
                "result_included": ai_block.get("result_included"),
                "provider_invoked": ai_block.get("provider_invoked"),
                "fallback_used": ai_block.get("fallback_used"),
                "stages_completed": ai_block.get("stages_completed"),
                "model_id": ai_block["model_id"],
                "provider": ai_block["provider"],
                "input_tokens": ai_block["input_tokens"],
                "output_tokens": ai_block["output_tokens"],
                "total_tokens": ai_block["total_tokens"],
                "latency_ms": ai_block["latency_ms"],
                "stop_reason": ai_block.get("stop_reason"),
                "executive_summary": ai_block["executive_summary"],
                "overall_assessment": ai_block["overall_assessment"],
                "key_risks": ai_block["key_risks"],
                "recommendations": ai_block["recommendations"],
                "phases": ai_block["phases"],
                "limitations": ai_block["limitations"],
                "evidence_coverage": ai_block["evidence_coverage"],
                "candidate_finding_count": ai_block.get("candidate_finding_count"),
                "included_finding_count": ai_block.get("included_finding_count"),
                "omitted_informational_count": ai_block.get("omitted_informational_count"),
                "static_analysis_profile": ai_block.get("static_analysis_profile"),
                "estimated_input_tokens": ai_block.get("estimated_input_tokens"),
                "failure_code": ai_block.get("failure_code"),
                "failure_message": ai_block.get("failure_message"),
                "failure_detail": ai_block.get("failure_detail"),
                "internal_execution_artifact": ai_block.get("internal_execution_artifact"),
            },
            "ai_enrichment": _ai_enrichment_payload(report_input),
            "timing": timing,
            "coverage": {
                "deterministic_analysis": "completed",
                "static_analysis": static_analysis["status"],
                "ai_interpretation": ai_block.get("status")
                or AIExecutionStatus.NOT_REQUESTED.value,
            },
        }
    if report_input.assessment_activation is not None:
        assessment["activation"] = report_input.assessment_activation
    _attach_optional_section(assessment, "architecture", report_input.architecture_report)
    _attach_optional_section(assessment, "technical_debt", report_input.technical_debt_report)
    _attach_optional_section(assessment, "dependency", report_input.dependency_report)
    _attach_optional_section(assessment, "security", report_input.security_report)
    _attach_optional_section(assessment, "testing", report_input.testing_report)
    _attach_optional_section(assessment, "cloud", report_input.cloud_report)
    _attach_optional_section(assessment, "ai_readiness", report_input.ai_readiness_report)
    _attach_optional_section(assessment, "performance", report_input.performance_report)

    # Canonical roadmap: Priority Action-backed when actions exist; else legacy.
    roadmap_payload = build_assessment_roadmap_payload(
        priority_actions,
        legacy_roadmap=report_input.roadmap_report,
    )
    if roadmap_payload is not None:
        assessment["roadmap"] = roadmap_payload
        assessment["summary"]["roadmap_initiative_count"] = int(
            roadmap_payload.get("initiatives_total")
            or len(roadmap_payload.get("initiatives") or [])
        )
    else:
        assessment["summary"]["roadmap_initiative_count"] = 0

    if priority_actions:
        # PA-backed roadmap is already aligned to the same universe — do not
        # silently filter supporting IDs (Slice 2.6 fail-closed policy).
        pass
    else:
        _align_roadmap_references(assessment)

    try:
        validate_assessment_traceability(assessment)
    except AssessmentTraceabilityError:
        raise

    # Slice 5.4 — additive Assessment-Head Confidence map (schema 1.2 preserved).
    from codestrata.application.assessment_heads import (
        build_assessment_coverage_map,
        build_assessment_head_confidence_map,
    )

    pack_sections = {
        "architecture": assessment.get("architecture"),
        "technical_debt": assessment.get("technical_debt"),
        "dependency": assessment.get("dependency"),
        "security": assessment.get("security"),
        "testing": assessment.get("testing"),
        "cloud": assessment.get("cloud"),
        "ai_readiness": assessment.get("ai_readiness"),
        "performance": assessment.get("performance"),
        "roadmap": assessment.get("roadmap"),
    }
    activation_payload = (
        assessment.get("activation")
        if isinstance(assessment.get("activation"), dict)
        else None
    )
    assessment["assessment_coverage"] = build_assessment_coverage_map(
        pack_sections=pack_sections,
        technologies_present=bool(assessment.get("technologies")),
        activation=activation_payload,
    )
    assessment["assessment_head_confidence"] = build_assessment_head_confidence_map(
        findings=assessment.get("findings") or (),
        pack_sections=pack_sections,
        technologies_present=bool(assessment.get("technologies")),
        activation=activation_payload,
        assessment_coverage_map=assessment["assessment_coverage"],
    )

    repository_id = (
        report_input.knowledge_repository_id
        or f"repo:{analysis.repository.name.strip().lower() or 'repository'}"
    )
    manifest = build_report_manifest(
        generation_mode=report_input.assessment_mode.value,
        repository_id=repository_id,
        scan_id=report_input.knowledge_run_id,
        assessment=assessment,
        generated_at=report_input.generated_at_utc,
    )
    return {
        "schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
        "report_version": ASSESSMENT_JSON_REPORT_VERSION,
        "manifest": manifest,
        "assessment": assessment,
    }


def _finding_correlations_payload(report_input: ModernizationReportInput) -> list[dict[str, Any]]:
    """Serialize additive finding_correlations (Slice 5.12)."""

    stored = tuple(getattr(report_input, "finding_correlations", ()) or ())
    if stored:
        return [dict(item) for item in stored if isinstance(item, dict)]
    evaluation = report_input.assessment_rule_evaluation
    if evaluation is None or not evaluation.findings:
        return []
    from codestrata.application.findings.correlation import correlate_findings

    result = correlate_findings(evaluation.findings)
    return [item.canonical_dict() for item in result.correlations]


def _attach_optional_section(assessment: dict[str, Any], key: str, section: Any) -> None:
    """Attach optional report section; omit when disabled or analytically empty."""

    if section is None:
        return
    payload = section.model_dump(mode="json")
    status = str(payload.get("status") or "").lower()
    if status in {"disabled", "not_requested", "unavailable"}:
        return
    if key == "roadmap":
        initiatives = payload.get("initiatives") or []
        if not initiatives and int(payload.get("initiatives_total") or 0) == 0:
            return
    assessment[key] = payload


def _align_roadmap_references(assessment: dict[str, Any]) -> None:
    """Keep roadmap supporting IDs aligned with report finding/recommendation IDs.

    Roadmap engines may reference Phase-3 graph IDs that are not emitted in the
    customer findings/recommendations arrays. Filter to IDs present in the
    report envelope and re-derive initiative IDs from stable keys so repeated
    runs stay structurally comparable.
    """

    from codestrata.domain.roadmap.identifiers import build_initiative_id

    roadmap = assessment.get("roadmap")
    if not isinstance(roadmap, dict):
        return
    finding_ids = {
        str(item.get("id"))
        for item in (assessment.get("findings") or [])
        if isinstance(item, dict) and item.get("id")
    }
    recommendation_ids = {
        str(item.get("id"))
        for item in (assessment.get("deterministic_recommendations") or [])
        if isinstance(item, dict) and item.get("id")
    }

    def _align_initiative(item: dict[str, Any]) -> tuple[int, str | None, str]:
        dropped = 0
        old_id = str(item.get("initiative_id") or "") or None
        for key, allowed in (
            ("supporting_finding_ids", finding_ids),
            ("supporting_recommendation_ids", recommendation_ids),
        ):
            original = item.get(key) or []
            if not isinstance(original, list):
                continue
            kept = sorted({str(value) for value in original if str(value) in allowed})
            dropped += len(original) - len(kept)
            item[key] = kept
        phase = str(item.get("phase") or "unknown")
        category = str(item.get("category") or "unknown")
        stable_keys = item.get("supporting_recommendation_ids") or []
        if not stable_keys:
            title = str(item.get("title") or item.get("summary") or "initiative")
            stable_keys = [title]
        new_id = build_initiative_id(
            phase=phase,
            category=category,
            recommendation_ids=[str(value) for value in stable_keys],
        )
        item["initiative_id"] = new_id
        return dropped, old_id, new_id

    dropped = 0
    id_map: dict[str, str] = {}
    aligned_items: list[dict[str, Any]] = []

    initiatives = roadmap.get("initiatives")
    if isinstance(initiatives, list):
        for item in initiatives:
            if isinstance(item, dict):
                count, old_id, new_id = _align_initiative(item)
                dropped += count
                if old_id:
                    id_map[old_id] = new_id
                aligned_items.append(item)

    phases = roadmap.get("phases")
    if isinstance(phases, list):
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            nested = phase.get("initiatives")
            if not isinstance(nested, list):
                continue
            for item in nested:
                if isinstance(item, dict):
                    count, old_id, new_id = _align_initiative(item)
                    dropped += count
                    if old_id:
                        id_map[old_id] = new_id
                    aligned_items.append(item)
            phase["initiative_ids"] = [
                str(item.get("initiative_id"))
                for item in nested
                if isinstance(item, dict) and item.get("initiative_id")
            ]

    known_ids = {
        str(item.get("initiative_id"))
        for item in aligned_items
        if item.get("initiative_id")
    }
    for item in aligned_items:
        deps = item.get("depends_on_initiative_ids") or []
        if not isinstance(deps, list):
            continue
        remapped = []
        for dep in deps:
            key = str(dep)
            mapped = id_map.get(key, key)
            if mapped in known_ids:
                remapped.append(mapped)
            else:
                dropped += 1
        item["depends_on_initiative_ids"] = sorted(set(remapped))

    if dropped:
        limitations = list(roadmap.get("limitations") or [])
        note = (
            "Some roadmap supporting finding/recommendation IDs were omitted "
            "because they are not present in the customer report finding/"
            "recommendation lists."
        )
        if note not in limitations:
            limitations.append(note)
        roadmap["limitations"] = limitations


def assessment_json_to_text(document: dict[str, Any], *, indent: int | None = 2) -> str:
    """Serialize an assessment JSON document with stable formatting."""

    from codestrata.security.customer_safe_text import ensure_customer_safe_report_document

    sanitized = ensure_customer_safe_report_document(document)
    text = json.dumps(
        sanitized,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ": ") if indent is not None else (",", ":"),
    )
    return text if text.endswith("\n") else f"{text}\n"


def _executive_summary_metrics(
    analysis: AnalysisResult,
    *,
    findings: tuple[CustomerFinding, ...],
    recommendations: tuple[CustomerRecommendation, ...],
) -> dict[str, Any]:
    severity_counts = Counter(
        "info" if item.severity.lower() == "informational" else item.severity.lower()
        for item in findings
    )
    priority_counts = Counter(
        "critical" if item.priority.lower() == "immediate" else item.priority.lower()
        for item in recommendations
    )
    structure = analysis.facts.structure
    cicd = analysis.facts.cicd
    cloud = analysis.facts.cloud
    critical_high = sum(
        1 for item in findings if item.severity.lower() in {"critical", "high"}
    )
    tests_detected = structure.has_tests if structure is not None else None
    ci_detected = cicd.has_ci if cicd is not None else None
    cloud_capabilities = list(cloud.cloud_capabilities) if cloud is not None else []

    finding_count = len(findings)
    recommendation_count = len(recommendations)
    critical_findings = sum(1 for item in findings if item.severity.lower() == "critical")
    high_recommendations = sum(
        1
        for item in recommendations
        if item.priority.lower() in {"critical", "high", "immediate"}
    )
    parts = [
        (
            f"Analyzed repository '{analysis.repository.name}' with "
            f"{len(analysis.repository.files)} scanned file(s)."
        ),
        (
            f"Detected {finding_count} finding(s) "
            f"({critical_findings} critical) and "
            f"{recommendation_count} recommendation(s) "
            f"({high_recommendations} critical/high priority)."
        ),
    ]
    if tests_detected is not None:
        parts.append(
            "Automated tests were detected."
            if tests_detected
            else "No automated tests were detected."
        )
    if ci_detected is not None:
        parts.append("CI was detected." if ci_detected else "No CI pipeline was detected.")
    if cloud_capabilities:
        parts.append("Cloud capabilities detected: " + ", ".join(cloud_capabilities) + ".")

    return {
        "summary_text": " ".join(parts),
        "finding_count": finding_count,
        "recommendation_count": recommendation_count,
        "file_count": analysis.repository.total_files or len(analysis.repository.files),
        "technology_count": len(analysis.technologies),
        "findings_by_severity": {
            key: severity_counts.get(key, 0)
            for key in ("critical", "high", "medium", "low", "info")
        },
        "recommendations_by_priority": {
            key: priority_counts.get(key, 0) for key in ("critical", "high", "medium", "low")
        },
        "critical_high_finding_count": critical_high,
        "tests_detected": tests_detected,
        "ci_detected": ci_detected,
        "cloud_capabilities": cloud_capabilities,
    }


def _facts_payload(analysis: AnalysisResult) -> dict[str, Any]:
    facts = analysis.facts
    return {
        "structure": facts.structure.model_dump(mode="json") if facts.structure else None,
        "technology": facts.technology.model_dump(mode="json") if facts.technology else None,
        "build": facts.build.model_dump(mode="json") if facts.build else None,
        "dependencies": (
            facts.dependencies.model_dump(mode="json") if facts.dependencies else None
        ),
        "cicd": facts.cicd.model_dump(mode="json") if facts.cicd else None,
        "security": facts.security.model_dump(mode="json") if facts.security else None,
        "architecture": (
            facts.architecture.model_dump(mode="json") if facts.architecture else None
        ),
        "cloud": facts.cloud.model_dump(mode="json") if facts.cloud else None,
    }


def _comparison_payload(analysis: AnalysisResult) -> dict[str, Any] | None:
    comparison = analysis.comparison
    if comparison is None or not comparison.baseline_available:
        return None
    payload = comparison.model_dump(mode="json")
    sanitized = _sanitize_payload_paths(payload)
    assert isinstance(sanitized, dict)
    return sanitized


def _ai_enrichment_payload(report_input: ModernizationReportInput) -> dict[str, Any] | None:
    """First-class Modernization Advisor domain model for report.json consumers."""

    enrichment = report_input.ai_enrichment
    if enrichment is None:
        return None
    return enrichment.model_dump(mode="json")


def _ai_block(report_input: ModernizationReportInput) -> dict[str, Any]:
    budget = None
    if (
        report_input.analysis_context is not None
        and report_input.analysis_context.budget is not None
    ):
        budget = report_input.analysis_context.budget.model_dump(mode="json")

    attempt = report_input.ai_attempt
    stages = [stage.value for stage in attempt.stages_completed] if attempt is not None else []
    budget_fields = {
        "candidate_finding_count": budget.get("candidate_finding_count") if budget else None,
        "included_finding_count": budget.get("included_finding_count") if budget else None,
        "omitted_informational_count": (
            budget.get("omitted_informational_count") if budget else None
        ),
        "static_analysis_profile": (budget.get("static_analysis_profile") if budget else None),
        "estimated_input_tokens": budget.get("estimated_input_tokens") if budget else None,
    }

    if report_input.ai_status != AIExecutionStatus.SUCCEEDED:
        latency_ms = None
        if attempt is not None and attempt.latency_ms is not None:
            latency_ms = attempt.latency_ms
        elif report_input.timing is not None:
            latency_ms = report_input.timing.ai_ms
        return {
            "status": report_input.ai_status.value,
            "executed": False,
            "result_included": False,
            "provider_invoked": report_input.ai_provider_invoked,
            "fallback_used": report_input.ai_fallback_used,
            "stages_completed": stages,
            "recommendation_count": 0,
            "phase_count": 0,
            "model_id": attempt.model_id if attempt is not None else None,
            "provider": attempt.provider if attempt is not None else None,
            "input_tokens": attempt.input_tokens if attempt is not None else None,
            "output_tokens": attempt.output_tokens if attempt is not None else None,
            "total_tokens": attempt.total_tokens if attempt is not None else None,
            "latency_ms": latency_ms,
            "stop_reason": attempt.stop_reason if attempt is not None else None,
            "executive_summary": None,
            "overall_assessment": None,
            "key_risks": [],
            "recommendations": [],
            "phases": [],
            "limitations": [],
            "evidence_coverage": None,
            "failure_code": (attempt.failure_code if attempt is not None else None),
            "failure_message": _sanitize_optional_message(report_input.ai_failure_message),
            "failure_detail": _sanitize_optional_message(
                attempt.failure_detail if attempt is not None else None
            ),
            "internal_execution_artifact": (
                AI_EXECUTION_FILENAME
                if report_input.ai_status != AIExecutionStatus.NOT_REQUESTED
                else None
            ),
            **budget_fields,
        }

    assessment = report_input.assessment_result
    assert assessment is not None
    recommendation = assessment.recommendation_result
    metadata = assessment.model_metadata
    usage = metadata.usage
    return {
        "status": AIExecutionStatus.SUCCEEDED.value,
        "executed": True,
        "result_included": True,
        "provider_invoked": True,
        "fallback_used": False,
        "stages_completed": stages
        or [
            "requested",
            "provider_invoked",
            "response_received",
            "response_parsed",
            "response_validated",
            "result_included",
        ],
        "recommendation_count": len(recommendation.recommendations),
        "phase_count": len(recommendation.modernization_phases),
        "model_id": metadata.model_id,
        "provider": metadata.provider,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "latency_ms": metadata.latency_ms,
        "stop_reason": metadata.stop_reason,
        "executive_summary": recommendation.executive_summary,
        "overall_assessment": recommendation.overall_assessment,
        "key_risks": list(recommendation.key_risks),
        "recommendations": [
            item.model_dump(mode="json") for item in recommendation.recommendations
        ],
        "phases": [item.model_dump(mode="json") for item in recommendation.modernization_phases],
        "limitations": list(recommendation.limitations),
        "evidence_coverage": recommendation.evidence_coverage.model_dump(mode="json"),
        "failure_code": None,
        "failure_message": None,
        "failure_detail": None,
        "internal_execution_artifact": AI_EXECUTION_FILENAME,
        **budget_fields,
    }


def _static_analysis_block(results: list[StaticAnalysisResult]) -> dict[str, Any]:
    if not results:
        return {
            "status": StaticAnalysisStatus.DISABLED.value,
            "providers": [],
            "provider": None,
            "provider_version": None,
            "finding_count": 0,
            "duration_ms": None,
            "message": "Static analysis was not configured for this assessment.",
            "profile": None,
            "rulesets": None,
            "eligible_file_count": 0,
            "files_analyzed": 0,
            "raw_observation_count": 0,
            "grouped_finding_count": 0,
            "primary_count": 0,
            "supporting_count": 0,
            "informational_count": 0,
            "suppressed_from_html_count": 0,
            "observations": [],
            "groups": [],
        }

    primary = results[0]
    providers = [
        {
            "provider_id": item.provider_id,
            "provider": item.provider_name,
            "status": item.status.value,
            "provider_version": item.provider_version,
            "finding_count": len(item.findings),
            "eligible_file_count": item.eligible_file_count,
            "files_analyzed": item.files_analyzed,
            "rulesets": item.command_metadata.get("rulesets"),
            "profile": item.profile or item.command_metadata.get("profile"),
            "duration_ms": item.duration_ms,
            "raw_observation_count": item.raw_observation_count,
            "grouped_finding_count": item.grouped_finding_count,
            "primary_count": item.primary_count,
            "supporting_count": item.supporting_count,
            "informational_count": item.informational_count,
            "suppressed_from_html_count": item.suppressed_from_html_count,
            "message": _sanitize_optional_message(item.error_message),
            "warnings": [
                _sanitize_optional_message(warning) or warning for warning in item.warnings
            ],
        }
        for item in results
    ]
    observations = [
        _observation_payload(observation) for item in results for observation in item.observations
    ]
    groups = [_group_payload(group) for item in results for group in item.groups]
    return {
        "status": primary.status.value,
        "providers": providers,
        "provider": primary.provider_name,
        "provider_version": primary.provider_version,
        "finding_count": sum(len(item.findings) for item in results),
        "duration_ms": primary.duration_ms,
        "message": _sanitize_optional_message(primary.error_message),
        "profile": primary.profile or primary.command_metadata.get("profile"),
        "rulesets": primary.command_metadata.get("rulesets"),
        "eligible_file_count": primary.eligible_file_count,
        "files_analyzed": primary.files_analyzed,
        "raw_observation_count": sum(item.raw_observation_count for item in results),
        "grouped_finding_count": sum(item.grouped_finding_count for item in results),
        "primary_count": sum(item.primary_count for item in results),
        "supporting_count": sum(item.supporting_count for item in results),
        "informational_count": sum(item.informational_count for item in results),
        "suppressed_from_html_count": sum(item.suppressed_from_html_count for item in results),
        "observations": observations,
        "groups": groups,
    }


def _observation_payload(observation: Any) -> dict[str, Any]:
    return {
        "observation_id": observation.observation_id,
        "provider": observation.provider_name,
        "provider_id": observation.provider_id,
        "rule_id": observation.rule_id,
        "external_rule_id": observation.external_rule_id,
        "provider_priority": observation.provider_priority,
        "provider_category": observation.provider_category,
        "normalized_category": observation.normalized_category.value,
        "normalized_severity": observation.normalized_severity.value,
        "customer_visibility": observation.customer_visibility.value,
        "modernization_relevance": observation.modernization_relevance.value,
        "file": sanitize_display_path(observation.file_path),
        "line": observation.line_number,
        "column": observation.column_number,
        "message": observation.message,
        "group_id": observation.group_id,
        "mapping_rationale": observation.mapping_rationale,
    }


def _group_payload(group: Any) -> dict[str, Any]:
    return {
        "group_id": group.group_id,
        "provider": group.provider_name,
        "provider_id": group.provider_id,
        "rule_id": group.rule_id,
        "title": group.title,
        "description": group.description,
        "category": group.category.value,
        "severity": group.severity.value,
        "customer_visibility": group.customer_visibility.value,
        "modernization_relevance": group.modernization_relevance.value,
        "occurrence_count": group.occurrence_count,
        "affected_file_count": group.affected_file_count,
        "representative_locations": [
            {
                "file_path": sanitize_display_path(str(location.get("file_path", ""))),
                "line_number": location.get("line_number"),
                "column_number": location.get("column_number"),
                "message": location.get("message"),
            }
            for location in group.representative_locations
        ],
        "observation_ids": list(group.observation_ids),
        "mapping_rationale": group.mapping_rationale,
    }


def _timing_block(timing: AssessmentTiming | None) -> dict[str, Any] | None:
    if timing is None:
        return None
    return {
        "total_ms": timing.total_ms,
        "scan_ms": timing.scan_ms,
        "analysis_ms": timing.analysis_ms,
        "static_analysis_ms": timing.static_analysis_ms,
        "ai_ms": timing.ai_ms,
        "report_ms": timing.report_ms,
        "graph_ms": timing.graph_ms,
        "rules_ms": timing.rules_ms,
        "evidence_ms": timing.evidence_ms,
        "knowledge_ms": timing.knowledge_ms,
        "files_loaded": timing.files_loaded,
        "files_skipped": timing.files_skipped,
        "cache_hits": timing.cache_hits,
        "cache_misses": timing.cache_misses,
        "peak_rss_mb": timing.peak_rss_mb,
    }


def _technology_payload(tech: Technology) -> dict[str, Any]:
    return {
        "name": tech.name,
        "category": str(getattr(tech.category, "value", tech.category)),
        "version": tech.version,
        "confidence": tech.confidence,
        "source": tech.source,
    }


def _dedupe_by_stable_id(
    items: list[Any],
    *,
    key: Any,
) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for item in items:
        sid = str(key(item))
        if sid in seen:
            continue
        seen.add(sid)
        out.append(item)
    return out


def _finding_payload(finding: Finding) -> dict[str, Any]:
    evidence_items = sorted_evidence(
        [
            {
                "file_path": sanitize_display_path(item.file_path),
                "line_number": item.line_number,
                "column_number": item.column_number,
                "description": item.description,
            }
            for item in finding.evidence
        ]
    )
    # Deduplicate identical evidence rows.
    deduped_evidence: list[dict[str, Any]] = []
    seen_evidence: set[tuple[Any, ...]] = set()
    for item in evidence_items:
        key = (
            item.get("file_path"),
            item.get("line_number"),
            item.get("column_number"),
            item.get("description"),
        )
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        deduped_evidence.append(item)
    return {
        "id": stable_finding_id(finding),
        "rule_id": finding.rule_id,
        "title": finding.title,
        "description": finding.description,
        "category": str(getattr(finding.category, "value", finding.category)),
        "severity": normalize_severity(finding.severity),
        "source": str(getattr(finding.source, "value", finding.source)),
        "affected_technologies": sorted(
            {str(item) for item in finding.affected_technologies}
        ),
        "evidence": deduped_evidence,
        "provider_name": finding.metadata.get("provider_name"),
        "customer_visibility": finding.metadata.get("customer_visibility"),
        "modernization_relevance": finding.metadata.get("modernization_relevance"),
        "group_id": finding.metadata.get("group_id"),
        "occurrence_count": finding.metadata.get("occurrence_count"),
        "affected_file_count": finding.metadata.get("affected_file_count"),
        "provider_priority": finding.metadata.get("original_priority"),
        "provider_category": finding.metadata.get("ruleset"),
    }


def _recommendation_payload(
    recommendation: Recommendation,
    *,
    finding_id_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    id_map = finding_id_map or {}
    related = list(
        remap_related_finding_ids(recommendation.related_finding_ids, id_map)
    )
    return {
        "id": stable_recommendation_id(recommendation),
        "rule_id": recommendation.rule_id,
        "title": recommendation.title,
        "description": recommendation.description,
        "rationale": recommendation.rationale,
        "priority": normalize_priority(recommendation.priority),
        "category": str(getattr(recommendation.category, "value", recommendation.category)),
        "effort": normalize_effort(recommendation.effort),
        "risk": normalize_risk(recommendation.risk),
        "related_finding_ids": related,
        "actions": list(recommendation.actions),
        "dependencies": list(recommendation.dependencies),
        "evidence": [
            {
                "file_path": sanitize_display_path(item.file_path),
                "line_number": item.line_number,
                "column_number": item.column_number,
                "description": item.description,
            }
            for item in recommendation.evidence
        ],
    }


def _sanitize_payload_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_payload_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload_paths(item) for item in value]
    if isinstance(value, str):
        if "/" in value or "\\" in value:
            candidate = sanitize_display_path(value)
            if candidate != value and (
                value.startswith("/") or (len(value) >= 3 and value[1] == ":")
            ):
                return candidate
            return _strip_absolute_paths(value)
        return value
    return value


def _sanitize_optional_message(message: str | None) -> str | None:
    if message is None:
        return None
    compact = " ".join(message.split())
    sanitized = _strip_absolute_paths(compact)
    if len(sanitized) > 400:
        return sanitized[:397] + "..."
    return sanitized


def _strip_absolute_paths(value: str) -> str:
    without_posix = re.sub(r"(?<!\w)/(?:[^/\s]+/)+[^/\s]+", "<path>", value)
    return re.sub(
        r"(?<!\w)[A-Za-z]:\\(?:[^\\\s]+\\)+[^\\\s]+",
        "<path>",
        without_posix,
    )


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(tz=value.tzinfo).isoformat().replace("+00:00", "Z")


# Explicit re-exports for callers that import versions from this module.
__all__ = [
    "ASSESSMENT_JSON_REPORT_VERSION",
    "ASSESSMENT_JSON_SCHEMA_VERSION",
    "assessment_json_to_text",
    "build_assessment_json_document",
]