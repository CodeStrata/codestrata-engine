"""Safety and package-boundary tests for domain.traceability."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.domain.traceability import (
    EvidenceLocation,
    EvidenceRef,
    evidence_ref_to_stable_dict,
    to_stable_dict,
)

_PACKAGE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "codestrata"
    / "domain"
    / "traceability"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "codestrata.application",
    "codestrata.reporting",
    "codestrata.interfaces",
    "codestrata.ai",
    "codestrata_platform",
)


def test_no_absolute_path_survives_serialization() -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        EvidenceLocation(path="/etc/passwd")
    ref = EvidenceRef(
        evidence_id="ev:safe",
        location=EvidenceLocation(path="src/ok.py"),
    )
    payload = evidence_ref_to_stable_dict(ref)
    assert not str(payload["location"]["path"]).startswith("/")
    assert "file:" not in str(payload).lower()


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceRef(evidence_id="ev:1", not_a_field=True)  # type: ignore[call-arg]


def test_package_remains_domain_layer_only() -> None:
    assert _PACKAGE.is_dir()
    for path in sorted(_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                        assert not alias.name.startswith(prefix), path
            elif isinstance(node, ast.ImportFrom) and node.module:
                for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                    assert not node.module.startswith(prefix), path


def test_stable_dict_key_order() -> None:
    payload = to_stable_dict(EvidenceLocation(path="a/b.py", line_start=1, line_end=2))
    assert list(payload.keys()) == sorted(payload.keys())
