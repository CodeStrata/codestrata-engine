"""E03.1 compiler tests: real YAML fixtures, not a mocked signature boolean."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from codestrata.application.rules.compiler import (
    CapabilityError,
    YamlCompileError,
    compile_rule_yaml,
    compile_ruleset_yaml,
    compile_yaml,
)
from codestrata.domain.contracts.examples_e01_3 import example_rule, example_ruleset
from codestrata.domain.contracts.rules import unsigned_rule_payload
from codestrata.domain.contracts.serialization import omit_key
from codestrata.domain.rules.compiler_models import COMPILER_VERSION

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e03.1"
EXPECTED = json.loads((FIXTURE_DIR / "expected-outcomes.json").read_text(encoding="utf-8"))


def _read(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def _rule_yaml(**overrides: object) -> bytes:
    payload = unsigned_rule_payload(example_rule())
    for key, value in overrides.items():
        if key == "metadata_title":
            metadata = dict(payload["metadata"])
            metadata["title"] = value
            payload["metadata"] = metadata
            continue
        if key == "select_nodes":
            select = dict(payload["select"])
            select["nodes"] = value
            payload["select"] = select
            continue
        if key == "condition_operator":
            condition = dict(payload["condition"])
            condition["operator"] = value
            payload["condition"] = condition
            continue
        if key == "applies_facts":
            applies = dict(payload["applies_to"])
            applies["facts"] = value
            payload["applies_to"] = applies
            continue
        payload[key] = value
    return yaml.safe_dump(payload, sort_keys=True).encode("utf-8")


def test_valid_rule_compiles_to_pinned_plan() -> None:
    plan = compile_yaml(_read("rule-valid.yaml"))
    assert plan.kind == "Rule"
    assert plan.rule is not None
    assert plan.selector_ast is not None
    assert plan.selector_digest == plan.selector_ast.digest
    assert plan.compiler_version == COMPILER_VERSION
    assert plan.capabilities.operators == ("cycle",)
    assert "module.declaration" in plan.capabilities.facts
    expected = EXPECTED["rule-valid"]
    assert plan.document_digest == expected["document_digest"]
    assert plan.selector_digest == expected["selector_digest"]
    assert plan.presentation_digest == expected["presentation_digest"]
    assert plan.plan_digest == expected["plan_digest"]


def test_deterministic_repeat_on_pinned_valid_fixture() -> None:
    raw = _read("rule-valid.yaml")
    digests = [compile_rule_yaml(raw).plan_digest for _ in range(3)]
    assert digests[0] == digests[1] == digests[2]


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("duplicate-keys.yaml"))
    assert caught.value.reason_code == "yaml_duplicate_key"


def test_unknown_tag_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("unknown-tag.yaml"))
    assert caught.value.reason_code == "yaml_unknown_tag"


def test_alias_expansion_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("alias.yaml"))
    assert caught.value.reason_code == "yaml_alias"


def test_merge_key_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("merge-key.yaml"))
    assert caught.value.reason_code == "yaml_merge"


def test_executable_string_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("executable-string.yaml"))
    assert caught.value.reason_code == "executable_string"


def test_unknown_field_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("unknown-field.yaml"))
    assert caught.value.reason_code == "unknown_field"


def test_invalid_type_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("invalid-type.yaml"))
    assert caught.value.reason_code == "invalid_type"


def test_excessive_bytes_rejected() -> None:
    blob = ("kind: Rule\npad: " + ("a" * (1024 * 1024 + 8)) + "\n").encode("utf-8")
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(blob, label="oversized.yaml")
    assert caught.value.reason_code == "excessive_bytes"


def test_excessive_nesting_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("deep-nesting.yaml"))
    assert caught.value.reason_code == "excessive_nesting"


@pytest.mark.parametrize(
    ("name", "operator"),
    [
        ("operator-eval.yaml", "eval"),
        ("operator-import.yaml", "import"),
        ("operator-shell.yaml", "shell"),
        ("operator-network.yaml", "network"),
        ("operator-file.yaml", "file"),
    ],
)
def test_disallowed_operators_rejected(name: str, operator: str) -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read(name))
    assert caught.value.reason_code == "disallowed_operator"
    assert caught.value.details["operator"] == operator


def test_unsupported_operator_is_capability_error() -> None:
    with pytest.raises(CapabilityError) as caught:
        compile_yaml(_read("unsupported-operator.yaml"))
    payload = caught.value.to_payload()
    assert payload["kind"] == "capability"
    assert payload["reason"] == "unsupported_operator"
    assert payload["token"] == "security.credential_literal"
    assert "cycle" in payload["supported"]
    assert payload["status"] == "ERROR"


def test_unsupported_fact_is_capability_error() -> None:
    with pytest.raises(CapabilityError) as caught:
        compile_yaml(_read("unsupported-fact.yaml"))
    payload = caught.value.to_payload()
    assert payload["kind"] == "capability"
    assert payload["reason"] == "unsupported_fact"
    assert payload["token"] == "os.environ"
    assert "module.declaration" in payload["supported"]


def test_selector_change_is_not_presentation() -> None:
    baseline = compile_rule_yaml(_rule_yaml())
    title_only = compile_rule_yaml(_rule_yaml(metadata_title="A different title"))
    selector_changed = compile_rule_yaml(
        _rule_yaml(select_nodes={"all": [{"type": "file"}]})
    )
    assert title_only.selector_digest == baseline.selector_digest
    assert title_only.presentation_digest != baseline.presentation_digest
    assert title_only.document_digest != baseline.document_digest
    assert selector_changed.selector_digest != baseline.selector_digest
    assert selector_changed.presentation_digest == baseline.presentation_digest


def test_presentation_cannot_bind_as_selector() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("selector-in-presentation.yaml"))
    assert caught.value.reason_code in {"unknown_field", "schema"}


def test_unknown_selector_predicate_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("unknown-selector-predicate.yaml"))
    assert caught.value.reason_code == "unknown_field"


def test_partial_missing_condition() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("partial-missing-condition.yaml"))
    assert caught.value.reason_code == "schema"


def test_corrupt_yaml_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("corrupt.yaml"))
    assert caught.value.reason_code == "invalid_yaml"


def test_ruleset_pins_selector_ast_digest() -> None:
    plan = compile_ruleset_yaml(_read("ruleset-valid.yaml"))
    assert plan.kind == "RuleSet"
    assert plan.ruleset is not None
    assert len(plan.selectors) == 1
    assert plan.selectors[0].digest == plan.ruleset.selectors[0].digest
    expected = EXPECTED["ruleset-valid"]
    assert plan.selector_digest == expected["selector_digest"]
    assert plan.document_digest == expected["document_digest"]


def test_ruleset_selector_digest_mismatch_rejected() -> None:
    with pytest.raises(YamlCompileError) as caught:
        compile_yaml(_read("ruleset-selector-mismatch.yaml"))
    assert caught.value.reason_code == "selector_digest_mismatch"


def test_example_rule_round_trip_through_compiler() -> None:
    raw = yaml.safe_dump(unsigned_rule_payload(example_rule()), sort_keys=True).encode("utf-8")
    plan = compile_rule_yaml(raw)
    assert plan.rule is not None
    assert plan.rule.metadata.id == example_rule().metadata.id
    assert omit_key(plan.rule.model_dump(mode="json"), "digest") == unsigned_rule_payload(
        example_rule()
    )


def test_example_ruleset_needs_ast_pin() -> None:
    payload = omit_key(example_ruleset().model_dump(mode="json"), "digest")
    raw = yaml.safe_dump(payload, sort_keys=True).encode("utf-8")
    with pytest.raises(YamlCompileError) as caught:
        compile_ruleset_yaml(raw)
    assert caught.value.reason_code == "selector_digest_mismatch"
