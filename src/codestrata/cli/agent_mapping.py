"""CLI wrappers around transport-neutral agent serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from codestrata.application.agents.serialization import (
    DEFAULT_EVIDENCE_SUMMARY_LIMIT,
    DEFAULT_ISSUE_LIMIT,
    DEFAULT_TOP_ITEMS,
    agent_result_to_dict,
    exit_code_for_status,
    map_modernization_review,
    map_repository_assessment,
    map_repository_review,
    map_snapshot_review,
    map_validation,
    map_validation_workflow,
)

EXIT_SUCCESS = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2

__all__ = [
    "DEFAULT_EVIDENCE_SUMMARY_LIMIT",
    "DEFAULT_ISSUE_LIMIT",
    "DEFAULT_TOP_ITEMS",
    "EXIT_BLOCKED",
    "EXIT_ERROR",
    "EXIT_SUCCESS",
    "agent_result_to_dict",
    "dumps_agent_json",
    "exit_code_for_status",
    "map_modernization_review",
    "map_repository_assessment",
    "map_repository_review",
    "map_snapshot_review",
    "map_validation",
    "map_validation_workflow",
]


def dumps_agent_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
