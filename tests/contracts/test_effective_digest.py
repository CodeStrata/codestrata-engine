"""E04.3 Effective RuleSet digest sealing and execution parity."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.rules.composition.catalog import RuleCatalog, catalog_from_mapping
from codestrata.application.rules.composition.resolver import resolve_ruleset
from codestrata.application.rules.effective import (
    CandidateRunRequest,
    EffectiveSealError,
    ExecutionContext,
    LocalUnsignedConfig,
    admit_effective,
    compare_reviewed_and_production,
    execute_candidate,
    execute_preview,
    finding_fingerprint,
    seal_bundled_community,
    seal_effective_ruleset,
    seal_neutral_customer_package,
)
from codestrata.application.rules.effective.command import main
from codestrata.application.rules.effective.packages import BUNDLED_INPUT, CUSTOMER_INPUT
from codestrata.application.rules.effective.seal import signed_identity_bytes
from codestrata.application.rules.overrides.apply import apply_overrides
from codestrata.application.rules.overrides.models import (
    PolicyFragment,
    PolicyOverrideBundle,
    ScopedException,
    SubjectScope,
    TypedOverride,
)
from codestrata.application.rules.overrides.presentation import PresentationOverlay
from codestrata.domain.contracts.enums import AdoptionLabel, ExecutionPurpose
from codestrata.domain.contracts.examples_e01_3 import example_rule
from codestrata.domain.contracts.rules import (
    ParentRef,
    Rule,
    RuleSet,
    RuleSetEntry,
    RuleSetMetadata,
    SelectorDef,
    bind_digest,
    parse_effective_ruleset,
    unsigned_rule_payload,
)
from codestrata.domain.contracts.serialization import digest_canonical, dumps_canonical
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.rules.operators.models import (
    OperatorContext,
    OperatorEdge,
    OperatorGraph,
    OperatorLimits,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e04.3"
SCHEMA_DIR = (
    Path(__file__).resolve().parents[2] / "schemas" / "contracts" / "codestrata.io" / "v1.2"
)
NOW = datetime(2026, 9, 22, tzinfo=UTC)
EXPIRY = "2026-12-31T00:00:00Z"


def _rule(*, rule_id: str | None = None, version: str = "1.0.0") -> Rule:
    payload = unsigned_rule_payload(example_rule())
    metadata = dict(payload["metadata"])
    if rule_id is not None:
        metadata["id"] = rule_id
    metadata["version"] = version
    payload["metadata"] = metadata
    return bind_digest(Rule, payload)


def _selector(*, selector_id: str, generated: bool = False) -> SelectorDef:
    nodes = {"all": [{"type": "module"}, {"generated": generated}]}
    return SelectorDef(
        id=selector_id,
        source="repository_graph",
        nodes=nodes,
        digest=digest_canonical({"source": "repository_graph", "nodes": nodes}),
    )


def _entry(
    rule: Rule,
    *,
    parameters: dict[str, str | int | float | bool] | None = None,
    severity: FindingSeverity | None = FindingSeverity.HIGH,
) -> RuleSetEntry:
    return RuleSetEntry(
        rule_id=rule.metadata.id,
        revision=rule.metadata.version,
        digest=rule.digest,
        default_enabled=True,
        adoption=AdoptionLabel.RECOMMENDED,
        parameters=parameters or {},
        severity_override=severity,
    )


def _ruleset(
    rule: Rule,
    *,
    ruleset_id: str,
    extends: tuple[ParentRef, ...] = (),
    parameters: dict[str, str | int | float | bool] | None = None,
) -> RuleSet:
    selector = _selector(selector_id="codestrata.production_modules")
    return bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id=ruleset_id,
                version="1.0.0",
                title=ruleset_id,
                owner="codestrata",
            ),
            "extends": extends,
            "selectors": (selector,),
            "rules": (_entry(rule, parameters=parameters),),
        },
    )


def _parent_ref(ruleset: RuleSet) -> ParentRef:
    return ParentRef(
        id=ruleset.metadata.id,
        version=ruleset.metadata.version,
        digest=ruleset.digest,
    )


def _compose(rule: Rule | None = None):
    rule = rule or _rule()
    ruleset = _ruleset(rule, ruleset_id="codestrata.engineering-standard")
    catalog = catalog_from_mapping([ruleset], [rule])
    return resolve_ruleset(ruleset, catalog), catalog, rule


def _load_expected(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _acyclic() -> OperatorContext:
    return OperatorContext(
        declared_graph=OperatorGraph(
            nodes=("a", "b"),
            edges=(OperatorEdge(source="a", target="b", edge_type="imports"),),
            complete=True,
        )
    )


def _cyclic() -> OperatorContext:
    return OperatorContext(
        declared_graph=OperatorGraph(
            nodes=("a", "b"),
            edges=(
                OperatorEdge(source="a", target="b", edge_type="imports"),
                OperatorEdge(source="b", target="a", edge_type="imports"),
            ),
            complete=True,
        )
    )


def _unknown() -> OperatorContext:
    return OperatorContext(declared_graph=OperatorGraph(nodes=("a", "b"), edges=(), complete=False))


def _context(
    purpose: ExecutionPurpose = ExecutionPurpose.CANDIDATE_VALIDATION,
) -> ExecutionContext:
    return ExecutionContext(now=NOW, requested_purpose=purpose)


def test_bundled_community_identity_matches_independent_fixture() -> None:
    first, _catalog = seal_bundled_community()
    second, _ = seal_bundled_community()
    third, _ = seal_bundled_community()
    actual = json.loads(dumps_canonical(first.model_dump(mode="json")))
    expected = _load_expected("expected-bundled-production.json")
    assert actual == expected
    assert first.effective_ruleset_digest == second.effective_ruleset_digest
    assert second.effective_ruleset_digest == third.effective_ruleset_digest
    assert first.input_digest == BUNDLED_INPUT
    assert first.execution_purpose is ExecutionPurpose.PRODUCTION
    parse_effective_ruleset(actual)


def test_neutral_customer_package_fixture_is_not_community_authoring() -> None:
    composed, catalog, rule = _compose()
    overlay = PolicyOverrideBundle(
        policies=(
            PolicyFragment(
                policy_ref="policy:opaque:customer.pack@1.0.0",
                version="1.0.0",
                overrides=(
                    TypedOverride(
                        rule_id=rule.metadata.id,
                        revision=rule.metadata.version,
                        severity=FindingSeverity.MEDIUM,
                    ),
                ),
            ),
        )
    )
    first = seal_neutral_customer_package(
        catalog,
        overlay,
        ruleset_id="codestrata.engineering-standard",
    )
    second = seal_effective_ruleset(
        composed=composed,
        overridden=apply_overrides(composed, catalog, overlay),
        catalog=catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=CUSTOMER_INPUT,
        package_digest=CUSTOMER_INPUT,
        validity_not_after="2027-09-15T00:00:00Z",
    )
    actual = json.loads(dumps_canonical(first.model_dump(mode="json")))
    expected = _load_expected("expected-customer-production.json")
    assert actual == expected
    assert first.effective_ruleset_digest == second.effective_ruleset_digest
    assert first.rules[0].effective_severity is FindingSeverity.MEDIUM
    assert first.input_digest == CUSTOMER_INPUT


def test_reviewed_candidate_matches_production_signed_bytes() -> None:
    production, catalog = seal_bundled_community()
    candidate, _ = seal_bundled_community(purpose=ExecutionPurpose.CANDIDATE_VALIDATION)
    compare_reviewed_and_production(candidate, production)
    assert candidate.signed_base_digest == production.signed_base_digest
    assert signed_identity_bytes(candidate) == signed_identity_bytes(production)
    assert candidate.effective_ruleset_digest != production.effective_ruleset_digest
    assert candidate.execution_purpose is ExecutionPurpose.CANDIDATE_VALIDATION
    del catalog
    with pytest.raises(EffectiveSealError, match="preview_cannot_authorize_production"):
        compare_reviewed_and_production(production, production)


def test_expiry_cannot_exceed_exception_validity() -> None:
    composed, catalog, rule = _compose()
    bundle = PolicyOverrideBundle(
        exceptions=(
            ScopedException(
                exception_ref="exception:opaque:cycle-window@1.0.0",
                rule_id=rule.metadata.id,
                revision=rule.metadata.version,
                scope=SubjectScope(kind="path", identifiers=("src",)),
                valid_not_after="2026-06-01T00:00:00Z",
            ),
        )
    )
    overridden = apply_overrides(composed, catalog, bundle)
    with pytest.raises(EffectiveSealError, match="expiry_exceeds_exception_validity"):
        seal_effective_ruleset(
            composed=composed,
            overridden=overridden,
            catalog=catalog,
            purpose=ExecutionPurpose.PRODUCTION,
            input_digest=digest_canonical({"input": "expiry"}),
            validity_not_after="2027-09-15T00:00:00Z",
        )
    sealed = seal_effective_ruleset(
        composed=composed,
        overridden=overridden,
        catalog=catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=digest_canonical({"input": "expiry"}),
        validity_not_after="2026-05-01T00:00:00Z",
    )
    late = admit_effective(
        sealed,
        ExecutionContext(
            now=datetime(2026, 5, 15, tzinfo=UTC),
            requested_purpose=ExecutionPurpose.PRODUCTION,
        ),
        exception_valid_not_after=("2026-06-01T00:00:00Z",),
    )
    assert late.admitted is False
    assert late.reason_code == "expired"
    assert "now" not in json.dumps(sealed.model_dump(mode="json"))


def test_time_is_execution_context_not_digest() -> None:
    production, _ = seal_bundled_community()
    early = admit_effective(
        production,
        ExecutionContext(
            now=datetime(2026, 1, 1, tzinfo=UTC),
            requested_purpose=ExecutionPurpose.PRODUCTION,
        ),
    )
    later = admit_effective(
        production,
        ExecutionContext(
            now=datetime(2026, 6, 1, tzinfo=UTC),
            requested_purpose=ExecutionPurpose.PRODUCTION,
        ),
    )
    assert early.admitted is True
    assert later.admitted is True
    assert early.observed_at != later.observed_at
    assert early.observed_at not in dumps_canonical(production.model_dump(mode="json"))


def test_parent_order_and_effective_settings_change_digest() -> None:
    rule = _rule()
    parent_a = _ruleset(rule, ruleset_id="codestrata.parent-a", parameters={"max_cycle_length": 4})
    parent_b = _ruleset(rule, ruleset_id="codestrata.parent-b", parameters={"max_cycle_length": 12})
    first_child = _ruleset(
        rule,
        ruleset_id="codestrata.child",
        extends=(_parent_ref(parent_a), _parent_ref(parent_b)),
    )
    second_child = _ruleset(
        rule,
        ruleset_id="codestrata.child",
        extends=(_parent_ref(parent_b), _parent_ref(parent_a)),
    )
    first_catalog = RuleCatalog((parent_a, parent_b, first_child), (rule,))
    second_catalog = RuleCatalog((parent_a, parent_b, second_child), (rule,))
    first_composed = resolve_ruleset(first_child, first_catalog)
    second_composed = resolve_ruleset(second_child, second_catalog)
    first = seal_effective_ruleset(
        composed=first_composed,
        overridden=apply_overrides(first_composed, first_catalog),
        catalog=first_catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=digest_canonical({"input": "order"}),
        validity_not_after="2027-09-15T00:00:00Z",
    )
    second = seal_effective_ruleset(
        composed=second_composed,
        overridden=apply_overrides(second_composed, second_catalog),
        catalog=second_catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=digest_canonical({"input": "order"}),
        validity_not_after="2027-09-15T00:00:00Z",
    )
    assert first.effective_ruleset_digest != second.effective_ruleset_digest
    assert first.signed_base_digest != second.signed_base_digest

    composed, catalog, rule_obj = _compose()
    overlay = PolicyOverrideBundle(
        policies=(
            PolicyFragment(
                policy_ref="policy:opaque:severity@1.0.0",
                version="1.0.0",
                overrides=(
                    TypedOverride(
                        rule_id=rule_obj.metadata.id,
                        revision=rule_obj.metadata.version,
                        severity=FindingSeverity.LOW,
                    ),
                ),
            ),
        )
    )
    changed = seal_effective_ruleset(
        composed=composed,
        overridden=apply_overrides(composed, catalog, overlay),
        catalog=catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=digest_canonical({"input": "settings"}),
        validity_not_after="2027-09-15T00:00:00Z",
    )
    baseline = seal_effective_ruleset(
        composed=composed,
        overridden=apply_overrides(composed, catalog),
        catalog=catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=digest_canonical({"input": "settings"}),
        validity_not_after="2027-09-15T00:00:00Z",
    )
    assert changed.effective_ruleset_digest != baseline.effective_ruleset_digest


def test_rendered_message_never_changes_finding_fingerprint() -> None:
    production, catalog = seal_bundled_community(purpose=ExecutionPurpose.PREVIEW)
    resolved = production.rules[0]
    left = finding_fingerprint(resolved, subject="module:a", rendered_message="cycle at a")
    right = finding_fingerprint(
        resolved, subject="module:a", rendered_message="totally different text"
    )
    assert left == right
    request = CandidateRunRequest(
        effective=production,
        expiry=EXPIRY,
        permitted_paths=("./fixture",),
        fixtures=(
            {
                "name": "message-a",
                "expected_status": "fail",
                "operator_context": _cyclic(),
                "rendered_message": "first rendering",
            },
            {
                "name": "message-b",
                "expected_status": "fail",
                "operator_context": _cyclic(),
                "rendered_message": "second rendering",
            },
        ),
    )
    result = execute_candidate(request, catalog, context=_context())
    assert result.outcomes[0].finding_fingerprint == result.outcomes[1].finding_fingerprint


def test_local_parameters_hash_separately_from_signed_base() -> None:
    composed, catalog, rule = _compose()
    overridden = apply_overrides(composed, catalog)
    base = seal_effective_ruleset(
        composed=composed,
        overridden=overridden,
        catalog=catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=digest_canonical({"input": "local"}),
        validity_not_after="2027-09-15T00:00:00Z",
    )
    local = seal_effective_ruleset(
        composed=composed,
        overridden=overridden,
        catalog=catalog,
        purpose=ExecutionPurpose.PRODUCTION,
        input_digest=digest_canonical({"input": "local"}),
        local_config=LocalUnsignedConfig(
            parameters_by_rule={rule.metadata.id: {"max_cycle_length": 16}}
        ),
        validity_not_after="2027-09-15T00:00:00Z",
    )
    assert base.signed_base_digest == local.signed_base_digest
    assert base.local_unsigned_config_digest != local.local_unsigned_config_digest
    assert base.effective_ruleset_digest != local.effective_ruleset_digest
    assert local.rules[0].parameters["max_cycle_length"] == 16


def test_preview_never_silently_becomes_production() -> None:
    preview, catalog = seal_bundled_community(purpose=ExecutionPurpose.PREVIEW)
    admission = admit_effective(
        preview,
        ExecutionContext(now=NOW, requested_purpose=ExecutionPurpose.PRODUCTION),
    )
    assert admission.admitted is False
    assert admission.reason_code == "preview_cannot_authorize_production"
    with pytest.raises(
        (EffectiveSealError, ValidationError),
        match="preview_cannot_authorize_production",
    ):
        CandidateRunRequest(
            effective=preview,
            expiry=EXPIRY,
            requested_purpose=ExecutionPurpose.PRODUCTION,
            fixtures=({"name": "x", "expected_status": "pass", "operator_context": _acyclic()},),
        )
    with pytest.raises(EffectiveSealError, match="preview_cannot_authorize_production"):
        execute_candidate(
            CandidateRunRequest(
                effective=preview,
                expiry=EXPIRY,
                fixtures=(
                    {
                        "name": "promote",
                        "expected_status": "pass",
                        "operator_context": _acyclic(),
                        "promote_to_production": True,
                    },
                ),
            ),
            catalog,
            context=_context(),
        )


def test_candidate_fixtures_and_preview_use_production_compiler() -> None:
    candidate, catalog = seal_bundled_community(purpose=ExecutionPurpose.CANDIDATE_VALIDATION)
    expected = _load_expected("expected-outcomes.json")
    request = CandidateRunRequest(
        effective=candidate,
        expiry=EXPIRY,
        permitted_paths=("./fixture",),
        fixtures=(
            {
                "name": "compliant",
                "expected_status": "pass",
                "operator_context": _acyclic(),
                "path": "fixture/ok.py",
            },
            {
                "name": "violating",
                "expected_status": "fail",
                "operator_context": _cyclic(),
                "path": "fixture/bad.py",
            },
            {
                "name": "unknown-edge",
                "expected_status": "unknown",
                "operator_context": _unknown(),
                "path": "fixture/partial.py",
            },
            {
                "name": "budget",
                "expected_status": "error",
                "operator_context": OperatorContext(
                    declared_graph=OperatorGraph(
                        nodes=("a", "b", "c"),
                        edges=(OperatorEdge(source="a", target="b", edge_type="imports"),),
                    ),
                    limits=OperatorLimits(graph_max_visited_nodes=1),
                ),
                "path": "fixture/budget.py",
            },
        ),
    )
    result = execute_candidate(request, catalog, context=_context())
    actual = [
        {
            "name": item.name,
            "expected_status": item.expected_status.value,
            "actual_status": item.actual_status.value,
            "coverage": item.coverage,
        }
        for item in result.outcomes
    ]
    assert actual == expected["outcomes"]
    assert result.production_promotion_allowed is False
    assert result.candidate_digest == candidate.effective_ruleset_digest
    assert result.input_digest == candidate.input_digest
    assert result.validation.stale_evidence is False
    preview = execute_preview(request, catalog, context=_context())
    assert preview.purpose is ExecutionPurpose.PREVIEW
    assert [item.actual_status for item in preview.outcomes] == [
        item.actual_status for item in result.outcomes
    ]


def test_stale_preview_parameter_selector_scope_and_promotion_fail() -> None:
    candidate, catalog = seal_bundled_community(purpose=ExecutionPurpose.CANDIDATE_VALIDATION)
    with pytest.raises((EffectiveSealError, ValidationError), match="stale_preview_evidence"):
        CandidateRunRequest(
            effective=candidate,
            expiry=EXPIRY,
            stale_evidence=True,
            fixtures=({"name": "x", "expected_status": "pass", "operator_context": _acyclic()},),
        )
    with pytest.raises(EffectiveSealError, match="stale_preview_evidence"):
        execute_candidate(
            CandidateRunRequest(
                effective=candidate,
                expiry="2026-01-01T00:00:00Z",
                fixtures=(
                    {
                        "name": "stale",
                        "expected_status": "pass",
                        "operator_context": _acyclic(),
                    },
                ),
            ),
            catalog,
            context=_context(),
        )
    with pytest.raises(EffectiveSealError, match="stale_preview_evidence"):
        execute_candidate(
            CandidateRunRequest(
                effective=candidate,
                expiry=EXPIRY,
                evidence_candidate_digest=digest_canonical({"other": True}),
                fixtures=(
                    {
                        "name": "rebinding",
                        "expected_status": "pass",
                        "operator_context": _acyclic(),
                    },
                ),
            ),
            catalog,
            context=_context(),
        )
    with pytest.raises(EffectiveSealError, match="parameter_change"):
        execute_candidate(
            CandidateRunRequest(
                effective=candidate,
                expiry=EXPIRY,
                fixtures=(
                    {
                        "name": "params",
                        "expected_status": "pass",
                        "operator_context": _acyclic(),
                        "parameters_override": {"max_cycle_length": 99},
                    },
                ),
            ),
            catalog,
            context=_context(),
        )
    with pytest.raises(EffectiveSealError, match="selector_rebinding"):
        execute_candidate(
            CandidateRunRequest(
                effective=candidate,
                expiry=EXPIRY,
                fixtures=(
                    {
                        "name": "selector",
                        "expected_status": "pass",
                        "operator_context": _acyclic(),
                        "selector_override": {
                            "source": "repository_graph",
                            "nodes": {"all": [{"type": "file"}]},
                        },
                    },
                ),
            ),
            catalog,
            context=_context(),
        )
    with pytest.raises(EffectiveSealError, match="scope_violation"):
        execute_candidate(
            CandidateRunRequest(
                effective=candidate,
                expiry=EXPIRY,
                permitted_paths=("./fixture",),
                fixtures=(
                    {
                        "name": "escape",
                        "expected_status": "pass",
                        "operator_context": _acyclic(),
                        "path": "../secret/repo.py",
                    },
                ),
            ),
            catalog,
            context=_context(),
        )


def test_message_overlay_does_not_change_finding_fingerprint() -> None:
    composed, catalog, rule = _compose()
    overlay = PolicyOverrideBundle(
        policies=(
            PolicyFragment(
                policy_ref="policy:opaque:message@1.0.0",
                version="1.0.0",
                overrides=(
                    TypedOverride(
                        rule_id=rule.metadata.id,
                        revision=rule.metadata.version,
                        presentation=PresentationOverlay(
                            message_template="{{dependency_path}} is in a cycle"
                        ),
                    ),
                ),
            ),
        )
    )
    original = seal_effective_ruleset(
        composed=composed,
        overridden=apply_overrides(composed, catalog),
        catalog=catalog,
        purpose=ExecutionPurpose.PREVIEW,
        input_digest=digest_canonical({"input": "message"}),
    )
    rewritten = seal_effective_ruleset(
        composed=composed,
        overridden=apply_overrides(composed, catalog, overlay),
        catalog=catalog,
        purpose=ExecutionPurpose.PREVIEW,
        input_digest=digest_canonical({"input": "message"}),
    )
    assert original.effective_ruleset_digest != rewritten.effective_ruleset_digest
    assert finding_fingerprint(original.rules[0], subject="module:a") == finding_fingerprint(
        rewritten.rules[0],
        subject="module:a",
        rendered_message="irrelevant",
    )


def test_bundled_command_is_not_customer_authoring(tmp_path: Path) -> None:
    assert main(["--bundled", "--output", str(tmp_path)]) == 0
    written = next(tmp_path.glob("*.effective.json"))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["execution_purpose"] == "production"
    with pytest.raises(SystemExit):
        main(["--output", str(tmp_path)])


def test_schema_and_negative_partial_unsupported_budget() -> None:
    schema = json.loads((SCHEMA_DIR / "CandidateRunResult.json").read_text(encoding="utf-8"))
    assert schema["properties"]["production_promotion_allowed"]["const"] is False
    composed, catalog, _rule_obj = _compose()
    other_rule = _rule(rule_id="architecture.framework-leakage")
    other_composed, other_catalog, _other = _compose(other_rule)
    with pytest.raises(EffectiveSealError, match="identity_mismatch"):
        seal_effective_ruleset(
            composed=composed,
            overridden=apply_overrides(other_composed, other_catalog),
            catalog=catalog,
            purpose=ExecutionPurpose.PREVIEW,
            input_digest=digest_canonical({"input": "mismatch"}),
        )
    with pytest.raises((EffectiveSealError, ValidationError), match="excessive_size"):
        LocalUnsignedConfig(
            parameters_by_rule={f"rule.{index}": {"max_cycle_length": 4} for index in range(1001)}
        )
    preview, _ = seal_bundled_community(purpose=ExecutionPurpose.PREVIEW)
    with pytest.raises((EffectiveSealError, ValidationError), match="excessive_size"):
        CandidateRunRequest(
            effective=preview,
            expiry=EXPIRY,
            fixtures=tuple(
                {"name": f"f{index}", "expected_status": "pass", "operator_context": _acyclic()}
                for index in range(65)
            ),
        )
