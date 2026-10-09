"""E04.2 typed overrides and resolved scoped exceptions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.rules.composition.catalog import catalog_from_mapping
from codestrata.application.rules.composition.resolver import resolve_ruleset
from codestrata.application.rules.overrides import (
    OverrideError,
    apply_overrides,
    load_override_bundle,
    parse_override_bundle,
)
from codestrata.application.rules.overrides.models import (
    PolicyFragment,
    PolicyOverrideBundle,
    ScopedException,
    SubjectScope,
    TypedOverride,
)
from codestrata.application.rules.overrides.presentation import PresentationOverlay
from codestrata.domain.contracts.enums import AdoptionLabel
from codestrata.domain.contracts.examples_e01_3 import example_rule
from codestrata.domain.contracts.rules import (
    MessageBinding,
    ParameterField,
    Rule,
    RuleSet,
    RuleSetEntry,
    RuleSetMetadata,
    SelectorDef,
    bind_digest,
    unsigned_rule_payload,
)
from codestrata.domain.contracts.serialization import digest_canonical, dumps_canonical
from codestrata.domain.findings.enums import FindingSeverity

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e04.2"
SCHEMA_DIR = (
    Path(__file__).resolve().parents[2] / "schemas" / "contracts" / "codestrata.io" / "v1.2"
)


def _rule(*, rule_id: str | None = None, version: str = "1.0.0") -> Rule:
    payload = unsigned_rule_payload(example_rule())
    metadata = dict(payload["metadata"])
    if rule_id is not None:
        metadata["id"] = rule_id
    metadata["version"] = version
    payload["metadata"] = metadata
    return bind_digest(Rule, payload)


def _entry(
    rule: Rule,
    *,
    enabled: bool = True,
    parameters: dict[str, str | int | float | bool] | None = None,
    severity: FindingSeverity | None = FindingSeverity.HIGH,
) -> RuleSetEntry:
    return RuleSetEntry(
        rule_id=rule.metadata.id,
        revision=rule.metadata.version,
        digest=rule.digest,
        default_enabled=enabled,
        adoption=AdoptionLabel.RECOMMENDED,
        parameters=parameters or {},
        severity_override=severity,
    )


def _ruleset(rule: Rule, *, ruleset_id: str = "codestrata.engineering-standard") -> RuleSet:
    selector = SelectorDef(
        id="codestrata.production_modules",
        source="repository_graph",
        nodes={"all": [{"type": "module"}, {"generated": False}]},
        digest=digest_canonical(
            {
                "source": "repository_graph",
                "nodes": {"all": [{"type": "module"}, {"generated": False}]},
            }
        ),
    )
    return bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id=ruleset_id,
                version="1.0.0",
                title="Engineering standard",
                owner="codestrata",
            ),
            "selectors": (selector,),
            "rules": (_entry(rule),),
        },
    )


def _compose(rule: Rule | None = None):
    rule = rule or _rule()
    ruleset = _ruleset(rule)
    catalog = catalog_from_mapping([ruleset], [rule])
    return resolve_ruleset(ruleset, catalog), catalog, rule


def _policy(
    rule: Rule,
    *,
    ref: str = "policy:opaque:acme.engineering-policy@3.0.0",
    **fields: object,
) -> PolicyFragment:
    override = TypedOverride(
        rule_id=rule.metadata.id,
        revision=rule.metadata.version,
        enabled=fields.get("enabled"),  # type: ignore[arg-type]
        severity=fields.get("severity"),  # type: ignore[arg-type]
        parameters=fields.get("parameters") or {},  # type: ignore[arg-type]
        presentation=fields.get("presentation"),  # type: ignore[arg-type]
    )
    return PolicyFragment(policy_ref=ref, version="3.0.0", overrides=(override,))


def _bundle(
    *policies: PolicyFragment,
    exceptions: tuple[ScopedException, ...] = (),
) -> PolicyOverrideBundle:
    return PolicyOverrideBundle(policies=policies, exceptions=exceptions)


def _load_expected(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_identity_apply_matches_independent_fixture() -> None:
    composed, catalog, _rule_obj = _compose()
    first = apply_overrides(composed, catalog)
    second = apply_overrides(composed, catalog, PolicyOverrideBundle())
    third = apply_overrides(composed, catalog)
    actual = json.loads(dumps_canonical(first.model_dump(mode="json")))
    expected = _load_expected("expected-identity.json")
    assert actual == expected
    assert second.overlay_digest == first.overlay_digest == third.overlay_digest
    resolved = first.rules[0].resolved
    assert resolved.enabled is True
    assert resolved.effective_severity is FindingSeverity.HIGH
    assert resolved.override_source is None
    assert resolved.policy_refs == ()


def test_reject_off_as_severity() -> None:
    with pytest.raises(OverrideError, match="off_is_not_severity"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "policies": [
                    {
                        "policy_ref": "policy:opaque:acme.engineering-policy@3.0.0",
                        "version": "3.0.0",
                        "overrides": [
                            {
                                "rule_id": "architecture.dependency-cycle",
                                "revision": "1.0.0",
                                "severity": "off",
                            }
                        ],
                    }
                ],
            }
        )


def test_reject_out_of_range_and_unknown_parameters() -> None:
    composed, catalog, rule = _compose()
    over = _bundle(_policy(rule, parameters={"max_cycle_length": 99}))
    with pytest.raises(OverrideError, match="out_of_range_parameter"):
        apply_overrides(composed, catalog, over)
    unknown = _bundle(_policy(rule, parameters={"secret_query": 1}))
    with pytest.raises(OverrideError, match="unknown_parameter"):
        apply_overrides(composed, catalog, unknown)


def test_reject_executable_messages() -> None:
    composed, catalog, rule = _compose()
    raw = {
        "schema_name": "codestrata.policy-override-bundle.v1",
        "schema_version": "1.0.0",
        "policies": [
            {
                "policy_ref": "policy:opaque:acme.engineering-policy@3.0.0",
                "version": "3.0.0",
                "overrides": [
                    {
                        "rule_id": rule.metadata.id,
                        "revision": rule.metadata.version,
                        "presentation": {"message_template": "eval(user_input)"},
                    }
                ],
            }
        ],
    }
    with pytest.raises(OverrideError, match="executable_message"):
        apply_overrides(composed, catalog, parse_override_bundle(raw))


def test_selector_schema_operator_changes_require_new_revision() -> None:
    raw = {
        "schema_name": "codestrata.policy-override-bundle.v1",
        "schema_version": "1.0.0",
        "policies": [
            {
                "policy_ref": "policy:opaque:acme.engineering-policy@3.0.0",
                "version": "3.0.0",
                "overrides": [
                    {
                        "rule_id": "architecture.dependency-cycle",
                        "revision": "1.0.0",
                        "condition": {"operator": "cycle"},
                    }
                ],
            }
        ],
    }
    with pytest.raises(OverrideError, match="logic_change_requires_revision"):
        parse_override_bundle(raw)


def test_deduplicate_equal_cross_policy_rules_retaining_attributions() -> None:
    composed, catalog, rule = _compose()
    bundle = _bundle(
        _policy(
            rule,
            ref="policy:opaque:acme.engineering-policy@3.0.0",
            severity=FindingSeverity.CRITICAL,
        ),
        _policy(
            rule,
            ref="policy:opaque:acme.security-policy@1.0.0",
            severity=FindingSeverity.CRITICAL,
        ),
    )
    applied = apply_overrides(composed, catalog, bundle)
    resolved = applied.rules[0].resolved
    assert resolved.effective_severity is FindingSeverity.CRITICAL
    assert resolved.policy_refs == (
        "policy:opaque:acme.engineering-policy@3.0.0",
        "policy:opaque:acme.security-policy@1.0.0",
    )
    assert resolved.override_source == "policy:opaque:acme.engineering-policy@3.0.0"
    expected = _load_expected("expected-deduped-policies.json")
    assert json.loads(dumps_canonical(applied.model_dump(mode="json"))) == expected


def test_reject_conflicting_revisions_and_settings() -> None:
    composed, catalog, rule = _compose()
    revision_conflict = _bundle(
        PolicyFragment(
            policy_ref="policy:opaque:acme.engineering-policy@3.0.0",
            version="3.0.0",
            overrides=(
                TypedOverride(
                    rule_id=rule.metadata.id,
                    revision="2.0.0",
                    severity=FindingSeverity.CRITICAL,
                ),
            ),
        )
    )
    with pytest.raises(OverrideError, match="conflicting_revision"):
        apply_overrides(composed, catalog, revision_conflict)
    settings_conflict = _bundle(
        _policy(
            rule,
            ref="policy:opaque:acme.engineering-policy@3.0.0",
            severity=FindingSeverity.CRITICAL,
        ),
        _policy(
            rule,
            ref="policy:opaque:acme.security-policy@1.0.0",
            severity=FindingSeverity.LOW,
        ),
    )
    with pytest.raises(OverrideError, match="conflicting_settings"):
        apply_overrides(composed, catalog, settings_conflict)


def test_overlapping_exception_values_rejected_disjoint_combined() -> None:
    composed, catalog, rule = _compose()
    conflict = _bundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:exc-a",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="path", identifiers=("src",)),
                enabled=False,
            ),
            ScopedException(
                exception_ref="exception:opaque:exc-b",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="path", identifiers=("src/app.py",)),
                enabled=True,
            ),
        )
    )
    with pytest.raises(OverrideError, match="overlapping_exception_conflict"):
        apply_overrides(composed, catalog, conflict)

    combined = _bundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:exc-a",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="path", identifiers=("src",)),
                enabled=False,
            ),
            ScopedException(
                exception_ref="exception:opaque:exc-b",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="path", identifiers=("src/app.py",)),
                severity=FindingSeverity.LOW,
            ),
        )
    )
    applied = apply_overrides(composed, catalog, combined)
    assert len(applied.rules[0].scoped_exceptions) == 2
    refs = applied.rules[0].resolved.exception_refs
    assert refs == ("exception:opaque:exc-a", "exception:opaque:exc-b")


def test_equal_exceptions_dedupe_opaque_refs() -> None:
    composed, catalog, rule = _compose()
    bundle = _bundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:exc-a",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="component", identifiers=("module:app",)),
                enabled=False,
            ),
            ScopedException(
                exception_ref="exception:opaque:exc-b",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="component", identifiers=("module:app",)),
                enabled=False,
            ),
        )
    )
    applied = apply_overrides(composed, catalog, bundle)
    scopes = applied.rules[0].scoped_exceptions
    assert len(scopes) == 1
    assert scopes[0].exception_refs == ("exception:opaque:exc-a", "exception:opaque:exc-b")


def test_only_opaque_refs_and_local_scopes_reach_engine() -> None:
    with pytest.raises(OverrideError, match="forbidden_authority"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "policies": [
                    {
                        "policy_ref": "approver:jane@example.com",
                        "version": "1.0.0",
                        "overrides": [],
                    }
                ],
            }
        )
    with pytest.raises(OverrideError, match="forbidden_authority"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "workspace_id": "ws-1",
                "policies": [],
            }
        )
    with pytest.raises(OverrideError, match="invalid_scope"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "exceptions": [
                    {
                        "exception_ref": "exception:opaque:exc-org",
                        "rule_id": "architecture.dependency-cycle",
                        "revision": "1.0.0",
                        "scope": {"kind": "organization", "identifiers": ["acme"]},
                        "enabled": False,
                    }
                ],
            }
        )
    with pytest.raises(OverrideError, match="invalid_scope"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "exceptions": [
                    {
                        "exception_ref": "exception:opaque:exc-escape",
                        "rule_id": "architecture.dependency-cycle",
                        "revision": "1.0.0",
                        "scope": {"kind": "path", "identifiers": ["../etc/passwd"]},
                        "enabled": False,
                    }
                ],
            }
        )


def test_partial_enabled_override_and_presentation_inherit() -> None:
    composed, catalog, rule = _compose()
    bundle = _bundle(_policy(rule, enabled=False))
    applied = apply_overrides(composed, catalog, bundle)
    resolved = applied.rules[0].resolved
    assert resolved.enabled is False
    assert resolved.default_enabled is True
    assert resolved.effective_severity is FindingSeverity.HIGH
    assert applied.rules[0].presentation.message_template == rule.finding.message_template


def test_unsupported_presentation_field_rejected() -> None:
    raw = {
        "schema_name": "codestrata.policy-override-bundle.v1",
        "schema_version": "1.0.0",
        "policies": [
            {
                "policy_ref": "policy:opaque:acme.engineering-policy@3.0.0",
                "version": "3.0.0",
                "overrides": [
                    {
                        "rule_id": "architecture.dependency-cycle",
                        "revision": "1.0.0",
                        "presentation": {"css": "expression(alert(1))"},
                    }
                ],
            }
        ],
    }
    with pytest.raises(OverrideError, match="unknown_presentation_field"):
        parse_override_bundle(raw)


def test_budget_failure_oversized_bundle() -> None:
    huge = b"{" + (b"x" * (1024 * 1024 + 8)) + b"}"
    with pytest.raises(OverrideError, match="excessive_size"):
        load_override_bundle(huge, label="overrides.yaml")


def test_load_yaml_bundle_and_apply() -> None:
    composed, catalog, rule = _compose()
    raw = (FIXTURE_DIR / "policy-severity.yaml").read_bytes()
    bundle = load_override_bundle(raw)
    applied = apply_overrides(composed, catalog, bundle)
    assert applied.rules[0].resolved.effective_severity is FindingSeverity.CRITICAL
    assert applied.rules[0].resolved.policy_refs == ("policy:opaque:acme.engineering-policy@3.0.0",)


def test_expected_outcome_codes() -> None:
    outcomes = _load_expected("expected-outcomes.json")
    composed, catalog, rule = _compose()
    cases = {
        "off_severity": lambda: parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "policies": [
                    {
                        "policy_ref": "policy:opaque:acme.engineering-policy@3.0.0",
                        "version": "3.0.0",
                        "overrides": [
                            {
                                "rule_id": rule.metadata.id,
                                "revision": "1.0.0",
                                "severity": "off",
                            }
                        ],
                    }
                ],
            }
        ),
        "out_of_range_parameter": lambda: apply_overrides(
            composed, catalog, _bundle(_policy(rule, parameters={"max_cycle_length": 0}))
        ),
        "executable_message": lambda: parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "policies": [
                    {
                        "policy_ref": "policy:opaque:acme.engineering-policy@3.0.0",
                        "version": "3.0.0",
                        "overrides": [
                            {
                                "rule_id": rule.metadata.id,
                                "revision": rule.metadata.version,
                                "presentation": {"message_template": "cycle {{path}} | upper"},
                            }
                        ],
                    }
                ],
            }
        ),
        "conflicting_settings": lambda: apply_overrides(
            composed,
            catalog,
            _bundle(
                _policy(
                    rule,
                    ref="policy:opaque:acme.engineering-policy@3.0.0",
                    enabled=True,
                ),
                _policy(
                    rule,
                    ref="policy:opaque:acme.security-policy@1.0.0",
                    enabled=False,
                ),
            ),
        ),
    }
    for name, action in cases.items():
        with pytest.raises(OverrideError) as caught:
            action()
        assert caught.value.code == outcomes[name]


def test_published_schemas_forbid_unknown_fields() -> None:
    for name in ("PolicyOverrideBundle", "OverriddenRuleSet"):
        schema = json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False


def _compose_with(rule: Rule):
    return _compose(rule)


def test_parameter_types_and_empty_schema() -> None:
    boolean_rule = bind_digest(
        Rule,
        {
            **unsigned_rule_payload(example_rule()),
            "parameter_schema": (
                ParameterField(name="strict", value_type="boolean", default=True),
            ),
        },
    )
    composed, catalog, rule = _compose_with(boolean_rule)
    applied = apply_overrides(
        composed, catalog, _bundle(_policy(rule, parameters={"strict": False}))
    )
    assert applied.rules[0].resolved.parameters["strict"] is False
    with pytest.raises(OverrideError, match="out_of_range_parameter"):
        apply_overrides(composed, catalog, _bundle(_policy(rule, parameters={"strict": "no"})))

    number_rule = bind_digest(
        Rule,
        {
            **unsigned_rule_payload(example_rule()),
            "parameter_schema": (
                ParameterField(
                    name="ratio", value_type="number", minimum=0.0, maximum=1.0, default=0.5
                ),
            ),
        },
    )
    composed, catalog, rule = _compose_with(number_rule)
    with pytest.raises(OverrideError, match="out_of_range_parameter"):
        apply_overrides(composed, catalog, _bundle(_policy(rule, parameters={"ratio": "fast"})))

    string_rule = bind_digest(
        Rule,
        {
            **unsigned_rule_payload(example_rule()),
            "parameter_schema": (ParameterField(name="label", value_type="string"),),
        },
    )
    composed, catalog, rule = _compose_with(string_rule)
    with pytest.raises(OverrideError, match="out_of_range_parameter"):
        apply_overrides(composed, catalog, _bundle(_policy(rule, parameters={"label": 1})))
    with pytest.raises(OverrideError, match="out_of_range_parameter"):
        apply_overrides(
            composed,
            catalog,
            _bundle(_policy(rule, parameters={"label": "x" * 1025})),
        )

    bare = bind_digest(
        Rule,
        {**unsigned_rule_payload(example_rule()), "parameter_schema": ()},
    )
    composed, catalog, rule = _compose_with(bare)
    with pytest.raises(OverrideError, match="unknown_parameter"):
        apply_overrides(composed, catalog, _bundle(_policy(rule, parameters={"x": 1})))

    weird = bind_digest(
        Rule,
        {
            **unsigned_rule_payload(example_rule()),
            "parameter_schema": (ParameterField(name="pattern", value_type="regex"),),
        },
    )
    composed, catalog, rule = _compose_with(weird)
    with pytest.raises(OverrideError, match="unknown_parameter"):
        apply_overrides(composed, catalog, _bundle(_policy(rule, parameters={"pattern": "a"})))


def test_missing_targets_duplicate_policy_overrides_and_exception_revision() -> None:
    composed, catalog, rule = _compose()
    other = _rule(rule_id="architecture.no-cycles")
    missing = _bundle(_policy(other, severity=FindingSeverity.LOW))
    with pytest.raises(OverrideError, match="missing_reference"):
        apply_overrides(composed, catalog, missing)
    missing_exc = _bundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:missing-rule",
                rule_id=other.metadata.id,
                revision=other.metadata.version,
                scope=SubjectScope(kind="subject", identifiers=("mod:a",)),
                enabled=False,
            ),
        )
    )
    with pytest.raises(OverrideError, match="missing_reference"):
        apply_overrides(composed, catalog, missing_exc)
    duplicate = PolicyFragment(
        policy_ref="policy:opaque:acme.engineering-policy@3.0.0",
        version="3.0.0",
        overrides=(
            TypedOverride(
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                enabled=True,
            ),
            TypedOverride(
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                enabled=False,
            ),
        ),
    )
    with pytest.raises(OverrideError, match="conflicting_settings"):
        apply_overrides(composed, catalog, _bundle(duplicate))
    wrong_rev = _bundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:stale",
                rule_id=rule.metadata.id,
                revision="9.0.0",
                scope=SubjectScope(kind="component", identifiers=("mod:a",)),
                enabled=False,
            ),
        )
    )
    with pytest.raises(OverrideError, match="conflicting_revision"):
        apply_overrides(composed, catalog, wrong_rev)


def test_overlapping_exception_parameter_and_presentation_conflicts() -> None:
    composed, catalog, rule = _compose()
    param_conflict = _bundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:exc-a",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="path", identifiers=("src/",)),
                parameters={"max_cycle_length": 4},
            ),
            ScopedException(
                exception_ref="exception:opaque:exc-b",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="path", identifiers=("src/app.py",)),
                parameters={"max_cycle_length": 8},
            ),
        )
    )
    with pytest.raises(OverrideError, match="overlapping_exception_conflict"):
        apply_overrides(composed, catalog, param_conflict)
    presentation_conflict = _bundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:exc-a",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="subject", identifiers=("mod:a",)),
                presentation=PresentationOverlay(message_template="one path"),
            ),
            ScopedException(
                exception_ref="exception:opaque:exc-b",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="subject", identifiers=("mod:a",)),
                presentation=PresentationOverlay(message_template="other path"),
            ),
        )
    )
    with pytest.raises(OverrideError, match="overlapping_exception_conflict"):
        apply_overrides(composed, catalog, presentation_conflict)


def test_presentation_bindings_url_and_parse_failures() -> None:
    composed, catalog, rule = _compose()
    overlay = PresentationOverlay(
        documentation_url="https://docs.codestrata.ai/rules/architecture/dependency-cycle",
        bindings=(
            MessageBinding(name="dependency_path", type="string", evidence="dependency_path"),
        ),
        remediation_template="break the cycle",
    )
    applied = apply_overrides(composed, catalog, _bundle(_policy(rule, presentation=overlay)))
    assert applied.rules[0].presentation.remediation_template == "break the cycle"
    with pytest.raises(OverrideError, match="invalid_presentation"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "policies": [
                    {
                        "policy_ref": "policy:opaque:acme.engineering-policy@3.0.0",
                        "version": "3.0.0",
                        "overrides": [
                            {
                                "rule_id": rule.metadata.id,
                                "revision": rule.metadata.version,
                                "presentation": {"documentation_url": "http://example.com"},
                            }
                        ],
                    }
                ],
            }
        )
    with pytest.raises(OverrideError, match="invalid_document"):
        load_override_bundle(b"[]", label="overrides.json")
    with pytest.raises(OverrideError, match="unknown_field"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "surprise": True,
            }
        )
    with pytest.raises(OverrideError, match="forbidden_authority"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "policies": [
                    {
                        "policy_ref": "policy:opaque:",
                        "version": "1.0.0",
                    }
                ],
            }
        )
    with pytest.raises(OverrideError, match="invalid_scope"):
        parse_override_bundle(
            {
                "schema_name": "codestrata.policy-override-bundle.v1",
                "schema_version": "1.0.0",
                "exceptions": [
                    {
                        "exception_ref": "exception:opaque:drive",
                        "rule_id": rule.metadata.id,
                        "revision": rule.metadata.version,
                        "scope": {"kind": "path", "identifiers": ["C:/Windows"]},
                        "enabled": False,
                    }
                ],
            }
        )


def test_selector_ref_rule_and_integer_type_mismatch() -> None:
    selector = SelectorDef(
        id="codestrata.production_modules",
        source="repository_graph",
        nodes={"all": [{"type": "module"}]},
        digest=digest_canonical(
            {"source": "repository_graph", "nodes": {"all": [{"type": "module"}]}}
        ),
    )
    payload = unsigned_rule_payload(example_rule())
    payload["select"] = {
        "selector_ref": selector.id,
        "selector_digest": selector.digest,
    }
    rule = bind_digest(Rule, payload)
    ruleset = bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id="codestrata.engineering-standard",
                version="1.0.0",
                title="Engineering standard",
                owner="codestrata",
            ),
            "selectors": (selector,),
            "rules": (_entry(rule),),
        },
    )
    catalog = catalog_from_mapping([ruleset], [rule])
    composed = resolve_ruleset(ruleset, catalog)
    applied = apply_overrides(composed, catalog)
    assert applied.rules[0].resolved.selector_digest == selector.digest
    with pytest.raises(OverrideError, match="out_of_range_parameter"):
        apply_overrides(
            composed, catalog, _bundle(_policy(rule, parameters={"max_cycle_length": True}))
        )
