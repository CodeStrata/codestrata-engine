"""Canonical normalization and semantic equivalence for assessments."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CompleteAssessmentArtifacts(BaseModel):
    """Transport-neutral semantic assessment content for equivalence checks.

    Built from application/domain artifacts — never from report files.
    Non-semantic fields (run/snapshot/artifact IDs, timestamps, paths) are omitted.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    inventory_paths: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    repository_graph_node_keys: tuple[str, ...] = ()
    repository_graph_edge_keys: tuple[str, ...] = ()
    knowledge_graph_node_keys: tuple[str, ...] = ()
    knowledge_graph_edge_keys: tuple[str, ...] = ()
    assessment_graph_node_keys: tuple[str, ...] = ()
    assessment_graph_edge_keys: tuple[str, ...] = ()
    finding_keys: tuple[str, ...] = ()
    recommendation_keys: tuple[str, ...] = ()
    roadmap_keys: tuple[str, ...] = ()
    findings_count: int = Field(ge=0, default=0)
    recommendations_count: int = Field(ge=0, default=0)
    phases_count: int = Field(ge=0, default=0)
    technologies_count: int = Field(ge=0, default=0)


class AssessmentEquivalenceDifference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str
    code: str
    safe_message: str
    left_value: str | None = None
    right_value: str | None = None


class AssessmentEquivalenceResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    equivalent: bool
    inventory_equivalent: bool
    repository_graph_equivalent: bool
    knowledge_graph_equivalent: bool
    assessment_graph_equivalent: bool
    findings_equivalent: bool
    recommendations_equivalent: bool
    roadmap_equivalent: bool
    differences: tuple[AssessmentEquivalenceDifference, ...] = ()
    normalized_hashes: dict[str, str] = Field(default_factory=dict)
    compared_counts: dict[str, int] = Field(default_factory=dict)


_NON_SEMANTIC_KEYS = frozenset(
    {
        "id",
        "run_id",
        "snapshot_id",
        "artifact_id",
        "execution_id",
        "plan_id",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "timestamp",
        "storage_uri",
        "blob_path",
        "absolute_path",
        "run_directory",
        "html_report_path",
        "json_report_path",
        "report_path",
        "graphs_directory",
        "findings_artifact_path",
        "recommendations_artifact_path",
        "knowledge_run_id",
        "knowledge_snapshot_id",
        "duration_ms",
        "latency_ms",
        "input_tokens",
        "output_tokens",
    }
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def normalize_paths(paths: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    cleaned = sorted({str(path).replace("\\", "/").lstrip("./") for path in paths if path})
    return tuple(cleaned)


def normalize_string_keys(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted({str(item) for item in values if str(item).strip()}))


def strip_non_semantic(mapping: dict[str, Any]) -> dict[str, Any]:
    """Drop known non-semantic keys without removing meaningful fields."""

    return {key: value for key, value in mapping.items() if key not in _NON_SEMANTIC_KEYS}


def artifacts_from_assessment_result(result: Any) -> CompleteAssessmentArtifacts:
    """Build comparable artifacts from AssessmentCommandResult-like objects."""

    findings_count = int(getattr(result, "findings_count", 0) or 0)
    recommendations_count = int(getattr(result, "recommendations_count", 0) or 0)
    phases_count = int(getattr(result, "phases_count", 0) or 0)
    technologies_count = int(getattr(result, "technologies_count", 0) or 0)
    return CompleteAssessmentArtifacts(
        findings_count=findings_count,
        recommendations_count=recommendations_count,
        phases_count=phases_count,
        technologies_count=technologies_count,
        finding_keys=tuple(f"finding:{i}" for i in range(findings_count)),
        recommendation_keys=tuple(f"recommendation:{i}" for i in range(recommendations_count)),
        roadmap_keys=tuple(f"phase:{i}" for i in range(phases_count)),
        technologies=tuple(f"technology:{i}" for i in range(technologies_count)),
        repository_graph_node_keys=tuple(
            f"rgn:{i}" for i in range(int(getattr(result, "repository_graph_node_count", 0) or 0))
        ),
        repository_graph_edge_keys=tuple(
            f"rge:{i}"
            for i in range(int(getattr(result, "repository_graph_relationship_count", 0) or 0))
        ),
        assessment_graph_node_keys=tuple(
            f"agn:{i}" for i in range(int(getattr(result, "assessment_graph_node_count", 0) or 0))
        ),
        assessment_graph_edge_keys=tuple(
            f"age:{i}"
            for i in range(int(getattr(result, "assessment_graph_relationship_count", 0) or 0))
        ),
    )


def artifacts_from_semantic_payloads(
    *,
    inventory_paths: tuple[str, ...] = (),
    technologies: tuple[str, ...] = (),
    repository_graph_node_keys: tuple[str, ...] = (),
    repository_graph_edge_keys: tuple[str, ...] = (),
    knowledge_graph_node_keys: tuple[str, ...] = (),
    knowledge_graph_edge_keys: tuple[str, ...] = (),
    assessment_graph_node_keys: tuple[str, ...] = (),
    assessment_graph_edge_keys: tuple[str, ...] = (),
    finding_keys: tuple[str, ...] = (),
    recommendation_keys: tuple[str, ...] = (),
    roadmap_keys: tuple[str, ...] = (),
) -> CompleteAssessmentArtifacts:
    inv = normalize_paths(inventory_paths)
    techs = normalize_string_keys(technologies)
    findings = normalize_string_keys(finding_keys)
    recs = normalize_string_keys(recommendation_keys)
    roadmap = normalize_string_keys(roadmap_keys)
    return CompleteAssessmentArtifacts(
        inventory_paths=inv,
        technologies=techs,
        repository_graph_node_keys=normalize_string_keys(repository_graph_node_keys),
        repository_graph_edge_keys=normalize_string_keys(repository_graph_edge_keys),
        knowledge_graph_node_keys=normalize_string_keys(knowledge_graph_node_keys),
        knowledge_graph_edge_keys=normalize_string_keys(knowledge_graph_edge_keys),
        assessment_graph_node_keys=normalize_string_keys(assessment_graph_node_keys),
        assessment_graph_edge_keys=normalize_string_keys(assessment_graph_edge_keys),
        finding_keys=findings,
        recommendation_keys=recs,
        roadmap_keys=roadmap,
        findings_count=len(findings),
        recommendations_count=len(recs),
        phases_count=len(roadmap),
        technologies_count=len(techs),
    )


class AssessmentSemanticComparator:
    """Compare deterministic assessment artifacts for semantic equivalence."""

    def __init__(self, *, max_differences: int = 100) -> None:
        self._max_differences = max(1, max_differences)

    def compare(
        self,
        incremental: CompleteAssessmentArtifacts,
        full: CompleteAssessmentArtifacts,
    ) -> AssessmentEquivalenceResult:
        differences: list[AssessmentEquivalenceDifference] = []

        def check_tuple(
            category: str,
            left: tuple[str, ...],
            right: tuple[str, ...],
        ) -> bool:
            if left == right:
                return True
            differences.append(
                AssessmentEquivalenceDifference(
                    category=category,
                    code=f"{category}_mismatch",
                    safe_message=f"{category} semantic keys differ",
                    left_value=f"count={len(left)}",
                    right_value=f"count={len(right)}",
                )
            )
            return False

        inventory_ok = check_tuple("inventory", incremental.inventory_paths, full.inventory_paths)
        # When inventory keys are empty on both sides (count-only artifacts), treat counts.
        if not incremental.inventory_paths and not full.inventory_paths:
            inventory_ok = True

        repo_ok = check_tuple(
            "repository_graph",
            incremental.repository_graph_node_keys + incremental.repository_graph_edge_keys,
            full.repository_graph_node_keys + full.repository_graph_edge_keys,
        )
        knowledge_ok = check_tuple(
            "knowledge_graph",
            incremental.knowledge_graph_node_keys + incremental.knowledge_graph_edge_keys,
            full.knowledge_graph_node_keys + full.knowledge_graph_edge_keys,
        )
        assessment_ok = check_tuple(
            "assessment_graph",
            incremental.assessment_graph_node_keys + incremental.assessment_graph_edge_keys,
            full.assessment_graph_node_keys + full.assessment_graph_edge_keys,
        )
        findings_ok = incremental.findings_count == full.findings_count and check_tuple(
            "findings", incremental.finding_keys, full.finding_keys
        )
        if incremental.finding_keys == full.finding_keys:
            findings_ok = incremental.findings_count == full.findings_count

        recommendations_ok = incremental.recommendations_count == full.recommendations_count and (
            not incremental.recommendation_keys
            and not full.recommendation_keys
            or incremental.recommendation_keys == full.recommendation_keys
        )
        if not recommendations_ok:
            differences.append(
                AssessmentEquivalenceDifference(
                    category="recommendations",
                    code="recommendations_mismatch",
                    safe_message="recommendation semantic content differs",
                    left_value=f"count={incremental.recommendations_count}",
                    right_value=f"count={full.recommendations_count}",
                )
            )

        roadmap_ok = incremental.phases_count == full.phases_count and (
            not incremental.roadmap_keys
            and not full.roadmap_keys
            or incremental.roadmap_keys == full.roadmap_keys
        )
        if not roadmap_ok:
            differences.append(
                AssessmentEquivalenceDifference(
                    category="roadmap",
                    code="roadmap_mismatch",
                    safe_message="roadmap semantic content differs",
                    left_value=f"count={incremental.phases_count}",
                    right_value=f"count={full.phases_count}",
                )
            )

        if incremental.technologies_count != full.technologies_count:
            differences.append(
                AssessmentEquivalenceDifference(
                    category="technologies",
                    code="technologies_mismatch",
                    safe_message="technology counts differ",
                    left_value=str(incremental.technologies_count),
                    right_value=str(full.technologies_count),
                )
            )
            inventory_ok = False

        equivalent = (
            inventory_ok
            and repo_ok
            and knowledge_ok
            and assessment_ok
            and findings_ok
            and recommendations_ok
            and roadmap_ok
            and incremental.technologies_count == full.technologies_count
        )
        hashes = {
            "incremental": canonical_hash(incremental.model_dump(mode="json")),
            "full": canonical_hash(full.model_dump(mode="json")),
        }
        return AssessmentEquivalenceResult(
            equivalent=equivalent,
            inventory_equivalent=inventory_ok,
            repository_graph_equivalent=repo_ok,
            knowledge_graph_equivalent=knowledge_ok,
            assessment_graph_equivalent=assessment_ok,
            findings_equivalent=findings_ok,
            recommendations_equivalent=recommendations_ok,
            roadmap_equivalent=roadmap_ok,
            differences=tuple(differences[: self._max_differences]),
            normalized_hashes=hashes,
            compared_counts={
                "findings": incremental.findings_count,
                "recommendations": incremental.recommendations_count,
                "phases": incremental.phases_count,
                "technologies": incremental.technologies_count,
                "differences": len(differences),
            },
        )
