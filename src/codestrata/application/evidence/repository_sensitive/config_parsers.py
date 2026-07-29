"""Conservative configuration parsers for repository-sensitive evidence."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import PurePosixPath

from codestrata.application.evidence.repository_sensitive.keys import (
    classify_key_family,
    is_explicit_wildcard_origin,
    is_security_relevant_key,
    is_sensitive_literal_key,
    normalize_key,
    parse_literal_boolean,
    value_looks_like_http_endpoint,
)
from codestrata.application.evidence.repository_sensitive.values import value_facts
from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationFormat,
    ConfigurationKeyFamily,
    ValueKind,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def detect_format(path: str) -> ConfigurationFormat:
    name = PurePosixPath(path).name.lower()
    suffix = PurePosixPath(path).suffix.lower()
    if name.startswith(".env") or name in {".npmrc", ".netrc", ".pypirc"}:
        return ConfigurationFormat.DOTENV
    if suffix == ".properties" or name == "credentials":
        return ConfigurationFormat.PROPERTIES
    if suffix in {".yml", ".yaml"}:
        return ConfigurationFormat.YAML
    if suffix == ".json":
        return ConfigurationFormat.JSON
    if suffix == ".toml":
        return ConfigurationFormat.TOML
    if name.endswith(".properties"):
        return ConfigurationFormat.PROPERTIES
    return ConfigurationFormat.UNKNOWN


def _emit(
    *,
    key: str,
    value: str,
    section: str | None,
    line: int | None,
) -> dict[str, object] | None:
    if not is_security_relevant_key(key) and not value_looks_like_http_endpoint(value):
        return None
    family = classify_key_family(key)
    sensitive = is_sensitive_literal_key(key) or "password" in value.lower()
    if value_looks_like_http_endpoint(value) and value.strip().lower().startswith(
        "http://"
    ):
        # Collect plaintext HTTP endpoints as non-secret policy facts.
        sensitive = False
        if family is ConfigurationKeyFamily.UNKNOWN:
            family = ConfigurationKeyFamily.OTHER
    facts = value_facts(value, sensitive=sensitive)
    literal_boolean = None
    if facts["value_kind"] is ValueKind.BOOLEAN:
        literal_boolean = parse_literal_boolean(value)
    wildcard = (
        family is ConfigurationKeyFamily.CORS_ORIGIN
        and is_explicit_wildcard_origin(value)
    )
    return {
        "normalized_key": normalize_key(key),
        "key_family": family,
        "section": section,
        "line_start": line,
        "literal_boolean": literal_boolean,
        "is_wildcard_origin": wildcard,
        **facts,
    }


def parse_dotenv(text: str) -> tuple[list[dict[str, object]], list[str]]:
    facts: list[dict[str, object]] = []
    diagnostics: list[str] = []
    for index, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        item = _emit(key=key, value=value, section=None, line=index)
        if item:
            facts.append(item)
    return facts, diagnostics


_PROP_LINE = re.compile(r"^\s*([^#!=\s][^=]*?)\s*=\s*(.*)$")


def parse_properties(text: str) -> tuple[list[dict[str, object]], list[str]]:
    facts: list[dict[str, object]] = []
    diagnostics: list[str] = []
    for index, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        match = _PROP_LINE.match(raw)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        item = _emit(key=key, value=value, section=None, line=index)
        if item:
            facts.append(item)
    return facts, diagnostics


def _walk_mapping(
    data: object,
    *,
    prefix: str = "",
    section: str | None = None,
) -> Iterator[tuple[str, str, str | None]]:
    if isinstance(data, dict):
        for key, value in data.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            next_section = section or (key_text if not prefix else section)
            if isinstance(value, (dict, list)):
                yield from _walk_mapping(value, prefix=path, section=next_section)
            else:
                yield path, "" if value is None else str(value), next_section
    elif isinstance(data, list):
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]"
            if isinstance(value, (dict, list)):
                yield from _walk_mapping(value, prefix=path, section=section)
            else:
                yield path, "" if value is None else str(value), section


def parse_json(text: str) -> tuple[list[dict[str, object]], list[str]]:
    facts: list[dict[str, object]] = []
    diagnostics: list[str] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        diagnostics.append(f"malformed_json:{error.msg}")
        return facts, diagnostics
    for key, value, section in _walk_mapping(data):
        item = _emit(key=key, value=value, section=section, line=None)
        if item:
            facts.append(item)
    return facts, diagnostics


def parse_toml(text: str) -> tuple[list[dict[str, object]], list[str]]:
    facts: list[dict[str, object]] = []
    diagnostics: list[str] = []
    try:
        data = tomllib.loads(text)
    except Exception as error:  # noqa: BLE001 - bounded diagnostic
        diagnostics.append(f"malformed_toml:{type(error).__name__}")
        return facts, diagnostics
    for key, value, section in _walk_mapping(data):
        item = _emit(key=key, value=value, section=section, line=None)
        if item:
            facts.append(item)
    return facts, diagnostics


def parse_yaml(text: str) -> tuple[list[dict[str, object]], list[str]]:
    facts: list[dict[str, object]] = []
    diagnostics: list[str] = []
    if yaml is None:
        diagnostics.append("yaml_parser_unavailable")
        return facts, diagnostics
    try:
        data = yaml.safe_load(text)
    except Exception as error:  # noqa: BLE001 - bounded diagnostic
        diagnostics.append(f"malformed_yaml:{type(error).__name__}")
        return facts, diagnostics
    if data is None:
        return facts, diagnostics
    for key, value, section in _walk_mapping(data):
        item = _emit(key=key, value=value, section=section, line=None)
        if item:
            facts.append(item)
    return facts, diagnostics


def parse_configuration(
    path: str, text: str
) -> tuple[ConfigurationFormat, list[dict[str, object]], list[str]]:
    fmt = detect_format(path)
    if fmt is ConfigurationFormat.DOTENV:
        facts, diagnostics = parse_dotenv(text)
    elif fmt is ConfigurationFormat.PROPERTIES:
        facts, diagnostics = parse_properties(text)
    elif fmt is ConfigurationFormat.JSON:
        facts, diagnostics = parse_json(text)
    elif fmt is ConfigurationFormat.TOML:
        facts, diagnostics = parse_toml(text)
    elif fmt is ConfigurationFormat.YAML:
        facts, diagnostics = parse_yaml(text)
    else:
        # Attempt dotenv-style for unknown text credential files.
        facts, diagnostics = parse_dotenv(text)
        fmt = ConfigurationFormat.DOTENV
    return fmt, facts, diagnostics
