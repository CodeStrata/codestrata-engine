"""Load the executable Engine quality-command manifest."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from verification.quality_commands.models import (
    CommandStatus,
    CoveragePolicy,
    EngineTestsJob,
    QualityCommand,
    QualityManifest,
    SecurityScanner,
)

MANIFEST_FILENAME = "manifest.yaml"
# E00.2 requires these ids in the YAML so a trimmed file cannot silently drop a gate.
REQUIRED_COMMAND_IDS: tuple[str, ...] = (
    "pip-check",
    "ruff",
    "mypy",
    "pytest-coverage",
    "pip-audit",
)


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parent / MANIFEST_FILENAME


def _require_mapping(payload: object, label: str) -> Mapping[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a mapping")
    return payload


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("expected a list of strings")
    return tuple(str(item) for item in value)


def _status(value: object, default: CommandStatus) -> CommandStatus:
    if value is None:
        return default
    return CommandStatus(str(value))


def load_manifest(path: Path | None = None) -> QualityManifest:
    """Parse YAML into typed records. Missing required command ids is an error."""
    manifest_path = path or default_manifest_path()
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    data = _require_mapping(payload, "manifest")
    coverage_raw = _require_mapping(data.get("coverage"), "coverage")
    job_raw = _require_mapping(data.get("engine_tests_job"), "engine_tests_job")
    scanner_raw = _require_mapping(data.get("security_scanner"), "security_scanner")
    commands_raw = data.get("commands")
    if not isinstance(commands_raw, list) or not commands_raw:
        raise ValueError("manifest.commands must be a non-empty list")

    commands: list[QualityCommand] = []
    for item in commands_raw:
        mapping = _require_mapping(item, "command")
        commands.append(
            QualityCommand(
                id=str(mapping["id"]),
                argv=_string_tuple(mapping.get("argv")),
                required=bool(mapping.get("required", True)),
                timeout_seconds=int(mapping.get("timeout_seconds", 300)),
                missing_tool_status=_status(
                    mapping.get("missing_tool_status"),
                    CommandStatus.BLOCKED,
                ),
            )
        )

    ids = tuple(command.id for command in commands)
    missing = [command_id for command_id in REQUIRED_COMMAND_IDS if command_id not in ids]
    if missing:
        raise ValueError(f"quality manifest is missing required commands: {missing}")

    baseline_raw = data.get("baseline_failures", {})
    baseline_notes = ""
    if isinstance(baseline_raw, dict):
        baseline_notes = str(baseline_raw.get("notes", ""))

    return QualityManifest(
        schema_version=int(data["schema_version"]),
        id=str(data["id"]),
        version=str(data["version"]),
        working_directory=str(data.get("working_directory", "engine")),
        coverage=CoveragePolicy(
            source=str(coverage_raw["source"]),
            branch=bool(coverage_raw["branch"]),
            fail_under=int(coverage_raw["fail_under"]),
        ),
        engine_tests_job=EngineTestsJob(
            name=str(job_raw["name"]),
            workflow=str(job_raw["workflow"]),
            proves=_string_tuple(job_raw.get("proves")),
            does_not_prove=_string_tuple(job_raw.get("does_not_prove")),
            reviewer_checkpoint=str(job_raw.get("reviewer_checkpoint", "required")),
            automatic_branch_protection=bool(job_raw.get("automatic_branch_protection", False)),
        ),
        security_scanner=SecurityScanner(
            id=str(scanner_raw["id"]),
            module=str(scanner_raw["module"]),
            argv=_string_tuple(scanner_raw.get("argv")),
            extra=str(scanner_raw.get("extra", "development")),
            version_constraint=str(scanner_raw.get("version_constraint", "")),
            inputs=str(scanner_raw.get("inputs", "")),
            severity_policy=str(scanner_raw.get("severity_policy", "")).strip(),
            feed_required=bool(scanner_raw.get("feed_required", True)),
        ),
        commands=tuple(commands),
        baseline_notes=baseline_notes,
    )
