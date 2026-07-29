"""Phase 2F.2 execution, merge, and gating tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codestrata.application.incremental.errors import (
    IncrementalArtifactMergeError,
    IncrementalConfigurationError,
)
from codestrata.application.incremental.execution import IncrementalAssessmentExecutor
from codestrata.application.incremental.execution_gating import evaluate_selective_eligibility
from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionRequest,
    IncrementalExecutionStatus,
)
from codestrata.application.incremental.execution_policies import (
    IncrementalExecutionPolicy,
    execution_policy_from_settings,
)
from codestrata.application.incremental.graph_rebuild import (
    merge_graph_snapshots,
    nodes_sourced_from_paths,
)
from codestrata.application.incremental.inventory_merge import merge_inventory
from codestrata.application.incremental.models import (
    CompatibilityResult,
    IncrementalAssessmentPlan,
    IncrementalPlanMode,
    IncrementalPlanStep,
    IncrementalStepType,
)
from codestrata.application.incremental.selective_scan import (
    CandidateManifestSelectiveScanService,
    SelectiveScanRequest,
)
from codestrata.config import load_settings
from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
    GraphStatus,
    GraphType,
    NodeId,
)
from codestrata.domain.repository.enums import RepositoryFileKind
from tests.application.incremental.helpers import candidate_state, entry, manifest


def _plan(
    *,
    mode: IncrementalPlanMode = IncrementalPlanMode.NO_CHANGES,
    full_rebuild: bool = False,
    reasons: tuple[str, ...] = (),
) -> IncrementalAssessmentPlan:
    return IncrementalAssessmentPlan(
        plan_id="plan-1",
        mode=mode,
        repository_id="repo-1",
        previous_run_id="run-1",
        previous_snapshot_id="snap-1",
        compatibility=CompatibilityResult(compatible=True),
        change_summary={"change_count": 0, "unchanged_count": 1},
        impact_summary={"truncated": False, "requires_full_rebuild": False, "unknown_impacts": []},
        steps=(
            IncrementalPlanStep(
                sequence=1,
                step_type=IncrementalStepType.REUSE_INVENTORY,
            ),
        ),
        full_rebuild_required=full_rebuild,
        full_rebuild_reasons=reasons,
        created_at=datetime.now(UTC),
    )


def test_execution_disabled_gates_selective() -> None:
    eligible, reasons = evaluate_selective_eligibility(
        _plan(),
        IncrementalExecutionPolicy(execution_enabled=False),
    )
    assert eligible is False
    assert "execution_disabled" in reasons


def test_full_rebuild_plan_not_executed_selectively() -> None:
    eligible, reasons = evaluate_selective_eligibility(
        _plan(mode=IncrementalPlanMode.FULL_REBUILD, full_rebuild=True, reasons=("x",)),
        IncrementalExecutionPolicy(execution_enabled=True, enabled=True),
    )
    assert eligible is False
    assert "plan_requires_full_rebuild" in reasons


def test_no_change_plan_eligible_when_execution_enabled() -> None:
    eligible, reasons = evaluate_selective_eligibility(
        _plan(),
        IncrementalExecutionPolicy(execution_enabled=True, enabled=True),
    )
    assert eligible is True
    assert reasons == ()


def test_inventory_merge_add_modify_delete() -> None:
    previous = manifest(
        entry("src/A.java", "a" * 64),
        entry("src/B.java", "b" * 64),
        entry("README.md", "c" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None),
    )
    current = manifest(
        entry("src/A.java", "d" * 64),
        entry("src/C.java", "e" * 64),
        entry("README.md", "c" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None),
    )
    from codestrata.application.incremental.changes import ChangeClassifier

    changes = ChangeClassifier().classify(previous, current)
    updated = (
        entry("src/A.java", "d" * 64),
        entry("src/C.java", "e" * 64),
    )
    merged = merge_inventory(previous, changes=changes, updated_entries=updated)
    paths = {item.path.root for item in merged.files}
    assert paths == {"src/A.java", "src/C.java", "README.md"}
    original_a = next(item for item in previous.files if item.path.root == "src/A.java")
    assert original_a.fingerprint.digest == "a" * 64  # immutable previous


def test_inventory_merge_rejects_path_traversal() -> None:
    previous = manifest(entry("src/A.java", "a" * 64))
    from codestrata.application.incremental.models import (
        FileChange,
        FileChangeKind,
        RepositoryChangeSet,
    )

    changes = RepositoryChangeSet(
        added=(
            FileChange(path="/etc/passwd", kind=FileChangeKind.ADDED),
        ),
        change_count=1,
    )
    with pytest.raises(IncrementalArtifactMergeError):
        merge_inventory(
            previous,
            changes=changes,
            updated_entries=(),
        )


def test_graph_merge_removes_and_adds() -> None:
    meta = GraphMetadata(
        graph_id=GraphId("g1"),
        graph_type=GraphType.REPOSITORY,
        schema_version="1.0.0",
        generator_version="1.0.0",
        source_fingerprint="sha256:" + ("0" * 64),
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )
    a = GraphNode(
        id=NodeId("a"),
        node_type="module",
        schema_version="1.0.0",
        properties={"path": "src/A.java"},
    )
    b = GraphNode(
        id=NodeId("b"),
        node_type="module",
        schema_version="1.0.0",
        properties={"path": "src/B.java"},
    )
    rel = GraphRelationship(
        id="r1",
        relationship_type="depends_on",
        source_node_id=NodeId("a"),
        target_node_id=NodeId("b"),
    )
    previous = GraphSnapshot(metadata=meta, nodes=(a, b), relationships=(rel,))
    remove = nodes_sourced_from_paths(previous, {"src/A.java"})
    assert "a" in remove
    c = GraphNode(
        id=NodeId("c"),
        node_type="module",
        schema_version="1.0.0",
        properties={"path": "src/C.java"},
    )
    merged = merge_graph_snapshots(
        previous,
        remove_node_ids=remove,
        new_nodes=(c,),
        new_relationships=(),
    )
    ids = {str(node.id) for node in merged.nodes}
    assert ids == {"b", "c"}
    assert merged.relationships == ()


def test_executor_falls_back_when_execution_disabled() -> None:
    runner = MagicMock()
    runner.run_full.return_value = MagicMock(
        knowledge_run_id="run-new",
        knowledge_snapshot_id="snap-new",
        findings_count=1,
        recommendations_count=1,
    )
    executor = IncrementalAssessmentExecutor(
        assessment_runner=runner,
        policy=IncrementalExecutionPolicy(execution_enabled=False),
    )
    result = executor.execute(
        IncrementalExecutionRequest(
            repository="/tmp/repo",
            output_directory="/tmp/out",
            plan=_plan(),
        )
    )
    assert result.fallback_used is True
    assert result.mode is IncrementalExecutionMode.FULL_REBUILD_FALLBACK
    assert result.status is IncrementalExecutionStatus.FALLBACK_COMPLETED
    runner.run_full.assert_called_once()
    assert runner.run_full.call_args.kwargs["scanned_repository"] is None


def test_executor_selective_no_change_with_candidate(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "A.java").write_text("class A {}", encoding="utf-8")

    base = manifest(entry("src/A.java", "a" * 64))
    candidate = candidate_state(base)
    queries = MagicMock()
    queries.get_repository_manifest.return_value = base
    runner = MagicMock()
    runner.run_full.return_value = MagicMock(
        knowledge_run_id="run-2",
        knowledge_snapshot_id="snap-2",
        findings_count=0,
        recommendations_count=0,
    )
    executor = IncrementalAssessmentExecutor(
        assessment_runner=runner,
        query_service=queries,
        selective_scan=CandidateManifestSelectiveScanService(),
        policy=IncrementalExecutionPolicy(execution_enabled=True, enabled=True),
    )
    result = executor.execute(
        IncrementalExecutionRequest(
            repository=str(repo_dir),
            output_directory=str(tmp_path / "out"),
            plan=_plan(),
            candidate=candidate,
        )
    )
    assert result.fallback_used is False
    assert result.mode is IncrementalExecutionMode.INCREMENTAL
    assert result.reused_counts.files >= 0
    assert runner.run_full.call_args.kwargs["scanned_repository"] is not None


def test_candidate_manifest_selective_scan_paths() -> None:
    previous = manifest(entry("src/A.java", "a" * 64))
    current = manifest(entry("src/A.java", "b" * 64))
    from codestrata.application.incremental.changes import ChangeClassifier

    changes = ChangeClassifier().classify(previous, current)
    scan = CandidateManifestSelectiveScanService().scan(
        SelectiveScanRequest(
            repository="demo",
            changes=changes,
            previous_manifest=previous,
            candidate=candidate_state(current),
        )
    )
    assert scan.complete is True
    assert scan.supports_subset is True
    assert scan.scanned_files == ("src/A.java",)


def test_execution_policy_hard_safety() -> None:
    with pytest.raises(IncrementalConfigurationError):
        IncrementalExecutionPolicy(fallback_on_step_failure=False)
    with pytest.raises(IncrementalConfigurationError):
        IncrementalExecutionPolicy(allow_ai_reuse=True)


def test_settings_execution_defaults(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.incremental.execution_enabled is False
    assert settings.incremental.allow_ai_reuse is False
    policy = execution_policy_from_settings(settings)
    assert policy.execution_enabled is False


def test_settings_rejects_ai_reuse(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        [incremental]
        allow_ai_reuse = true
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_settings(config)


def test_architecture_forbids_transport_and_infra_tokens() -> None:
    import codestrata.application.incremental as pkg

    root = Path(pkg.__file__).resolve().parent
    forbidden = (
        "fastmcp",
        "typer",
        "sqlite3",
        "SqliteKnowledgeStore",
        "report.json",
        "report.html",
        "subprocess",
        "boto3",
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains {token}"
