"""Shared deterministic JSON codecs for assessment and knowledge artifacts."""

from __future__ import annotations

import json
from typing import Any

from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.repository import RepositoryManifest
from codestrata.security.redaction import redact_report_payload
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult


def dumps_stable_json(payload: Any) -> str:
    """Serialize a JSON-compatible payload with stable formatting."""

    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def loads_stable_json(text: str) -> Any:
    """Parse JSON text produced by ``dumps_stable_json``."""

    return json.loads(text)


def repository_manifest_payload(manifest: RepositoryManifest) -> dict[str, Any]:
    return manifest.model_dump(mode="json")


def repository_graph_payload(result: GraphAssessmentPipelineResult) -> dict[str, Any]:
    return result.repository_graph.snapshot.model_dump(mode="json")


def engineering_knowledge_graph_payload(
    result: GraphAssessmentPipelineResult,
) -> dict[str, Any]:
    return result.knowledge_graph.snapshot.model_dump(mode="json")


def knowledge_bindings_payload(result: GraphAssessmentPipelineResult) -> dict[str, Any]:
    return result.binding_result.model_dump(mode="json")


def assessment_graph_payload(result: GraphAssessmentPipelineResult) -> dict[str, Any]:
    return result.assessment_graph.snapshot.model_dump(mode="json")


def graph_summary_payload(result: GraphAssessmentPipelineResult) -> dict[str, Any]:
    # Lazy import avoids a cycle with graph_assessment.artifacts writers.
    from codestrata.services.graph_assessment.artifacts import build_graph_artifact_summary

    return build_graph_artifact_summary(result).model_dump(mode="json")


def findings_payload(evaluation: RuleEvaluationResult) -> dict[str, Any]:
    payload = {
        "finding_count": evaluation.finding_count,
        "findings": [item.model_dump(mode="json") for item in evaluation.findings],
        "rules_evaluated": list(evaluation.rules_evaluated),
        "rules_skipped": list(evaluation.rules_skipped),
    }
    return redact_report_payload(payload)


def recommendations_payload(result: RecommendationResult) -> dict[str, Any]:
    payload = {
        "providers_evaluated": list(result.providers_evaluated),
        "providers_skipped": list(result.providers_skipped),
        "recommendation_count": result.recommendation_count,
        "recommendations": [item.model_dump(mode="json") for item in result.recommendations],
        "unmatched_finding_ids": list(result.unmatched_finding_ids),
        "version": result.version,
    }
    return redact_report_payload(payload)
