"""Infrastructure defaults for the SQLite knowledge store."""

from __future__ import annotations

from pathlib import Path

DEFAULT_KNOWLEDGE_DIRECTORY = Path(".codestrata/knowledge")
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
