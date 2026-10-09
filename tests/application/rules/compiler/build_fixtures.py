"""Generate E03.1 YAML fixtures. Test-only helper, not a product secret."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from codestrata.application.rules.compiler import compile_ruleset_yaml, compile_yaml
from codestrata.domain.contracts.examples_e01_3 import example_rule, example_ruleset
from codestrata.domain.contracts.rules import unsigned_rule_payload
from codestrata.domain.contracts.serialization import omit_key
from codestrata.domain.rules.compiler_models import selector_ast_digest_for

ROOT = Path(__file__).resolve().parent / "fixtures" / "e03.1"


def _dump(name: str, payload: object) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / name).write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")


def main() -> None:
    rule = unsigned_rule_payload(example_rule())
    _dump("rule-valid.yaml", rule)

    duplicate = yaml.safe_dump(rule, sort_keys=True) + "kind: Rule\n"
    (ROOT / "duplicate-keys.yaml").write_text(duplicate, encoding="utf-8")
    (ROOT / "unknown-tag.yaml").write_text("kind: !!python/object:object {}\n", encoding="utf-8")
    (ROOT / "alias.yaml").write_text(
        "kind: Rule\nanchor: &x cycle\ncondition:\n  operator: *x\n",
        encoding="utf-8",
    )
    (ROOT / "merge-key.yaml").write_text(
        "kind: Rule\nselect:\n  <<:\n    source: repository_graph\n",
        encoding="utf-8",
    )

    executable = dict(rule)
    executable["finding"] = dict(rule["finding"])
    executable["finding"]["message_template"] = "eval(payload) participates in a cycle"
    _dump("executable-string.yaml", executable)

    unknown_field = dict(rule)
    unknown_field["python_eval"] = "nope"
    _dump("unknown-field.yaml", unknown_field)

    (ROOT / "invalid-type.yaml").write_text("kind: Rule\nmetadata: 2020-01-01\n", encoding="utf-8")

    nested = "x: 1\n"
    for _ in range(34):
        nested = "child:\n" + "\n".join("  " + line for line in nested.splitlines()) + "\n"
    (ROOT / "deep-nesting.yaml").write_text("kind: Rule\n" + nested, encoding="utf-8")

    for name, operator in (
        ("operator-eval.yaml", "eval"),
        ("operator-import.yaml", "import"),
        ("operator-shell.yaml", "shell"),
        ("operator-network.yaml", "network"),
        ("operator-file.yaml", "file"),
        ("unsupported-operator.yaml", "security.credential_literal"),
    ):
        payload = dict(rule)
        payload["condition"] = dict(rule["condition"])
        payload["condition"]["operator"] = operator
        _dump(name, payload)

    fact = dict(rule)
    fact["applies_to"] = dict(rule["applies_to"])
    fact["applies_to"]["facts"] = ["os.environ"]
    _dump("unsupported-fact.yaml", fact)

    present = dict(rule)
    present["finding"] = dict(rule["finding"])
    present["finding"]["select"] = {
        "source": "hidden_graph",
        "nodes": {"all": [{"type": "secret"}]},
    }
    _dump("selector-in-presentation.yaml", present)

    predicate = dict(rule)
    predicate["select"] = dict(rule["select"])
    predicate["select"]["nodes"] = {"all": [{"type": "module", "eval": "1+1"}]}
    _dump("unknown-selector-predicate.yaml", predicate)

    partial = dict(rule)
    del partial["condition"]
    _dump("partial-missing-condition.yaml", partial)

    (ROOT / "corrupt.yaml").write_text("kind: Rule\nmetadata: [\n", encoding="utf-8")

    ruleset = omit_key(example_ruleset().model_dump(mode="json"), "digest")
    selector = dict(ruleset["selectors"][0])
    selector["digest"] = selector_ast_digest_for(
        source=selector["source"],
        nodes=selector["nodes"],
    )
    ruleset["selectors"] = [selector]
    _dump("ruleset-valid.yaml", ruleset)

    mismatched = dict(ruleset)
    bad = dict(selector)
    bad["digest"] = "0" * 64
    mismatched["selectors"] = [bad]
    _dump("ruleset-selector-mismatch.yaml", mismatched)

    rule_plan = compile_yaml((ROOT / "rule-valid.yaml").read_bytes())
    ruleset_plan = compile_ruleset_yaml((ROOT / "ruleset-valid.yaml").read_bytes())
    expected = {
        "rule-valid": {
            "document_digest": rule_plan.document_digest,
            "selector_digest": rule_plan.selector_digest,
            "presentation_digest": rule_plan.presentation_digest,
            "plan_digest": rule_plan.plan_digest,
        },
        "ruleset-valid": {
            "document_digest": ruleset_plan.document_digest,
            "selector_digest": ruleset_plan.selector_digest,
            "presentation_digest": ruleset_plan.presentation_digest,
            "plan_digest": ruleset_plan.plan_digest,
        },
    }
    (ROOT / "expected-outcomes.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
