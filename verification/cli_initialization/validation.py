"""Configuration validation for generated codestrata.toml."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from verification.cli_initialization.contract import (
    FORBIDDEN_CONFIG_MARKERS,
    REQUIRED_CONFIG_MARKERS,
    InitializationContract,
    default_contract,
)

_ABS_PATH = re.compile(r"(?i)(^|[\s=\"'])(/Users/|/home/|[A-Za-z]:\\)")
_HOME_TILDE = re.compile(r"(?i)(^|[\s=\"'])~/")


def parse_config(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def validate_generated_config(
    path: Path,
    *,
    contract: InitializationContract | None = None,
) -> tuple[bool, list[str], dict[str, Any]]:
    """Validate defaults and safety of generated configuration."""

    active = contract or default_contract()
    failures: list[str] = []
    evidence: dict[str, Any] = {}
    raw = path.read_text(encoding="utf-8")
    evidence["newline"] = "lf" if "\r\n" not in raw else "crlf"
    evidence["encoding"] = "utf-8"
    evidence["ends_with_newline"] = raw.endswith("\n")

    for marker in REQUIRED_CONFIG_MARKERS:
        if marker not in raw:
            failures.append(f"missing_marker:{marker}")
    for marker in FORBIDDEN_CONFIG_MARKERS:
        if marker.lower() in raw.lower():
            failures.append(f"forbidden_marker:{marker}")

    if _ABS_PATH.search(raw) or _HOME_TILDE.search(raw):
        failures.append("absolute_or_home_path_in_config")

    try:
        data = parse_config(path)
    except Exception as error:  # noqa: BLE001 — report parse failure
        failures.append(f"parse_error:{error.__class__.__name__}")
        return False, failures, evidence

    evidence["top_level_keys"] = sorted(data.keys())
    repo = data.get("repository") or {}
    if repo.get("path") != ".":
        failures.append("repository.path_not_dot")
    # Current template places `profile = "community"` inside the [repository]
    # table (TOML continuation). Accept either nesting as long as value matches.
    profile = data.get("profile")
    if profile is None:
        profile = repo.get("profile")
    if profile != "community":
        failures.append("profile_not_community")
    evidence["profile"] = profile
    evidence["profile_location"] = (
        "top_level"
        if "profile" in data
        else ("repository" if "profile" in repo else "missing")
    )

    knowledge = data.get("knowledge") or {}
    if knowledge.get("enabled") is not False:
        failures.append("knowledge_not_disabled")

    static_analysis = data.get("static_analysis") or {}
    if static_analysis.get("enabled") is not False:
        failures.append("static_analysis_not_disabled")

    ai = data.get("ai") or {}
    if "provider" not in ai:
        failures.append("ai_provider_missing")
    # Presence of provider is not silent enablement; assess requires --with-ai.
    evidence["ai_provider"] = ai.get("provider")
    evidence["telemetry_section_present"] = "telemetry" in data
    if data.get("telemetry") not in (None, {}):
        tel = data.get("telemetry") or {}
        if tel.get("enabled") is True:
            failures.append("telemetry_enabled")

    if active.telemetry_enabled_by_default:
        failures.append("contract_claims_telemetry_enabled")
    if active.ai_silently_enabled:
        failures.append("contract_claims_ai_silently_enabled")

    # Workspace/knowledge dirs must remain relative.
    workspace = data.get("workspace") or {}
    if str(workspace.get("directory", "")).startswith(("/", "~")):
        failures.append("workspace_absolute")
    if str(knowledge.get("directory", "")).startswith(("/", "~")):
        failures.append("knowledge_absolute")

    return (not failures), failures, evidence


def configs_byte_identical(first: Path, second: Path) -> bool:
    return first.read_bytes() == second.read_bytes()
