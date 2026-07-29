"""Extracted dependency facts used before Repository Graph node construction.

These models are distinct from Phase 1 ``codestrata.models.Dependency`` and from the
graph-node property bag ``DependencyProperties``.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.domain.repository_graph.enums import DependencyScope

_LEADING_VERSION = re.compile(r"^[^\d]*?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?")


class DependencyVersion(BaseModel):
    """Normalized dependency version string with lightweight parsing helpers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw: str

    @field_validator("raw", mode="before")
    @classmethod
    def normalize_raw(cls, value: object) -> str:
        return require_nonblank(str(value), label="version")

    @property
    def major(self) -> int | None:
        match = _LEADING_VERSION.match(self.raw.strip())
        if match is None:
            return None
        return int(match.group("major"))

    @property
    def minor(self) -> int | None:
        match = _LEADING_VERSION.match(self.raw.strip())
        if match is None or match.group("minor") is None:
            return None
        return int(match.group("minor"))

    def is_java_8(self) -> bool:
        compact = self.raw.strip().lower().lstrip("v")
        if compact in {"1.8", "1.8.0", "8", "8.0"}:
            return True
        return self.major == 8 and (self.minor is None or self.minor == 0)

    def is_spring_boot_2(self) -> bool:
        return self.major == 2


class Dependency(BaseModel):
    """One extracted dependency coordinate before graph materialization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ecosystem: str
    name: str
    namespace: str | None = None
    version: DependencyVersion | None = None
    scope: DependencyScope = DependencyScope.UNKNOWN
    source_file: str
    direct: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ecosystem", "name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="dependency field")

    @field_validator("namespace", mode="before")
    @classmethod
    def normalize_namespace(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="namespace")

    @field_validator("source_file", mode="before")
    @classmethod
    def normalize_source_file(cls, value: object) -> str:
        return normalize_repository_relative_path(str(value))

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a mapping")
        return dict(value)

    @property
    def version_raw(self) -> str | None:
        return None if self.version is None else self.version.raw
