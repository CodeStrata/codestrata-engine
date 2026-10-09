"""Bounded local JSON/YAML loading for Rule and RuleSet documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode

from codestrata.application.rules.composition.bounds import composition_budgets
from codestrata.application.rules.composition.errors import ResolutionError


class _StrictLoader(yaml.SafeLoader):
    def compose_node(self, parent: Node | None, index: int) -> Node | None:
        check_event: Any = self.check_event
        if check_event(yaml.AliasEvent):
            raise ResolutionError("yaml_alias", "YAML aliases are not allowed")
        return super().compose_node(parent, index)


def _construct_mapping_no_duplicates(
    loader: yaml.SafeLoader, node: MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == "<<":
            raise ResolutionError("yaml_merge", "YAML merge keys are not allowed")
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ResolutionError("yaml_duplicate_key", f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


def _reject_undefined(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    tag = getattr(node, "tag", "")
    raise ResolutionError("yaml_tag", f"unknown or unsupported YAML tag: {tag}")


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)
_StrictLoader.add_constructor(None, _reject_undefined)  # type: ignore[arg-type]


def resolve_catalog_path(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    path = candidate if candidate.is_absolute() else root_resolved / candidate
    resolved = path.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as error:
        raise ResolutionError("path_escape", f"path {candidate} escapes catalog root") from error
    return resolved


def load_document_bytes(raw: bytes, *, label: str) -> dict[str, Any]:
    _parent_depth, _max_rules, max_bytes, max_nesting = composition_budgets()
    if len(raw) > max_bytes:
        raise ResolutionError("excessive_size", f"{label} exceeds {max_bytes} bytes")
    text = raw.decode("utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as error:
            raise ResolutionError("invalid_json", f"{label} is not valid JSON") from error
    else:
        loaded = _load_yaml(text, label=label)
    if not isinstance(loaded, dict):
        raise ResolutionError("invalid_document", f"{label} must be a mapping")
    _assert_nesting(loaded, depth=0, limit=max_nesting, label=label)
    return loaded


def load_document_file(path: Path, *, root: Path) -> dict[str, Any]:
    resolved = resolve_catalog_path(root, path)
    if not resolved.is_file():
        raise ResolutionError("missing_file", f"missing catalog file {resolved}")
    return load_document_bytes(resolved.read_bytes(), label=str(resolved.name))


def _load_yaml(text: str, *, label: str) -> object:
    try:
        loader = _StrictLoader(text)
        try:
            return loader.get_single_data()
        finally:
            dispose: Any = loader.dispose
            dispose()
    except ResolutionError:
        raise
    except yaml.YAMLError as error:
        raise ResolutionError("invalid_yaml", f"invalid YAML in {label}") from error


def _assert_nesting(value: object, *, depth: int, limit: int, label: str) -> None:
    if depth > limit:
        raise ResolutionError("excessive_depth", f"{label} exceeds YAML nesting {limit}")
    if isinstance(value, dict):
        for item in value.values():
            _assert_nesting(item, depth=depth + 1, limit=limit, label=label)
        return
    if isinstance(value, list):
        for item in value:
            _assert_nesting(item, depth=depth + 1, limit=limit, label=label)
