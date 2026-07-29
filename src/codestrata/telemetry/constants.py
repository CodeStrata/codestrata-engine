"""Telemetry constants — schema version, events, and allowlists."""

from __future__ import annotations

from enum import StrEnum

SCHEMA_VERSION = "1.0.0"

# Local state under ~/.codestrata/ (override with CODESTRATA_HOME for tests).
INSTALLATION_ID_FILENAME = "installation_id"
PREFERENCES_FILENAME = "telemetry.json"
QUEUE_FILENAME = "telemetry-queue.jsonl"

# Endpoint override (optional). When unset, events stay queued locally.
ENDPOINT_ENV = "CODESTRATA_TELEMETRY_ENDPOINT"
HOME_ENV = "CODESTRATA_HOME"
# Force off (CI / automation). Does not enable by default when unset.
FORCE_DISABLE_ENV = "CODESTRATA_TELEMETRY"
SKIP_PROMPT_ENV = "CODESTRATA_TELEMETRY_SKIP_PROMPT"


class EventName(StrEnum):
    INSTALLATION_CREATED = "installation_created"
    TELEMETRY_ENABLED = "telemetry_enabled"
    TELEMETRY_DISABLED = "telemetry_disabled"
    ASSESSMENT_STARTED = "assessment_started"
    ASSESSMENT_COMPLETED = "assessment_completed"
    ASSESSMENT_FAILED = "assessment_failed"
    REPORT_OPENED = "report_opened"
    AI_USED = "ai_used"
    VERSION_CHECK = "version_check"
    UPGRADE_COMPLETED = "upgrade_completed"


ALLOWED_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "event",
        "installation_id",
        "codestrata_version",
        "os",
        "python_version",
        "command",
        "enabled_assessment_domains",
        "language_categories",
        "repository_size_band",
        "duration_band",
        "ai_enabled",
        "success",
        "timestamp",
        "previous_version",
        "queue_depth",
    }
)

FORBIDDEN_SUBSTRINGS = frozenset(
    {
        "password",
        "secret",
        "token",
        "credential",
        "api_key",
        "private_key",
        "hostname",
        "username",
        "email",
        "repository_name",
        "repository_url",
        "git_remote",
        "file_name",
        "filename",
        "filepath",
        "prompt",
        "finding",
        "recommendation",
        "source_code",
    }
)

LANGUAGE_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".java": "java",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".cs": "csharp",
    ".rs": "rust",
}

SIZE_BANDS: tuple[tuple[int | None, str], ...] = (
    (100, "0-100"),
    (500, "101-500"),
    (1000, "501-1000"),
    (5000, "1001-5000"),
    (10000, "5001-10000"),
    (None, "10000+"),
)

DURATION_BANDS_MS: tuple[tuple[float | None, str], ...] = (
    (5_000.0, "0-5s"),
    (30_000.0, "5-30s"),
    (60_000.0, "30-60s"),
    (300_000.0, "1-5m"),
    (900_000.0, "5-15m"),
    (None, "15m+"),
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".codestrata",
        ".export-staging",
    }
)
