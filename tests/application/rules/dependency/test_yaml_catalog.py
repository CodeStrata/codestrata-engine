"""Bundled dependency YAML catalog tests (E06.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.rules.dependency.yaml_catalog import (
    ALLOWED_OPERATORS,
    CATALOG_DIR,
    YamlCatalogError,
    dependency_catalog_digests,
    load_dependency_rules,
    parse_dependency_rule_document,
)
from codestrata.application.rules.security.yaml_catalog import MAX_RULE_BYTES, load_yaml_document
from codestrata.domain.dependency.ids import HYGIENE_RULE_IDS
from codestrata.domain.rules.enums import RuleSeverity


def test_bundled_catalog_covers_hygiene_rules() -> None:
    rules = load_dependency_rules()
    assert tuple(rules) == HYGIENE_RULE_IDS
    expected_severity = {
        "dependency.unresolved-version": RuleSeverity.MEDIUM,
        "dependency.mutable-version": RuleSeverity.MEDIUM,
        "dependency.unbounded-requirement": RuleSeverity.MEDIUM,
        "dependency.conflicting-exact-versions": RuleSeverity.HIGH,
        "dependency.duplicate-declaration": RuleSeverity.LOW,
    }
    for rule_id, item in rules.items():
        assert (CATALOG_DIR / f"{rule_id}.yaml").is_file()
        assert item["operator"] in ALLOWED_OPERATORS
        assert item["default_severity"] is expected_severity[rule_id]


def test_dependency_catalog_digests_are_stable() -> None:
    first = dependency_catalog_digests()
    second = dependency_catalog_digests()
    assert first == second
    assert set(first) >= {"pack", *HYGIENE_RULE_IDS}


def test_loader_rejects_unknown_dependency_rule_fields(tmp_path: Path) -> None:
    document = {
        "api_version": "codestrata.io/rules/v1",
        "kind": "Rule",
        "metadata": {
            "id": "dependency.mutable-version",
            "version": "1.0.0",
            "title": "x",
            "category": "dependency",
            "owner": "codestrata",
            "measurement": "M12",
            "tags": ["dependency"],
        },
        "applies_to": {"languages": ["python"]},
        "select": {"source": "dependency"},
        "condition": {"operator": "dependency.mutable_version"},
        "emit": {
            "finding": {
                "default_severity": "medium",
                "message": {"template": "ok {{path}}"},
            }
        },
        "evidence": {"include": ["declaration_path"]},
        "parameters": {},
        "shell": "rm -rf /",
    }
    with pytest.raises(YamlCatalogError, match="unknown fields"):
        parse_dependency_rule_document(document, path=tmp_path / "bad.yaml")


def test_loader_rejects_wrong_operator(tmp_path: Path) -> None:
    document = {
        "api_version": "codestrata.io/rules/v1",
        "kind": "Rule",
        "metadata": {
            "id": "dependency.mutable-version",
            "version": "1.0.0",
            "title": "x",
            "category": "dependency",
            "owner": "codestrata",
            "measurement": "M12",
            "tags": ["dependency"],
        },
        "applies_to": {"languages": ["python"]},
        "select": {"source": "dependency"},
        "condition": {"operator": "dependency.eval_version"},
        "emit": {
            "finding": {
                "default_severity": "medium",
                "message": {"template": "ok"},
            }
        },
        "evidence": {"include": ["declaration_path"]},
        "parameters": {},
    }
    with pytest.raises(YamlCatalogError, match="not allowlisted"):
        parse_dependency_rule_document(document, path=tmp_path / "bad.yaml")
    with pytest.raises(YamlCatalogError, match="executable string"):
        load_yaml_document(
            "title: exec('secret')\n",
            max_bytes=MAX_RULE_BYTES,
            label="exec.yaml",
        )
