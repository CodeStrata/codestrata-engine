"""Load the E00.3 isolation policy. This is documentation plus executable checks."""

from __future__ import annotations

from pathlib import Path

import yaml

from verification.release_isolation.models import (
    CandidateNamespaces,
    IsolationLanes,
    IsolationPolicy,
    RollbackArtifact,
)

POLICY_FILENAME = "policy.yaml"


def default_policy_path() -> Path:
    return Path(__file__).resolve().parent / POLICY_FILENAME


def load_policy(path: Path | None = None) -> IsolationPolicy:
    target = path or default_policy_path()
    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("isolation policy is not a mapping")
    lanes = payload["lanes"]
    namespaces = payload["namespaces"]
    rollback = payload["rollback"]
    return IsolationPolicy(
        lanes=IsolationLanes(
            integration=str(lanes["integration"]),
            maintenance=str(lanes["maintenance"]),
            story_prefix=str(lanes["story_prefix"]),
            hotfix_prefix=str(lanes["hotfix_prefix"]),
        ),
        namespaces=CandidateNamespaces(
            venv=str(namespaces["venv"]),
            output=str(namespaces["output"]),
            versioned_output_template=str(namespaces["versioned_output_template"]),
            quality_logs=str(namespaces["quality_logs"]),
            rollback_venv=str(namespaces["rollback_venv"]),
            live_output_forbidden=tuple(str(item) for item in namespaces["live_output_forbidden"]),
        ),
        rollback=RollbackArtifact(
            name=str(rollback["name"]),
            version=str(rollback["version"]),
            sha256=str(rollback["sha256"]),
            notes=str(rollback["notes"]),
        ),
        required_push_glob=str(payload["required_push_glob"]),
        ordinary_ci_workflow=str(payload["ordinary_ci_workflow"]),
    )
