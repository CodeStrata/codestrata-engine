"""Tests for EvidenceLocation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.traceability import (
    EvidenceLocation,
    LocationKind,
    LocationPrecision,
    to_stable_dict,
)


def test_valid_repository_relative_posix_path() -> None:
    location = EvidenceLocation(path="src/app.py", line_start=10, line_end=12)
    assert location.path == "src/app.py"
    assert location.location_kind is LocationKind.FILE_SPAN


def test_normalizes_supported_separators() -> None:
    location = EvidenceLocation(path=r"src\pkg\mod.py")
    assert location.path == "src/pkg/mod.py"


def test_rejects_absolute_unix_path() -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        EvidenceLocation(path="/Users/me/repo/src/app.py")


def test_rejects_absolute_windows_path() -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        EvidenceLocation(path="C:/Users/me/repo/src/app.py")


def test_rejects_file_uri() -> None:
    with pytest.raises(ValidationError, match="file://"):
        EvidenceLocation(path="file:///tmp/secret.py")


def test_rejects_parent_traversal() -> None:
    with pytest.raises(ValidationError, match=r"\.\."):
        EvidenceLocation(path="../outside.py")


def test_valid_line_and_column_spans() -> None:
    location = EvidenceLocation(
        path="a.py",
        line_start=1,
        line_end=1,
        column_start=2,
        column_end=8,
    )
    assert location.column_end == 8


def test_rejects_reversed_line_span() -> None:
    with pytest.raises(ValidationError, match="line_end"):
        EvidenceLocation(path="a.py", line_start=5, line_end=2)


def test_rejects_partial_span() -> None:
    with pytest.raises(ValidationError, match="both be set"):
        EvidenceLocation(path="a.py", line_start=5)


def test_symbolic_only_location() -> None:
    location = EvidenceLocation(symbolic_reference="unit:payments")
    assert location.path is None
    assert location.location_kind is LocationKind.SYMBOLIC
    assert location.precision is LocationPrecision.SYMBOLIC_ONLY


def test_requires_path_or_symbolic() -> None:
    with pytest.raises(ValidationError, match="path and/or"):
        EvidenceLocation()


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceLocation(path="a.py", unexpected="x")  # type: ignore[call-arg]


def test_stable_dict_omits_empty_and_keeps_relative_path() -> None:
    payload = to_stable_dict(EvidenceLocation(path="src/a.py"))
    assert payload["path"] == "src/a.py"
    assert "line_start" not in payload
    assert not str(payload["path"]).startswith("/")
