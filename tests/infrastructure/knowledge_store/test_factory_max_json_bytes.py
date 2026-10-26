"""Settings and factory wiring for knowledge JSON size bounds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
)

from codestrata.application.knowledge.models import (
    KnowledgeArtifactKind,
    RepositoryIdentityHints,
    StagedKnowledgeArtifact,
)
from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.config.settings import CodestrataSettings, load_settings
from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType
from codestrata.infrastructure.knowledge_store.factory import (
    create_knowledge_store,
    max_json_bytes_from_settings,
)
from codestrata.infrastructure.knowledge_store.file.store import FileKnowledgeStore
from codestrata.infrastructure.knowledge_store.io import DEFAULT_MAX_JSON_BYTES


def test_max_json_bytes_from_settings_default_when_omitted() -> None:
    assert max_json_bytes_from_settings(None) == DEFAULT_MAX_JSON_BYTES


def test_create_knowledge_store_uses_default_bound_without_settings(tmp_path: Path) -> None:
    store = create_knowledge_store(tmp_path / "knowledge")
    assert store._paths.max_json_bytes == DEFAULT_MAX_JSON_BYTES  # noqa: SLF001


def test_create_knowledge_store_threads_settings_bound(tmp_path: Path) -> None:
    bound = 32 * 1024 * 1024
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "knowledge": {"max_json_bytes": bound},
        }
    )
    store = create_knowledge_store(tmp_path / "knowledge", settings=settings)
    assert store._paths.max_json_bytes == bound  # noqa: SLF001


def test_knowledge_max_json_bytes_rejects_non_positive() -> None:
    with pytest.raises(ValidationError):
        CodestrataSettings.model_validate(
            {
                "repository": {"path": "."},
                "knowledge": {"max_json_bytes": 0},
            }
        )


def test_load_settings_reads_knowledge_max_json_bytes(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [knowledge]
        max_json_bytes = 33554432
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.knowledge.max_json_bytes == 33_554_432


def test_larger_bound_persists_and_reloads_findings(tmp_path: Path) -> None:
    bound = 48 * 1024
    payload = {"findings": [{"evidence": "x" * (bound // 2)}]}
    serialized = len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    assert serialized < bound
    assert serialized > 2048

    with FileKnowledgeStore(tmp_path / "knowledge", max_json_bytes=bound) as store:
        record = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.LOCAL,
                display_name="large",
                local_path=tmp_path / "large",
            )
        )
        manifest = make_manifest()
        snapshot = store.snapshots.create_or_get_snapshot(
            repository_id=record.repository_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            manifest=manifest,
            content_fingerprint=fingerprint_for(manifest),
        )
        run = store.runs.create_run(
            repository_id=record.repository_id,
            assessment_mode="deterministic",
            codestrata_version="0.3.0",
            ruleset_version="1.2.0",
        )
        completed = store.runs.complete_run(
            run.run_id,
            snapshot_id=snapshot.snapshot_id,
            artifacts=[
                StagedKnowledgeArtifact(
                    artifact_kind=KnowledgeArtifactKind.FINDINGS,
                    schema_version="1.0.0",
                    payload=payload,
                )
            ],
        )
        assert completed.status.value == "completed"

    with FileKnowledgeStore(tmp_path / "knowledge", max_json_bytes=bound) as store:
        document = store.runs.read_artifact_payload(run.run_id, KnowledgeArtifactKind.FINDINGS)
        assert isinstance(document, dict)
        assert document["findings"][0]["evidence"] == payload["findings"][0]["evidence"]


def test_over_bound_failure_leaves_no_completed_run_or_findings_blob(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge", max_json_bytes=2048) as store:
        record = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.LOCAL,
                display_name="bounded",
                local_path=tmp_path / "bounded",
            )
        )
        manifest = make_manifest()
        snapshot = store.snapshots.create_or_get_snapshot(
            repository_id=record.repository_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            manifest=manifest,
            content_fingerprint=fingerprint_for(manifest),
        )
        run = store.runs.create_run(
            repository_id=record.repository_id,
            assessment_mode="deterministic",
            codestrata_version="0.3.0",
            ruleset_version="1.2.0",
        )
        blobs_before = set(store.blobs_directory.glob("**/*"))
        with pytest.raises(KnowledgeStoreError, match="output bound"):
            store.runs.complete_run(
                run.run_id,
                snapshot_id=snapshot.snapshot_id,
                artifacts=[
                    StagedKnowledgeArtifact(
                        artifact_kind=KnowledgeArtifactKind.FINDINGS,
                        schema_version="1.0.0",
                        payload={"findings": [{"evidence": "x" * 4096}]},
                    )
                ],
            )
        assert store.runs.get_latest_completed_run(record.repository_id) is None
        blobs_after = set(store.blobs_directory.glob("**/*"))
        assert blobs_after == blobs_before
