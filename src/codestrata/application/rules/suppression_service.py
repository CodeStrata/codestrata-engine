"""Suppression evaluation for shared rule matches."""

from __future__ import annotations

from datetime import UTC, datetime
from fnmatch import fnmatch

from codestrata.domain.rules.applicability import RuleSuppression, RuleSuppressionDecision
from codestrata.domain.rules.results import RuleMatch


class RuleSuppressionService:
    def __init__(self, suppressions: tuple[RuleSuppression, ...] = ()) -> None:
        self._suppressions = tuple(
            sorted(suppressions, key=lambda item: (str(item.rule_id), item.suppression_id))
        )

    def decide(
        self,
        match: RuleMatch,
        *,
        repository_id: str | None,
        now: datetime | None = None,
    ) -> RuleSuppressionDecision:
        current = now or datetime.now(UTC)
        for suppression in self._suppressions:
            if not suppression.is_active(now=current):
                continue
            if str(suppression.rule_id) != str(match.rule_id):
                continue
            if suppression.repository_id and repository_id:
                if suppression.repository_id != repository_id:
                    continue
            elif suppression.repository_id and not repository_id:
                continue
            if suppression.subject_reference:
                subjects = set(match.affected_entities) | set(match.subject_keys)
                subjects.update(item.subject_reference for item in match.evidence)
                if suppression.subject_reference not in subjects:
                    continue
            if suppression.path_pattern:
                paths = [
                    item.safe_location
                    for item in match.evidence
                    if item.safe_location
                ]
                if not any(fnmatch(path, suppression.path_pattern) for path in paths):
                    continue
            return RuleSuppressionDecision(
                suppressed=True,
                suppression=suppression,
                reason=suppression.reason,
            )
        return RuleSuppressionDecision(suppressed=False)
