"""Local status/health for the file knowledge store (no HTTP, no database)."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.application.knowledge.models import AssessmentRunStatus
from codestrata.infrastructure.knowledge_store.defaults import DATABASE_FILENAME
from codestrata.infrastructure.knowledge_store.file.indexes import iter_repository_ids
from codestrata.infrastructure.knowledge_store.file.layout import (
    FILE_STORE_SCHEMA_VERSION,
    FileStorePaths,
)
from codestrata.infrastructure.knowledge_store.io import iter_jsonl


@dataclass(frozen=True, slots=True)
class FileKnowledgeHealth:
    """Headless local health independent of assessment truth."""

    backend: str
    schema_version: int
    open: bool
    sqlite_present_untouched: bool
    derived_index_present: bool
    running_runs: int
    completed_runs: int
    tmp_leftovers: int
    ok: bool
    issues: tuple[str, ...]


def collect_health(
    paths: FileStorePaths,
    *,
    is_open: bool,
    schema_version: int,
    runs: object | None,
) -> FileKnowledgeHealth:
    issues: list[str] = []
    sqlite_path = paths.root / DATABASE_FILENAME
    sqlite_present = sqlite_path.is_file()
    index_path = paths.index_path("repositories.jsonl")
    derived = index_path.is_file()
    if not derived:
        issues.append("derived repository index missing")

    running = 0
    completed = 0
    if runs is not None:
        list_runs = getattr(runs, "list_runs", None)
        if callable(list_runs):
            for repository_id in iter_repository_ids(paths):
                for run in list_runs(repository_id, limit=500):
                    if run.status is AssessmentRunStatus.RUNNING:
                        running += 1
                    elif run.status is AssessmentRunStatus.COMPLETED:
                        completed += 1
    else:
        try:
            for row in iter_jsonl(paths.index_path("runs.jsonl"), root=paths.root):
                status = str(row.get("status", ""))
                if status == AssessmentRunStatus.RUNNING.value:
                    running += 1
                elif status == AssessmentRunStatus.COMPLETED.value:
                    completed += 1
        except Exception as error:  # noqa: BLE001
            issues.append(f"run index unreadable: {error}")

    tmp_leftovers = 0
    if paths.tmp.is_dir():
        tmp_leftovers = sum(1 for item in paths.tmp.iterdir() if item.is_file())

    ok = is_open and schema_version == FILE_STORE_SCHEMA_VERSION and not issues
    return FileKnowledgeHealth(
        backend="file",
        schema_version=schema_version,
        open=is_open,
        sqlite_present_untouched=sqlite_present,
        derived_index_present=derived,
        running_runs=running,
        completed_runs=completed,
        tmp_leftovers=tmp_leftovers,
        ok=ok,
        issues=tuple(issues),
    )
