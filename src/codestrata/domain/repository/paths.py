"""Canonical repository-relative path value object.

``RepositoryPath`` is the single normalization authority for inventory paths and
Repository Graph file identities. The repository root is not represented as a
path entry: ``\".\"`` is invalid.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from pydantic import ConfigDict, RootModel, model_validator

from codestrata.domain.graph.validation import require_nonblank

_ABSOLUTE_WINDOWS = re.compile(r"^[A-Za-z]:[/\\]")


def normalize_repository_relative_path(value: str) -> str:
    """Normalize a repository-relative POSIX path without filesystem access."""

    raw = require_nonblank(value, label="path")
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or _ABSOLUTE_WINDOWS.match(normalized):
        raise ValueError("path must be repository-relative, not absolute")

    path = PurePosixPath(normalized)
    parts = path.parts
    if not parts or parts == (".",):
        raise ValueError("path must not be blank after normalization")
    if any(part == ".." for part in parts):
        raise ValueError("path must not contain '..' traversal segments")

    cleaned_parts = [part for part in parts if part not in ("", ".")]
    if not cleaned_parts:
        raise ValueError("path must not be blank after normalization")
    return "/".join(cleaned_parts)


class RepositoryPath(RootModel[str]):
    """Frozen value object for a normalized repository-relative file path."""

    model_config = ConfigDict(frozen=True)

    root: str

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: Any) -> str:
        if isinstance(value, RepositoryPath):
            return value.root
        if isinstance(value, RootModel):
            value = value.root
        if not isinstance(value, str):
            raise ValueError("RepositoryPath must be a string")
        return normalize_repository_relative_path(value)

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return f"RepositoryPath({self.root!r})"

    def __lt__(self, other: object) -> bool:
        if isinstance(other, RepositoryPath):
            return self.root < other.root
        if isinstance(other, str):
            return self.root < other
        return NotImplemented
