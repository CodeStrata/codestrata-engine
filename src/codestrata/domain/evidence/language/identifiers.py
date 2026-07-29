"""Stable identifiers for language evidence providers."""

from __future__ import annotations

import hashlib
import re

from pydantic import RootModel, field_validator

_PROVIDER_ID_PATTERN = re.compile(r"^language\.[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)*$")
_CAPABILITY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$")


def validate_provider_id(value: str) -> str:
    compact = value.strip().lower()
    if not _PROVIDER_ID_PATTERN.fullmatch(compact):
        raise ValueError(
            "provider_id must look like language.<name>[.<qualifier>] "
            "(example: language.python.core)"
        )
    return compact


def validate_capability_id(value: str) -> str:
    compact = value.strip().lower()
    if not _CAPABILITY_ID_PATTERN.fullmatch(compact):
        raise ValueError(
            "capability_id must use dotted kebab form "
            "(example: dependencies.imports)"
        )
    return compact


def stable_evidence_id(*parts: str) -> str:
    """Deterministic evidence identity from stable parts (no timestamps/UUIDs)."""

    payload = "\n".join(part.strip().lower() for part in parts if part and part.strip())
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"ev:{digest}"


class LanguageEvidenceProviderId(RootModel[str]):
    root: str

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value: object) -> str:
        return validate_provider_id(str(value))

    def __str__(self) -> str:
        return self.root


class EvidenceCapabilityId(RootModel[str]):
    root: str

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value: object) -> str:
        return validate_capability_id(str(value))

    def __str__(self) -> str:
        return self.root
