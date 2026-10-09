"""In-memory and file-backed catalogs of pinned Rule and RuleSet documents."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from codestrata.application.rules.composition.bounds import FLOATING_REF_MARKERS
from codestrata.application.rules.composition.errors import ResolutionError
from codestrata.application.rules.composition.loader import load_document_file, resolve_catalog_path
from codestrata.domain.contracts.rules import (
    ContractError,
    ParentRef,
    Rule,
    RuleSet,
    parse_rule,
    parse_ruleset,
)
from codestrata.domain.contracts.serialization import require_pinned_version


class RuleCatalog:
    """Lookup by immutable id/version/digest. No URLs or runtime fetch."""

    def __init__(self, rulesets: Iterable[RuleSet], rules: Iterable[Rule]) -> None:
        self._rulesets_by_digest: dict[str, RuleSet] = {}
        self._rulesets_by_id: dict[tuple[str, str], RuleSet] = {}
        self._rules_by_digest: dict[str, Rule] = {}
        self._rules_by_id: dict[tuple[str, str], Rule] = {}
        for ruleset in rulesets:
            self._add_ruleset(ruleset)
        for rule in rules:
            self._add_rule(rule)

    def _add_ruleset(self, ruleset: RuleSet) -> None:
        digest = ruleset.digest
        identity = (ruleset.metadata.id, ruleset.metadata.version)
        existing = self._rulesets_by_digest.get(digest)
        if existing is not None and existing != ruleset:
            raise ResolutionError("duplicate_ruleset", f"conflicting RuleSet digest {digest}")
        self._rulesets_by_digest[digest] = ruleset
        prior = self._rulesets_by_id.get(identity)
        if prior is not None and prior.digest != digest:
            raise ResolutionError(
                "duplicate_identity",
                f"RuleSet {identity[0]}@{identity[1]} has conflicting digests",
            )
        self._rulesets_by_id[identity] = ruleset

    def _add_rule(self, rule: Rule) -> None:
        digest = rule.digest
        identity = (rule.metadata.id, rule.metadata.version)
        existing = self._rules_by_digest.get(digest)
        if existing is not None and existing != rule:
            raise ResolutionError("duplicate_rule", f"conflicting Rule digest {digest}")
        self._rules_by_digest[digest] = rule
        prior = self._rules_by_id.get(identity)
        if prior is not None and prior.digest != digest:
            raise ResolutionError(
                "duplicate_identity",
                f"Rule {identity[0]}@{identity[1]} has conflicting digests",
            )
        self._rules_by_id[identity] = rule

    def rulesets(self) -> tuple[RuleSet, ...]:
        return tuple(sorted(self._rulesets_by_digest.values(), key=lambda item: item.metadata.id))

    def get_ruleset(self, ref: ParentRef) -> RuleSet:
        _reject_floating(ref.id, ref.version)
        found = self._rulesets_by_digest.get(ref.digest)
        if found is None:
            raise ResolutionError(
                "missing_reference",
                f"missing parent RuleSet {ref.id}@{ref.version} digest {ref.digest}",
            )
        if found.metadata.id != ref.id or found.metadata.version != ref.version:
            raise ResolutionError(
                "missing_reference",
                f"parent pin {ref.id}@{ref.version} does not match catalog document",
            )
        if found.digest != ref.digest:
            raise ResolutionError("missing_reference", "parent digest mismatch")
        return found

    def get_rule(self, rule_id: str, revision: str, digest: str) -> Rule:
        _reject_floating(rule_id, revision)
        found = self._rules_by_digest.get(digest)
        if found is None:
            raise ResolutionError(
                "missing_reference",
                f"missing Rule {rule_id}@{revision} digest {digest}",
            )
        if found.metadata.id != rule_id or found.metadata.version != revision:
            raise ResolutionError(
                "missing_reference",
                f"rule pin {rule_id}@{revision} does not match catalog document",
            )
        return found


def catalog_from_mapping(
    rulesets: Mapping[str, RuleSet] | Iterable[RuleSet],
    rules: Mapping[str, Rule] | Iterable[Rule],
) -> RuleCatalog:
    ruleset_items = rulesets.values() if isinstance(rulesets, Mapping) else rulesets
    rule_items = rules.values() if isinstance(rules, Mapping) else rules
    return RuleCatalog(ruleset_items, rule_items)


def catalog_from_directory(root: Path) -> RuleCatalog:
    root_resolved = root.resolve()
    if not root_resolved.is_dir():
        raise ResolutionError("missing_file", f"catalog root {root} is not a directory")
    rulesets: list[RuleSet] = []
    rules: list[Rule] = []
    for path in sorted(root_resolved.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            continue
        resolve_catalog_path(root_resolved, path)
        document = load_document_file(path, root=root_resolved)
        kind = str(document.get("kind") or "")
        try:
            if kind == "RuleSet":
                rulesets.append(parse_ruleset(document))
            elif kind == "Rule":
                rules.append(parse_rule(document))
            else:
                raise ResolutionError("invalid_document", f"{path.name} is not a Rule or RuleSet")
        except ContractError as error:
            message = str(error)
            lowered = message.lower()
            if "floating" in lowered or "pinned" in lowered:
                raise ResolutionError("floating_reference", message) from error
            raise ResolutionError("invalid_document", message) from error
    if not rulesets:
        raise ResolutionError("missing_reference", "catalog contains no RuleSet documents")
    return RuleCatalog(rulesets, rules)


def _reject_floating(identity: str, version: str) -> None:
    compact_id = identity.strip().lower()
    if "://" in compact_id or compact_id.startswith(("http:", "https:", "git+", "s3:")):
        raise ResolutionError("floating_reference", f"mutable URL reference rejected: {identity}")
    token = version.strip().lower()
    if token in FLOATING_REF_MARKERS:
        raise ResolutionError("floating_reference", f"floating version {version!r} rejected")
    require_pinned_version(version, label="catalog version")
