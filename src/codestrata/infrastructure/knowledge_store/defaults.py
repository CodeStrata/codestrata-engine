"""Infrastructure defaults for the SQLite knowledge store."""

from __future__ import annotations

import os
from pathlib import Path

from codestrata.application.knowledge.lock_policy import knowledge_lock_timeout_seconds

DEFAULT_KNOWLEDGE_DIRECTORY = Path(".codestrata/knowledge")
KNOWLEDGE_DIRECTORY_ENV = "CODESTRATA_KNOWLEDGE_DIRECTORY"

__all__ = [
    "DEFAULT_KNOWLEDGE_DIRECTORY",
    "KNOWLEDGE_DIRECTORY_ENV",
    "default_knowledge_directory",
    "knowledge_lock_timeout_seconds",
]


def default_knowledge_directory() -> Path:
    """Return the host default, or a test/session override when set."""

    override = os.environ.get(KNOWLEDGE_DIRECTORY_ENV, "").strip()
    if override:
        return Path(override)
    return DEFAULT_KNOWLEDGE_DIRECTORY


DATABASE_FILENAME = "knowledge.sqlite"
LOCKS_DIRECTORY_NAME = "locks"
BLOBS_DIRECTORY_NAME = "blobs"
TMP_DIRECTORY_NAME = "tmp"
SCHEMA_VERSION_KEY = "schema_version"
CURRENT_SCHEMA_VERSION = 3
DEFAULT_BUSY_TIMEOUT_MS = 5_000
DEFAULT_STALE_RUN_SECONDS = 6 * 60 * 60
BLOB_KIND_DIRECTORIES = {
    "repository_manifest": "manifests",
    "repository_graph": "graphs",
    "engineering_knowledge_graph": "graphs",
    "knowledge_bindings": "graphs",
    "assessment_graph": "graphs",
    "findings": "findings",
    "recommendations": "recommendations",
    "ai_execution": "ai",
    "ai_enrichment": "ai",
}
