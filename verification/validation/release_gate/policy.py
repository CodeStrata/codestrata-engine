"""Load E15.3 release-gate policy YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from verification.validation.release_gate.models import (
    CheckpointGate,
    OutOfScopeException,
    ReleaseGatePolicy,
    ReviewedException,
)

POLICY_NAME = "release-gate-policy.yaml"
EXCEPTIONS_NAME = "reviewed-exception-list.yaml"


def default_policy_path() -> Path:
    return Path(__file__).resolve().parents[1] / "corpus" / POLICY_NAME


def default_exceptions_path() -> Path:
    return Path(__file__).resolve().parents[1] / "corpus" / EXCEPTIONS_NAME


def _mapping(payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{name} is not a mapping")
    return payload


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("expected a list of strings")
    return tuple(str(item) for item in value)


def load_policy(path: Path | None = None) -> ReleaseGatePolicy:
    policy_path = path or default_policy_path()
    raw = _mapping(yaml.safe_load(policy_path.read_text(encoding="utf-8")), policy_path.name)
    gates_raw = raw.get("required_checkpoint_gates")
    if not isinstance(gates_raw, list):
        raise ValueError("required_checkpoint_gates must be a list")
    gates = tuple(
        CheckpointGate(
            id=str(_mapping(item, "gate")["id"]),
            ledger=str(_mapping(item, "gate")["ledger"]),
        )
        for item in (_mapping(entry, "gate") for entry in gates_raw)
    )
    oos_raw = raw.get("out_of_scope_exceptions") or []
    if not isinstance(oos_raw, list):
        raise ValueError("out_of_scope_exceptions must be a list")
    oos = tuple(
        OutOfScopeException(
            id=str(_mapping(item, "exception")["id"]),
            scope=str(item["scope"]),
            rationale=str(item["rationale"]),
            requires_independent_review=bool(item.get("requires_independent_review", True)),
        )
        for item in (_mapping(entry, "exception") for entry in oos_raw)
    )
    budgets = _mapping(raw.get("m33_proposed_budgets"), "m33_proposed_budgets")
    return ReleaseGatePolicy(
        package_revision=str(raw["package_revision"]),
        story=str(raw["story"]),
        measurement_id=str(raw["measurement_id"]),
        required_checkpoint_gates=gates,
        required_story_ledgers=_str_tuple(raw.get("required_story_ledgers")),
        integrated_status_markers=_str_tuple(raw.get("integrated_status_markers")),
        blocked_status_markers=_str_tuple(raw.get("blocked_status_markers")),
        out_of_scope_exceptions=oos,
        remote_tier_env=str(raw["remote_tier_env"]),
        minimum_external_pins=int(raw["minimum_external_pins"]),
        five_repos_do_not_replace_fifty=bool(raw["five_repos_do_not_replace_fifty"]),
        m33_proposed_budgets={
            "le_10k_files": str(budgets["le_10k_files"]),
            "le_100k_files": str(budgets["le_100k_files"]),
            "host": str(budgets["host"]),
            "published": bool(budgets["published"]),
        },
    )


def load_reviewed_exceptions(path: Path | None = None) -> tuple[ReviewedException, ...]:
    exc_path = path or default_exceptions_path()
    raw = _mapping(yaml.safe_load(exc_path.read_text(encoding="utf-8")), exc_path.name)
    items = raw.get("exceptions")
    if not isinstance(items, list):
        raise ValueError("exceptions must be a list")
    return tuple(
        ReviewedException(
            id=str(_mapping(item, "exception")["id"]),
            gate_or_story=str(item.get("gate_or_story") or ""),
            scope=str(item.get("scope") or ""),
            rationale=str(item.get("rationale") or ""),
            reviewed=bool(item.get("reviewed", False)),
            reviewer=str(item.get("reviewer") or ""),
            review_date=str(item.get("review_date") or ""),
        )
        for item in (_mapping(entry, "exception") for entry in items)
    )
