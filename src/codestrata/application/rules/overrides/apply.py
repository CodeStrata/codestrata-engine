"""Apply typed policy overrides and resolved scoped exceptions to a composed RuleSet."""

from __future__ import annotations

from codestrata.application.rules.composition.catalog import RuleCatalog
from codestrata.application.rules.composition.models import ComposedRuleSet
from codestrata.application.rules.overrides.authority import assert_engine_local_payload
from codestrata.application.rules.overrides.errors import OverrideError
from codestrata.application.rules.overrides.models import (
    AppliedRule,
    OverriddenRuleSet,
    PolicyFragment,
    PolicyOverrideBundle,
    ScopedException,
    ScopedExceptionApplication,
    SubjectScope,
    TypedOverride,
    bind_overridden,
)
from codestrata.application.rules.overrides.parameters import merge_and_validate_parameters
from codestrata.application.rules.overrides.presentation import (
    PresentationFields,
    PresentationOverlay,
    merge_presentation,
)
from codestrata.domain.contracts.rules import ResolvedRule, Rule, RuleSetEntry
from codestrata.domain.contracts.serialization import digest_canonical, dumps_canonical
from codestrata.domain.findings.enums import FindingSeverity


def apply_overrides(
    composed: ComposedRuleSet,
    catalog: RuleCatalog,
    bundle: PolicyOverrideBundle | None = None,
) -> OverriddenRuleSet:
    overlay = bundle or PolicyOverrideBundle()
    assert_engine_local_payload(overlay.model_dump(mode="json"))
    composed_by_id = {entry.rule_id: entry for entry in composed.rules}
    _reject_unknown_targets(overlay, composed_by_id)

    applied: list[AppliedRule] = []
    for entry in composed.rules:
        rule = catalog.get_rule(entry.rule_id, entry.revision, entry.digest)
        policy_hits = _overrides_for(overlay.policies, entry.rule_id)
        exception_hits = tuple(item for item in overlay.exceptions if item.rule_id == entry.rule_id)
        settings, policy_refs = _merge_policy_settings(rule, entry, policy_hits)
        scoped = _merge_exceptions(rule, entry, settings, exception_hits)
        selector = _selector_digest(rule, composed)
        override_source = policy_refs[0] if _differs_from_composed(rule, entry, settings) else None
        resolved = ResolvedRule(
            rule_id=entry.rule_id,
            revision=entry.revision,
            rule_digest=entry.digest,
            enabled=settings.enabled,
            default_enabled=entry.default_enabled,
            adoption=entry.adoption,
            default_severity=rule.finding.default_severity,
            effective_severity=settings.severity,
            override_source=override_source,
            parameters=settings.parameters,
            selector_digest=selector,
            exception_refs=tuple(ref for item in scoped for ref in item.exception_refs),
            policy_refs=policy_refs,
        )
        applied.append(
            AppliedRule(
                resolved=resolved,
                presentation=settings.presentation,
                scoped_exceptions=scoped,
            )
        )

    return bind_overridden(
        {
            "composition_digest": composed.composition_digest,
            "ruleset_id": composed.ruleset_id,
            "ruleset_version": composed.ruleset_version,
            "rules": tuple(applied),
        }
    )


class _Settings:
    __slots__ = ("enabled", "severity", "parameters", "presentation")

    def __init__(
        self,
        *,
        enabled: bool,
        severity: FindingSeverity,
        parameters: dict[str, str | int | float | bool],
        presentation: PresentationFields,
    ) -> None:
        self.enabled = enabled
        self.severity = severity
        self.parameters = parameters
        self.presentation = presentation

    def fingerprint(self) -> str:
        return dumps_canonical(
            {
                "enabled": self.enabled,
                "severity": self.severity.value,
                "parameters": self.parameters,
                "presentation": self.presentation.model_dump(mode="json"),
            }
        )


def _composed_settings(rule: Rule, entry: RuleSetEntry) -> _Settings:
    severity = entry.severity_override or rule.finding.default_severity
    presentation = PresentationFields(
        message_template=rule.finding.message_template,
        documentation_url=rule.finding.documentation_url,
        bindings=rule.finding.bindings,
    )
    parameters = merge_and_validate_parameters(rule, dict(entry.parameters), {})
    return _Settings(
        enabled=entry.default_enabled,
        severity=severity,
        parameters=parameters,
        presentation=presentation,
    )


def _apply_overlay(rule: Rule, base: _Settings, override: TypedOverride) -> _Settings:
    enabled = base.enabled if override.enabled is None else override.enabled
    severity = base.severity if override.severity is None else override.severity
    parameters = merge_and_validate_parameters(
        rule, dict(base.parameters), dict(override.parameters)
    )
    presentation = merge_presentation(base.presentation, override.presentation)
    return _Settings(
        enabled=enabled,
        severity=severity,
        parameters=parameters,
        presentation=presentation,
    )


def _merge_policy_settings(
    rule: Rule,
    entry: RuleSetEntry,
    hits: tuple[tuple[str, TypedOverride], ...],
) -> tuple[_Settings, tuple[str, ...]]:
    base = _composed_settings(rule, entry)
    if not hits:
        return base, ()
    fingerprints: dict[str, list[str]] = {}
    by_fp: dict[str, _Settings] = {}
    for policy_ref, override in hits:
        if override.revision != entry.revision:
            raise OverrideError(
                "conflicting_revision",
                f"policy {policy_ref} targets {override.rule_id}@{override.revision} "
                f"but composition pinned {entry.revision}",
            )
        settings = _apply_overlay(rule, base, override)
        key = settings.fingerprint()
        fingerprints.setdefault(key, []).append(policy_ref)
        by_fp[key] = settings
    if len(by_fp) > 1:
        raise OverrideError(
            "conflicting_settings",
            f"cross-policy effective settings conflict for {entry.rule_id}",
        )
    fingerprint, refs = next(iter(fingerprints.items()))
    return by_fp[fingerprint], tuple(sorted(set(refs)))


def _merge_exceptions(
    rule: Rule,
    entry: RuleSetEntry,
    policy_settings: _Settings,
    hits: tuple[ScopedException, ...],
) -> tuple[ScopedExceptionApplication, ...]:
    if not hits:
        return ()
    for item in hits:
        if item.revision != entry.revision:
            raise OverrideError(
                "conflicting_revision",
                f"exception {item.exception_ref} targets {item.rule_id}@{item.revision} "
                f"but composition pinned {entry.revision}",
            )
        _validate_exception_values(rule, policy_settings, item)

    applications: list[ScopedExceptionApplication] = []
    for item in hits:
        applications.append(_exception_application((item.exception_ref,), item))

    for left_index, left in enumerate(applications):
        for right in applications[left_index + 1 :]:
            if not _scopes_overlap(left.scope, right.scope):
                continue
            if _specified_conflict(left, right):
                raise OverrideError(
                    "overlapping_exception_conflict",
                    f"overlapping scoped exceptions conflict for {entry.rule_id}",
                )

    return tuple(_dedupe_exceptions(applications))


def _validate_exception_values(
    rule: Rule,
    policy_settings: _Settings,
    item: ScopedException,
) -> None:
    overlay = TypedOverride(
        rule_id=item.rule_id,
        revision=item.revision,
        enabled=item.enabled,
        severity=item.severity,
        parameters=item.parameters,
        presentation=item.presentation,
    )
    _apply_overlay(rule, policy_settings, overlay)


def _exception_application(
    refs: tuple[str, ...],
    item: ScopedException,
) -> ScopedExceptionApplication:
    return ScopedExceptionApplication(
        exception_refs=tuple(sorted(set(refs))),
        scope=item.scope,
        enabled=item.enabled,
        severity=item.severity,
        parameters=dict(item.parameters),
        presentation=item.presentation,
        valid_not_after=item.valid_not_after,
    )


def _dedupe_exceptions(
    applications: list[ScopedExceptionApplication],
) -> list[ScopedExceptionApplication]:
    grouped: dict[str, ScopedExceptionApplication] = {}
    for item in applications:
        key = dumps_canonical(
            {
                "scope": item.scope.model_dump(mode="json"),
                "enabled": item.enabled,
                "severity": None if item.severity is None else item.severity.value,
                "parameters": item.parameters,
                "presentation": None
                if item.presentation is None
                else item.presentation.model_dump(mode="json"),
                "valid_not_after": item.valid_not_after,
            }
        )
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = item
            continue
        grouped[key] = item.model_copy(
            update={
                "exception_refs": tuple(sorted(set(existing.exception_refs + item.exception_refs)))
            }
        )
    return sorted(
        grouped.values(),
        key=lambda item: (item.exception_refs, item.scope.kind, item.scope.identifiers),
    )


def _specified_conflict(
    left: ScopedExceptionApplication,
    right: ScopedExceptionApplication,
) -> bool:
    if left.enabled is not None and right.enabled is not None and left.enabled != right.enabled:
        return True
    if left.severity is not None and right.severity is not None and left.severity != right.severity:
        return True
    shared = set(left.parameters) & set(right.parameters)
    for key in shared:
        if left.parameters[key] != right.parameters[key]:
            return True
    if left.presentation is not None and right.presentation is not None:
        if _presentation_specified_conflict(left.presentation, right.presentation):
            return True
    return False


def _presentation_specified_conflict(
    left: PresentationOverlay,
    right: PresentationOverlay,
) -> bool:
    if (
        left.message_template is not None
        and right.message_template is not None
        and left.message_template != right.message_template
    ):
        return True
    if (
        left.documentation_url is not None
        and right.documentation_url is not None
        and left.documentation_url != right.documentation_url
    ):
        return True
    if left.bindings is not None and right.bindings is not None and left.bindings != right.bindings:
        return True
    if (
        left.remediation_template is not None
        and right.remediation_template is not None
        and left.remediation_template != right.remediation_template
    ):
        return True
    return False


def _scopes_overlap(left: SubjectScope, right: SubjectScope) -> bool:
    if left.kind != right.kind:
        return False
    if left.kind == "path":
        return any(
            _path_overlap(first, second)
            for first in left.identifiers
            for second in right.identifiers
        )
    return bool(set(left.identifiers) & set(right.identifiers))


def _path_overlap(left: str, right: str) -> bool:
    first = left.rstrip("/")
    second = right.rstrip("/")
    if first == second:
        return True
    return first.startswith(f"{second}/") or second.startswith(f"{first}/")


def _overrides_for(
    policies: tuple[PolicyFragment, ...],
    rule_id: str,
) -> tuple[tuple[str, TypedOverride], ...]:
    hits: list[tuple[str, TypedOverride]] = []
    for policy in policies:
        matching = tuple(item for item in policy.overrides if item.rule_id == rule_id)
        if len(matching) > 1:
            fingerprints = {_override_fingerprint(item) for item in matching}
            if len(fingerprints) > 1:
                raise OverrideError(
                    "conflicting_settings",
                    f"policy {policy.policy_ref} repeats conflicting overrides for {rule_id}",
                )
        for item in matching:
            hits.append((policy.policy_ref, item))
    return tuple(hits)


def _override_fingerprint(override: TypedOverride) -> str:
    return dumps_canonical(override.model_dump(mode="json"))


def _reject_unknown_targets(
    overlay: PolicyOverrideBundle,
    composed_by_id: dict[str, RuleSetEntry],
) -> None:
    for policy in overlay.policies:
        for override in policy.overrides:
            if override.rule_id not in composed_by_id:
                raise OverrideError(
                    "missing_reference",
                    f"policy {policy.policy_ref} targets unknown rule {override.rule_id}",
                )
    for exception in overlay.exceptions:
        if exception.rule_id not in composed_by_id:
            raise OverrideError(
                "missing_reference",
                f"exception {exception.exception_ref} targets unknown rule {exception.rule_id}",
            )


def _selector_digest(rule: Rule, composed: ComposedRuleSet) -> str:
    select = rule.select
    if select.selector_ref:
        for selector in composed.selectors:
            if selector.id == select.selector_ref:
                if select.selector_digest and select.selector_digest != selector.digest:
                    raise OverrideError(
                        "logic_change_requires_revision",
                        f"selector rebinding for {rule.metadata.id} requires a new Rule revision",
                    )
                return selector.digest
        raise OverrideError(
            "missing_reference",
            f"rule {rule.metadata.id} references missing selector {select.selector_ref}",
        )
    if select.selector_digest:
        return select.selector_digest
    return digest_canonical({"source": select.source, "nodes": select.nodes})


def _differs_from_composed(rule: Rule, entry: RuleSetEntry, settings: _Settings) -> bool:
    base = _composed_settings(rule, entry)
    return settings.fingerprint() != base.fingerprint()
