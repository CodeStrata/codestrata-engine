"""E04.1 pinned RuleSet composition and deterministic precedence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.rules.composition.bundled import bundled_community_catalog
from codestrata.application.rules.composition.catalog import (
    RuleCatalog,
    catalog_from_directory,
)
from codestrata.application.rules.composition.command import main, prerresolve
from codestrata.application.rules.composition.errors import ResolutionError
from codestrata.application.rules.composition.loader import (
    load_document_bytes,
    resolve_catalog_path,
)
from codestrata.application.rules.composition.merge import merge_defined_fields
from codestrata.application.rules.composition.resolver import resolve_ruleset
from codestrata.domain.contracts.enums import AdoptionLabel
from codestrata.domain.contracts.examples_e01_3 import example_rule
from codestrata.domain.contracts.rules import (
    ParentRef,
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

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e04.1"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "contracts"
    / "codestrata.io"
    / "v1.2"
    / "ComposedRuleSet.json"
)


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
    enabled: bool = True,
    adoption: AdoptionLabel = AdoptionLabel.RECOMMENDED,
    parameters: dict[str, str | int | float | bool] | None = None,
    severity: FindingSeverity | None = FindingSeverity.HIGH,
) -> RuleSetEntry:
    return RuleSetEntry(
        rule_id=rule.metadata.id,
        revision=rule.metadata.version,
        digest=rule.digest,
        default_enabled=enabled,
        adoption=adoption,
        parameters=parameters or {},
        severity_override=severity,
    )


def _ruleset(
    *,
    ruleset_id: str,
    rules: tuple[RuleSetEntry, ...],
    extends: tuple[ParentRef, ...] = (),
    selectors: tuple[SelectorDef, ...] = (),
    version: str = "1.0.0",
) -> RuleSet:
    return bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id=ruleset_id,
                version=version,
                title=ruleset_id,
                owner="codestrata",
            ),
            "extends": extends,
            "selectors": selectors,
            "rules": rules,
        },
    )


def _parent_ref(ruleset: RuleSet) -> ParentRef:
    return ParentRef(
        id=ruleset.metadata.id,
        version=ruleset.metadata.version,
        digest=ruleset.digest,
    )


def test_schema_declares_composed_ruleset() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_name"]["const"] == "codestrata.composed-ruleset.v1"


def test_later_parent_overrides_earlier_configuration() -> None:
    rule = _rule()
    extra = _rule(rule_id="architecture.framework-leakage")
    selector = _selector(selector_id="codestrata.production_modules")
    early = _ruleset(
        ruleset_id="codestrata.parent-early",
        selectors=(selector,),
        rules=(
            _entry(
                rule,
                enabled=True,
                parameters={"limit": 8, "keep": 1},
                severity=FindingSeverity.HIGH,
            ),
        ),
    )
    late = _ruleset(
        ruleset_id="codestrata.parent-late",
        selectors=(selector,),
        rules=(
            _entry(
                rule,
                enabled=False,
                adoption=AdoptionLabel.OPTIONAL,
                parameters={"limit": 2},
                severity=None,
            ),
        ),
    )
    child = _ruleset(
        ruleset_id="codestrata.child",
        extends=(_parent_ref(early), _parent_ref(late)),
        selectors=(selector,),
        rules=(_entry(extra),),
    )
    composed = resolve_ruleset(child, RuleCatalog((early, late, child), (rule, extra)))
    inherited = next(item for item in composed.rules if item.rule_id == rule.metadata.id)
    assert inherited.default_enabled is False
    assert inherited.adoption is AdoptionLabel.OPTIONAL
    assert inherited.parameters == {"limit": 2, "keep": 1}
    assert inherited.severity_override is FindingSeverity.HIGH


def test_parent_order_changes_composition_digest() -> None:
    rule = _rule()
    extra = _rule(rule_id="architecture.framework-leakage")
    selector = _selector(selector_id="codestrata.production_modules")
    early = _ruleset(
        ruleset_id="codestrata.parent-a",
        selectors=(selector,),
        rules=(_entry(rule, enabled=True, parameters={"limit": 1}),),
    )
    late = _ruleset(
        ruleset_id="codestrata.parent-b",
        selectors=(selector,),
        rules=(_entry(rule, enabled=False, parameters={"limit": 9}),),
    )
    left = _ruleset(
        ruleset_id="codestrata.ordered",
        extends=(_parent_ref(early), _parent_ref(late)),
        selectors=(selector,),
        rules=(_entry(extra),),
    )
    right = _ruleset(
        ruleset_id="codestrata.ordered",
        extends=(_parent_ref(late), _parent_ref(early)),
        selectors=(selector,),
        rules=(_entry(extra),),
    )
    catalog_left = RuleCatalog((early, late, left), (rule, extra))
    catalog_right = RuleCatalog((early, late, right), (rule, extra))
    first = resolve_ruleset(left, catalog_left)
    second = resolve_ruleset(right, catalog_right)
    first_inherited = next(item for item in first.rules if item.rule_id == rule.metadata.id)
    second_inherited = next(item for item in second.rules if item.rule_id == rule.metadata.id)
    assert first_inherited.parameters["limit"] == 9
    assert second_inherited.parameters["limit"] == 1
    assert first.composition_digest != second.composition_digest


def test_explicit_child_revision_resolves_parent_conflict() -> None:
    first = _rule(version="1.0.0")
    second = _rule(version="1.1.0")
    selector = _selector(selector_id="codestrata.production_modules")
    parent_a = _ruleset(
        ruleset_id="codestrata.rev-a",
        selectors=(selector,),
        rules=(_entry(first, parameters={"from": "a"}),),
    )
    parent_b = _ruleset(
        ruleset_id="codestrata.rev-b",
        selectors=(selector,),
        rules=(_entry(second, parameters={"from": "b"}),),
    )
    child = _ruleset(
        ruleset_id="codestrata.rev-child",
        extends=(_parent_ref(parent_a), _parent_ref(parent_b)),
        selectors=(selector,),
        rules=(_entry(second, parameters={"pinned": True}),),
    )
    composed = resolve_ruleset(
        child, RuleCatalog((parent_a, parent_b, child), (first, second))
    )
    assert composed.rules[0].revision == "1.1.0"
    assert composed.rules[0].digest == second.digest
    assert composed.rules[0].parameters["from"] == "b"
    assert composed.rules[0].parameters["pinned"] is True

    unpinned = _ruleset(
        ruleset_id="codestrata.rev-unpinned",
        extends=(_parent_ref(parent_a), _parent_ref(parent_b)),
        selectors=(selector,),
        rules=(_entry(_rule(rule_id="architecture.framework-leakage")),),
    )
    leak = _rule(rule_id="architecture.framework-leakage")
    with pytest.raises(ResolutionError, match="revision_conflict"):
        resolve_ruleset(
            unpinned,
            RuleCatalog((parent_a, parent_b, unpinned), (first, second, leak)),
        )


def test_maps_merge_lists_replace_null_does_not_reset() -> None:
    merged = merge_defined_fields(
        {"map": {"a": 1, "b": 2}, "list": ["old"], "scalar": "keep"},
        {"map": {"b": 3, "c": 4, "a": None}, "list": ["new"], "scalar": None},
    )
    assert merged == {"map": {"a": 1, "b": 3, "c": 4}, "list": ["new"], "scalar": "keep"}


def test_conflicting_selector_asts_cannot_shadow() -> None:
    rule = _rule()
    one = _selector(selector_id="codestrata.production_modules", generated=False)
    two = _selector(selector_id="codestrata.production_modules", generated=True)
    parent = _ruleset(
        ruleset_id="codestrata.sel-parent",
        selectors=(one,),
        rules=(_entry(rule),),
    )
    child = _ruleset(
        ruleset_id="codestrata.sel-child",
        extends=(_parent_ref(parent),),
        selectors=(two,),
        rules=(_entry(rule),),
    )
    with pytest.raises(ResolutionError, match="selector_conflict"):
        resolve_ruleset(child, RuleCatalog((parent, child), (rule,)))


def test_identical_selector_asts_deduplicate() -> None:
    rule = _rule()
    selector = _selector(selector_id="codestrata.production_modules")
    parent = _ruleset(
        ruleset_id="codestrata.sel-same-parent",
        selectors=(selector,),
        rules=(_entry(rule),),
    )
    child = _ruleset(
        ruleset_id="codestrata.sel-same-child",
        extends=(_parent_ref(parent),),
        selectors=(selector,),
        rules=(_entry(rule),),
    )
    composed = resolve_ruleset(child, RuleCatalog((parent, child), (rule,)))
    assert len(composed.selectors) == 1
    assert composed.selectors[0].id == selector.id


def test_missing_cyclic_and_floating_references() -> None:
    rule = _rule()
    selector = _selector(selector_id="codestrata.production_modules")
    missing_parent = _ruleset(
        ruleset_id="codestrata.missing-root",
        extends=(
            ParentRef(
                id="codestrata.absent",
                version="1.0.0",
                digest=digest_canonical({"missing": True}),
            ),
        ),
        selectors=(selector,),
        rules=(_entry(rule),),
    )
    with pytest.raises(ResolutionError, match="missing_reference"):
        resolve_ruleset(missing_parent, RuleCatalog((missing_parent,), (rule,)))

    looping = _ruleset(
        ruleset_id="codestrata.cycle-root",
        extends=(
            ParentRef(
                id="codestrata.cycle-loop",
                version="1.0.0",
                digest=digest_canonical({"cycle": True}),
            ),
        ),
        selectors=(selector,),
        rules=(_entry(rule),),
    )

    class _LoopCatalog(RuleCatalog):
        def get_ruleset(self, ref: ParentRef) -> RuleSet:
            return looping

    with pytest.raises(ResolutionError, match="cyclic_reference"):
        resolve_ruleset(looping, _LoopCatalog((looping,), (rule,)))

    with pytest.raises(ResolutionError, match="floating_reference"):
        catalog_from_directory(FIXTURE_DIR / "floating")


def test_excessive_depth_and_rule_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = _rule()
    selector = _selector(selector_id="codestrata.production_modules")
    chain: list[RuleSet] = []
    current = _ruleset(
        ruleset_id="codestrata.depth-0",
        selectors=(selector,),
        rules=(_entry(rule),),
    )
    chain.append(current)
    for index in range(1, 10):
        current = _ruleset(
            ruleset_id=f"codestrata.depth-{index}",
            extends=(_parent_ref(current),),
            selectors=(selector,),
            rules=(_entry(rule),),
        )
        chain.append(current)
    with pytest.raises(ResolutionError, match="excessive_depth"):
        resolve_ruleset(chain[-1], RuleCatalog(chain, (rule,)))

    extra = _rule(rule_id="architecture.framework-leakage")
    wide = _ruleset(
        ruleset_id="codestrata.wide",
        selectors=(selector,),
        rules=(_entry(rule), _entry(extra)),
    )
    monkeypatch.setattr(
        "codestrata.application.rules.composition.resolver.composition_budgets",
        lambda: (8, 1, 1_048_576, 32),
    )
    with pytest.raises(ResolutionError, match="excessive_size"):
        resolve_ruleset(wide, RuleCatalog((wide,), (rule, extra)))


def test_oversized_and_alias_documents_rejected() -> None:
    with pytest.raises(ResolutionError, match="excessive_size"):
        load_document_bytes(b"{" + (b"x" * 1_048_577), label="huge")
    with pytest.raises(ResolutionError, match="yaml_alias"):
        load_document_bytes(b"a: &id 1\nb: *id\n", label="alias.yaml")


def test_path_escape_rejected(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    root.mkdir()
    outside = tmp_path / "secret.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ResolutionError, match="path_escape"):
        resolve_catalog_path(root, Path("../secret.json"))


def test_identical_input_bytes_resolve_deterministically() -> None:
    catalog = bundled_community_catalog()
    root = next(
        item for item in catalog.rulesets() if item.metadata.id.endswith("engineering-standard")
    )
    payloads = [
        dumps_canonical(resolve_ruleset(root, catalog).model_dump(mode="json")) for _ in range(3)
    ]
    assert payloads[0] == payloads[1] == payloads[2]
    expected = json.loads(
        (FIXTURE_DIR / "expected-bundled-standard.json").read_text(encoding="utf-8")
    )
    actual = json.loads(payloads[0])
    assert actual == expected
    assert actual["rules"][0]["parameters"]["max_cycle_length"] == 4
    assert actual["rules"][0]["severity_override"] == "high"
    assert actual["rules"][0]["default_enabled"] is True


def test_file_catalog_and_preresolution_command(tmp_path: Path) -> None:
    catalog = bundled_community_catalog()
    source = tmp_path / "catalog"
    source.mkdir()
    for ruleset in catalog.rulesets():
        (source / f"{ruleset.metadata.id}.json").write_text(
            dumps_canonical(ruleset.model_dump(mode="json")),
            encoding="utf-8",
        )
    (source / "rule.json").write_text(
        dumps_canonical(example_rule().model_dump(mode="json")),
        encoding="utf-8",
    )
    loaded = catalog_from_directory(source)
    root = next(item for item in loaded.rulesets() if "standard" in item.metadata.id)
    composed = resolve_ruleset(root, loaded)
    assert composed.rules[0].parameters["max_cycle_length"] == 4

    output = tmp_path / "out"
    assert prerresolve(catalog_dir=None, bundled=True, output_dir=output) == 2
    produced = list(output.glob("*.composed.json"))
    assert len(produced) == 2
    assert main(["--bundled", "--output", str(tmp_path / "cli")]) == 0
