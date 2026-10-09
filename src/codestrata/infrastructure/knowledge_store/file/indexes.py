"""Scan valid manifests and rebuild derived JSONL indexes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.infrastructure.knowledge_store.file.codec import (
    aliases_from_document,
    artifacts_from_document,
    repository_from_document,
    run_document,
    run_from_document,
    snapshot_document,
    snapshot_from_document,
)
from codestrata.infrastructure.knowledge_store.file.layout import (
    REPOSITORY_MANIFEST_NAME,
    RUN_MANIFEST_NAME,
    FileStorePaths,
    require_safe_id,
)
from codestrata.infrastructure.knowledge_store.io import (
    DEFAULT_MAX_STREAM_RECORDS,
    atomic_write_json,
    read_json_file,
    write_jsonl,
)
from codestrata.infrastructure.knowledge_store.sqlite.locking import repository_file_lock


def iter_repository_ids(paths: FileStorePaths) -> Iterator[str]:
    if not paths.repositories.is_dir():
        return
    try:
        children = sorted(paths.repositories.iterdir())
    except OSError:
        return
    for child in children:
        if not child.is_dir() or child.is_symlink():
            continue
        try:
            require_safe_id(child.name, field="repository_id")
        except KnowledgeStoreError:
            continue
        manifest = child / REPOSITORY_MANIFEST_NAME
        if manifest.is_file() and not manifest.is_symlink():
            yield child.name


def load_valid_repository(paths: FileStorePaths, repository_id: str) -> dict[str, Any] | None:
    manifest = paths.repository_manifest(repository_id)
    if not manifest.is_file() or manifest.is_symlink():
        return None
    try:
        document = read_json_file(manifest, root=paths.root)
        if not isinstance(document, dict):
            return None
        record = repository_from_document(document)
    except (KnowledgeStoreError, OSError, KeyError, ValueError, TypeError):
        return None
    if record.repository_id != repository_id:
        return None
    return document


def rebuild_derived_indexes(paths: FileStorePaths, *, tmp_directory: Any | None = None) -> int:
    """Rebuild JSONL indexes from valid manifests only. Never mutates source manifests."""

    paths.locks.mkdir(parents=True, exist_ok=True)
    with repository_file_lock(paths.locks, "derived-indexes", timeout_seconds=30.0):
        return _rebuild_derived_indexes_unlocked(paths, tmp_directory=tmp_directory)


def _rebuild_derived_indexes_unlocked(
    paths: FileStorePaths, *, tmp_directory: Any | None = None
) -> int:
    tmp = tmp_directory or paths.tmp
    repo_rows: list[dict[str, Any]] = []
    alias_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    for repository_id in iter_repository_ids(paths):
        document = load_valid_repository(paths, repository_id)
        if document is None:
            continue
        repo_rows.append(document)
        aliases_path = paths.aliases_path(repository_id)
        if aliases_path.is_file() and not aliases_path.is_symlink():
            try:
                aliases = aliases_from_document(read_json_file(aliases_path, root=paths.root))
            except (KnowledgeStoreError, OSError, KeyError, ValueError, TypeError):
                aliases = ()
            for alias in aliases:
                alias_rows.append(
                    {
                        "repository_id": alias.repository_id,
                        "alias_type": alias.alias_type.value,
                        "alias_value": alias.alias_value,
                        "created_at": document["updated_at"],
                    }
                )
        snapshots_dir = paths.snapshots_dir(repository_id)
        if snapshots_dir.is_dir() and not snapshots_dir.is_symlink():
            for snap_file in sorted(snapshots_dir.glob("*.json")):
                if snap_file.is_symlink() or not snap_file.is_file():
                    continue
                try:
                    snap_doc = read_json_file(snap_file, root=paths.root)
                    record = snapshot_from_document(snap_doc)
                except (KnowledgeStoreError, OSError, KeyError, ValueError, TypeError):
                    continue
                snapshot_rows.append(snapshot_document(record))
        runs_dir = paths.runs_dir(repository_id)
        if runs_dir.is_dir() and not runs_dir.is_symlink():
            for run_dir in sorted(runs_dir.iterdir()):
                if not run_dir.is_dir() or run_dir.is_symlink():
                    continue
                run_file = run_dir / RUN_MANIFEST_NAME
                if not run_file.is_file() or run_file.is_symlink():
                    continue
                try:
                    run_doc = read_json_file(run_file, root=paths.root)
                    run = run_from_document(run_doc)
                except (KnowledgeStoreError, OSError, KeyError, ValueError, TypeError):
                    continue
                artifacts_path = paths.artifacts_manifest(repository_id, run.run_id)
                if run.status.value == "completed":
                    if not artifacts_path.is_file():
                        # Incomplete finalize — do not advertise as completed.
                        continue
                    try:
                        artifacts_from_document(read_json_file(artifacts_path, root=paths.root))
                    except (KnowledgeStoreError, OSError, KeyError, ValueError, TypeError):
                        continue
                run_rows.append(run_document(run))

    repo_rows.sort(key=lambda item: str(item.get("canonical_key", "")))
    alias_rows.sort(
        key=lambda item: (
            str(item.get("alias_type", "")),
            str(item.get("alias_value", "")),
        )
    )
    snapshot_rows.sort(key=lambda item: str(item.get("captured_at", "")), reverse=True)
    run_rows.sort(key=lambda item: str(item.get("started_at", "")), reverse=True)
    indexed_repositories = repo_rows[:DEFAULT_MAX_STREAM_RECORDS]
    indexed_aliases = alias_rows[:DEFAULT_MAX_STREAM_RECORDS]
    indexed_snapshots = snapshot_rows[:DEFAULT_MAX_STREAM_RECORDS]
    indexed_runs = run_rows[:DEFAULT_MAX_STREAM_RECORDS]

    paths.indexes.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        paths.index_path("repositories.jsonl"),
        indexed_repositories,
        tmp_directory=tmp,
    )
    write_jsonl(paths.index_path("aliases.jsonl"), indexed_aliases, tmp_directory=tmp)
    write_jsonl(paths.index_path("snapshots.jsonl"), indexed_snapshots, tmp_directory=tmp)
    write_jsonl(paths.index_path("runs.jsonl"), indexed_runs, tmp_directory=tmp)
    marker = {
        "schema": "codestrata-derived-index:1",
        "rebuilt": True,
        "repository_count": len(repo_rows),
        "repository_indexed_count": len(indexed_repositories),
        "snapshot_count": len(snapshot_rows),
        "snapshot_indexed_count": len(indexed_snapshots),
        "run_count": len(run_rows),
        "run_indexed_count": len(indexed_runs),
        "truncated": any(
            len(source) > DEFAULT_MAX_STREAM_RECORDS
            for source in (repo_rows, alias_rows, snapshot_rows, run_rows)
        ),
    }
    atomic_write_json(paths.indexes / "rebuild-marker.json", marker, tmp_directory=tmp)
    return len(repo_rows)
