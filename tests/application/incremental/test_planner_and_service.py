"""Planner, policy, and service unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from codestrata.application.incremental.changes import ChangeClassifier
from codestrata.application.incremental.compatibility import CompatibilityEvaluator
from codestrata.application.incremental.errors import (
    IncrementalConfigurationError,
    IncrementalManifestError,
)
from codestrata.application.incremental.factory import create_incremental_planning_service
from codestrata.application.incremental.fingerprints import current_engine_fingerprint
from codestrata.application.incremental.impact import ImpactAnalyzer
from codestrata.application.incremental.models import (
    IncrementalPlanMode,
    IncrementalPlanningRequest,
    IncrementalStepType,
)
from codestrata.application.incremental.planner import IncrementalPlanner
from codestrata.application.incremental.policies import (
    IncrementalPlanningPolicy,
    policy_from_settings,
)
from codestrata.application.incremental.reuse import ReusePolicy
from codestrata.application.incremental.service import IncrementalPlanningService
from codestrata.config import load_settings
from codestrata.domain.repository.enums import RepositoryFileKind
from tests.application.incremental.helpers import candidate_state, entry, manifest


def _plan_for_manifests(previous_files: tuple, current_files: tuple):
    previous = manifest(*previous_files)
    current = manifest(*current_files)
    changes = ChangeClassifier().classify(previous, current, previous_snapshot_id="snap-1")
    compatibility = CompatibilityEvaluator().evaluate(
        current_engine_fingerprint(),
        current_engine_fingerprint(),
    )
    impact = ImpactAnalyzer().analyze(changes, repository_graph=None, compatibility=compatibility)
    reuse = ReusePolicy().evaluate(changes=changes, impact=impact, compatibility=compatibility)
    return IncrementalPlanner().plan(
        repository_id="repo-1",
        previous_run_id="run-1",
        previous_snapshot_id="snap-1",
        candidate_snapshot_id=None,
        changes=changes,
        compatibility=compatibility,
        impact=impact,
        reuse=reuse,
    )


def test_no_change_plan() -> None:
    plan = _plan_for_manifests(
        (entry("src/A.java", "a" * 64),),
        (entry("src/A.java", "a" * 64),),
    )
    assert plan.mode is IncrementalPlanMode.NO_CHANGES
    assert plan.full_rebuild_required is False
    assert plan.steps[0].step_type is IncrementalStepType.REUSE_INVENTORY
    assert all(step.status == "planned" for step in plan.steps)


def test_documentation_metadata_plan() -> None:
    plan = _plan_for_manifests(
        (entry("README.md", "a" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None),),
        (entry("README.md", "b" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None),),
    )
    assert plan.mode is IncrementalPlanMode.METADATA_ONLY
    assert plan.full_rebuild_required is False


def test_dependency_change_full_rebuild_plan() -> None:
    plan = _plan_for_manifests(
        (entry("pom.xml", "a" * 64, kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language=None),),
        (entry("pom.xml", "b" * 64, kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language=None),),
    )
    assert plan.mode is IncrementalPlanMode.FULL_REBUILD
    assert plan.steps[0].step_type is IncrementalStepType.FULL_REBUILD
    assert "dependency_manifest_changed" in plan.full_rebuild_reasons


def test_too_many_changed_files_fallback() -> None:
    previous = manifest(*(entry(f"src/F{i}.java", ("a" * 63) + "0") for i in range(5)))
    current = manifest(*(entry(f"src/F{i}.java", ("b" * 63) + "1") for i in range(5)))
    changes = ChangeClassifier().classify(previous, current)
    compatibility = CompatibilityEvaluator().evaluate(
        current_engine_fingerprint(),
        current_engine_fingerprint(),
    )
    impact = ImpactAnalyzer().analyze(
        changes,
        repository_graph=None,
        compatibility=compatibility,
        policy=IncrementalPlanningPolicy(max_changed_files=2),
    )
    reuse = ReusePolicy().evaluate(changes=changes, impact=impact, compatibility=compatibility)
    plan = IncrementalPlanner().plan(
        repository_id="repo-1",
        previous_run_id="run-1",
        previous_snapshot_id="snap-1",
        candidate_snapshot_id=None,
        changes=changes,
        compatibility=compatibility,
        impact=impact,
        reuse=reuse,
        policy=IncrementalPlanningPolicy(max_changed_files=2),
    )
    assert plan.full_rebuild_required is True
    assert "too_many_changed_files" in plan.full_rebuild_reasons


def test_policy_hard_safety_cannot_disable() -> None:
    with pytest.raises(IncrementalConfigurationError):
        IncrementalPlanningPolicy(fallback_on_unknown_impact=False)
    with pytest.raises(IncrementalConfigurationError):
        IncrementalPlanningPolicy(require_complete_fingerprints=False)
    with pytest.raises(ValidationError):
        IncrementalPlanningPolicy(dependency_depth=4)


def test_settings_incremental_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.incremental.enabled is False
    assert settings.incremental.max_changed_files == 100
    policy = policy_from_settings(settings)
    assert policy.enabled is False


def test_settings_incremental_custom_and_invalid(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"

        [incremental]
        enabled = false
        max_changed_files = 50
        max_change_ratio = 0.2
        dependency_depth = 3
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.incremental.max_changed_files == 50
    assert settings.incremental.dependency_depth == 3

    bad = tmp_path / "bad.toml"
    bad.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        [incremental]
        max_change_ratio = 1.5
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_settings(bad)

    bad2 = tmp_path / "bad2.toml"
    bad2.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        [incremental]
        dependency_depth = 4
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_settings(bad2)


def test_service_no_previous_run_full_rebuild() -> None:
    queries = MagicMock()
    queries.resolve_repository.return_value = MagicMock(
        repository_id="repo-1",
        canonical_key="demo",
        display_name="demo",
    )
    queries.get_latest_completed_run.return_value = None
    service = IncrementalPlanningService(query_service=queries)
    candidate = candidate_state(manifest(entry("src/A.java", "a" * 64)))
    plan = service.create_plan(
        IncrementalPlanningRequest(repository_identifier="demo", candidate=candidate)
    )
    assert plan.mode is IncrementalPlanMode.FULL_REBUILD
    assert "no_previous_run" in plan.full_rebuild_reasons
    queries.get_repository_manifest.assert_not_called()


def test_service_requires_candidate_without_provider() -> None:
    service = IncrementalPlanningService()
    with pytest.raises(IncrementalManifestError):
        service.create_plan(IncrementalPlanningRequest(repository_identifier="demo"))


def test_factory_injects_query_service() -> None:
    queries = MagicMock()
    service = create_incremental_planning_service(query_service=queries)
    assert isinstance(service, IncrementalPlanningService)


def test_plan_serialization_stable_for_mode_and_steps() -> None:
    plan = _plan_for_manifests(
        (entry("src/A.java", "a" * 64),),
        (entry("src/A.java", "a" * 64),),
    )
    payload: dict[str, Any] = plan.model_dump(mode="json")
    assert payload["mode"] == "no_changes"
    assert payload["steps"][0]["step_type"] == "reuse_inventory"
    assert payload["steps"][0]["status"] == "planned"
