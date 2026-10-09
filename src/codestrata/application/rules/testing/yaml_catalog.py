"""Safe loader for the bundled testing.core YAML catalog (E08.2)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from codestrata.application.rules.security.yaml_catalog import (
    API_VERSION,
    MAX_PACK_BYTES,
    MAX_RULE_BYTES,
    RULESET_API_VERSION,
    YamlCatalogError,
    load_yaml_document,
)
from codestrata.application.rules.technical_debt.yaml_catalog import quality_catalog_digests
from codestrata.domain.rules.enums import RuleSeverity

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
PACK_FILENAME = "pack.yaml"
TESTING_RULE_IDS: tuple[str, ...] = (
    "testing.disabled",
    "testing.ci_gap",
    "testing.test-001",
    "testing.test-002",
    "testing.test-003",
    "testing.test-005",
)
ALLOWED_OPERATORS = frozenset(TESTING_RULE_IDS)
_RULE_FIELDS = frozenset(
    {
        "api_version",
        "kind",
        "metadata",
        "applies_to",
        "select",
        "condition",
        "emit",
        "evidence",
        "parameters",
    }
)
_METADATA_FIELDS = frozenset(
    {
        "id",
        "version",
        "title",
        "category",
        "owner",
        "measurement",
        "tags",
    }
)


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_fields(document: dict[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise YamlCatalogError(f"{label} has unknown fields: {unknown}")


def _languages(document: dict[str, Any]) -> tuple[str, ...]:
    applies = document.get("applies_to")
    if not isinstance(applies, dict):
        return ()
    languages = applies.get("languages")
    if not isinstance(languages, list):
        return ()
    return tuple(str(item) for item in languages)


def parse_testing_rule_document(document: dict[str, Any], *, path: Path) -> dict[str, Any]:
    _require_fields(document, _RULE_FIELDS, path.name)
    if document.get("api_version") != API_VERSION:
        raise YamlCatalogError(f"{path.name} api_version must be {API_VERSION}")
    if document.get("kind") != "Rule":
        raise YamlCatalogError(f"{path.name} kind must be Rule")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise YamlCatalogError(f"{path.name} metadata must be a mapping")
    _require_fields(metadata, _METADATA_FIELDS, f"{path.name}.metadata")
    rule_id = str(metadata.get("id") or "")
    if rule_id not in TESTING_RULE_IDS:
        raise YamlCatalogError(f"{path.name} id {rule_id!r} is not a testing rule")
    condition = document.get("condition")
    if not isinstance(condition, dict):
        raise YamlCatalogError(f"{path.name} condition must be a mapping")
    operator = str(condition.get("operator") or "")
    if operator != rule_id or operator not in ALLOWED_OPERATORS:
        raise YamlCatalogError(f"{path.name} operator {operator!r} is not allowlisted")
    emit = document.get("emit")
    if not isinstance(emit, dict) or not isinstance(emit.get("finding"), dict):
        raise YamlCatalogError(f"{path.name} emit.finding is required")
    finding = emit["finding"]
    severity_text = str(finding.get("default_severity") or "")
    try:
        severity = RuleSeverity(severity_text)
    except ValueError as error:
        raise YamlCatalogError(
            f"{path.name} default_severity {severity_text!r} is invalid"
        ) from error
    message = finding.get("message")
    if not isinstance(message, dict) or not str(message.get("template") or "").strip():
        raise YamlCatalogError(f"{path.name} emit.finding.message.template is required")
    parameters = document.get("parameters")
    if parameters is not None and not isinstance(parameters, dict):
        raise YamlCatalogError(f"{path.name} parameters must be a mapping")
    return {
        "rule_id": rule_id,
        "version": str(metadata.get("version") or ""),
        "title": str(metadata.get("title") or ""),
        "description": str(message.get("template") or "").strip(),
        "category": str(metadata.get("category") or "testing"),
        "owner": str(metadata.get("owner") or ""),
        "measurement": str(metadata.get("measurement") or ""),
        "operator": operator,
        "default_severity": severity,
        "documentation_url": str(
            finding.get("documentation_url")
            or "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        "message_template": str(message.get("template") or "").strip(),
        "languages": _languages(document),
        "parameters": parameters or {},
        "source_path": str(path.as_posix()),
        "file_digest": _file_digest(path),
        "canonical_digest": _canonical_digest(document),
        "document": document,
    }


@lru_cache(maxsize=1)
def load_testing_pack() -> dict[str, Any]:
    pack_path = CATALOG_DIR / PACK_FILENAME
    if not pack_path.is_file():
        raise YamlCatalogError(f"missing bundled pack at {pack_path}")
    pack = load_yaml_document(
        pack_path.read_text(encoding="utf-8"),
        max_bytes=MAX_PACK_BYTES,
        label=PACK_FILENAME,
    )
    if pack.get("api_version") != RULESET_API_VERSION:
        raise YamlCatalogError("pack api_version mismatch")
    if pack.get("kind") != "RuleSet":
        raise YamlCatalogError("pack kind must be RuleSet")
    declared = pack.get("rules")
    if not isinstance(declared, dict):
        raise YamlCatalogError("pack.rules must be a mapping")
    missing = [rule_id for rule_id in TESTING_RULE_IDS if rule_id not in declared]
    extra = sorted(set(declared) - set(TESTING_RULE_IDS))
    if missing or extra:
        raise YamlCatalogError(f"pack rule set mismatch missing={missing} extra={extra}")
    return {
        "document": pack,
        "file_digest": _file_digest(pack_path),
        "canonical_digest": _canonical_digest(pack),
        "deferred_rule_ids": tuple(str(item) for item in pack.get("deferred_rule_ids") or ()),
    }


@lru_cache(maxsize=1)
def load_testing_rules() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for rule_id in TESTING_RULE_IDS:
        path = CATALOG_DIR / f"{rule_id}.yaml"
        if not path.is_file():
            raise YamlCatalogError(f"missing bundled rule YAML: {path.name}")
        document = load_yaml_document(
            path.read_text(encoding="utf-8"),
            max_bytes=MAX_RULE_BYTES,
            label=path.name,
        )
        loaded[rule_id] = parse_testing_rule_document(document, path=path)
    load_testing_pack()
    return loaded


def bundled_testing_rule(rule_id: str) -> dict[str, Any]:
    rules = load_testing_rules()
    try:
        return rules[rule_id]
    except KeyError as error:
        raise YamlCatalogError(f"unknown bundled rule {rule_id}") from error


def testing_catalog_digests() -> dict[str, str]:
    rules = load_testing_rules()
    pack = load_testing_pack()
    quality = quality_catalog_digests()
    return {
        "pack": pack["file_digest"],
        **{rule_id: item["file_digest"] for rule_id, item in rules.items()},
        "quality.test_association": quality["quality.test_association"],
        "quality.pack": quality["pack"],
    }


__all__ = [
    "ALLOWED_OPERATORS",
    "CATALOG_DIR",
    "TESTING_RULE_IDS",
    "YamlCatalogError",
    "bundled_testing_rule",
    "load_testing_pack",
    "load_testing_rules",
    "parse_testing_rule_document",
    "testing_catalog_digests",
]
