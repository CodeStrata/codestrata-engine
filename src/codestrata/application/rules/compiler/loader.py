"""Safe YAML/JSON loader for E03.1 rule documents.

Reuses the E04.1 bounded loader (1 MiB, nesting 32, aliases off, no merge keys,
no unknown tags, no duplicate keys) and adds type and executable-string checks.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from codestrata.application.rules.composition.errors import ResolutionError
from codestrata.application.rules.composition.loader import load_document_bytes
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.rules.compiler_errors import YamlCompileError

_ALLOWED_SCALAR = (str, int, float, bool, type(None))
_EXECUTABLE_MARKERS = (
    "eval(",
    "exec(",
    "compile(",
    "__import__",
    "os.system",
    "subprocess",
    "popen(",
    "/bin/sh",
    "/bin/bash",
    "powershell",
    "cmd.exe",
    "import os",
    "import sys",
    "!!python",
    "!expr",
    "!shell",
    "javascript:",
)
_LOADER_CODE_MAP = {
    "yaml_alias": "yaml_alias",
    "yaml_merge": "yaml_merge",
    "yaml_duplicate_key": "yaml_duplicate_key",
    "yaml_tag": "yaml_unknown_tag",
    "excessive_size": "excessive_bytes",
    "excessive_depth": "excessive_nesting",
    "invalid_yaml": "invalid_yaml",
    "invalid_json": "invalid_json",
    "invalid_document": "invalid_document",
}


def load_rule_document(raw: bytes, *, label: str = "document") -> tuple[dict[str, Any], str]:
    """Load a mapping and return it with a source digest of the loaded object."""

    try:
        loaded = load_document_bytes(raw, label=label)
    except ResolutionError as error:
        raise YamlCompileError(
            str(error),
            reason_code=_LOADER_CODE_MAP.get(error.code, error.code),
        ) from error
    _assert_plain_types(loaded, path="$")
    _assert_no_executable_strings(loaded, path="$")
    return loaded, digest_canonical(loaded)


def _assert_plain_types(value: object, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise YamlCompileError(
                    f"YAML mapping keys must be strings at {path}",
                    reason_code="invalid_type",
                    details={"path": path, "key_type": type(key).__name__},
                )
            _assert_plain_types(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_plain_types(item, path=f"{path}[{index}]")
        return
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise YamlCompileError(
                f"non-finite number rejected at {path}",
                reason_code="invalid_type",
                details={"path": path},
            )
        return
    if isinstance(value, str):
        return
    if isinstance(value, (bytes, bytearray, datetime, date, set, tuple)):
        raise YamlCompileError(
            f"unsupported YAML type {type(value).__name__} at {path}",
            reason_code="invalid_type",
            details={"path": path, "python_type": type(value).__name__},
        )
    if not isinstance(value, _ALLOWED_SCALAR):
        raise YamlCompileError(
            f"unsupported YAML type {type(value).__name__} at {path}",
            reason_code="invalid_type",
            details={"path": path, "python_type": type(value).__name__},
        )


def _assert_no_executable_strings(value: object, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_executable_strings(key, path=f"{path}.@key")
            _assert_no_executable_strings(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_executable_strings(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    lowered = value.lower()
    for marker in _EXECUTABLE_MARKERS:
        if marker in lowered:
            raise YamlCompileError(
                f"executable string rejected at {path}",
                reason_code="executable_string",
                details={"path": path, "marker": marker},
            )
