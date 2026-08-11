"""Deterministic SharedRule registry."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from codestrata.application.rules.errors import RuleRegistryError
from codestrata.application.rules.models import RuleInspectionView
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.rule_confidence import RuleConfidence


class RuleRegistry:
    """Explicit registration only — no dynamic imports or plugins."""

    def __init__(self) -> None:
        self._rules: dict[str, SharedRule] = {}
        self._production_flags: dict[str, bool] = {}

    def register(self, rule: SharedRule, *, production: bool = True) -> None:
        metadata = rule.metadata
        rule_id = str(metadata.rule_id)
        if not isinstance(metadata.confidence, RuleConfidence):
            raise RuleRegistryError(
                f"Rule Confidence metadata is required for {rule_id}",
                reason_code="missing_rule_confidence",
                rule_id=rule_id,
            )
        existing = self._rules.get(rule_id)
        if existing is not None:
            if str(existing.metadata.version) != str(metadata.version):
                raise RuleRegistryError(
                    f"Conflicting versions for rule {rule_id}: "
                    f"{existing.metadata.version} vs {metadata.version}",
                    reason_code="conflicting_rule_version",
                    rule_id=rule_id,
                )
            raise RuleRegistryError(
                f"Duplicate rule ID: {rule_id}",
                reason_code="duplicate_rule_id",
                rule_id=rule_id,
            )
        self._rules[rule_id] = rule
        self._production_flags[rule_id] = production

    def register_collection(
        self,
        rules: Sequence[SharedRule] | Iterable[SharedRule],
        *,
        production: bool = True,
    ) -> None:
        for rule in rules:
            self.register(rule, production=production)

    def get(self, rule_id: str) -> SharedRule:
        key = rule_id.strip().lower()
        rule = self._rules.get(key)
        if rule is None:
            raise RuleRegistryError(
                f"Unknown rule: {rule_id}",
                reason_code="rule_not_found",
                rule_id=rule_id,
            )
        return rule

    def list_rules(
        self,
        *,
        category: RuleCategory | None = None,
        language: str | None = None,
        enabled_only: bool = False,
        include_non_production: bool = False,
    ) -> tuple[RuleInspectionView, ...]:
        views: list[RuleInspectionView] = []
        for rule_id in sorted(self._rules):
            rule = self._rules[rule_id]
            production = self._production_flags.get(rule_id, True)
            if not include_non_production and not production:
                continue
            meta = rule.metadata
            if category is not None and meta.category is not category:
                continue
            if enabled_only and not meta.enabled_by_default:
                continue
            if language is not None:
                lang = language.strip().lower()
                supported = meta.supported_languages
                if supported and lang not in supported:
                    continue
            views.append(RuleInspectionView(metadata=meta, production=production))
        return tuple(views)

    def metadata_for(self, rule_id: str) -> RuleMetadata:
        return self.get(rule_id).metadata

    def validate(self) -> None:
        for rule_id, rule in self._rules.items():
            if str(rule.metadata.rule_id) != rule_id:
                raise RuleRegistryError(
                    "Rule metadata ID mismatch",
                    reason_code="metadata_mismatch",
                    rule_id=rule_id,
                )

    def is_production(self, rule_id: str) -> bool:
        return self._production_flags.get(rule_id.strip().lower(), False)

    @property
    def size(self) -> int:
        return len(self._rules)
