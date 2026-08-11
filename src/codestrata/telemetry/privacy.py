"""Structural privacy filtering for telemetry runtime events (Slice 9.1)."""

from __future__ import annotations

from codestrata.telemetry.errors import TelemetryRuntimeError, TelemetryRuntimeErrorCode

# Exact field-name denylist (authority). Safe categorical enum values that
# happen to contain substrings like "token" or "source" are evaluated as
# bounded enums, not via substring rejection of values.
FORBIDDEN_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "repository",
        "repository_name",
        "repository_url",
        "project",
        "project_name",
        "organization",
        "source",
        "source_code",
        "code",
        "finding",
        "findings",
        "evidence",
        "recommendation",
        "recommendations",
        "path",
        "file",
        "filepath",
        "filename",
        "file_name",
        "directory",
        "cwd",
        "argv",
        "command_line",
        "command",
        "exception",
        "exception_message",
        "traceback",
        "stack",
        "stack_trace",
        "environment",
        "env",
        "credential",
        "credentials",
        "secret",
        "token",
        "password",
        "api_key",
        "authorization",
        "cookie",
        "prompt",
        "response",
        "model_id",
        "cost",
        "email",
        "user",
        "username",
        "account",
        "customer",
        "installation_id",
        "hostname",
        "home",
        "pid",
        "ip",
        "commit",
        "branch",
        "config_path",
        "output_path",
        "report_path",
        "package_name",
        "package_names",
        "exact_token_count",
        "token_count",
    }
)

APPROVED_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "event_type",
        "client_name",
        "cli_version",
        "os_family",
        "arch_family",
        "lifecycle",
        "result",
        "duration_bucket",
        "operation_category",
        "enabled_assessment_heads",
        "offline_mode",
        "ai_used",
        "failure_category",
        "schema_version",
        "runtime_policy_version",
    }
)


def assert_field_name_allowed(name: str) -> None:
    if name in FORBIDDEN_FIELD_NAMES:
        raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_FIELD)
    if name not in APPROVED_FIELD_NAMES:
        raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNKNOWN_FIELD)


def looks_like_path_or_secret_value(value: str) -> bool:
    """Conservative detector for accidental path/secret-shaped strings."""

    lowered = value.lower()
    if any(marker in value for marker in ("/", "\\", "://")):
        return True
    if any(
        marker in lowered
        for marker in (
            "-----begin",
            "sk-",
            "password=",
            "secret=",
            "api_key=",
            "bearer ",
        )
    ):
        return True
    return False


__all__ = [
    "APPROVED_FIELD_NAMES",
    "FORBIDDEN_FIELD_NAMES",
    "assert_field_name_allowed",
    "looks_like_path_or_secret_value",
]
