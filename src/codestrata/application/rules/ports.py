"""Ports for Shared Rule Platform (optional persistence / suppression sources)."""

from __future__ import annotations

from typing import Protocol

from codestrata.domain.rules.applicability import RuleSuppression


class RuleSuppressionSourcePort(Protocol):
    def list_suppressions(
        self,
        *,
        repository_id: str | None = None,
    ) -> tuple[RuleSuppression, ...]:
        ...
