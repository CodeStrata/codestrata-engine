"""On-disk layout for the bounded file knowledge store."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.infrastructure.knowledge_store.defaults import (
    BLOBS_DIRECTORY_NAME,
    LOCKS_DIRECTORY_NAME,
    TMP_DIRECTORY_NAME,
)
from codestrata.infrastructure.knowledge_store.io import DEFAULT_MAX_JSON_BYTES

STORE_MANIFEST_NAME = "store.json"
REPOSITORIES_DIRNAME = "repositories"
INDEXES_DIRNAME = "indexes"
STAGING_DIRNAME = "staging"
SNAPSHOTS_DIRNAME = "snapshots"
RUNS_DIRNAME = "runs"
ALIASES_FILENAME = "aliases.json"
REPOSITORY_MANIFEST_NAME = "repository.json"
RUN_MANIFEST_NAME = "run.json"
ARTIFACTS_MANIFEST_NAME = "artifacts.json"
FILE_STORE_FORMAT = "codestrata-file-knowledge-store"
FILE_STORE_SCHEMA_VERSION = 1

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def require_safe_id(value: str, *, field: str) -> str:
    compact = value.strip()
    if (
        not compact
        or not _SAFE_ID.fullmatch(compact)
        or ".." in compact
        or "/" in compact
        or "\\" in compact
        or compact.startswith(".")
    ):
        raise KnowledgeStoreError(f"Illegal {field}: path-unsafe identifier")
    return compact


@dataclass(frozen=True, slots=True)
class FileStorePaths:
    """Resolved directories under a knowledge root."""

    root: Path
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES

    @property
    def store_manifest(self) -> Path:
        return self.root / STORE_MANIFEST_NAME

    @property
    def repositories(self) -> Path:
        return self.root / REPOSITORIES_DIRNAME

    @property
    def indexes(self) -> Path:
        return self.root / INDEXES_DIRNAME

    @property
    def staging(self) -> Path:
        return self.root / STAGING_DIRNAME

    @property
    def locks(self) -> Path:
        return self.root / LOCKS_DIRECTORY_NAME

    @property
    def blobs(self) -> Path:
        return self.root / BLOBS_DIRECTORY_NAME

    @property
    def tmp(self) -> Path:
        return self.root / TMP_DIRECTORY_NAME

    def repository_dir(self, repository_id: str) -> Path:
        return self.repositories / require_safe_id(repository_id, field="repository_id")

    def repository_manifest(self, repository_id: str) -> Path:
        return self.repository_dir(repository_id) / REPOSITORY_MANIFEST_NAME

    def aliases_path(self, repository_id: str) -> Path:
        return self.repository_dir(repository_id) / ALIASES_FILENAME

    def snapshots_dir(self, repository_id: str) -> Path:
        return self.repository_dir(repository_id) / SNAPSHOTS_DIRNAME

    def snapshot_manifest(self, repository_id: str, snapshot_id: str) -> Path:
        safe_snap = require_safe_id(snapshot_id, field="snapshot_id")
        return self.snapshots_dir(repository_id) / f"{safe_snap}.json"

    def runs_dir(self, repository_id: str) -> Path:
        return self.repository_dir(repository_id) / RUNS_DIRNAME

    def run_dir(self, repository_id: str, run_id: str) -> Path:
        return self.runs_dir(repository_id) / require_safe_id(run_id, field="run_id")

    def run_manifest(self, repository_id: str, run_id: str) -> Path:
        return self.run_dir(repository_id, run_id) / RUN_MANIFEST_NAME

    def artifacts_manifest(self, repository_id: str, run_id: str) -> Path:
        return self.run_dir(repository_id, run_id) / ARTIFACTS_MANIFEST_NAME

    def index_path(self, name: str) -> Path:
        if name not in {
            "repositories.jsonl",
            "aliases.jsonl",
            "snapshots.jsonl",
            "runs.jsonl",
        }:
            raise KnowledgeStoreError(f"Unknown derived index: {name}")
        return self.indexes / name
