"""Repository identity and revision contracts.

Inventory identity describes *which* repository and revision were observed.
These fields intentionally do not participate in repository *content*
fingerprints: renaming a branch or changing a clone URL must not alter the
content fingerprint used for incremental graph extraction.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType

_URL_USERINFO = re.compile(r"://[^/\s]*@")


def normalize_repository_key(value: str) -> str:
    """Normalize a stable repository key shared with Repository Graph identities.

    Callers must supply the key explicitly. Values must not embed credentials,
    URL query strings, or fragments.
    """

    key = require_nonblank(value, label="repository_key")
    if "://" in key or "@" in key:
        raise ValueError("repository_key must not contain URLs or credential material")
    if any(ch in key for ch in ("?", "#")):
        raise ValueError("repository_key must not contain query strings or fragments")
    if any(ch in key for ch in ("/", "\\", ":")):
        raise ValueError("repository_key must not contain path separators or ':' characters")
    return key


def normalize_source_location(value: str) -> str:
    """Accept a source locator while rejecting embedded credential material."""

    location = require_nonblank(value, label="source_location")
    if _URL_USERINFO.search(location):
        raise ValueError("source_location must not contain embedded credentials")
    return location


class RepositoryIdentity(BaseModel):
    """Stable identity for a source repository (scanner-independent)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_key: str
    source_type: RepositorySourceType
    display_name: str
    source_location: str | None = None

    @field_validator("repository_key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return normalize_repository_key(str(value))

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="display_name")

    @field_validator("source_location", mode="before")
    @classmethod
    def normalize_location(cls, value: object) -> str | None:
        if value is None:
            return None
        return normalize_source_location(str(value))


class RepositoryRevision(BaseModel):
    """Observed revision contract without querying Git or generating clocks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str
    revision_type: RepositoryRevisionType
    branch: str | None = None
    tag: str | None = None
    captured_at: datetime | None = None

    @field_validator("revision_id", mode="before")
    @classmethod
    def normalize_revision_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="revision_id")

    @field_validator("branch", "tag", mode="before")
    @classmethod
    def normalize_optional_refs(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional revision field")

    @field_validator("captured_at")
    @classmethod
    def require_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value
