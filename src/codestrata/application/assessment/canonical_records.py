"""Seal baseline M22/M25/M26 and trust records during assess.

Production report generation copies these metadata keys. It must not
re-observe live HEAD when the keys are present.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codestrata.domain.contracts.envelope import CapabilityCoverage, CapabilityFreshness
from codestrata.domain.contracts.hotspot import (
    ChangeSummary,
    EngineeringHotspot,
    OwnershipConcentration,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.infrastructure.knowledge_store.git_revision import (
    observe_local_git_state,
    observe_repository_revision,
)
from codestrata.models.analysis_result import AnalysisResult
from codestrata.reporting.journey_observations import JourneyObservation, observe_repository

CANONICAL_HOTSPOTS_KEY = "canonical_hotspots"
CANONICAL_OWNERSHIP_KEY = "canonical_ownership"
CANONICAL_COCHANGE_KEY = "canonical_cochange"
CANONICAL_COVERAGE_KEY = "canonical_coverage"
CANONICAL_FRESHNESS_KEY = "canonical_freshness"
CANONICAL_CHANGE_SUMMARY_KEY = "canonical_change_summary"
CANONICAL_LIMITATIONS_KEY = "canonical_limitations"
CANONICAL_GRAPH_REF_KEY = "canonical_graph_ref"
SOURCE_REVISION_KEY = "source_revision"
GIT_HEAD_KEY = "git_head"
DIRTY_KEY = "dirty"
WORKING_STATE_DIGEST_KEY = "working_state_digest"
WORKING_TREE_DIGEST_KEY = "working_tree_digest"
# Display hint only. Not an input to the digest, evidence IDs, or canonical schema.
WORKING_STATE_DIGEST_KIND_KEY = "working_state_digest_kind"
GIT_WORKING_STATE_KIND = "git_working_state"
COMMITTED_SNAPSHOT_KIND = "committed_snapshot"
GIT_HISTORY_COVERAGE_KEY = "git_history_coverage"
FEED_DIGEST_KEY = "feed_digest"
EVALUATION_TIME_KEY = "evaluation_time"
COVERAGE_STATUS_KEY = "coverage_status"
METRICS_KEY = "metrics"

SEALED_RECORD_KEYS = (
    CANONICAL_HOTSPOTS_KEY,
    CANONICAL_OWNERSHIP_KEY,
    CANONICAL_COCHANGE_KEY,
    CANONICAL_COVERAGE_KEY,
    CANONICAL_FRESHNESS_KEY,
)


def has_sealed_canonical_records(metadata: Mapping[str, Any]) -> bool:
    """True when assess-time hotspot or ownership records were attached."""

    return CANONICAL_HOTSPOTS_KEY in metadata or CANONICAL_OWNERSHIP_KEY in metadata


def graph_reference_from_artifacts(artifacts: Any | None) -> dict[str, Any] | None:
    """Copy existing graph artifact identity. Does not invent nodes or edges."""

    if artifacts is None:
        return None
    summary = getattr(artifacts, "summary", None)
    directory = getattr(artifacts, "directory", None)
    if summary is None:
        return None
    return {
        "directory": None if directory is None else str(directory),
        "repository_graph_id": summary.repository_graph_id,
        "repository_source_fingerprint": summary.repository_source_fingerprint,
        "repository_node_count": summary.repository_node_count,
        "repository_relationship_count": summary.repository_relationship_count,
        "assessment_graph_id": summary.assessment_graph_id,
        "assessment_node_count": summary.assessment_node_count,
        "assessment_relationship_count": summary.assessment_relationship_count,
    }


def observation_from_sealed_metadata(metadata: Mapping[str, Any]) -> JourneyObservation | None:
    """Rebuild the observation object from assess-time metadata. No Git I/O."""

    if not has_sealed_canonical_records(metadata):
        return None
    hotspots = _models(metadata.get(CANONICAL_HOTSPOTS_KEY), EngineeringHotspot)
    ownership = _models(metadata.get(CANONICAL_OWNERSHIP_KEY), OwnershipConcentration)
    coverage = _models(metadata.get(CANONICAL_COVERAGE_KEY), CapabilityCoverage)
    freshness = _models(metadata.get(CANONICAL_FRESHNESS_KEY), CapabilityFreshness)
    change = None
    raw_change = metadata.get(CANONICAL_CHANGE_SUMMARY_KEY)
    if isinstance(raw_change, ChangeSummary):
        change = raw_change
    elif isinstance(raw_change, Mapping):
        change = ChangeSummary.model_validate(raw_change)
    cochange = tuple(metadata.get(CANONICAL_COCHANGE_KEY) or ())
    limitations = tuple(metadata.get(CANONICAL_LIMITATIONS_KEY) or ())
    metrics = metadata.get(METRICS_KEY)
    return JourneyObservation(
        hotspots=hotspots,
        ownership=ownership,
        cochange=tuple(dict(item) for item in cochange if isinstance(item, Mapping)),
        change_summary=change,
        coverage=coverage,
        freshness=freshness,
        limitations=tuple(str(item) for item in limitations),
        metrics=metrics if isinstance(metrics, dict) else {},
        coverage_status=str(metadata.get(COVERAGE_STATUS_KEY) or "unknown"),
        feed_digest=str(metadata.get(FEED_DIGEST_KEY) or ""),
    )


def seal_assess_canonical_records(
    analysis_result: AnalysisResult,
    *,
    repository_root: Path,
    evaluation_time: datetime,
    graph_reference: Mapping[str, Any] | None = None,
    head: str | None = None,
) -> AnalysisResult:
    """Attach current-snapshot history/trust records to one assess result."""

    if evaluation_time.tzinfo is None:
        raise ValueError("evaluation_time must be timezone-aware")
    pinned = evaluation_time.astimezone(UTC)
    root = Path(repository_root)
    observed = observe_repository(root, evaluation_time=pinned, head=head)
    if head:
        # Committed snapshot identity. Do not re-read live HEAD/dirty state.
        dirty = False
        source_revision = head
        sealed_git_head = head
        snapshot_digest = digest_canonical(
            {"kind": "committed-snapshot", "head": head, "root": str(root)}
        )
        working_state_digest = snapshot_digest
        working_tree_digest = snapshot_digest
        working_state_digest_kind = COMMITTED_SNAPSHOT_KIND
    else:
        revision = observe_repository_revision(root)
        git_state = observe_local_git_state(root)
        dirty = bool(revision.dirty or git_state.dirty)
        source_revision = revision.revision_id
        sealed_git_head = git_state.head_sha or source_revision
        working_state_digest = git_state.state_digest
        working_tree_digest = git_state.working_tree_digest
        working_state_digest_kind = GIT_WORKING_STATE_KIND
    metadata = dict(analysis_result.metadata)
    metadata.update(
        {
            CANONICAL_HOTSPOTS_KEY: [item.model_dump(mode="json") for item in observed.hotspots],
            CANONICAL_OWNERSHIP_KEY: [item.model_dump(mode="json") for item in observed.ownership],
            CANONICAL_COCHANGE_KEY: [dict(item) for item in observed.cochange],
            CANONICAL_COVERAGE_KEY: [item.model_dump(mode="json") for item in observed.coverage],
            CANONICAL_FRESHNESS_KEY: [item.model_dump(mode="json") for item in observed.freshness],
            CANONICAL_CHANGE_SUMMARY_KEY: (
                None
                if observed.change_summary is None
                else observed.change_summary.model_dump(mode="json")
            ),
            CANONICAL_LIMITATIONS_KEY: list(observed.limitations),
            CANONICAL_GRAPH_REF_KEY: None if graph_reference is None else dict(graph_reference),
            SOURCE_REVISION_KEY: source_revision,
            GIT_HEAD_KEY: sealed_git_head,
            DIRTY_KEY: dirty,
            WORKING_STATE_DIGEST_KEY: working_state_digest,
            WORKING_TREE_DIGEST_KEY: working_tree_digest,
            WORKING_STATE_DIGEST_KIND_KEY: working_state_digest_kind,
            GIT_HISTORY_COVERAGE_KEY: _history_coverage(observed),
            FEED_DIGEST_KEY: observed.feed_digest,
            EVALUATION_TIME_KEY: pinned.isoformat().replace("+00:00", "Z"),
            COVERAGE_STATUS_KEY: observed.coverage_status,
            METRICS_KEY: observed.metrics,
        }
    )
    repo_meta = dict(analysis_result.repository.metadata)
    repo_meta.update(
        {
            SOURCE_REVISION_KEY: source_revision,
            GIT_HEAD_KEY: sealed_git_head,
            DIRTY_KEY: dirty,
            WORKING_STATE_DIGEST_KEY: working_state_digest,
            WORKING_TREE_DIGEST_KEY: working_tree_digest,
            WORKING_STATE_DIGEST_KIND_KEY: working_state_digest_kind,
        }
    )
    repository = analysis_result.repository.model_copy(update={"metadata": repo_meta})
    return analysis_result.model_copy(update={"metadata": metadata, "repository": repository})


def _history_coverage(observed: JourneyObservation) -> str:
    for row in observed.coverage:
        if row.capability_id == "quality.m22.hotspots":
            return row.coverage_reason or row.execution_state.value
    return "unknown"


def _models(raw: object, model: type[Any]) -> tuple[Any, ...]:
    if raw is None:
        return ()
    rows = raw if isinstance(raw, (list, tuple)) else (raw,)
    parsed: list[Any] = []
    for item in rows:
        if isinstance(item, model):
            parsed.append(item)
            continue
        if isinstance(item, Mapping):
            parsed.append(model.model_validate(item))
    return tuple(parsed)
