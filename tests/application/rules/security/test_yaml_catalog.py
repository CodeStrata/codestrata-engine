"""Bundled YAML catalog loader tests (E06.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.rules.security.yaml_catalog import (
    ALLOWED_OPERATORS,
    CATALOG_DIR,
    MAX_RULE_BYTES,
    YamlCatalogError,
    catalog_digests,
    load_security_rules,
    load_yaml_document,
)
from codestrata.domain.security.ids import HYGIENE_RULE_IDS


def test_bundled_catalog_covers_eight_hygiene_rules() -> None:
    rules = load_security_rules()
    assert tuple(rules) == HYGIENE_RULE_IDS
    for rule_id, item in rules.items():
        assert (CATALOG_DIR / f"{rule_id}.yaml").is_file()
        assert item["operator"] in ALLOWED_OPERATORS
        assert item["file_digest"]
        assert item["default_severity"].value in {"low", "medium", "high", "critical"}


def test_catalog_digests_are_stable() -> None:
    first = catalog_digests()
    second = catalog_digests()
    assert first == second
    assert set(first) >= {"pack", *HYGIENE_RULE_IDS}


def test_loader_rejects_aliases_duplicates_tags_and_executables() -> None:
    with pytest.raises(YamlCatalogError, match="aliases"):
        load_yaml_document(
            "a: &id value\nb: *id\n",
            max_bytes=MAX_RULE_BYTES,
            label="alias.yaml",
        )
    with pytest.raises(YamlCatalogError, match="duplicate"):
        load_yaml_document(
            "api_version: x\napi_version: y\n",
            max_bytes=MAX_RULE_BYTES,
            label="dup.yaml",
        )
    with pytest.raises(YamlCatalogError, match="executable string"):
        load_yaml_document(
            "title: eval('secret')\n",
            max_bytes=MAX_RULE_BYTES,
            label="exec.yaml",
        )
    with pytest.raises(YamlCatalogError, match="exceeds"):
        load_yaml_document(
            "k: " + ("v" * (MAX_RULE_BYTES + 10)),
            max_bytes=64,
            label="big.yaml",
        )


def test_loader_rejects_unknown_rule_fields(tmp_path: Path) -> None:
    from codestrata.application.rules.security.yaml_catalog import parse_rule_document

    document = {
        "api_version": "codestrata.io/rules/v1",
        "kind": "Rule",
        "metadata": {
            "id": "security.private-key-material",
            "version": "1.0.0",
            "title": "x",
            "category": "security",
            "owner": "codestrata",
            "measurement": "M10",
            "tags": ["security"],
        },
        "applies_to": {"languages": ["python"]},
        "select": {"source": "repository_sensitive"},
        "condition": {"operator": "security.has_private_key_material"},
        "emit": {
            "finding": {
                "default_severity": "high",
                "message": {"template": "ok {{path}}"},
            }
        },
        "evidence": {"include": ["source_location"]},
        "parameters": {},
        "shell": "rm -rf /",
    }
    with pytest.raises(YamlCatalogError, match="unknown fields"):
        parse_rule_document(document, path=tmp_path / "bad.yaml")
