"""Phase 2F.3 tests: validation, metrics, equivalence, explainability, rollout."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from codestrata.application.incremental.equivalence import (
    AssessmentSemanticComparator,
    CompleteAssessmentArtifacts,
    artifacts_from_semantic_payloads,
)
from codestrata.application.incremental.errors import (
    IncrementalConfigurationError,
    IncrementalExecutionRecordNotFoundError,
    IncrementalRolloutDisabledError,
)
from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionResult,
    IncrementalExecutionStatus,
    IncrementalRecomputeCounts,
    IncrementalReuseCounts,
)
from codestrata.application.incremental.execution_record import IncrementalExecutionRecord
from codestrata.application.incremental.explainability import (
    ExplanationFilters,
    IncrementalExplainabilityService,
    IncrementalExplanationKind,
)
from codestrata.application.incremental.inspection import IncrementalInspectionService
from codestrata.application.incremental.metrics import IncrementalMetricsCalculator
from codestrata.application.incremental.models import (
    CompatibilityResult,
    IncrementalAssessmentPlan,
    IncrementalPlanMode,
)
from codestrata.application.incremental.operations import IncrementalOperationsService
from codestrata.application.incremental.provenance import InMemoryIncrementalExecutionRecordStore
from codestrata.application.incremental.rollout import (
    IncrementalRolloutMode,
    IncrementalRolloutPolicy,
    resolve_rollout_mode,
)
from codestrata.application.incremental.service import IncrementalPlanningService
from codestrata.application.incremental.validation import IncrementalValidationService
from codestrata.application.incremental.validation_models import (
    IncrementalValidationRequest,
    IncrementalValidationStatus,
)
from codestrata.config import load_settings


def _execution(
    *,
    fallback: bool = False,
    reuse_findings: int = 0,
    recompute_findings: int = 2,
    ai_reuse: int = 0,
) -> IncrementalExecutionResult:
    now = datetime.now(UTC)
    return IncrementalExecutionResult(
        execution_id=str(uuid4()),
        plan_id=str(uuid4()),
        mode=(
            IncrementalExecutionMode.FULL_REBUILD_FALLBACK
            if fallback
            else IncrementalExecutionMode.INCREMENTAL
        ),
        status=(
            IncrementalExecutionStatus.FALLBACK_COMPLETED
            if fallback
            else IncrementalExecutionStatus.COMPLETED
        ),
        repository_id="repo-1",
        run_id="run-1",
        snapshot_id="snap-1",
        reused_counts=IncrementalReuseCounts(
            findings=reuse_findings,
            ai_artifacts=ai_reuse,
        ),
        recomputed_counts=IncrementalRecomputeCounts(findings=recompute_findings),
        fallback_used=fallback,
        fallback_reasons=("engine_incompatible",) if fallback else (),
        started_at=now,
        completed_at=now,
        assessment_result=type(
            "R",
            (),
            {
                "findings_count": reuse_findings + recompute_findings,
                "recommendations_count": 1,
                "phases_count": 1,
                "technologies_count": 1,
            },
        )(),
    )


def _plan(
    *,
    mode: IncrementalPlanMode = IncrementalPlanMode.INCREMENTAL_CANDIDATE,
) -> IncrementalAssessmentPlan:
    return IncrementalAssessmentPlan(
        plan_id=str(uuid4()),
        mode=mode,
        repository_id="repo-1",
        compatibility=CompatibilityResult(compatible=True),
        change_summary={
            "added": 1,
            "modified": 0,
            "deleted": 0,
            "change_count": 1,
            "unchanged_count": 9,
        },
        impact_summary={"directly_changed_files": 1, "impacted_findings": 1},
        full_rebuild_required=mode is IncrementalPlanMode.FULL_REBUILD,
        full_rebuild_reasons=(("forced",) if mode is IncrementalPlanMode.FULL_REBUILD else ()),
        created_at=datetime.now(UTC),
    )


def test_validation_passes_for_completed_incremental() -> None:
    plan = _plan()
    execution = _execution().model_copy(update={"plan_id": plan.plan_id})
    result = IncrementalValidationService().validate(
        IncrementalValidationRequest(execution=execution, plan=plan)
    )
    assert result.status is IncrementalValidationStatus.PASSED
    assert result.blocking_issues == ()


def test_validation_fails_on_ai_reuse() -> None:
    plan = _plan()
    execution = _execution(ai_reuse=1).model_copy(update={"plan_id": plan.plan_id})
    result = IncrementalValidationService().validate(
        IncrementalValidationRequest(execution=execution, plan=plan)
    )
    assert result.status is IncrementalValidationStatus.FAILED
    assert any(issue.code == "ai_artifacts_reused" for issue in result.blocking_issues)


def test_validation_fallback_requires_reasons() -> None:
    plan = _plan()
    execution = _execution(fallback=True).model_copy(
        update={"fallback_reasons": (), "plan_id": plan.plan_id}
    )
    result = IncrementalValidationService().validate(
        IncrementalValidationRequest(execution=execution, plan=plan)
    )
    assert result.status is IncrementalValidationStatus.FAILED


def test_equivalence_identical_semantic_artifacts() -> None:
    left = artifacts_from_semantic_payloads(
        inventory_paths=("a.py", "b.py"),
        finding_keys=("f1", "f2"),
        recommendation_keys=("r1",),
        roadmap_keys=("p1",),
        technologies=("java",),
    )
    right = CompleteAssessmentArtifacts.model_validate(left.model_dump())
    eq = AssessmentSemanticComparator().compare(left, right)
    assert eq.equivalent is True
    assert eq.normalized_hashes["incremental"] == eq.normalized_hashes["full"]


def test_equivalence_findings_mismatch() -> None:
    left = artifacts_from_semantic_payloads(finding_keys=("f1",))
    right = artifacts_from_semantic_payloads(finding_keys=("f2",))
    eq = AssessmentSemanticComparator().compare(left, right)
    assert eq.equivalent is False
    assert eq.findings_equivalent is False


def test_metrics_fallback_zero_reuse() -> None:
    metrics = IncrementalMetricsCalculator().calculate(
        _execution(fallback=True, reuse_findings=5),
        plan=_plan(),
    )
    assert metrics.fallback_used is True
    assert metrics.findings_reused == 0
    assert metrics.overall_reuse_ratio == 0.0
    assert metrics.fallback_reason_codes == ("engine_incompatible",)


def test_metrics_zero_denominator_ratios() -> None:
    metrics = IncrementalMetricsCalculator().calculate(_execution())
    assert 0.0 <= metrics.file_reuse_ratio <= 1.0
    assert 0.0 <= metrics.overall_reuse_ratio <= 1.0


def test_explainability_includes_fallback_and_ai() -> None:
    explanations = IncrementalExplainabilityService().explain(
        execution=_execution(fallback=True),
        plan=_plan(mode=IncrementalPlanMode.FULL_REBUILD),
    )
    kinds = {item.kind for item in explanations}
    assert IncrementalExplanationKind.FALLBACK in kinds
    assert IncrementalExplanationKind.AI in kinds
    filtered = IncrementalExplainabilityService().filter_explanations(
        explanations,
        ExplanationFilters(kind=IncrementalExplanationKind.FALLBACK, limit=10),
    )
    assert filtered and all(item.kind is IncrementalExplanationKind.FALLBACK for item in filtered)


def test_provenance_store_roundtrip() -> None:
    store = InMemoryIncrementalExecutionRecordStore()
    now = datetime.now(UTC)
    record = IncrementalExecutionRecord(
        execution_id="exec-1",
        plan_id="plan-1",
        repository_id="repo-1",
        actual_mode=IncrementalExecutionMode.INCREMENTAL,
        status=IncrementalExecutionStatus.COMPLETED,
        started_at=now,
        completed_at=now,
    )
    store.save(record)
    loaded = store.get("exec-1")
    assert loaded.execution_id == "exec-1"
    listed = store.list_for_repository("repo-1", limit=5)
    assert listed[0].execution_id == "exec-1"


def test_inspection_service_not_found() -> None:
    service = IncrementalInspectionService(InMemoryIncrementalExecutionRecordStore())
    with pytest.raises(IncrementalExecutionRecordNotFoundError):
        service.get_execution("missing")


def test_rollout_modes() -> None:
    assert resolve_rollout_mode(rollout_mode=None, enabled=False, execution_enabled=False) is (
        IncrementalRolloutMode.OFF
    )
    assert resolve_rollout_mode(rollout_mode=None, enabled=True, execution_enabled=False) is (
        IncrementalRolloutMode.PLAN_ONLY
    )
    assert resolve_rollout_mode(rollout_mode=None, enabled=True, execution_enabled=True) is (
        IncrementalRolloutMode.OPT_IN
    )
    with pytest.raises(IncrementalConfigurationError):
        resolve_rollout_mode(rollout_mode="off", enabled=True, execution_enabled=False)
    with pytest.raises(IncrementalConfigurationError):
        IncrementalRolloutPolicy(fallback_on_validation_failure=False)


def test_operations_blocks_when_rollout_off() -> None:
    from codestrata.application.incremental.models import IncrementalPlanningRequest

    ops = IncrementalOperationsService(
        planning_service=IncrementalPlanningService(),
        rollout=IncrementalRolloutPolicy(mode=IncrementalRolloutMode.OFF),
    )
    with pytest.raises(IncrementalRolloutDisabledError):
        ops.create_plan(IncrementalPlanningRequest(repository_identifier="test-fixtures/sample-js-app"))


def test_settings_rollout_defaults(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.incremental.rollout_mode == "off"
    assert settings.incremental.execution_enabled is False
    assert settings.incremental.validate_after_execution is True
    assert settings.incremental.allow_ai_reuse is False


def test_settings_legacy_enabled_maps_to_plan_only(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        [incremental]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.incremental.rollout_mode == "plan_only"


def test_settings_conflict_rejected(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        [incremental]
        rollout_mode = "off"
        enabled = true
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_settings(config)


def test_plan_only_blocks_execution() -> None:
    from codestrata.application.incremental.execution_models import IncrementalExecutionRequest

    ops = IncrementalOperationsService(
        planning_service=IncrementalPlanningService(),
        rollout=IncrementalRolloutPolicy(mode=IncrementalRolloutMode.PLAN_ONLY),
    )
    with pytest.raises(IncrementalRolloutDisabledError):
        ops.execute(
            IncrementalExecutionRequest(
                repository="test-fixtures/sample-js-app",
                output_directory="reports",
            )
        )


def test_architecture_still_forbids_transport_imports() -> None:
    import codestrata.application.incremental as pkg

    root = Path(pkg.__file__).resolve().parent
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "fastmcp" not in text
        assert "typer" not in text
        assert "sqlite3" not in text
        assert "subprocess" not in text
        assert "boto3" not in text
