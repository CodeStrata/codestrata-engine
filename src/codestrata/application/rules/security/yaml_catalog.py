"""Safe loader for the bundled security.core YAML catalog (E06.1).

This is an Engine-local catalog binder until E03.1 publishes the shared YAML
compiler. It rejects aliases, merge keys, unknown tags, duplicate keys,
executable strings and oversized documents. Rule logic lives in YAML; Python
only extracts facts and dispatches named operators.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode

from codestrata.domain.rules.enums import RuleSeverity
from codestrata.domain.security.ids import HYGIENE_RULE_IDS

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
PACK_FILENAME = "pack.yaml"
API_VERSION = "codestrata.io/rules/v1"
RULESET_API_VERSION = "codestrata.io/ruleset/v1"
MAX_RULE_BYTES = 32_768
MAX_PACK_BYTES = 32_768
MAX_NESTING = 8
ALLOWED_OPERATORS = frozenset(
    {
        "security.has_private_key_material",
        "security.credential_literal",
        "security.placeholder_credential",
        "security.tls_verification_disabled",
        "security.hostname_verification_disabled",
        "security.authentication_disabled",
        "security.permissive_cors_origin",
        "security.debug_enabled",
    }
)
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
_EXECUTABLE = re.compile(
    r"(?is)\b(eval|exec|__import__|os\.system|subprocess|importlib|"
    r"pty\.spawn|powershell|cmd\.exe|/bin/sh)\b"
)


class YamlCatalogError(ValueError):
    """Bundled YAML catalog failed validation."""


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects aliases, merge keys and unknown tags."""

    def compose_node(self, parent: Node | None, index: int) -> Node | None:
        check_event: Any = self.check_event
        if check_event(yaml.AliasEvent):
            raise YamlCatalogError("YAML aliases are not allowed")
        return super().compose_node(parent, index)


def _construct_mapping_no_duplicates(
    loader: yaml.SafeLoader, node: MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == "<<":
            raise YamlCatalogError("YAML merge keys are not allowed")
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise YamlCatalogError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


def _reject_undefined(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    tag = getattr(node, "tag", "")
    raise YamlCatalogError(f"unknown or unsupported YAML tag: {tag}")


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)
_StrictLoader.add_constructor(None, _reject_undefined)  # type: ignore[arg-type]


def load_yaml_document(text: str, *, max_bytes: int, label: str) -> dict[str, Any]:
    payload = text.encode("utf-8")
    if len(payload) > max_bytes:
        raise YamlCatalogError(f"{label} exceeds {max_bytes} bytes")
    try:
        loader = _StrictLoader(text)
        try:
            loaded = loader.get_single_data()
        finally:
            dispose: Any = loader.dispose
            dispose()
    except YamlCatalogError:
        raise
    except yaml.YAMLError as error:
        raise YamlCatalogError(f"invalid YAML in {label}: {type(error).__name__}") from error
    if not isinstance(loaded, dict):
        raise YamlCatalogError(f"{label} must be a mapping")
    _assert_bounds(loaded, depth=0, label=label)
    return loaded


def _assert_bounds(value: object, *, depth: int, label: str) -> None:
    if depth > MAX_NESTING:
        raise YamlCatalogError(f"{label} exceeds nesting depth {MAX_NESTING}")
    if isinstance(value, str):
        if _EXECUTABLE.search(value):
            raise YamlCatalogError(f"{label} contains an executable string")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise YamlCatalogError(f"{label} keys must be strings")
            _assert_bounds(item, depth=depth + 1, label=label)
        return
    if isinstance(value, list):
        for item in value:
            _assert_bounds(item, depth=depth + 1, label=label)
        return
    if value is None or isinstance(value, int | float | bool):
        return
    raise YamlCatalogError(f"{label} has unsupported YAML type {type(value).__name__}")


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_fields(document: dict[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise YamlCatalogError(f"{label} has unknown fields: {unknown}")


def parse_rule_document(document: dict[str, Any], *, path: Path) -> dict[str, Any]:
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
    if rule_id not in HYGIENE_RULE_IDS:
        raise YamlCatalogError(f"{path.name} id {rule_id!r} is not a hygiene rule")
    condition = document.get("condition")
    if not isinstance(condition, dict):
        raise YamlCatalogError(f"{path.name} condition must be a mapping")
    operator = str(condition.get("operator") or "")
    if operator not in ALLOWED_OPERATORS:
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
    return {
        "rule_id": rule_id,
        "version": str(metadata.get("version") or ""),
        "title": str(metadata.get("title") or ""),
        "description": str(message.get("template") or "").strip(),
        "category": str(metadata.get("category") or "security"),
        "owner": str(metadata.get("owner") or ""),
        "measurement": str(metadata.get("measurement") or ""),
        "operator": operator,
        "default_severity": severity,
        "remediation": str(
            finding.get("documentation_url") or "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        "documentation_url": str(
            finding.get("documentation_url") or "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        "message_template": str(message.get("template") or "").strip(),
        "languages": _languages(document),
        "source_path": str(path.as_posix()),
        "file_digest": _file_digest(path),
        "canonical_digest": _canonical_digest(document),
        "document": document,
    }


KNOWN_VULNERABILITY_RULE_ID = "security.known_vulnerability"
KNOWN_VULNERABILITY_OPERATOR = "security.known_vulnerability"
VULNERABILITY_OPERATORS = frozenset({KNOWN_VULNERABILITY_OPERATOR})
LICENSE_DISALLOWED_RULE_ID = "license.disallowed"
LICENSE_DISALLOWED_OPERATOR = "license.disallowed"
LICENSE_OPERATORS = frozenset({LICENSE_DISALLOWED_OPERATOR})


def parse_named_rule_document(
    document: dict[str, Any],
    *,
    path: Path,
    expected_id: str,
    allowed_operators: frozenset[str],
) -> dict[str, Any]:
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
    if rule_id != expected_id:
        raise YamlCatalogError(f"{path.name} id must be {expected_id}")
    condition = document.get("condition")
    if not isinstance(condition, dict):
        raise YamlCatalogError(f"{path.name} condition must be a mapping")
    operator = str(condition.get("operator") or "")
    if operator not in allowed_operators:
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
    return {
        "rule_id": rule_id,
        "version": str(metadata.get("version") or ""),
        "title": str(metadata.get("title") or ""),
        "description": str(message.get("template") or "").strip(),
        "category": str(metadata.get("category") or "security"),
        "owner": str(metadata.get("owner") or ""),
        "measurement": str(metadata.get("measurement") or ""),
        "operator": operator,
        "default_severity": severity,
        "remediation": str(
            finding.get("documentation_url") or "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        "documentation_url": str(
            finding.get("documentation_url") or "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        "message_template": str(message.get("template") or "").strip(),
        "languages": _languages(document),
        "source_path": str(path.as_posix()),
        "file_digest": _file_digest(path),
        "canonical_digest": _canonical_digest(document),
        "document": document,
    }


def parse_vulnerability_rule_document(document: dict[str, Any], *, path: Path) -> dict[str, Any]:
    return parse_named_rule_document(
        document,
        path=path,
        expected_id=KNOWN_VULNERABILITY_RULE_ID,
        allowed_operators=VULNERABILITY_OPERATORS,
    )


def parse_license_rule_document(document: dict[str, Any], *, path: Path) -> dict[str, Any]:
    return parse_named_rule_document(
        document,
        path=path,
        expected_id=LICENSE_DISALLOWED_RULE_ID,
        allowed_operators=LICENSE_OPERATORS,
    )


@lru_cache(maxsize=1)
def load_known_vulnerability_rule() -> dict[str, Any]:
    path = CATALOG_DIR / f"{KNOWN_VULNERABILITY_RULE_ID}.yaml"
    if not path.is_file():
        raise YamlCatalogError(f"missing bundled rule YAML: {path.name}")
    document = load_yaml_document(
        path.read_text(encoding="utf-8"),
        max_bytes=MAX_RULE_BYTES,
        label=path.name,
    )
    return parse_vulnerability_rule_document(document, path=path)


@lru_cache(maxsize=1)
def load_license_disallowed_rule() -> dict[str, Any]:
    path = CATALOG_DIR / f"{LICENSE_DISALLOWED_RULE_ID}.yaml"
    if not path.is_file():
        raise YamlCatalogError(f"missing bundled rule YAML: {path.name}")
    document = load_yaml_document(
        path.read_text(encoding="utf-8"),
        max_bytes=MAX_RULE_BYTES,
        label=path.name,
    )
    return parse_license_rule_document(document, path=path)


def _languages(document: dict[str, Any]) -> tuple[str, ...]:
    applies = document.get("applies_to")
    if not isinstance(applies, dict):
        return ()
    languages = applies.get("languages")
    if not isinstance(languages, list):
        return ()
    return tuple(str(item) for item in languages)


@lru_cache(maxsize=1)
def load_security_pack() -> dict[str, Any]:
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
    missing = [rule_id for rule_id in HYGIENE_RULE_IDS if rule_id not in declared]
    extra = sorted(set(declared) - set(HYGIENE_RULE_IDS))
    if missing or extra:
        raise YamlCatalogError(f"pack rule set mismatch missing={missing} extra={extra}")
    return {
        "document": pack,
        "file_digest": _file_digest(pack_path),
        "canonical_digest": _canonical_digest(pack),
        "deferred_rule_ids": tuple(str(item) for item in pack.get("deferred_rule_ids") or ()),
    }


@lru_cache(maxsize=1)
def load_security_rules() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for rule_id in HYGIENE_RULE_IDS:
        path = CATALOG_DIR / f"{rule_id}.yaml"
        if not path.is_file():
            raise YamlCatalogError(f"missing bundled rule YAML: {path.name}")
        document = load_yaml_document(
            path.read_text(encoding="utf-8"),
            max_bytes=MAX_RULE_BYTES,
            label=path.name,
        )
        loaded[rule_id] = parse_rule_document(document, path=path)
    load_security_pack()
    return loaded


def bundled_rule(rule_id: str) -> dict[str, Any]:
    rules = load_security_rules()
    try:
        return rules[rule_id]
    except KeyError as error:
        raise YamlCatalogError(f"unknown bundled rule {rule_id}") from error


def catalog_digests() -> dict[str, str]:
    rules = load_security_rules()
    pack = load_security_pack()
    vulnerability = load_known_vulnerability_rule()
    license_rule = load_license_disallowed_rule()
    return {
        "pack": pack["file_digest"],
        **{rule_id: item["file_digest"] for rule_id, item in rules.items()},
        KNOWN_VULNERABILITY_RULE_ID: vulnerability["file_digest"],
        LICENSE_DISALLOWED_RULE_ID: license_rule["file_digest"],
    }


__all__ = [
    "ALLOWED_OPERATORS",
    "CATALOG_DIR",
    "KNOWN_VULNERABILITY_OPERATOR",
    "KNOWN_VULNERABILITY_RULE_ID",
    "LICENSE_DISALLOWED_OPERATOR",
    "LICENSE_DISALLOWED_RULE_ID",
    "LICENSE_OPERATORS",
    "VULNERABILITY_OPERATORS",
    "YamlCatalogError",
    "bundled_rule",
    "catalog_digests",
    "load_known_vulnerability_rule",
    "load_license_disallowed_rule",
    "load_security_pack",
    "load_security_rules",
    "load_yaml_document",
]
