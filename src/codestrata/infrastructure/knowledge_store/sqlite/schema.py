"""SQLite schema definition for knowledge store versions."""

from __future__ import annotations

SCHEMA_V1_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE schema_metadata (
        key TEXT PRIMARY KEY NOT NULL,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE repositories (
        repository_id TEXT PRIMARY KEY NOT NULL,
        canonical_key TEXT NOT NULL UNIQUE,
        source_type TEXT NOT NULL,
        display_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE repository_aliases (
        repository_id TEXT NOT NULL,
        alias_type TEXT NOT NULL,
        alias_value TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (alias_type, alias_value),
        FOREIGN KEY (repository_id)
            REFERENCES repositories(repository_id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX idx_repositories_canonical_key
        ON repositories(canonical_key)
    """,
    """
    CREATE INDEX idx_repository_aliases_repository_id
        ON repository_aliases(repository_id)
    """,
    """
    CREATE INDEX idx_repository_aliases_type_value
        ON repository_aliases(alias_type, alias_value)
    """,
)

SCHEMA_V2_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE repository_snapshots (
        snapshot_id TEXT PRIMARY KEY NOT NULL,
        repository_id TEXT NOT NULL,
        branch_name TEXT NOT NULL DEFAULT '',
        revision_type TEXT NOT NULL,
        revision_id TEXT NOT NULL,
        content_fingerprint TEXT NOT NULL,
        manifest_schema_version TEXT NOT NULL,
        manifest_blob_ref TEXT NOT NULL,
        manifest_blob_hash TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (repository_id, branch_name, content_fingerprint),
        FOREIGN KEY (repository_id)
            REFERENCES repositories(repository_id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE assessment_runs (
        run_id TEXT PRIMARY KEY NOT NULL,
        repository_id TEXT NOT NULL,
        snapshot_id TEXT,
        status TEXT NOT NULL,
        assessment_mode TEXT NOT NULL,
        codestrata_version TEXT NOT NULL,
        ruleset_version TEXT NOT NULL,
        request_fingerprint TEXT,
        invalidation_fingerprint TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        failed_at TEXT,
        error_code TEXT,
        error_message TEXT,
        FOREIGN KEY (repository_id)
            REFERENCES repositories(repository_id)
            ON DELETE CASCADE,
        FOREIGN KEY (snapshot_id)
            REFERENCES repository_snapshots(snapshot_id)
    )
    """,
    """
    CREATE TABLE knowledge_artifacts (
        artifact_id TEXT PRIMARY KEY NOT NULL,
        run_id TEXT NOT NULL,
        snapshot_id TEXT,
        artifact_kind TEXT NOT NULL,
        schema_version TEXT NOT NULL,
        blob_ref TEXT NOT NULL,
        blob_hash TEXT NOT NULL,
        source_fingerprint TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (run_id, artifact_kind),
        FOREIGN KEY (run_id)
            REFERENCES assessment_runs(run_id)
            ON DELETE CASCADE,
        FOREIGN KEY (snapshot_id)
            REFERENCES repository_snapshots(snapshot_id)
    )
    """,
    """
    CREATE INDEX idx_snapshots_repo_branch_captured
        ON repository_snapshots(repository_id, branch_name, captured_at DESC)
    """,
    """
    CREATE INDEX idx_snapshots_repo_fingerprint
        ON repository_snapshots(repository_id, content_fingerprint)
    """,
    """
    CREATE INDEX idx_runs_repo_status_started
        ON assessment_runs(repository_id, status, started_at DESC)
    """,
    """
    CREATE INDEX idx_runs_repo_completed
        ON assessment_runs(repository_id, completed_at DESC)
    """,
    """
    CREATE INDEX idx_artifacts_run_kind
        ON knowledge_artifacts(run_id, artifact_kind)
    """,
    """
    CREATE INDEX idx_artifacts_snapshot_kind
        ON knowledge_artifacts(snapshot_id, artifact_kind)
    """,
)
