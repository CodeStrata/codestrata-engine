"""Collect evidence IDs that an optional explanation is allowed to cite.

IDs come from the local artifact reader. This module does not call a provider,
open a database, or transmit evidence.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.application.knowledge.artifact_evidence import LocalArtifactEvidenceService
from codestrata.application.knowledge.queries.errors import QueryBudgetExceededError

DEFAULT_EXPLANATION_EVIDENCE_BUDGET = 32


def collect_permitted_evidence_ids(
    service: LocalArtifactEvidenceService,
    local_root: str | Path,
    *,
    run_id: str | None = None,
    budget: int = DEFAULT_EXPLANATION_EVIDENCE_BUDGET,
) -> tuple[str, ...]:
    """Return evidence IDs from one local run, or raise when the page exceeds budget."""

    if budget < 1:
        raise QueryBudgetExceededError("explanation evidence budget must be >= 1")
    items, total = service.list_evidence(local_root, run_id=run_id, limit=budget, offset=0)
    if total > budget:
        raise QueryBudgetExceededError(
            f"Evidence count {total} exceeds the explanation budget of {budget}"
        )
    evidence_ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        evidence_id = item.get("evidence_id")
        if not isinstance(evidence_id, str):
            continue
        compact = evidence_id.strip()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        evidence_ids.append(compact)
    return tuple(evidence_ids)


__all__ = [
    "DEFAULT_EXPLANATION_EVIDENCE_BUDGET",
    "collect_permitted_evidence_ids",
]
