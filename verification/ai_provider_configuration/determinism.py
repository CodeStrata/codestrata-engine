"""Determinism helpers and checks: two runs of this suite must produce identical JSON."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from codestrata.ai.provider_contracts.configuration_projection import project_configuration
from codestrata.ai.provider_contracts.configuration_serialization import (
    serialize_configuration_for_diagnostics,
)
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput
from verification.ai_provider_configuration.models import CheckResult


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def reports_are_identical(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return canonical_json(first) == canonical_json(second)


def check_project_configuration_is_deterministic() -> CheckResult:
    input_data = LegacyConfigurationInput(
        provider="openai", cli_model_id="gpt-4o", openai_api_key_present=True
    )
    first = serialize_configuration_for_diagnostics(project_configuration(input_data))
    second = serialize_configuration_for_diagnostics(project_configuration(input_data))
    ok = first == second
    return CheckResult(
        name="project_configuration_is_deterministic_across_repeated_calls",
        category="determinism",
        ok=ok,
        detail="identical serialized output" if ok else "serialized output differed",
    )


def check_default_configuration_hash_is_stable_across_five_runs() -> CheckResult:
    def _hash_default_configuration() -> str:
        text = serialize_configuration_for_diagnostics(
            project_configuration(LegacyConfigurationInput())
        )
        return stable_hash(json.loads(text))

    hashes = {_hash_default_configuration() for _ in range(5)}
    ok = len(hashes) == 1
    return CheckResult(
        name="default_configuration_hash_is_stable_across_five_runs",
        category="determinism",
        ok=ok,
        detail=f"distinct_hashes={len(hashes)}",
    )


def run_determinism_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_project_configuration_is_deterministic(),
        check_default_configuration_hash_is_stable_across_five_runs(),
    ]
    matrix: dict[str, Any] = {}
    return checks, matrix


__all__ = [
    "canonical_json",
    "check_default_configuration_hash_is_stable_across_five_runs",
    "check_project_configuration_is_deterministic",
    "reports_are_identical",
    "run_determinism_checks",
    "stable_hash",
]
