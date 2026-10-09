"""R2-P02: assess seals M22/M25/M26 and trust records at assessment time."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.application.incremental.git_repo_helpers import commit_all, init_repo, write

from codestrata.application.assessment.canonical_records import (
    CANONICAL_COCHANGE_KEY,
    CANONICAL_COVERAGE_KEY,
    CANONICAL_FRESHNESS_KEY,
    CANONICAL_GRAPH_REF_KEY,
    CANONICAL_HOTSPOTS_KEY,
    CANONICAL_OWNERSHIP_KEY,
    COMMITTED_SNAPSHOT_KIND,
    DIRTY_KEY,
    EVALUATION_TIME_KEY,
    GIT_HEAD_KEY,
    GIT_WORKING_STATE_KIND,
    SOURCE_REVISION_KEY,
    WORKING_STATE_DIGEST_KEY,
    WORKING_STATE_DIGEST_KIND_KEY,
    seal_assess_canonical_records,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.infrastructure.knowledge_store.git_revision import observe_local_git_state
from codestrata.models.analysis_result import AnalysisResult
from codestrata.models.repository import Repository
from codestrata.reporting.assessment_canonical import canonical_report_from_analysis
from codestrata.reporting.journey_observations import JOURNEY_EVALUATION_TIME

_EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "journeys"
_PINNED = datetime(2026, 9, 27, tzinfo=UTC)


def _result(path: Path, files: list[str] | None = None) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name=path.name,
            path=path,
            files=files or ["src/app.js"],
        )
    )


def _seal(path: Path) -> AnalysisResult:
    return seal_assess_canonical_records(
        _result(path),
        repository_root=path,
        evaluation_time=_PINNED,
    )


def test_complete_repo_seals_hotspots_ownership_and_cochange(tmp_path: Path) -> None:
    repo = tmp_path / "complete-js"
    shutil.copytree(_EXAMPLES / "complete-js", repo)
    init_repo(repo)
    sha = commit_all(repo, "pin fixture")
    sealed = _seal(repo)
    assert sealed.metadata[CANONICAL_HOTSPOTS_KEY]
    assert sealed.metadata[CANONICAL_OWNERSHIP_KEY]
    assert sealed.metadata[CANONICAL_COCHANGE_KEY] is not None
    assert sealed.metadata[CANONICAL_COVERAGE_KEY]
    assert sealed.metadata[CANONICAL_FRESHNESS_KEY]
    assert sealed.metadata[SOURCE_REVISION_KEY] == sha
    assert sealed.metadata[DIRTY_KEY] is False
    assert sealed.repository.metadata[DIRTY_KEY] is False
    assert sealed.metadata[EVALUATION_TIME_KEY] == "2026-09-27T00:00:00Z"
    assert sealed.metadata[WORKING_STATE_DIGEST_KIND_KEY] == GIT_WORKING_STATE_KIND
    assert sealed.metadata[WORKING_STATE_DIGEST_KEY] == observe_local_git_state(repo).state_digest
    hotspot = sealed.metadata[CANONICAL_HOTSPOTS_KEY][0]
    assert hotspot["ranking_value"] == "12"
    assert hotspot["subject_id"] == "src/app.js"
    ownership = sealed.metadata[CANONICAL_OWNERSHIP_KEY][0]
    assert ownership["serialized_ratio"] == "1.000000"
    assert ownership["status"] == "pass"


def test_missing_git_and_feed_are_unknown_not_clean(tmp_path: Path) -> None:
    repo = tmp_path / "missing"
    (repo / "src").mkdir(parents=True)
    shutil.copy(_EXAMPLES / "complete-js" / "src" / "app.js", repo / "src" / "app.js")
    sealed = _seal(repo)
    assert sealed.metadata[DIRTY_KEY] is False
    assert sealed.metadata[SOURCE_REVISION_KEY] == "working-tree"
    hotspots = sealed.metadata[CANONICAL_HOTSPOTS_KEY]
    assert hotspots
    assert all(item.get("ranking_value") is None for item in hotspots)
    ownership = sealed.metadata[CANONICAL_OWNERSHIP_KEY][0]
    assert ownership["status"] == "unknown"
    assert ownership["serialized_ratio"] is None
    reasons = [row["coverage_reason"] for row in sealed.metadata[CANONICAL_COVERAGE_KEY]]
    assert "missing_git_history" in reasons
    feed_states = [
        row["state"]
        for row in sealed.metadata[CANONICAL_FRESHNESS_KEY]
        if row["capability_id"] == "security.m13.vulnerabilities"
    ]
    assert feed_states
    assert feed_states[0] != "fresh"
    assert "feed_missing" in sealed.metadata["canonical_limitations"]


def test_dirty_worktree_is_explicit_and_not_clean_head(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "dirty")
    write(repo, "src/app.js", "export const n = 1;\n")
    sha = commit_all(repo, "base")
    write(repo, "src/extra.js", "export const dirty = true;\n")
    sealed = seal_assess_canonical_records(
        _result(repo, files=["src/app.js", "src/extra.js"]),
        repository_root=repo,
        evaluation_time=_PINNED,
    )
    assert sealed.metadata[DIRTY_KEY] is True
    assert sealed.repository.metadata[DIRTY_KEY] is True
    assert sealed.metadata[SOURCE_REVISION_KEY] == sha
    assert sealed.repository.metadata[SOURCE_REVISION_KEY] == sha


def test_subdirectory_assessment_uses_containing_git_head(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "monorepo")
    write(repo, "engine/src/app.js", "export const engine = 1;\n")
    write(repo, "other/secret.js", "export const leaked = true;\n")
    sha = commit_all(repo, "pin monorepo")
    engine = repo / "engine"
    sealed = seal_assess_canonical_records(
        _result(engine, files=["src/app.js"]),
        repository_root=engine,
        evaluation_time=_PINNED,
    )
    assert sealed.metadata[SOURCE_REVISION_KEY] == sha
    assert sealed.metadata[GIT_HEAD_KEY] == sha
    assert sealed.metadata[DIRTY_KEY] is False
    subjects = [item["subject_id"] for item in sealed.metadata[CANONICAL_HOTSPOTS_KEY]]
    assert any("src/app.js" in str(item) for item in subjects)
    assert all("secret.js" not in str(item) for item in subjects)
    assert all("other/" not in str(item) for item in subjects)
    write(repo, "other/more.js", "export const extra = 2;\n")
    dirty = seal_assess_canonical_records(
        _result(engine, files=["src/app.js"]),
        repository_root=engine,
        evaluation_time=_PINNED,
    )
    assert dirty.metadata[SOURCE_REVISION_KEY] == sha
    assert dirty.metadata[GIT_HEAD_KEY] == sha
    assert dirty.metadata[DIRTY_KEY] is True


def test_pinned_evaluation_time_is_deterministic(tmp_path: Path) -> None:
    repo = tmp_path / "complete-js"
    shutil.copytree(_EXAMPLES / "complete-js", repo)
    init_repo(repo)
    commit_all(repo, "pin fixture")
    first = _seal(repo)
    second = _seal(repo)
    assert first.metadata[CANONICAL_HOTSPOTS_KEY] == second.metadata[CANONICAL_HOTSPOTS_KEY]
    assert first.metadata[CANONICAL_OWNERSHIP_KEY] == second.metadata[CANONICAL_OWNERSHIP_KEY]
    assert first.metadata[WORKING_STATE_DIGEST_KEY] == second.metadata[WORKING_STATE_DIGEST_KEY]


def test_naive_evaluation_time_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="timezone-aware"):
        seal_assess_canonical_records(
            _result(repo),
            repository_root=repo,
            evaluation_time=datetime(2026, 9, 27),
        )


def test_sealed_report_does_not_call_observe_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "complete-js"
    shutil.copytree(_EXAMPLES / "complete-js", repo)
    init_repo(repo)
    commit_all(repo, "pin fixture")
    sealed = _seal(repo)

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("observe_repository must not run for sealed assess records")

    monkeypatch.setattr(
        "codestrata.reporting.assessment_canonical.observe_repository",
        _forbidden,
    )
    report = canonical_report_from_analysis(sealed)
    assert report.envelope.body.hotspots[0].ranking_value == "12"
    assert report.envelope.body.source_revision != "unavailable"


def test_graph_reference_is_copied_not_invented(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    sealed = seal_assess_canonical_records(
        _result(repo, files=[]),
        repository_root=repo,
        evaluation_time=_PINNED,
        graph_reference={
            "repository_graph_id": "graph:fixture",
            "repository_node_count": 2,
            "repository_relationship_count": 1,
        },
    )
    assert sealed.metadata[CANONICAL_GRAPH_REF_KEY]["repository_graph_id"] == "graph:fixture"
    assert sealed.metadata[CANONICAL_GRAPH_REF_KEY]["repository_node_count"] == 2


def test_journey_constant_is_not_the_production_default() -> None:
    assert JOURNEY_EVALUATION_TIME == datetime(2026, 9, 27, tzinfo=UTC)


def test_historical_head_binds_source_revision_not_live_head(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "history")
    write(repo, "src/app.js", "function app() { return 1; }\n")
    first = commit_all(repo, "first")
    write(repo, "src/later.js", "function later() { return 2; }\n")
    commit_all(repo, "later")
    write(repo, "dirty.txt", "uncommitted\n")
    sealed = seal_assess_canonical_records(
        _result(repo, files=["src/app.js"]),
        repository_root=repo,
        evaluation_time=_PINNED,
        head=first,
    )
    assert sealed.metadata[SOURCE_REVISION_KEY] == first
    assert sealed.metadata[GIT_HEAD_KEY] == first
    assert sealed.repository.metadata[SOURCE_REVISION_KEY] == first
    assert sealed.repository.metadata[GIT_HEAD_KEY] == first
    assert sealed.metadata[DIRTY_KEY] is False
    assert sealed.metadata[WORKING_STATE_DIGEST_KIND_KEY] == COMMITTED_SNAPSHOT_KIND
    assert sealed.metadata[WORKING_STATE_DIGEST_KEY] == digest_canonical(
        {"kind": "committed-snapshot", "head": first, "root": str(repo)}
    )
    ownership = sealed.metadata[CANONICAL_OWNERSHIP_KEY][0]
    assert ownership["history_profile_id"] == first
